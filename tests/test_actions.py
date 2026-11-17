"""Unit tests for BLADE ARENA action definitions, metadata, and legality evaluation."""

from __future__ import annotations

import dataclasses
import subprocess
import sys

import pytest

from blade_arena.game.actions import (
    ORDERED_ACTIONS,
    ActionDefinition,
    check_action_legality,
    get_action_definition,
    get_action_recovery,
    get_all_action_definitions,
    is_action_legal,
    legal_actions,
)
from blade_arena.game.blade_definitions import create_blade_state
from blade_arena.game.initial_state import (
    DEFAULT_PLAYER_1_ID,
    DEFAULT_PLAYER_2_ID,
    create_default_match,
    create_initial_match,
)
from blade_arena.game.match_controller import ActionSubmissionError, MatchController
from blade_arena.game.models import (
    Action,
    BladeType,
    FinishReason,
    MatchResult,
    MatchState,
    MatchStatus,
    Position,
)
from blade_arena.game.resolver import RoundResolver


class DummyResolver(RoundResolver):
    def resolve_round(
        self,
        state: MatchState,
        player_1_action: Action,
        player_2_action: Action,
    ) -> MatchState:
        return dataclasses.replace(state, completed_rounds=state.completed_rounds + 1)


# ==============================================================================
# A. ACTION METADATA & REGISTRY
# ==============================================================================


def test_action_metadata_values() -> None:
    """Verify costs, recoils, and cooldown parameters for all five actions."""
    charge_def = get_action_definition(Action.CHARGE)
    assert charge_def.action == Action.CHARGE
    assert charge_def.name == "Charge"
    assert charge_def.energy_cost == 0.0
    assert charge_def.stability_recoil == 0.0
    assert charge_def.requires_cooldown is False
    assert charge_def.cooldown_duration == 0.0

    attack_def = get_action_definition(Action.ATTACK)
    assert attack_def.action == Action.ATTACK
    assert attack_def.name == "Attack"
    assert attack_def.energy_cost == 8.0
    assert attack_def.stability_recoil == 0.0
    assert attack_def.requires_cooldown is False
    assert attack_def.cooldown_duration == 0.0

    guard_def = get_action_definition(Action.GUARD)
    assert guard_def.action == Action.GUARD
    assert guard_def.name == "Guard"
    assert guard_def.energy_cost == 4.0
    assert guard_def.stability_recoil == 0.0
    assert guard_def.requires_cooldown is False
    assert guard_def.cooldown_duration == 0.0

    dodge_def = get_action_definition(Action.DODGE)
    assert dodge_def.action == Action.DODGE
    assert dodge_def.name == "Dodge"
    assert dodge_def.energy_cost == 8.0
    assert dodge_def.stability_recoil == 0.0
    assert dodge_def.requires_cooldown is False
    assert dodge_def.cooldown_duration == 0.0

    special_def = get_action_definition(Action.SPECIAL_SPIN)
    assert special_def.action == Action.SPECIAL_SPIN
    assert special_def.name == "Special Spin"
    assert special_def.energy_cost == 35.0
    assert special_def.stability_recoil == 10.0
    assert special_def.requires_cooldown is True
    assert special_def.cooldown_duration == 3.0


def test_action_definitions_are_immutable() -> None:
    """Verify ActionDefinition instances and registry cannot be modified."""
    charge_def = get_action_definition(Action.CHARGE)
    with pytest.raises(dataclasses.FrozenInstanceError):
        charge_def.energy_cost = 10.0  # type: ignore

    all_defs = get_all_action_definitions()
    with pytest.raises(TypeError):
        all_defs[Action.CHARGE] = charge_def  # type: ignore


def test_get_action_definition_type_and_key_errors() -> None:
    """Verify invalid types raise TypeError and unknown values raise KeyError."""
    with pytest.raises(TypeError, match="Expected Action enum"):
        get_action_definition("ATTACK")  # type: ignore

    with pytest.raises(TypeError, match="Expected Action enum"):
        get_action_definition(None)  # type: ignore


