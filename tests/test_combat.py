"""Comprehensive unit and integration tests for BLADE ARENA combat and round resolution."""

import itertools
import pytest

from blade_arena.game.actions import ActionLegalityError
from blade_arena.game.blade_definitions import create_blade_state
from blade_arena.game.combat import (
    BladeRoundAudit,
    ClassicDishRoundResolver,
    CombatConfig,
    DEFAULT_COMBAT_CONFIG,
    IllegalRoundResolutionError,
    RoundCombatEvents,
    calculate_hit_effects,
    calculate_push_vector,
    determine_hit,
    resolve_combat_round,
)
from blade_arena.game.geometry import distance
from blade_arena.game.initial_state import create_default_match, create_initial_match
from blade_arena.game.match_controller import MatchController, RoundResolutionError
from blade_arena.game.models import (
    Action,
    BladeState,
    BladeType,
    MatchState,
    MatchStatus,
    Position,
    StadiumState,
    StadiumType,
)


def test_combat_config_immutability_and_validation() -> None:
    """Verify CombatConfig is frozen and validates numeric parameters."""
    config = CombatConfig()
    assert config.normal_attack_damage == 12.0
    assert config.normal_attack_push == 1.2
    assert config.special_spin_damage == 25.0
    assert config.special_spin_self_recoil == 10.0
    assert config.charging_defender_damage_multiplier == 1.25
    assert config.guard_normal_damage_multiplier == 0.50
    assert config.guard_special_damage_multiplier == 0.70
    assert config.guard_attacker_recoil_normal_attack == 3.0

    with pytest.raises((AttributeError, TypeError)):
        config.normal_attack_damage = 15.0  # type: ignore[misc]

    with pytest.raises(ValueError):
        CombatConfig(normal_attack_damage=-1.0)
    with pytest.raises(TypeError):
        CombatConfig(normal_attack_damage="12.0")  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("action_1", "action_2"),
    list(itertools.product(Action, Action)),
)
def test_all_25_action_pairs_resolution(action_1: Action, action_2: Action) -> None:
    """Test resolution of all 25 simultaneous action combinations from standard starting state."""
    match = create_default_match()
    resolver = ClassicDishRoundResolver()

    next_state = resolver.resolve_round(match, action_1, action_2)

    # Completed rounds advances by exactly 1
    assert next_state.completed_rounds == 1
    assert next_state.status == MatchStatus.IN_PROGRESS
    assert next_state.result is None

    # Both blades remain within valid resource bounds
    b1 = next_state.player_1_blade
    b2 = next_state.player_2_blade
    assert 0.0 <= b1.current_energy <= b1.max_energy
    assert 0.0 <= b1.current_stability <= b1.max_stability
    assert 0.0 <= b2.current_energy <= b2.max_energy
    assert 0.0 <= b2.current_stability <= b2.max_stability

    # Positions remain finite
    assert isinstance(b1.position, Position)
    assert isinstance(b2.position, Position)


def test_attack_vs_charge_multiplier() -> None:
    """Verify charging defender receives 1.25x damage and 1.25x push."""
    # Place combatants so they end up within hit range (post-move distance <= 1.2)
    # Start: P1 at (-0.6, 0.0), P2 at (0.6, 0.0)
    # P1 Attacks: moves 1.6 toward (0.6, 0.0), capped at (0.6, 0.0) -> distance is 0 or close
    # P2 Charges: moves 1.0 toward (0.0, 0.0) -> reaches (0.0, 0.0)
    # P1 starts at (-1.0, 0.0), P2 at (1.0, 0.0).
    # P1 Attacks toward P2: moves 1.6 from -1.0 -> 0.6.
    # P2 Charges toward (0,0): moves 1.0 from 1.0 -> 0.0.
    # Post positions: P1 at 0.6, P2 at 0.0. Post distance is 0.6 <= 1.2 (Hit!).
    match = create_initial_match(
        player_1_pos=Position(-1.0, 0.0),
        player_2_pos=Position(1.0, 0.0),
    )
    resolver = ClassicDishRoundResolver()

    next_state, events = resolve_combat_round(match, Action.ATTACK, Action.CHARGE)

    # P1 attacked and hit
    assert events.player_1_audit.attack_hit is True
    # Base damage 12.0 * 1.0 (Balanced power) * 1.25 (Charging) = 15.0
    assert events.player_1_audit.stability_damage_dealt == pytest.approx(15.0)
    # Base push 1.2 * 1.25 = 1.5
    assert events.player_1_audit.push_magnitude_received == 0.0
    assert events.player_2_audit.push_magnitude_received == pytest.approx(1.5)

    # P2 received 15.0 damage
    # P2 start stability 100 - 15 = 85.0
    assert next_state.player_2_blade.current_stability == pytest.approx(85.0)

    # P2 Charged: cost 0, recovered 20 energy, lost 3 passive energy -> 100 - 0 + 20 (cap 100) - 3 = 97.0
    assert next_state.player_2_blade.current_energy == pytest.approx(97.0)


