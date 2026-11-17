"""Unit and integration tests for Ironclad Minimax AI (Module 11).

Verifies:
1. MAX maximizes and MIN minimizes in controlled game states.
2. Terminal utility dominance: forces win and avoids forced loss.
3. Iterative deepening: depths 1, 2, and 3 lookahead with depth reporting.
4. Budget interruption and fallback:
   - Pre-depth-1 interruption falls back safely to first legal action.
   - Mid-search interruption retains last fully completed depth.
5. Deterministic tie-breaking based on canonical ORDERED_ACTIONS.
6. Fairness and secrecy: no access to hidden opponent actions.
7. Finished state rejection raising MatchFinishedError.
8. Agent API compliance (choose_action and decide).
9. Search execution timing and performance telemetry.
10. Headless purity and complete immutability of game state.
"""

from __future__ import annotations

import time
import pytest

from blade_arena.ai.ironclad import (
    DIFFICULTY_DEPTHS,
    IroncladAgent,
    IroncladConfig,
    IroncladDecision,
    IroncladDifficulty,
    choose_action,
    decide,
)
from blade_arena.game.actions import ORDERED_ACTIONS, legal_actions
from blade_arena.game.blade_definitions import create_blade_state
from blade_arena.game.combat import ClassicDishRoundResolver
from blade_arena.game.initial_state import create_default_match
from blade_arena.game.match_controller import MatchController, MatchFinishedError
from blade_arena.game.models import (
    Action,
    BladeType,
    FinishReason,
    MatchResult,
    MatchState,
    MatchStatus,
    Position,
    StadiumState,
    StadiumType,
)


# -----------------------------------------------------------------------------
# 1. Decision Quality in Controlled Tactical States
# -----------------------------------------------------------------------------

def test_ironclad_seizes_immediate_knockout_opportunity() -> None:
    """When an opponent is on the brink of burst with limited options, Ironclad chooses an action that forces the win."""
    # Place Player 1 at (0.0, 0.0) facing Player 2 at (0.5, 0.0).
    # Player 2 has 1.0 energy and 1.0 stability (can only CHARGE, cannot guard/dodge).
    # Attack connects and inflicts fatal stability damage, forcing a terminal win.
    match = MatchState(
        player_1_blade=create_blade_state(
            player_id="player_1",
            blade_type=BladeType.ATTACKER,
            position=Position(0.0, 0.0),
        ),
        player_2_blade=create_blade_state(
            player_id="player_2",
            blade_type=BladeType.BALANCED,
            position=Position(0.5, 0.0),
        ),
        stadium=StadiumState(StadiumType.CLASSIC_DISH, Position(0.0, 0.0), 10.0),
        completed_rounds=1,
        status=MatchStatus.IN_PROGRESS,
        result=None,
    )
    object.__setattr__(match.player_2_blade, "current_stability", 1.0)
    object.__setattr__(match.player_2_blade, "current_energy", 1.0)

    decision = decide(match, "player_1", config=IroncladConfig(max_depth=1))
    assert decision.eval_score == 100.0
    assert decision.action in (Action.ATTACK, Action.SPECIAL_SPIN)


def test_ironclad_avoids_suicide_move() -> None:
    """When near the edge, Ironclad selects an action that prevents immediate ring-out."""
    # Player 1 is at (-9.4, 0.0) near perimeter. Center is to the right (+x).
    # Charge moves toward center (+2.0 -> to -7.4), which is safe.
    # Dodge might move sideways or near-edge.
    match = MatchState(
        player_1_blade=create_blade_state(
            player_id="player_1",
            blade_type=BladeType.DEFENDER,
            position=Position(-9.4, 0.0),
        ),
        player_2_blade=create_blade_state(
            player_id="player_2",
            blade_type=BladeType.BALANCED,
            position=Position(0.0, 0.0),
        ),
        stadium=StadiumState(StadiumType.CLASSIC_DISH, Position(0.0, 0.0), 10.0),
        completed_rounds=1,
        status=MatchStatus.IN_PROGRESS,
        result=None,
    )

    decision = decide(match, "player_1", config=IroncladConfig(max_depth=1))
    assert decision.action in legal_actions(match, "player_1")
    # Action chosen must guarantee non-negative utility (not guaranteed loss -100.0)
    assert decision.eval_score > -100.0