def test_action_definition_validation_bounds() -> None:
    """Verify ActionDefinition constructor rejects negative costs or durations."""
    with pytest.raises(ValueError, match="energy_cost must be non-negative"):
        ActionDefinition(
            action=Action.ATTACK,
            name="Attack",
            energy_cost=-5.0,
            stability_recoil=0.0,
            requires_cooldown=False,
            cooldown_duration=0.0,
            description="desc",
        )

    with pytest.raises(ValueError, match="stability_recoil must be non-negative"):
        ActionDefinition(
            action=Action.SPECIAL_SPIN,
            name="Special Spin",
            energy_cost=35.0,
            stability_recoil=-10.0,
            requires_cooldown=True,
            cooldown_duration=3.0,
            description="desc",
        )

    with pytest.raises(ValueError, match="cooldown_duration must be non-negative"):
        ActionDefinition(
            action=Action.SPECIAL_SPIN,
            name="Special Spin",
            energy_cost=35.0,
            stability_recoil=10.0,
            requires_cooldown=True,
            cooldown_duration=-3.0,
            description="desc",
        )

    with pytest.raises(ValueError, match="name must be a non-empty string"):
        ActionDefinition(
            action=Action.CHARGE,
            name="   ",
            energy_cost=0.0,
            stability_recoil=0.0,
            requires_cooldown=False,
            cooldown_duration=0.0,
            description="desc",
        )


# ==============================================================================
# B. BLADE-SPECIFIC RECOVERY LOOKUP
# ==============================================================================


@pytest.mark.parametrize(
    "blade_type, expected_charge_rec, expected_guard_rec",
    [
        (BladeType.BALANCED, 20.0, 5.0),
        (BladeType.ATTACKER, 20.0, 5.0),
        (BladeType.DEFENDER, 20.0, 10.0),
        (BladeType.STAMINA, 25.0, 5.0),
    ],
)
def test_archetype_specific_recovery_lookup(
    blade_type: BladeType,
    expected_charge_rec: float,
    expected_guard_rec: float,
) -> None:
    """Verify recovery amounts correspond directly to Module 4 archetype definitions."""
    assert get_action_recovery(blade_type, Action.CHARGE) == expected_charge_rec
    assert get_action_recovery(blade_type, Action.GUARD) == expected_guard_rec
    assert get_action_recovery(blade_type, Action.ATTACK) == 0.0
    assert get_action_recovery(blade_type, Action.DODGE) == 0.0
    assert get_action_recovery(blade_type, Action.SPECIAL_SPIN) == 0.0


# ==============================================================================
# C. LEGALITY: ENERGY THRESHOLDS
# ==============================================================================


def test_charge_is_legal_even_at_zero_energy() -> None:
    """Verify Charge has zero energy cost and is legal at 0 energy."""
    match = create_default_match()
    depleted_blade = dataclasses.replace(match.player_1_blade, current_energy=0.0)
    match = dataclasses.replace(match, player_1_blade=depleted_blade)

    res = check_action_legality(match, DEFAULT_PLAYER_1_ID, Action.CHARGE)
    assert res.is_legal is True
    assert is_action_legal(match, DEFAULT_PLAYER_1_ID, Action.CHARGE) is True


@pytest.mark.parametrize(
    "action, cost",
    [
        (Action.GUARD, 4.0),
        (Action.ATTACK, 8.0),
        (Action.DODGE, 8.0),
        (Action.SPECIAL_SPIN, 35.0),
    ],
)
def test_action_energy_thresholds_below_equal_above(action: Action, cost: float) -> None:
    """Verify legality below, equal to, and above the energy cost."""
    match = create_default_match()

    # Below cost -> Illegal
    blade_below = dataclasses.replace(match.player_1_blade, current_energy=cost - 0.1)
    match_below = dataclasses.replace(match, player_1_blade=blade_below)
    res_below = check_action_legality(match_below, DEFAULT_PLAYER_1_ID, action)
    assert res_below.is_legal is False
    assert "Insufficient energy" in (res_below.reason or "")

    # Exactly cost -> Legal
    blade_exact = dataclasses.replace(match.player_1_blade, current_energy=cost)
    match_exact = dataclasses.replace(match, player_1_blade=blade_exact)
    assert is_action_legal(match_exact, DEFAULT_PLAYER_1_ID, action) is True

    # Above cost -> Legal
    blade_above = dataclasses.replace(match.player_1_blade, current_energy=cost + 10.0)
    match_above = dataclasses.replace(match, player_1_blade=blade_above)
    assert is_action_legal(match_above, DEFAULT_PLAYER_1_ID, action) is True


