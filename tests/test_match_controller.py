"""Unit tests for BLADE ARENA match controller, simultaneous action flow, and resolver interface."""

from __future__ import annotations

import dataclasses
import subprocess
import sys
from typing import List, Tuple

import pytest

from blade_arena.game.initial_state import (
    DEFAULT_PLAYER_1_ID,
    DEFAULT_PLAYER_2_ID,
    create_default_match,
)
from blade_arena.game.match_controller import (
    ActionSubmissionError,
    MatchController,
    MatchFinishedError,
    MatchPausedError,
    RoundResolutionError,
)
from blade_arena.game.models import (
    Action,
    FinishReason,
    MatchResult,
    MatchState,
    MatchStatus,
)
from blade_arena.game.resolver import RoundRecord, RoundResolver

# ==============================================================================
# Test-Only Resolvers (Test Fixtures)
# ==============================================================================


class RecordingResolver(RoundResolver):
    """Test-only resolver that records invocation arguments and advances exactly 1 round."""

    def __init__(self) -> None:
        self.calls: List[Tuple[MatchState, Action, Action]] = []

    def resolve_round(
        self,
        state: MatchState,
        player_1_action: Action,
        player_2_action: Action,
    ) -> MatchState:
        self.calls.append((state, player_1_action, player_2_action))
        return dataclasses.replace(state, completed_rounds=state.completed_rounds + 1)


class FinishingResolver(RoundResolver):
    """Test-only resolver that transitions the match to FINISHED on round 1."""

    def resolve_round(
        self,
        state: MatchState,
        player_1_action: Action,
        player_2_action: Action,
    ) -> MatchState:
        result = MatchResult(winner=DEFAULT_PLAYER_1_ID, reason=FinishReason.BURST)
        return dataclasses.replace(
            state,
            completed_rounds=state.completed_rounds + 1,
            status=MatchStatus.FINISHED,
            result=result,
        )


class FailingResolver(RoundResolver):
    """Test-only resolver that intentionally raises an exception."""

    def resolve_round(
        self,
        state: MatchState,
        player_1_action: Action,
        player_2_action: Action,
    ) -> MatchState:
        raise RuntimeError("Simulated resolver computation crash")


class InvalidTypeResolver(RoundResolver):
    """Test-only resolver that returns an invalid object type."""

    def resolve_round(
        self,
        state: MatchState,
        player_1_action: Action,
        player_2_action: Action,
    ) -> MatchState:
        return "not a match state"  # type: ignore


class NoAdvanceResolver(RoundResolver):
    """Test-only resolver that fails to advance completed_rounds."""

    def resolve_round(
        self,
        state: MatchState,
        player_1_action: Action,
        player_2_action: Action,
    ) -> MatchState:
        return state  # 0 round advance


class DoubleAdvanceResolver(RoundResolver):
    """Test-only resolver that incorrectly advances 2 rounds instead of 1."""

    def resolve_round(
        self,
        state: MatchState,
        player_1_action: Action,
        player_2_action: Action,
    ) -> MatchState:
        return dataclasses.replace(state, completed_rounds=state.completed_rounds + 2)


# ==============================================================================
# A. INITIAL CONTROLLER STATE
# ==============================================================================


def test_initial_controller_state() -> None:
    """Verify initial controller properties and readiness."""
    initial = create_default_match()
    resolver = RecordingResolver()
    controller = MatchController(initial_state=initial, resolver=resolver)

    assert controller.state == initial
    assert controller.is_paused is False
    assert controller.is_finished is False
    assert controller.can_resolve() is False
    assert controller.get_pending_players() == {DEFAULT_PLAYER_1_ID, DEFAULT_PLAYER_2_ID}
    assert controller.has_player_submitted(DEFAULT_PLAYER_1_ID) is False
    assert controller.has_player_submitted(DEFAULT_PLAYER_2_ID) is False
    assert len(controller.round_history) == 0