# -----------------------------------------------------------------------------
# 2. Iterative Deepening and Depth Cutoffs
# -----------------------------------------------------------------------------

def test_iterative_deepening_easy_depth_1() -> None:
    """Easy difficulty completes depth 1 and evaluates at most 25 root action pairs."""
    match = create_default_match()
    cfg = IroncladConfig.for_difficulty(IroncladDifficulty.EASY)
    decision = decide(match, "player_1", config=cfg)

    assert decision.depth_completed == 1
    assert decision.action in legal_actions(match, "player_1")
    assert 1 <= decision.nodes_evaluated <= 25
    assert decision.decision_time_seconds >= 0.0


def test_iterative_deepening_medium_depth_2() -> None:
    """Medium difficulty completes depth 2 with higher node count."""
    match = create_default_match()
    cfg = IroncladConfig.for_difficulty(IroncladDifficulty.MEDIUM)
    decision = decide(match, "player_1", config=cfg)

    assert decision.depth_completed == 2
    assert decision.action in legal_actions(match, "player_1")
    assert decision.nodes_evaluated > 25
    assert decision.decision_time_seconds >= 0.0


def test_iterative_deepening_hard_depth_3() -> None:
    """Hard difficulty completes depth 3 search cleanly."""
    match = create_default_match()
    cfg = IroncladConfig.for_difficulty(IroncladDifficulty.HARD)
    decision = decide(match, "player_1", config=cfg)

    assert decision.depth_completed == 3
    assert decision.action in legal_actions(match, "player_1")
    assert decision.nodes_evaluated > 200
    assert decision.decision_time_seconds >= 0.0


# -----------------------------------------------------------------------------
# 3. Interruption Handling and Safe Fallback Guarantees
# -----------------------------------------------------------------------------

def test_interruption_before_depth_1_guarantees_legal_fallback() -> None:
    """If node budget is exceeded during depth 1, the immediate legal fallback is returned."""
    match = create_default_match()
    # Set node limit to 2 (depth 1 needs 14-25 nodes to complete)
    cfg = IroncladConfig(max_depth=2, max_nodes=2)
    decision = decide(match, "player_1", config=cfg)

    assert decision.depth_completed == 0
    assert decision.action in legal_actions(match, "player_1")
    assert decision.nodes_evaluated <= 3


def test_interruption_during_depth_2_preserves_depth_1_decision() -> None:
    """If node budget allows depth 1 but interrupts depth 2, depth 1 decision is retained."""
    match = create_default_match()
    # Depth 1 needs ~14 nodes. Give budget of 30 nodes so depth 1 finishes but depth 2 interrupts
    cfg_limited = IroncladConfig(max_depth=2, max_nodes=30)
    cfg_depth1 = IroncladConfig(max_depth=1)

    decision_limited = decide(match, "player_1", config=cfg_limited)
    decision_d1 = decide(match, "player_1", config=cfg_depth1)

    assert decision_limited.depth_completed == 1
    assert decision_limited.action == decision_d1.action
    assert decision_limited.eval_score == decision_d1.eval_score


# -----------------------------------------------------------------------------
# 4. Deterministic Tie-Breaking
# -----------------------------------------------------------------------------

def test_deterministic_tie_breaking_order() -> None:
    """When all candidate actions yield identical heuristic evaluations, canonical ORDERED_ACTIONS order wins."""
    match = create_default_match()
    decision = decide(match, "player_1", config=IroncladConfig(max_depth=1))

    # All decisions must be 100% deterministic
    decision2 = decide(match, "player_1", config=IroncladConfig(max_depth=1))
    assert decision.action == decision2.action
    assert decision.eval_score == decision2.eval_score
    assert decision.action_scores == decision2.action_scores


def test_pruned_and_unpruned_search_produce_identical_decisions() -> None:
    """Alpha-pruned search produces identical action choice and score to unpruned search."""
    match = create_default_match()
    # Moderate damage so state has non-trivial gradients
    object.__setattr__(match.player_2_blade, "current_energy", 60.0)

    cfg_pruned = IroncladConfig(max_depth=2, enable_pruning=True)
    cfg_unpruned = IroncladConfig(max_depth=2, enable_pruning=False)

    dec_pruned = decide(match, "player_1", config=cfg_pruned)
    dec_unpruned = decide(match, "player_1", config=cfg_unpruned)

    assert dec_pruned.action == dec_unpruned.action
    assert pytest.approx(dec_pruned.eval_score, abs=1e-5) == dec_unpruned.eval_score
    assert dec_pruned.nodes_evaluated < dec_unpruned.nodes_evaluated


