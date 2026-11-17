"""Automated tests for BLADE ARENA game modes and headless orchestration (Module 13).

Verifies:
- Participant protocol, HumanParticipant non-blocking staging, AIParticipant agent wrapping.
- Action privacy and identical pre-round state snapshot observation.
- Rejection of illegal human and AI actions with state preservation and recovery.
- MatchSession lifecycle controls: start, pause, resume, restart, and swap sides.
- Strict one-round stepping and finished-match rejection.
- Defensive iteration guard tripping.
- Headless batch runner with alternating sides, reproducible seeds, and aggregate summaries.
- Real headless AI vs AI match to genuine terminal completion.
- Zero Pygame display dependency.
"""

from __future__ import annotations

import subprocess
import sys
from typing import Any, List, Optional

import pytest

from blade_arena.ai.cyclone import CycloneAgent, CycloneConfig
from blade_arena.ai.ironclad import IroncladAgent, IroncladConfig
from blade_arena.game.match_controller import MatchFinishedError, MatchPausedError
from blade_arena.game.models import (
    Action,
    BladeType,
    FinishReason,
    MatchState,
    MatchStatus,
    Position,
)
from blade_arena.orchestration import (
    AgentType,
    AIParticipant,
    BatchMatchResult,
    BatchSummary,
    GameMode,
    HumanActionRequiredError,
    HumanParticipant,
    IllegalParticipantActionError,
    IterationGuardError,
    MatchSession,
    Participant,
    SessionConfig,
    StepRecord,
    create_ai_participant,
    run_headless_batch,
)


class StubAgent:
    """Configurable stub participant for controlled unit testing."""

    def __init__(self, name: str, action_sequence: List[Action]) -> None:
        self.name = name
        self.action_sequence = list(action_sequence)
        self.observed_states: List[MatchState] = []
        self.observed_player_ids: List[str] = []
        self.is_human = False
        self.last_diagnostics = {"stub": True}

    def choose_action(self, state: MatchState, player_id: str) -> Action:
        self.observed_states.append(state)
        self.observed_player_ids.append(player_id)
        if not self.action_sequence:
            return Action.CHARGE
        return self.action_sequence.pop(0)


# ==============================================================================
# 1. Participant Interface Tests
# ==============================================================================


def test_human_participant_staging_and_consumption() -> None:
    """Verify HumanParticipant requires queued actions, does not block, and clears on use."""
    human = HumanParticipant(name="PlayerOne")
    assert human.name == "PlayerOne"
    assert human.is_human is True
    assert human.has_queued_action is False
    assert human.last_diagnostics is None

    # Error if no action queued
    from blade_arena.game.initial_state import create_initial_match
    state = create_initial_match()

    with pytest.raises(HumanActionRequiredError, match="has no queued action"):
        human.choose_action(state, "player_1")

    # Queue valid action
    human.queue_action(Action.ATTACK)
    assert human.has_queued_action is True

    # Consuming returns the action and resets queue
    chosen = human.choose_action(state, "player_1")
    assert chosen == Action.ATTACK
    assert human.has_queued_action is False

    # Second call raises again
    with pytest.raises(HumanActionRequiredError):
        human.choose_action(state, "player_1")


def test_human_participant_rejects_invalid_type() -> None:
    """Verify queue_action rejects non-Action objects."""
    human = HumanParticipant()
    with pytest.raises(TypeError, match="Expected Action enum"):
        human.queue_action("ATTACK")  # type: ignore[arg-type]


def test_ai_participant_wraps_ironclad_and_records_diagnostics() -> None:
    """Verify AIParticipant wraps IroncladAgent and preserves decision diagnostics."""
    participant = create_ai_participant("IroncladBot", AgentType.IRONCLAD, difficulty="easy")
    assert participant.name == "IroncladBot"
    assert participant.is_human is False

    from blade_arena.game.initial_state import create_initial_match
    state = create_initial_match()

    action = participant.choose_action(state, "player_1")
    assert isinstance(action, Action)
    assert participant.last_diagnostics is not None
    assert hasattr(participant.last_diagnostics, "nodes_evaluated")


def test_ai_participant_wraps_cyclone_and_records_diagnostics() -> None:
    """Verify AIParticipant wraps CycloneAgent and preserves decision diagnostics."""
    participant = create_ai_participant("CycloneBot", AgentType.CYCLONE, difficulty="easy", seed=42)
    assert participant.name == "CycloneBot"
    assert participant.is_human is False

    from blade_arena.game.initial_state import create_initial_match
    state = create_initial_match()

    action = participant.choose_action(state, "player_2")
    assert isinstance(action, Action)
    assert participant.last_diagnostics is not None
    assert hasattr(participant.last_diagnostics, "action_visits")