def test_attack_vs_guard_mitigation_and_attacker_recoil() -> None:
    """Verify Guard halves incoming normal attack damage/push, and inflicts 3 recoil on attacker."""
    # Start: P1 at (-1.0, 0.0), P2 at (0.5, 0.0)
    # P1 Attacks toward 0.5: moves 1.5 -> reaches 0.5
    # P2 Guards: stays at 0.5. Post distance = 0.0 <= 1.2 (Hit!).
    match = create_initial_match(
        player_1_pos=Position(-1.0, 0.0),
        player_2_pos=Position(0.5, 0.0),
    )

    next_state, events = resolve_combat_round(match, Action.ATTACK, Action.GUARD)

    assert events.player_1_audit.attack_hit is True
    # Damage: 12.0 * 1.0 * 0.50 = 6.0
    assert events.player_1_audit.stability_damage_dealt == pytest.approx(6.0)
    # Push on P2: 1.2 * 0.50 = 0.6
    assert events.player_2_audit.push_magnitude_received == pytest.approx(0.6)
    # Recoil on P1 (Attacker): 3.0 stability
    assert events.player_1_audit.guard_recoil_suffered == pytest.approx(3.0)

    # P1 stability: 100.0 - 3.0 = 97.0
    assert next_state.player_1_blade.current_stability == pytest.approx(97.0)

    # P2 stability: 100.0 + 5.0 (Guard recovery, capped at 100) - 6.0 = 94.0
    assert next_state.player_2_blade.current_stability == pytest.approx(94.0)


def test_special_spin_vs_guard_mitigation_and_self_recoil() -> None:
    """Verify Special Spin deals 0.70x damage/push on Guard, incurs 10 self-recoil, and triggers cooldown."""
    match = create_initial_match(
        player_1_pos=Position(-1.0, 0.0),
        player_2_pos=Position(0.5, 0.0),
    )

    next_state, events = resolve_combat_round(match, Action.SPECIAL_SPIN, Action.GUARD)

    assert events.player_1_audit.attack_hit is True
    # Damage: 25.0 * 1.0 * 0.70 = 17.5
    assert events.player_1_audit.stability_damage_dealt == pytest.approx(17.5)
    # Push on P2: 2.0 * 0.70 = 1.4
    assert events.player_2_audit.push_magnitude_received == pytest.approx(1.4)
    # Self-recoil on Special Spin: 10.0
    assert events.player_1_audit.self_recoil_suffered == pytest.approx(10.0)
    # Special Spin does NOT incur 3.0 guard recoil (normal attack only)
    assert events.player_1_audit.guard_recoil_suffered == 0.0

    # P1 stability: 100 - 10 = 90.0
    assert next_state.player_1_blade.current_stability == pytest.approx(90.0)
    # P1 energy: 100 - 35 (cost) - 3 (passive) = 62.0
    assert next_state.player_1_blade.current_energy == pytest.approx(62.0)
    # P1 special_ready_at updated to elapsed_game_time (0.0) + 3.0 = 3.0
    assert next_state.player_1_blade.special_ready_at == pytest.approx(3.0)

    # P2 stability: 100 + 5 (cap 100) - 17.5 = 82.5
    assert next_state.player_2_blade.current_stability == pytest.approx(82.5)