def test_controller_initialization_type_checks() -> None:
    """Verify constructor rejects invalid state or resolver types."""
    resolver = RecordingResolver()
    with pytest.raises(TypeError, match="initial_state must be a MatchState"):
        MatchController(initial_state="invalid", resolver=resolver)  # type: ignore

    initial = create_default_match()
    with pytest.raises(TypeError, match="resolver must satisfy the RoundResolver protocol"):
        MatchController(initial_state=initial, resolver="invalid")  # type: ignore


def test_controller_creation_does_not_initialize_pygame() -> None:
    """Verify creating a MatchController does not initialize Pygame or open a window."""
    code = (
        "import pygame\n"
        "from blade_arena.game import create_default_match, MatchController\n"
        "from blade_arena.game.resolver import RoundResolver\n"
        "class Dummy(RoundResolver):\n"
        "    def resolve_round(self, s, a1, a2): return s\n"
        "c = MatchController(create_default_match(), Dummy())\n"
        "assert not pygame.get_init(), 'Pygame was initialized'\n"
        "assert not pygame.display.get_init(), 'Display was initialized'\n"
    )
    res = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=5)
    assert res.returncode == 0, f"Pygame was initialized on controller creation: {res.stderr}"


# ==============================================================================
# B. ACTION SUBMISSION
# ==============================================================================


def test_valid_action_submissions() -> None:
    """Verify players can submit valid actions and submission status updates."""
    controller = MatchController(create_default_match(), RecordingResolver())

    controller.submit_action(DEFAULT_PLAYER_1_ID, Action.ATTACK)
    assert controller.has_player_submitted(DEFAULT_PLAYER_1_ID) is True
    assert controller.has_player_submitted(DEFAULT_PLAYER_2_ID) is False
    assert controller.get_pending_players() == {DEFAULT_PLAYER_2_ID}
    assert controller.can_resolve() is False

    controller.submit_action(DEFAULT_PLAYER_2_ID, Action.GUARD)
    assert controller.has_player_submitted(DEFAULT_PLAYER_2_ID) is True
    assert controller.get_pending_players() == set()
    assert controller.can_resolve() is True


def test_submission_rejects_unknown_player() -> None:
    """Verify submitting for a non-participating player raises ActionSubmissionError."""
    controller = MatchController(create_default_match(), RecordingResolver())
    with pytest.raises(ActionSubmissionError, match="Invalid player 'player_99'"):
        controller.submit_action("player_99", Action.CHARGE)


def test_has_player_submitted_rejects_unknown_player() -> None:
    """Verify inspecting an unknown player raises ActionSubmissionError."""
    controller = MatchController(create_default_match(), RecordingResolver())
    with pytest.raises(ActionSubmissionError, match="Player 'player_99' is not in this match"):
        controller.has_player_submitted("player_99")


def test_submission_rejects_invalid_action_type() -> None:
    """Verify submitting a non-Action value raises ActionSubmissionError."""
    controller = MatchController(create_default_match(), RecordingResolver())
    with pytest.raises(ActionSubmissionError, match="Expected valid Action enum instance"):
        controller.submit_action(DEFAULT_PLAYER_1_ID, "ATTACK")  # type: ignore

    with pytest.raises(ActionSubmissionError, match="Expected valid Action enum instance"):
        controller.submit_action(DEFAULT_PLAYER_1_ID, None)  # type: ignore


def test_submission_rejects_double_submission_in_same_round() -> None:
    """Verify a player cannot commit more than one action in a single round."""
    controller = MatchController(create_default_match(), RecordingResolver())
    controller.submit_action(DEFAULT_PLAYER_1_ID, Action.CHARGE)

    with pytest.raises(ActionSubmissionError, match="already submitted an action"):
        controller.submit_action(DEFAULT_PLAYER_1_ID, Action.DODGE)


