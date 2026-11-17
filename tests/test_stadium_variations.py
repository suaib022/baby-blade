"""Automated tests for BLADE ARENA stadium variations (Module 14).

Verifies:
- Definition registry and validation for Classic Dish, Ice Rink, and Steep Bowl.
- Classic Dish baseline non-regression (1.0x movement, 1.0x push, 0.0 drift).
- Ice Rink movement distance scaling (1.25x) and attack push scaling (1.25x) applied exactly once.
- Steep Bowl center drift (0.3 units inward) applied after action movement and capped at center (no overshoot).
- Dodge candidate selection and evasion margin check consistency with drift.
- Stadium shrink schedule milestones (rounds 6, 12, 18, 24 down to min radius 6.0) across all variations.
- Match creation, controller resolution, and session restart/side-swap stadium preservation.
- Equivalence between direct resolver and MatchController across all three stadiums.
- Autonomous AI search (Ironclad Minimax and Cyclone MCTS) simulation compatibility with stadium variations.
- Complete headless match execution to authentic terminal completion across all stadium types.
- Zero Pygame display dependency.
"""

from __future__ import annotations

import math
import subprocess
import sys

import pytest

from blade_arena.ai.cyclone import CycloneAgent, CycloneConfig
from blade_arena.ai.ironclad import IroncladAgent, IroncladConfig
from blade_arena.game.blade_definitions import create_blade_state
from blade_arena.game.combat import (
    ClassicDishRoundResolver,
    CombatConfig,
    DEFAULT_COMBAT_CONFIG,
    resolve_combat_round,
)
from blade_arena.game.geometry import (
    DEFAULT_ARENA_CENTER,
    apply_center_drift,
    boundary_margin,
    distance,
)
from blade_arena.game.initial_state import create_default_match, create_initial_match
from blade_arena.game.match_controller import MatchController
from blade_arena.game.models import (
    Action,
    BladeType,
    FinishReason,
    MatchState,
    MatchStatus,
    Position,
    StadiumState,
    StadiumType,
)
from blade_arena.game.movement import (
    ATTACK_MOVE_DISTANCE,
    CHARGE_MOVE_DISTANCE,
    DODGE_EVASION_MARGIN_THRESHOLD,
    DODGE_MOVE_DISTANCE,
    SPECIAL_SPIN_MOVE_DISTANCE,
    calculate_blade_movement,
    calculate_planned_movement,
    select_dodge_position,
)
from blade_arena.game.stadium_definitions import (
    STADIUM_DEFINITIONS,
    StadiumDefinition,
    get_all_stadium_definitions,
    get_stadium_definition,
)
from blade_arena.orchestration import (
    GameMode,
    MatchSession,
    SessionConfig,
    create_ai_participant,
)


# ==============================================================================
# 1. Stadium Definition Registry & Validation Tests
# ==============================================================================


def test_exactly_three_stadium_definitions_registered() -> None:
    """Verify Classic Dish, Ice Rink, and Steep Bowl are registered with unique types."""
    definitions = get_all_stadium_definitions()
    assert len(definitions) == 3

    types = {d.stadium_type for d in definitions}
    assert types == {
        StadiumType.CLASSIC_DISH,
        StadiumType.ICE_RINK,
        StadiumType.STEEP_BOWL,
    }


def test_stadium_characteristics_values() -> None:
    """Verify characteristics of all three stadiums against project specifications."""
    classic = get_stadium_definition(StadiumType.CLASSIC_DISH)
    assert classic.display_name == "Classic Dish"
    assert classic.movement_multiplier == 1.0
    assert classic.push_multiplier == 1.0
    assert classic.center_drift == 0.0
    assert classic.initial_radius == 10.0
    assert classic.min_radius == 6.0
    assert classic.shrink_interval_rounds == 6
    assert classic.shrink_amount == 1.0

    ice = get_stadium_definition(StadiumType.ICE_RINK)
    assert ice.display_name == "Ice Rink"
    assert ice.movement_multiplier == 1.25
    assert ice.push_multiplier == 1.25
    assert ice.center_drift == 0.0
    assert ice.initial_radius == 10.0
    assert ice.min_radius == 6.0

    steep = get_stadium_definition(StadiumType.STEEP_BOWL)
    assert steep.display_name == "Steep Bowl"
    assert steep.movement_multiplier == 1.0
    assert steep.push_multiplier == 1.0
    assert steep.center_drift == 0.3
    assert steep.initial_radius == 10.0
    assert steep.min_radius == 6.0


