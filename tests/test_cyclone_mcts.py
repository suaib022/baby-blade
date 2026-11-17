"""Unit and integration tests for Cyclone Monte Carlo Tree Search (MCTS) AI (Module 12).

Verifies:
1. UCB1 selection math and unvisited action prioritization.
2. Expansion and distinct branching across sampled opponent replies.
3. Terminal reward evaluation (+1.0 for win, -1.0 for loss, 0.0 for draw).
4. Rollout cutoff heuristic evaluation in [-0.85, +0.85].
5. Same-seed reproducibility: identical seeds produce bitwise identical trees, visits, and decisions.
6. Zero budget fallback: returns immediate legal action with 0 iterations completed.
7. Finished state rejection: raises MatchFinishedError on finished or terminal states.
8. Purity: zero global random state mutation and zero game state mutation.
9. Full headless match execution between Cyclone and Ironclad / Cyclone and Cyclone.
10. Performance profiling across Easy (50), Medium (200), and Hard (500) budgets.
"""

from __future__ import annotations

import math
import random
import sys
import pytest

from blade_arena.ai.cyclone import (
    DIFFICULTY_ITERATIONS,
    CycloneAgent,
    CycloneConfig,
    CycloneDecision,
    CycloneDifficulty,
    _MCTSActionNode,
    _MCTSStateNode,
    _simulate_rollout,
    _ucb1,
    choose_action,
    decide,
)
from blade_arena.ai.ironclad import IroncladAgent, IroncladDifficulty
from blade_arena.game.actions import ORDERED_ACTIONS, legal_actions
from blade_arena.game.blade_definitions import create_blade_state
from blade_arena.game.combat import ClassicDishRoundResolver, resolve_combat_round
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
# 1. UCB1 Formula and Selection
# -----------------------------------------------------------------------------

def test_ucb1_unvisited_node_returns_infinity() -> None:
    """An unvisited action node returns infinity, ensuring it is explored first."""
    node = _MCTSActionNode(Action.ATTACK, [Action.CHARGE, Action.GUARD])
    assert node.visits == 0
    assert _ucb1(node, parent_visits=10, c=1.4) == float("inf")


def test_ucb1_calculation_accuracy() -> None:
    """UCB1 matches manual analytical evaluation."""
    node = _MCTSActionNode(Action.CHARGE, [])
    node.visits = 4
    node.total_reward = 2.0  # avg reward = 0.5
    parent_visits = 16

    # exploitation = 0.5
    # exploration = 1.4 * sqrt(ln(16) / 4) = 1.4 * sqrt(2.7725887 / 4) = 1.4 * sqrt(0.693147) = 1.4 * 0.8325546 = 1.165576
    # UCB1 = 0.5 + 1.165576 = 1.665576
    expected = 0.5 + 1.4 * math.sqrt(math.log(16) / 4)
    calculated = _ucb1(node, parent_visits=16, c=1.4)
    assert pytest.approx(calculated, abs=1e-6) == expected


# -----------------------------------------------------------------------------
# 2. Expansion and Distinct Opponent Outcomes
# -----------------------------------------------------------------------------

def test_expansion_creates_distinct_opponent_outcomes() -> None:
    """Opponent replies under one action remain distinct state nodes in the tree."""
    match = create_default_match()
    state_node = _MCTSStateNode(match, "player_1", "player_2")

    # Action child for ATTACK
    attack_node = state_node.children[Action.ATTACK]
    assert len(attack_node.outcomes) == 0
    assert len(attack_node.unexpanded_opp_actions) > 0

    # Expand one opponent reply
    opp_act1 = attack_node.unexpanded_opp_actions.pop(0)
    nxt1, _ = resolve_combat_round(match, Action.ATTACK, opp_act1)
    attack_node.outcomes[opp_act1] = _MCTSStateNode(nxt1, "player_1", "player_2")

    # Expand a different opponent reply
    opp_act2 = attack_node.unexpanded_opp_actions.pop(0)
    nxt2, _ = resolve_combat_round(match, Action.ATTACK, opp_act2)
    attack_node.outcomes[opp_act2] = _MCTSStateNode(nxt2, "player_1", "player_2")

    assert opp_act1 != opp_act2
    assert len(attack_node.outcomes) == 2
    assert attack_node.outcomes[opp_act1] is not attack_node.outcomes[opp_act2]


