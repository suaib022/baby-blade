# BLADE ARENA — Cyclone MCTS AI

> **Status Notice:** This document specifies **Module 12: Cyclone — Monte Carlo Tree Search AI**. It defines the sampling-based statistical decision engine employing Monte Carlo Tree Search with simultaneous-action modeling, UCB1 selection, uniform opponent sampling, bounded rollout cutoffs, and isolated RNG reproducibility.

---

## 1. Architectural Role and Core Philosophy

While **Ironclad** (Module 11) employs depth-limited Minimax to maximize guaranteed worst-case floors, **Cyclone** approaches the simultaneous matrix space through **Monte Carlo Tree Search (MCTS)**. Cyclone samples stochastic rollouts across thousands of simulated round trajectories to statistically estimate expected action payoffs.

```
                         [MCTS State Node S]
                                  |
              +-------------------+-------------------+
              |                   |                   |
        [Action Node: C]    [Action Node: A]    [Action Node: G] ...
              |                   |                   |
        Sample opp in A_opp Sample opp in A_opp Sample opp in A_opp
              |                   |                   |
        +-----+-----+       +-----+-----+       +-----+-----+
        |     |     |       |     |     |       |     |     |
       S'_c1 S'_c2 ...     S'_a1 S'_a2 ...     S'_g1 S'_g2 ...
```

### Strategic Contrast: Ironclad vs. Cyclone
- **Ironclad (Minimax):** Extremely conservative. Assumes the opponent always plays the optimal counter-action. Excellent against aggressive, predictable adversaries, but can be overly cautious.
- **Cyclone (MCTS):** Expectation-oriented. Explores multiple possible opponent reactions, discovering dynamic multi-turn tactical combinations that Minimax might prune as risky.

---

## 2. The Four MCTS Phases

### Phase 1: Selection via UCB1
Starting from the root state node, Cyclone traverses the tree using the Upper Confidence Bound applied to trees (UCB1):
$$\text{UCB1}(a) = \frac{Q_a}{n_a} + C \sqrt{\frac{\ln(N)}{n_a}}$$
Where:
- $Q_a$: Cumulative reward accumulated by action node $a$.
- $n_a$: Visit count of action node $a$.
- $N$: Total visits to the parent state node.
- $C$: Exploration parameter (default: $1.4$, configurable via `CycloneConfig`).

#### Unvisited Node Priority
If any candidate action child has zero visits ($n_a = 0$), UCB1 returns $+\infty$. All unvisited legal action children are fully explored once in canonical `ORDERED_ACTIONS` priority before any child is visited a second time.

### Phase 2: Expansion & Simultaneous Action Modeling
When an action node $a$ is selected:
1. Cyclone identifies all unexpanded opponent counter-actions $o \in \text{legal\_actions}(S, \text{opponent\_id})$.
2. If unexpanded opponent replies remain:
   - One reply $o$ is sampled uniformly at random using Cyclone's isolated RNG.
   - The action pair $(a, o)$ is resolved using the production rules engine:
     $$S', \_ = \text{resolve\_combat\_round}(S, a, o)$$
   - A new child `MCTSStateNode(S')` is added to $a.\text{outcomes}[o]$.
   - The simulation rollout proceeds from $S'$.
3. If all opponent replies have already been expanded:
   - Cyclone samples an opponent counter-action $o \sim \text{Uniform}(\text{legal\_actions}(S, \text{opponent\_id}))$ to descend deeper into the tree.

> [!IMPORTANT]
> **Distinct Outcome Preservation:** Different sampled opponent replies to the same Cyclone action remain completely distinct nodes in `outcomes[o]`. A single opponent reaction is never cached as the sole future of an action.

### Phase 3: Simulation (Rollout)
From the newly expanded leaf state $S'$, Cyclone executes a rapid forward simulation up to `max_rollout_depth` rounds (default: 6 rounds):
- In each step, both Cyclone and the opponent choose actions uniformly at random from their legal options.
- The state is advanced using `resolve_combat_round`.
- If the match reaches a terminal state, the true terminal reward is immediately returned:
  - **Cyclone Win:** $+1.0$
  - **Cyclone Loss:** $-1.0$
  - **Draw:** $0.0$
