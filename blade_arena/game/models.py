"""Core domain models for BLADE ARENA.

Provides pure-Python immutable data structures for actions, positions, blade states,
stadium properties, and match status.
"""

from __future__ import annotations

import enum
import math
from dataclasses import dataclass
from typing import Optional

# Logical game timing constants
SECONDS_PER_ROUND: float = 3.0
STANDARD_MAX_ROUNDS: int = 40


class Action(str, enum.Enum):
    """The five turn actions available to a blade."""

    CHARGE = "CHARGE"
    ATTACK = "ATTACK"
    GUARD = "GUARD"
    DODGE = "DODGE"
    SPECIAL_SPIN = "SPECIAL_SPIN"


class BladeType(str, enum.Enum):
    """Categorization of blade archetype."""

    BALANCED = "BALANCED"
    ATTACKER = "ATTACKER"
    DEFENDER = "DEFENDER"
    STAMINA = "STAMINA"


class StadiumType(str, enum.Enum):
    """Categorization of arena layout."""

    CLASSIC_DISH = "CLASSIC_DISH"
    ICE_RINK = "ICE_RINK"
    STEEP_BOWL = "STEEP_BOWL"


class MatchStatus(str, enum.Enum):
    """Lifecycle status of a match."""

    IN_PROGRESS = "IN_PROGRESS"
    FINISHED = "FINISHED"


class FinishReason(str, enum.Enum):
    """Reason a match concluded."""

    RING_OUT = "RING_OUT"
    BURST = "BURST"
    SPIN_OUT = "SPIN_OUT"
    SIMULTANEOUS_ELIMINATION = "SIMULTANEOUS_ELIMINATION"
    POINTS_DECISION = "POINTS_DECISION"


@dataclass(frozen=True)
class Position:
    """2D Cartesian coordinates within the stadium."""

    x: float
    y: float

    def __post_init__(self) -> None:
        for name, val in [("x", self.x), ("y", self.y)]:
            if isinstance(val, bool) or not isinstance(val, (int, float)):
                raise TypeError(f"Position coordinate '{name}' must be numeric, got {type(val).__name__}")
            if not math.isfinite(val):
                raise ValueError(f"Position coordinate '{name}' must be finite, got {val}")

    def distance_to(self, other: Position) -> float:
        """Calculate Euclidean distance to another Position."""
        if not isinstance(other, Position):
            raise TypeError(f"Expected Position instance, got {type(other).__name__}")
        return math.hypot(self.x - other.x, self.y - other.y)

    def distance_from_center(self) -> float:
        """Calculate Euclidean distance from stadium origin (0, 0)."""
        return math.hypot(self.x, self.y)


@dataclass(frozen=True)
class BladeState:
    """Immutable state representation of a single blade."""

    player_id: str
    blade_type: BladeType
    current_energy: float
    max_energy: float
    current_stability: float
    max_stability: float
    position: Position
    special_ready_at: float

    def __post_init__(self) -> None:
        if not isinstance(self.player_id, str) or not self.player_id.strip():
            raise ValueError("player_id must be a non-empty string")

        if not isinstance(self.blade_type, BladeType):
            raise TypeError(f"blade_type must be a BladeType enum, got {type(self.blade_type).__name__}")

        if not isinstance(self.position, Position):
            raise TypeError(f"position must be a Position instance, got {type(self.position).__name__}")

        # Validate numeric attributes
        numeric_fields = [
            ("current_energy", self.current_energy),
            ("max_energy", self.max_energy),
            ("current_stability", self.current_stability),
            ("max_stability", self.max_stability),
            ("special_ready_at", self.special_ready_at),
        ]
        for name, val in numeric_fields:
            if isinstance(val, bool) or not isinstance(val, (int, float)):
                raise TypeError(f"{name} must be numeric, got {type(val).__name__}")
            if not math.isfinite(val):
                raise ValueError(f"{name} must be a finite number, got {val}")

        # Maximum energy and stability must be strictly positive
        if self.max_energy <= 0.0:
            raise ValueError(f"max_energy must be strictly positive, got {self.max_energy}")
        if self.max_stability <= 0.0:
            raise ValueError(f"max_stability must be strictly positive, got {self.max_stability}")

        # Current energy and stability must be non-negative
        if self.current_energy < 0.0:
            raise ValueError(f"current_energy must be non-negative, got {self.current_energy}")
        if self.current_stability < 0.0:
            raise ValueError(f"current_stability must be non-negative, got {self.current_stability}")

        # Current values must not exceed maximum values
        if self.current_energy > self.max_energy:
            raise ValueError(
                f"current_energy ({self.current_energy}) cannot exceed max_energy ({self.max_energy})"
            )
        if self.current_stability > self.max_stability:
            raise ValueError(
                f"current_stability ({self.current_stability}) cannot exceed max_stability ({self.max_stability})"
            )

        # Special spin ready-at time must be non-negative
        if self.special_ready_at < 0.0:
            raise ValueError(f"special_ready_at must be non-negative, got {self.special_ready_at}")


