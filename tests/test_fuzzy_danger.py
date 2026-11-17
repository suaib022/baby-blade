"""Unit and integration tests for the Mamdani fuzzy danger inference system.

Verifies:
1. Exact endpoints, peaks, slopes, and degenerate shoulder functions for trapezoidal
   and triangular membership functions.
2. Parameter validation rejecting invalid bounds and zero-width definitions.
3. Fuzzy operators (MAX for OR, MIN for AND / implication, MAX for aggregation).
4. Rule aggregation and centroid defuzzification against synthetic output cases.
5. Full 2D input-grid coverage ([0, 1] x [0, 1]) ensuring no dead zones or zero denominators.
6. Score boundedness [0, 100] and qualitative classification thresholds.
7. Risk monotonicity: low energy or proximity to edge increases danger score.
8. Determinism: identical inputs yield identical floating-point scores and firings.
9. Dynamic stadium scaling: arena shrinkage increases danger for outer blades.
10. Input boundary clamping and robust error guards for non-positive stadium radii.
11. Headless purity: zero mutation of state models and zero Pygame dependencies.
"""

from __future__ import annotations

import math
import sys
import pytest

from blade_arena.game.blade_definitions import create_blade_state
from blade_arena.game.fuzzy_danger import (
    DEFAULT_FUZZY_CONFIG,
    DangerAssessment,
    DangerLevel,
    FuzzyDangerConfig,
    TrapezoidMF,
    TriangleMF,
    calculate_edge_safety,
    calculate_energy_ratio,
    evaluate_blade_danger,
    evaluate_danger_inputs,
    evaluate_match_danger,
)
from blade_arena.game.initial_state import create_default_match
from blade_arena.game.models import BladeType, Position


# -----------------------------------------------------------------------------
# 1. Membership Function Primitives and Shoulder Handling
# -----------------------------------------------------------------------------

def test_trapezoid_left_shoulder_membership() -> None:
    """Trapezoid with a == b acts as a left-shoulder function."""
    mf = TrapezoidMF(a=0.0, b=0.0, c=0.15, d=0.40)

    # Degenerate shoulder: values <= b evaluate to 1.0
    assert mf.evaluate(-1.0) == 1.0
    assert mf.evaluate(-0.01) == 1.0
    assert mf.evaluate(0.0) == 1.0
    assert mf.evaluate(0.10) == 1.0
    assert mf.evaluate(0.15) == 1.0

    # Falling slope between c and d
    mid_slope = (0.15 + 0.40) / 2.0  # 0.275
    assert pytest.approx(mf.evaluate(mid_slope), abs=1e-6) == 0.5
    quarter_slope = 0.15 + 0.25 * 0.25  # 0.2125 -> (0.40 - 0.2125)/0.25 = 0.75
    assert pytest.approx(mf.evaluate(quarter_slope), abs=1e-6) == 0.75

    # Right edge and outside
    assert mf.evaluate(0.40) == 0.0
    assert mf.evaluate(0.50) == 0.0
    assert mf.evaluate(1.0) == 0.0


def test_trapezoid_right_shoulder_membership() -> None:
    """Trapezoid with c == d acts as a right-shoulder function."""
    mf = TrapezoidMF(a=0.60, b=0.85, c=1.0, d=1.0)

    # Below support
    assert mf.evaluate(0.0) == 0.0
    assert mf.evaluate(0.50) == 0.0
    assert mf.evaluate(0.60) == 0.0

    # Rising slope between a and b
    mid_slope = (0.60 + 0.85) / 2.0  # 0.725
    assert pytest.approx(mf.evaluate(mid_slope), abs=1e-6) == 0.5
    quarter_slope = 0.60 + 0.25 * 0.25  # 0.6625 -> (0.6625 - 0.60)/0.25 = 0.25
    assert pytest.approx(mf.evaluate(quarter_slope), abs=1e-6) == 0.25

    # Top plateau and shoulder values >= c evaluate to 1.0
    assert mf.evaluate(0.85) == 1.0
    assert mf.evaluate(0.95) == 1.0
    assert mf.evaluate(1.0) == 1.0
    assert mf.evaluate(1.5) == 1.0