# ==============================================================================
# 2. Snapshot Consistency and Privacy Tests
# ==============================================================================


def test_controlled_stub_agents_observe_identical_pre_round_state() -> None:
    """Verify both participants receive the exact same pre-round immutable state snapshot."""
    stub1 = StubAgent("Agent1", [Action.CHARGE])
    stub2 = StubAgent("Agent2", [Action.CHARGE])

    session = MatchSession(participant_1=stub1, participant_2=stub2)
    session.step_round()

    assert len(stub1.observed_states) == 1
    assert len(stub2.observed_states) == 1

    s1 = stub1.observed_states[0]
    s2 = stub2.observed_states[0]
    # Exact equivalence and completed_rounds == 0
    assert s1 == s2
    assert s1.completed_rounds == 0


def test_no_hidden_action_leak_between_participants() -> None:
    """Verify participant 2 cannot inspect participant 1's action choice during deliberation."""
    p1_chosen_action = Action.ATTACK

    class SpyingAgent:
        def __init__(self) -> None:
            self.name = "Spy"
            self.is_human = False
            self.last_diagnostics = None
            self.leaked_data: Optional[Any] = None

        def choose_action(self, state: MatchState, player_id: str) -> Action:
            # Check state and attributes to confirm player_1's action is nowhere in state
            # MatchState has no pending actions field
            assert not hasattr(state, "pending_actions")
            assert not hasattr(state, "player_1_action")
            return Action.GUARD

    stub1 = StubAgent("Agent1", [p1_chosen_action])
    spy2 = SpyingAgent()

    session = MatchSession(participant_1=stub1, participant_2=spy2)
    session.step_round()

    assert len(session.round_history) == 1
    record = session.round_history[0]
    assert record.player_1_action == Action.ATTACK
    assert record.player_2_action == Action.GUARD


# ==============================================================================
# 3. Legality Enforcement and Recovery Tests
# ==============================================================================


def test_illegal_human_action_rejected_and_state_preserved() -> None:
    """Verify illegal human action raises clear error and allows recovery/reselection."""
    human = HumanParticipant("HumanPlayer")
    stub_ai = StubAgent("AI", [Action.CHARGE, Action.CHARGE])

    session = MatchSession(participant_1=human, participant_2=stub_ai)
    pre_state = session.state

    # Special spin requires energy >= 35. At start, energy=100 so it's legal.
    # To test illegal action, let's artificially stage an illegal action.
    # We can create a state where energy is 0.
    from blade_arena.game.blade_definitions import create_blade_state
    low_energy_blade = create_blade_state("player_1", BladeType.BALANCED, Position(-2.0, 0.0))
    # Replace current_energy with 0.0
    from dataclasses import replace
    state_no_energy = replace(
        session.state,
        player_1_blade=replace(low_energy_blade, current_energy=0.0),
    )
    session.restart(state_no_energy)

    # In state_no_energy, ATTACK costs 8.0 energy, so ATTACK is illegal!
    human.queue_action(Action.ATTACK)

    with pytest.raises(IllegalParticipantActionError, match="selected illegal action ATTACK"):
        session.step_round()

    # Verify state was not modified and completed_rounds is still 0
    assert session.state.completed_rounds == 0

    # Verify recovery: human stages legal CHARGE (costs 0 energy) and stepping succeeds!
    human.queue_action(Action.CHARGE)
    step_record = session.step_round()

    assert step_record.round_number == 1
    assert step_record.player_1_action == Action.CHARGE
    assert session.state.completed_rounds == 1


def test_illegal_ai_action_rejected_and_cleans_up_controller() -> None:
    """Verify illegal AI action raises IllegalParticipantActionError and preserves match state."""
    from blade_arena.game.blade_definitions import create_blade_state
    from dataclasses import replace

    # AI attempts ATTACK with 0 energy
    illegal_ai = StubAgent("BadAI", [Action.ATTACK])
    stub2 = StubAgent("GoodAI", [Action.CHARGE])

    session = MatchSession(participant_1=illegal_ai, participant_2=stub2)
    zero_e = replace(
        session.state,
        player_1_blade=replace(session.state.player_1_blade, current_energy=0.0),
    )
    session.restart(zero_e)

    with pytest.raises(IllegalParticipantActionError, match="selected illegal action ATTACK"):
        session.step_round()

    assert session.state.completed_rounds == 0


