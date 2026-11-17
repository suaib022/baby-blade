# BLADE ARENA — Mamdani Fuzzy Danger Estimation

> **Status Notice:** This document specifies **Module 9: Mamdani Fuzzy Danger Estimation**. It defines an interpretable, deterministic fuzzy inference system that evaluates situational danger for each blade based on residual energy and boundary proximity.

---

## 1. Architectural Overview and System Role

The Mamdani Fuzzy Danger System provides an interpretable, continuous situational risk assessment for spinning blades in the arena.

```
+-------------------------------------------------------------+
|                     Match State                             |
|  - Blade: current_energy / max_energy                       |
|  - Blade: position -> distance_from_center                  |
|  - Stadium: current radius r                                |
+-------------------------------------------------------------+
                              |
                              v
+-------------------------------------------------------------+
|                   Input Normalization                       |
|  - energy_ratio = clamp(current_energy / max_energy, 0, 1)  |
|  - edge_safety  = clamp((r - distance) / r, 0, 1)          |
+-------------------------------------------------------------+
                              |
                              v
+-------------------------------------------------------------+
|                      Fuzzification                          |
|  - Energy: Low (trap), Medium (tri), High (trap)            |
|  - Edge:   Near (trap), Medium (tri), Safe (trap)           |
+-------------------------------------------------------------+
                              |
                              v
+-------------------------------------------------------------+
|                      Rule Evaluation                        |
|  - R1: Near Edge OR Low Energy     => High Danger (MAX/MIN) |
|  - R2: Med Safety AND Med Energy   => Med Danger (MIN/MIN)  |
|  - R3: Med Safety AND High Energy  => Med Danger (MIN/MIN)  |
|  - R4: Safe Edge AND Med Energy    => Med Danger (MIN/MIN)  |
|  - R5: Safe Edge AND High Energy   => Low Danger (MIN/MIN)  |
+-------------------------------------------------------------+
                              |
                              v
+-------------------------------------------------------------+
|                 Aggregation & Defuzzification               |
|  - Union clipping: mu_agg(y) = max(mu_low, mu_med, mu_high) |
|  - Centroid: y_cog = sum(y * mu_agg) / sum(mu_agg)          |
|  - Grid: y in [0, 100] with step 0.5 (201 sample points)    |
+-------------------------------------------------------------+
                              |
                              v
+-------------------------------------------------------------+
|                      DangerAssessment                       |
|  - score: float in [0, 100]                                 |
|  - level: LOW (< 35) | MEDIUM (35-65) | HIGH (>= 65)        |
|  - memberships & rule_firings telemetry                     |
+-------------------------------------------------------------+
```

### Advisory Boundary Guarantee
> [!IMPORTANT]
> The fuzzy danger assessment is **purely advisory**. It supplies heuristic telemetry to search algorithms (Minimax in Module 11, MCTS in Module 12) and HUD danger gauges (Module 15). It **never** triggers knockouts, alters blade attributes, or replaces the deterministic win-condition rules engine.

---

## 2. Input Normalization

The inference system takes two normalized scalar inputs bounded to $[0.0, 1.0]$:

### 2.1 Energy Ratio ($E_r$)
Measures residual rotational kinetic energy relative to the blade's initial maximum capacity:
$$E_r = \text{clamp}\left(\frac{\text{current\_energy}}{\text{max\_energy}}, 0.0, 1.0\right)$$
- If $\text{max\_energy} \le 0.0$, the function returns $0.0$ to guard against division by zero.
- $E_r = 1.0$ indicates a fully charged blade.
- $E_r = 0.0$ indicates total rotational depletion (imminent spin-out).

### 2.2 Edge Safety ($S_e$)
Measures geometric distance from the lethal arena boundary:
$$S_e = \text{clamp}\left(\frac{r - d(P)}{r}, 0.0, 1.0\right)$$
Where $d(P) = \sqrt{x^2 + y^2}$ is the Euclidean distance from the arena center $(0, 0)$ and $r$ is the current stadium radius.
- If $r \le 0.0$, the function returns $0.0$ as an emergency guard.
- $S_e = 1.0$ when the blade is at the exact center ($d = 0$).
- $S_e = 0.0$ when the blade is at or beyond the arena perimeter ($d \ge r$).

---

## 3. Membership Function Specifications

All membership functions are piecewise-linear functions with full endpoint support.

### 3.1 Mathematical Definitions

#### Triangular Function: $\text{TriangleMF}(a, b, c)$
With strict parameter ordering $a < b < c$:
$$\mu(x) = \begin{cases} 
0.0 & x \le a \text{ or } x \ge c \\
\frac{x - a}{b - a} & a < x \le b \\
\frac{c - x}{c - b} & b < x < c 
\end{cases}$$