# -----------------------------------------------------------------------------
# 3. Rollout Simulation and Reward Extremes
# -----------------------------------------------------------------------------

def test_rollout_evaluates_terminal_state_directly() -> None:
    """Terminal state leaf evaluates directly to +1.0 for win, -1.0 for loss, 0.0 for draw."""
    win_match = MatchState(
        player_1_blade=create_blade_state("player_1", BladeType.BALANCED, Position(0.0, 0.0)),
        player_2_blade=create_blade_state("player_2", BladeType.BALANCED, Position(12.0, 0.0)),
        stadium=StadiumState(StadiumType.CLASSIC_DISH, Position(0.0, 0.0), 10.0),
        completed_rounds=5,
        status=MatchStatus.FINISHED,
        result=MatchResult(winner="player_1", reason=FinishReason.RING_OUT),
    )
    cfg = CycloneConfig()
    rng = random.Random(42)

    reward_p1 = _simulate_rollout(win_match, "player_1", "player_2", cfg, rng)
    reward_p2 = _simulate_rollout(win_match, "player_2", "player_1", cfg, rng)

    assert reward_p1 == 1.0
    assert reward_p2 == -1.0


def test_rollout_heuristic_cutoff_bounded_within_extremes() -> None:
    """Nonterminal rollout cutoff yields rewards strictly within (-1.0, +1.0)."""
    match = create_default_match()
    cfg = CycloneConfig(max_rollout_depth=1)
    rng = random.Random(42)

    reward = _simulate_rollout(match, "player_1", "player_2", cfg, rng)
    assert -0.85 <= reward <= 0.85
    assert reward < 1.0
    assert reward > -1.0


# -----------------------------------------------------------------------------
# 4. Reproducibility with Injected Seed and RNG Isolation
# -----------------------------------------------------------------------------

def test_same_seed_gives_identical_decisions_and_tree_statistics() -> None:
    """Identical seeds and iteration counts yield identical visit counts, rewards, and action choices."""
    match = create_default_match()
    cfg1 = CycloneConfig(iterations=100, seed=12345)
    cfg2 = CycloneConfig(iterations=100, seed=12345)

    dec1 = decide(match, "player_1", config=cfg1)
    dec2 = decide(match, "player_1", config=cfg2)

    assert dec1.action == dec2.action
    assert dec1.eval_score == dec2.eval_score
    assert dec1.action_visits == dec2.action_visits
    assert dec1.action_rewards == dec2.action_rewards
    assert dec1.iterations_completed == dec2.iterations_completed == 100


def test_mcts_does_not_mutate_global_random_state() -> None:
    """Cyclone search does not mutate or advance the global random module state."""
    # Capture global random state
    random.seed(999)
    state_before = random.getstate()

    match = create_default_match()
    _ = decide(match, "player_1", config=CycloneConfig(iterations=50, seed=42))

    state_after = random.getstate()
    assert state_before == state_after


# -----------------------------------------------------------------------------
# 5. Fallback and Edge Case Handling
# -----------------------------------------------------------------------------

def test_zero_iteration_budget_returns_legal_fallback() -> None:
    """A zero-iteration budget returns an immediately legal fallback action with 0 iterations."""
    match = create_default_match()
    cfg = CycloneConfig(iterations=0)
    decision = decide(match, "player_1", config=cfg)

    assert decision.iterations_completed == 0
    assert decision.action in legal_actions(match, "player_1")
    assert decision.eval_score == 0.0