# ==============================================================================
# 4. Lifecycle Controls Tests
# ==============================================================================


def test_ai_vs_ai_lifecycle_pause_resume_restart() -> None:
    """Verify pause, resume, and restart controls in AI vs AI mode."""
    stub1 = StubAgent("A1", [Action.CHARGE, Action.CHARGE, Action.CHARGE])
    stub2 = StubAgent("A2", [Action.CHARGE, Action.CHARGE, Action.CHARGE])

    session = MatchSession(participant_1=stub1, participant_2=stub2)
    assert session.mode == GameMode.AI_VS_AI
    assert session.can_step is True

    # 1. Step 1 round
    rec1 = session.step_round()
    assert rec1.round_number == 1
    assert session.state.completed_rounds == 1

    # 2. Pause
    session.pause()
    assert session.is_paused is True
    assert session.can_step is False

    with pytest.raises(MatchPausedError, match="while match is paused"):
        session.step_round()

    # 3. Resume
    session.resume()
    assert session.is_paused is False
    assert session.can_step is True

    # 4. Step second round
    rec2 = session.step_round()
    assert rec2.round_number == 2
    assert session.state.completed_rounds == 2
    assert len(session.round_history) == 2

    # 5. Restart
    session.restart()
    assert session.state.completed_rounds == 0
    assert len(session.round_history) == 0
    assert session.can_step is True


def test_side_swap_ai_vs_ai() -> None:
    """Verify side swapping in AI vs AI mode exchanges participants and restarts."""
    a1 = StubAgent("AgentA", [Action.CHARGE])
    a2 = StubAgent("AgentB", [Action.CHARGE])

    session = MatchSession(
        participant_1=a1,
        participant_2=a2,
        config=SessionConfig(
            player_1_blade=BladeType.ATTACKER,
            player_2_blade=BladeType.DEFENDER,
        ),
    )

    assert session.participant_1.name == "AgentA"
    assert session.participant_2.name == "AgentB"
    assert session.state.player_1_blade.blade_type == BladeType.ATTACKER
    assert session.state.player_2_blade.blade_type == BladeType.DEFENDER

    # Swap sides
    session.swap_sides()

    assert session.participant_1.name == "AgentB"
    assert session.participant_2.name == "AgentA"
    assert session.state.player_1_blade.blade_type == BladeType.DEFENDER
    assert session.state.player_2_blade.blade_type == BladeType.ATTACKER
    assert session.state.completed_rounds == 0


def test_side_swap_human_vs_ai() -> None:
    """Verify side swapping allows human to play as Player 1 or Player 2."""
    human = HumanParticipant("User")
    ai = StubAgent("AI", [Action.CHARGE])

    # Human starts as Player 1
    session = MatchSession(participant_1=human, participant_2=ai)
    assert session.mode == GameMode.HUMAN_VS_AI
    assert session.participant_1.is_human is True
    assert session.participant_2.is_human is False

    # Swap sides -> Human becomes Player 2
    session.swap_sides()
    assert session.participant_1.is_human is False
    assert session.participant_2.is_human is True

    # Human supplies action directly to step_round
    step_record = session.step_round(human_action=Action.GUARD)
    assert step_record.player_2_action == Action.GUARD
    assert session.state.completed_rounds == 1


# ==============================================================================
# 5. Iteration Guard and Termination Tests
# ==============================================================================


def test_iteration_guard_trips_on_excessive_rounds() -> None:
    """Verify the defensive iteration guard prevents infinite loops."""
    # Endless Charge actions
    stub1 = StubAgent("A1", [Action.CHARGE] * 10)
    stub2 = StubAgent("A2", [Action.CHARGE] * 10)

    # Set guard bound to 3 rounds
    config = SessionConfig(max_rounds_guard=3)
    session = MatchSession(participant_1=stub1, participant_2=stub2, config=config)

    session.step_round()  # Round 1
    session.step_round()  # Round 2
    session.step_round()  # Round 3 -> completed_rounds == 3

    # Attempting round 4 trips the iteration guard
    with pytest.raises(IterationGuardError, match="Defensive iteration guard tripped"):
        session.step_round()


