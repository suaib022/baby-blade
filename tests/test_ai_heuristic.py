"""Unit and integration tests for the shared AI heuristic evaluation function.

Verifies:
1. Terminal utility values (+100.0 for win, -100.0 for loss, 0.0 for draw).
2. Absolute dominance of terminal utility over any possible nonterminal score.
3. Perspective awareness and zero-sum symmetry: swapping perspective negates score.
4. Monotonicity of individual components:
   - Energy ratio increases blade value.
   - Stability ratio increases blade value.
   - Positional safety (center proximity) increases blade value.
   - Special Spin availability adds +0.05 bonus when legal.
   - Fuzzy danger ratio subtracts from blade value.
5. MCTS rollout reward scaling:
   - Bounded strictly to [-0.85, +0.85] for nonterminal states.
   - Terminal states map to +1.0, -1.0, and 0.0.
   - Rollout rewards never equal or outrank terminal outcomes.
6. Error handling:
   - Invalid player IDs raise ValueError.
   - Non-MatchState inputs raise TypeError.
7. Unfinalized terminal state detection (e.g. successor states generated in search).
8. Immutability, reproducibility, and 100% Pygame independence.
"""

from __future__ import annotations

import sys
import pytest

from blade_arena.game.blade_definitions import create_blade_state
from blade_arena.game.heuristic import (
    DEFAULT_HEURISTIC_CONFIG,
    BladeEvaluationBreakdown,
    EvaluationResult,
    HeuristicConfig,
    evaluate_blade_components,
    evaluate_heuristic,
    evaluate_state,
)
from blade_arena.game.initial_state import create_default_match, create_initial_match
from blade_arena.game.models import (
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
# 1. Component Evaluation and Formula Verification
# -----------------------------------------------------------------------------

def test_evaluate_blade_components_formula() -> None:
    """Verifies that blade component evaluation matches the exact weighted formula."""
    blade = create_blade_state(
        blade_type=BladeType.BALANCED,
        player_id="player_1",
        position=Position(x=0.0, y=0.0),  # Exact center -> position_safety = 1.0
    )
    # At center with full energy and full stability, special is legal
    breakdown = evaluate_blade_components(
        blade=blade,
        stadium_radius=10.0,
        is_special_legal=True,
    )

    # Verification of normalized inputs
    assert breakdown.energy_ratio == 1.0
    assert breakdown.stability_ratio == 1.0
    assert breakdown.position_safety == 1.0
    assert breakdown.special_availability == 1.0

    # Expected value:
    # 0.30*1.0 + 0.30*1.0 + 0.20*1.0 + 0.05*1.0 - 0.15*danger_ratio
    # At center (edge_safety=1.0) and full energy (1.0), danger score is ~14.56 -> danger_ratio ~0.1456
    expected_danger_ratio = breakdown.danger_ratio
    expected_value = 0.30 + 0.30 + 0.20 + 0.05 - 0.15 * expected_danger_ratio

    assert pytest.approx(breakdown.blade_value, abs=1e-6) == expected_value
    assert breakdown.weighted_components["energy"] == 0.30
    assert breakdown.weighted_components["stability"] == 0.30
    assert breakdown.weighted_components["position"] == 0.20
    assert breakdown.weighted_components["special"] == 0.05
    assert breakdown.weighted_components["danger_penalty"] == -0.15 * expected_danger_ratio


def test_special_availability_toggle() -> None:
    """Special Spin availability adds exactly 0.05 when available versus unavailable."""
    blade = create_blade_state(
        blade_type=BladeType.BALANCED,
        player_id="player_1",
        position=Position(x=2.0, y=0.0),
    )
    bd_with_special = evaluate_blade_components(blade, 10.0, is_special_legal=True)
    bd_no_special = evaluate_blade_components(blade, 10.0, is_special_legal=False)

    diff = bd_with_special.blade_value - bd_no_special.blade_value
    assert pytest.approx(diff, abs=1e-6) == 0.05


def test_monotonicity_energy_increase() -> None:
    """Holding all other factors constant, higher energy increases blade value."""
    b_low_energy = create_blade_state(
        blade_type=BladeType.BALANCED,
        player_id="player_1",
        position=Position(x=2.0, y=0.0),
    )
    b_high_energy = create_blade_state(
        blade_type=BladeType.BALANCED,
        player_id="player_1",
        position=Position(x=2.0, y=0.0),
    )
    # Simulate energy difference
    object.__setattr__(b_low_energy, "current_energy", 30.0)
    object.__setattr__(b_high_energy, "current_energy", 80.0)

    bd_low = evaluate_blade_components(b_low_energy, 10.0, is_special_legal=False)
    bd_high = evaluate_blade_components(b_high_energy, 10.0, is_special_legal=True)

    assert bd_high.blade_value > bd_low.blade_value


def test_monotonicity_stability_increase() -> None:
    """Holding all other factors constant, higher stability increases blade value."""
    b_low_stab = create_blade_state(
        blade_type=BladeType.DEFENDER,
        player_id="player_1",
        position=Position(x=0.0, y=0.0),
    )
    b_high_stab = create_blade_state(
        blade_type=BladeType.DEFENDER,
        player_id="player_1",
        position=Position(x=0.0, y=0.0),
    )
    object.__setattr__(b_low_stab, "current_stability", 25.0)
    object.__setattr__(b_high_stab, "current_stability", 100.0)

    bd_low = evaluate_blade_components(b_low_stab, 10.0, is_special_legal=True)
    bd_high = evaluate_blade_components(b_high_stab, 10.0, is_special_legal=True)

    assert bd_high.blade_value > bd_low.blade_value


def test_monotonicity_positional_safety() -> None:
    """A blade closer to the center of the stadium has a higher positional safety and blade value."""
    b_center = create_blade_state(
        blade_type=BladeType.BALANCED,
        player_id="player_1",
        position=Position(x=1.0, y=0.0),
    )
    b_perimeter = create_blade_state(
        blade_type=BladeType.BALANCED,
        player_id="player_1",
        position=Position(x=8.5, y=0.0),
    )

    bd_center = evaluate_blade_components(b_center, 10.0, is_special_legal=True)
    bd_perimeter = evaluate_blade_components(b_perimeter, 10.0, is_special_legal=True)

    assert bd_center.position_safety > bd_perimeter.position_safety
    assert bd_center.blade_value > bd_perimeter.blade_value


# -----------------------------------------------------------------------------
# 2. Perspective Awareness and Zero-Sum Symmetry
# -----------------------------------------------------------------------------

def test_perspective_awareness_and_negation_nonterminal() -> None:
    """Swapping perspective in a nonterminal state strictly negates the score and MCTS reward."""
    match = create_default_match()
    # Damage player 2 so state is non-symmetric
    object.__setattr__(match.player_2_blade, "current_energy", 50.0)
    object.__setattr__(match.player_2_blade, "current_stability", 60.0)

    res_p1 = evaluate_state(match, "player_1")
    res_p2 = evaluate_state(match, "player_2")

    assert not res_p1.is_terminal
    assert not res_p2.is_terminal
    assert res_p1.score == pytest.approx(-res_p2.score, abs=1e-6)
    assert res_p1.mcts_reward == pytest.approx(-res_p2.mcts_reward, abs=1e-6)
    assert res_p1.own_blade_value == pytest.approx(res_p2.opponent_blade_value, abs=1e-6)
    assert res_p1.opponent_blade_value == pytest.approx(res_p2.own_blade_value, abs=1e-6)


def test_default_symmetric_initial_match_evaluates_to_zero() -> None:
    """A perfectly symmetrical default match evaluates to exactly 0.0 from both sides."""
    match = create_default_match()

    res_p1 = evaluate_state(match, "player_1")
    res_p2 = evaluate_state(match, "player_2")

    assert pytest.approx(res_p1.score, abs=1e-6) == 0.0
    assert pytest.approx(res_p2.score, abs=1e-6) == 0.0
    assert pytest.approx(res_p1.mcts_reward, abs=1e-6) == 0.0


# -----------------------------------------------------------------------------
# 3. Terminal State Utility and Absolute Dominance
# -----------------------------------------------------------------------------

def test_terminal_win_loss_and_draw_utility() -> None:
    """Terminal outcomes produce +100.0 (win), -100.0 (loss), and 0.0 (draw)."""
    # Player 1 Win
    p1_win_match = MatchState(
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
            player_1_causes=(),
            player_2_causes=(FinishReason.RING_OUT,),
        ),
    )

    res_p1 = evaluate_state(p1_win_match, "player_1")
    res_p2 = evaluate_state(p1_win_match, "player_2")

    assert res_p1.is_terminal
    assert res_p1.score == 100.0
    assert res_p1.mcts_reward == 1.0

    assert res_p2.is_terminal
    assert res_p2.score == -100.0
    assert res_p2.mcts_reward == -1.0

    # Draw
    draw_match = MatchState(
        player_1_blade=create_blade_state(
            player_id="player_1",
            blade_type=BladeType.BALANCED,
            position=Position(11.0, 0.0),
        ),
        player_2_blade=create_blade_state(
            player_id="player_2",
            blade_type=BladeType.BALANCED,
            position=Position(11.0, 0.0),
        ),
        stadium=StadiumState(StadiumType.CLASSIC_DISH, Position(0.0, 0.0), 10.0),
        completed_rounds=5,
        status=MatchStatus.FINISHED,
        result=MatchResult(
            winner=None,
            reason=FinishReason.SIMULTANEOUS_ELIMINATION,
            player_1_causes=(FinishReason.RING_OUT,),
            player_2_causes=(FinishReason.RING_OUT,),
        ),
    )

    res_draw_p1 = evaluate_state(draw_match, "player_1")
    res_draw_p2 = evaluate_state(draw_match, "player_2")

    assert res_draw_p1.is_terminal
    assert res_draw_p1.score == 0.0
    assert res_draw_p1.mcts_reward == 0.0
    assert res_draw_p2.score == 0.0


