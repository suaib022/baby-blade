"""Pure geometry, vector mathematics, and stadium boundary functions for BLADE ARENA.

Provides deterministic, Pygame-independent calculations for:
- Vector normalization, lengths, and orthogonal projections.
- Arena center distance and boundary margin calculations.
- Inside/outside boundary queries with consistent numerical tolerance.
- Stadium shrink schedule based on completed match rounds.
- Toward-target motion with overshoot capping.
"""

from __future__ import annotations

import math
from typing import Tuple

from blade_arena.game.models import Position

# Central geometry tolerance for floating-point comparisons
DEFAULT_GEOMETRY_EPSILON: float = 1e-9

# Standard arena origin
DEFAULT_ARENA_CENTER: Position = Position(0.0, 0.0)

# Stadium shrink constants (project rules)
INITIAL_STADIUM_RADIUS: float = 10.0
MIN_STADIUM_RADIUS: float = 6.0
SHRINK_INTERVAL_ROUNDS: int = 6
SHRINK_DECREMENT: float = 1.0


def vector_length(dx: float, dy: float) -> float:
    """Calculate the Euclidean length of a 2D vector (dx, dy)."""
    if isinstance(dx, bool) or not isinstance(dx, (int, float)):
        raise TypeError(f"dx must be numeric, got {type(dx).__name__}")
    if isinstance(dy, bool) or not isinstance(dy, (int, float)):
        raise TypeError(f"dy must be numeric, got {type(dy).__name__}")
    if not math.isfinite(dx) or not math.isfinite(dy):
        raise ValueError(f"Vector components must be finite, got dx={dx}, dy={dy}")
    return math.hypot(dx, dy)


def distance(p1: Position, p2: Position) -> float:
    """Calculate Euclidean distance between two Positions."""
    if not isinstance(p1, Position):
        raise TypeError(f"p1 must be a Position instance, got {type(p1).__name__}")
    if not isinstance(p2, Position):
        raise TypeError(f"p2 must be a Position instance, got {type(p2).__name__}")
    return p1.distance_to(p2)


def distance_from_center(position: Position, center: Position = DEFAULT_ARENA_CENTER) -> float:
    """Calculate Euclidean distance from a specified arena center (default: 0, 0)."""
    if not isinstance(position, Position):
        raise TypeError(f"position must be a Position instance, got {type(position).__name__}")
    if not isinstance(center, Position):
        raise TypeError(f"center must be a Position instance, got {type(center).__name__}")
    return position.distance_to(center)


def normalize_vector(
    dx: float,
    dy: float,
    fallback: Tuple[float, float] = (1.0, 0.0),
    tolerance: float = DEFAULT_GEOMETRY_EPSILON,
) -> Tuple[float, float]:
    """Normalize a 2D vector to unit length.

    If the vector magnitude is less than or equal to tolerance (zero-length vector),
    returns the normalized fallback direction.

    Args:
        dx: X component of vector.
        dy: Y component of vector.
        fallback: Direction vector to use if magnitude is zero (default: (1.0, 0.0)).
        tolerance: Numerical threshold below which vector is considered zero-length.

    Returns:
        A tuple of (unit_x, unit_y) with magnitude 1.0.
    """
    length = vector_length(dx, dy)
    if length <= tolerance:
        fb_len = vector_length(fallback[0], fallback[1])
        if fb_len <= tolerance:
            raise ValueError("Fallback direction vector cannot be zero-length")
        return (fallback[0] / fb_len, fallback[1] / fb_len)
    return (dx / length, dy / length)


def perpendicular_vectors(
    dx: float,
    dy: float,
    fallback: Tuple[float, float] = (1.0, 0.0),
    tolerance: float = DEFAULT_GEOMETRY_EPSILON,
) -> Tuple[Tuple[float, float], Tuple[float, float]]:
    """Compute the two unit orthogonal (perpendicular) vectors in 2D Cartesian plane.

    Args:
        dx: X component of base vector.
        dy: Y component of base vector.
        fallback: Fallback direction if (dx, dy) is zero-length.
        tolerance: Numerical threshold for zero-length detection.

    Returns:
        A 2-tuple:
        - Candidate 1: Counter-Clockwise (CCW / Left / +90 deg): (-unit_y, unit_x)
        - Candidate 2: Clockwise (CW / Right / -90 deg): (unit_y, -unit_x)
    """
    ux, uy = normalize_vector(dx, dy, fallback=fallback, tolerance=tolerance)
    ccw = (-uy, ux)
    cw = (uy, -ux)
    return (ccw, cw)


