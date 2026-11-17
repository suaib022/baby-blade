"""Ironclad AI — Depth-limited Minimax search with iterative deepening.

This module implements the Ironclad AI agent using classical depth-limited
Minimax with explicit MAX/MIN roles, simultaneous-action conservatism,
and iterative deepening.

Search Model:
In BLADE ARENA, actions are chosen simultaneously and committed blindly:
- MAX (the acting agent) proposes an action a in legal_actions(S, player_id).
- MIN (the conservative opponent model) evaluates all legal counter-actions
  o in legal_actions(S, opponent_id).
- Each action pair is resolved using the production rules engine (`resolve_combat_round`).
- MIN selects the reply minimizing MAX's payoff:
  V(a) = min_{o} Minimax(S(a, o), depth - 1).
- MAX selects the action maximizing this guaranteed floor:
  a* = argmax_{a} V(a).
- Deterministic tie-breaking favors earlier actions in canonical ORDERED_ACTIONS.

Iterative Deepening:
- Explores depths 1..max_depth sequentially.
- If a node budget or deadline interrupts search, only the last fully completed
  depth's decision is retained.
- An immediate legal fallback is always guaranteed.
- Search operates exclusively on immutable snapshots and never inspects
  pending hidden opponent actions.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Optional, Tuple, Union

from blade_arena.game.actions import ORDERED_ACTIONS, legal_actions
from blade_arena.game.combat import resolve_combat_round
from blade_arena.game.heuristic import (
    DEFAULT_HEURISTIC_CONFIG,
    HeuristicConfig,
    evaluate_heuristic,
)
from blade_arena.game.match_controller import MatchFinishedError
from blade_arena.game.models import Action, MatchState, MatchStatus
from blade_arena.game.win_conditions import is_match_terminal


class IroncladDifficulty(str, Enum):
    """Preset difficulty configurations for Ironclad Minimax."""

    EASY = "easy"        # Depth 1 lookahead
    MEDIUM = "medium"    # Depth 2 lookahead
    HARD = "hard"        # Depth 3 lookahead


DIFFICULTY_DEPTHS: Dict[IroncladDifficulty, int] = {
    IroncladDifficulty.EASY: 1,
    IroncladDifficulty.MEDIUM: 2,
    IroncladDifficulty.HARD: 3,
}


@dataclass(frozen=True)
class IroncladConfig:
    """Configuration for Ironclad Minimax search.

    Attributes:
        max_depth: Maximum search depth in complete resolved rounds (1, 2, or 3).
        max_nodes: Optional node evaluation budget across iterative deepening.
        time_limit_seconds: Optional wall-clock search budget.
        enable_pruning: Whether to use conservative alpha-pruning in the MIN loop.
        heuristic_config: Configuration for the terminal and leaf evaluator.
    """

    max_depth: int = 2
    max_nodes: Optional[int] = None
    time_limit_seconds: Optional[float] = None
    enable_pruning: bool = True
    heuristic_config: HeuristicConfig = DEFAULT_HEURISTIC_CONFIG

    def __post_init__(self) -> None:
        if self.max_depth < 1:
            raise ValueError(f"max_depth must be at least 1, got {self.max_depth}")
        if self.max_nodes is not None and self.max_nodes < 1:
            raise ValueError(f"max_nodes must be at least 1, got {self.max_nodes}")
        if self.time_limit_seconds is not None and self.time_limit_seconds <= 0.0:
            raise ValueError("time_limit_seconds must be positive if specified")

    @classmethod
    def for_difficulty(
        cls,
        difficulty: Union[IroncladDifficulty, str] = IroncladDifficulty.MEDIUM,
        **kwargs,
    ) -> IroncladConfig:
        """Create a configuration tuned for a given difficulty preset."""
        diff_enum = IroncladDifficulty(difficulty)
        depth = DIFFICULTY_DEPTHS[diff_enum]
        return cls(max_depth=depth, **kwargs)


@dataclass(frozen=True)
class IroncladDecision:
    """Diagnostics and decision telemetry returned by Ironclad."""

    action: Action
    eval_score: float
    depth_completed: int
    nodes_evaluated: int
    decision_time_seconds: float
    action_scores: Dict[Action, float]


class _SearchInterrupted(Exception):
    """Internal exception raised when node budget or deadline is exceeded."""


class _SearchContext:
    """Internal mutable tracking context for node counts and deadlines."""

    def __init__(
        self,
        max_nodes: Optional[int],
        deadline: Optional[float],
    ) -> None:
        self.max_nodes = max_nodes
        self.deadline = deadline
        self.nodes_evaluated = 0

    def record_node(self) -> None:
        self.nodes_evaluated += 1
        if self.max_nodes is not None and self.nodes_evaluated > self.max_nodes:
            raise _SearchInterrupted("Node budget exceeded")
        if self.deadline is not None and time.perf_counter() >= self.deadline:
            raise _SearchInterrupted("Time deadline exceeded")


def _minimax_value(
    state: MatchState,
    depth: int,
    player_id: str,
    opponent_id: str,
    config: IroncladConfig,
    ctx: _SearchContext,
    alpha: float,
) -> float:
    """Evaluate non-root state using conservative worst-case Minimax."""
    ctx.record_node()

    # 1. Terminal State Check
    if state.status == MatchStatus.FINISHED or is_match_terminal(state):
        return evaluate_heuristic(state, player_id, config=config.heuristic_config)

    # 2. Depth Cutoff Check
    if depth <= 0:
        return evaluate_heuristic(state, player_id, config=config.heuristic_config)

    my_actions = legal_actions(state, player_id)
    opp_actions = legal_actions(state, opponent_id)

    if not my_actions:
        return evaluate_heuristic(state, player_id, config=config.heuristic_config)
    if not opp_actions:
        # Opponent has no legal actions (should be terminal, but safeguard)
        return evaluate_heuristic(state, player_id, config=config.heuristic_config)

    best_max_val = float("-inf")

    # Order actions deterministically using canonical ORDERED_ACTIONS
    ordered_my = [a for a in ORDERED_ACTIONS if a in my_actions]
    ordered_opp = [a for a in ORDERED_ACTIONS if a in opp_actions]

    is_p1 = player_id == state.player_1_blade.player_id

    for my_act in ordered_my:
        worst_opp_val = float("inf")

        for opp_act in ordered_opp:
            p1_act, p2_act = (my_act, opp_act) if is_p1 else (opp_act, my_act)
            next_state, _ = resolve_combat_round(state, p1_act, p2_act)

            sub_val = _minimax_value(
                state=next_state,
                depth=depth - 1,
                player_id=player_id,
                opponent_id=opponent_id,
                config=config,
                ctx=ctx,
                alpha=best_max_val,
            )

            if sub_val < worst_opp_val:
                worst_opp_val = sub_val

            # Conservative alpha-pruning in MIN loop
            if config.enable_pruning and worst_opp_val <= best_max_val:
                break

        if worst_opp_val > best_max_val + 1e-6:
            best_max_val = worst_opp_val

    return best_max_val


def _search_single_depth(
    state: MatchState,
    depth: int,
    player_id: str,
    opponent_id: str,
    config: IroncladConfig,
    ctx: _SearchContext,
) -> Tuple[Action, float, Dict[Action, float]]:
    """Execute complete root search at a single fixed depth."""
    my_actions = legal_actions(state, player_id)
    opp_actions = legal_actions(state, opponent_id)

    ordered_my = [a for a in ORDERED_ACTIONS if a in my_actions]
    ordered_opp = [a for a in ORDERED_ACTIONS if a in opp_actions]

    is_p1 = player_id == state.player_1_blade.player_id

    best_action = ordered_my[0]
    best_score = float("-inf")
    action_scores: Dict[Action, float] = {}

    for my_act in ordered_my:
        worst_opp_val = float("inf")

        for opp_act in ordered_opp:
            p1_act, p2_act = (my_act, opp_act) if is_p1 else (opp_act, my_act)
            next_state, _ = resolve_combat_round(state, p1_act, p2_act)

            if next_state.status == MatchStatus.FINISHED or is_match_terminal(next_state) or depth == 1:
                ctx.record_node()
                val = evaluate_heuristic(next_state, player_id, config=config.heuristic_config)
            else:
                val = _minimax_value(
                    state=next_state,
                    depth=depth - 1,
                    player_id=player_id,
                    opponent_id=opponent_id,
                    config=config,
                    ctx=ctx,
                    alpha=best_score,
                )

            if val < worst_opp_val:
                worst_opp_val = val

            # Alpha pruning at root
            if config.enable_pruning and worst_opp_val <= best_score:
                break

        action_scores[my_act] = worst_opp_val

        # Deterministic tie-breaking: strictly greater by 1e-6 to override earlier action
        if worst_opp_val > best_score + 1e-6:
            best_score = worst_opp_val
            best_action = my_act

    return best_action, best_score, action_scores


def decide(
    state: MatchState,
    player_id: str,
    config: Optional[IroncladConfig] = None,
) -> IroncladDecision:
    """Execute depth-limited Minimax with iterative deepening from a player's perspective.

    Args:
        state: Pre-round immutable MatchState.
        player_id: Acting player identifier ('player_1' or 'player_2').
        config: Optional IroncladConfig instance (defaults to Medium difficulty).

    Returns:
        IroncladDecision containing chosen action, evaluation score, and telemetry.

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

    # Reject requests on finished or terminal states
    if state.status == MatchStatus.FINISHED or is_match_terminal(state):
        raise MatchFinishedError("Cannot choose an action: the match is already finished.")

    my_actions = legal_actions(state, player_id)
    if not my_actions:
        raise MatchFinishedError("No legal actions available for player.")

    cfg = config or IroncladConfig()

    deadline = (start_time + cfg.time_limit_seconds) if cfg.time_limit_seconds is not None else None
    ctx = _SearchContext(max_nodes=cfg.max_nodes, deadline=deadline)

    # Immediate fallback guarantee before depth 1
    ordered_legal = [a for a in ORDERED_ACTIONS if a in my_actions]
    best_action: Action = ordered_legal[0]
    best_score: float = 0.0
    action_scores: Dict[Action, float] = {a: 0.0 for a in ordered_legal}
    depth_completed = 0

    # Iterative Deepening: 1..max_depth
    for d in range(1, cfg.max_depth + 1):
        try:
            depth_act, depth_score, depth_action_scores = _search_single_depth(
                state=state,
                depth=d,
                player_id=player_id,
                opponent_id=opponent_id,
                config=cfg,
                ctx=ctx,
            )
            # Retain only fully completed iterations
            best_action = depth_act
            best_score = depth_score
            action_scores = depth_action_scores
            depth_completed = d

            # Early cutoff if proven winning terminal utility is achieved at depth d
            if best_score >= cfg.heuristic_config.terminal_win_score - 1e-6:
                break

        except _SearchInterrupted:
            # Budget exceeded: retain results from last fully completed depth
            break

    elapsed_time = time.perf_counter() - start_time

    return IroncladDecision(
        action=best_action,
        eval_score=best_score,
        depth_completed=depth_completed,
        nodes_evaluated=ctx.nodes_evaluated,
        decision_time_seconds=elapsed_time,
        action_scores=action_scores,
    )


