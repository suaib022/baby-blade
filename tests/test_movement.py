"""Unit and integration tests for BLADE ARENA pure movement and dodge mechanics."""

import pytest

from blade_arena.game.blade_definitions import create_blade_state
from blade_arena.game.geometry import (
    DEFAULT_GEOMETRY_EPSILON,
    boundary_margin,
    distance,
)
from blade_arena.game.initial_state import create_default_match
from blade_arena.game.models import (
    Action,
    BladeType,
    Position,
)
from blade_arena.game.movement import (
    ATTACK_MOVE_DISTANCE,
    CHARGE_MOVE_DISTANCE,
    DODGE_EVASION_MARGIN_THRESHOLD,
    DODGE_MOVE_DISTANCE,
    GUARD_MOVE_DISTANCE,
    PLAYER_1_DEFAULT_FORWARD,
    PLAYER_2_DEFAULT_FORWARD,
    PlannedMovementResult,
    SPECIAL_SPIN_MOVE_DISTANCE,
    calculate_blade_movement,
    calculate_dodge_candidates,
    calculate_match_planned_movement,
    calculate_planned_movement,
    evaluate_dodge_success,
    select_dodge_position,
)


def test_movement_distance_constants() -> None:
    """Verify proposed movement distance constants match module specification."""
    assert CHARGE_MOVE_DISTANCE == 1.0
    assert ATTACK_MOVE_DISTANCE == 1.6
    assert GUARD_MOVE_DISTANCE == 0.0
    assert DODGE_MOVE_DISTANCE == 1.4
    assert SPECIAL_SPIN_MOVE_DISTANCE == 2.0
    assert DODGE_EVASION_MARGIN_THRESHOLD == 0.5


def test_guard_stays_stationary() -> None:
    """Verify Guard action does not move the blade and does not trigger dodge evasion."""
    pos = Position(-3.0, 2.0)
    opp = Position(1.0, 2.0)
    result = calculate_blade_movement(
        self_pos=pos,
        self_action=Action.GUARD,
        opp_pos=opp,
        radius=10.0,
    )
    assert result.position == pos
    assert result.distance_moved == 0.0
    assert result.dodge_success is False


def test_charge_moves_toward_center_and_caps() -> None:
    """Verify Charge moves toward (0, 0) by up to 1.0 unit without overshooting."""
    # From (-3.0, 0.0), distance is 3.0 > 1.0 -> moves to (-2.0, 0.0)
    pos_far = Position(-3.0, 0.0)
    opp = Position(2.0, 0.0)
    res_far = calculate_blade_movement(pos_far, Action.CHARGE, opp, radius=10.0)
    assert res_far.position.x == pytest.approx(-2.0)
    assert res_far.position.y == pytest.approx(0.0)
    assert res_far.distance_moved == pytest.approx(1.0)
    assert res_far.dodge_success is False

    # From (-0.6, 0.0), distance is 0.6 <= 1.0 -> stops at (0.0, 0.0) without overshoot
    pos_close = Position(-0.6, 0.0)
    res_close = calculate_blade_movement(pos_close, Action.CHARGE, opp, radius=10.0)
    assert res_close.position.x == pytest.approx(0.0)
    assert res_close.position.y == pytest.approx(0.0)
    assert res_close.distance_moved == pytest.approx(0.6)

    # Already at center (0.0, 0.0) -> stays at center
    pos_center = Position(0.0, 0.0)
    res_center = calculate_blade_movement(pos_center, Action.CHARGE, opp, radius=10.0)
    assert res_center.position.x == pytest.approx(0.0)
    assert res_center.position.y == pytest.approx(0.0)
    assert res_center.distance_moved == 0.0


def test_attack_moves_toward_opponent_and_caps() -> None:
    """Verify Attack moves toward opponent by up to 1.6 units without overshooting."""
    # Distance is 4.0 > 1.6 -> moves 1.6 units
    p1 = Position(-2.0, 0.0)
    p2 = Position(2.0, 0.0)
    res = calculate_blade_movement(p1, Action.ATTACK, p2, radius=10.0)
    assert res.position.x == pytest.approx(-0.4)
    assert res.position.y == pytest.approx(0.0)
    assert res.distance_moved == pytest.approx(1.6)
    assert res.dodge_success is False

    # Close distance: 1.0 <= 1.6 -> caps at opponent position exactly
    p_close = Position(-0.5, 0.0)
    p_opp_close = Position(0.5, 0.0)
    res_capped = calculate_blade_movement(p_close, Action.ATTACK, p_opp_close, radius=10.0)
    assert res_capped.position.x == pytest.approx(0.5)
    assert res_capped.position.y == pytest.approx(0.0)
    assert res_capped.distance_moved == pytest.approx(1.0)