def boundary_margin(
    position: Position,
    radius: float,
    center: Position = DEFAULT_ARENA_CENTER,
) -> float:
    """Calculate the signed distance from the arena boundary to the given position.

    Positive margin: strictly inside the boundary.
    Zero margin: exactly on the boundary edge.
    Negative margin: strictly outside the boundary (ring-out territory).

    Args:
        position: Blade center position.
        radius: Current stadium radius.
        center: Arena center position (default: (0, 0)).

    Returns:
        radius - distance_to_center
    """
    if not isinstance(position, Position):
        raise TypeError(f"position must be a Position instance, got {type(position).__name__}")
    if isinstance(radius, bool) or not isinstance(radius, (int, float)):
        raise TypeError(f"radius must be numeric, got {type(radius).__name__}")
    if not math.isfinite(radius) or radius <= 0.0:
        raise ValueError(f"radius must be finite and positive, got {radius}")

    dist = distance_from_center(position, center)
    return radius - dist


def is_inside_stadium(
    position: Position,
    radius: float,
    center: Position = DEFAULT_ARENA_CENTER,
    tolerance: float = DEFAULT_GEOMETRY_EPSILON,
) -> bool:
    """Check if a position's center is inside or on the stadium boundary.

    Equality is considered inside: distance <= radius + tolerance.

    Args:
        position: Position to test.
        radius: Current arena radius.
        center: Arena center.
        tolerance: Numerical tolerance for floating-point comparisons.

    Returns:
        True if inside or on boundary, False if strictly outside.
    """
    margin = boundary_margin(position, radius, center=center)
    return margin >= -tolerance


def is_outside_stadium(
    position: Position,
    radius: float,
    center: Position = DEFAULT_ARENA_CENTER,
    tolerance: float = DEFAULT_GEOMETRY_EPSILON,
) -> bool:
    """Check if a position's center is strictly outside the stadium boundary.

    Ring-out definition: distance > radius + tolerance (margin < -tolerance).

    Args:
        position: Position to test.
        radius: Current arena radius.
        center: Arena center.
        tolerance: Numerical tolerance for floating-point comparisons.

    Returns:
        True if strictly outside, False if on or inside boundary.
    """
    return not is_inside_stadium(position, radius, center=center, tolerance=tolerance)


def calculate_stadium_radius(
    completed_rounds: int,
    initial_radius: float = INITIAL_STADIUM_RADIUS,
    min_radius: float = MIN_STADIUM_RADIUS,
    interval: int = SHRINK_INTERVAL_ROUNDS,
    decrement: float = SHRINK_DECREMENT,
) -> float:
    """Calculate the stadium radius as a pure function of completed rounds.

    Shrinking Schedule:
    - Starts at initial_radius (default: 10.0).
    - After every `interval` completed rounds (default: 6), decreases by `decrement` (default: 1.0).
    - Rounds 0..5: 10.0
    - Rounds 6..11: 9.0
    - Rounds 12..17: 8.0
    - Rounds 18..23: 7.0
    - Rounds 24+: 6.0 (clamped at min_radius).

    This calculation is idempotent and derived directly from initial configured radius
    and completed rounds to prevent accidental double-shrinking.

    Args:
        completed_rounds: Number of rounds completed so far.
        initial_radius: Starting arena radius.
        min_radius: Clamped minimum arena radius.
        interval: Completed rounds required per shrink step.
        decrement: Arena radius reduction per shrink step.

    Returns:
        The current arena radius.
    """
    if isinstance(completed_rounds, bool) or not isinstance(completed_rounds, int):
        raise TypeError(f"completed_rounds must be an integer, got {type(completed_rounds).__name__}")
    if completed_rounds < 0:
        raise ValueError(f"completed_rounds must be non-negative, got {completed_rounds}")

    if isinstance(initial_radius, bool) or not isinstance(initial_radius, (int, float)):
        raise TypeError(f"initial_radius must be numeric, got {type(initial_radius).__name__}")
    if not math.isfinite(initial_radius) or initial_radius <= 0.0:
        raise ValueError(f"initial_radius must be finite and positive, got {initial_radius}")

    if isinstance(min_radius, bool) or not isinstance(min_radius, (int, float)):
        raise TypeError(f"min_radius must be numeric, got {type(min_radius).__name__}")
    if not math.isfinite(min_radius) or min_radius <= 0.0:
        raise ValueError(f"min_radius must be finite and positive, got {min_radius}")

    if isinstance(interval, bool) or not isinstance(interval, int) or interval <= 0:
        raise ValueError(f"interval must be a positive integer, got {interval}")

    if isinstance(decrement, bool) or not isinstance(decrement, (int, float)) or decrement < 0.0:
        raise ValueError(f"decrement must be a non-negative number, got {decrement}")

    shrink_steps = completed_rounds // interval
    shrunk_radius = initial_radius - (shrink_steps * decrement)
    return max(min_radius, shrunk_radius)


