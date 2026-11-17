"""Unit tests for BLADE ARENA geometry, vector math, and stadium boundary functions."""

import math
import pytest

from blade_arena.game.geometry import (
    DEFAULT_ARENA_CENTER,
    DEFAULT_GEOMETRY_EPSILON,
    INITIAL_STADIUM_RADIUS,
    MIN_STADIUM_RADIUS,
    SHRINK_DECREMENT,
    SHRINK_INTERVAL_ROUNDS,
    boundary_margin,
    calculate_stadium_radius,
    distance,
    distance_from_center,
    is_inside_stadium,
    is_outside_stadium,
    move_toward,
    normalize_vector,
    perpendicular_vectors,
    vector_length,
)
from blade_arena.game.models import Position


def test_vector_length_calculations() -> None:
    """Verify vector length calculation for standard and edge cases."""
    assert vector_length(3.0, 4.0) == pytest.approx(5.0)
    assert vector_length(0.0, 0.0) == 0.0
    assert vector_length(-3.0, -4.0) == pytest.approx(5.0)
    assert vector_length(1.0, 0.0) == pytest.approx(1.0)


def test_vector_length_type_and_value_errors() -> None:
    """Verify vector length rejects non-numeric or non-finite arguments."""
    with pytest.raises(TypeError):
        vector_length("3.0", 4.0)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        vector_length(True, 4.0)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        vector_length(float("nan"), 0.0)
    with pytest.raises(ValueError):
        vector_length(0.0, float("inf"))


def test_distance_and_distance_from_center() -> None:
    """Verify distance calculations between Positions and from center."""
    p1 = Position(1.0, 2.0)
    p2 = Position(4.0, 6.0)
    assert distance(p1, p2) == pytest.approx(5.0)

    p_center = Position(0.0, 0.0)
    assert distance_from_center(p1) == pytest.approx(math.hypot(1.0, 2.0))
    assert distance_from_center(p_center) == 0.0

    custom_center = Position(1.0, 1.0)
    assert distance_from_center(p1, center=custom_center) == pytest.approx(1.0)


def test_normalize_vector_standard_and_zero_vector() -> None:
    """Verify vector normalization and zero-vector fallback."""
    nx, ny = normalize_vector(3.0, 4.0)
    assert nx == pytest.approx(0.6)
    assert ny == pytest.approx(0.8)

    # Zero vector uses default fallback (1.0, 0.0)
    fx, fy = normalize_vector(0.0, 0.0)
    assert (fx, fy) == (1.0, 0.0)

    # Zero vector with custom fallback
    fx2, fy2 = normalize_vector(0.0, 0.0, fallback=(0.0, 2.0))
    assert (fx2, fy2) == (0.0, 1.0)

    # Zero fallback vector raises ValueError
    with pytest.raises(ValueError, match="Fallback direction vector cannot be zero-length"):
        normalize_vector(0.0, 0.0, fallback=(0.0, 0.0))


def test_perpendicular_vectors_orthogonality() -> None:
    """Verify perpendicular vectors produce unit orthogonal vectors in CCW and CW directions."""
    # Base vector pointing along +X: (1, 0)
    (ccw_x, ccw_y), (cw_x, cw_y) = perpendicular_vectors(1.0, 0.0)
    assert (ccw_x, ccw_y) == pytest.approx((0.0, 1.0))  # +Y is CCW / Left
    assert (cw_x, cw_y) == pytest.approx((0.0, -1.0))  # -Y is CW / Right

    # Base vector pointing along +Y: (0, 1)
    (ccw_x2, ccw_y2), (cw_x2, cw_y2) = perpendicular_vectors(0.0, 1.0)
    assert (ccw_x2, ccw_y2) == pytest.approx((-1.0, 0.0))
    assert (cw_x2, cw_y2) == pytest.approx((1.0, 0.0))

    # Dot product of base and perpendiculars must be 0
    bx, by = 3.0, 4.0
    (c1x, c1y), (c2x, c2y) = perpendicular_vectors(bx, by)
    assert (bx * c1x + by * c1y) == pytest.approx(0.0, abs=1e-9)
    assert (bx * c2x + by * c2y) == pytest.approx(0.0, abs=1e-9)

    # Magnitudes must be 1.0
    assert math.hypot(c1x, c1y) == pytest.approx(1.0)
    assert math.hypot(c2x, c2y) == pytest.approx(1.0)


def test_boundary_margin_calculations() -> None:
    """Verify boundary margin calculation inside, on, and outside arena."""
    radius = 10.0
    center = Position(0.0, 0.0)

    # At center: margin == radius
    assert boundary_margin(center, radius) == pytest.approx(10.0)

    # Inside at distance 6.0: margin == 4.0
    pos_inside = Position(6.0, 0.0)
    assert boundary_margin(pos_inside, radius) == pytest.approx(4.0)

    # On boundary: margin == 0.0
    pos_edge = Position(10.0, 0.0)
    assert boundary_margin(pos_edge, radius) == pytest.approx(0.0)

    # Outside at distance 12.0: margin == -2.0
    pos_outside = Position(0.0, 12.0)
    assert boundary_margin(pos_outside, radius) == pytest.approx(-2.0)


