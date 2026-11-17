"""Match coordination controller for BLADE ARENA.

Coordinates simultaneous turn action collection, round resolution via injected resolvers,
match lifecycle (pause, resume, restart), and finished-state protection.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Set, Tuple

from blade_arena.game.models import Action, MatchState, MatchStatus
from blade_arena.game.resolver import RoundRecord, RoundResolver


class MatchError(ValueError):
    """Base exception for all match controller domain errors."""

    pass


class MatchPausedError(MatchError):
    """Raised when an operation is disallowed because the match is paused."""

    pass


class MatchFinishedError(MatchError):
    """Raised when an operation is disallowed because the match is already finished."""

    pass


class ActionSubmissionError(MatchError):
    """Raised when an action submission fails validation."""

    pass


class RoundResolutionError(MatchError):
    """Raised when round resolution fails or resolver output is invalid."""

    pass


class MatchController:
    """Manages match execution and simultaneous action collection.

    The controller collects actions sequentially in code but treats them as simultaneous
    commitments in the game. Actions are kept private until both players have committed,
    at which point they are dispatched together to a RoundResolver.
    """

    def __init__(
        self,
        initial_state: MatchState,
        resolver: RoundResolver,
        enforce_legality: bool = False,
    ) -> None:
        """Initialize controller with an initial match state and a round resolver.

        Args:
            initial_state: The starting immutable MatchState.
            resolver: A component implementing the RoundResolver protocol.
            enforce_legality: If True, validates action legality before accepting submissions.
        """
        if not isinstance(initial_state, MatchState):
            raise TypeError(f"initial_state must be a MatchState, got {type(initial_state).__name__}")
        if not isinstance(resolver, RoundResolver):
            raise TypeError("resolver must satisfy the RoundResolver protocol")

        self._initial_state: MatchState = initial_state
        self._state: MatchState = initial_state
        self._resolver: RoundResolver = resolver
        self._enforce_legality: bool = enforce_legality

        self._is_paused: bool = False
        self._pending_actions: Dict[str, Action] = {}
        self._round_history: List[RoundRecord] = []

    # --------------------------------------------------------------------------
    # Public State Properties
    # --------------------------------------------------------------------------

    @property
    def state(self) -> MatchState:
        """Current immutable game-state snapshot."""
        return self._state

    @property
    def is_paused(self) -> bool:
        """True if the match is currently paused."""
        return self._is_paused

    @property
    def is_finished(self) -> bool:
        """True if the match has concluded."""
        return self._state.status == MatchStatus.FINISHED

    @property
    def round_history(self) -> Tuple[RoundRecord, ...]:
        """Audit log of all resolved rounds in this match session."""
        return tuple(self._round_history)

    # --------------------------------------------------------------------------
    # Player & Submission Inspection API
    # --------------------------------------------------------------------------

    def get_valid_player_ids(self) -> Set[str]:
        """Set of player identifiers participating in this match."""
        return {
            self._state.player_1_blade.player_id,
            self._state.player_2_blade.player_id,
        }

    def get_pending_players(self) -> Set[str]:
        """Set of player identifiers who have NOT yet submitted an action this round."""
        return self.get_valid_player_ids() - set(self._pending_actions.keys())

    def has_player_submitted(self, player_id: str) -> bool:
        """Check whether a specific player has submitted an action for the current round.

        Note: Does not expose the action value itself.
        """
        if player_id not in self.get_valid_player_ids():
            raise ActionSubmissionError(f"Player '{player_id}' is not in this match")
        return player_id in self._pending_actions

    def can_resolve(self) -> bool:
        """Check whether the current round is ready for resolution."""
        if self.is_paused or self.is_finished:
            return False
        return len(self.get_pending_players()) == 0

    def get_legal_actions(self, player_id: str) -> Tuple[Action, ...]:
        """Query legal actions for a player given the current state snapshot."""
        from blade_arena.game.actions import legal_actions

        return legal_actions(self._state, player_id)

    # --------------------------------------------------------------------------
    # Action Submission API
    # --------------------------------------------------------------------------

    def submit_action(self, player_id: str, action: Action) -> None:
        """Submit an action choice for a participating player.

        Args:
            player_id: Identifier of the submitting player.
            action: Selected Action enum member.

        Raises:
            MatchFinishedError: If the match has already concluded.
            MatchPausedError: If the match is currently paused.
            ActionSubmissionError: If player_id is invalid, action is invalid,
                the player has already committed an action this round, or (if
                enforce_legality is enabled) the action is illegal.
        """
        if self.is_finished:
            raise MatchFinishedError("Cannot submit action: match is already finished")

        if self.is_paused:
            raise MatchPausedError("Cannot submit action while match is paused")

        if player_id not in self.get_valid_player_ids():
            raise ActionSubmissionError(
                f"Invalid player '{player_id}': match participants are {sorted(self.get_valid_player_ids())}"
            )

        if not isinstance(action, Action):
            raise ActionSubmissionError(
                f"Expected valid Action enum instance, got {type(action).__name__}: {action}"
            )

        if player_id in self._pending_actions:
            raise ActionSubmissionError(
                f"Player '{player_id}' has already submitted an action for round {self._state.completed_rounds + 1}"
            )

        if self._enforce_legality:
            from blade_arena.game.actions import check_action_legality

            result = check_action_legality(self._state, player_id, action)
            if not result.is_legal:
                raise ActionSubmissionError(f"Illegal action submission: {result.reason}")

        # Store secretly in internal pending map; never exposed in public state
        self._pending_actions[player_id] = action

    def clear_pending_action(self, player_id: str) -> None:
        """Clear a committed pending action for the specified player.

        Allows discarding or re-selecting an action (e.g. following a resolver
        rejection due to illegality) without discarding or revealing the
        opponent's unrevealed pending selection.

        Args:
            player_id: Identifier of the player whose pending action to clear.

        Raises:
            ActionSubmissionError: If player_id is not in this match.
        """
        if player_id not in self.get_valid_player_ids():
            raise ActionSubmissionError(f"Player '{player_id}' is not in this match")
        self._pending_actions.pop(player_id, None)

    # --------------------------------------------------------------------------
    # Round Resolution API
    # --------------------------------------------------------------------------

    def resolve_round(self) -> RoundRecord:
        """Resolve the current round using both committed actions.

        Calls the resolver with (state, player_1_action, player_2_action) in stable
        player order, regardless of which player committed first.

        Returns:
            A RoundRecord documenting the resolved round and transition.

        Raises:
            MatchFinishedError: If the match has already concluded.
            MatchPausedError: If the match is paused.
            RoundResolutionError: If not all players have submitted, or if the resolver
                fails, raises an exception, or returns an invalid state.
        """
        if self.is_finished:
            raise MatchFinishedError("Cannot resolve round: match is already finished")

        if self.is_paused:
            raise MatchPausedError("Cannot resolve round while match is paused")

        pending = self.get_pending_players()
        if pending:
            raise RoundResolutionError(
                f"Cannot resolve round: awaiting action from players {sorted(pending)}"
            )

        p1_id = self._state.player_1_blade.player_id
        p2_id = self._state.player_2_blade.player_id
        p1_action = self._pending_actions[p1_id]
        p2_action = self._pending_actions[p2_id]

        pre_state = self._state

        # Invoke resolver with dependency injection
        try:
            next_state = self._resolver.resolve_round(pre_state, p1_action, p2_action)
        except Exception as exc:
            # Preserve pending actions and pre-round state on resolver failure
            raise RoundResolutionError(f"Resolver raised an unhandled exception: {exc}") from exc

        # Validate resolver returned state
        if not isinstance(next_state, MatchState):
            raise RoundResolutionError(
                f"Resolver returned invalid type: expected MatchState, got {type(next_state).__name__}"
            )

        expected_round = pre_state.completed_rounds + 1
        if next_state.completed_rounds != expected_round:
            raise RoundResolutionError(
                f"Resolver must advance completed_rounds by exactly 1: expected {expected_round}, got {next_state.completed_rounds}"
            )

        # Success: commit new state and clear pending commitments
        self._state = next_state
        self._pending_actions.clear()

        record = RoundRecord(
            round_number=expected_round,
            player_1_action=p1_action,
            player_2_action=p2_action,
            state_before=pre_state,
            state_after=next_state,
        )
        self._round_history.append(record)
        return record

    # --------------------------------------------------------------------------
    # Lifecycle Control API
    # --------------------------------------------------------------------------

    def pause(self) -> None:
        """Pause the match. Idempotent.

        Prevents action submissions and round resolution without modifying game state
        or losing committed actions.
        """
        self._is_paused = True

    def resume(self) -> None:
        """Resume a paused match. Idempotent.

        Restores ability to submit actions and resolve rounds. Does not advance rounds.
        """
        self._is_paused = False

    def restart(self, initial_state: Optional[MatchState] = None) -> None:
        """Reset the match to initial state.

        Clears pending actions, unpauses the match, and clears round history.
        Can be called at any point, including after a match is finished.

        Args:
            initial_state: Optional new starting MatchState. If omitted, restores
                the original initial_state provided at construction.
        """
        if initial_state is not None:
            if not isinstance(initial_state, MatchState):
                raise TypeError(f"initial_state must be a MatchState, got {type(initial_state).__name__}")
            self._initial_state = initial_state

        self._state = self._initial_state
        self._pending_actions.clear()
        self._round_history.clear()
        self._is_paused = False
