"""Combat resolution rules and Classic Dish round resolver for BLADE ARENA.

Provides pure, deterministic, simultaneous round resolution including:
- Authoritative action legality validation before execution.
- Common pre-round movement execution (Module 6).
- Post-movement hit range detection and dodge evasion checks.
- Damage and knockback push calculations scaled by attacker power and defender stance.
- Normal attack on Guard recoil (3.0 stability) and Special Spin self-recoil (10.0 stability).
- Simultaneous push vector application without player priority.
- Action recoveries (Charge energy, Guard stability) capped at archetype maximums.
- Passive round energy loss per archetype.
- Resource bounds clamping (energy >= 0, stability >= 0).
- Special Spin cooldown progression (elapsed_game_time + 3.0s).
- Idempotent stadium shrinking schedule (Module 6).
- Round advancement by exactly 1 round.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional, Tuple

from blade_arena.game.actions import check_action_legality
from blade_arena.game.blade_definitions import get_blade_definition
from blade_arena.game.stadium_definitions import get_stadium_definition
from blade_arena.game.geometry import (
    DEFAULT_ARENA_CENTER,
    DEFAULT_GEOMETRY_EPSILON,
    calculate_stadium_radius,
    distance,
    vector_length,
)
from blade_arena.game.models import (
    Action,
    BladeState,
    MatchState,
    MatchStatus,
    Position,
    StadiumState,
)
from blade_arena.game.movement import (
    PLAYER_1_DEFAULT_FORWARD,
    PLAYER_2_DEFAULT_FORWARD,
    calculate_planned_movement,
)
from blade_arena.game.win_conditions import evaluate_match_termination


class IllegalRoundResolutionError(ValueError):
    """Raised when round resolution is attempted with one or more illegal actions."""

    pass


# ==============================================================================
# PROPOSED COMBAT TUNING SPECIFICATION
# All values are proposed baseline calibrations, central and immutable.
# ==============================================================================
@dataclass(frozen=True)
class CombatConfig:
    """Immutable combat parameter tuning for Classic Dish battles."""

    # Normal Attack baseline
    normal_attack_damage: float = 12.0
    normal_attack_push: float = 1.2
    normal_attack_hit_range: float = 1.2

    # Special Spin baseline
    special_spin_damage: float = 25.0
    special_spin_push: float = 2.0
    special_spin_hit_range: float = 1.2
    special_spin_self_recoil: float = 10.0
    special_spin_cooldown_seconds: float = 3.0

    # Defender Stance Modifiers
    charging_defender_damage_multiplier: float = 1.25
    charging_defender_push_multiplier: float = 1.25

    guard_normal_damage_multiplier: float = 0.50
    guard_normal_push_multiplier: float = 0.50
    guard_special_damage_multiplier: float = 0.70
    guard_special_push_multiplier: float = 0.70

    # Guard Counter-Recoil to Attacker (Normal Attack only)
    guard_attacker_recoil_normal_attack: float = 3.0

    # Comparison tolerance
    hit_range_tolerance: float = DEFAULT_GEOMETRY_EPSILON

    def __post_init__(self) -> None:
        numeric_fields = [
            ("normal_attack_damage", self.normal_attack_damage),
            ("normal_attack_push", self.normal_attack_push),
            ("normal_attack_hit_range", self.normal_attack_hit_range),
            ("special_spin_damage", self.special_spin_damage),
            ("special_spin_push", self.special_spin_push),
            ("special_spin_hit_range", self.special_spin_hit_range),
            ("special_spin_self_recoil", self.special_spin_self_recoil),
            ("special_spin_cooldown_seconds", self.special_spin_cooldown_seconds),
            ("charging_defender_damage_multiplier", self.charging_defender_damage_multiplier),
            ("charging_defender_push_multiplier", self.charging_defender_push_multiplier),
            ("guard_normal_damage_multiplier", self.guard_normal_damage_multiplier),
            ("guard_normal_push_multiplier", self.guard_normal_push_multiplier),
            ("guard_special_damage_multiplier", self.guard_special_damage_multiplier),
            ("guard_special_push_multiplier", self.guard_special_push_multiplier),
            ("guard_attacker_recoil_normal_attack", self.guard_attacker_recoil_normal_attack),
            ("hit_range_tolerance", self.hit_range_tolerance),
        ]
        for name, val in numeric_fields:
            if isinstance(val, bool) or not isinstance(val, (int, float)):
                raise TypeError(f"{name} must be numeric, got {type(val).__name__}")
            if not math.isfinite(val) or val < 0.0:
                raise ValueError(f"{name} must be finite and non-negative, got {val}")


DEFAULT_COMBAT_CONFIG: CombatConfig = CombatConfig()


@dataclass(frozen=True)
class BladeRoundAudit:
    """Detailed audit record of effects applied to a single blade during round resolution."""

    player_id: str
    action: Action
    start_position: Position
    post_movement_position: Position
    final_position: Position
    dodge_success: bool
    attack_attempted: bool
    attack_hit: bool
    stability_damage_dealt: float
    stability_damage_received: float
    push_magnitude_received: float
    self_recoil_suffered: float
    guard_recoil_suffered: float
    energy_spent: float
    energy_recovered: float
    stability_recovered: float
    passive_energy_lost: float


@dataclass(frozen=True)
class RoundCombatEvents:
    """Audit bundle documenting all simultaneous events that transpired in a resolved round."""

    round_number: int
    player_1_audit: BladeRoundAudit
    player_2_audit: BladeRoundAudit
    stadium_radius_before: float
    stadium_radius_after: float


def determine_hit(
    attacker_action: Action,
    dist_post: float,
    defender_action: Action,
    defender_dodge_success: bool,
    config: CombatConfig = DEFAULT_COMBAT_CONFIG,
) -> bool:
    """Determine whether an attacker's action successfully lands a hit on the defender.

    Rules:
    - Only ATTACK and SPECIAL_SPIN are offensive attacks.
    - Hit range is checked after planned movements (before knockback pushes).
    - If the defender chose DODGE and dodge_success is True, incoming attacks miss.
    - If in range and not evaded by successful dodge, the attack hits.

    Args:
        attacker_action: Action chosen by attacking blade.
        dist_post: Distance between combatants after movement.
        defender_action: Action chosen by defending blade.
        defender_dodge_success: Whether defending blade successfully executed dodge.
        config: Combat tuning configuration.

    Returns:
        True if the attack hits, False otherwise.
    """
    if attacker_action not in (Action.ATTACK, Action.SPECIAL_SPIN):
        return False

    hit_range = (
        config.normal_attack_hit_range
        if attacker_action == Action.ATTACK
        else config.special_spin_hit_range
    )

    if dist_post > hit_range + config.hit_range_tolerance:
        return False

    # Evaded by successful dodge
    if defender_action == Action.DODGE and defender_dodge_success:
        return False

    return True


def calculate_hit_effects(
    attacker_action: Action,
    attacker_power: float,
    defender_action: Action,
    config: CombatConfig = DEFAULT_COMBAT_CONFIG,
) -> Tuple[float, float, float]:
    """Calculate outgoing stability damage, push magnitude, and attacker recoil for a landed hit.

    Args:
        attacker_action: ATTACK or SPECIAL_SPIN.
        attacker_power: Attack power multiplier from attacker's BladeDefinition.
        defender_action: Action chosen by defender (CHARGE, GUARD, ATTACK, DODGE, SPECIAL_SPIN).
        config: Combat tuning configuration.

    Returns:
        A 3-tuple:
        - stability_damage: Applied to defender (scaled by power and defender stance).
        - push_magnitude: Applied to defender (scaled by defender stance, NOT by power).
        - attacker_recoil: Applied to attacker (e.g. 3.0 if Normal Attack hits Guard).
    """
    if attacker_action == Action.ATTACK:
        base_damage = config.normal_attack_damage
        base_push = config.normal_attack_push
    elif attacker_action == Action.SPECIAL_SPIN:
        base_damage = config.special_spin_damage
        base_push = config.special_spin_push
    else:
        return (0.0, 0.0, 0.0)

    # Defender Stance Modifiers
    if defender_action == Action.CHARGE:
        dmg_mult = config.charging_defender_damage_multiplier
        push_mult = config.charging_defender_push_multiplier
        attacker_recoil = 0.0
    elif defender_action == Action.GUARD:
        if attacker_action == Action.ATTACK:
            dmg_mult = config.guard_normal_damage_multiplier
            push_mult = config.guard_normal_push_multiplier
            attacker_recoil = config.guard_attacker_recoil_normal_attack
        else:  # SPECIAL_SPIN
            dmg_mult = config.guard_special_damage_multiplier
            push_mult = config.guard_special_push_multiplier
            attacker_recoil = 0.0
    else:
        dmg_mult = 1.0
        push_mult = 1.0
        attacker_recoil = 0.0

    # Blade power multiplier scales stability damage only; push is unscaled by power
    damage = base_damage * attacker_power * dmg_mult
    push = base_push * push_mult
    return (damage, push, attacker_recoil)


def calculate_push_vector(
    attacker_post: Position,
    defender_post: Position,
    attacker_pre: Position,
    defender_pre: Position,
    push_magnitude: float,
    default_fallback: Tuple[float, float],
    tolerance: float = DEFAULT_GEOMETRY_EPSILON,
) -> Tuple[float, float]:
    """Calculate knockback displacement vector applied to the defender.

    Direction logic:
    1. Points from attacker toward defender using post-movement positions.
    2. If post-movement positions coincide, uses pre-movement relative direction.
    3. If pre-movement positions also coincide, uses default_fallback.

    Args:
        attacker_post: Post-movement position of attacker.
        defender_post: Post-movement position of defender.
        attacker_pre: Pre-movement position of attacker.
        defender_pre: Pre-movement position of defender.
        push_magnitude: Scalar push distance in arena units.
        default_fallback: Fallback unit direction vector.
        tolerance: Numerical threshold for zero-length detection.

    Returns:
        Displacement tuple (dx, dy) to add to defender's post-movement position.
    """
    if push_magnitude <= tolerance:
        return (0.0, 0.0)

    dx_post = defender_post.x - attacker_post.x
    dy_post = defender_post.y - attacker_post.y
    len_post = math.hypot(dx_post, dy_post)

    if len_post > tolerance:
        ux = dx_post / len_post
        uy = dy_post / len_post
        return (push_magnitude * ux, push_magnitude * uy)

    # Post-movement positions coincide; attempt pre-movement direction
    dx_pre = defender_pre.x - attacker_pre.x
    dy_pre = defender_pre.y - attacker_pre.y
    len_pre = math.hypot(dx_pre, dy_pre)

    if len_pre > tolerance:
        ux = dx_pre / len_pre
        uy = dy_pre / len_pre
        return (push_magnitude * ux, push_magnitude * uy)

    # Coincident in both; use stable fallback
    fb_len = math.hypot(default_fallback[0], default_fallback[1])
    ux = default_fallback[0] / fb_len
    uy = default_fallback[1] / fb_len
    return (push_magnitude * ux, push_magnitude * uy)


def resolve_combat_round(
    state: MatchState,
    player_1_action: Action,
    player_2_action: Action,
    config: CombatConfig = DEFAULT_COMBAT_CONFIG,
) -> Tuple[MatchState, RoundCombatEvents]:
    """Execute authoritative simultaneous round resolution for Classic Dish arena.

    Execution Stages:
    1. Authoritative Action Legality Pre-Check:
       Both actions are checked against pre-round state. If either action is illegal,
       raises IllegalRoundResolutionError without state mutation.
    2. Simultaneous Movement & Dodge Evasion:
       Calculates post-movement positions and dodge success flags simultaneously from
       pre-round positions using Module 6 rules.
    3. Intermediate Clash & Hit Detection:
       Measures post-movement distance (before knockback pushes) to determine hits.
       Successful dodge evades attacks.
    4. Hit Effects & Counter-Recoil:
       Calculates stability damage, push magnitudes, and guard counter-recoils.
    5. Knockback Displacements:
       Applies push vectors simultaneously to post-movement positions.
    6. Resource Progression:
       - Subtracts action energy costs.
       - Applies Charge/Guard recoveries (capped at archetype maximums).
       - Applies hit damage, self-recoil (Special Spin: 10), and Guard counter-recoil.
       - Applies archetype passive energy loss.
       - Clamps residual energy and stability at 0.0 minimum.
       - Updates Special Spin ready timestamp (elapsed_game_time + 3.0s).
    7. Stadium Shrink & Advancement:
       Idempotently updates stadium radius after every 6th completed round, and
       increments completed_rounds by exactly 1. Match status remains IN_PROGRESS.

    Args:
        state: Pre-round immutable MatchState.
        player_1_action: Action chosen by Player 1.
        player_2_action: Action chosen by Player 2.
        config: Combat configuration parameters.

    Returns:
        A 2-tuple:
        - next_state: New immutable MatchState with completed_rounds incremented by 1.
        - events: RoundCombatEvents detailing all round telemetry.
    """
    if not isinstance(state, MatchState):
        raise TypeError(f"state must be MatchState, got {type(state).__name__}")
    if state.status == MatchStatus.FINISHED:
        raise IllegalRoundResolutionError("Cannot resolve round: match is already finished")
    if not isinstance(player_1_action, Action):
        raise TypeError(f"player_1_action must be an Action enum, got {type(player_1_action).__name__}")
    if not isinstance(player_2_action, Action):
        raise TypeError(f"player_2_action must be an Action enum, got {type(player_2_action).__name__}")

    p1_blade = state.player_1_blade
    p2_blade = state.player_2_blade
    p1_id = p1_blade.player_id
    p2_id = p2_blade.player_id

    # --------------------------------------------------------------------------
    # 1. Authoritative Legality Pre-Check
    # --------------------------------------------------------------------------
    p1_legality = check_action_legality(state, p1_id, player_1_action)
    if not p1_legality.is_legal:
        raise IllegalRoundResolutionError(
            f"Player 1 ('{p1_id}') action {player_1_action.name} is illegal: {p1_legality.reason}"
        )

    p2_legality = check_action_legality(state, p2_id, player_2_action)
    if not p2_legality.is_legal:
        raise IllegalRoundResolutionError(
            f"Player 2 ('{p2_id}') action {player_2_action.name} is illegal: {p2_legality.reason}"
        )

    # Retrieve archetype definitions for power multipliers, recoveries, and passive loss
    p1_def = get_blade_definition(p1_blade.blade_type)
    p2_def = get_blade_definition(p2_blade.blade_type)
    stadium_def = get_stadium_definition(state.stadium.stadium_type)

    # --------------------------------------------------------------------------
    # 2. Simultaneous Movement & Dodge Evasion Evaluation
    # --------------------------------------------------------------------------
    planned_moves = calculate_planned_movement(
        blade_1=p1_blade,
        action_1=player_1_action,
        blade_2=p2_blade,
        action_2=player_2_action,
        radius=state.stadium.radius,
        fallback_1=PLAYER_1_DEFAULT_FORWARD,
        fallback_2=PLAYER_2_DEFAULT_FORWARD,
        center=state.stadium.center,
        tolerance=config.hit_range_tolerance,
        stadium_type=state.stadium.stadium_type,
    )

    p1_post_pos = planned_moves.player_1_position
    p2_post_pos = planned_moves.player_2_position
    p1_dodge_success = planned_moves.player_1_dodge_success
    p2_dodge_success = planned_moves.player_2_dodge_success

    # Post-movement distance before knockback pushes
    dist_post = distance(p1_post_pos, p2_post_pos)

    # --------------------------------------------------------------------------
    # 3. Hit Detection (Simultaneous Evaluation)
    # --------------------------------------------------------------------------
    p1_hits = determine_hit(
        attacker_action=player_1_action,
        dist_post=dist_post,
        defender_action=player_2_action,
        defender_dodge_success=p2_dodge_success,
        config=config,
    )

    p2_hits = determine_hit(
        attacker_action=player_2_action,
        dist_post=dist_post,
        defender_action=player_1_action,
        defender_dodge_success=p1_dodge_success,
        config=config,
    )

    # --------------------------------------------------------------------------
    # 4. Damage, Push, and Guard Counter-Recoil
    # --------------------------------------------------------------------------
    if p1_hits:
        p1_dmg_dealt, p2_push_mag, p1_guard_recoil = calculate_hit_effects(
            attacker_action=player_1_action,
            attacker_power=p1_def.attack_power_multiplier,
            defender_action=player_2_action,
            config=config,
        )
        p2_push_mag = p2_push_mag * stadium_def.push_multiplier
    else:
        p1_dmg_dealt, p2_push_mag, p1_guard_recoil = 0.0, 0.0, 0.0

    if p2_hits:
        p2_dmg_dealt, p1_push_mag, p2_guard_recoil = calculate_hit_effects(
            attacker_action=player_2_action,
            attacker_power=p2_def.attack_power_multiplier,
            defender_action=player_1_action,
            config=config,
        )
        p1_push_mag = p1_push_mag * stadium_def.push_multiplier
    else:
        p2_dmg_dealt, p1_push_mag, p2_guard_recoil = 0.0, 0.0, 0.0

    # --------------------------------------------------------------------------
    # 5. Knockback Displacements (Simultaneous)
    # --------------------------------------------------------------------------
    # Push on Player 2 comes from Player 1
    push_vec_p2 = calculate_push_vector(
        attacker_post=p1_post_pos,
        defender_post=p2_post_pos,
        attacker_pre=p1_blade.position,
        defender_pre=p2_blade.position,
        push_magnitude=p2_push_mag,
        default_fallback=PLAYER_1_DEFAULT_FORWARD,  # Push toward +X
        tolerance=config.hit_range_tolerance,
    )

    # Push on Player 1 comes from Player 2
    push_vec_p1 = calculate_push_vector(
        attacker_post=p2_post_pos,
        defender_post=p1_post_pos,
        attacker_pre=p2_blade.position,
        defender_pre=p1_blade.position,
        push_magnitude=p1_push_mag,
        default_fallback=PLAYER_2_DEFAULT_FORWARD,  # Push toward -X
        tolerance=config.hit_range_tolerance,
    )

    p1_final_pos = Position(p1_post_pos.x + push_vec_p1[0], p1_post_pos.y + push_vec_p1[1])
    p2_final_pos = Position(p2_post_pos.x + push_vec_p2[0], p2_post_pos.y + push_vec_p2[1])

    # --------------------------------------------------------------------------
    # 6. Resource Progression (Costs, Recoveries, Damage, Recoils, Passive Loss)
    # --------------------------------------------------------------------------
    # Action energy costs
    cost_1 = 0.0
    if player_1_action == Action.ATTACK or player_1_action == Action.DODGE:
        cost_1 = 8.0
    elif player_1_action == Action.GUARD:
        cost_1 = 4.0
    elif player_1_action == Action.SPECIAL_SPIN:
        cost_1 = 35.0

    cost_2 = 0.0
    if player_2_action == Action.ATTACK or player_2_action == Action.DODGE:
        cost_2 = 8.0
    elif player_2_action == Action.GUARD:
        cost_2 = 4.0
    elif player_2_action == Action.SPECIAL_SPIN:
        cost_2 = 35.0

    # Recoveries (Capped at maximums)
    # Charge energy recovery
    p1_charge_rec = p1_def.charge_energy_recovery if player_1_action == Action.CHARGE else 0.0
    p2_charge_rec = p2_def.charge_energy_recovery if player_2_action == Action.CHARGE else 0.0

    # Guard stability recovery
    p1_guard_rec = p1_def.guard_stability_recovery if player_1_action == Action.GUARD else 0.0
    p2_guard_rec = p2_def.guard_stability_recovery if player_2_action == Action.GUARD else 0.0

    # Special Spin self-recoil (10.0 stability on use, hits or misses)
    p1_self_recoil = config.special_spin_self_recoil if player_1_action == Action.SPECIAL_SPIN else 0.0
    p2_self_recoil = config.special_spin_self_recoil if player_2_action == Action.SPECIAL_SPIN else 0.0

    # Energy computation: start - cost + recovery (capped at max) - passive_loss -> clamp at 0
    p1_energy_after_action = p1_blade.current_energy - cost_1
    p1_energy_after_rec = min(p1_blade.max_energy, p1_energy_after_action + p1_charge_rec)
    p1_final_energy = max(0.0, p1_energy_after_rec - p1_def.passive_energy_loss)

    p2_energy_after_action = p2_blade.current_energy - cost_2
    p2_energy_after_rec = min(p2_blade.max_energy, p2_energy_after_action + p2_charge_rec)
    p2_final_energy = max(0.0, p2_energy_after_rec - p2_def.passive_energy_loss)

    # Stability computation: start + recovery (capped at max) - damage_received - self_recoil - guard_recoil -> clamp at 0
    p1_stab_after_rec = min(p1_blade.max_stability, p1_blade.current_stability + p1_guard_rec)
    p1_final_stability = max(0.0, p1_stab_after_rec - p2_dmg_dealt - p1_self_recoil - p1_guard_recoil)

    p2_stab_after_rec = min(p2_blade.max_stability, p2_blade.current_stability + p2_guard_rec)
    p2_final_stability = max(0.0, p2_stab_after_rec - p1_dmg_dealt - p2_self_recoil - p2_guard_recoil)

    # Cooldown updates (Special Spin ready_at = elapsed_game_time + 3.0s)
    current_time = state.elapsed_game_time
    p1_special_ready = (
        current_time + config.special_spin_cooldown_seconds
        if player_1_action == Action.SPECIAL_SPIN
        else p1_blade.special_ready_at
    )
    p2_special_ready = (
        current_time + config.special_spin_cooldown_seconds
        if player_2_action == Action.SPECIAL_SPIN
        else p2_blade.special_ready_at
    )

    # --------------------------------------------------------------------------
    # 7. Stadium Shrink & Next Match State Assembly
    # --------------------------------------------------------------------------
    next_completed_rounds = state.completed_rounds + 1
    if next_completed_rounds % 6 == 0:
        next_radius = max(6.0, state.stadium.radius - 1.0)
    else:
        next_radius = state.stadium.radius

    next_p1_blade = BladeState(
        player_id=p1_id,
        blade_type=p1_blade.blade_type,
        current_energy=p1_final_energy,
        max_energy=p1_blade.max_energy,
        current_stability=p1_final_stability,
        max_stability=p1_blade.max_stability,
        position=p1_final_pos,
        special_ready_at=p1_special_ready,
    )

    next_p2_blade = BladeState(
        player_id=p2_id,
        blade_type=p2_blade.blade_type,
        current_energy=p2_final_energy,
        max_energy=p2_blade.max_energy,
        current_stability=p2_final_stability,
        max_stability=p2_blade.max_stability,
        position=p2_final_pos,
        special_ready_at=p2_special_ready,
    )

    next_stadium = StadiumState(
        stadium_type=state.stadium.stadium_type,
        center=state.stadium.center,
        radius=next_radius,
    )

    candidate_state = MatchState(
        player_1_blade=next_p1_blade,
        player_2_blade=next_p2_blade,
        stadium=next_stadium,
        completed_rounds=next_completed_rounds,
        status=MatchStatus.IN_PROGRESS,
        result=None,
    )

    termination_result = evaluate_match_termination(candidate_state, tolerance=config.hit_range_tolerance)
    if termination_result is not None:
        next_state = MatchState(
            player_1_blade=next_p1_blade,
            player_2_blade=next_p2_blade,
            stadium=next_stadium,
            completed_rounds=next_completed_rounds,
            status=MatchStatus.FINISHED,
            result=termination_result,
        )
    else:
        next_state = candidate_state

    p1_audit = BladeRoundAudit(
        player_id=p1_id,
        action=player_1_action,
        start_position=p1_blade.position,
        post_movement_position=p1_post_pos,
        final_position=p1_final_pos,
        dodge_success=p1_dodge_success,
        attack_attempted=player_1_action in (Action.ATTACK, Action.SPECIAL_SPIN),
        attack_hit=p1_hits,
        stability_damage_dealt=p1_dmg_dealt,
        stability_damage_received=p2_dmg_dealt,
        push_magnitude_received=p1_push_mag,
        self_recoil_suffered=p1_self_recoil,
        guard_recoil_suffered=p1_guard_recoil,
        energy_spent=cost_1,
        energy_recovered=p1_charge_rec,
        stability_recovered=p1_guard_rec,
        passive_energy_lost=p1_def.passive_energy_loss,
    )

    p2_audit = BladeRoundAudit(
        player_id=p2_id,
        action=player_2_action,
        start_position=p2_blade.position,
        post_movement_position=p2_post_pos,
        final_position=p2_final_pos,
        dodge_success=p2_dodge_success,
        attack_attempted=player_2_action in (Action.ATTACK, Action.SPECIAL_SPIN),
        attack_hit=p2_hits,
        stability_damage_dealt=p2_dmg_dealt,
        stability_damage_received=p1_dmg_dealt,
        push_magnitude_received=p2_push_mag,
        self_recoil_suffered=p2_self_recoil,
        guard_recoil_suffered=p2_guard_recoil,
        energy_spent=cost_2,
        energy_recovered=p2_charge_rec,
        stability_recovered=p2_guard_rec,
        passive_energy_lost=p2_def.passive_energy_loss,
    )

    events = RoundCombatEvents(
        round_number=next_completed_rounds,
        player_1_audit=p1_audit,
        player_2_audit=p2_audit,
        stadium_radius_before=state.stadium.radius,
        stadium_radius_after=next_radius,
    )

    return (next_state, events)


class ClassicDishRoundResolver:
    """Authoritative Classic Dish combat rules engine.

    Satisfies the RoundResolver protocol defined in Module 3. Both human match
    controllers and AI search rollouts (Minimax and MCTS) use this exact deterministic
    rules engine.
    """

    def __init__(self, config: Optional[CombatConfig] = None) -> None:
        self._config: CombatConfig = config or DEFAULT_COMBAT_CONFIG

    @property
    def config(self) -> CombatConfig:
        """Active combat tuning configuration."""
        return self._config

    def resolve_round(
        self,
        state: MatchState,
        player_1_action: Action,
        player_2_action: Action,
    ) -> MatchState:
        """Resolve one combat round and return the next immutable MatchState.

        Args:
            state: Pre-round immutable MatchState.
            player_1_action: Action chosen by Player 1.
            player_2_action: Action chosen by Player 2.

        Returns:
            A new immutable MatchState with completed_rounds incremented by exactly 1.

        Raises:
            IllegalRoundResolutionError: If either action is illegal.
        """
        next_state, _ = resolve_combat_round(
            state=state,
            player_1_action=player_1_action,
            player_2_action=player_2_action,
            config=self._config,
        )
        return next_state
