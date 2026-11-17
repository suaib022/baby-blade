"""Action definitions, metadata, and legality evaluation for BLADE ARENA.

Provides pure-Python immutable specifications for the five turn actions (Charge, Attack,
Guard, Dodge, Special Spin) and rules for evaluating action legality against a MatchState.
"""

from __future__ import annotations

import types
from dataclasses import dataclass
from typing import Mapping, Optional, Tuple

from blade_arena.game.blade_definitions import get_blade_definition
from blade_arena.game.models import Action, BladeType, MatchState, MatchStatus


@dataclass(frozen=True)
class ActionDefinition:
    """Immutable metadata and baseline costs for a turn action."""

    action: Action
    name: str
    energy_cost: float
    stability_recoil: float
    requires_cooldown: bool
    cooldown_duration: float
    description: str

    def __post_init__(self) -> None:
        if not isinstance(self.action, Action):
            raise TypeError(f"action must be an Action enum, got {type(self.action).__name__}")
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("name must be a non-empty string")
        if self.energy_cost < 0.0:
            raise ValueError(f"energy_cost must be non-negative, got {self.energy_cost}")
        if self.stability_recoil < 0.0:
            raise ValueError(f"stability_recoil must be non-negative, got {self.stability_recoil}")
        if self.cooldown_duration < 0.0:
            raise ValueError(f"cooldown_duration must be non-negative, got {self.cooldown_duration}")


@dataclass(frozen=True)
class LegalityResult:
    """Outcome of an action legality check."""

    is_legal: bool
    reason: Optional[str] = None


class ActionLegalityError(ValueError):
    """Raised when an illegal action is submitted under strict legality enforcement."""

    pass


# ------------------------------------------------------------------------------
# Action Definitions Registry
# ------------------------------------------------------------------------------

_ACTION_DEFINITIONS: dict[Action, ActionDefinition] = {
    Action.CHARGE: ActionDefinition(
        action=Action.CHARGE,
        name="Charge",
        energy_cost=0.0,
        stability_recoil=0.0,
        requires_cooldown=False,
        cooldown_duration=0.0,
        description="Move toward stadium center and recover energy. Vulnerable to attacks.",
    ),
    Action.ATTACK: ActionDefinition(
        action=Action.ATTACK,
        name="Attack",
        energy_cost=8.0,
        stability_recoil=0.0,
        requires_cooldown=False,
        cooldown_duration=0.0,
        description="Advance toward opponent to deal stability damage and knockback push.",
    ),
    Action.GUARD: ActionDefinition(
        action=Action.GUARD,
        name="Guard",
        energy_cost=4.0,
        stability_recoil=0.0,
        requires_cooldown=False,
        cooldown_duration=0.0,
        description="Brace in place, recover stability, and mitigate incoming damage/push.",
    ),
    Action.DODGE: ActionDefinition(
        action=Action.DODGE,
        name="Dodge",
        energy_cost=8.0,
        stability_recoil=0.0,
        requires_cooldown=False,
        cooldown_duration=0.0,
        description="Displace sideways to evade incoming normal and special attacks.",
    ),
    Action.SPECIAL_SPIN: ActionDefinition(
        action=Action.SPECIAL_SPIN,
        name="Special Spin",
        energy_cost=35.0,
        stability_recoil=10.0,
        requires_cooldown=True,
        cooldown_duration=3.0,
        description="High-power offensive surge with self-recoil. Requires cooldown availability.",
    ),
}

# Canonical deterministic action ordering
ORDERED_ACTIONS: Tuple[Action, ...] = (
    Action.CHARGE,
    Action.ATTACK,
    Action.GUARD,
    Action.DODGE,
    Action.SPECIAL_SPIN,
)


def get_action_definition(action: Action) -> ActionDefinition:
    """Retrieve the immutable ActionDefinition for an Action enum member.

    Args:
        action: The Action enum member.

    Returns:
        The corresponding ActionDefinition.

    Raises:
        KeyError: If action is unknown or unsupported.
        TypeError: If action is not an Action instance.
    """
    if not isinstance(action, Action):
        raise TypeError(f"Expected Action enum, got {type(action).__name__}: {action}")
    if action not in _ACTION_DEFINITIONS:
        raise KeyError(f"Unsupported action: {action}")
    return _ACTION_DEFINITIONS[action]


