"""Stadium archetype definitions and central registry for BLADE ARENA.

Provides immutable definitions and validation for all supported arena layouts:
- Classic Dish: standard baseline movement, push, and shrink dynamics.
- Ice Rink: low-friction arena with 1.25x action movement and 1.25x attack push.
- Steep Bowl: sloped arena with up to 0.3 units inward radial drift toward center.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, Tuple, Union

from blade_arena.game.models import StadiumType


@dataclass(frozen=True)
class StadiumDefinition:
    """Immutable characteristics and balance parameters for a stadium archetype."""

    stadium_type: StadiumType
    display_name: str
    movement_multiplier: float
    push_multiplier: float
    center_drift: float
    initial_radius: float = 10.0
    min_radius: float = 6.0
    shrink_interval_rounds: int = 6
    shrink_amount: float = 1.0

    def __post_init__(self) -> None:
        if not isinstance(self.stadium_type, StadiumType):
            raise TypeError(f"stadium_type must be a StadiumType enum, got {type(self.stadium_type).__name__}")
        if not isinstance(self.display_name, str) or not self.display_name.strip():
            raise ValueError("display_name must be a non-empty string")

        for name, val in [
            ("movement_multiplier", self.movement_multiplier),
            ("push_multiplier", self.push_multiplier),
        ]:
            if isinstance(val, bool) or not isinstance(val, (int, float)):
                raise TypeError(f"{name} must be numeric, got {type(val).__name__}")
            if not math.isfinite(val) or val <= 0.0:
                raise ValueError(f"{name} must be positive and finite, got {val}")

        if isinstance(self.center_drift, bool) or not isinstance(self.center_drift, (int, float)):
            raise TypeError(f"center_drift must be numeric, got {type(self.center_drift).__name__}")
        if not math.isfinite(self.center_drift) or self.center_drift < 0.0:
            raise ValueError(f"center_drift must be non-negative and finite, got {self.center_drift}")

        if self.initial_radius <= 0.0 or not math.isfinite(self.initial_radius):
            raise ValueError(f"initial_radius must be positive, got {self.initial_radius}")
        if self.min_radius <= 0.0 or self.min_radius > self.initial_radius:
            raise ValueError(f"min_radius must be positive and <= initial_radius, got {self.min_radius}")
        if self.shrink_interval_rounds <= 0:
            raise ValueError(f"shrink_interval_rounds must be positive, got {self.shrink_interval_rounds}")
        if self.shrink_amount < 0.0 or not math.isfinite(self.shrink_amount):
            raise ValueError(f"shrink_amount must be non-negative, got {self.shrink_amount}")


# Central immutable definitions registry
STADIUM_DEFINITIONS: Dict[StadiumType, StadiumDefinition] = {
    StadiumType.CLASSIC_DISH: StadiumDefinition(
        stadium_type=StadiumType.CLASSIC_DISH,
        display_name="Classic Dish",
        movement_multiplier=1.0,
        push_multiplier=1.0,
        center_drift=0.0,
        initial_radius=10.0,
        min_radius=6.0,
        shrink_interval_rounds=6,
        shrink_amount=1.0,
    ),
    StadiumType.ICE_RINK: StadiumDefinition(
        stadium_type=StadiumType.ICE_RINK,
        display_name="Ice Rink",
        movement_multiplier=1.25,
        push_multiplier=1.25,
        center_drift=0.0,
        initial_radius=10.0,
        min_radius=6.0,
        shrink_interval_rounds=6,
        shrink_amount=1.0,
    ),
    StadiumType.STEEP_BOWL: StadiumDefinition(
        stadium_type=StadiumType.STEEP_BOWL,
        display_name="Steep Bowl",
        movement_multiplier=1.0,
        push_multiplier=1.0,
        center_drift=0.3,
        initial_radius=10.0,
        min_radius=6.0,
        shrink_interval_rounds=6,
        shrink_amount=1.0,
    ),
}


def get_stadium_definition(stadium_type: Union[StadiumType, str]) -> StadiumDefinition:
    """Retrieve the authoritative immutable definition for a stadium archetype.

    Args:
        stadium_type: StadiumType enum member or case-insensitive string name.

    Returns:
        The matching StadiumDefinition.

    Raises:
        KeyError: If the stadium type is not recognized.
        TypeError: If stadium_type is neither StadiumType nor str.
    """
    if isinstance(stadium_type, StadiumType):
        key = stadium_type
    elif isinstance(stadium_type, str):
        normalized = stadium_type.strip().upper()
        try:
            key = StadiumType(normalized)
        except ValueError:
            raise KeyError(
                f"Unknown stadium type string '{stadium_type}'. Supported: {[t.value for t in StadiumType]}"
            )
    else:
        raise TypeError(f"stadium_type must be StadiumType or str, got {type(stadium_type).__name__}")

    try:
        return STADIUM_DEFINITIONS[key]
    except KeyError:
        raise KeyError(f"No definition registered for stadium type {key}")


def get_all_stadium_definitions() -> Tuple[StadiumDefinition, ...]:
    """Retrieve all registered stadium definitions in canonical order."""
    return tuple(STADIUM_DEFINITIONS.values())