def test_state_does_not_change_after_single_submission() -> None:
    """Verify the visible state snapshot is identical before and after one player submits."""
    initial = create_default_match()
    controller = MatchController(initial, RecordingResolver())

    controller.submit_action(DEFAULT_PLAYER_1_ID, Action.SPECIAL_SPIN)
    assert controller.state == initial
    assert controller.state.completed_rounds == 0


def test_normal_observation_api_does_not_reveal_actions() -> None:
    """Verify that neither the state nor public controller inspection reveals committed actions."""
    controller = MatchController(create_default_match(), RecordingResolver())
    controller.submit_action(DEFAULT_PLAYER_1_ID, Action.SPECIAL_SPIN)

    # State object contains no action fields
    assert not hasattr(controller.state, "action")
    assert not hasattr(controller.state, "player_1_action")
    assert not hasattr(controller.state.player_1_blade, "action")

    # Public helper shows presence, not action
    assert controller.has_player_submitted(DEFAULT_PLAYER_1_ID) is True
    assert controller.get_pending_players() == {DEFAULT_PLAYER_2_ID}


# ==============================================================================
# C. SIMULTANEOUS RESOLUTION
# ==============================================================================


def test_cannot_resolve_with_zero_or_one_action() -> None:
    """Verify round resolution is rejected when 0 or 1 player has submitted."""
    controller = MatchController(create_default_match(), RecordingResolver())

    with pytest.raises(RoundResolutionError, match="awaiting action from players"):
        controller.resolve_round()

    controller.submit_action(DEFAULT_PLAYER_1_ID, Action.ATTACK)
    with pytest.raises(RoundResolutionError, match="awaiting action from players"):
        controller.resolve_round()


def test_resolver_receives_actions_in_player_order_regardless_of_submission_order() -> None:
    """Verify that Player 2 submitting before Player 1 does not alter resolver argument order."""
    resolver = RecordingResolver()
    controller = MatchController(create_default_match(), resolver)

    # Player 2 commits first, Player 1 commits second
    controller.submit_action(DEFAULT_PLAYER_2_ID, Action.DODGE)
    controller.submit_action(DEFAULT_PLAYER_1_ID, Action.ATTACK)

    record = controller.resolve_round()

    assert len(resolver.calls) == 1
    call_state, p1_action, p2_action = resolver.calls[0]
    assert p1_action == Action.ATTACK
    assert p2_action == Action.DODGE

    # RoundRecord also records in stable player order
    assert record.player_1_action == Action.ATTACK
    assert record.player_2_action == Action.DODGE
    assert record.round_number == 1


def test_successful_resolution_advances_round_and_clears_pending() -> None:
    """Verify successful round resolution updates state and clears pending submissions."""
    resolver = RecordingResolver()
    initial = create_default_match()
    controller = MatchController(initial, resolver)

    controller.submit_action(DEFAULT_PLAYER_1_ID, Action.CHARGE)
    controller.submit_action(DEFAULT_PLAYER_2_ID, Action.GUARD)

    record = controller.resolve_round()

    assert controller.state.completed_rounds == 1
    assert controller.state.elapsed_game_time == 3.0
    assert initial.completed_rounds == 0  # Immutability preserved

    # Pending actions cleared
    assert controller.get_pending_players() == {DEFAULT_PLAYER_1_ID, DEFAULT_PLAYER_2_ID}
    assert controller.has_player_submitted(DEFAULT_PLAYER_1_ID) is False
    assert controller.has_player_submitted(DEFAULT_PLAYER_2_ID) is False
    assert controller.can_resolve() is False

    # Round history recorded
    assert controller.round_history == (record,)

    # Both players can submit again for round 2
    controller.submit_action(DEFAULT_PLAYER_1_ID, Action.ATTACK)
    controller.submit_action(DEFAULT_PLAYER_2_ID, Action.DODGE)
    record_2 = controller.resolve_round()

    assert controller.state.completed_rounds == 2
    assert controller.state.elapsed_game_time == 6.0
    assert len(controller.round_history) == 2
    assert controller.round_history[1] == record_2


