"""Match orchestration session for BLADE ARENA game modes.

Coordinates simultaneous match execution across:
- Human vs AI: caller-supplied human action with AI opponent.
- AI vs AI: autonomous agent duels (e.g. Ironclad vs Cyclone).
- Lifecycle controls: start, pause, resume, restart, swap sides, single-step.
- Strict action privacy, pre-round snapshot consistency, and legality enforcement.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, List, Optional, Tuple

from blade_arena.game.actions import check_action_legality
from blade_arena.game.combat import ClassicDishRoundResolver
from blade_arena.game.initial_state import create_initial_match
from blade_arena.game.match_controller import (
    MatchController,
    MatchFinishedError,
    MatchPausedError,
)
from blade_arena.game.models import Action, BladeType, MatchState, StadiumType
from blade_arena.game.resolver import RoundResolver
from blade_arena.orchestration.participants import (
    HumanActionRequiredError,
    IllegalParticipantActionError,
    Participant,
)


class OrchestrationError(ValueError):
    """Base exception for match orchestration errors."""

    pass


class IterationGuardError(OrchestrationError):
    """Raised when a match exceeds the defensive maximum iteration round bound."""

    pass


class GameMode(str, Enum):
    """Supported match game modes."""

    HUMAN_VS_AI = "human_vs_ai"
    AI_VS_AI = "ai_vs_ai"


@dataclass(frozen=True)
class StepRecord:
    """Audit record capturing the full context of a single orchestrated round."""

    round_number: int
    player_1_id: str
    player_2_id: str
    player_1_action: Action
    player_2_action: Action
    state_before: MatchState
    state_after: MatchState
    elapsed_logical_time: float
    p1_diagnostics: Optional[Any] = None
    p2_diagnostics: Optional[Any] = None


@dataclass(frozen=True)
class SessionConfig:
    """Configuration settings for an orchestration session."""

    mode: Optional[GameMode] = None
    player_1_blade: BladeType = BladeType.BALANCED
    player_2_blade: BladeType = BladeType.BALANCED
    stadium_type: StadiumType = StadiumType.CLASSIC_DISH
    initial_state: Optional[MatchState] = None
    resolver: Optional[RoundResolver] = None
    enforce_legality: bool = True
    max_rounds_guard: int = 45


class MatchSession:
    """Orchestrates an active match between two participants."""

    def __init__(
        self,
        participant_1: Participant,
        participant_2: Participant,
        config: Optional[SessionConfig] = None,
    ) -> None:
        """Initialize an orchestrated match session.

        Args:
            participant_1: Participant controlling player 1.
            participant_2: Participant controlling player 2.
            config: Optional session configuration.
        """
        self._p1: Participant = participant_1
        self._p2: Participant = participant_2
        self._config: SessionConfig = config or SessionConfig()

        # Infer game mode if not explicitly specified
        if self._config.mode is not None:
            self._mode: GameMode = self._config.mode
        elif self._p1.is_human or self._p2.is_human:
            self._mode = GameMode.HUMAN_VS_AI
        else:
            self._mode = GameMode.AI_VS_AI

        # Establish resolver
        self._resolver: RoundResolver = (
            self._config.resolver
            if self._config.resolver is not None
            else ClassicDishRoundResolver()
        )

        # Build initial match state
        if self._config.initial_state is not None:
            self._initial_state: MatchState = self._config.initial_state
        else:
            self._initial_state = create_initial_match(
                player_1_blade_type=self._config.player_1_blade,
                player_2_blade_type=self._config.player_2_blade,
                stadium_type=self._config.stadium_type,
            )

        self._p1_id: str = self._initial_state.player_1_blade.player_id
        self._p2_id: str = self._initial_state.player_2_blade.player_id

        # Controller maintains simultaneous action collection and lifecycle state
        self._controller: MatchController = MatchController(
            initial_state=self._initial_state,
            resolver=self._resolver,
            enforce_legality=self._config.enforce_legality,
        )

        self._history: List[StepRecord] = []

    # --------------------------------------------------------------------------
    # Inspection Properties
    # --------------------------------------------------------------------------

    @property
    def mode(self) -> GameMode:
        """Active game mode."""
        return self._mode

    @property
    def participant_1(self) -> Participant:
        """Participant controlling player 1."""
        return self._p1

    @property
    def participant_2(self) -> Participant:
        """Participant controlling player 2."""
        return self._p2

    @property
    def player_1_id(self) -> str:
        """Identifier for player 1."""
        return self._p1_id

    @property
    def player_2_id(self) -> str:
        """Identifier for player 2."""
        return self._p2_id

    @property
    def state(self) -> MatchState:
        """Current immutable match state snapshot."""
        return self._controller.state

    @property
    def is_paused(self) -> bool:
        """True if the match is currently paused."""
        return self._controller.is_paused

    @property
    def is_finished(self) -> bool:
        """True if the match has concluded."""
        return self._controller.is_finished

    @property
    def can_step(self) -> bool:
        """True if the match is in progress and not paused."""
        return not self.is_paused and not self.is_finished

    @property
    def round_history(self) -> Tuple[StepRecord, ...]:
        """Chronological audit records of all resolved rounds in this session."""
        return tuple(self._history)

    # --------------------------------------------------------------------------
    # Lifecycle Controls
    # --------------------------------------------------------------------------

    def start(self) -> None:
        """Start or unpause the session. Idempotent."""
        if self._controller.is_paused:
            self._controller.resume()

    def pause(self) -> None:
        """Pause the match session. Idempotent."""
        self._controller.pause()

    def resume(self) -> None:
        """Resume a paused match session. Idempotent."""
        self._controller.resume()

    def restart(self, initial_state: Optional[MatchState] = None) -> None:
        """Restart the match from initial conditions.

        Args:
            initial_state: Optional new starting MatchState.
        """
        if initial_state is not None:
            self._initial_state = initial_state
            self._p1_id = initial_state.player_1_blade.player_id
            self._p2_id = initial_state.player_2_blade.player_id

        self._controller.restart(self._initial_state)
        self._history.clear()

        # Clear any staged human actions
        if hasattr(self._p1, "clear_queued_action"):
            self._p1.clear_queued_action()
        if hasattr(self._p2, "clear_queued_action"):
            self._p2.clear_queued_action()

    def swap_sides(self) -> None:
        """Swap player assignments between participants and restart the match.

        Allows Human or AI agents to exchange starting sides (Player 1 vs Player 2).
        If the session was created with distinct blade archetypes, the blade archetypes
        swap as well to preserve the participant-to-blade pairing.
        """
        # Swap participants
        self._p1, self._p2 = self._p2, self._p1

        # Re-derive initial match with swapped archetypes
        swapped_initial = create_initial_match(
            player_1_blade_type=self._initial_state.player_2_blade.blade_type,
            player_2_blade_type=self._initial_state.player_1_blade.blade_type,
            stadium_type=self._initial_state.stadium.stadium_type,
            player_1_id=self._p1_id,
            player_2_id=self._p2_id,
        )
        self.restart(swapped_initial)

    # --------------------------------------------------------------------------
    # Step Execution
    # --------------------------------------------------------------------------

    def step_round(self, human_action: Optional[Action] = None) -> StepRecord:
        """Step exactly one round of simultaneous combat.

        Collects decisions from both participants using an immutable pre-round state
        snapshot, enforces action legality, submits choices secretly to the controller,
        and resolves combat using the production resolver.

        Args:
            human_action: Optional action choice for the human participant (if any).

        Returns:
            A StepRecord detailing round choices, transitions, and AI diagnostics.

        Raises:
            MatchFinishedError: If the match has already concluded.
            MatchPausedError: If the match is paused.
            IterationGuardError: If completed rounds exceed max_rounds_guard.
            HumanActionRequiredError: If human participant has no staged action.
            IllegalParticipantActionError: If either participant selects an illegal action.
        """
        if self.is_finished:
            raise MatchFinishedError("Cannot step round: match is already finished")

        if self.is_paused:
            raise MatchPausedError("Cannot step round while match is paused")

        if self.state.completed_rounds >= self._config.max_rounds_guard:
            raise IterationGuardError(
                f"Defensive iteration guard tripped: match exceeded {self._config.max_rounds_guard} rounds without finishing."
            )

        pre_state = self._controller.state

        # Handle caller-supplied human action
        if human_action is not None:
            if self._p1.is_human and hasattr(self._p1, "queue_action"):
                self._p1.queue_action(human_action)
            elif self._p2.is_human and hasattr(self._p2, "queue_action"):
                self._p2.queue_action(human_action)

        # 1. Collect Action 1 (isolated snapshot)
        try:
            action_1 = self._p1.choose_action(pre_state, self._p1_id)
        except Exception:
            self._cleanup_pending()
            raise

        legality_1 = check_action_legality(pre_state, self._p1_id, action_1)
        if not legality_1.is_legal:
            self._cleanup_pending()
            raise IllegalParticipantActionError(
                f"Participant 1 '{self._p1.name}' ({self._p1_id}) selected illegal action "
                f"{action_1.name}: {legality_1.reason}"
            )

        # 2. Collect Action 2 (isolated snapshot; action_1 is NOT leaked)
        try:
            action_2 = self._p2.choose_action(pre_state, self._p2_id)
        except Exception:
            self._cleanup_pending()
            raise

        legality_2 = check_action_legality(pre_state, self._p2_id, action_2)
        if not legality_2.is_legal:
            self._cleanup_pending()
            raise IllegalParticipantActionError(
                f"Participant 2 '{self._p2.name}' ({self._p2_id}) selected illegal action "
                f"{action_2.name}: {legality_2.reason}"
            )

        # 3. Submit both choices secretly to controller
        try:
            self._controller.submit_action(self._p1_id, action_1)
            self._controller.submit_action(self._p2_id, action_2)
            round_record = self._controller.resolve_round()
        except Exception:
            self._cleanup_pending()
            raise

        # 4. Construct StepRecord capturing diagnostics and logical time
        step_record = StepRecord(
            round_number=round_record.round_number,
            player_1_id=self._p1_id,
            player_2_id=self._p2_id,
            player_1_action=action_1,
            player_2_action=action_2,
            state_before=pre_state,
            state_after=round_record.state_after,
            elapsed_logical_time=round_record.state_after.elapsed_game_time,
            p1_diagnostics=self._p1.last_diagnostics,
            p2_diagnostics=self._p2.last_diagnostics,
        )
        self._history.append(step_record)
        return step_record

    def run_to_completion(self, max_rounds: Optional[int] = None) -> MatchState:
        """Run rounds continuously until match termination or bound reached.

        Only usable for non-blocking participants (e.g. AI vs AI).

        Args:
            max_rounds: Optional round cap.

        Returns:
            Final MatchState.
        """
        cap = max_rounds if max_rounds is not None else self._config.max_rounds_guard
        while not self.is_finished:
            if self.state.completed_rounds >= cap:
                raise IterationGuardError(
                    f"Match reached round limit of {cap} without terminating."
                )
            self.step_round()
        return self.state

    def _cleanup_pending(self) -> None:
        """Clear pending commitments in controller if round execution fails."""
        if hasattr(self._controller, "clear_pending_action"):
            try:
                self._controller.clear_pending_action(self._p1_id)
            except Exception:
                pass
            try:
                self._controller.clear_pending_action(self._p2_id)
            except Exception:
                pass