def test_special_spin_moves_toward_opponent_and_caps() -> None:
    """Verify Special Spin moves toward opponent by up to 2.0 units without overshooting."""
    p1 = Position(-2.0, 0.0)
    p2 = Position(2.0, 0.0)
    res = calculate_blade_movement(p1, Action.SPECIAL_SPIN, p2, radius=10.0)
    assert res.position.x == pytest.approx(0.0)
    assert res.position.y == pytest.approx(0.0)
    assert res.distance_moved == pytest.approx(2.0)
    assert res.dodge_success is False

    # Close distance: 1.2 <= 2.0 -> caps at opponent
    p_close = Position(0.0, 0.0)
    p_opp_close = Position(0.0, 1.2)
    res_capped = calculate_blade_movement(p_close, Action.SPECIAL_SPIN, p_opp_close, radius=10.0)
    assert res_capped.position.x == pytest.approx(0.0)
    assert res_capped.position.y == pytest.approx(1.2)
    assert res_capped.distance_moved == pytest.approx(1.2)


def test_dodge_candidates_perpendicular_geometry() -> None:
    """Verify calculate_dodge_candidates computes CCW and CW 1.4-unit offsets."""
    p1 = Position(-2.0, 0.0)
    p2 = Position(2.0, 0.0)
    # Opponent vector is along +X: (1, 0)
    # CCW perp is (0, 1), CW perp is (0, -1)
    c1, c2 = calculate_dodge_candidates(p1, p2, dodge_distance=1.4)
    assert c1.x == pytest.approx(-2.0)
    assert c1.y == pytest.approx(1.4)
    assert c2.x == pytest.approx(-2.0)
    assert c2.y == pytest.approx(-1.4)
    assert distance(p1, c1) == pytest.approx(1.4)
    assert distance(p1, c2) == pytest.approx(1.4)


def test_dodge_selects_candidate_farther_inside_arena() -> None:
    """Verify Dodge chooses the candidate with the larger boundary margin (closer to center)."""
    # Blade is at (6.0, 2.0), opponent at (6.0, 0.0) -> facing vector is (0.0, -2.0) -> pointing -Y
    # Perpendiculars to (0, -1):
    # CCW: (1, 0) -> candidate 1: (7.4, 2.0) -> dist to (0,0) = hypot(7.4, 2) ~ 7.665
    # CW: (-1, 0) -> candidate 2: (4.6, 2.0) -> dist to (0,0) = hypot(4.6, 2) ~ 5.016
    # Candidate 2 is much closer to center, hence farther inside the arena!
    p_self = Position(6.0, 2.0)
    p_opp = Position(6.0, 0.0)
    chosen = select_dodge_position(p_self, p_opp, radius=10.0, dodge_distance=1.4)
    assert chosen.x == pytest.approx(4.6)
    assert chosen.y == pytest.approx(2.0)


def test_dodge_tie_break_horizontal_facing() -> None:
    """Verify symmetric horizontal facing tie-break prefers higher Y coordinate."""
    # From (-2, 0) facing (2, 0), candidates are (-2, 1.4) and (-2, -1.4).
    # Both are at distance sqrt(4 + 1.96) = sqrt(5.96) from (0,0). Boundary margins are equal.
    # Deterministic tie-break rule: higher Y coordinate -> (-2, 1.4)
    p1 = Position(-2.0, 0.0)
    p2 = Position(2.0, 0.0)
    chosen = select_dodge_position(p1, p2, radius=10.0, dodge_distance=1.4)
    assert chosen.x == pytest.approx(-2.0)
    assert chosen.y == pytest.approx(1.4)


