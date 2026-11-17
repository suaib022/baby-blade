"""Unit tests for BLADE ARENA blade types, archetype statistics, and initialization."""

from __future__ import annotations

import dataclasses
import subprocess
import sys
from typing import Mapping

import pytest

from blade_arena.game.blade_definitions import (
    BladeDefinition,
    create_blade,
    create_blade_state,
    get_all_blade_definitions,
    get_blade_definition,
)
from blade_arena.game.initial_state import (
    DEFAULT_PLAYER_1_ID,
    DEFAULT_PLAYER_1_POS,
    DEFAULT_PLAYER_2_ID,
    DEFAULT_PLAYER_2_POS,
    DEFAULT_STADIUM_CENTER,
    DEFAULT_STADIUM_RADIUS,
    create_default_match,
    create_initial_match,
)
from blade_arena.game.match_controller import MatchController
from blade_arena.game.models import (
    Action,
    BladeType,
    MatchState,
    MatchStatus,
    Position,
)
from blade_arena.game.resolver import RoundResolver


class SimpleTestResolver(RoundResolver):
    """Test-only resolver that records and advances exactly 1 round."""

    def resolve_round(
        self,
        state: MatchState,
        player_1_action: Action,
        player_2_action: Action,
    ) -> MatchState:
        return dataclasses.replace(state, completed_rounds=state.completed_rounds + 1)


# ==============================================================================
# A. BLADE TYPES
# ==============================================================================


def test_exactly_four_blade_types_exist() -> None:
    """Verify exactly BALANCED, ATTACKER, DEFENDER, and STAMINA exist."""
    expected = {"BALANCED", "ATTACKER", "DEFENDER", "STAMINA"}
    actual = {bt.name for bt in BladeType}
    assert actual == expected
    assert len(BladeType) == 4


def test_blade_type_identifiers_are_unique() -> None:
    """Verify blade type enum names and values are distinct."""
    names = [bt.name for bt in BladeType]
    values = [bt.value for bt in BladeType]
    assert len(names) == len(set(names))
    assert len(values) == len(set(values))


def test_existing_balanced_references_continue_to_work() -> None:
    """Verify backward compatibility with BladeType.BALANCED."""
    assert BladeType.BALANCED.value == "BALANCED"
    assert BladeType("BALANCED") == BladeType.BALANCED


# ==============================================================================
# B. BLADE DEFINITIONS
# ==============================================================================


def test_balanced_statistics_match_specification() -> None:
    """Verify Balanced blade archetype statistics."""
    defn = get_blade_definition(BladeType.BALANCED)
    assert defn.blade_type == BladeType.BALANCED
    assert defn.name == "Balanced"
    assert defn.max_energy == 100.0
    assert defn.max_stability == 100.0
    assert defn.passive_energy_loss == 3.0
    assert defn.attack_power_multiplier == 1.00
    assert defn.guard_stability_recovery == 5.0
    assert defn.charge_energy_recovery == 20.0


def test_attacker_statistics_match_specification() -> None:
    """Verify Attacker blade archetype statistics."""
    defn = get_blade_definition(BladeType.ATTACKER)
    assert defn.blade_type == BladeType.ATTACKER
    assert defn.name == "Attacker"
    assert defn.max_energy == 100.0
    assert defn.max_stability == 90.0
    assert defn.passive_energy_loss == 4.0
    assert defn.attack_power_multiplier == 1.25
    assert defn.guard_stability_recovery == 5.0
    assert defn.charge_energy_recovery == 20.0


def test_defender_statistics_match_specification() -> None:
    """Verify Defender blade archetype statistics."""
    defn = get_blade_definition(BladeType.DEFENDER)
    assert defn.blade_type == BladeType.DEFENDER
    assert defn.name == "Defender"
    assert defn.max_energy == 100.0
    assert defn.max_stability == 120.0
    assert defn.passive_energy_loss == 3.0
    assert defn.attack_power_multiplier == 0.85
    assert defn.guard_stability_recovery == 10.0
    assert defn.charge_energy_recovery == 20.0


def test_stamina_statistics_match_specification() -> None:
    """Verify Stamina blade archetype statistics."""
    defn = get_blade_definition(BladeType.STAMINA)
    assert defn.blade_type == BladeType.STAMINA
    assert defn.name == "Stamina"
    assert defn.max_energy == 100.0
    assert defn.max_stability == 100.0
    assert defn.passive_energy_loss == 2.0
    assert defn.attack_power_multiplier == 1.00
    assert defn.guard_stability_recovery == 5.0
    assert defn.charge_energy_recovery == 25.0


def test_blade_definitions_are_immutable() -> None:
    """Verify BladeDefinition instances and the registry map cannot be mutated."""
    defn = get_blade_definition(BladeType.BALANCED)
    with pytest.raises(dataclasses.FrozenInstanceError):
        defn.max_energy = 200.0  # type: ignore

    all_defs = get_all_blade_definitions()
    with pytest.raises(TypeError):
        all_defs[BladeType.BALANCED] = defn  # type: ignore


