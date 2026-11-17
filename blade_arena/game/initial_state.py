"""Initial state factories for BLADE ARENA matches.

Constructs fresh, independent match instances with customizable or default blade archetypes.
"""

from __future__ import annotations

from blade_arena.game.blade_definitions import create_blade_state
from blade_arena.game.models import (
    BladeState,
    BladeType,
    MatchState,
    MatchStatus,
    Position,
    StadiumState,
    StadiumType,
)

# Implementation assumptions and defaults
DEFAULT_PLAYER_1_ID: str = "player_1"
DEFAULT_PLAYER_2_ID: str = "player_2"

# Proposed starting positions (symmetric along the x-axis)
DEFAULT_PLAYER_1_POS: Position = Position(-2.0, 0.0)
DEFAULT_PLAYER_2_POS: Position = Position(2.0, 0.0)

# Proposed stadium origin and radius from project specification
DEFAULT_STADIUM_CENTER: Position = Position(0.0, 0.0)
DEFAULT_STADIUM_RADIUS: float = 10.0

# Initial attribute values for the Balanced blade archetype (retained for backward compatibility)
INITIAL_ENERGY: float = 100.0
MAX_ENERGY: float = 100.0
INITIAL_STABILITY: float = 100.0
MAX_STABILITY: float = 100.0
INITIAL_SPECIAL_READY_AT: float = 0.0


def create_initial_match(
    player_1_blade_type: BladeType = BladeType.BALANCED,
    player_2_blade_type: BladeType = BladeType.BALANCED,
    stadium_type: StadiumType = StadiumType.CLASSIC_DISH,
    player_1_id: str = DEFAULT_PLAYER_1_ID,
    player_2_id: str = DEFAULT_PLAYER_2_ID,
    player_1_pos: Position = DEFAULT_PLAYER_1_POS,
    player_2_pos: Position = DEFAULT_PLAYER_2_POS,
    stadium_center: Position = DEFAULT_STADIUM_CENTER,
    stadium_radius: float = DEFAULT_STADIUM_RADIUS,
) -> MatchState:
    """Create a new match state with customizable blade types.

    Produces:
    - Two combatants with attributes derived from their respective BladeDefinitions.
    - Full energy and full archetype stability for both combatants.
    - Special Spin ready at game time 0.0s for both combatants.
    - Stadium archetype (defaults to Classic Dish).
    - Zero completed rounds (elapsed game time = 0.0s).
    - IN_PROGRESS match status and no match result.

    Args:
        player_1_blade_type: Blade archetype for player 1 (default: BALANCED).
        player_2_blade_type: Blade archetype for player 2 (default: BALANCED).
        stadium_type: Stadium archetype (default: CLASSIC_DISH).
        player_1_id: Identifier for player 1.
        player_2_id: Identifier for player 2.
        player_1_pos: Initial position for player 1.
        player_2_pos: Initial position for player 2.
        stadium_center: Origin of the arena dish.
        stadium_radius: Initial radius of the dish.

    Returns:
        An independent, fully immutable MatchState instance.
    """
    blade_1 = create_blade_state(
        player_id=player_1_id,
        blade_type=player_1_blade_type,
        position=player_1_pos,
    )
    blade_2 = create_blade_state(
        player_id=player_2_id,
        blade_type=player_2_blade_type,
        position=player_2_pos,
    )
    stadium = StadiumState(
        stadium_type=stadium_type,
        center=stadium_center,
        radius=stadium_radius,
    )
    return MatchState(
        player_1_blade=blade_1,
        player_2_blade=blade_2,
        stadium=stadium,
        completed_rounds=0,
        status=MatchStatus.IN_PROGRESS,
        result=None,
    )


def create_default_match(
    player_1_id: str = DEFAULT_PLAYER_1_ID,
    player_2_id: str = DEFAULT_PLAYER_2_ID,
    player_1_blade_type: BladeType = BladeType.BALANCED,
    player_2_blade_type: BladeType = BladeType.BALANCED,
    stadium_type: StadiumType = StadiumType.CLASSIC_DISH,
) -> MatchState:
    """Create a default match state (defaults to two Balanced blades).

    Maintains 100% backward compatibility with Module 2 & Module 3 callers.
    """
    return create_initial_match(
        player_1_blade_type=player_1_blade_type,
        player_2_blade_type=player_2_blade_type,
        stadium_type=stadium_type,
        player_1_id=player_1_id,
        player_2_id=player_2_id,
    )
