"""Shared AI heuristic evaluation function for BLADE ARENA.

This module provides a pure-Python state evaluation function used by both
Ironclad (Minimax in Module 11) and Cyclone (MCTS in Module 12) agents.

Evaluation Principles:
1. Perspective-aware zero-sum formulation:
   `score(state, P1) == -score(state, P2)`.
2. Absolute dominance of terminal utility:
   Terminal states return +100.0 (Win), -100.0 (Loss), or 0.0 (Draw),
   strictly dominating all nonterminal scores (which lie in [-1.0, +1.0]).
3. Multi-factor blade evaluation:
   `blade_value = 0.30*energy_ratio + 0.30*stability_ratio + 0.20*position_safety
                  + 0.05*special_availability - 0.15*danger_ratio`.
4. MCTS rollout reward scaling:
   Nonterminal values are bounded to [-0.85, +0.85] to ensure rollouts never
   outrank actual terminal win/loss outcomes (+1.0 / -1.0).
5. Comprehensive explainability breakdown:
   Returns fine-grained telemetry without requiring recomputation.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

from blade_arena.game.actions import is_action_legal
from blade_arena.game.fuzzy_danger import (
    DEFAULT_FUZZY_CONFIG,
    FuzzyDangerConfig,
    evaluate_blade_danger,
)
from blade_arena.game.geometry import distance_from_center
from blade_arena.game.models import (
    Action,
    BladeState,
    MatchResult,
    MatchState,
    MatchStatus,
)
from blade_arena.game.win_conditions import evaluate_match_termination


@dataclass(frozen=True)
class HeuristicConfig:
    """Centralized, immutable configuration for AI heuristic evaluation.

    All component weights and terminal utilities are proposed calibrations
    designed for stable adversarial search and tree exploration.
    """

    # Proposed blade evaluation weights
    weight_energy: float = 0.30
    weight_stability: float = 0.30
    weight_position: float = 0.20
    weight_special: float = 0.05
    weight_danger: float = 0.15

    # Terminal utility scores
    terminal_win_score: float = 100.0
    terminal_loss_score: float = -100.0
    terminal_draw_score: float = 0.0

    # MCTS normalized rollout rewards
    mcts_terminal_win_reward: float = 1.0
    mcts_terminal_loss_reward: float = -1.0
    mcts_terminal_draw_reward: float = 0.0
    mcts_max_nonterminal_magnitude: float = 0.85

    # Fuzzy danger configuration
    fuzzy_config: FuzzyDangerConfig = DEFAULT_FUZZY_CONFIG

    def __post_init__(self) -> None:
        if self.terminal_win_score <= 0.0 or self.terminal_loss_score >= 0.0:
            raise ValueError("terminal_win_score must be positive and terminal_loss_score negative")
        if not (0.0 < self.mcts_max_nonterminal_magnitude < 1.0):
            raise ValueError("mcts_max_nonterminal_magnitude must be strictly within (0.0, 1.0)")


DEFAULT_HEURISTIC_CONFIG = HeuristicConfig()


@dataclass(frozen=True)
class BladeEvaluationBreakdown:
    """Detailed feature breakdown for a single blade evaluation.

    Attributes:
        energy_ratio: Normalized energy in [0.0, 1.0].
        stability_ratio: Normalized stability in [0.0, 1.0].
        position_safety: Center proximity clamp(1 - d/r, 0, 1) in [0.0, 1.0].
        special_availability: 1.0 if Special Spin is currently legal, else 0.0.
        danger_ratio: Mamdani fuzzy danger score / 100.0 in [0.0, 1.0].
        blade_value: Weighted combination of the above components.
        weighted_components: Dictionary mapping feature names to weighted contributions.
    """

    energy_ratio: float
    stability_ratio: float
    position_safety: float
    special_availability: float
    danger_ratio: float
    blade_value: float
    weighted_components: Dict[str, float]


@dataclass(frozen=True)
class EvaluationResult:
    """Immutable outcome of evaluating a match state from a player's perspective.

    Attributes:
        score: Minimax evaluation score in [-100.0, +100.0].
        mcts_reward: Bounded rollout reward in [-1.0, +1.0].
        is_terminal: True if the state is terminal (game over).
        perspective_player: Player ID whose perspective this evaluation reflects.
        opponent_player: Opponent player ID.
        own_blade_value: Raw blade value of the perspective player.
        opponent_blade_value: Raw blade value of the opponent.
        own_breakdown: Detailed breakdown for own blade (None if terminal knockout).
        opponent_breakdown: Detailed breakdown for opponent blade (None if terminal knockout).
    """

    score: float
    mcts_reward: float
    is_terminal: bool
    perspective_player: str
    opponent_player: str
    own_blade_value: float
    opponent_blade_value: float
    own_breakdown: Optional[BladeEvaluationBreakdown] = None
    opponent_breakdown: Optional[BladeEvaluationBreakdown] = None


def evaluate_blade_components(
    blade: BladeState,
    stadium_radius: float,
    is_special_legal: bool,
    config: HeuristicConfig = DEFAULT_HEURISTIC_CONFIG,
) -> BladeEvaluationBreakdown:
    """Compute normalized components and composite value for a single blade.

    Formula:
        blade_value = (weight_energy * energy_ratio)
                    + (weight_stability * stability_ratio)
                    + (weight_position * position_safety)
                    + (weight_special * special_availability)
                    - (weight_danger * danger_ratio)

    Args:
        blade: Immutable BladeState instance.
        stadium_radius: Current radius of the circular stadium.
        is_special_legal: Boolean flag indicating if Special Spin can be legally chosen.
        config: HeuristicConfig instance.

    Returns:
        BladeEvaluationBreakdown containing raw ratios, weighted values, and composite score.
    """
    # 1. Energy Ratio: clamp(current / max, 0, 1)
    energy = getattr(blade, "current_energy", getattr(blade, "energy", 0.0))
    max_energy = getattr(blade, "max_energy", getattr(blade, "maximum_energy", 100.0))
    energy_ratio = max(0.0, min(1.0, energy / max_energy)) if max_energy > 0.0 else 0.0

    # 2. Stability Ratio: clamp(current / max, 0, 1)
    stability = getattr(blade, "current_stability", getattr(blade, "stability", 0.0))
    max_stability = getattr(blade, "max_stability", getattr(blade, "maximum_stability", 100.0))
    stability_ratio = max(0.0, min(1.0, stability / max_stability)) if max_stability > 0.0 else 0.0

    # 3. Position Safety: clamp(1 - distance / radius, 0, 1)
    dist = distance_from_center(blade.position)
    position_safety = max(0.0, min(1.0, 1.0 - (dist / stadium_radius))) if stadium_radius > 0.0 else 0.0

    # 4. Special Spin Availability: 1.0 if legal, 0.0 otherwise
    special_availability = 1.0 if is_special_legal else 0.0

    # 5. Fuzzy Danger Ratio: score / 100.0 in [0.0, 1.0]
    danger_eval = evaluate_blade_danger(blade, stadium_radius, config=config.fuzzy_config)
    danger_ratio = danger_eval.score / 100.0

    # Weighted components
    w_energy = config.weight_energy * energy_ratio
    w_stability = config.weight_stability * stability_ratio
    w_pos = config.weight_position * position_safety
    w_special = config.weight_special * special_availability
    w_danger = config.weight_danger * danger_ratio

    blade_value = w_energy + w_stability + w_pos + w_special - w_danger

    weighted_components = {
        "energy": w_energy,
        "stability": w_stability,
        "position": w_pos,
        "special": w_special,
        "danger_penalty": -w_danger,
    }

    return BladeEvaluationBreakdown(
        energy_ratio=energy_ratio,
        stability_ratio=stability_ratio,
        position_safety=position_safety,
        special_availability=special_availability,
        danger_ratio=danger_ratio,
        blade_value=blade_value,
        weighted_components=weighted_components,
    )


def evaluate_state(
    state: MatchState,
    player_id: str,
    config: Optional[HeuristicConfig] = None,
) -> EvaluationResult:
    """Evaluate a MatchState from the perspective of a specific player.

    Pure function executing perspective-aware evaluation:
    1. Validates that player_id belongs to the match.
    2. Identifies terminal conditions (either recorded in state or via win evaluator).
    3. If terminal: returns +100.0 for win, -100.0 for loss, 0.0 for draw.
    4. If nonterminal: evaluates blade components for both players and computes
       `score = own_blade_value - opponent_blade_value`.
    5. Computes bounded MCTS rollout reward in [-0.85, +0.85] ensuring terminal
       outcomes (+1.0 / -1.0) strictly dominate nonterminal states.

    Args:
        state: Pre-round or post-round immutable MatchState.
        player_id: Identifier of the perspective player ('player_1' or 'player_2').
        config: Optional HeuristicConfig instance.

    Returns:
        EvaluationResult containing score, MCTS reward, terminal status, and breakdowns.

    Raises:
        TypeError: If state or player_id has an invalid type.
        ValueError: If player_id does not belong to the match.
    """
    if not isinstance(state, MatchState):
        raise TypeError(f"state must be a MatchState instance, got {type(state).__name__}")
    if not isinstance(player_id, str):
        raise TypeError(f"player_id must be a string, got {type(player_id).__name__}")

    p1_id = state.player_1_blade.player_id
    p2_id = state.player_2_blade.player_id

    if player_id == p1_id:
        own_blade = state.player_1_blade
        opp_blade = state.player_2_blade
        opp_id = p2_id
    elif player_id == p2_id:
        own_blade = state.player_2_blade
        opp_blade = state.player_1_blade
        opp_id = p1_id
    else:
        raise ValueError(
            f"Unknown player_id '{player_id}'. Must be '{p1_id}' or '{p2_id}'."
        )

    cfg = config or DEFAULT_HEURISTIC_CONFIG

    # Check for terminal status
    # 1. Explicit finished status on MatchState
    is_terminal = False
    result: Optional[MatchResult] = None

    if state.status == MatchStatus.FINISHED and state.result is not None:
        is_terminal = True
        result = state.result
    else:
        # 2. Check if the current state satisfies terminal win conditions
        terminal_eval = evaluate_match_termination(state)
        if terminal_eval is not None:
            is_terminal = True
            result = terminal_eval

    # Case A: Terminal State Evaluation
    if is_terminal and result is not None:
        if result.winner == player_id:
            score = cfg.terminal_win_score
            mcts_reward = cfg.mcts_terminal_win_reward
        elif result.winner == opp_id:
            score = cfg.terminal_loss_score
            mcts_reward = cfg.mcts_terminal_loss_reward
        else:
            # Draw
            score = cfg.terminal_draw_score
            mcts_reward = cfg.mcts_terminal_draw_reward

        return EvaluationResult(
            score=score,
            mcts_reward=mcts_reward,
            is_terminal=True,
            perspective_player=player_id,
            opponent_player=opp_id,
            own_blade_value=score,
            opponent_blade_value=-score,
            own_breakdown=None,
            opponent_breakdown=None,
        )

    # Case B: Nonterminal State Evaluation
    radius = state.stadium.radius

    # Determine special spin legality for both players
    own_special_legal = is_action_legal(state, player_id, Action.SPECIAL_SPIN)
    opp_special_legal = is_action_legal(state, opp_id, Action.SPECIAL_SPIN)

    own_breakdown = evaluate_blade_components(own_blade, radius, own_special_legal, config=cfg)
    opp_breakdown = evaluate_blade_components(opp_blade, radius, opp_special_legal, config=cfg)

    # Perspective score: own value minus opponent value
    score = own_breakdown.blade_value - opp_breakdown.blade_value

    # MCTS bounded rollout scaling: clamp nonterminal score into [-max_mag, +max_mag]
    max_mag = cfg.mcts_max_nonterminal_magnitude
    mcts_reward = max(-max_mag, min(max_mag, score))

    return EvaluationResult(
        score=score,
        mcts_reward=mcts_reward,
        is_terminal=False,
        perspective_player=player_id,
        opponent_player=opp_id,
        own_blade_value=own_breakdown.blade_value,
        opponent_blade_value=opp_breakdown.blade_value,
        own_breakdown=own_breakdown,
        opponent_breakdown=opp_breakdown,
    )


def evaluate_heuristic(
    state: MatchState,
    player_id: str,
    config: Optional[HeuristicConfig] = None,
) -> float:
    """Convenience evaluator returning the raw minimax heuristic score as a float.

    Args:
        state: MatchState instance.
        player_id: Player ID from whose perspective the score is calculated.
        config: Optional HeuristicConfig instance.

    Returns:
        Heuristic score in [-100.0, +100.0].
    """
    return evaluate_state(state, player_id, config=config).score