def get_all_action_definitions() -> Mapping[Action, ActionDefinition]:
    """Retrieve a read-only mapping of all registered action definitions."""
    return types.MappingProxyType(_ACTION_DEFINITIONS)


def get_action_recovery(blade_type: BladeType, action: Action) -> float:
    """Retrieve the archetype-specific recovery value for Charge or Guard.

    Args:
        blade_type: The blade's archetype.
        action: The action to check (Charge or Guard).

    Returns:
        The recovery amount specified by the archetype definition (0.0 for other actions).
    """
    blade_def = get_blade_definition(blade_type)
    if action == Action.CHARGE:
        return blade_def.charge_energy_recovery
    if action == Action.GUARD:
        return blade_def.guard_stability_recovery
    return 0.0


# ------------------------------------------------------------------------------
# Pure Legality Evaluation API
# ------------------------------------------------------------------------------


def check_action_legality(
    state: MatchState,
    player_id: str,
    action: Action,
) -> LegalityResult:
    """Evaluate whether an action is legal for a player given the pre-round state.

    Legality criteria:
    1. Match must be IN_PROGRESS (finished matches offer no legal actions).
    2. Player ID must belong to the match.
    3. Action must be a valid Action enum instance.
    4. Current energy must be >= action energy cost.
    5. If action requires cooldown (Special Spin), elapsed_game_time must be >= special_ready_at.

    Args:
        state: Pre-round immutable MatchState.
        player_id: Identifier of the acting player.
        action: The candidate Action enum member.

    Returns:
        A LegalityResult with is_legal=True, or is_legal=False and a descriptive reason.

    Raises:
        TypeError: If state, player_id, or action has an invalid type.
        ValueError: If player_id does not belong to the match.
    """
    if not isinstance(state, MatchState):
        raise TypeError(f"state must be a MatchState, got {type(state).__name__}")
    if not isinstance(player_id, str) or not player_id.strip():
        raise TypeError(f"player_id must be a non-empty string, got {player_id!r}")
    if not isinstance(action, Action):
        raise TypeError(f"action must be an Action enum, got {type(action).__name__}")

    # Identify combatant blade
    if player_id == state.player_1_blade.player_id:
        blade = state.player_1_blade
    elif player_id == state.player_2_blade.player_id:
        blade = state.player_2_blade
    else:
        raise ValueError(
            f"Invalid player '{player_id}': match participants are {[state.player_1_blade.player_id, state.player_2_blade.player_id]}"
        )

    # 1. Finished match check
    if state.status == MatchStatus.FINISHED:
        return LegalityResult(is_legal=False, reason="Match is already finished")

    action_def = get_action_definition(action)

    # 2. Energy cost payable check
    if blade.current_energy < action_def.energy_cost:
        return LegalityResult(
            is_legal=False,
            reason=(
                f"Insufficient energy for {action_def.name}: requires {action_def.energy_cost}, "
                f"available {blade.current_energy}"
            ),
        )

    # 3. Cooldown check (Special Spin)
    if action_def.requires_cooldown:
        if state.elapsed_game_time < blade.special_ready_at:
            return LegalityResult(
                is_legal=False,
                reason=(
                    f"{action_def.name} on cooldown until {blade.special_ready_at:.1f}s "
                    f"(current game time {state.elapsed_game_time:.1f}s)"
                ),
            )

    return LegalityResult(is_legal=True)


def is_action_legal(state: MatchState, player_id: str, action: Action) -> bool:
    """Convenience boolean check for action legality."""
    return check_action_legality(state, player_id, action).is_legal


def legal_actions(state: MatchState, player_id: str) -> Tuple[Action, ...]:
    """Retrieve all legal actions for a player in deterministic canonical order.

    Returns:
        A tuple of legal actions ordered as: CHARGE, ATTACK, GUARD, DODGE, SPECIAL_SPIN.
        Empty tuple if the match is finished.
    """
    if state.status == MatchStatus.FINISHED:
        return ()

    return tuple(
        act for act in ORDERED_ACTIONS if is_action_legal(state, player_id, act)
    )