@dataclass(frozen=True)
class StadiumState:
    """Immutable representation of stadium geometry."""

    stadium_type: StadiumType
    center: Position
    radius: float

    def __post_init__(self) -> None:
        if not isinstance(self.stadium_type, StadiumType):
            raise TypeError(f"stadium_type must be StadiumType, got {type(self.stadium_type).__name__}")
        if not isinstance(self.center, Position):
            raise TypeError(f"center must be Position, got {type(self.center).__name__}")
        if isinstance(self.radius, bool) or not isinstance(self.radius, (int, float)):
            raise TypeError(f"radius must be numeric, got {type(self.radius).__name__}")
        if not math.isfinite(self.radius) or self.radius <= 0.0:
            raise ValueError(f"radius must be finite and positive, got {self.radius}")


@dataclass(frozen=True)
class MatchResult:
    """Outcome data for a finished match."""

    winner: Optional[str]
    reason: FinishReason
    player_1_causes: Tuple[FinishReason, ...] = ()
    player_2_causes: Tuple[FinishReason, ...] = ()
    scores: Optional[Tuple[float, float]] = None

    def __post_init__(self) -> None:
        if not isinstance(self.reason, FinishReason):
            raise TypeError(f"reason must be a FinishReason enum, got {type(self.reason).__name__}")
        if self.winner is not None:
            if not isinstance(self.winner, str) or not self.winner.strip():
                raise ValueError("winner must be None (for draw/simultaneous elimination) or a non-empty player ID")
        if not isinstance(self.player_1_causes, tuple):
            raise TypeError("player_1_causes must be a tuple")
        for cause in self.player_1_causes:
            if not isinstance(cause, FinishReason):
                raise TypeError(f"Each cause in player_1_causes must be a FinishReason enum, got {type(cause).__name__}")
        if not isinstance(self.player_2_causes, tuple):
            raise TypeError("player_2_causes must be a tuple")
        for cause in self.player_2_causes:
            if not isinstance(cause, FinishReason):
                raise TypeError(f"Each cause in player_2_causes must be a FinishReason enum, got {type(cause).__name__}")
        if self.scores is not None:
            if not isinstance(self.scores, tuple) or len(self.scores) != 2:
                raise TypeError("scores must be a 2-tuple of floats or None")
            for s in self.scores:
                if isinstance(s, bool) or not isinstance(s, (int, float)) or not math.isfinite(s):
                    raise ValueError(f"scores values must be finite floats, got {s}")


@dataclass(frozen=True)
class MatchState:
    """Top-level immutable match state."""

    player_1_blade: BladeState
    player_2_blade: BladeState
    stadium: StadiumState
    completed_rounds: int
    status: MatchStatus
    result: Optional[MatchResult] = None

    def __post_init__(self) -> None:
        if not isinstance(self.player_1_blade, BladeState):
            raise TypeError(f"player_1_blade must be BladeState, got {type(self.player_1_blade).__name__}")
        if not isinstance(self.player_2_blade, BladeState):
            raise TypeError(f"player_2_blade must be BladeState, got {type(self.player_2_blade).__name__}")

        if self.player_1_blade.player_id == self.player_2_blade.player_id:
            raise ValueError(
                f"player_1 and player_2 must have distinct IDs, got duplicate '{self.player_1_blade.player_id}'"
            )

        if not isinstance(self.stadium, StadiumState):
            raise TypeError(f"stadium must be StadiumState, got {type(self.stadium).__name__}")

        if isinstance(self.completed_rounds, bool) or not isinstance(self.completed_rounds, int):
            raise TypeError(f"completed_rounds must be an integer, got {type(self.completed_rounds).__name__}")
        if self.completed_rounds < 0:
            raise ValueError(f"completed_rounds must be non-negative, got {self.completed_rounds}")

        if not isinstance(self.status, MatchStatus):
            raise TypeError(f"status must be MatchStatus, got {type(self.status).__name__}")

        if self.status == MatchStatus.IN_PROGRESS and self.result is not None:
            raise ValueError("An in-progress match must not have a result")

        if self.status == MatchStatus.FINISHED and self.result is None:
            raise ValueError("A finished match must have a result")

        if self.result is not None and not isinstance(self.result, MatchResult):
            raise TypeError(f"result must be MatchResult or None, got {type(self.result).__name__}")

    @property
    def elapsed_game_time(self) -> float:
        """Derived logical game time in seconds (completed_rounds * 3.0 seconds)."""
        return self.completed_rounds * SECONDS_PER_ROUND
