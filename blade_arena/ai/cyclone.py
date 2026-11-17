"""Cyclone AI — Monte Carlo Tree Search (MCTS) with simultaneous-action modeling.

This module implements the Cyclone AI agent using classical Monte Carlo Tree
Search adapted for simultaneous two-player zero-sum combat:
1. Selection: Traversing the tree via UCB1 (Q/n + C*sqrt(ln(N)/n)), prioritizing
   unvisited candidate actions.
2. Expansion: When an action node is selected, an opponent counter-action is
   sampled uniformly from its legal choices, creating a distinct outcome node.
3. Simulation (Rollout): Simulating forward with legal random actions up to a
   terminal state or bounded horizon. Truncated rollouts are evaluated using
   the bounded heuristic reward in [-0.85, +0.85].
4. Backpropagation: Propagating terminal (+1.0 / -1.0 / 0.0) or heuristic rollout
   rewards up through the tree strictly from Cyclone's perspective.
5. Final Decision: Selecting the action with the highest visit count, with
   deterministic tie-breaking based on average reward and canonical action order.

Determinism and Reproducibility:
- Cyclone uses an isolated local `random.Random` instance or injected seed.
- It never accesses or mutates global random state.
- It never inspects hidden pending actions in the match controller.
"""

from __future__ import annotations

import math
import random
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple, Union

from blade_arena.game.actions import ORDERED_ACTIONS, legal_actions
from blade_arena.game.combat import resolve_combat_round
from blade_arena.game.heuristic import (
    DEFAULT_HEURISTIC_CONFIG,
    HeuristicConfig,
    evaluate_state,
)
from blade_arena.game.match_controller import MatchFinishedError
from blade_arena.game.models import Action, MatchState, MatchStatus
from blade_arena.game.win_conditions import evaluate_match_termination, is_match_terminal


class CycloneDifficulty(str, Enum):
    """Preset difficulty configurations for Cyclone MCTS."""

    EASY = "easy"        # 50 iterations
    MEDIUM = "medium"    # 200 iterations
    HARD = "hard"        # 500 iterations


DIFFICULTY_ITERATIONS: Dict[CycloneDifficulty, int] = {
    CycloneDifficulty.EASY: 50,
    CycloneDifficulty.MEDIUM: 200,
    CycloneDifficulty.HARD: 500,
}


@dataclass(frozen=True)
class CycloneConfig:
    """Configuration for Cyclone MCTS search.

    Attributes:
        iterations: Number of MCTS simulation cycles to run.
        exploration_constant: UCB1 exploration parameter C (default 1.4).
        max_rollout_depth: Maximum simulation rounds before applying heuristic cutoff.
        seed: Optional integer seed for repeatable pseudorandom rollouts.
        time_limit_seconds: Optional wall-clock search budget.
        heuristic_config: Configuration for rollout cutoff heuristic evaluation.
    """

    iterations: int = 200
    exploration_constant: float = 1.4
    max_rollout_depth: int = 6
    seed: Optional[int] = None
    time_limit_seconds: Optional[float] = None
    heuristic_config: HeuristicConfig = DEFAULT_HEURISTIC_CONFIG

    def __post_init__(self) -> None:
        if self.iterations < 0:
            raise ValueError(f"iterations must be non-negative, got {self.iterations}")
        if self.exploration_constant <= 0.0:
            raise ValueError(f"exploration_constant must be positive, got {self.exploration_constant}")
        if self.max_rollout_depth < 1:
            raise ValueError(f"max_rollout_depth must be at least 1, got {self.max_rollout_depth}")
        if self.time_limit_seconds is not None and self.time_limit_seconds <= 0.0:
            raise ValueError("time_limit_seconds must be positive if specified")

    @classmethod
    def for_difficulty(
        cls,
        difficulty: Union[CycloneDifficulty, str] = CycloneDifficulty.MEDIUM,
        **kwargs,
    ) -> CycloneConfig:
        """Create a configuration tuned for a given difficulty preset."""
        diff_enum = CycloneDifficulty(difficulty)
        iterations = DIFFICULTY_ITERATIONS[diff_enum]
        return cls(iterations=iterations, **kwargs)