def test_dodge_tie_break_vertical_facing() -> None:
    """Verify symmetric vertical facing tie-break (equal Y) prefers higher X coordinate."""
    # From (0, -2) facing (0, 2), vector is (0, 1).
    # CCW perp is (-1, 0) -> C1: (-1.4, -2.0)
    # CW perp is (1, 0) -> C2: (1.4, -2.0)
    # Both candidates have equal distance sqrt(1.96 + 4) = sqrt(5.96) from center.
    # Both candidates have equal Y coordinate (-2.0).
    # Tie-break hierarchy checks X coordinate: C2 has x=1.4 > -1.4, so C2 is selected.
    p1 = Position(0.0, -2.0)
    p2 = Position(0.0, 2.0)
    chosen = select_dodge_position(p1, p2, radius=10.0, dodge_distance=1.4)
    assert chosen.x == pytest.approx(1.4)
    assert chosen.y == pytest.approx(-2.0)


def test_dodge_evasion_success_and_near_edge_failure() -> None:
    """Verify Dodge succeeds only when margin >= 0.5, and fails near the arena edge."""
    radius = 10.0

    # Interior position: distance 5.0 -> margin = 5.0 >= 0.5 -> succeeds
    p_deep_interior = Position(5.0, 0.0)
    assert evaluate_dodge_success(p_deep_interior, radius) is True

    # Exact threshold: distance 9.5 -> margin = 0.5 -> succeeds
    p_exact_threshold = Position(9.5, 0.0)
    assert evaluate_dodge_success(p_exact_threshold, radius) is True

    # Near-edge position: distance 9.7 -> margin = 0.3 < 0.5 -> fails evasion!
    p_near_edge = Position(9.7, 0.0)
    assert evaluate_dodge_success(p_near_edge, radius) is False

    # Near-edge blade action calculation: blade moves to candidate, but dodge_success is False
    # Blade starts at (9.0, 0.0) facing opponent at (0.0, 0.0)
    # Candidates are (9.0, 1.4) and (9.0, -1.4); distance ~ hypot(9, 1.4) ~ 9.108
    # If arena radius is 9.5, margin = 9.5 - 9.108 = 0.392 < 0.5 -> moves but fails evasion
    res = calculate_blade_movement(
        self_pos=Position(9.0, 0.0),
        self_action=Action.DODGE,
        opp_pos=Position(0.0, 0.0),
        radius=9.5,
    )
    assert res.position.x == pytest.approx(9.0)
    assert abs(res.position.y) == pytest.approx(1.4)
    assert res.distance_moved == pytest.approx(1.4)
    assert res.dodge_success is False


def test_coincident_positions_handling() -> None:
    """Verify coincident blade positions handle zero-vector gracefully without division by zero."""
    coincident_pos = Position(0.0, 0.0)

    # Attack when coincident: distance is 0, capped at opponent -> remains at (0, 0)
    res_attack = calculate_blade_movement(
        self_pos=coincident_pos,
        self_action=Action.ATTACK,
        opp_pos=coincident_pos,
        radius=10.0,
    )
    assert res_attack.position == coincident_pos
    assert res_attack.distance_moved == 0.0

    # Dodge when coincident: uses fallback direction without ZeroDivisionError
    res_dodge_p1 = calculate_blade_movement(
        self_pos=coincident_pos,
        self_action=Action.DODGE,
        opp_pos=coincident_pos,
        radius=10.0,
        fallback_direction=PLAYER_1_DEFAULT_FORWARD,  # (1.0, 0.0)
    )
    # Perpendiculars to (1, 0) are (0, 1.4) and (0, -1.4). Tie-break picks Y=1.4
    assert res_dodge_p1.position.x == pytest.approx(0.0)
    assert res_dodge_p1.position.y == pytest.approx(1.4)
    assert res_dodge_p1.dodge_success is True


def test_pairwise_planned_movement_simultaneous_symmetry() -> None:
    """Verify calculate_planned_movement computes simultaneous movements from pre-round positions."""
    b1 = create_blade_state(player_id="player_1", blade_type=BladeType.BALANCED, position=Position(-2.0, 0.0))
    b2 = create_blade_state(player_id="player_2", blade_type=BladeType.BALANCED, position=Position(2.0, 0.0))

    # Both Attack: P1 moves toward (2, 0) by 1.6 -> (-0.4, 0); P2 moves toward (-2, 0) by 1.6 -> (0.4, 0)
    result = calculate_planned_movement(
        blade_1=b1,
        action_1=Action.ATTACK,
        blade_2=b2,
        action_2=Action.ATTACK,
        radius=10.0,
    )

    assert result.player_1_position.x == pytest.approx(-0.4)
    assert result.player_1_position.y == pytest.approx(0.0)
    assert result.player_2_position.x == pytest.approx(0.4)
    assert result.player_2_position.y == pytest.approx(0.0)
    assert result.player_1_dodge_success is False
    assert result.player_2_dodge_success is False
    assert result.stadium_radius == 10.0

    # Helper lookup methods
    assert result.get_position("player_1") == result.player_1_position
    assert result.get_position("player_2") == result.player_2_position
    assert result.get_dodge_success("player_1") is False

    with pytest.raises(KeyError):
        result.get_position("unknown_player")
    with pytest.raises(KeyError):
        result.get_dodge_success("unknown_player")


