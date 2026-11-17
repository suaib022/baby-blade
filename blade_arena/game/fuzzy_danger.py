"""Interpretable, deterministic Mamdani fuzzy inference system for blade danger.

This module provides a pure-Python Mamdani fuzzy inference engine assessing
the situational danger of each blade inside the arena based on two normalized
indicators:
1. `energy_ratio`: Residual rotational energy relative to maximum energy in [0, 1].
2. `edge_safety`: Proximity to the stadium boundary relative to radius in [0, 1].

The output is an interpretable continuous danger score in [0, 100] alongside
a discrete danger level (LOW, MEDIUM, HIGH) and fine-grained rule activation
telemetry for future AI decision-making (Minimax, MCTS) and diagnostic HUD panels.

Note:
All membership parameters and thresholds are proposed initial calibrations,
not fixed requirements from the course proposal.
The fuzzy danger evaluator is purely advisory and does not replace the
deterministic win-condition rules engine.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Optional, Tuple

from blade_arena.game.geometry import distance_from_center
from blade_arena.game.models import BladeState, MatchState


class DangerLevel(str, Enum):
    """Categorical classification of blade danger."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass(frozen=True)
class TrapezoidMF:
    """Piecewise-linear trapezoidal membership function with shoulder support.

    Parameters:
        a: Left base coordinate where membership begins rising from 0.0.
        b: Left top coordinate where membership reaches 1.0.
        c: Right top coordinate where membership begins falling from 1.0.
        d: Right base coordinate where membership returns to 0.0.

    Degenerate shoulders:
        - If a == b (left shoulder), membership is 1.0 for all x <= b.
        - If c == d (right shoulder), membership is 1.0 for all x >= c.
    """

    a: float
    b: float
    c: float
    d: float

    def __post_init__(self) -> None:
        if not (self.a <= self.b <= self.c <= self.d):
            raise ValueError(
                f"Trapezoid parameters must satisfy a <= b <= c <= d, got "
                f"a={self.a}, b={self.b}, c={self.c}, d={self.d}"
            )
        if self.a == self.d:
            raise ValueError("Trapezoid width must be greater than zero (a < d)")

    def evaluate(self, x: float) -> float:
        """Evaluate membership degree mu(x) in [0.0, 1.0]."""
        # Degenerate left shoulder
        if self.a == self.b and x <= self.b:
            return 1.0
        # Degenerate right shoulder
        if self.c == self.d and x >= self.c:
            return 1.0
        # Outside base support
        if x <= self.a or x >= self.d:
            return 0.0
        # Rising slope
        if self.a < x < self.b:
            return (x - self.a) / (self.b - self.a)
        # Flat plateau
        if self.b <= x <= self.c:
            return 1.0
        # Falling slope
        if self.c < x < self.d:
            return (self.d - x) / (self.d - self.c)
        return 0.0


@dataclass(frozen=True)
class TriangleMF:
    """Piecewise-linear triangular membership function.

    Parameters:
        a: Left base coordinate where membership begins rising from 0.0.
        b: Peak coordinate where membership reaches 1.0.
        c: Right base coordinate where membership returns to 0.0.
    """

    a: float
    b: float
    c: float

    def __post_init__(self) -> None:
        if not (self.a < self.b < self.c):
            raise ValueError(
                f"Triangle parameters must satisfy a < b < c, got "
                f"a={self.a}, b={self.b}, c={self.c}"
            )

    def evaluate(self, x: float) -> float:
        """Evaluate membership degree mu(x) in [0.0, 1.0]."""
        if x <= self.a or x >= self.c:
            return 0.0
        if self.a < x <= self.b:
            return (x - self.a) / (self.b - self.a)
        if self.b < x < self.c:
            return (self.c - x) / (self.c - self.b)
        return 0.0