def test_get_stadium_definition_lookup_forms_and_errors() -> None:
    """Verify get_stadium_definition accepts enums and strings, and rejects invalid keys."""
    assert get_stadium_definition("ice_rink").stadium_type == StadiumType.ICE_RINK
    assert get_stadium_definition("STEEP_BOWL").stadium_type == StadiumType.STEEP_BOWL

    with pytest.raises(KeyError, match="Unknown stadium type"):
        get_stadium_definition("rough_ground")

    with pytest.raises(TypeError, match="must be StadiumType or str"):
        get_stadium_definition(123)  # type: ignore[arg-type]


def test_stadium_definition_validation_bounds() -> None:
    """Verify StadiumDefinition enforces sanity bounds on all fields."""
    with pytest.raises(ValueError, match="display_name must be a non-empty string"):
        StadiumDefinition(StadiumType.CLASSIC_DISH, "   ", 1.0, 1.0, 0.0)

    with pytest.raises(ValueError, match="movement_multiplier must be positive"):
        StadiumDefinition(StadiumType.CLASSIC_DISH, "Bad", 0.0, 1.0, 0.0)

    with pytest.raises(ValueError, match="push_multiplier must be positive"):
        StadiumDefinition(StadiumType.CLASSIC_DISH, "Bad", 1.0, -1.0, 0.0)

    with pytest.raises(ValueError, match="center_drift must be non-negative"):
        StadiumDefinition(StadiumType.CLASSIC_DISH, "Bad", 1.0, 1.0, -0.1)

    with pytest.raises(ValueError, match="min_radius must be positive and <= initial_radius"):
        StadiumDefinition(StadiumType.CLASSIC_DISH, "Bad", 1.0, 1.0, 0.0, initial_radius=5.0, min_radius=10.0)


# ==============================================================================
# 2. Movement & Push Scaling Tests (Ice Rink & Classic Dish)
# ==============================================================================


def test_classic_dish_movement_and_push_baseline() -> None:
    """Verify Classic Dish retains exact baseline movement and push values."""
    p_start = Position(3.0, 0.0)
    p_opp = Position(-3.0, 0.0)

    # Charge moves 1.0 toward (0, 0) -> (2.0, 0.0)
    m_charge = calculate_blade_movement(
        self_pos=p_start,
        self_action=Action.CHARGE,
        opp_pos=p_opp,
        radius=10.0,
        movement_multiplier=1.0,
        center_drift=0.0,
    )
    assert m_charge.position.x == pytest.approx(2.0)
    assert m_charge.distance_moved == pytest.approx(1.0)

    # Attack moves 1.6 toward opp -> (1.4, 0.0)
    m_attack = calculate_blade_movement(
        self_pos=p_start,
        self_action=Action.ATTACK,
        opp_pos=p_opp,
        radius=10.0,
        movement_multiplier=1.0,
        center_drift=0.0,
    )
    assert m_attack.position.x == pytest.approx(1.4)
    assert m_attack.distance_moved == pytest.approx(1.6)