# ==============================================================================
# D. ERROR HANDLING
# ==============================================================================


def test_resolver_exception_preserves_state_and_pending_actions() -> None:
    """Verify unhandled resolver exceptions leave state and pending actions intact for retry."""
    controller = MatchController(create_default_match(), FailingResolver())

    controller.submit_action(DEFAULT_PLAYER_1_ID, Action.CHARGE)
    controller.submit_action(DEFAULT_PLAYER_2_ID, Action.ATTACK)

    with pytest.raises(RoundResolutionError, match="Resolver raised an unhandled exception"):
        controller.resolve_round()

    # Pre-round state preserved
    assert controller.state.completed_rounds == 0

    # Pending actions preserved
    assert controller.has_player_submitted(DEFAULT_PLAYER_1_ID) is True
    assert controller.has_player_submitted(DEFAULT_PLAYER_2_ID) is True
    assert controller.can_resolve() is True


def test_resolver_invalid_type_rejected_and_preserves_actions() -> None:
    """Verify non-MatchState resolver output raises RoundResolutionError and preserves actions."""
    controller = MatchController(create_default_match(), InvalidTypeResolver())

    controller.submit_action(DEFAULT_PLAYER_1_ID, Action.ATTACK)
    controller.submit_action(DEFAULT_PLAYER_2_ID, Action.GUARD)

    with pytest.raises(RoundResolutionError, match="Resolver returned invalid type"):
        controller.resolve_round()

    assert controller.state.completed_rounds == 0
    assert controller.can_resolve() is True


def test_resolver_failing_to_advance_round_rejected() -> None:
    """Verify resolver advancing 0 or 2 rounds raises RoundResolutionError."""
    # Zero advance
    controller_no_adv = MatchController(create_default_match(), NoAdvanceResolver())
    controller_no_adv.submit_action(DEFAULT_PLAYER_1_ID, Action.ATTACK)
    controller_no_adv.submit_action(DEFAULT_PLAYER_2_ID, Action.GUARD)
    with pytest.raises(RoundResolutionError, match="Resolver must advance completed_rounds by exactly 1"):
        controller_no_adv.resolve_round()

    # Double advance
    controller_dbl_adv = MatchController(create_default_match(), DoubleAdvanceResolver())
    controller_dbl_adv.submit_action(DEFAULT_PLAYER_1_ID, Action.ATTACK)
    controller_dbl_adv.submit_action(DEFAULT_PLAYER_2_ID, Action.GUARD)
    with pytest.raises(RoundResolutionError, match="Resolver must advance completed_rounds by exactly 1"):
        controller_dbl_adv.resolve_round()


# ==============================================================================
# E. PAUSE AND RESUME
# ==============================================================================


def test_pause_and_resume_lifecycle() -> None:
    """Verify pause, resume, and their idempotence."""
    controller = MatchController(create_default_match(), RecordingResolver())
    assert controller.is_paused is False

    controller.pause()
    assert controller.is_paused is True
    # Idempotent
    controller.pause()
    assert controller.is_paused is True

    controller.resume()
    assert controller.is_paused is False
    # Idempotent
    controller.resume()
    assert controller.is_paused is False


def test_pause_prevents_submission_and_resolution() -> None:
    """Verify submissions and resolutions are rejected while paused."""
    controller = MatchController(create_default_match(), RecordingResolver())
    controller.pause()

    with pytest.raises(MatchPausedError, match="Cannot submit action while match is paused"):
        controller.submit_action(DEFAULT_PLAYER_1_ID, Action.CHARGE)

    with pytest.raises(MatchPausedError, match="Cannot resolve round while match is paused"):
        controller.resolve_round()