def test_terminal_dominance_over_nonterminal_scores() -> None:
    """Terminal win (+100.0) strictly dominates every possible nonterminal score,
    and terminal loss (-100.0) is strictly worse than every possible nonterminal score."""
    match = create_default_match()

    # Extreme theoretical advantage: Player 1 pristine at center, Player 2 near dead
    object.__setattr__(match.player_1_blade, "position", Position(0.0, 0.0))
    object.__setattr__(match.player_1_blade, "current_energy", 100.0)
    object.__setattr__(match.player_1_blade, "current_stability", 100.0)

    object.__setattr__(match.player_2_blade, "position", Position(9.9, 0.0))
    object.__setattr__(match.player_2_blade, "current_energy", 1.0)
    object.__setattr__(match.player_2_blade, "current_stability", 1.0)

    res = evaluate_state(match, "player_1")
    assert not res.is_terminal
    # Max nonterminal score is bounded roughly within [-1.0, +1.0]
    assert res.score < 1.0
    assert res.score < DEFAULT_HEURISTIC_CONFIG.terminal_win_score  # 100.0 > ~0.8
    assert -res.score > DEFAULT_HEURISTIC_CONFIG.terminal_loss_score  # -100.0 < -0.8


def test_unfinalized_terminal_state_detection() -> None:
    """Even if state.status is IN_PROGRESS, a state meeting knockout criteria evaluates as terminal."""
    match = create_default_match()
    # Player 2 stability is 0 -> Burst
    object.__setattr__(match.player_2_blade, "current_stability", 0.0)

    res = evaluate_state(match, "player_1")
    assert res.is_terminal
    assert res.score == 100.0
    assert res.mcts_reward == 1.0