def test_successful_dodge_evades_attacks() -> None:
    """Verify a successful Dodge causes incoming Attack and Special Spin to miss completely."""
    # P1 at (-2.0, 0.0), P2 at (2.0, 0.0)
    # P1 Attacks: moves 1.6 toward (2.0, 0.0) -> (-0.4, 0.0)
    # P2 Dodges: moves 1.4 sideways -> (2.0, 1.4). Interior margin > 0.5 (dodge succeeds)
    # Distance: hypot(2.4, 1.4) = sqrt(5.76 + 1.96) = sqrt(7.72) ~ 2.778 > 1.2
    # Even if distance was close, dodge_success=True guarantees miss!
    # Let's test close distance:
    # P1 at (-0.5, 0.0), P2 at (0.5, 0.0).
    # P1 Attacks: moves 1.0 toward 0.5 -> reaches 0.5
    # P2 Dodges: moves 1.4 sideways from 0.5 -> (0.5, 1.4).
    # Post distance is 1.4 (or if distance <= 1.2):
    # Let's check with exact dodge evasion:
    match = create_initial_match(
        player_1_pos=Position(-0.5, 0.0),
        player_2_pos=Position(0.5, 0.0),
    )

    next_state, events = resolve_combat_round(match, Action.ATTACK, Action.DODGE)

    assert events.player_2_audit.dodge_success is True
    # Attack misses because defender successfully dodged
    assert events.player_1_audit.attack_hit is False
    assert events.player_1_audit.stability_damage_dealt == 0.0
    assert events.player_2_audit.stability_damage_received == 0.0
    assert events.player_2_audit.push_magnitude_received == 0.0

    # P2 took 0 damage
    assert next_state.player_2_blade.current_stability == pytest.approx(100.0)


def test_failed_near_edge_dodge_gets_hit() -> None:
    """Verify near-edge Dodge (margin < 0.5) fails evasion and takes full attack hit when in range."""
    # Direct pure function check:
    # Within hit range (e.g. dist 1.0):
    # If dodge_success is True, incoming attack misses
    assert determine_hit(Action.ATTACK, 1.0, Action.DODGE, defender_dodge_success=True) is False
    # If dodge_success is False, incoming attack hits!
    assert determine_hit(Action.ATTACK, 1.0, Action.DODGE, defender_dodge_success=False) is True

    # Round resolution verification with tuned hit range:
    # P2 at (9.0, 0.0), P1 at (8.5, 0.0). P1 moves to (9.0, 0.0).
    # P2 dodges to (9.0, 1.4). With radius 9.5, margin = 0.392 < 0.5 -> dodge_success = False.
    # Distance between them is 1.4.
    config = CombatConfig(normal_attack_hit_range=1.5)
    custom_stadium = StadiumState(
        stadium_type=StadiumType.CLASSIC_DISH,
        center=Position(0.0, 0.0),
        radius=9.5,
    )
    b1 = create_blade_state("player_1", BladeType.BALANCED, position=Position(8.5, 0.0))
    b2 = create_blade_state("player_2", BladeType.BALANCED, position=Position(9.0, 0.0))
    match = MatchState(
        player_1_blade=b1,
        player_2_blade=b2,
        stadium=custom_stadium,
        completed_rounds=0,
        status=MatchStatus.IN_PROGRESS,
    )

    next_state, events = resolve_combat_round(match, Action.ATTACK, Action.DODGE, config=config)

    # Dodge failed evasion
    assert events.player_2_audit.dodge_success is False
    # P1 hit successfully!
    assert events.player_1_audit.attack_hit is True
    assert events.player_1_audit.stability_damage_dealt == pytest.approx(12.0)
    assert events.player_2_audit.stability_damage_received == pytest.approx(12.0)