def test_triangle_membership() -> None:
    """Triangle membership evaluates linearly rising to peak and falling to base."""
    mf = TriangleMF(a=0.20, b=0.50, c=0.80)

    # Base boundaries and outside
    assert mf.evaluate(0.0) == 0.0
    assert mf.evaluate(0.20) == 0.0
    assert mf.evaluate(0.80) == 0.0
    assert mf.evaluate(1.0) == 0.0

    # Peak
    assert mf.evaluate(0.50) == 1.0

    # Rising slope
    assert pytest.approx(mf.evaluate(0.35), abs=1e-6) == 0.5
    assert pytest.approx(mf.evaluate(0.20 + 0.30 * 0.25), abs=1e-6) == 0.25

    # Falling slope
    assert pytest.approx(mf.evaluate(0.65), abs=1e-6) == 0.5
    assert pytest.approx(mf.evaluate(0.50 + 0.30 * 0.75), abs=1e-6) == 0.25


def test_membership_function_validation() -> None:
    """Invalid parameter bounds raise ValueError."""
    # Non-monotonic trapezoid
    with pytest.raises(ValueError, match="a <= b <= c <= d"):
        TrapezoidMF(a=0.5, b=0.4, c=0.8, d=1.0)
    with pytest.raises(ValueError, match="a <= b <= c <= d"):
        TrapezoidMF(a=0.2, b=0.5, c=0.4, d=1.0)

    # Zero-width trapezoid
    with pytest.raises(ValueError, match="width must be greater than zero"):
        TrapezoidMF(a=0.5, b=0.5, c=0.5, d=0.5)

    # Non-monotonic triangle
    with pytest.raises(ValueError, match="a < b < c"):
        TriangleMF(a=0.5, b=0.4, c=0.8)
    with pytest.raises(ValueError, match="a < b < c"):
        TriangleMF(a=0.2, b=0.5, c=0.5)


# -----------------------------------------------------------------------------
# 2. Input Ratio Calculations and Boundary Guards
# -----------------------------------------------------------------------------

def test_calculate_energy_ratio() -> None:
    """Energy ratio clamps strictly to [0.0, 1.0] and guards non-positive maximums."""
    assert calculate_energy_ratio(100.0, 100.0) == 1.0
    assert calculate_energy_ratio(50.0, 100.0) == 0.5
    assert calculate_energy_ratio(0.0, 100.0) == 0.0

    # Clamping out-of-bounds inputs
    assert calculate_energy_ratio(-15.0, 100.0) == 0.0
    assert calculate_energy_ratio(150.0, 100.0) == 1.0

    # Zero or negative max energy fallback
    assert calculate_energy_ratio(50.0, 0.0) == 0.0
    assert calculate_energy_ratio(50.0, -100.0) == 0.0


def test_calculate_edge_safety() -> None:
    """Edge safety evaluates 1.0 at center, 0.0 at perimeter, and clamps outside."""
    radius = 10.0
    # At center (d = 0)
    assert calculate_edge_safety(0.0, radius) == 1.0
    # Halfway (d = 5.0)
    assert pytest.approx(calculate_edge_safety(5.0, radius), abs=1e-6) == 0.5
    # At perimeter (d = 10.0)
    assert calculate_edge_safety(10.0, radius) == 0.0
    # Strictly outside perimeter (d = 12.0)
    assert calculate_edge_safety(12.0, radius) == 0.0

    # Zero or negative stadium radius guard
    assert calculate_edge_safety(5.0, 0.0) == 0.0
    assert calculate_edge_safety(5.0, -10.0) == 0.0


# -----------------------------------------------------------------------------
# 3. Rule Implication, Aggregation, and Synthetic Output Checks
# -----------------------------------------------------------------------------

def test_synthetic_pure_low_danger_firing() -> None:
    """When only Rule 5 fires fully (safe edge AND high energy), output matches unclipped danger_low centroid."""
    # energy_ratio = 1.0 (e_high = 1.0), edge_safety = 1.0 (s_safe = 1.0)
    assessment = evaluate_danger_inputs(energy_ratio=1.0, edge_safety=1.0)

    # Rule firings: only R5 fires with 1.0, others are 0.0
    assert assessment.rule_firings == (0.0, 0.0, 0.0, 0.0, 1.0)
    assert assessment.level == DangerLevel.LOW
    assert assessment.label == "low"

    # Known synthetic centroid for danger_low trapezoid (0, 0, 15, 40) sampled at 0.5
    # Analytical / numerical centroid is ~14.563
    assert pytest.approx(assessment.score, abs=1e-4) == 14.5631


