# BLADE ARENA — Shared AI Heuristic Evaluation

> **Status Notice:** This document specifies **Module 10: Shared AI Heuristic Evaluation**. It defines a transparent, perspective-aware, and deterministic state evaluation engine shared by both Ironclad (Minimax in Module 11) and Cyclone (MCTS in Module 12).

---

## 1. Architectural Role and Design Principles

The heuristic evaluation function serves as the central scoring oracle for all autonomous decision-making agents in BLADE ARENA.

```
                           +--------------------------+
                           |        MatchState        |
                           +--------------------------+
                                        |
                 +----------------------+----------------------+
                 |                                             |
                 v                                             v
     [Is Match Terminal?]                            [Match In Progress]
                 |                                             |
                 v                                             v
     +-----------------------+                    +--------------------------+
     |   Terminal Utility    |                    |  Evaluate Both Blades:   |
     |   Win:   +100.0       |                    |  - Energy Ratio   (0.30) |
     |   Loss:  -100.0       |                    |  - Stability      (0.30) |
     |   Draw:     0.0       |                    |  - Position Safe  (0.20) |
     +-----------------------+                    |  - Special Spin   (0.05) |
                 |                                |  - Fuzzy Danger  (-0.15) |
                 |                                +--------------------------+
                 |                                             |
                 |                                             v
                 |                                +--------------------------+
                 |                                |   Nonterminal Score:     |
                 |                                |   V(own) - V(opponent)   |
                 |                                +--------------------------+
                 |                                             |
                 |                                             v
                 |                                +--------------------------+
                 |                                |   MCTS Scaled Reward:    |
                 |                                |   clamp(score, -.85, .85)|
                 +----------------------+---------+--------------------------+
                                        |
                                        v
                           +--------------------------+
                           |     EvaluationResult     |
                           |  - score: [-100, +100]   |
                           |  - mcts_reward: [-1, +1] |
                           |  - feature breakdowns    |
                           +--------------------------+
```

### Core Design Principles
1. **Perspective-Aware Zero-Sum Symmetry:**
   $$\text{score}(S, P_1) = -\text{score}(S, P_2)$$
   Swapping the perspective player strictly negates the score and the MCTS rollout reward.
2. **Absolute Dominance of Terminal Utility:**
   Terminal knockouts and timeouts return $\pm 100.0$, strictly dominating all nonterminal heuristic scores (which reside inside $[-1.0, +1.0]$). An agent will never sacrifice a terminal win for an advantageous nonterminal configuration.
3. **MCTS Reward Normalization:**
   Nonterminal rollout evaluations are clamped to $[-0.85, +0.85]$, guaranteeing that nonterminal rollouts cannot equal or outrank terminal wins ($+1.0$) or losses ($-1.0$).
4. **Pure Functionality & Immutability:**
   Zero side effects, zero state mutation, and 100% Pygame-independent.

---

## 2. Blade Component Evaluation

For any blade $B$ in a stadium with radius $r$:

### 2.1 Component Ratios
1. **Energy Ratio ($E_r$):**
   $$E_r = \text{clamp}\left(\frac{B.\text{current\_energy}}{B.\text{max\_energy}}, 0.0, 1.0\right)$$
2. **Stability Ratio ($S_r$):**
   $$S_r = \text{clamp}\left(\frac{B.\text{current\_stability}}{B.\text{max\_stability}}, 0.0, 1.0\right)$$
3. **Position Safety ($P_s$):**
   $$P_s = \text{clamp}\left(1.0 - \frac{d(B.\text{position})}{r}, 0.0, 1.0\right)$$
   Where $d(P) = \sqrt{x^2 + y^2}$. Center proximity yields $1.0$; boundary edge yields $0.0$.
4. **Special Spin Availability ($A_{\text{special}}$):**
   $$A_{\text{special}} = \begin{cases} 1.0 & \text{Special Spin is legal (energy } \ge 35.0 \text{ and cooldown ready)} \\ 0.0 & \text{otherwise} \end{cases}$$
5. **Fuzzy Danger Ratio ($D_r$):**
   $$D_r = \frac{\text{MamdaniDangerScore}(B, r)}{100.0} \in [0.0, 1.0]$$

### 2.2 Composite Blade Value Formula
The composite value of a single blade is defined as:
$$\text{blade\_value} = 0.30 \cdot E_r + 0.30 \cdot S_r + 0.20 \cdot P_s + 0.05 \cdot A_{\text{special}} - 0.15 \cdot D_r$$

#### Theoretical Bounds
- **Maximum Blade Value:** $\approx +0.828$ (Full energy, full stability, at center, special ready, minimal danger $\approx 14.56$).
- **Minimum Blade Value:** $\approx -0.128$ (Zero energy, zero stability, at edge, special locked, maximal danger $\approx 85.44$).
- **Net Theoretical Span:** $\Delta V_{\text{blade}} \le 1.0$.

---

## 3. Nonterminal State Evaluation

From the perspective of player $P$ against opponent $O$:
$$\text{score}(S, P) = \text{blade\_value}(P) - \text{blade\_value}(O)$$