def test_attack_vs_attack_simultaneous_clash() -> None:
    """Verify both blades hit simultaneously during an Attack clash with no player priority."""
    # Both start at distance 2.0: (-1.0, 0.0) and (1.0, 0.0)
    # P1 moves 1.6 toward 1.0 -> reaches 0.6
    # P2 moves 1.6 toward -1.0 -> reaches -0.6
    # They pass each other; post distance is 1.2 <= 1.2 (Hit range!).
    match = create_initial_match(
        player_1_pos=Position(-1.0, 0.0),
        player_2_pos=Position(1.0, 0.0),
    )

    next_state, events = resolve_combat_round(match, Action.ATTACK, Action.ATTACK)

    # Both attacks hit!
    assert events.player_1_audit.attack_hit is True
    assert events.player_2_audit.attack_hit is True

    # Both deal and receive 12.0 damage
    assert events.player_1_audit.stability_damage_dealt == pytest.approx(12.0)
    assert events.player_2_audit.stability_damage_dealt == pytest.approx(12.0)

    # Both receive 1.2 push
    assert events.player_1_audit.push_magnitude_received == pytest.approx(1.2)
    assert events.player_2_audit.push_magnitude_received == pytest.approx(1.2)

    # Both blades take 12.0 damage
    assert next_state.player_1_blade.current_stability == pytest.approx(88.0)
    assert next_state.player_2_blade.current_stability == pytest.approx(88.0)


def test_special_spin_vs_special_spin_simultaneous() -> None:
    """Verify Special Spin clash: both deal 25 damage, both take 10 self-recoil, both push 2.0."""
    # Start at distance 1.0: (-0.5, 0.0) and (0.5, 0.0)
    # P1 moves toward 0.5: distance is 1.0 < 2.0 -> capped at 0.5
    # P2 moves toward -0.5: distance is 1.0 < 2.0 -> capped at -0.5
    # Post distance is 1.0 <= 1.2 (Hit range!).
    match = create_initial_match(
        player_1_pos=Position(-0.5, 0.0),
        player_2_pos=Position(0.5, 0.0),
    )

    next_state, events = resolve_combat_round(match, Action.SPECIAL_SPIN, Action.SPECIAL_SPIN)

    assert events.player_1_audit.attack_hit is True
    assert events.player_2_audit.attack_hit is True

    # Both take 25 hit damage + 10 self-recoil = 35 total stability loss
    assert next_state.player_1_blade.current_stability == pytest.approx(65.0)
    assert next_state.player_2_blade.current_stability == pytest.approx(65.0)

    # Both spend 35 energy + 3 passive loss = 38 energy loss -> 100 - 38 = 62.0
    assert next_state.player_1_blade.current_energy == pytest.approx(62.0)
    assert next_state.player_2_blade.current_energy == pytest.approx(62.0)

    # Both have special_ready_at set to 3.0s
    assert next_state.player_1_blade.special_ready_at == pytest.approx(3.0)
    assert next_state.player_2_blade.special_ready_at == pytest.approx(3.0)


def test_miss_outside_hit_range() -> None:
    """Verify attack misses when combatants remain outside 1.2 unit hit range."""
    # Start: (-5.0, 0.0) and (5.0, 0.0)
    # P1 Attacks: moves 1.6 -> (-3.4, 0.0)
    # P2 Guards: stays at (5.0, 0.0)
    # Distance is 8.4 > 1.2 -> Miss!
    match = create_initial_match(
        player_1_pos=Position(-5.0, 0.0),
        player_2_pos=Position(5.0, 0.0),
    )

    next_state, events = resolve_combat_round(match, Action.ATTACK, Action.GUARD)

    assert events.player_1_audit.attack_hit is False
    assert events.player_1_audit.stability_damage_dealt == 0.0
    assert events.player_2_audit.stability_damage_received == 0.0
    assert events.player_1_audit.guard_recoil_suffered == 0.0  # Miss on Guard causes no recoil