@dataclass(frozen=True)
class FuzzyDangerConfig:
    """Centralized configuration for the Mamdani fuzzy danger inference system.

    All membership parameters and classification thresholds are proposed
    tuning values designed for smooth, interpretable danger estimation.
    """

    # Input Membership Functions: Energy Ratio on [0.0, 1.0]
    energy_low: TrapezoidMF = TrapezoidMF(0.0, 0.0, 0.15, 0.40)
    energy_medium: TriangleMF = TriangleMF(0.20, 0.50, 0.80)
    energy_high: TrapezoidMF = TrapezoidMF(0.60, 0.85, 1.0, 1.0)

    # Input Membership Functions: Edge Safety on [0.0, 1.0]
    edge_near: TrapezoidMF = TrapezoidMF(0.0, 0.0, 0.15, 0.40)
    edge_medium: TriangleMF = TriangleMF(0.20, 0.50, 0.80)
    edge_safe: TrapezoidMF = TrapezoidMF(0.60, 0.85, 1.0, 1.0)

    # Output Membership Functions: Danger Score on [0.0, 100.0]
    danger_low: TrapezoidMF = TrapezoidMF(0.0, 0.0, 15.0, 40.0)
    danger_medium: TriangleMF = TriangleMF(20.0, 50.0, 80.0)
    danger_high: TrapezoidMF = TrapezoidMF(60.0, 85.0, 100.0, 100.0)

    # Defuzzification Grid Sampling Parameters
    grid_min: float = 0.0
    grid_max: float = 100.0
    grid_step: float = 0.5

    # Discrete Classification Thresholds (Display / Diagnostic)
    threshold_low: float = 35.0
    threshold_high: float = 65.0

    # Fallback Neutral Score in the Unlikely Event of Zero Denominator
    fallback_score: float = 50.0

    def __post_init__(self) -> None:
        if self.grid_min >= self.grid_max:
            raise ValueError("grid_min must be less than grid_max")
        if self.grid_step <= 0.0:
            raise ValueError("grid_step must be positive")
        if not (self.grid_min <= self.threshold_low < self.threshold_high <= self.grid_max):
            raise ValueError("Thresholds must satisfy grid_min <= threshold_low < threshold_high <= grid_max")


DEFAULT_FUZZY_CONFIG = FuzzyDangerConfig()


@dataclass(frozen=True)
class DangerAssessment:
    """Immutable assessment of a blade's situational danger.

    Attributes:
        score: Continuous defuzzified danger score in [0.0, 100.0].
        level: Categorical danger level (LOW, MEDIUM, HIGH).
        energy_ratio: Normalized energy input in [0.0, 1.0].
        edge_safety: Normalized edge safety input in [0.0, 1.0].
        memberships: Fuzzified input membership degrees.
        rule_firings: Firing strength of each rule (R1 through R5).
    """

    score: float
    level: DangerLevel
    energy_ratio: float
    edge_safety: float
    memberships: Dict[str, Dict[str, float]]
    rule_firings: Tuple[float, float, float, float, float]

    @property
    def label(self) -> str:
        """String representation of danger level for backward compatibility."""
        return self.level.value


def calculate_energy_ratio(energy: float, maximum_energy: float) -> float:
    """Calculate clamped energy ratio in [0.0, 1.0].

    If maximum_energy <= 0.0, returns 0.0.
    """
    if maximum_energy <= 0.0:
        return 0.0
    ratio = energy / maximum_energy
    return max(0.0, min(1.0, float(ratio)))


def calculate_edge_safety(distance_from_center: float, stadium_radius: float) -> float:
    """Calculate clamped edge safety in [0.0, 1.0].

    1.0 indicates blade center is at the stadium center.
    0.0 indicates blade center is at or outside the stadium perimeter.
    If stadium_radius <= 0.0, returns 0.0.
    """
    if stadium_radius <= 0.0:
        return 0.0
    clamped_dist = max(0.0, float(distance_from_center))
    safety = (stadium_radius - clamped_dist) / stadium_radius
    return max(0.0, min(1.0, float(safety)))