### Mathematical Symmetry Proof
$$\text{score}(S, O) = \text{blade\_value}(O) - \text{blade\_value}(P) = -(\text{blade\_value}(P) - \text{blade\_value}(O)) = -\text{score}(S, P)$$
This zero-sum symmetry ensures that Minimax search trees and MCTS backpropagations evaluate opposing moves with identical adversarial accuracy.

---

## 4. Terminal Utility & Absolute Dominance

When a state is terminal (either with `status == FINISHED` or satisfying terminal conditions via `evaluate_match_termination`):

| Match Outcome | Minimax Utility | MCTS Rollout Reward | Tactical Priority |
| :--- | :---: | :---: | :--- |
| **Perspective Player Win** | $+100.0$ | $+1.0$ | Ultimate Goal |
| **Perspective Player Loss** | $-100.0$ | $-1.0$ | Absolute Avoidance |
| **Draw / Tie** | $0.0$ | $0.0$ | Neutral Outcome |

### Dominance Proof
Because nonterminal scores are bounded by:
$$\max |\text{score}_{\text{nonterminal}}| = \text{blade\_value}_{\max} - \text{blade\_value}_{\min} \approx 0.828 - (-0.128) = 0.956 < 1.0$$
It follows that:
$$\min(\text{Terminal Win}) = +100.0 \gg +0.956 \ge \max(\text{Nonterminal})$$
$$\max(\text{Terminal Loss}) = -100.0 \ll -0.956 \le \min(\text{Nonterminal})$$

> [!IMPORTANT]
> A search algorithm maximizing this heuristic will **never** prefer an advantageous nonterminal board state over an actual knockout victory, and will **never** allow a nonterminal advantage to obscure an incoming knockout defeat.

---

## 5. MCTS Rollout Reward Bounded Scaling

Monte Carlo Tree Search operates best when simulation rollout values are scaled to a normalized reward space $[-1.0, +1.0]$.

For nonterminal rollout cutoffs:
$$\text{mcts\_reward} = \text{clamp}(\text{score}, -0.85, +0.85)$$

### Properties:
1. **Preserved Linear Ordering:** Heuristic advantage translates directly to positive rollout rewards without distorting relative gradients.
2. **Terminal Separation:** A nonterminal rollout can achieve at most $\pm 0.85$, strictly inferior to a true terminal win ($+1.0$) and strictly superior to a true terminal loss ($-1.0$).
3. **Zero Equivalence:** An exactly balanced match ($\text{score} = 0.0$) produces reward $0.0$, matching the neutral value of a draw.

---

## 6. Analysis of "Double-Counting" Position and Energy

Notice that energy and stadium position appear twice in the heuristic:
1. **Direct Linear Terms:** $+0.30 \cdot E_r$ and $+0.20 \cdot P_s$.
2. **Indirect Fuzzy Danger Penalty:** $-0.15 \cdot D_r$, where $D_r$ itself is computed by fuzzifying $E_r$ and $S_e$ ($= P_s$).

### Why This Is Intentional and Beneficial
- **Linear Terms Reward Steady Progress:** The direct terms reward marginal resource preservation and gradual repositioning toward the arena center during neutral exchanges.
- **Fuzzy Danger Imposes a "Cliff Penalty":** Mamdani Rule 1 (`near edge OR low energy => high danger`) activates sharply when a blade enters the critical perimeter zone or depletes its reserves. The fuzzy penalty acts as an emergency deterrent against high-risk positions that look superficially acceptable under pure linear metrics.
- **Complementary Dynamic:** The combination gives the AI smooth directional gradients in the center while creating steep repulsive barriers near the boundaries and resource exhaustion thresholds.

---

## 7. Explainability and Breakdown Schema

The evaluation returns an immutable `EvaluationResult` containing full introspection data:

```python
@dataclass(frozen=True)
class EvaluationResult:
    score: float                         # Minimax score in [-100.0, +100.0]
    mcts_reward: float                   # MCTS rollout reward in [-1.0, +1.0]
    is_terminal: bool                    # Whether state is terminal
    perspective_player: str              # Perspective player ID
    opponent_player: str                 # Opponent player ID
    own_blade_value: float               # Raw composite value of own blade
    opponent_blade_value: float          # Raw composite value of opponent
    own_breakdown: Optional[BladeEvaluationBreakdown]       # Detailed telemetry
    opponent_breakdown: Optional[BladeEvaluationBreakdown]  # Detailed telemetry
```

---

## 8. Public Python API

```python
from blade_arena.game import (
    evaluate_state,
    evaluate_heuristic,
    evaluate_blade_components,
    HeuristicConfig,
)

# 1. Full evaluation with breakdown
result = evaluate_state(match_state, "player_1")
print(f"Minimax Score: {result.score:.3f}")
print(f"MCTS Reward:   {result.mcts_reward:.3f}")
print(f"P1 Value:      {result.own_blade_value:.3f}")
print(f"P2 Value:      {result.opponent_blade_value:.3f}")

# 2. Fast float-only evaluator for Minimax inner loops
score = evaluate_heuristic(match_state, "player_1")
```