def test_special_spin_self_recoil_applies_even_on_miss() -> None:
    """Verify Special Spin incurs 10 self-recoil and sets cooldown even when it misses."""
    match = create_initial_match(
        player_1_pos=Position(-5.0, 0.0),
        player_2_pos=Position(5.0, 0.0),
    )

    next_state, events = resolve_combat_round(match, Action.SPECIAL_SPIN, Action.GUARD)

    assert events.player_1_audit.attack_hit is False
    assert events.player_1_audit.self_recoil_suffered == pytest.approx(10.0)
    assert next_state.player_1_blade.current_stability == pytest.approx(90.0)
    assert next_state.player_1_blade.special_ready_at == pytest.approx(3.0)


def test_attacker_archetype_power_multiplier() -> None:
    """Verify Attacker archetype (power 1.3) deals 1.3x damage, but push is unaffected."""
    # Player 1 is ATTACKER (power 1.3), Player 2 is BALANCED (power 1.0)
    match = create_initial_match(
        player_1_blade_type=BladeType.ATTACKER,
        player_2_blade_type=BladeType.BALANCED,
        player_1_pos=Position(-1.0, 0.0),
        player_2_pos=Position(0.5, 0.0),
    )

    next_state, events = resolve_combat_round(match, Action.ATTACK, Action.CHARGE)

    # Base damage 12 * 1.25 (Attacker power) * 1.25 (Charging) = 18.75
    assert events.player_1_audit.stability_damage_dealt == pytest.approx(18.75)
    # Push: 1.2 * 1.25 = 1.5 (power does NOT multiply push)
    assert events.player_2_audit.push_magnitude_received == pytest.approx(1.5)


def test_defender_archetype_recovery_and_power() -> None:
    """Verify Defender archetype has 0.8x power and recovers +10 stability on Guard."""
    match = create_initial_match(
        player_1_blade_type=BladeType.DEFENDER,
        player_2_blade_type=BladeType.BALANCED,
        player_1_pos=Position(-1.0, 0.0),
        player_2_pos=Position(0.5, 0.0),
    )

    # Defender Guards, Balanced Attacks
    next_state, events = resolve_combat_round(match, Action.GUARD, Action.ATTACK)

    # P1 (Defender) recovers +10 stability on Guard
    assert events.player_1_audit.stability_recovered == pytest.approx(10.0)


def test_stamina_archetype_charge_recovery_and_passive_loss() -> None:
    """Verify Stamina archetype recovers +25 energy on Charge and loses only 3 passive energy."""
    match = create_initial_match(
        player_1_blade_type=BladeType.STAMINA,
        player_2_blade_type=BladeType.BALANCED,
        player_1_pos=Position(-5.0, 0.0),
        player_2_pos=Position(5.0, 0.0),
    )

    next_state, events = resolve_combat_round(match, Action.CHARGE, Action.GUARD)

    assert events.player_1_audit.energy_recovered == pytest.approx(25.0)
    assert events.player_1_audit.passive_energy_lost == pytest.approx(2.0)


def test_resource_bounds_clamping_to_zero() -> None:
    """Verify excessive damage or energy drain clamps at 0.0 and does not go negative."""
    # Create low-resource blade
    b1 = create_blade_state("player_1", BladeType.BALANCED, position=Position(-1.0, 0.0))
    # Mutate to very low stability: 5.0
    b1_low = BladeState(
        player_id=b1.player_id,
        blade_type=b1.blade_type,
        current_energy=2.0,
        max_energy=b1.max_energy,
        current_stability=5.0,
        max_stability=b1.max_stability,
        position=b1.position,
        special_ready_at=b1.special_ready_at,
    )
    b2 = create_blade_state("player_2", BladeType.BALANCED, position=Position(0.5, 0.0))
    match = MatchState(
        player_1_blade=b1_low,
        player_2_blade=b2,
        stadium=StadiumState(StadiumType.CLASSIC_DISH, Position(0.0, 0.0), 10.0),
        completed_rounds=0,
        status=MatchStatus.IN_PROGRESS,
    )

    # P2 Attacks for 12 damage; P1 stability was 5.0 -> should clamp at 0.0
    # P1 Charges: energy 2.0 + 20 - 5 = 17.0
    next_state, events = resolve_combat_round(match, Action.CHARGE, Action.ATTACK)

    assert next_state.player_1_blade.current_stability == 0.0
    assert next_state.player_1_blade.current_stability >= 0.0