#### Trapezoidal Function with Shoulder Support: $\text{TrapezoidMF}(a, b, c, d)$
With parameter ordering $a \le b \le c \le d$ and $a < d$:
$$\mu(x) = \begin{cases}
1.0 & a = b \text{ and } x \le b \quad \text{(Left Shoulder)} \\
1.0 & c = d \text{ and } x \ge c \quad \text{(Right Shoulder)} \\
0.0 & x \le a \text{ or } x \ge d \\
\frac{x - a}{b - a} & a < x < b \\
1.0 & b \le x \le c \\
\frac{d - x}{d - c} & c < x < d 
\end{cases}$$

### 3.2 Proposed Initial Calibration Parameters

> [!NOTE]
> The numeric parameters below are proposed initial calibrations designed for smooth gradation and comprehensive coverage across all input combinations. They are exposed via `FuzzyDangerConfig` for straightforward retuning.

#### Input Sets on $[0.0, 1.0]$:
| Linguistic Set | Function Type | Parameters $(a, b, c, d)$ | Meaning |
| :--- | :--- | :--- | :--- |
| **Energy Low** | Trapezoid (Left Shoulder) | $(0.0, 0.0, 0.15, 0.40)$ | Energy depleted or critically low |
| **Energy Medium** | Triangle | $(0.20, 0.50, 0.80)$ | Nominal operating energy |
| **Energy High** | Trapezoid (Right Shoulder) | $(0.60, 0.85, 1.0, 1.0)$ | Robust / near-maximum energy |
| **Edge Near** | Trapezoid (Left Shoulder) | $(0.0, 0.0, 0.15, 0.40)$ | Immediate ring-out hazard |
| **Edge Medium** | Triangle | $(0.20, 0.50, 0.80)$ | Moderate distance from wall |
| **Edge Safe** | Trapezoid (Right Shoulder) | $(0.60, 0.85, 1.0, 1.0)$ | Deep interior arena position |

#### Output Sets on $[0.0, 100.0]$:
| Linguistic Set | Function Type | Parameters $(a, b, c, d)$ | Centroid |
| :--- | :--- | :--- | :--- |
| **Danger Low** | Trapezoid (Left Shoulder) | $(0.0, 0.0, 15.0, 40.0)$ | $\approx 14.56$ |
| **Danger Medium** | Triangle | $(20.0, 50.0, 80.0)$ | $50.00$ |
| **Danger High** | Trapezoid (Right Shoulder) | $(60.0, 85.0, 100.0, 100.0)$ | $\approx 85.44$ |

---

## 4. Rule Base & Fuzzy Logic Operators

### 4.1 Canonical Rules
The rule base evaluates five deterministic Mamdani propositions:

1. **Rule 1 (Critical Hazard):**
   $$\text{IF } \text{Edge is Near OR Energy is Low } \implies \text{Danger is High}$$
   $$\text{fire}_1 = \max(\mu_{\text{edge: near}}(S_e), \mu_{\text{energy: low}}(E_r))$$

2. **Rule 2 (Interior Attrition):**
   $$\text{IF } \text{Edge is Medium AND Energy is Medium } \implies \text{Danger is Medium}$$
   $$\text{fire}_2 = \min(\mu_{\text{edge: medium}}(S_e), \mu_{\text{energy: medium}}(E_r))$$

3. **Rule 3 (Perimeter Caution):**
   $$\text{IF } \text{Edge is Medium AND Energy is High } \implies \text{Danger is Medium}$$
   $$\text{fire}_3 = \min(\mu_{\text{edge: medium}}(S_e), \mu_{\text{energy: high}}(E_r))$$

4. **Rule 4 (Depleting Interior):**
   $$\text{IF } \text{Edge is Safe AND Energy is Medium } \implies \text{Danger is Medium}$$
   $$\text{fire}_4 = \min(\mu_{\text{edge: safe}}(S_e), \mu_{\text{energy: medium}}(E_r))$$

5. **Rule 5 (Prime Dominance):**
   $$\text{IF } \text{Edge is Safe AND Energy is High } \implies \text{Danger is Low}$$
   $$\text{fire}_5 = \min(\mu_{\text{edge: safe}}(S_e), \mu_{\text{energy: high}}(E_r))$$