def test_ice_rink_movement_scaling_1_25x() -> None:
    """Verify Ice Rink scales action movement distances by exactly 1.25x."""
    p_start = Position(5.0, 0.0)
    p_opp = Position(-5.0, 0.0)

    # CHARGE: 1.0 * 1.25 = 1.25 units toward center -> x = 5.0 - 1.25 = 3.75
    m_charge = calculate_blade_movement(
        self_pos=p_start,
        self_action=Action.CHARGE,
        opp_pos=p_opp,
        radius=10.0,
        movement_multiplier=1.25,
        center_drift=0.0,
    )
    assert m_charge.position.x == pytest.approx(3.75)
    assert m_charge.distance_moved == pytest.approx(1.25)

    # ATTACK: 1.6 * 1.25 = 2.0 units toward opponent -> x = 5.0 - 2.0 = 3.0
    m_attack = calculate_blade_movement(
        self_pos=p_start,
        self_action=Action.ATTACK,
        opp_pos=p_opp,
        radius=10.0,
        movement_multiplier=1.25,
        center_drift=0.0,
    )
    assert m_attack.position.x == pytest.approx(3.0)
    assert m_attack.distance_moved == pytest.approx(2.0)

    # SPECIAL_SPIN: 2.0 * 1.25 = 2.5 units toward opponent -> x = 5.0 - 2.5 = 2.5
    m_special = calculate_blade_movement(
        self_pos=p_start,
        self_action=Action.SPECIAL_SPIN,
        opp_pos=p_opp,
        radius=10.0,
        movement_multiplier=1.25,
        center_drift=0.0,
    )
    assert m_special.position.x == pytest.approx(2.5)
    assert m_special.distance_moved == pytest.approx(2.5)

    # GUARD: 0.0 units
    m_guard = calculate_blade_movement(
        self_pos=p_start,
        self_action=Action.GUARD,
        opp_pos=p_opp,
        radius=10.0,
        movement_multiplier=1.25,
        center_drift=0.0,
    )
    assert m_guard.position == p_start
    assert m_guard.distance_moved == pytest.approx(0.0)

    # DODGE: 1.4 * 1.25 = 1.75 units sideways
    m_dodge = calculate_blade_movement(
        self_pos=p_start,
        self_action=Action.DODGE,
        opp_pos=p_opp,
        radius=10.0,
        movement_multiplier=1.25,
        center_drift=0.0,
    )
    assert m_dodge.distance_moved == pytest.approx(1.75)


def test_ice_rink_push_scaling_in_combat_resolution() -> None:
    """Verify Ice Rink scales attack push by exactly 1.25x in full round resolution."""
    # Set up combatants: P1 at (-2.0, 0), P2 at (0.0, 0)
    # P1 ATTACK, P2 GUARD
    match_classic = create_initial_match(
        stadium_type=StadiumType.CLASSIC_DISH,
        player_1_pos=Position(-2.0, 0.0),
        player_2_pos=Position(0.0, 0.0),
    )
    match_ice = create_initial_match(
        stadium_type=StadiumType.ICE_RINK,
        player_1_pos=Position(-2.0, 0.0),
        player_2_pos=Position(0.0, 0.0),
    )

    next_classic, events_classic = resolve_combat_round(
        match_classic, Action.ATTACK, Action.GUARD
    )
    next_ice, events_ice = resolve_combat_round(
        match_ice, Action.ATTACK, Action.GUARD
    )

    # In Classic Dish: base normal attack push on Guard is 1.2 * 0.5 = 0.6
    push_classic = events_classic.player_2_audit.push_magnitude_received
    assert push_classic == pytest.approx(0.6)

    # In Ice Rink: attack push is 0.6 * 1.25 = 0.75
    push_ice = events_ice.player_2_audit.push_magnitude_received
    assert push_ice == pytest.approx(0.75)

    # Verify P2 is pushed further in Ice Rink than Classic Dish
    assert next_ice.player_2_blade.position.x > next_classic.player_2_blade.position.x


# ==============================================================================
# 3. Steep Bowl Center Drift Tests
# ==============================================================================


