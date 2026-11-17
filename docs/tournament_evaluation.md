# BLADE ARENA — Tournament Evaluation and Reproducible AI Benchmark

## 1. Overview and Architecture

Module 16 establishes the tournament evaluation engine, reproducible AI benchmarking system, and telemetry logging infrastructure for **BLADE ARENA**.

The tournament architecture provides:
1. **Headless Batch Runner (`TournamentBatchRunner`)**: Executes configurable multi-match series with alternating starting sides, seeded random number generation, and timeout iteration guards.
2. **Side-Swap Fairness**: To eliminate starting position bias, agents strictly alternate starting sides on odd match indices ($i \pmod 2 = 1$). Both overall win rates and side-specific breakdowns (as Player 1 vs as Player 2) are tracked independently.
3. **Telemetry & Decision Timing**: Captures exact wall-clock decision times for every action chosen by both agents, computing per-agent mean decision duration without fabricated values.
4. **Structured Logging**: Automatically writes per-match detailed JSON audit logs and aggregate CSV summaries to disk with overwrite protection and directory auto-disambiguation.
5. **Interactive UI (`TournamentScene`)**: Provides an in-app visual tournament dashboard with progress monitoring, live analytics, graceful cancellation, and one-click log export.

---

## 2. Metrics and Statistical Methodology

All tournament metrics are computed strictly from completed match data without extrapolation:

| Metric | Mathematical Definition | Interpretation |
| :--- | :--- | :--- |
| **Total Scheduled** | $N_{\text{sched}}$ | Target number of matches configured for the series. |
| **Completed Matches** | $N_{\text{comp}}$ | Number of matches actually resolved before completion or cancellation. |
| **Agent A Win Rate** | $W_A / N_{\text{comp}}$ | Fraction of completed matches won by Agent A. |
| **Agent B Win Rate** | $W_B / N_{\text{comp}}$ | Fraction of completed matches won by Agent B. |
| **Draw Rate** | $D / N_{\text{comp}}$ | Fraction of completed matches ending in a draw. |
| **Agent A as P1 Win Rate** | $W_{A, P1} / M_{A, P1}$ | Win rate of Agent A when assigned Player 1 (Left, $(-2, 0)$). |
| **Agent A as P2 Win Rate** | $W_{A, P2} / M_{A, P2}$ | Win rate of Agent A when assigned Player 2 (Right, $(+2, 0)$). |
| **Average Completed Rounds** | $\frac{1}{N_{\text{comp}}} \sum R_i$ | Mean match duration in discrete combat rounds ($0 \le R \le 40$). |
| **Average Logical Time** | $\frac{1}{N_{\text{comp}}} \sum (R_i \times 3.0\text{s})$ | Mean match duration in simulated game seconds. |
| **Mean Decision Duration** | $\frac{1}{K} \sum_{j=1}^K \Delta t_j$ | Mean wall-clock time in seconds per decision across all live turns. |

### Finish Reason Classifications
Matches terminate under five mutually exclusive primary finish reasons:
- **`RING_OUT`**: Blade was knocked outside the active stadium radius ($r > R_{\text{stadium}}$).
- **`BURST`**: Blade stability was reduced to $0.0$.
- **`SPIN_OUT`**: Blade energy was reduced to $0.0$.
- **`POINTS_DECISION`**: Match reached the 40-round ($120.0\text{s}$) limit without elimination; decided by weighted points formula.
- **`SIMULTANEOUS_ELIMINATION`**: Both blades satisfied terminal elimination conditions in the identical combat round, producing a deterministic draw.

---

## 3. Reproducible Benchmark Experiment

To validate the tournament evaluation system, a reproducible 50-match experiment was conducted comparing **Ironclad (Minimax)** against **Cyclone (MCTS)** under standardized laboratory conditions.