### 4.2 Mathematical Operators
- **T-norm (Fuzzy AND):** Standard minimum: $\min(u, v)$
- **S-norm (Fuzzy OR):** Standard maximum: $\max(u, v)$
- **Fuzzy Implication (Mamdani Clipping):** Output membership functions are clipped at the rule's activation firing strength:
  $$\mu_{\text{clipped}}(y) = \min(\text{fire}_r, \mu_{\text{out}}(y))$$
- **Rule Aggregation:** Output membership union across all five rules using maximum:
  $$\mu_{\text{agg}}(y) = \max_{r \in \{1..5\}} \min(\text{fire}_r, \mu_{\text{out}_r}(y))$$

### 4.3 Input Partition Coverage Matrix

| Edge Safety \ Energy | Low Energy | Medium Energy | High Energy |
| :--- | :---: | :---: | :---: |
| **Near Edge** | **High** (R1 via both) | **High** (R1 via Near) | **High** (R1 via Near) |
| **Medium Safety** | **High** (R1 via Low) | **Medium** (R2) | **Medium** (R3) |
| **Safe Center** | **High** (R1 via Low) | **Medium** (R4) | **Low** (R5) |

> [!TIP]
> Notice that all 9 quadrants of the input state space are explicitly mapped to at least one active rule. There are zero unmapped regions or dead zones anywhere on $[0, 1] \times [0, 1]$.

---

## 5. Defuzzification via Discrete Centroid

The aggregated fuzzy output $\mu_{\text{agg}}(y)$ is transformed into a continuous crisp scalar score in $[0.0, 100.0]$ via the Center of Gravity (Centroid) method discretized over a uniform grid:

$$\text{Score} = \frac{\sum_{i=0}^{N} y_i \cdot \mu_{\text{agg}}(y_i)}{\sum_{i=0}^{N} \mu_{\text{agg}}(y_i)}$$

### Sampling Parameters
- **Domain:** $y \in [0.0, 100.0]$
- **Step Size:** $\Delta y = 0.5$
- **Sample Count:** $N = 201$ evaluation points ($0.0, 0.5, 1.0, \dots, 99.5, 100.0$)

### Zero Denominator Fallback
Because all 9 input quadrants are covered by overlapping membership functions, the denominator $\sum \mu_{\text{agg}}(y_i)$ is mathematically guaranteed to be strictly positive ($\ge 35.93$ across the entire surface). If an anomalous zero denominator occurs, the engine falls back to `fallback_score = 50.0` (Medium Danger).

---

## 6. Categorical Classification Thresholds

For HUD telemetry displays and high-level behavioral branch selection:

| Danger Level | Crisp Score Range | Tactical Interpretation |
| :--- | :--- | :--- |
| **`DangerLevel.LOW`** | $\text{score} < 35.0$ | Stable position, abundant energy, offensive opportunity |
| **`DangerLevel.MEDIUM`** | $35.0 \le \text{score} < 65.0$ | Contested territory or moderate attrition; defensive vigilance needed |
| **`DangerLevel.HIGH`** | $\text{score} \ge 65.0$ | Imminent elimination hazard (critical energy or near perimeter) |

---

## 7. Computational Complexity and Limitations

### Performance Characteristics
- **Time Complexity:** $O(1)$ constant time per evaluation. Exactly 201 iterations over simple floating-point operations.
- **Memory Footprint:** Zero dynamic memory allocation beyond the returned frozen `DangerAssessment` dataclass.
- **Purity:** Pure mathematical functions; strictly zero side effects or state mutations.

### Domain Limitations
- **Instantaneous Threat Only:** The evaluator assesses the current snapshot. It does not predict future blade velocity vectors or planned actions (which is the domain of Minimax search in Module 11 and MCTS in Module 12).
- **Advisory Status:** Danger scores do not cause eliminations; ring-outs and bursts are triggered exclusively by the deterministic win-condition engine.

---

## 8. Public Python API

```python
from blade_arena.game import (
    evaluate_blade_danger,
    evaluate_danger_inputs,
    evaluate_match_danger,
    DangerAssessment,
    DangerLevel,
    FuzzyDangerConfig,
)

# 1. Evaluate from normalized inputs
assessment = evaluate_danger_inputs(energy_ratio=0.85, edge_safety=0.90)
print(assessment.score)  # ~14.56
print(assessment.level)  # DangerLevel.LOW

# 2. Evaluate from a BladeState and current arena radius
blade_danger = evaluate_blade_danger(match.player_1_blade, match.stadium.radius)
print(f"P1 Danger: {blade_danger.score:.1f} ({blade_danger.level.value})")

# 3. Evaluate both blades in a match state
p1_danger, p2_danger = evaluate_match_danger(match)
```