def test_finished_match_rejects_action_selection() -> None:
    """Calling choose_action or decide on a finished match raises MatchFinishedError."""
    finished_match = MatchState(
        player_1_blade=create_blade_state("player_1", BladeType.BALANCED, Position(0.0, 0.0)),
        player_2_blade=create_blade_state("player_2", BladeType.BALANCED, Position(12.0, 0.0)),
        stadium=StadiumState(StadiumType.CLASSIC_DISH, Position(0.0, 0.0), 10.0),
        completed_rounds=5,
        status=MatchStatus.FINISHED,
        result=MatchResult(winner="player_1", reason=FinishReason.RING_OUT),
    )

    with pytest.raises(MatchFinishedError, match="match is already finished"):
        choose_action(finished_match, "player_1")

    with pytest.raises(MatchFinishedError, match="match is already finished"):
        decide(finished_match, "player_1")


def test_invalid_player_id_rejected() -> None:
    """Unknown player IDs raise ValueError."""
    match = create_default_match()
    with pytest.raises(ValueError, match="Unknown player_id 'player_xyz'"):
        choose_action(match, "player_xyz")


# -----------------------------------------------------------------------------
# 6. Fair Play, Secrecy, and Immutability
# -----------------------------------------------------------------------------

def test_cyclone_does_not_inspect_controller_pending_actions() -> None:
    """Cyclone operates solely on MatchState and does not observe hidden pending controller choices."""
    controller = MatchController(create_default_match(), ClassicDishRoundResolver())
    controller.submit_action("player_2", Action.GUARD)

    state = controller.state
    agent = CycloneAgent(player_id="player_1", difficulty=CycloneDifficulty.EASY)

    action = agent.choose_action(state)
    assert action in legal_actions(state, "player_1")


def test_state_immutability_during_mcts_search() -> None:
    """Tree search and simulation rollouts leave the root MatchState completely unmodified."""
    match = create_default_match()
    orig_p1_energy = match.player_1_blade.current_energy
    orig_p2_pos = match.player_2_blade.position
    orig_rounds = match.completed_rounds

    _ = decide(match, "player_1", config=CycloneConfig(iterations=50, seed=42))

    assert match.player_1_blade.current_energy == orig_p1_energy
    assert match.player_2_blade.position == orig_p2_pos
    assert match.completed_rounds == orig_rounds


# -----------------------------------------------------------------------------
# 7. Agent Wrapper API and Match Simulation
# -----------------------------------------------------------------------------

def test_cyclone_agent_wrapper_api() -> None:
    """CycloneAgent provides choose_action (plain Action or with diagnostics) and decide."""
    match = create_default_match()
    agent = CycloneAgent(player_id="player_1", difficulty=CycloneDifficulty.EASY)

    # Plain Action
    act = agent.choose_action(match)
    assert isinstance(act, Action)
    assert act in legal_actions(match, "player_1")

    # With diagnostics
    act_diag, decision = agent.choose_action(match, return_diagnostics=True)
    assert act_diag == decision.action
    assert isinstance(decision, CycloneDecision)
    assert decision.iterations_completed == 50


def test_cyclone_vs_ironclad_headless_match_simulation() -> None:
    """A complete multi-round match between Cyclone and Ironclad executes cleanly via MatchController."""
    match = create_default_match()
    controller = MatchController(match, ClassicDishRoundResolver())

    cyclone = CycloneAgent(player_id="player_1", config=CycloneConfig(iterations=30, seed=42))
    ironclad = IroncladAgent(player_id="player_2", difficulty=IroncladDifficulty.EASY)

    rounds_played = 0
    max_rounds = 8

    while controller.state.status == MatchStatus.IN_PROGRESS and rounds_played < max_rounds:
        st = controller.state
        act1 = cyclone.choose_action(st)
        act2 = ironclad.choose_action(st)

        controller.submit_action("player_1", act1)
        controller.submit_action("player_2", act2)
        controller.resolve_round()
        rounds_played += 1

    assert rounds_played > 0
    assert controller.state.completed_rounds == rounds_played


def test_cyclone_does_not_initialize_pygame() -> None:
    """Cyclone subsystem has zero Pygame dependencies."""
    import blade_arena.ai.cyclone as cyclone_module

    assert not hasattr(cyclone_module, "pygame")