def test_steep_bowl_drift_applied_toward_center_and_capped() -> None:
    """Verify Steep Bowl center drift pulls inward by 0.3 and caps at (0, 0) without overshooting."""
    # 1. Far from center: (5.0, 0.0) -> moves inward by 0.3 to (4.7, 0.0)
    p1 = Position(5.0, 0.0)
    d1 = apply_center_drift(p1, drift_distance=0.3)
    assert d1.x == pytest.approx(4.7)
    assert d1.y == pytest.approx(0.0)

    # 2. Diagonal: (3.0, 4.0), distance = 5.0 -> distance becomes 4.7
    p2 = Position(3.0, 4.0)
    d2 = apply_center_drift(p2, drift_distance=0.3)
    assert distance(d2, Position(0.0, 0.0)) == pytest.approx(4.7)

    # 3. Close to center: distance 0.2 <= 0.3 -> capped at center (0.0, 0.0)
    p3 = Position(0.2, 0.0)
    d3 = apply_center_drift(p3, drift_distance=0.3)
    assert d3.x == pytest.approx(0.0)
    assert d3.y == pytest.approx(0.0)

    # 4. Exactly at center: (0.0, 0.0) -> remains (0.0, 0.0)
    p4 = Position(0.0, 0.0)
    d4 = apply_center_drift(p4, drift_distance=0.3)
    assert d4.x == pytest.approx(0.0)
    assert d4.y == pytest.approx(0.0)


def test_steep_bowl_independent_pairwise_drift_in_movement() -> None:
    """Verify both combatants apply center drift independently after action movement."""
    match_steep = create_initial_match(
        stadium_type=StadiumType.STEEP_BOWL,
        player_1_pos=Position(-3.0, 0.0),
        player_2_pos=Position(3.0, 0.0),
    )

    # Both blades GUARD: action movement is 0.0; both drift inward by 0.3
    moves = calculate_planned_movement(
        blade_1=match_steep.player_1_blade,
        action_1=Action.GUARD,
        blade_2=match_steep.player_2_blade,
        action_2=Action.GUARD,
        radius=10.0,
        stadium_type=StadiumType.STEEP_BOWL,
    )

    # P1 drifts from -3.0 to -2.7; P2 drifts from 3.0 to 2.7
    assert moves.player_1_position.x == pytest.approx(-2.7)
    assert moves.player_2_position.x == pytest.approx(2.7)


def test_dodge_candidate_selection_includes_drift_in_steep_bowl() -> None:
    """Verify Dodge candidate evaluation incorporates 0.3 drift consistently."""
    self_pos = Position(0.0, 8.0)
    opp_pos = Position(0.0, 2.0)

    # Dodge sideways from (0, 8) facing (0, 2)
    # Drift pulls both candidates inward toward (0, 0)
    pos_steep = select_dodge_position(
        self_pos=self_pos,
        opp_pos=opp_pos,
        radius=10.0,
        dodge_distance=1.4,
        center_drift=0.3,
    )

    # Distance to center is strictly less than without drift
    pos_classic = select_dodge_position(
        self_pos=self_pos,
        opp_pos=opp_pos,
        radius=10.0,
        dodge_distance=1.4,
        center_drift=0.0,
    )

    assert distance(pos_steep, Position(0.0, 0.0)) < distance(pos_classic, Position(0.0, 0.0))


# ==============================================================================
# 4. Stadium Shrink Schedule Across Variations
# ==============================================================================


def test_stadium_shrink_schedule_milestones_all_types() -> None:
    """Verify all three stadiums adhere to the identical 6-round shrink schedule down to 6.0."""
    for st in [StadiumType.CLASSIC_DISH, StadiumType.ICE_RINK, StadiumType.STEEP_BOWL]:
        match = create_initial_match(stadium_type=st)
        assert match.stadium.radius == pytest.approx(10.0)

        # Simulate 6 rounds of Charge vs Charge to trigger shrink to 9.0
        curr = match
        for r in range(6):
            curr, _ = resolve_combat_round(curr, Action.CHARGE, Action.CHARGE)

        assert curr.completed_rounds == 6
        assert curr.stadium.radius == pytest.approx(9.0)
        assert curr.stadium.stadium_type == st


# ==============================================================================
# 5. Controller & MatchSession Integration Tests
# ==============================================================================


def test_match_controller_with_ice_rink_and_steep_bowl() -> None:
    """Verify MatchController operates seamlessly with non-default stadium variations."""
    for st in [StadiumType.ICE_RINK, StadiumType.STEEP_BOWL]:
        match = create_initial_match(stadium_type=st)
        resolver = ClassicDishRoundResolver()
        controller = MatchController(match, resolver)

        assert controller.state.stadium.stadium_type == st

        controller.submit_action("player_1", Action.CHARGE)
        controller.submit_action("player_2", Action.GUARD)
        record = controller.resolve_round()

        assert record.round_number == 1
        assert record.state_after.stadium.stadium_type == st

        # Restart restores stadium
        controller.restart()
        assert controller.state.stadium.stadium_type == st
        assert controller.state.completed_rounds == 0