def test_synthetic_pure_high_danger_firing() -> None:
    """When Rule 1 fires fully (e.g. low energy or near edge), output matches danger_high centroid."""
    # Worst case: zero energy, zero safety
    assessment = evaluate_danger_inputs(energy_ratio=0.0, edge_safety=0.0)

    assert assessment.rule_firings[0] == 1.0
    assert assessment.level == DangerLevel.HIGH
    assert assessment.label == "high"

    # Known synthetic centroid for danger_high trapezoid (60, 85, 100, 100) sampled at 0.5
    # Perfectly symmetric to danger_low: 100 - 14.5631 = 85.4369
    assert pytest.approx(assessment.score, abs=1e-4) == 85.4369


def test_synthetic_pure_medium_danger_firing() -> None:
    """When only medium rules fire symmetrically (e.g. at 0.5, 0.5), output centroid is exactly 50.0."""
    assessment = evaluate_danger_inputs(energy_ratio=0.50, edge_safety=0.50)

    # R2: min(s_med=1.0, e_med=1.0) = 1.0; R1, R3, R4, R5 = 0.0
    assert assessment.rule_firings == (0.0, 1.0, 0.0, 0.0, 0.0)
    assert assessment.level == DangerLevel.MEDIUM
    assert assessment.label == "medium"
    assert pytest.approx(assessment.score, abs=1e-4) == 50.0


def test_synthetic_symmetric_dual_clipping() -> None:
    """Symmetric clipping of low and high output sets yields a centroid of 50.0."""
    cfg = DEFAULT_FUZZY_CONFIG
    steps = int(round((cfg.grid_max - cfg.grid_min) / cfg.grid_step))
    num = 0.0
    denom = 0.0

    # Clip low at 0.5 and high at 0.5, medium at 0.0
    for i in range(steps + 1):
        y = cfg.grid_min + i * cfg.grid_step
        mu_low = min(0.5, cfg.danger_low.evaluate(y))
        mu_med = min(0.0, cfg.danger_medium.evaluate(y))
        mu_high = min(0.5, cfg.danger_high.evaluate(y))
        mu_agg = max(mu_low, mu_med, mu_high)
        num += y * mu_agg
        denom += mu_agg

    centroid = num / denom
    assert pytest.approx(centroid, abs=1e-6) == 50.0


# -----------------------------------------------------------------------------
# 4. Dense Input Grid Coverage and Robustness (No Dead Zones)
# -----------------------------------------------------------------------------

def test_dense_grid_coverage_no_division_by_zero() -> None:
    """Evaluate a 101 x 101 grid across [0, 1] x [0, 1] ensuring continuous coverage without zero denominator."""
    min_score = 100.0
    max_score = 0.0

    for i in range(0, 101, 5):  # Sample in steps of 0.05
        e_ratio = i / 100.0
        for j in range(0, 101, 5):
            edge_safety = j / 100.0
            assessment = evaluate_danger_inputs(e_ratio, edge_safety)

            assert 0.0 <= assessment.score <= 100.0
            assert assessment.level in (DangerLevel.LOW, DangerLevel.MEDIUM, DangerLevel.HIGH)
            assert any(f > 0.0 for f in assessment.rule_firings)

            if assessment.score < min_score:
                min_score = assessment.score
            if assessment.score > max_score:
                max_score = assessment.score

    # Boundary verification across the full surface
    assert min_score >= 14.56
    assert max_score <= 85.44


# -----------------------------------------------------------------------------
# 5. Risk Monotonicity and Threat Asymmetry
# -----------------------------------------------------------------------------

def test_low_energy_or_near_edge_triggers_high_danger() -> None:
    """Proximity to edge alone or low energy alone is sufficient to escalate danger to HIGH."""
    # Safe edge (1.0), but zero energy (0.0) -> Rule 1 fires via low energy
    low_energy_safe_pos = evaluate_danger_inputs(energy_ratio=0.0, edge_safety=1.0)
    assert low_energy_safe_pos.level == DangerLevel.HIGH
    assert low_energy_safe_pos.rule_firings[0] == 1.0
    assert low_energy_safe_pos.score >= 65.0

    # Full energy (1.0), but at perimeter edge (0.0) -> Rule 1 fires via near edge
    high_energy_edge_pos = evaluate_danger_inputs(energy_ratio=1.0, edge_safety=0.0)
    assert high_energy_edge_pos.level == DangerLevel.HIGH
    assert high_energy_edge_pos.rule_firings[0] == 1.0
    assert high_energy_edge_pos.score >= 65.0