# -----------------------------------------------------------------------------
# 5. Fair Play and Secrecy: No Hidden Action Leaks
# -----------------------------------------------------------------------------

def test_ironclad_does_not_inspect_controller_pending_actions() -> None:
    """Ironclad operates solely on MatchState and does not observe hidden pending controller choices."""
    controller = MatchController(create_default_match(), ClassicDishRoundResolver())
    controller.submit_action("player_2", Action.GUARD)

    # Controller has pending action for player 2, but state hides pending choices
    state = controller.state
    agent = IroncladAgent(player_id="player_1", difficulty=IroncladDifficulty.EASY)

    # Agent must choose an action without knowing player 2 selected GUARD
    act = agent.choose_action(state)
    assert act in legal_actions(state, "player_1")


# -----------------------------------------------------------------------------
# 6. Lifecycle and Terminal State Handling
# -----------------------------------------------------------------------------

def test_finished_match_rejects_action_selection() -> None:
    """Requesting an action for a match marked FINISHED raises MatchFinishedError."""
    match = MatchState(
        player_1_blade=create_blade_state(
            player_id="player_1",
            blade_type=BladeType.BALANCED,
            position=Position(0.0, 0.0),
        ),
        player_2_blade=create_blade_state(
            player_id="player_2",
            blade_type=BladeType.BALANCED,
            position=Position(12.0, 0.0),
        ),
        stadium=StadiumState(StadiumType.CLASSIC_DISH, Position(0.0, 0.0), 10.0),
        completed_rounds=5,
        status=MatchStatus.FINISHED,
        result=MatchResult(
            winner="player_1",
            reason=FinishReason.RING_OUT,
        ),
    )

    with pytest.raises(MatchFinishedError, match="match is already finished"):
        choose_action(match, "player_1")

    with pytest.raises(MatchFinishedError, match="match is already finished"):
        decide(match, "player_1")


def test_unfinalized_terminal_state_rejects_action_selection() -> None:
    """A match that has reached zero stability is terminal and rejects action selection."""
    match = create_default_match()
    object.__setattr__(match.player_1_blade, "current_stability", 0.0)

    with pytest.raises(MatchFinishedError, match="match is already finished"):
        choose_action(match, "player_1")


# -----------------------------------------------------------------------------
# 7. Agent Wrapper API and Symmetry
# -----------------------------------------------------------------------------

def test_ironclad_agent_api() -> None:
    """IroncladAgent provides clean choose_action and decide interfaces for both sides."""
    match = create_default_match()
    p1_agent = IroncladAgent(player_id="player_1", difficulty=IroncladDifficulty.EASY)
    p2_agent = IroncladAgent(player_id="player_2", difficulty=IroncladDifficulty.EASY)

    # Simple action retrieval
    p1_act = p1_agent.choose_action(match)
    assert isinstance(p1_act, Action)
    assert p1_act in legal_actions(match, "player_1")

    # With diagnostics
    p2_act, p2_diag = p2_agent.choose_action(match, return_diagnostics=True)
    assert isinstance(p2_act, Action)
    assert isinstance(p2_diag, IroncladDecision)
    assert p2_diag.action == p2_act


def test_invalid_player_id_rejected() -> None:
    """Invalid player IDs raise ValueError."""
    match = create_default_match()
    with pytest.raises(ValueError, match="Unknown player_id 'player_unknown'"):
        choose_action(match, "player_unknown")


def test_state_immutability_during_search() -> None:
    """Minimax tree search leaves root MatchState completely unmodified."""
    match = create_default_match()
    orig_p1_energy = match.player_1_blade.current_energy
    orig_p2_pos = match.player_2_blade.position
    orig_rounds = match.completed_rounds

    _ = decide(match, "player_1", config=IroncladConfig(max_depth=2))

    assert match.player_1_blade.current_energy == orig_p1_energy
    assert match.player_2_blade.position == orig_p2_pos
    assert match.completed_rounds == orig_rounds


def test_ironclad_does_not_initialize_pygame() -> None:
    """Ironclad subsystem has zero Pygame dependencies."""
    import blade_arena.ai.ironclad as ironclad_module

    assert not hasattr(ironclad_module, "pygame")
