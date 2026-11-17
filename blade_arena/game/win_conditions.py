"""Terminal evaluation and win condition rules for BLADE ARENA.

Provides pure, deterministic evaluation of elimination conditions and points decisions:
- Ring-out: blade center is strictly outside the current stadium radius.
- Burst: blade stability is less than or equal to 0.0.
- Spin-out: blade energy is less than or equal to 0.0.
- Cause Priority: Ring-out > Burst > Spin-out when a blade triggers multiple causes.
- Simultaneous Elimination: Both blades eliminated in the same round results in a Draw.
- Points Decision: If neither blade is eliminated after completed round 40 (120 logical seconds),
  the winner is decided by normalized points:
  0.40 * (energy / max_energy) + 0.40 * (stability / max_stability) + 0.20 * max(0, 1 - dist/radius).
  A score difference <= 1e-6 is a Draw.
"""

from __future__ import annotations

import math
from typing import Optional, Tuple

from blade_arena.game.geometry import (
    DEFAULT_ARENA_CENTER,
    DEFAULT_GEOMETRY_EPSILON,
    distance_from_center,
    is_outside_stadium,
)
from blade_arena.game.models import (
    BladeState,
    FinishReason,
    MatchResult,
    MatchState,
    MatchStatus,
    Position,
    STANDARD_MAX_ROUNDS,
)

# Points decision weighting constants
DEFAULT_POINTS_WEIGHT_ENERGY: float = 0.40
DEFAULT_POINTS_WEIGHT_STABILITY: float = 0.40
DEFAULT_POINTS_WEIGHT_POSITION: float = 0.20

# Points difference threshold for a draw
POINTS_DECISION_TOLERANCE: float = 1e-6

# Elimination cause display priority order
ELIMINATION_CAUSE_PRIORITY: Tuple[FinishReason, ...] = (
    FinishReason.RING_OUT,
    FinishReason.BURST,
    FinishReason.SPIN_OUT,
)


def calculate_blade_points(
    blade: BladeState,
    stadium_radius: float,
    center: Position = DEFAULT_ARENA_CENTER,
) -> float:
    """Calculate the normalized point score for a blade at round 40 conclusion.

    Formula:
        0.40 * (energy / max_energy)
      + 0.40 * (stability / max_stability)
      + 0.20 * max(0.0, 1.0 - (distance_from_center / stadium_radius))

    Args:
        blade: BladeState to score.
        stadium_radius: Final stadium radius.
        center: Arena center position.

    Returns:
        A normalized float score in range [0.0, 1.0].
    """
    if not isinstance(blade, BladeState):
        raise TypeError(f"blade must be BladeState, got {type(blade).__name__}")
    if isinstance(stadium_radius, bool) or not isinstance(stadium_radius, (int, float)):
        raise TypeError(f"stadium_radius must be numeric, got {type(stadium_radius).__name__}")
    if not math.isfinite(stadium_radius) or stadium_radius <= 0.0:
        raise ValueError(f"stadium_radius must be finite and positive, got {stadium_radius}")

    energy_ratio = blade.current_energy / blade.max_energy
    stability_ratio = blade.current_stability / blade.max_stability

    dist = distance_from_center(blade.position, center=center)
    center_component = max(0.0, 1.0 - (dist / stadium_radius))

    score = (
        DEFAULT_POINTS_WEIGHT_ENERGY * energy_ratio
        + DEFAULT_POINTS_WEIGHT_STABILITY * stability_ratio
        + DEFAULT_POINTS_WEIGHT_POSITION * center_component
    )
    return score


def get_blade_elimination_causes(
    blade: BladeState,
    stadium_radius: float,
    center: Position = DEFAULT_ARENA_CENTER,
    tolerance: float = DEFAULT_GEOMETRY_EPSILON,
) -> Tuple[FinishReason, ...]:
    """Identify all elimination causes currently affecting a blade.

    Elimination Criteria:
    - Ring-out: blade center strictly outside current radius (tolerance-aware).
    - Burst: stability <= 0.0.
    - Spin-out: energy <= 0.0.

    Causes are returned in priority order:
    1. RING_OUT
    2. BURST
    3. SPIN_OUT

    Args:
        blade: BladeState to evaluate.
        stadium_radius: Current stadium radius.
        center: Stadium center.
        tolerance: Numerical tolerance.

    Returns:
        A tuple of FinishReason members (empty if blade is not eliminated).
    """
    if not isinstance(blade, BladeState):
        raise TypeError(f"blade must be BladeState, got {type(blade).__name__}")

    causes: list[FinishReason] = []

    # Priority 1: Ring-out
    if is_outside_stadium(blade.position, stadium_radius, center=center, tolerance=tolerance):
        causes.append(FinishReason.RING_OUT)

    # Priority 2: Burst
    if blade.current_stability <= 0.0:
        causes.append(FinishReason.BURST)

    # Priority 3: Spin-out
    if blade.current_energy <= 0.0:
        causes.append(FinishReason.SPIN_OUT)

    return tuple(causes)