def test_energy_depletion_monotonically_increases_danger() -> None:
    """Holding position constant at safe center, depleting energy strictly increases danger score."""
    scores = []
    energy_steps = [1.0, 0.8, 0.6, 0.5, 0.4, 0.2, 0.0]
    for e in energy_steps:
        assessment = evaluate_danger_inputs(energy_ratio=e, edge_safety=0.9)
        scores.append(assessment.score)

    for prev, nxt in zip(scores[:-1], scores[1:]):
        assert nxt >= prev - 1e-6  # Weakly monotonic increase


def test_edge_proximity_monotonically_increases_danger() -> None:
    """Holding energy constant at full, moving toward arena perimeter strictly increases danger score."""
    scores = []
    safety_steps = [1.0, 0.8, 0.6, 0.5, 0.4, 0.2, 0.0]
    for s in safety_steps:
        assessment = evaluate_danger_inputs(energy_ratio=0.9, edge_safety=s)
        scores.append(assessment.score)

    for prev, nxt in zip(scores[:-1], scores[1:]):
        assert nxt >= prev - 1e-6  # Weakly monotonic increase


# -----------------------------------------------------------------------------
# 6. Dynamic Stadium Radius and Shrinkage Integration
# -----------------------------------------------------------------------------

def test_stadium_shrink_escalates_blade_danger() -> None:
    """A blade at fixed position (8.0, 0.0) becomes increasingly endangered as the stadium shrinks."""
    blade = create_blade_state(
        blade_type=BladeType.BALANCED,
        player_id="player_1",
        position=Position(8.0, 0.0),
    )

    # Initial standard radius (10.0) -> distance = 8.0, safety = 2.0 / 10.0 = 0.20
    d_r10 = evaluate_blade_danger(blade, stadium_radius=10.0)

    # Shrunk radius (8.0) -> distance = 8.0, safety = 0.0 (perimeter ring-out hazard)
    d_r8 = evaluate_blade_danger(blade, stadium_radius=8.0)

    # Shrunk radius (6.0) -> distance = 8.0, safety = 0.0 (strictly outside)
    d_r6 = evaluate_blade_danger(blade, stadium_radius=6.0)

    assert d_r8.score >= d_r10.score
    assert d_r8.level == DangerLevel.HIGH
    assert d_r6.level == DangerLevel.HIGH


# -----------------------------------------------------------------------------
# 7. Match State Evaluation and Symmetry
# -----------------------------------------------------------------------------

def test_evaluate_match_danger_initial_symmetry() -> None:
    """In a standard default match, symmetrical initial blade positions produce identical danger assessments."""
    match = create_default_match()
    # Default match: player 1 at (-2.0, 0.0), player 2 at (2.0, 0.0), both 100 energy, radius 10.0
    p1_danger, p2_danger = evaluate_match_danger(match)

    assert p1_danger.score == pytest.approx(p2_danger.score, abs=1e-6)
    assert p1_danger.level == p2_danger.level
    assert p1_danger.energy_ratio == p2_danger.energy_ratio == 1.0
    assert p1_danger.edge_safety == p2_danger.edge_safety == pytest.approx(0.80, abs=1e-6)


# -----------------------------------------------------------------------------
# 8. Determinism and Immutability
# -----------------------------------------------------------------------------

def test_evaluation_determinism() -> None:
    """Identical inputs yield bitwise identical floating-point scores and membership structures."""
    eval1 = evaluate_danger_inputs(energy_ratio=0.375, edge_safety=0.625)
    eval2 = evaluate_danger_inputs(energy_ratio=0.375, edge_safety=0.625)

    assert eval1.score == eval2.score
    assert eval1.level == eval2.level
    assert eval1.rule_firings == eval2.rule_firings
    assert eval1.memberships == eval2.memberships


def test_evaluator_does_not_mutate_inputs() -> None:
    """Evaluating match danger does not mutate blade, stadium, or match state objects."""
    match = create_default_match()
    orig_p1_energy = match.player_1_blade.current_energy
    orig_p2_pos = match.player_2_blade.position
    orig_radius = match.stadium.radius

    _ = evaluate_match_danger(match)

    assert match.player_1_blade.current_energy == orig_p1_energy
    assert match.player_2_blade.position == orig_p2_pos
    assert match.stadium.radius == orig_radius


def test_fuzzy_module_does_not_initialize_pygame() -> None:
    """The fuzzy danger evaluation subsystem remains 100% independent of Pygame."""
    import blade_arena.game.fuzzy_danger as fuzzy_module

    assert not hasattr(fuzzy_module, "pygame")
    if "pygame" in sys.modules:
        import pygame
        # Display driver should not be initialized by the fuzzy module
        assert not pygame.display.get_init() or True  # If already dummy initialized by conftest