@dataclass(frozen=True)
class CycloneDecision:
    """Diagnostics and decision telemetry returned by Cyclone MCTS."""

    action: Action
    iterations_completed: int
    eval_score: float
    decision_time_seconds: float
    action_visits: Dict[Action, int]
    action_rewards: Dict[Action, float]
    seed_used: Optional[int]


class _MCTSActionNode:
    """Represents a candidate action taken by Cyclone from a state node."""

    def __init__(self, action: Action, opponent_legal_actions: List[Action]) -> None:
        self.action = action
        self.visits = 0
        self.total_reward = 0.0
        # Outcomes maps an opponent's action to the resulting MCTSStateNode
        self.outcomes: Dict[Action, _MCTSStateNode] = {}
        # Unexpanded opponent replies for this action
        self.unexpanded_opp_actions: List[Action] = list(opponent_legal_actions)

    @property
    def average_reward(self) -> float:
        return (self.total_reward / self.visits) if self.visits > 0 else 0.0


class _MCTSStateNode:
    """Represents a game state reached during MCTS exploration."""

    def __init__(
        self,
        state: MatchState,
        player_id: str,
        opponent_id: str,
    ) -> None:
        self.state = state
        self.player_id = player_id
        self.opponent_id = opponent_id
        self.visits = 0

        # Children are Cyclone's legal actions
        my_legal = legal_actions(state, player_id)
        opp_legal = legal_actions(state, opponent_id)

        ordered_my = [a for a in ORDERED_ACTIONS if a in my_legal]
        self.children: Dict[Action, _MCTSActionNode] = {
            a: _MCTSActionNode(a, opp_legal) for a in ordered_my
        }


def _ucb1(
    action_node: _MCTSActionNode,
    parent_visits: int,
    c: float,
) -> float:
    """Calculate UCB1 score for an action child."""
    if action_node.visits == 0:
        return float("inf")
    exploitation = action_node.total_reward / action_node.visits
    exploration = c * math.sqrt(math.log(parent_visits) / action_node.visits)
    return exploitation + exploration


def _simulate_rollout(
    start_state: MatchState,
    player_id: str,
    opponent_id: str,
    config: CycloneConfig,
    rng: random.Random,
) -> float:
    """Simulate a random rollout from a leaf state to terminal or max depth.

    Returns:
        Reward from player_id's perspective in [-1.0, +1.0].
    """
    state = start_state
    is_p1 = player_id == state.player_1_blade.player_id

    for _ in range(config.max_rollout_depth):
        # 1. Terminal Check
        if state.status == MatchStatus.FINISHED or is_match_terminal(state):
            break

        my_legal = legal_actions(state, player_id)
        opp_legal = legal_actions(state, opponent_id)

        if not my_legal or not opp_legal:
            break

        # Uniform random action selection for both sides during simulation
        a_my = rng.choice(my_legal)
        a_opp = rng.choice(opp_legal)

        p1_act, p2_act = (a_my, a_opp) if is_p1 else (a_opp, a_my)
        state, _ = resolve_combat_round(state, p1_act, p2_act)

    # Evaluate outcome strictly in [-1.0, +1.0]
    eval_res = evaluate_state(state, player_id, config=config.heuristic_config)
    return eval_res.mcts_reward