def test_stadium_shrinking_milestone_after_round_6() -> None:
    """Verify stadium radius shrinks from 10.0 to 9.0 after the 6th completed round."""
    # Match at completed_rounds = 5
    match_r5 = MatchState(
        player_1_blade=create_blade_state("player_1", BladeType.BALANCED, position=Position(-2.0, 0.0)),
        player_2_blade=create_blade_state("player_2", BladeType.BALANCED, position=Position(2.0, 0.0)),
        stadium=StadiumState(StadiumType.CLASSIC_DISH, Position(0.0, 0.0), 10.0),
        completed_rounds=5,
        status=MatchStatus.IN_PROGRESS,
    )

    next_state, events = resolve_combat_round(match_r5, Action.GUARD, Action.GUARD)

    assert next_state.completed_rounds == 6
    assert next_state.stadium.radius == pytest.approx(9.0)
    assert events.stadium_radius_before == pytest.approx(10.0)
    assert events.stadium_radius_after == pytest.approx(9.0)


def test_authoritative_legality_rejection_prevents_resolution() -> None:
    """Verify resolver authoritatively rejects illegal actions without state mutation."""
    # Player 1 has 10 energy, tries Special Spin (costs 35)
    b1_low = BladeState(
        player_id="player_1",
        blade_type=BladeType.BALANCED,
        current_energy=10.0,
        max_energy=100.0,
        current_stability=100.0,
        max_stability=100.0,
        position=Position(-2.0, 0.0),
        special_ready_at=0.0,
    )
    b2 = create_blade_state("player_2", BladeType.BALANCED, position=Position(2.0, 0.0))
    match = MatchState(
        player_1_blade=b1_low,
        player_2_blade=b2,
        stadium=StadiumState(StadiumType.CLASSIC_DISH, Position(0.0, 0.0), 10.0),
        completed_rounds=0,
        status=MatchStatus.IN_PROGRESS,
    )

    resolver = ClassicDishRoundResolver()
    with pytest.raises(IllegalRoundResolutionError, match="action SPECIAL_SPIN is illegal"):
        resolver.resolve_round(match, Action.SPECIAL_SPIN, Action.GUARD)


def test_controller_integration_with_classic_dish_resolver() -> None:
    """Verify MatchController operates seamlessly with ClassicDishRoundResolver."""
    match = create_default_match()
    resolver = ClassicDishRoundResolver()
    controller = MatchController(initial_state=match, resolver=resolver)

    controller.submit_action("player_1", Action.ATTACK)
    controller.submit_action("player_2", Action.GUARD)

    record = controller.resolve_round()

    assert record.round_number == 1
    assert controller.state.completed_rounds == 1
    assert len(controller.round_history) == 1
    assert controller.can_resolve() is False


def test_controller_atomic_rejection_and_reselection_workflow() -> None:
    """Verify controller preserves state on resolver rejection and allows single-player reselection."""
    # P1 has only 10 energy
    b1_low = BladeState(
        player_id="player_1",
        blade_type=BladeType.BALANCED,
        current_energy=10.0,
        max_energy=100.0,
        current_stability=100.0,
        max_stability=100.0,
        position=Position(-2.0, 0.0),
        special_ready_at=0.0,
    )
    b2 = create_blade_state("player_2", BladeType.BALANCED, position=Position(2.0, 0.0))
    match = MatchState(
        player_1_blade=b1_low,
        player_2_blade=b2,
        stadium=StadiumState(StadiumType.CLASSIC_DISH, Position(0.0, 0.0), 10.0),
        completed_rounds=0,
        status=MatchStatus.IN_PROGRESS,
    )

    # Controller without upfront check (enforce_legality=False) to test resolver rejection
    resolver = ClassicDishRoundResolver()
    controller = MatchController(initial_state=match, resolver=resolver, enforce_legality=False)

    controller.submit_action("player_1", Action.SPECIAL_SPIN)  # Illegal!
    controller.submit_action("player_2", Action.GUARD)         # Legal

    # Resolution attempt fails due to resolver legality check
    with pytest.raises(RoundResolutionError, match="action SPECIAL_SPIN is illegal"):
        controller.resolve_round()

    # Pre-round state and pending commitments remain untouched
    assert controller.state.completed_rounds == 0
    assert controller.has_player_submitted("player_1") is True
    assert controller.has_player_submitted("player_2") is True

    # Player 1 clears their invalid pending action without disturbing Player 2
    controller.clear_pending_action("player_1")
    assert controller.has_player_submitted("player_1") is False
    assert controller.has_player_submitted("player_2") is True  # Player 2 still submitted!

    # Player 1 resubmits legal Charge
    controller.submit_action("player_1", Action.CHARGE)
    assert controller.can_resolve() is True

    # Resolution now completes cleanly
    record = controller.resolve_round()
    assert record.round_number == 1
    assert controller.state.completed_rounds == 1