def choose_action(
    state: MatchState,
    player_id: str,
    config: Optional[IroncladConfig] = None,
    return_diagnostics: bool = False,
) -> Union[Action, Tuple[Action, IroncladDecision]]:
    """Common agent API returning a legal action, plus optional diagnostics.

    Args:
        state: Pre-round immutable MatchState.
        player_id: Acting player identifier ('player_1' or 'player_2').
        config: Optional IroncladConfig instance.
        return_diagnostics: If True, returns (action, decision). If False, returns action.

    Returns:
        Action enum member, or tuple of (Action, IroncladDecision).
    """
    decision = decide(state=state, player_id=player_id, config=config)
    if return_diagnostics:
        return decision.action, decision
    return decision.action


class IroncladAgent:
    """Stateful agent wrapper encapsulating player perspective and configuration."""

    def __init__(
        self,
        player_id: str,
        difficulty: IroncladDifficulty = IroncladDifficulty.MEDIUM,
        config: Optional[IroncladConfig] = None,
    ) -> None:
        self.player_id = player_id
        self.difficulty = difficulty
        self.config = config or IroncladConfig.for_difficulty(difficulty)

    def choose_action(
        self,
        state: MatchState,
        return_diagnostics: bool = False,
    ) -> Union[Action, Tuple[Action, IroncladDecision]]:
        """Choose a legal action for the configured player."""
        return choose_action(
            state=state,
            player_id=self.player_id,
            config=self.config,
            return_diagnostics=return_diagnostics,
        )

    def decide(self, state: MatchState) -> IroncladDecision:
        """Execute decision with full diagnostic telemetry."""
        return decide(
            state=state,
            player_id=self.player_id,
            config=self.config,
        )