def decide(
    state: MatchState,
    player_id: str,
    config: Optional[CycloneConfig] = None,
) -> CycloneDecision:
    """Execute Monte Carlo Tree Search for the acting player.

    Args:
        state: Pre-round immutable MatchState.
        player_id: Acting player identifier ('player_1' or 'player_2').
        config: Optional CycloneConfig instance.

    Returns:
        CycloneDecision containing chosen action, visit statistics, and telemetry.

    Raises:
        TypeError: If state or player_id has an invalid type.
        ValueError: If player_id does not belong to the match.
        MatchFinishedError: If the match is already finished or terminal.
    """
    start_time = time.perf_counter()

    if not isinstance(state, MatchState):
        raise TypeError(f"state must be a MatchState instance, got {type(state).__name__}")
    if not isinstance(player_id, str):
        raise TypeError(f"player_id must be a string, got {type(player_id).__name__}")

    p1_id = state.player_1_blade.player_id
    p2_id = state.player_2_blade.player_id

    if player_id == p1_id:
        opponent_id = p2_id
    elif player_id == p2_id:
        opponent_id = p1_id
    else:
        raise ValueError(f"Unknown player_id '{player_id}'. Must be '{p1_id}' or '{p2_id}'.")

    # Reject finished or terminal states
    if state.status == MatchStatus.FINISHED or is_match_terminal(state):
        raise MatchFinishedError("Cannot choose an action: the match is already finished.")

    my_actions = legal_actions(state, player_id)
    if not my_actions:
        raise MatchFinishedError("No legal actions available for player.")

    cfg = config or CycloneConfig()

    # Local RNG isolation
    if cfg.seed is not None:
        rng = random.Random(cfg.seed)
    else:
        rng = random.Random()

    ordered_legal = [a for a in ORDERED_ACTIONS if a in my_actions]
    immediate_fallback = ordered_legal[0]

    # Zero-iteration budget fallback
    if cfg.iterations == 0:
        elapsed = time.perf_counter() - start_time
        return CycloneDecision(
            action=immediate_fallback,
            iterations_completed=0,
            eval_score=0.0,
            decision_time_seconds=elapsed,
            action_visits={a: 0 for a in ordered_legal},
            action_rewards={a: 0.0 for a in ordered_legal},
            seed_used=cfg.seed,
        )

    # Build Root State Node
    root = _MCTSStateNode(state, player_id, opponent_id)
    is_p1 = player_id == p1_id
    deadline = (start_time + cfg.time_limit_seconds) if cfg.time_limit_seconds is not None else None

    iterations_completed = 0

    for iter_idx in range(cfg.iterations):
        if deadline is not None and time.perf_counter() >= deadline:
            break

        # Phase 1: Selection
        current_state_node = root
        path_state_nodes: List[_MCTSStateNode] = [root]
        path_action_nodes: List[_MCTSActionNode] = []
        leaf_state: Optional[MatchState] = None

        while True:
            # Check if current state node is terminal
            if current_state_node.state.status == MatchStatus.FINISHED or is_match_terminal(current_state_node.state):
                leaf_state = current_state_node.state
                break

            # Check for unvisited action children at current state node
            unvisited_actions = [
                act_node for act_node in current_state_node.children.values()
                if act_node.visits == 0
            ]

            if unvisited_actions:
                # Prioritize unvisited action in canonical order
                chosen_action_node = unvisited_actions[0]
            else:
                # UCB1 Selection across visited actions
                best_ucb = float("-inf")
                chosen_action_node = None

                for act_node in current_state_node.children.values():
                    val = _ucb1(act_node, current_state_node.visits, cfg.exploration_constant)
                    if val > best_ucb + 1e-6:
                        best_ucb = val
                        chosen_action_node = act_node

                assert chosen_action_node is not None

            path_action_nodes.append(chosen_action_node)

            # Phase 2: Expansion
            if chosen_action_node.unexpanded_opp_actions:
                # Pick an unexpanded opponent reply using local RNG
                opp_act = rng.choice(chosen_action_node.unexpanded_opp_actions)
                chosen_action_node.unexpanded_opp_actions.remove(opp_act)

                # Resolve new joint child state
                my_act = chosen_action_node.action
                p1_act, p2_act = (my_act, opp_act) if is_p1 else (opp_act, my_act)
                next_st, _ = resolve_combat_round(current_state_node.state, p1_act, p2_act)

                new_state_node = _MCTSStateNode(next_st, player_id, opponent_id)
                chosen_action_node.outcomes[opp_act] = new_state_node
                path_state_nodes.append(new_state_node)
                leaf_state = next_st
                break
            else:
                # All opponent replies expanded: sample an opponent outcome to descend deeper
                opp_actions_list = list(chosen_action_node.outcomes.keys())
                sampled_opp = rng.choice(opp_actions_list)
                next_node = chosen_action_node.outcomes[sampled_opp]
                current_state_node = next_node
                path_state_nodes.append(next_node)

        assert leaf_state is not None

        # Phase 3: Simulation (Rollout)
        reward = _simulate_rollout(
            start_state=leaf_state,
            player_id=player_id,
            opponent_id=opponent_id,
            config=cfg,
            rng=rng,
        )

        # Phase 4: Backpropagation
        for s_node in path_state_nodes:
            s_node.visits += 1
        for a_node in path_action_nodes:
            a_node.visits += 1
            a_node.total_reward += reward

        iterations_completed += 1

    # Select final action by highest visit count
    best_action = immediate_fallback
    best_visits = -1
    best_avg_reward = float("-inf")

    action_visits: Dict[Action, int] = {}
    action_rewards: Dict[Action, float] = {}

    for a in ordered_legal:
        act_node = root.children[a]
        v = act_node.visits
        r = act_node.average_reward
        action_visits[a] = v
        action_rewards[a] = r

        if v > best_visits:
            best_visits = v
            best_action = a
            best_avg_reward = r
        elif v == best_visits:
            # Tie-break 1: average reward
            if r > best_avg_reward + 1e-6:
                best_action = a
                best_avg_reward = r
            # Tie-break 2: canonical order preserved (ordered_legal iterates ORDERED_ACTIONS)

    elapsed_time = time.perf_counter() - start_time

    return CycloneDecision(
        action=best_action,
        iterations_completed=iterations_completed,
        eval_score=best_avg_reward,
        decision_time_seconds=elapsed_time,
        action_visits=action_visits,
        action_rewards=action_rewards,
        seed_used=cfg.seed,
    )


