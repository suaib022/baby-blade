# BLADE ARENA — Ironclad Minimax AI

> **Status Notice:** This document specifies **Module 11: Ironclad — Minimax AI**. It defines the classical adversarial search engine employing depth-limited Minimax with explicit MAX/MIN roles, simultaneous-action conservatism, alpha-pruning, and iterative deepening.

---

## 1. Formal Problem Formulation

The decision problem confronting Ironclad is modeled as a two-player zero-sum simultaneous matrix game unfolded across discrete multi-round tree depths:

| Component | Formal Definition | BLADE ARENA Implementation |
| :--- | :--- | :--- |
| **State Space ($S$)** | Game configuration at round start | Immutable `MatchState` snapshot |
| **Acting Agent (MAX)** | Deciding agent seeking to maximize utility | `player_id` |
| **Opponent Model (MIN)** | Adversary assumed to minimize MAX's payoff | `opponent_id` |
| **Actions ($A(S, p)$)** | Available legal decisions for player $p$ | `legal_actions(state, p)` (subset of `ORDERED_ACTIONS`) |
| **Transition ($\text{RESULT}$)** | Joint simultaneous resolution of action pair | `resolve_combat_round(state, p1_action, p2_action)` |
| **Terminal Test ($\text{IS\_TERMINAL}$)** | Check for knockout or round 40 completion | `state.status == FINISHED` or `is_match_terminal(state)` |
| **Utility ($\text{UTILITY}$)** | Payoff from MAX's perspective | Terminal: $+100.0$ (Win), $-100.0$ (Loss), $0.0$ (Draw)<br>Nonterminal: `evaluate_heuristic(state, MAX)` |

---

## 2. Simultaneous-Action Conservatism

In BLADE ARENA, both players submit actions simultaneously and blindly without prior disclosure.

```
                           [MAX (Ironclad)]
                           Selects Action a
                                  |
              +-------------------+-------------------+
              |                   |                   |
            CHARGE              ATTACK              GUARD ...
              |                   |                   |
        [MIN evaluates]     [MIN evaluates]     [MIN evaluates]
       Opponent replies:   Opponent replies:   Opponent replies:
       {C, A, G, D, S}     {C, A, G, D, S}     {C, A, G, D, S}
              |                   |                   |
              v                   v                   v
          min V(C, o)         min V(A, o)         min V(G, o)
              \                   |                   /
               \                  |                  /
                +-----------------+-----------------+
                                  |
                        MAX selects argmax_a [ min_o V(a, o) ]
```

### The Worst-Case Guarantee
Because the opponent commits their move blindly at the same moment, Ironclad conservatively assumes the opponent will choose the move that minimizes MAX's outcome:
$$V(a) = \min_{o \in A(S, \text{opp})} \text{Minimax}(\text{resolve}(S, a, o), d - 1)$$
MAX then selects the action that maximizes this worst-case floor:
$$a^* = \arg\max_{a \in A(S, \text{MAX})} V(a)$$

> [!NOTE]
> This worst-case assumption does **not** assume the opponent can see MAX's action. Rather, it guarantees that even if the opponent plays an optimal counter, MAX will achieve at least value $V(a^*)$. It is the optimal strategy for zero-sum matrix games without mixed-strategy randomization.

---

## 3. Iterative Deepening Architecture

Ironclad employs **Iterative Deepening Search (IDS)** across depths $d = 1, 2, \dots, \text{max\_depth}$:

1. **Immediate Fallback Guarantee:** Before search commences, an immediate legal fallback action (the first legal action in `ORDERED_ACTIONS`) is cached.
2. **Depth Iteration:**
   - Depth 1 completes and caches $(a_1^*, V_1)$.
   - Depth 2 completes and overwrites $(a_2^*, V_2)$.
   - Depth $d$ executes. If interrupted mid-search (by node budget or deadline), the partial search is discarded and $(a_{d-1}^*, V_{d-1})$ is safely returned.
3. **Early Cutoff on Terminal Win:** If any completed depth discovers an action guaranteeing a terminal win ($V \ge +100.0$), search immediately terminates as no deeper search can improve upon certainty.

---

## 4. Conservative Alpha-Pruning

While standard alpha-beta pruning applies to alternating turns, simultaneous matrix games permit **inner-loop alpha pruning**:

When MAX is searching candidates, let $\alpha$ be the highest guaranteed value found among previously evaluated candidate actions.
When evaluating candidate $a_{\text{max}}$:
$$\text{worst\_opp\_val} = \min_{o} V(a_{\text{max}}, o)$$
If any opponent response $o$ produces $V(a_{\text{max}}, o) \le \alpha$:
$$\text{worst\_opp\_val} \le \alpha$$
Therefore, $a_{\text{max}}$ cannot beat MAX's existing best choice $\alpha$. The search immediately breaks out of the opponent loop, pruning all remaining unvisited counter-actions!

### Empirical Pruning Impact (Initial Match State)
| Depth | Unpruned Nodes | Pruned Nodes | Pruning Savings |
| :---: | :---: | :---: | :---: |
| **1** | 25 | 14 | **44.0%** |
| **2** | 650 | 236 | **63.7%** |
| **3** | 15,625 | 2,425 | **84.5%** |

Both pruned and unpruned search produce mathematically identical decisions and evaluations.

---

## 5. Deterministic Tie-Breaking

To guarantee full determinism across test suites and AI tournaments:
- Actions are iterated in canonical priority order:
  `ORDERED_ACTIONS = (Action.CHARGE, Action.ATTACK, Action.GUARD, Action.DODGE, Action.SPECIAL_SPIN)`
- A later candidate action replaces the current best action if and only if:
  $$V(a_{\text{new}}) > V(a_{\text{best}}) + 10^{-6}$$
- On ties (absolute difference $\le 10^{-6}$), the earlier action in `ORDERED_ACTIONS` is retained.

---

## 6. Empirical Performance Benchmarks

Measured on standard 64-bit Python 3.12 under the default match state ($r = 10.0$, balanced blades at distance $4.0$):

| Difficulty Preset | Depth | Evaluated Nodes | Execution Time | Output Score |
| :--- | :---: | :---: | :---: | :---: |
| **`IroncladDifficulty.EASY`** | 1 | 14 | $4.43\text{ ms}$ | $-0.0120$ |
| **`IroncladDifficulty.MEDIUM`** | 2 | 236 | $65.36\text{ ms}$ | $-0.0128$ |
| **`IroncladDifficulty.HARD`** | 3 | 2,425 | $619.49\text{ ms}$ | $-0.0166$ |

> [!NOTE]
> Higher difficulty budgets deepen lookahead, but in accordance with the project specification, Hard is presented as a deeper search budget, not as an uncalibrated claim of absolute gameplay superiority.

---

## 7. Public Python API

```python
from blade_arena.ai import (
    IroncladAgent,
    IroncladConfig,
    IroncladDifficulty,
    choose_action,
    decide,
)

# 1. Stateless functional decision (plain Action)
action = choose_action(match_state, "player_1")

# 2. Functional decision with diagnostic telemetry
action, decision = choose_action(match_state, "player_1", return_diagnostics=True)
print(f"Action: {decision.action.name}")
print(f"Depth Completed: {decision.depth_completed}")
print(f"Nodes Evaluated: {decision.nodes_evaluated}")
print(f"Time: {decision.decision_time_seconds * 1000:.2f} ms")

# 3. Object-oriented agent wrapper
agent = IroncladAgent(
    player_id="player_1",
    difficulty=IroncladDifficulty.MEDIUM,
)
action = agent.choose_action(match_state)
```