# ==============================================================================
# D. LEGALITY: COOLDOWN EVALUATION
# ==============================================================================


def test_special_spin_cooldown_evaluation() -> None:
    """Verify Special Spin requires elapsed_game_time >= special_ready_at."""
    match = create_default_match()

    # Cooldown ready at 6.0s, current time is 0.0s (round 0) -> Illegal
    blade_cd = dataclasses.replace(match.player_1_blade, special_ready_at=6.0)
    match_cd = dataclasses.replace(match, player_1_blade=blade_cd, completed_rounds=0)
    res = check_action_legality(match_cd, DEFAULT_PLAYER_1_ID, Action.SPECIAL_SPIN)
    assert res.is_legal is False
    assert "on cooldown" in (res.reason or "")

    # Current time reaches 6.0s (round 2) -> Exactly ready -> Legal
    match_ready = dataclasses.replace(match, player_1_blade=blade_cd, completed_rounds=2)
    assert match_ready.elapsed_game_time == 6.0
    assert is_action_legal(match_ready, DEFAULT_PLAYER_1_ID, Action.SPECIAL_SPIN) is True

    # Current time exceeds 6.0s (round 3 = 9.0s) -> Legal
    match_past = dataclasses.replace(match, player_1_blade=blade_cd, completed_rounds=3)
    assert match_past.elapsed_game_time == 9.0
    assert is_action_legal(match_past, DEFAULT_PLAYER_1_ID, Action.SPECIAL_SPIN) is True


# ==============================================================================
# E. LEGALITY: MATCH LIFECYCLE & INPUT VALIDATION
# ==============================================================================


def test_finished_match_offers_no_legal_actions() -> None:
    """Verify finished matches reject all actions and return empty legal actions tuple."""
    match = create_default_match()
    finished_result = MatchResult(winner=DEFAULT_PLAYER_1_ID, reason=FinishReason.BURST)
    finished_match = dataclasses.replace(
        match,
        status=MatchStatus.FINISHED,
        result=finished_result,
    )

    for action in Action:
        res = check_action_legality(finished_match, DEFAULT_PLAYER_1_ID, action)
        assert res.is_legal is False
        assert "Match is already finished" in (res.reason or "")

    assert legal_actions(finished_match, DEFAULT_PLAYER_1_ID) == ()
    assert legal_actions(finished_match, DEFAULT_PLAYER_2_ID) == ()


def test_unknown_player_rejected() -> None:
    """Verify querying an unknown player raises ValueError."""
    match = create_default_match()
    with pytest.raises(ValueError, match="Invalid player 'player_99'"):
        check_action_legality(match, "player_99", Action.ATTACK)


def test_invalid_arguments_rejected() -> None:
    """Verify invalid argument types raise TypeError."""
    match = create_default_match()
    with pytest.raises(TypeError, match="action must be an Action enum"):
        check_action_legality(match, DEFAULT_PLAYER_1_ID, "ATTACK")  # type: ignore

    with pytest.raises(TypeError, match="state must be a MatchState"):
        check_action_legality("invalid_state", DEFAULT_PLAYER_1_ID, Action.ATTACK)  # type: ignore


# ==============================================================================
# F. DETERMINISTIC ORDERING & IMMUTABILITY
# ==============================================================================