def test_boundary_margin_validates_inputs() -> None:
    """Verify boundary margin rejects invalid radius or position types."""
    with pytest.raises(TypeError):
        boundary_margin((0.0, 0.0), 10.0)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        boundary_margin(Position(0.0, 0.0), "10.0")  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        boundary_margin(Position(0.0, 0.0), -5.0)
    with pytest.raises(ValueError):
        boundary_margin(Position(0.0, 0.0), 0.0)


def test_inside_and_outside_boundary_queries() -> None:
    """Verify is_inside_stadium and is_outside_stadium on boundary, inside, and outside."""
    radius = 10.0

    # Strictly inside
    p_inside = Position(5.0, 5.0)
    assert is_inside_stadium(p_inside, radius) is True
    assert is_outside_stadium(p_inside, radius) is False

    # Exactly on boundary: equality is inside
    p_on_boundary = Position(10.0, 0.0)
    assert is_inside_stadium(p_on_boundary, radius) is True
    assert is_outside_stadium(p_on_boundary, radius) is False

    # Within numerical tolerance (1e-10 > 10.0)
    p_near_boundary = Position(10.0 + 1e-10, 0.0)
    assert is_inside_stadium(p_near_boundary, radius) is True
    assert is_outside_stadium(p_near_boundary, radius) is False

    # Strictly outside
    p_outside = Position(10.05, 0.0)
    assert is_inside_stadium(p_outside, radius) is False
    assert is_outside_stadium(p_outside, radius) is True


@pytest.mark.parametrize(
    ("completed_rounds", "expected_radius"),
    [
        (0, 10.0),
        (1, 10.0),
        (5, 10.0),
        (6, 9.0),
        (7, 9.0),
        (11, 9.0),
        (12, 8.0),
        (17, 8.0),
        (18, 7.0),
        (23, 7.0),
        (24, 6.0),
        (25, 6.0),
        (29, 6.0),
        (30, 6.0),
        (40, 6.0),
        (100, 6.0),
    ],
)
def test_stadium_radius_shrink_schedule(completed_rounds: int, expected_radius: float) -> None:
    """Verify shrinking schedule decreases by 1 every 6 completed rounds and clamps at 6.0."""
    actual_radius = calculate_stadium_radius(completed_rounds)
    assert actual_radius == pytest.approx(expected_radius)


def test_stadium_radius_custom_parameters() -> None:
    """Verify calculate_stadium_radius supports customized parameters."""
    # Initial 8.0, clamp at 5.0, interval 4, decrement 0.5
    assert calculate_stadium_radius(
        completed_rounds=0, initial_radius=8.0, min_radius=5.0, interval=4, decrement=0.5
    ) == pytest.approx(8.0)
    assert calculate_stadium_radius(
        completed_rounds=4, initial_radius=8.0, min_radius=5.0, interval=4, decrement=0.5
    ) == pytest.approx(7.5)
    assert calculate_stadium_radius(
        completed_rounds=8, initial_radius=8.0, min_radius=5.0, interval=4, decrement=0.5
    ) == pytest.approx(7.0)
    assert calculate_stadium_radius(
        completed_rounds=28, initial_radius=8.0, min_radius=5.0, interval=4, decrement=0.5
    ) == pytest.approx(5.0)


def test_stadium_radius_validation() -> None:
    """Verify calculate_stadium_radius validates argument types and domains."""
    with pytest.raises(TypeError):
        calculate_stadium_radius("6")  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        calculate_stadium_radius(True)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        calculate_stadium_radius(-1)
    with pytest.raises(ValueError):
        calculate_stadium_radius(6, initial_radius=-10.0)
    with pytest.raises(ValueError):
        calculate_stadium_radius(6, min_radius=0.0)
    with pytest.raises(ValueError):
        calculate_stadium_radius(6, interval=0)
    with pytest.raises(ValueError):
        calculate_stadium_radius(6, decrement=-1.0)


def test_move_toward_normal_step() -> None:
    """Verify normal move toward destination without overshoot."""
    start = Position(0.0, 0.0)
    target = Position(10.0, 0.0)
    result = move_toward(start, target, max_distance=2.0)
    assert result.x == pytest.approx(2.0)
    assert result.y == pytest.approx(0.0)


def test_move_toward_prevents_overshoot() -> None:
    """Verify move_toward caps at target and does not overshoot."""
    start = Position(0.0, 0.0)
    target = Position(1.5, 0.0)
    # Move distance 2.0 exceeds distance 1.5; must stop at target
    result = move_toward(start, target, max_distance=2.0)
    assert result.x == pytest.approx(1.5)
    assert result.y == pytest.approx(0.0)


def test_move_toward_already_at_target() -> None:
    """Verify move_toward returns start position when already at target."""
    target = Position(3.0, 4.0)
    result = move_toward(target, target, max_distance=5.0)
    assert result.x == pytest.approx(3.0)
    assert result.y == pytest.approx(4.0)


def test_move_toward_zero_max_distance() -> None:
    """Verify move_toward with max_distance=0 returns start position."""
    start = Position(1.0, 2.0)
    target = Position(5.0, 6.0)
    result = move_toward(start, target, max_distance=0.0)
    assert result == start