def test_calculate_match_planned_movement_integration_and_immutability() -> None:
    """Verify calculate_match_planned_movement extracts state and preserves immutability."""
    match = create_default_match()
    orig_p1_x = match.player_1_blade.position.x
    orig_p2_x = match.player_2_blade.position.x

    # P1 Charges toward center; P2 Dodges
    result = calculate_match_planned_movement(match, Action.CHARGE, Action.DODGE)

    # P1 from -2.0 toward 0.0 moves to -1.0
    assert result.player_1_position.x == pytest.approx(-1.0)
    assert result.player_1_position.y == pytest.approx(0.0)
    assert result.player_1_dodge_success is False

    # P2 from 2.0 facing -2.0 (vector (-1, 0)): CCW is (0, -1), CW is (0, 1)
    # Tie-break selects higher Y: (2.0, 1.4)
    assert result.player_2_position.x == pytest.approx(2.0)
    assert result.player_2_position.y == pytest.approx(1.4)
    assert result.player_2_dodge_success is True

    # Verify original match state is strictly unmodified
    assert match.player_1_blade.position.x == orig_p1_x
    assert match.player_2_blade.position.x == orig_p2_x
    assert match.completed_rounds == 0


def test_geometry_and_movement_do_not_import_or_initialize_pygame() -> None:
    """Verify geometry and movement modules are 100% decoupled from Pygame."""
    import sys

    # Check that neither geometry nor movement imports pygame
    import blade_arena.game.geometry as geo
    import blade_arena.game.movement as mov

    # Verify no 'pygame' module was auto-initialized by importing them
    import pygame

    assert not pygame.get_init(), "Pygame should not be initialized by game domain imports"


def test_pairwise_both_players_dodge_symmetric() -> None:
    """Verify simultaneous pairwise dodge by both players from symmetric positions."""
    b1 = create_blade_state(player_id="player_1", blade_type=BladeType.BALANCED, position=Position(-2.0, 0.0))
    b2 = create_blade_state(player_id="player_2", blade_type=BladeType.BALANCED, position=Position(2.0, 0.0))

    result = calculate_planned_movement(
        blade_1=b1,
        action_1=Action.DODGE,
        blade_2=b2,
        action_2=Action.DODGE,
        radius=10.0,
    )

    # P1 from -2.0 facing 2.0 (vector (1, 0)) -> candidates (-2, 1.4) and (-2, -1.4)
    # Tie-break selects higher Y: (-2.0, 1.4)
    assert result.player_1_position.x == pytest.approx(-2.0)
    assert result.player_1_position.y == pytest.approx(1.4)
    assert result.player_1_dodge_success is True

    # P2 from 2.0 facing -2.0 (vector (-1, 0)) -> candidates (2, -1.4) and (2, 1.4)
    # Tie-break selects higher Y: (2.0, 1.4)
    assert result.player_2_position.x == pytest.approx(2.0)
    assert result.player_2_position.y == pytest.approx(1.4)
    assert result.player_2_dodge_success is True


def test_movement_type_and_value_validation() -> None:
    """Verify movement functions validate argument types and bounds."""
    p1 = Position(0.0, 0.0)
    p2 = Position(1.0, 0.0)

    with pytest.raises(TypeError):
        calculate_blade_movement((0.0, 0.0), Action.ATTACK, p2, radius=10.0)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        calculate_blade_movement(p1, "ATTACK", p2, radius=10.0)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        calculate_blade_movement(p1, Action.ATTACK, (1.0, 0.0), radius=10.0)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        calculate_dodge_candidates((0.0, 0.0), p2)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        calculate_dodge_candidates(p1, p2, dodge_distance=-1.0)