def move_toward(
    start: Position,
    target: Position,
    max_distance: float,
    tolerance: float = DEFAULT_GEOMETRY_EPSILON,
) -> Position:
    """Move from start toward target position by up to max_distance.

    Overshoot Prevention:
    If the Euclidean distance between start and target is less than or equal to
    max_distance, movement stops exactly at the target.

    If start and target already coincide (distance <= tolerance), movement
    distance is zero and start is returned.

    Args:
        start: Current blade position.
        target: Target destination position (e.g. opponent or arena center).
        max_distance: Maximum travel distance in arena units.
        tolerance: Numerical tolerance for distance comparisons.

    Returns:
        A new Position representing the destination.
    """
    if not isinstance(start, Position):
        raise TypeError(f"start must be a Position instance, got {type(start).__name__}")
    if not isinstance(target, Position):
        raise TypeError(f"target must be a Position instance, got {type(target).__name__}")
    if isinstance(max_distance, bool) or not isinstance(max_distance, (int, float)):
        raise TypeError(f"max_distance must be numeric, got {type(max_distance).__name__}")
    if not math.isfinite(max_distance) or max_distance < 0.0:
        raise ValueError(f"max_distance must be finite and non-negative, got {max_distance}")

    dist = start.distance_to(target)

    # Already at target or distance to move is negligible
    if dist <= tolerance or max_distance <= tolerance:
        return start

    # Capped at target to avoid overshooting
    if max_distance >= dist:
        return Position(target.x, target.y)

    # Move along unit vector
    step = max_distance
    ux = (target.x - start.x) / dist
    uy = (target.y - start.y) / dist
    return Position(start.x + step * ux, start.y + step * uy)


def apply_center_drift(
    position: Position,
    drift_distance: float,
    center: Position = DEFAULT_ARENA_CENTER,
    tolerance: float = DEFAULT_GEOMETRY_EPSILON,
) -> Position:
    """Apply radial drift toward the arena center, capped at center (no overshoot).

    Moves the position toward center by at most drift_distance. If distance to center
    is less than or equal to drift_distance, places the blade directly at center.

    Args:
        position: Starting position before drift.
        drift_distance: Maximum drift displacement in arena units.
        center: Stadium center position (default: (0, 0)).
        tolerance: Numerical tolerance.

    Returns:
        New Position displaced toward center, capped at center.
    """
    if not isinstance(position, Position):
        raise TypeError(f"position must be a Position instance, got {type(position).__name__}")
    if not isinstance(center, Position):
        raise TypeError(f"center must be a Position instance, got {type(center).__name__}")
    if isinstance(drift_distance, bool) or not isinstance(drift_distance, (int, float)):
        raise TypeError(f"drift_distance must be numeric, got {type(drift_distance).__name__}")
    if not math.isfinite(drift_distance) or drift_distance < 0.0:
        raise ValueError(f"drift_distance must be finite and non-negative, got {drift_distance}")

    if drift_distance <= tolerance:
        return position

    return move_toward(
        start=position,
        target=center,
        max_distance=drift_distance,
        tolerance=tolerance,
    )
