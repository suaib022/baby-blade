"""Round resolver protocol and record definitions for BLADE ARENA.

Defines the contract between the match coordinator and domain simulation resolvers.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from blade_arena.game.combat import (
    BladeRoundAudit,
    ClassicDishRoundResolver,
    CombatConfig,
    DEFAULT_COMBAT_CONFIG,
    IllegalRoundResolutionError,
    RoundCombatEvents,
    resolve_combat_round,
)
from blade_arena.game.models import Action, MatchState


@dataclass(frozen=True)
class RoundRecord:
    """Immutable audit record of a resolved round."""

    round_number: int
    player_1_action: Action
    player_2_action: Action
    state_before: MatchState
    state_after: MatchState


@runtime_checkable
class RoundResolver(Protocol):
    """Protocol defining round resolution.

    A resolver accepts the pre-round immutable state and both players' committed actions,
    and returns a new immutable MatchState with completed_rounds incremented by exactly 1.
    """

    def resolve_round(
        self,
        state: MatchState,
        player_1_action: Action,
        player_2_action: Action,
    ) -> MatchState:
        """Resolve one combat round and return the next match state.

        Args:
            state: Pre-round immutable MatchState.
            player_1_action: Action chosen by Player 1.
            player_2_action: Action chosen by Player 2.

        Returns:
            A new immutable MatchState with completed_rounds == state.completed_rounds + 1.
        """
        ...


__all__ = [
    "BladeRoundAudit",
    "ClassicDishRoundResolver",
    "CombatConfig",
    "DEFAULT_COMBAT_CONFIG",
    "IllegalRoundResolutionError",
    "RoundCombatEvents",
    "RoundRecord",
    "RoundResolver",
    "resolve_combat_round",
]