### 3.1 Experimental Configuration
- **Total Matches**: 50 scheduled, 50 completed.
- **Agent A**: Ironclad Minimax (`difficulty="easy"`, search depth budget $d=1$).
- **Agent B**: Cyclone MCTS (`difficulty="easy"`, iteration budget $N=50$ rollouts, exploration constant $C=1.4$, rollout depth $D=6$).
- **Blades**: Balanced vs Balanced (Starting Energy: 100, Starting Stability: 100).
- **Stadium**: Classic Dish (Initial Radius: 10.0m, Shrink Interval: every 6 rounds to min 6.0m).
- **RNG Seeds**: Deterministic range $[1000, 1049]$ (Match $i$ received seed $1000 + i$).
- **Side Assignment**: Strict alternation ($i \pmod 2 = 1$ swapped P1/P2 roles).
- **Hardware / Runtime**: AMD Ryzen / Windows 11 (64-bit), CPython 3.12.13, Pygame-ce 2.5.8.
- **Output Artifacts**: [docs/benchmark_results/summary.json](file:///d:/Projects/baby-blade/docs/benchmark_results/summary.json) and [docs/benchmark_results/tournament_summary.csv](file:///d:/Projects/baby-blade/docs/benchmark_results/tournament_summary.csv).

### 3.2 Measured Experimental Results

```text
====================================================================
HEADLESS TOURNAMENT BATCH SUMMARY (50 MATCHES)
====================================================================
Total Matches  : 50 / 50 (100.0% completion)
Ironclad Wins  : 36 (72.0%)
  As P1 (Left) : 19 / 25 (76.0%)
  As P2 (Right): 17 / 25 (68.0%)
Cyclone Wins   : 9 (18.0%)
  As P1 (Left) : 7 / 25 (28.0%)
  As P2 (Right): 2 / 25 (8.0%)
Draws          : 5 (10.0%) (All simultaneous eliminations)
--------------------------------------------------------------------
FINISH REASONS:
  Stability Bursts   : 25 (50.0%)
  Points Decisions   : 19 (38.0%)
  Simultaneous Draws : 5 (10.0%)
  Energy Spin-Outs   : 1 (2.0%)
  Ring-Out Ejections : 0 (0.0%)
--------------------------------------------------------------------
TIMING & TELEMETRY:
  Average Completed Rounds : 33.9 rounds
  Average Logical Duration : 101.7s (simulated)
  Total Wall-Clock Time    : 25.37s
  Ironclad Mean Decision   : 2.88 ms (1,697 decisions)
  Cyclone Mean Decision    : 12.03 ms (1,697 decisions)
====================================================================
```

### 3.3 Algorithmic Discussion and Analysis
1. **Performance Disparity**:
   Ironclad achieved a $72.0\%$ win rate versus Cyclone's $18.0\%$ with $10.0\%$ draws. This outcome stems from the differing nature of the search algorithms under low computational budgets:
   - **Ironclad Minimax**: Evaluates all immediate simultaneous action pairs ($5 \times 5 = 25$ outcomes) using a depth-1 exhaustive search coupled with the shared heuristic function. Because it directly examines all opponent responses and minimizes maximum damage, Ironclad exhibits disciplined, defensive play.
   - **Cyclone MCTS**: With only 50 simulation rollouts per decision, Cyclone's random rollout policy samples only a fraction of the combinatoric branch space. When opponent actions in rollouts are selected uniformly at random, MCTS can misjudge the risk of aggressive moves (such as charging into an attack), leading to stability depletion.
2. **Side Symmetry**:
   - Ironclad won $76.0\%$ as P1 and $68.0\%$ as P2 (an $8.0\%$ delta).
   - Cyclone won $28.0\%$ as P1 and $8.0\%$ as P2.
   Both agents performed slightly better as Player 1 (starting at $(-2, 0)$). This reinforces the necessity of alternating starting sides to ensure scientific fairness.
3. **Computational Efficiency**:
   Ironclad executed in **2.88 ms** per decision, whereas Cyclone required **12.03 ms** per decision (a $4.18\times$ compute difference). Depth-limited Minimax is significantly faster than tree-based random rollouts in this state space.

---

## 4. Structured Output Formats

### 4.1 CSV Summary Schema (`tournament_summary.csv`)
Columns:
- `match_index`: Integer 1-based index.
- `seed`: Random seed passed to stochastic agents.
- `player_1_name`, `player_2_name`: Names of participants.
- `p1_blade`, `p2_blade`: Archetypes (`BALANCED`, `ATTACKER`, `DEFENDER`, `STAMINA`).
- `stadium`: Stadium environment (`CLASSIC_DISH`, `ICE_RINK`, `STEEP_BOWL`).
- `winner_name`, `winner_player_id`: Winning agent and ID (`player_1`, `player_2`, or `DRAW`).
- `finish_reason`: FinishReason enum name.
- `completed_rounds`: Total rounds played ($1–40$).
- `elapsed_logical_seconds`: Logical match time ($R \times 3.0$).
- `p1_points`, `p2_points`: End-of-match weighted scores.
- `wall_clock_seconds`: Wall-clock execution time of the match.
- `p1_decisions`, `p1_mean_decision_seconds`: Player 1 decision count and mean latency.
- `p2_decisions`, `p2_mean_decision_seconds`: Player 2 decision count and mean latency.

### 4.2 Per-Match JSON Log Schema (`matches/match_XXX.json`)
```json
{
  "version": "1.0.0",
  "match_index": 1,
  "seed": 1000,
  "timestamp": "2026-11-17T21:34:00.123456",
  "configuration": {
    "stadium": "CLASSIC_DISH",
    "player_1": {"name": "Ironclad (easy)", "blade": "BALANCED", "budget": 1},
    "player_2": {"name": "Cyclone (easy)", "blade": "BALANCED", "budget": 50}
  },
  "outcome": {
    "winner_name": "Ironclad (easy)",
    "winner_id": "player_1",
    "finish_reason": "BURST",
    "p1_causes": ["BURST"],
    "p2_causes": [],
    "p1_final_points": 0.32,
    "p2_final_points": 0.24
  },
  "timing": {
    "completed_rounds": 24,
    "elapsed_logical_seconds": 72.0,
    "wall_clock_seconds": 0.3878
  },
  "telemetry": {
    "p1_decisions": 24,
    "p1_total_decision_time": 0.082,
    "p1_mean_decision_time": 0.0034,
    "p2_decisions": 24,
    "p2_total_decision_time": 0.305,
    "p2_mean_decision_time": 0.0127
  },
  "rounds": [
    {
      "round": 1,
      "p1_action": "ATTACK",
      "p2_action": "GUARD",
      "p1_stability": 98.0,
      "p1_energy": 92.0,
      "p2_stability": 96.0,
      "p2_energy": 96.0,
      "stadium_radius": 10.0
    }
  ]
}
```

---

## 5. CLI Execution & Reproduction

To reproduce the 50-match tournament experiment headlessly:

```bash
python main.py --batch 50 --agent1 ironclad --agent2 cyclone --diff1 easy --diff2 easy --seed 1000 --save-logs --out-dir docs/benchmark_results
```