def evaluate_match_termination(
    state: MatchState,
    max_rounds: int = STANDARD_MAX_ROUNDS,
    tolerance: float = DEFAULT_GEOMETRY_EPSILON,
) -> Optional[MatchResult]:
    """Pure terminal evaluator determining whether a match has finished and its outcome.

    Evaluation Process:
    1. Check elimination causes for both combatants after all effects and arena shrink.
    2. If both eliminated in the same round: Draw with reason SIMULTANEOUS_ELIMINATION.
    3. If only one eliminated: Other player wins with reason set to eliminated player's
       highest priority cause (RING_OUT > BURST > SPIN_OUT).
    4. If neither eliminated:
       - If completed_rounds >= max_rounds (40 rounds): Points decision is evaluated.
         Higher score wins; absolute difference <= 1e-6 is a Draw.
       - If completed_rounds < max_rounds: Match remains IN_PROGRESS (returns None).

    Note: 40th-round elimination takes priority over a points decision.

    Args:
        state: MatchState to evaluate.
        max_rounds: Maximum round limit (default: 40).
        tolerance: Numerical tolerance.

    Returns:
        MatchResult if the match has concluded, None if in progress.
    """
    if not isinstance(state, MatchState):
        raise TypeError(f"state must be MatchState, got {type(state).__name__}")

    radius = state.stadium.radius
    center = state.stadium.center

    causes_1 = get_blade_elimination_causes(state.player_1_blade, radius, center=center, tolerance=tolerance)
    causes_2 = get_blade_elimination_causes(state.player_2_blade, radius, center=center, tolerance=tolerance)

    eliminated_1 = len(causes_1) > 0
    eliminated_2 = len(causes_2) > 0

    p1_id = state.player_1_blade.player_id
    p2_id = state.player_2_blade.player_id

    # Case 1: Both eliminated simultaneously
    if eliminated_1 and eliminated_2:
        return MatchResult(
            winner=None,
            reason=FinishReason.SIMULTANEOUS_ELIMINATION,
            player_1_causes=causes_1,
            player_2_causes=causes_2,
        )

    # Case 2: Only Player 1 eliminated -> Player 2 wins
    if eliminated_1 and not eliminated_2:
        primary_reason = causes_1[0]
        return MatchResult(
            winner=p2_id,
            reason=primary_reason,
            player_1_causes=causes_1,
            player_2_causes=(),
        )

    # Case 3: Only Player 2 eliminated -> Player 1 wins
    if eliminated_2 and not eliminated_1:
        primary_reason = causes_2[0]
        return MatchResult(
            winner=p1_id,
            reason=primary_reason,
            player_1_causes=(),
            player_2_causes=causes_2,
        )

    # Case 4: Neither eliminated -> Check round 40 limit
    if state.completed_rounds >= max_rounds:
        score_1 = calculate_blade_points(state.player_1_blade, radius, center=center)
        score_2 = calculate_blade_points(state.player_2_blade, radius, center=center)
        diff = score_1 - score_2

        if abs(diff) <= POINTS_DECISION_TOLERANCE:
            winner = None
        elif diff > POINTS_DECISION_TOLERANCE:
            winner = p1_id
        else:
            winner = p2_id

        return MatchResult(
            winner=winner,
            reason=FinishReason.POINTS_DECISION,
            player_1_causes=(),
            player_2_causes=(),
            scores=(score_1, score_2),
        )

    # Neither eliminated and completed_rounds < max_rounds -> Match in progress
    return None


def is_match_terminal(
    state: MatchState,
    max_rounds: int = STANDARD_MAX_ROUNDS,
    tolerance: float = DEFAULT_GEOMETRY_EPSILON,
) -> bool:
    """Check whether a match state is terminal (finished)."""
    if state.status == MatchStatus.FINISHED:
        return True
    return evaluate_match_termination(state, max_rounds=max_rounds, tolerance=tolerance) is not None