def test_get_blade_definition_rejects_unsupported_or_invalid_type() -> None:
    """Verify get_blade_definition raises KeyError for unsupported and TypeError for invalid types."""
    with pytest.raises(TypeError, match="Expected BladeType enum"):
        get_blade_definition("BALANCED")  # type: ignore

    with pytest.raises(TypeError, match="Expected BladeType enum"):
        get_blade_definition(None)  # type: ignore


def test_blade_definition_validates_field_bounds() -> None:
    """Verify BladeDefinition constructor rejects invalid boundaries."""
    # Positive max_energy
    with pytest.raises(ValueError, match="max_energy must be strictly positive"):
        BladeDefinition(
            blade_type=BladeType.BALANCED,
            name="Test",
            max_energy=0.0,
            max_stability=100.0,
            passive_energy_loss=3.0,
            attack_power_multiplier=1.0,
            guard_stability_recovery=5.0,
            charge_energy_recovery=20.0,
        )

    # Positive max_stability
    with pytest.raises(ValueError, match="max_stability must be strictly positive"):
        BladeDefinition(
            blade_type=BladeType.BALANCED,
            name="Test",
            max_energy=100.0,
            max_stability=-10.0,
            passive_energy_loss=3.0,
            attack_power_multiplier=1.0,
            guard_stability_recovery=5.0,
            charge_energy_recovery=20.0,
        )

    # Non-negative passive loss
    with pytest.raises(ValueError, match="passive_energy_loss must be non-negative"):
        BladeDefinition(
            blade_type=BladeType.BALANCED,
            name="Test",
            max_energy=100.0,
            max_stability=100.0,
            passive_energy_loss=-1.0,
            attack_power_multiplier=1.0,
            guard_stability_recovery=5.0,
            charge_energy_recovery=20.0,
        )

    # Positive attack power multiplier
    with pytest.raises(ValueError, match="attack_power_multiplier must be strictly positive"):
        BladeDefinition(
            blade_type=BladeType.BALANCED,
            name="Test",
            max_energy=100.0,
            max_stability=100.0,
            passive_energy_loss=3.0,
            attack_power_multiplier=0.0,
            guard_stability_recovery=5.0,
            charge_energy_recovery=20.0,
        )

    # Non-negative recoveries
    with pytest.raises(ValueError, match="guard_stability_recovery must be non-negative"):
        BladeDefinition(
            blade_type=BladeType.BALANCED,
            name="Test",
            max_energy=100.0,
            max_stability=100.0,
            passive_energy_loss=3.0,
            attack_power_multiplier=1.0,
            guard_stability_recovery=-5.0,
            charge_energy_recovery=20.0,
        )

    with pytest.raises(ValueError, match="charge_energy_recovery must be non-negative"):
        BladeDefinition(
            blade_type=BladeType.BALANCED,
            name="Test",
            max_energy=100.0,
            max_stability=100.0,
            passive_energy_loss=3.0,
            attack_power_multiplier=1.0,
            guard_stability_recovery=5.0,
            charge_energy_recovery=-20.0,
        )

    # Empty name
    with pytest.raises(ValueError, match="name must be a non-empty string"):
        BladeDefinition(
            blade_type=BladeType.BALANCED,
            name="  ",
            max_energy=100.0,
            max_stability=100.0,
            passive_energy_loss=3.0,
            attack_power_multiplier=1.0,
            guard_stability_recovery=5.0,
            charge_energy_recovery=20.0,
        )


# ==============================================================================
# C. BLADE CREATION
# ==============================================================================


@pytest.mark.parametrize(
    "blade_type, expected_stability",
    [
        (BladeType.BALANCED, 100.0),
        (BladeType.ATTACKER, 90.0),
        (BladeType.DEFENDER, 120.0),
        (BladeType.STAMINA, 100.0),
    ],
)
def test_create_blade_state_for_each_archetype(blade_type: BladeType, expected_stability: float) -> None:
    """Verify each blade archetype initializes with full energy and archetype stability."""
    pos = Position(1.5, -2.5)
    blade = create_blade_state("test_player", blade_type, pos)

    assert blade.player_id == "test_player"
    assert blade.blade_type == blade_type
    assert blade.position == pos
    assert blade.current_energy == 100.0
    assert blade.max_energy == 100.0
    assert blade.current_stability == expected_stability
    assert blade.max_stability == expected_stability
    assert blade.special_ready_at == 0.0


def test_create_blade_alias() -> None:
    """Verify create_blade is an alias to create_blade_state."""
    assert create_blade is create_blade_state