def test_pending_action_survives_pause_and_resume() -> None:
    """Verify committed actions remain in place across pause and resume."""
    controller = MatchController(create_default_match(), RecordingResolver())
    controller.submit_action(DEFAULT_PLAYER_1_ID, Action.DODGE)

    controller.pause()
    assert controller.has_player_submitted(DEFAULT_PLAYER_1_ID) is True
    assert controller.get_pending_players() == {DEFAULT_PLAYER_2_ID}

    controller.resume()
    assert controller.has_player_submitted(DEFAULT_PLAYER_1_ID) is True
    assert controller.get_pending_players() == {DEFAULT_PLAYER_2_ID}

    # Second player submits after resume
    controller.submit_action(DEFAULT_PLAYER_2_ID, Action.ATTACK)
    record = controller.resolve_round()
    assert record.player_1_action == Action.DODGE
    assert record.player_2_action == Action.ATTACK
    assert controller.state.completed_rounds == 1


# ==============================================================================
# F. RESTART
# ==============================================================================


def test_restart_resets_match_state_and_pending_actions() -> None:
    """Verify restart resets state, history, paused flag, and pending actions."""
    initial = create_default_match()
    controller = MatchController(initial, RecordingResolver())

    controller.submit_action(DEFAULT_PLAYER_1_ID, Action.CHARGE)
    controller.submit_action(DEFAULT_PLAYER_2_ID, Action.ATTACK)
    controller.resolve_round()
    assert controller.state.completed_rounds == 1

    # Stage a pending action for round 2 and pause
    controller.submit_action(DEFAULT_PLAYER_1_ID, Action.GUARD)
    controller.pause()
    assert controller.is_paused is True

    controller.restart()

    assert controller.state == initial
    assert controller.state.completed_rounds == 0
    assert controller.is_paused is False
    assert controller.get_pending_players() == {DEFAULT_PLAYER_1_ID, DEFAULT_PLAYER_2_ID}
    assert len(controller.round_history) == 0

    # Can cleanly start a new round
    controller.submit_action(DEFAULT_PLAYER_1_ID, Action.ATTACK)
    controller.submit_action(DEFAULT_PLAYER_2_ID, Action.CHARGE)
    record = controller.resolve_round()
    assert record.round_number == 1
    assert controller.state.completed_rounds == 1


def test_restart_with_custom_initial_state() -> None:
    """Verify restarting with an explicit new initial state."""
    m1 = create_default_match()
    controller = MatchController(m1, RecordingResolver())

    m2 = dataclasses.replace(m1, completed_rounds=0)
    controller.restart(initial_state=m2)
    assert controller.state == m2

    with pytest.raises(TypeError, match="initial_state must be a MatchState"):
        controller.restart(initial_state="invalid")  # type: ignore


# ==============================================================================
# G. FINISHED MATCH
# ==============================================================================


def test_finished_match_rejects_submissions_and_resolution() -> None:
    """Verify that once a match reaches FINISHED, new submissions and resolutions are rejected."""
    controller = MatchController(create_default_match(), FinishingResolver())

    controller.submit_action(DEFAULT_PLAYER_1_ID, Action.ATTACK)
    controller.submit_action(DEFAULT_PLAYER_2_ID, Action.GUARD)
    record = controller.resolve_round()

    assert controller.is_finished is True
    assert controller.state.status == MatchStatus.FINISHED
    assert controller.state.result is not None
    assert controller.state.result.winner == DEFAULT_PLAYER_1_ID

    # Submissions rejected
    with pytest.raises(MatchFinishedError, match="match is already finished"):
        controller.submit_action(DEFAULT_PLAYER_1_ID, Action.CHARGE)

    # Resolution rejected
    with pytest.raises(MatchFinishedError, match="match is already finished"):
        controller.resolve_round()

    # Can restart from finished state
    controller.restart()
    assert controller.is_finished is False
    assert controller.state.status == MatchStatus.IN_PROGRESS
    assert controller.state.completed_rounds == 0