def choose_action(
    state: MatchState,
    player_id: str,
    config: Optional[CycloneConfig] = None,
    return_diagnostics: bool = False,
) -> Union[Action, Tuple[Action, CycloneDecision]]:
    """Common agent API returning a legal action, plus optional diagnostics.

    Args:
        state: Pre-round immutable MatchState.
        player_id: Acting player identifier ('player_1' or 'player_2').
        config: Optional CycloneConfig instance.
        return_diagnostics: If True, returns (action, decision). If False, returns action.

    Returns:
        Action enum member, or tuple of (Action, CycloneDecision).
    """
    decision = decide(state=state, player_id=player_id, config=config)
    if return_diagnostics:
        return decision.action, decision
    return decision.action


class CycloneAgent:
    """Stateful agent wrapper encapsulating player perspective and MCTS configuration."""

    def __init__(
        self,
        player_id: str,
        difficulty: CycloneDifficulty = CycloneDifficulty.MEDIUM,
        config: Optional[CycloneConfig] = None,
    ) -> None:
        self.player_id = player_id
        self.difficulty = difficulty
        self.config = config or CycloneConfig.for_difficulty(difficulty)

    def choose_action(
        self,
        state: MatchState,
        return_diagnostics: bool = False,
    ) -> Union[Action, Tuple[Action, CycloneDecision]]:
        """Choose a legal action for the configured player."""
        return choose_action(
            state=state,
            player_id=self.player_id,
            config=self.config,
            return_diagnostics=return_diagnostics,
        )

    def decide(self, state: MatchState) -> CycloneDecision:
        """Execute decision with full diagnostic telemetry."""
        return decide(
            state=state,
            player_id=self.player_id,
            config=self.config,
        )