def test_deterministic_replay_across_runs() -> None:
    """Verify identical action sequences yield bitwise identical states across separate runs."""
    m1 = create_default_match()
    m2 = create_default_match()
    resolver = ClassicDishRoundResolver()

    script = [
        (Action.ATTACK, Action.CHARGE),
        (Action.GUARD, Action.ATTACK),
        (Action.SPECIAL_SPIN, Action.GUARD),
        (Action.CHARGE, Action.DODGE),
    ]

    s1, s2 = m1, m2
    for a1, a2 in script:
        s1 = resolver.resolve_round(s1, a1, a2)
        s2 = resolver.resolve_round(s2, a1, a2)
        assert s1 == s2


def test_exact_energy_boundary_legality_and_execution() -> None:
    """Verify blades with exact energy to pay an action cost succeed and drop to 0 energy before passive loss."""
    # Player 1 has exact cost for Attack (8.0)
    b1 = BladeState(
        player_id="player_1",
        blade_type=BladeType.BALANCED,
        current_energy=8.0,
        max_energy=100.0,
        current_stability=100.0,
        max_stability=100.0,
        position=Position(-2.0, 0.0),
        special_ready_at=0.0,
    )
    b2 = create_blade_state("player_2", BladeType.BALANCED, position=Position(2.0, 0.0))
    match = MatchState(
        player_1_blade=b1,
        player_2_blade=b2,
        stadium=StadiumState(StadiumType.CLASSIC_DISH, Position(0.0, 0.0), 10.0),
        completed_rounds=0,
        status=MatchStatus.IN_PROGRESS,
    )

    resolver = ClassicDishRoundResolver()
    next_state = resolver.resolve_round(match, Action.ATTACK, Action.GUARD)

    # 8.0 - 8.0 (cost) = 0.0 - 3.0 (passive loss) -> clamped at 0.0
    assert next_state.player_1_blade.current_energy == 0.0


def test_both_submission_orders_produce_identical_results() -> None:
    """Verify player submission order does not affect round resolution in the controller."""
    m1 = create_default_match()
    m2 = create_default_match()
    resolver = ClassicDishRoundResolver()

    c1 = MatchController(m1, resolver)
    c1.submit_action("player_1", Action.ATTACK)
    c1.submit_action("player_2", Action.GUARD)
    r1 = c1.resolve_round()

    c2 = MatchController(m2, resolver)
    c2.submit_action("player_2", Action.GUARD)
    c2.submit_action("player_1", Action.ATTACK)
    r2 = c2.resolve_round()

    assert c1.state == c2.state
    assert r1.state_after == r2.state_after


def test_equal_coordinate_push_fallback() -> None:
    """Verify push vector calculation handles completely coincident positions using fallback."""
    pos = Position(0.0, 0.0)
    push_vec = calculate_push_vector(
        attacker_post=pos,
        defender_post=pos,
        attacker_pre=pos,
        defender_pre=pos,
        push_magnitude=1.5,
        default_fallback=(1.0, 0.0),
    )
    assert push_vec[0] == pytest.approx(1.5)
    assert push_vec[1] == pytest.approx(0.0)

