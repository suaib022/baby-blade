"""Pure movement and displacement calculations for BLADE ARENA combatants.

Implements simultaneous planned-movement calculations for all five turn actions:
- Charge: moves toward arena center (0, 0) by up to 1.0 unit (capped at center).
- Attack: moves toward opponent pre-round position by up to 1.6 units (capped at target).
- Guard: stays stationary (0.0 movement).
- Dodge: moves 1.4 units along one of two orthogonal directions to the opponent vector,
  selecting the candidate farther inside the arena, with a deterministic tie-break.
  Evades attacks only if the resulting position is at least 0.5 units inside the boundary.
- Special Spin: moves toward opponent pre-round position by up to 2.0 units (capped at target).

All calculations are pure, deterministic, and execute from a common pre-round snapshot.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Tuple

from blade_arena.game.geometry import (
    DEFAULT_ARENA_CENTER,
    DEFAULT_GEOMETRY_EPSILON,
    apply_center_drift,
    boundary_margin,
    distance,
    move_toward,
    perpendicular_vectors,
)
from blade_arena.game.models import (
    Action,
    BladeState,
    MatchState,
    Position,
    StadiumType,
)
from blade_arena.game.stadium_definitions import get_stadium_definition

# ==============================================================================
# PROPOSED MOVEMENT TUNING ASSUMPTIONS (Tunable parameters, not fixed PDF constants)
# ==============================================================================
CHARGE_MOVE_DISTANCE: float = 1.0
ATTACK_MOVE_DISTANCE: float = 1.6
GUARD_MOVE_DISTANCE: float = 0.0
DODGE_MOVE_DISTANCE: float = 1.4
SPECIAL_SPIN_MOVE_DISTANCE: float = 2.0

# Minimum arena boundary margin required for a Dodge to successfully evade incoming attacks
DODGE_EVASION_MARGIN_THRESHOLD: float = 0.5

# Stable fallback facing directions for coincident blades (no division by zero)
PLAYER_1_DEFAULT_FORWARD: Tuple[float, float] = (1.0, 0.0)
PLAYER_2_DEFAULT_FORWARD: Tuple[float, float] = (-1.0, 0.0)


@dataclass(frozen=True)
class SingleBladeMovement:
    """Displacement result for a single blade in a round."""

    position: Position
    dodge_success: bool
    distance_moved: float

    def __post_init__(self) -> None:
        if not isinstance(self.position, Position):
            raise TypeError(f"position must be Position, got {type(self.position).__name__}")
        if not isinstance(self.dodge_success, bool):
            raise TypeError(f"dodge_success must be bool, got {type(self.dodge_success).__name__}")
        if isinstance(self.distance_moved, bool) or not isinstance(self.distance_moved, (int, float)):
            raise TypeError(f"distance_moved must be numeric, got {type(self.distance_moved).__name__}")
        if not math.isfinite(self.distance_moved) or self.distance_moved < 0.0:
            raise ValueError(f"distance_moved must be finite and non-negative, got {self.distance_moved}")


@dataclass(frozen=True)
class PlannedMovementResult:
    """Pairwise planned-movement outcome for both combatants in a round.

    Calculated simultaneously from a common pre-round state snapshot.
    """

    player_1_position: Position
    player_2_position: Position
    player_1_dodge_success: bool
    player_2_dodge_success: bool
    stadium_radius: float

    def __post_init__(self) -> None:
        if not isinstance(self.player_1_position, Position):
            raise TypeError(f"player_1_position must be Position, got {type(self.player_1_position).__name__}")
        if not isinstance(self.player_2_position, Position):
            raise TypeError(f"player_2_position must be Position, got {type(self.player_2_position).__name__}")
        if not isinstance(self.player_1_dodge_success, bool):
            raise TypeError("player_1_dodge_success must be bool")
        if not isinstance(self.player_2_dodge_success, bool):
            raise TypeError("player_2_dodge_success must be bool")
        if isinstance(self.stadium_radius, bool) or not isinstance(self.stadium_radius, (int, float)):
            raise TypeError(f"stadium_radius must be numeric, got {type(self.stadium_radius).__name__}")
        if not math.isfinite(self.stadium_radius) or self.stadium_radius <= 0.0:
            raise ValueError(f"stadium_radius must be finite and positive, got {self.stadium_radius}")

    def get_position(self, player_id: str, player_1_id: str = "player_1", player_2_id: str = "player_2") -> Position:
        """Retrieve destination position for a specified player ID."""
        if player_id == player_1_id:
            return self.player_1_position
        if player_id == player_2_id:
            return self.player_2_position
        raise KeyError(f"Unknown player ID '{player_id}' (expected '{player_1_id}' or '{player_2_id}')")

    def get_dodge_success(self, player_id: str, player_1_id: str = "player_1", player_2_id: str = "player_2") -> bool:
        """Retrieve dodge evasion status for a specified player ID."""
        if player_id == player_1_id:
            return self.player_1_dodge_success
        if player_id == player_2_id:
            return self.player_2_dodge_success
        raise KeyError(f"Unknown player ID '{player_id}' (expected '{player_1_id}' or '{player_2_id}')")


def calculate_dodge_candidates(
    self_pos: Position,
    opp_pos: Position,
    dodge_distance: float = DODGE_MOVE_DISTANCE,
    fallback_direction: Tuple[float, float] = (1.0, 0.0),
    tolerance: float = DEFAULT_GEOMETRY_EPSILON,
) -> Tuple[Position, Position]:
    """Calculate the two perpendicular candidate positions for a Dodge action.

    The base vector is directed from self_pos toward opp_pos. If blades coincide,
    fallback_direction is used.

    Args:
        self_pos: Pre-round position of dodging blade.
        opp_pos: Pre-round position of opponent blade.
        dodge_distance: Travel distance (default: 1.4 units).
        fallback_direction: Direction vector if positions coincide.
        tolerance: Numerical threshold for coincident position detection.

    Returns:
        A 2-tuple of candidate Positions:
        - Candidate 1: Counter-Clockwise perpendicular candidate.
        - Candidate 2: Clockwise perpendicular candidate.
    """
    if not isinstance(self_pos, Position):
        raise TypeError(f"self_pos must be Position, got {type(self_pos).__name__}")
    if not isinstance(opp_pos, Position):
        raise TypeError(f"opp_pos must be Position, got {type(opp_pos).__name__}")
    if isinstance(dodge_distance, bool) or not isinstance(dodge_distance, (int, float)):
        raise TypeError(f"dodge_distance must be numeric, got {type(dodge_distance).__name__}")
    if not math.isfinite(dodge_distance) or dodge_distance < 0.0:
        raise ValueError(f"dodge_distance must be finite and non-negative, got {dodge_distance}")

    dx = opp_pos.x - self_pos.x
    dy = opp_pos.y - self_pos.y

    (ccw_x, ccw_y), (cw_x, cw_y) = perpendicular_vectors(
        dx, dy, fallback=fallback_direction, tolerance=tolerance
    )

    c1 = Position(self_pos.x + dodge_distance * ccw_x, self_pos.y + dodge_distance * ccw_y)
    c2 = Position(self_pos.x + dodge_distance * cw_x, self_pos.y + dodge_distance * cw_y)
    return (c1, c2)


def select_dodge_position(
    self_pos: Position,
    opp_pos: Position,
    radius: float,
    dodge_distance: float = DODGE_MOVE_DISTANCE,
    fallback_direction: Tuple[float, float] = (1.0, 0.0),
    center: Position = DEFAULT_ARENA_CENTER,
    tolerance: float = DEFAULT_GEOMETRY_EPSILON,
    center_drift: float = 0.0,
) -> Position:
    """Select the optimal dodge candidate that places the blade farther inside the arena.

    Selection Criteria:
    - Computes the boundary margin (radius - distance_to_center) for both candidates.
    - If center_drift > 0 (e.g. Steep Bowl), applies inward center drift to candidates
      prior to margin comparison so candidate selection and final position remain consistent.
    - Selects the candidate with the larger boundary margin (closer to arena center).
    - Deterministic Tie-Break:
      If boundary margins are equal within numerical tolerance:
      1. Candidate with larger Y coordinate.
      2. If Y coordinates are equal within tolerance, candidate with larger X coordinate.
      3. If both coordinates are identical, Candidate 1 (CCW).

    Args:
        self_pos: Pre-round position of dodging blade.
        opp_pos: Pre-round position of opponent blade.
        radius: Current stadium radius.
        dodge_distance: Travel distance.
        fallback_direction: Facing direction if blades coincide.
        center: Stadium center.
        tolerance: Numerical tolerance.
        center_drift: Inward radial drift toward center (e.g. 0.3 for Steep Bowl).

    Returns:
        The selected candidate Position (including drift if applicable).
    """
    c1, c2 = calculate_dodge_candidates(
        self_pos,
        opp_pos,
        dodge_distance=dodge_distance,
        fallback_direction=fallback_direction,
        tolerance=tolerance,
    )

    c1_eval = apply_center_drift(c1, center_drift, center=center, tolerance=tolerance) if center_drift > tolerance else c1
    c2_eval = apply_center_drift(c2, center_drift, center=center, tolerance=tolerance) if center_drift > tolerance else c2

    margin_1 = boundary_margin(c1_eval, radius, center=center)
    margin_2 = boundary_margin(c2_eval, radius, center=center)

    margin_diff = margin_1 - margin_2

    # Strictly farther inside
    if margin_diff > tolerance:
        return c1_eval
    if margin_diff < -tolerance:
        return c2_eval

    # Deterministic tie-break: higher Y coordinate
    y_diff = c1_eval.y - c2_eval.y
    if y_diff > tolerance:
        return c1_eval
    if y_diff < -tolerance:
        return c2_eval

    # Deterministic tie-break: higher X coordinate
    x_diff = c1_eval.x - c2_eval.x
    if x_diff > tolerance:
        return c1_eval
    if x_diff < -tolerance:
        return c2_eval

    # Fallback to Candidate 1 (CCW)
    return c1_eval


def evaluate_dodge_success(
    position: Position,
    radius: float,
    threshold: float = DODGE_EVASION_MARGIN_THRESHOLD,
    center: Position = DEFAULT_ARENA_CENTER,
    tolerance: float = DEFAULT_GEOMETRY_EPSILON,
) -> bool:
    """Evaluate whether a dodging blade's final position successfully evades incoming attacks.

    Rule:
    Dodge succeeds only if final position is at least threshold (default: 0.5) units
    inside the arena boundary:
        boundary_margin(position, radius, center) >= threshold - tolerance

    A blade near the boundary edge (< 0.5 margin) or outside the arena still moves,
    but fails to evade attacks (returns False).

    Args:
        position: Final position of dodging blade.
        radius: Current arena radius.
        threshold: Minimum required boundary margin (default: 0.5).
        center: Arena center.
        tolerance: Numerical tolerance.

    Returns:
        True if evasion succeeds, False otherwise.
    """
    margin = boundary_margin(position, radius, center=center)
    return margin >= (threshold - tolerance)


def calculate_blade_movement(
    self_pos: Position,
    self_action: Action,
    opp_pos: Position,
    radius: float,
    fallback_direction: Tuple[float, float] = (1.0, 0.0),
    center: Position = DEFAULT_ARENA_CENTER,
    tolerance: float = DEFAULT_GEOMETRY_EPSILON,
    movement_multiplier: float = 1.0,
    center_drift: float = 0.0,
) -> SingleBladeMovement:
    """Calculate the resulting position and dodge status for a single blade.

    Movement rules per action:
    - CHARGE: moves toward center (0, 0) by up to 1.0 * movement_multiplier (capped at center).
    - ATTACK: moves toward opp_pos by up to 1.6 * movement_multiplier (capped at opp_pos).
    - GUARD: stationary (0.0 distance moved before any drift).
    - DODGE: moves 1.4 * movement_multiplier units sideways toward arena interior; evasion evaluated at boundary.
    - SPECIAL_SPIN: moves toward opp_pos by up to 2.0 * movement_multiplier (capped at opp_pos).

    Inward center drift (e.g. 0.3 for Steep Bowl):
    - Applied after action movement before hit checks, capped at center (no overshoot).
    - For DODGE, candidate selection incorporates center drift directly so the chosen
      candidate, final position, and dodge evasion check remain consistent.

    Args:
        self_pos: Pre-round position of the acting blade.
        self_action: Chosen action for this round.
        opp_pos: Pre-round position of the opponent blade.
        radius: Arena radius for this round.
        fallback_direction: Facing direction if self_pos and opp_pos coincide.
        center: Arena center.
        tolerance: Numerical tolerance.
        movement_multiplier: Arena action movement multiplier (e.g. 1.25 for Ice Rink).
        center_drift: Inward radial drift toward arena center (e.g. 0.3 for Steep Bowl).

    Returns:
        A SingleBladeMovement record.
    """
    if not isinstance(self_pos, Position):
        raise TypeError(f"self_pos must be Position, got {type(self_pos).__name__}")
    if not isinstance(opp_pos, Position):
        raise TypeError(f"opp_pos must be Position, got {type(opp_pos).__name__}")
    if not isinstance(self_action, Action):
        raise TypeError(f"self_action must be an Action enum, got {type(self_action).__name__}")

    if self_action == Action.DODGE:
        destination = select_dodge_position(
            self_pos=self_pos,
            opp_pos=opp_pos,
            radius=radius,
            dodge_distance=DODGE_MOVE_DISTANCE * movement_multiplier,
            fallback_direction=fallback_direction,
            center=center,
            tolerance=tolerance,
            center_drift=center_drift,
        )
        success = evaluate_dodge_success(
            position=destination,
            radius=radius,
            threshold=DODGE_EVASION_MARGIN_THRESHOLD,
            center=center,
            tolerance=tolerance,
        )
        return SingleBladeMovement(
            position=destination,
            dodge_success=success,
            distance_moved=distance(self_pos, destination),
        )

    # 1. Base action movement
    if self_action == Action.GUARD:
        raw_dest = self_pos
    elif self_action == Action.CHARGE:
        raw_dest = move_toward(
            start=self_pos,
            target=center,
            max_distance=CHARGE_MOVE_DISTANCE * movement_multiplier,
            tolerance=tolerance,
        )
    elif self_action == Action.ATTACK:
        raw_dest = move_toward(
            start=self_pos,
            target=opp_pos,
            max_distance=ATTACK_MOVE_DISTANCE * movement_multiplier,
            tolerance=tolerance,
        )
    elif self_action == Action.SPECIAL_SPIN:
        raw_dest = move_toward(
            start=self_pos,
            target=opp_pos,
            max_distance=SPECIAL_SPIN_MOVE_DISTANCE * movement_multiplier,
            tolerance=tolerance,
        )
    else:
        raise ValueError(f"Unsupported action: {self_action}")

    # 2. Inward center drift (applied after action movement, capped at center)
    if center_drift > tolerance:
        final_dest = apply_center_drift(
            position=raw_dest,
            drift_distance=center_drift,
            center=center,
            tolerance=tolerance,
        )
    else:
        final_dest = raw_dest

    return SingleBladeMovement(
        position=final_dest,
        dodge_success=False,
        distance_moved=distance(self_pos, final_dest),
    )


def calculate_planned_movement(
    blade_1: BladeState,
    action_1: Action,
    blade_2: BladeState,
    action_2: Action,
    radius: float,
    fallback_1: Tuple[float, float] = PLAYER_1_DEFAULT_FORWARD,
    fallback_2: Tuple[float, float] = PLAYER_2_DEFAULT_FORWARD,
    center: Position = DEFAULT_ARENA_CENTER,
    tolerance: float = DEFAULT_GEOMETRY_EPSILON,
    movement_multiplier: float = 1.0,
    center_drift: float = 0.0,
    stadium_type: Optional[StadiumType] = None,
) -> PlannedMovementResult:
    """Pairwise planned-movement calculation using pre-round combatant states.

    Both combatants calculate their planned positions simultaneously using each other's
    pre-round positions. Neither blade state is mutated.

    Args:
        blade_1: Player 1's pre-round blade state.
        action_1: Player 1's selected action.
        blade_2: Player 2's pre-round blade state.
        action_2: Player 2's selected action.
        radius: Current stadium radius.
        fallback_1: Facing fallback for Player 1 if coincident.
        fallback_2: Facing fallback for Player 2 if coincident.
        center: Stadium center.
        tolerance: Numerical tolerance.
        movement_multiplier: Optional movement scalar (overridden by stadium_type if provided).
        center_drift: Optional inward drift distance (overridden by stadium_type if provided).
        stadium_type: Optional StadiumType enum to automatically configure multipliers and drift.

    Returns:
        A PlannedMovementResult with resulting positions and dodge success flags.
    """
    if not isinstance(blade_1, BladeState):
        raise TypeError(f"blade_1 must be BladeState, got {type(blade_1).__name__}")
    if not isinstance(blade_2, BladeState):
        raise TypeError(f"blade_2 must be BladeState, got {type(blade_2).__name__}")

    if stadium_type is not None:
        stadium_def = get_stadium_definition(stadium_type)
        movement_multiplier = stadium_def.movement_multiplier
        center_drift = stadium_def.center_drift

    move_1 = calculate_blade_movement(
        self_pos=blade_1.position,
        self_action=action_1,
        opp_pos=blade_2.position,
        radius=radius,
        fallback_direction=fallback_1,
        center=center,
        tolerance=tolerance,
        movement_multiplier=movement_multiplier,
        center_drift=center_drift,
    )

    move_2 = calculate_blade_movement(
        self_pos=blade_2.position,
        self_action=action_2,
        opp_pos=blade_1.position,
        radius=radius,
        fallback_direction=fallback_2,
        center=center,
        tolerance=tolerance,
        movement_multiplier=movement_multiplier,
        center_drift=center_drift,
    )

    return PlannedMovementResult(
        player_1_position=move_1.position,
        player_2_position=move_2.position,
        player_1_dodge_success=move_1.dodge_success,
        player_2_dodge_success=move_2.dodge_success,
        stadium_radius=radius,
    )


def calculate_match_planned_movement(
    match_state: MatchState,
    action_1: Action,
    action_2: Action,
    fallback_1: Tuple[float, float] = PLAYER_1_DEFAULT_FORWARD,
    fallback_2: Tuple[float, float] = PLAYER_2_DEFAULT_FORWARD,
    tolerance: float = DEFAULT_GEOMETRY_EPSILON,
) -> PlannedMovementResult:
    """Pairwise planned-movement calculation from a complete MatchState instance.

    Uses `match_state.stadium.radius` as the arena radius and automatically extracts
    stadium parameters (movement multiplier and drift) from `match_state.stadium.stadium_type`.
    Does not mutate the match state.

    Args:
        match_state: Current match state snapshot.
        action_1: Player 1's action.
        action_2: Player 2's action.
        fallback_1: Facing fallback for Player 1 if coincident.
        fallback_2: Facing fallback for Player 2 if coincident.
        tolerance: Numerical tolerance.

    Returns:
        A PlannedMovementResult.
    """
    if not isinstance(match_state, MatchState):
        raise TypeError(f"match_state must be MatchState, got {type(match_state).__name__}")

    return calculate_planned_movement(
        blade_1=match_state.player_1_blade,
        action_1=action_1,
        blade_2=match_state.player_2_blade,
        action_2=action_2,
        radius=match_state.stadium.radius,
        fallback_1=fallback_1,
        fallback_2=fallback_2,
        center=match_state.stadium.center,
        tolerance=tolerance,
        stadium_type=match_state.stadium.stadium_type,
    )