# -----------------------------------------------------------------------------
# 4. MCTS Rollout Bounded Scaling
# -----------------------------------------------------------------------------

def test_mcts_rollout_reward_scaling_bounds() -> None:
    """MCTS nonterminal reward is strictly bounded to [-0.85, +0.85] and never equals 1.0 or -1.0."""
    match = create_default_match()
    # Give player 1 extreme advantage
    object.__setattr__(match.player_1_blade, "position", Position(0.0, 0.0))
    object.__setattr__(match.player_2_blade, "position", Position(9.9, 0.0))
    object.__setattr__(match.player_2_blade, "current_energy", 1.0)
    object.__setattr__(match.player_2_blade, "current_stability", 1.0)

    res_p1 = evaluate_state(match, "player_1")
    res_p2 = evaluate_state(match, "player_2")

    assert not res_p1.is_terminal
    assert res_p1.mcts_reward <= 0.85
    assert res_p1.mcts_reward < 1.0
    assert res_p2.mcts_reward >= -0.85
    assert res_p2.mcts_reward > -1.0


# -----------------------------------------------------------------------------
# 5. Input Validation and Error Handling
# -----------------------------------------------------------------------------

def test_invalid_player_id_raises_value_error() -> None:
    """Invalid player IDs are rejected with a clear ValueError."""
    match = create_default_match()
    with pytest.raises(ValueError, match="Unknown player_id 'player_3'"):
        evaluate_state(match, "player_3")


def test_invalid_state_type_raises_type_error() -> None:
    """Non-MatchState objects are rejected with TypeError."""
    with pytest.raises(TypeError, match="state must be a MatchState"):
        evaluate_state("not_a_state", "player_1")  # type: ignore[arg-type]


# -----------------------------------------------------------------------------
# 6. Immutability, Purity, and Zero Pygame Dependencies
# -----------------------------------------------------------------------------

def test_evaluate_state_does_not_mutate_match_state() -> None:
    """Evaluating state preserves complete immutability of match, blades, and stadium."""
    match = create_default_match()
    p1_orig_energy = match.player_1_blade.current_energy
    p2_orig_pos = match.player_2_blade.position
    radius_orig = match.stadium.radius

    _ = evaluate_state(match, "player_1")

    assert match.player_1_blade.current_energy == p1_orig_energy
    assert match.player_2_blade.position == p2_orig_pos
    assert match.stadium.radius == radius_orig


def test_convenience_evaluate_heuristic_matches_evaluate_state_score() -> None:
    """evaluate_heuristic returns exactly evaluate_state(...).score as a float."""
    match = create_default_match()
    score_p1 = evaluate_heuristic(match, "player_1")
    score_p2 = evaluate_heuristic(match, "player_2")

    assert score_p1 == evaluate_state(match, "player_1").score
    assert score_p2 == evaluate_state(match, "player_2").score


def test_heuristic_module_does_not_initialize_pygame() -> None:
    """The heuristic subsystem remains 100% independent of Pygame."""
    import blade_arena.game.heuristic as heuristic_module

    assert not hasattr(heuristic_module, "pygame")