def test_blade_creation_does_not_initialize_pygame() -> None:
    """Verify create_blade_state operates cleanly without Pygame imports."""
    code = (
        "import pygame\n"
        "from blade_arena.game import BladeType, Position, create_blade_state\n"
        "b = create_blade_state('p1', BladeType.DEFENDER, Position(0.0, 0.0))\n"
        "assert b.max_stability == 120.0\n"
        "assert not pygame.get_init(), 'Pygame was initialized'\n"
        "assert not pygame.display.get_init(), 'Display was initialized'\n"
    )
    res = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=5)
    assert res.returncode == 0, f"Pygame was initialized: {res.stderr}"


# ==============================================================================
# D. MATCH CREATION
# ==============================================================================


def test_default_match_has_two_balanced_blades() -> None:
    """Verify create_default_match() continues to create two Balanced blades."""
    match = create_default_match()
    assert match.player_1_blade.blade_type == BladeType.BALANCED
    assert match.player_2_blade.blade_type == BladeType.BALANCED
    assert match.player_1_blade.max_stability == 100.0
    assert match.player_2_blade.max_stability == 100.0
    assert match.player_1_blade.position == DEFAULT_PLAYER_1_POS
    assert match.player_2_blade.position == DEFAULT_PLAYER_2_POS
    assert match.stadium.center == DEFAULT_STADIUM_CENTER
    assert match.stadium.radius == DEFAULT_STADIUM_RADIUS
    assert match.completed_rounds == 0
    assert match.status == MatchStatus.IN_PROGRESS
    assert match.result is None


def test_match_creation_with_different_blade_types() -> None:
    """Verify players can select different archetypes (e.g., Attacker vs Defender)."""
    match = create_initial_match(
        player_1_blade_type=BladeType.ATTACKER,
        player_2_blade_type=BladeType.DEFENDER,
    )
    assert match.player_1_blade.blade_type == BladeType.ATTACKER
    assert match.player_1_blade.current_stability == 90.0
    assert match.player_1_blade.max_stability == 90.0

    assert match.player_2_blade.blade_type == BladeType.DEFENDER
    assert match.player_2_blade.current_stability == 120.0
    assert match.player_2_blade.max_stability == 120.0

    assert match.player_1_blade.player_id == DEFAULT_PLAYER_1_ID
    assert match.player_2_blade.player_id == DEFAULT_PLAYER_2_ID


def test_create_default_match_with_custom_blade_types() -> None:
    """Verify create_default_match accepts custom blade types via keyword args."""
    match = create_default_match(
        player_1_blade_type=BladeType.STAMINA,
        player_2_blade_type=BladeType.ATTACKER,
    )
    assert match.player_1_blade.blade_type == BladeType.STAMINA
    assert match.player_2_blade.blade_type == BladeType.ATTACKER


# ==============================================================================
# E. CONTROLLER INTEGRATION
# ==============================================================================


def test_controller_with_custom_blade_match() -> None:
    """Verify MatchController operates seamlessly with non-default blade combinations."""
    match = create_initial_match(
        player_1_blade_type=BladeType.ATTACKER,
        player_2_blade_type=BladeType.DEFENDER,
    )
    resolver = SimpleTestResolver()
    controller = MatchController(initial_state=match, resolver=resolver)

    assert controller.state.player_1_blade.blade_type == BladeType.ATTACKER
    assert controller.state.player_2_blade.blade_type == BladeType.DEFENDER

    # Submit actions
    controller.submit_action(DEFAULT_PLAYER_1_ID, Action.ATTACK)
    controller.submit_action(DEFAULT_PLAYER_2_ID, Action.GUARD)

    record = controller.resolve_round()
    assert record.round_number == 1
    assert controller.state.completed_rounds == 1

    # Restart preserves custom archetypes
    controller.restart()
    assert controller.state.completed_rounds == 0
    assert controller.state.player_1_blade.blade_type == BladeType.ATTACKER
    assert controller.state.player_1_blade.current_stability == 90.0
    assert controller.state.player_2_blade.blade_type == BladeType.DEFENDER
    assert controller.state.player_2_blade.current_stability == 120.0


# ==============================================================================
# F. NO PREMATURE EFFECTS
# ==============================================================================


def test_no_premature_gameplay_effects() -> None:
    """Verify creating blades or matches does not prematurely apply energy deductions or recovery."""
    blade = create_blade_state("p1", BladeType.ATTACKER, Position(0.0, 0.0))
    # Full energy and stability, no passive loss subtracted
    assert blade.current_energy == 100.0
    assert blade.current_stability == 90.0

    match = create_initial_match(
        player_1_blade_type=BladeType.DEFENDER,
        player_2_blade_type=BladeType.STAMINA,
    )
    assert match.completed_rounds == 0
    assert match.elapsed_game_time == 0.0
    assert match.player_1_blade.current_energy == 100.0
    assert match.player_2_blade.current_energy == 100.0