- If the rollout reaches the horizon without a knockout, the state is evaluated using Module 10's heuristic evaluator:
  $$\text{reward} = \text{evaluate\_state}(S_{\text{horizon}}, \text{player\_id}).\text{mcts\_reward} \in [-0.85, +0.85]$$
  Because nonterminal rewards are strictly clamped to $[-0.85, +0.85]$, nonterminal rollouts **never** equal or outrank actual terminal outcomes.

### Phase 4: Backpropagation
The resulting reward $R \in [-1.0, +1.0]$ is backpropagated up the traversal path:
- Every state node along the path increments its visit count: `s_node.visits += 1`.
- Every action node along the path increments its visit count and accumulates the reward:
  $$a\_node.\text{visits} += 1$$
  $$a\_node.\text{total\_reward} += R$$

---

## 3. Final Decision Policy & Tie-Breaking

After completing all configured simulation iterations:
1. **Primary Criterion (Highest Visit Count):**
   $$a^* = \arg\max_{a} n_a$$
   In MCTS, visit count reflects the most robust, thoroughly validated action, avoiding sensitivity to outliers in average reward.
2. **First Tie-Break (Average Reward):** If two actions share the identical visit count, choose the action with the higher average reward:
   $$Q_a / n_a$$
3. **Second Tie-Break (Canonical Action Priority):** If visit counts and average rewards are identical within $10^{-6}$, choose the action appearing earlier in canonical `ORDERED_ACTIONS`:
   $$\text{CHARGE} \succ \text{ATTACK} \succ \text{GUARD} \succ \text{DODGE} \succ \text{SPECIAL\_SPIN}$$

---

## 4. Opponent Model Assumptions and Limitations

1. **Uniform Legal Sampling:** Cyclone models the opponent as selecting uniformly among legal actions during expansion and rollouts.
2. **No Mind-Reading Guarantee:** Cyclone does **not** predict the opponent's true hidden choice. Like Ironclad, Cyclone receives only the immutable public state snapshot and has zero access to the match controller's pending actions.
3. **Model Limitations:** Against an opponent with heavily biased or predictable habits, uniform modeling may under-exploit specific weaknesses, but provides robust, generalizable performance across diverse matchups.

---

## 5. Reproducibility & RNG Isolation

To ensure 100% deterministic test verification and reproducible tournament benchmarks:
- Cyclone instantiates an isolated local `random.Random(seed)` instance.
- It **never** invokes or mutates Python's global `random` module state.
- Injected seeds guarantee identical trees, visit distributions, and decisions across runs.

---

## 6. Empirical Performance Benchmarks

Measured on standard 64-bit Python 3.12 under the default match state ($r = 10.0$, balanced blades at distance $4.0$):

| Difficulty Preset | Iterations | Execution Time | Chosen Action | Action Visit Distribution |
| :--- | :---: | :---: | :---: | :--- |
| **`EASY`** | 50 | $20.99\text{ ms}$ | `ATTACK` | C: 11, A: 12, G: 9, D: 10, S: 8 |
| **`MEDIUM`** | 200 | $80.31\text{ ms}$ | `GUARD` | C: 53, A: 36, G: 62, D: 29, S: 20 |
| **`HARD`** | 500 | $201.09\text{ ms}$ | `DODGE` | C: 130, A: 82, G: 110, D: 138, S: 40 |

---

## 7. Public Python API

```python
from blade_arena.ai import (
    CycloneAgent,
    CycloneConfig,
    CycloneDifficulty,
    choose_cyclone_action,
    decide_cyclone,
)

# 1. Stateless functional decision (plain Action)
action = choose_cyclone_action(match_state, "player_1")

# 2. Functional decision with diagnostic telemetry
action, decision = choose_cyclone_action(match_state, "player_1", return_diagnostics=True)
print(f"Action: {decision.action.name}")
print(f"Iterations: {decision.iterations_completed}")
print(f"Visits: {decision.action_visits}")
print(f"Time: {decision.decision_time_seconds * 1000:.2f} ms")

# 3. Object-oriented agent wrapper with fixed seed
agent = CycloneAgent(
    player_id="player_1",
    difficulty=CycloneDifficulty.MEDIUM,
    config=CycloneConfig(iterations=200, seed=42),
)
action = agent.choose_action(match_state)
```