def test_cannot_step_finished_match() -> None:
    """Verify step_round raises MatchFinishedError once match is finished."""
    from dataclasses import replace
    from blade_arena.game.models import MatchResult

    stub1 = StubAgent("A1", [Action.CHARGE])
    stub2 = StubAgent("A2", [Action.CHARGE])

    session = MatchSession(participant_1=stub1, participant_2=stub2)

    # Set state as finished
    finished_state = replace(
        session.state,
        status=MatchStatus.FINISHED,
        result=MatchResult(winner="player_1", reason=FinishReason.BURST),
    )
    session.restart(finished_state)

    assert session.is_finished is True
    assert session.can_step is False

    with pytest.raises(MatchFinishedError, match="match is already finished"):
        session.step_round()


# ==============================================================================
# 6. Headless Batch Runner Tests
# ==============================================================================


def test_batch_runner_deterministic_seeds() -> None:
    """Verify identical seeds produce identical match results across batch executions."""
    # Run batch of 2 matches with fixed base_seed
    b1 = run_headless_batch(
        total_matches=2,
        agent_a="ironclad",
        agent_b="cyclone",
        agent_a_difficulty="easy",
        agent_b_difficulty="easy",
        base_seed=999,
        max_rounds_guard=45,
    )

    b2 = run_headless_batch(
        total_matches=2,
        agent_a="ironclad",
        agent_b="cyclone",
        agent_a_difficulty="easy",
        agent_b_difficulty="easy",
        base_seed=999,
        max_rounds_guard=45,
    )

    assert b1.total_matches == b2.total_matches == 2
    assert b1.agent_a_wins == b2.agent_a_wins
    assert b1.agent_b_wins == b2.agent_b_wins
    assert b1.draws == b2.draws

    for m1, m2 in zip(b1.matches, b2.matches):
        assert m1.winner_name == m2.winner_name
        assert m1.finish_reason == m2.finish_reason
        assert m1.completed_rounds == m2.completed_rounds


def test_batch_runner_alternating_sides() -> None:
    """Verify batch runner alternates Player 1 / Player 2 roles when configured."""
    summary = run_headless_batch(
        total_matches=4,
        agent_a="ironclad",
        agent_b="cyclone",
        agent_a_name="Ironclad",
        agent_b_name="Cyclone",
        agent_a_difficulty="easy",
        agent_b_difficulty="easy",
        alternate_sides=True,
    )

    assert len(summary.matches) == 4
    # Match 0: even -> P1=Ironclad, P2=Cyclone
    assert summary.matches[0].player_1_name == "Ironclad"
    assert summary.matches[0].player_2_name == "Cyclone"

    # Match 1: odd -> P1=Cyclone, P2=Ironclad
    assert summary.matches[1].player_1_name == "Cyclone"
    assert summary.matches[1].player_2_name == "Ironclad"

    # Match 2: even -> P1=Ironclad, P2=Cyclone
    assert summary.matches[2].player_1_name == "Ironclad"
    assert summary.matches[2].player_2_name == "Cyclone"

    # Match 3: odd -> P1=Cyclone, P2=Ironclad
    assert summary.matches[3].player_1_name == "Cyclone"
    assert summary.matches[3].player_2_name == "Ironclad"


def test_batch_runner_rejects_non_positive_matches() -> None:
    """Verify batch runner rejects zero or negative match counts."""
    with pytest.raises(ValueError, match="total_matches must be positive"):
        run_headless_batch(total_matches=0, agent_a="ironclad", agent_b="cyclone")


def test_complete_real_ai_vs_ai_headless_match() -> None:
    """Verify a complete real match between Ironclad and Cyclone executes to terminal state."""
    p1 = create_ai_participant("Ironclad", AgentType.IRONCLAD, difficulty="easy")
    p2 = create_ai_participant("Cyclone", AgentType.CYCLONE, difficulty="easy", seed=123)

    session = MatchSession(participant_1=p1, participant_2=p2)
    final_state = session.run_to_completion(max_rounds=45)

    assert final_state.status == MatchStatus.FINISHED
    assert final_state.result is not None
    assert isinstance(final_state.result.reason, FinishReason)
    assert final_state.completed_rounds >= 1
    assert len(session.round_history) == final_state.completed_rounds


def test_orchestration_does_not_initialize_pygame() -> None:
    """Verify importing orchestration does not initialize Pygame or open a window."""
    code = (
        "import blade_arena.orchestration\n"
        "import pygame\n"
        "assert not pygame.display.get_init(), 'Display was initialized on import'\n"
        "assert pygame.display.get_surface() is None, 'Display surface was created on import'\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        timeout=5,
    )
    assert result.returncode == 0, f"Import check failed: {result.stderr}"