def evaluate_danger_inputs(
    energy_ratio: float,
    edge_safety: float,
    config: Optional[FuzzyDangerConfig] = None,
) -> DangerAssessment:
    """Evaluate continuous danger score and level from normalized inputs.

    Pure function executing standard Mamdani fuzzy inference:
    1. Fuzzification of energy_ratio and edge_safety.
    2. Rule evaluation using MAX (OR) and MIN (AND).
    3. Implication using MIN (Mamdani clipping) and aggregation using MAX.
    4. Centroid defuzzification over discrete output grid.
    5. Categorical classification into LOW, MEDIUM, or HIGH.

    Args:
        energy_ratio: Normalized energy in [0.0, 1.0].
        edge_safety: Normalized edge safety in [0.0, 1.0].
        config: Optional configuration instance (defaults to DEFAULT_FUZZY_CONFIG).

    Returns:
        DangerAssessment containing defuzzified score, level, and telemetry.
    """
    cfg = config or DEFAULT_FUZZY_CONFIG

    # Clamp inputs to valid domain [0.0, 1.0]
    e_val = max(0.0, min(1.0, float(energy_ratio)))
    s_val = max(0.0, min(1.0, float(edge_safety)))

    # Step 1: Fuzzification
    e_low = cfg.energy_low.evaluate(e_val)
    e_med = cfg.energy_medium.evaluate(e_val)
    e_high = cfg.energy_high.evaluate(e_val)

    s_near = cfg.edge_near.evaluate(s_val)
    s_med = cfg.edge_medium.evaluate(s_val)
    s_safe = cfg.edge_safe.evaluate(s_val)

    memberships: Dict[str, Dict[str, float]] = {
        "energy": {"low": e_low, "medium": e_med, "high": e_high},
        "edge_safety": {"near": s_near, "medium": s_med, "safe": s_safe},
    }

    # Step 2: Rule Evaluation
    # Rule 1: near edge OR low energy => high danger
    r1 = max(s_near, e_low)
    # Rule 2: medium edge safety AND medium energy => medium danger
    r2 = min(s_med, e_med)
    # Rule 3: medium edge safety AND high energy => medium danger
    r3 = min(s_med, e_high)
    # Rule 4: safe edge AND medium energy => medium danger
    r4 = min(s_safe, e_med)
    # Rule 5: safe edge AND high energy => low danger
    r5 = min(s_safe, e_high)

    rule_firings: Tuple[float, float, float, float, float] = (r1, r2, r3, r4, r5)

    # Implication consequents
    high_fire = r1
    med_fire = max(r2, r3, r4)
    low_fire = r5

    # Step 3 & 4: Aggregation and Centroid Defuzzification
    # Discrete grid over [grid_min, grid_max]
    steps = int(round((cfg.grid_max - cfg.grid_min) / cfg.grid_step))
    numerator = 0.0
    denominator = 0.0

    for i in range(steps + 1):
        y = cfg.grid_min + i * cfg.grid_step
        # Implication: clipping output membership functions by firing strength
        mu_low = min(low_fire, cfg.danger_low.evaluate(y))
        mu_med = min(med_fire, cfg.danger_medium.evaluate(y))
        mu_high = min(high_fire, cfg.danger_high.evaluate(y))

        # Aggregation: union across rule consequents
        mu_agg = max(mu_low, mu_med, mu_high)

        numerator += y * mu_agg
        denominator += mu_agg

    if denominator > 1e-9:
        score = numerator / denominator
    else:
        # Fallback safeguard in case no rules fire
        score = cfg.fallback_score

    # Clamp score to [grid_min, grid_max]
    clamped_score = max(cfg.grid_min, min(cfg.grid_max, score))

    # Step 5: Categorical Label Classification
    if clamped_score < cfg.threshold_low:
        level = DangerLevel.LOW
    elif clamped_score < cfg.threshold_high:
        level = DangerLevel.MEDIUM
    else:
        level = DangerLevel.HIGH

    return DangerAssessment(
        score=clamped_score,
        level=level,
        energy_ratio=e_val,
        edge_safety=s_val,
        memberships=memberships,
        rule_firings=rule_firings,
    )


def evaluate_blade_danger(
    blade: BladeState,
    stadium_radius: float,
    config: Optional[FuzzyDangerConfig] = None,
) -> DangerAssessment:
    """Evaluate danger for a single blade given the current stadium radius.

    Pure function that calculates energy ratio and edge safety from blade state
    and stadium radius, then evaluates fuzzy danger.
    """
    dist = distance_from_center(blade.position)
    energy = getattr(blade, "current_energy", getattr(blade, "energy", 0.0))
    max_energy = getattr(blade, "max_energy", getattr(blade, "maximum_energy", 100.0))
    e_ratio = calculate_energy_ratio(energy, max_energy)
    edge_safety = calculate_edge_safety(dist, stadium_radius)
    return evaluate_danger_inputs(e_ratio, edge_safety, config=config)


def evaluate_match_danger(
    state: MatchState,
    config: Optional[FuzzyDangerConfig] = None,
) -> Tuple[DangerAssessment, DangerAssessment]:
    """Evaluate situational danger for both blades in the current match state.

    Returns:
        Tuple of (player_1_danger, player_2_danger).
    """
    radius = state.stadium.radius
    p1_danger = evaluate_blade_danger(state.player_1_blade, radius, config=config)
    p2_danger = evaluate_blade_danger(state.player_2_blade, radius, config=config)
    return p1_danger, p2_danger