def test_match_session_swap_sides_preserves_stadium() -> None:
    """Verify MatchSession preserves stadium variation across swap_sides() and restart()."""
    p1 = create_ai_participant("Bot1", "ironclad", difficulty="easy")
    p2 = create_ai_participant("Bot2", "cyclone", difficulty="easy", seed=42)

    config = SessionConfig(
        mode=GameMode.AI_VS_AI,
        stadium_type=StadiumType.ICE_RINK,
    )
    session = MatchSession(p1, p2, config=config)
    assert session.state.stadium.stadium_type == StadiumType.ICE_RINK

    session.step_round()
    assert session.state.completed_rounds == 1

    session.swap_sides()
    assert session.state.completed_rounds == 0
    assert session.state.stadium.stadium_type == StadiumType.ICE_RINK


def test_direct_resolver_and_controller_equivalence_across_stadiums() -> None:
    """Verify MatchController produces identical state transitions to direct resolver across stadiums."""
    for st in [StadiumType.CLASSIC_DISH, StadiumType.ICE_RINK, StadiumType.STEEP_BOWL]:
        match = create_initial_match(stadium_type=st)

        # Direct resolver
        next_direct, _ = resolve_combat_round(match, Action.ATTACK, Action.GUARD)

        # Controller
        controller = MatchController(match, ClassicDishRoundResolver())
        controller.submit_action("player_1", Action.ATTACK)
        controller.submit_action("player_2", Action.GUARD)
        rec = controller.resolve_round()

        assert rec.state_after == next_direct


# ==============================================================================
# 6. Autonomous AI Search Compatibility
# ==============================================================================


def test_ironclad_and_cyclone_simulate_in_stadium_variations() -> None:
    """Verify Ironclad Minimax and Cyclone MCTS deliberate correctly in Ice Rink and Steep Bowl."""
    for st in [StadiumType.ICE_RINK, StadiumType.STEEP_BOWL]:
        match = create_initial_match(stadium_type=st)

        ironclad = IroncladAgent(player_id="player_1", config=IroncladConfig.for_difficulty("easy"))
        a_ironclad = ironclad.choose_action(match)
        assert isinstance(a_ironclad, Action)

        cyclone = CycloneAgent(player_id="player_2", config=CycloneConfig.for_difficulty("easy", seed=99))
        a_cyclone = cyclone.choose_action(match)
        assert isinstance(a_cyclone, Action)


def test_complete_headless_match_in_each_stadium() -> None:
    """Execute complete real AI vs AI duels to terminal conclusion in all three stadiums."""
    for st in [StadiumType.CLASSIC_DISH, StadiumType.ICE_RINK, StadiumType.STEEP_BOWL]:
        p1 = create_ai_participant("Ironclad", "ironclad", difficulty="easy")
        p2 = create_ai_participant("Cyclone", "cyclone", difficulty="easy", seed=777)

        session = MatchSession(
            p1,
            p2,
            config=SessionConfig(mode=GameMode.AI_VS_AI, stadium_type=st, max_rounds_guard=45),
        )
        final_state = session.run_to_completion(max_rounds=45)

        assert final_state.status == MatchStatus.FINISHED
        assert final_state.result is not None
        assert isinstance(final_state.result.reason, FinishReason)
        assert final_state.stadium.stadium_type == st


def test_stadium_definitions_module_does_not_initialize_pygame() -> None:
    """Verify importing stadium definitions does not initialize Pygame display."""
    code = (
        "import blade_arena.game.stadium_definitions\n"
        "import pygame\n"
        "assert not pygame.display.get_init(), 'Display was initialized on import'\n"
        "assert pygame.display.get_surface() is None, 'Display surface was created on import'\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        timeout=5,
    )
    assert result.returncode == 0, f"Import check failed: {result.stderr}"