def test_legal_actions_deterministic_canonical_ordering() -> None:
    """Verify legal_actions returns actions matching ORDERED_ACTIONS."""
    match = create_default_match()

    # At full energy (100) and ready cooldown, all 5 actions are legal
    actions = legal_actions(match, DEFAULT_PLAYER_1_ID)
    assert actions == ORDERED_ACTIONS
    assert actions == (
        Action.CHARGE,
        Action.ATTACK,
        Action.GUARD,
        Action.DODGE,
        Action.SPECIAL_SPIN,
    )

    # At energy 5.0 and ready cooldown: Charge (cost 0) and Guard (cost 4) are legal
    blade_low = dataclasses.replace(match.player_1_blade, current_energy=5.0)
    match_low = dataclasses.replace(match, player_1_blade=blade_low)
    actions_low = legal_actions(match_low, DEFAULT_PLAYER_1_ID)
    assert actions_low == (Action.CHARGE, Action.GUARD)


def test_legality_queries_do_not_mutate_state() -> None:
    """Verify checking action legality leaves MatchState completely unaltered."""
    initial = create_default_match()
    _ = check_action_legality(initial, DEFAULT_PLAYER_1_ID, Action.ATTACK)
    _ = is_action_legal(initial, DEFAULT_PLAYER_1_ID, Action.SPECIAL_SPIN)
    _ = legal_actions(initial, DEFAULT_PLAYER_1_ID)

    assert initial == create_default_match()
    assert initial.player_1_blade.current_energy == 100.0


# ==============================================================================
# G. CONTROLLER COMPATIBILITY & STRICT ENFORCEMENT
# ==============================================================================


def test_controller_default_preserves_type_only_submission() -> None:
    """Verify controller with default enforce_legality=False accepts submissions regardless of energy."""
    match = create_default_match()
    depleted_blade = dataclasses.replace(match.player_1_blade, current_energy=0.0)
    match = dataclasses.replace(match, player_1_blade=depleted_blade)

    controller = MatchController(match, DummyResolver())
    # Submitting Attack at 0 energy is accepted by default controller (test compatibility)
    controller.submit_action(DEFAULT_PLAYER_1_ID, Action.ATTACK)
    assert controller.has_player_submitted(DEFAULT_PLAYER_1_ID) is True


def test_controller_with_strict_legality_enforcement() -> None:
    """Verify controller with enforce_legality=True rejects illegal submissions."""
    match = create_default_match()
    depleted_blade = dataclasses.replace(match.player_1_blade, current_energy=0.0)
    match = dataclasses.replace(match, player_1_blade=depleted_blade)

    controller = MatchController(match, DummyResolver(), enforce_legality=True)

    # Charge at 0 energy is legal -> Accepted
    controller.submit_action(DEFAULT_PLAYER_1_ID, Action.CHARGE)
    assert controller.has_player_submitted(DEFAULT_PLAYER_1_ID) is True

    # Attack at 0 energy for player 2 (with 0 energy) -> Rejected
    depleted_blade_2 = dataclasses.replace(match.player_2_blade, current_energy=0.0)
    match_both_depleted = dataclasses.replace(match, player_2_blade=depleted_blade_2)
    controller_strict = MatchController(match_both_depleted, DummyResolver(), enforce_legality=True)

    with pytest.raises(ActionSubmissionError, match="Illegal action submission: Insufficient energy"):
        controller_strict.submit_action(DEFAULT_PLAYER_2_ID, Action.ATTACK)


def test_controller_get_legal_actions_helper() -> None:
    """Verify controller exposes get_legal_actions helper."""
    controller = MatchController(create_default_match(), DummyResolver())
    assert controller.get_legal_actions(DEFAULT_PLAYER_1_ID) == ORDERED_ACTIONS


def test_actions_module_does_not_initialize_pygame() -> None:
    """Verify importing and using actions module does not initialize Pygame."""
    code = (
        "import pygame\n"
        "from blade_arena.game import Action, create_default_match, legal_actions\n"
        "m = create_default_match()\n"
        "acts = legal_actions(m, 'player_1')\n"
        "assert len(acts) == 5\n"
        "assert not pygame.get_init(), 'Pygame was initialized'\n"
        "assert not pygame.display.get_init(), 'Display was initialized'\n"
    )
    res = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=5)
    assert res.returncode == 0, f"Pygame was initialized on importing actions: {res.stderr}"
