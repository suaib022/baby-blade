# BLADE ARENA — Final Project Showcase & Submission Guide

## 1. Project Overview & Deliverables

**BLADE ARENA** is an AI-powered 2D spinning-top battle game built in Python using **Pygame Community Edition (`pygame-ce`)** for a university AI Lab curriculum. The system combines deterministic simultaneous turn-based physical combat with classical AI techniques:

1. **Ironclad AI**: Depth-limited Minimax with iterative deepening, alpha-pruning, and simultaneous-action conservatism.
2. **Cyclone AI**: Monte Carlo Tree Search (MCTS) with simultaneous-action branch selection, UCB1 balancing, and rollout simulations.
3. **Mamdani Fuzzy Logic**: Dynamic threat assessment estimating situational risk from edge proximity and residual energy.
4. **Interactive 2D Visual Experience**: A complete 60 FPS Pygame GUI with Main Menu, Match Setup, Battle Viewport, Live HUD, Procedural Tops, Combat VFX, Results Debriefing, and Tournament Runner.
5. **Headless Multi-Match Tournament Engine**: Reproducible seeded experimentation with alternating side assignments, telemetry logging, and CSV/JSON output.

---

## 2. AI Architecture Summary

```
                      ┌────────────────────────────────────────┐
                      │             Game State                 │
                      │  (Positions, Blades, Stadium, Time)   │
                      └──────────────────┬─────────────────────┘
                                         │
                 ┌───────────────────────┼──────────────────────┐
                 ▼                       ▼                      ▼
      ┌────────────────────┐  ┌────────────────────┐  ┌───────────────────┐
      │  Ironclad Minimax  │  │   Cyclone MCTS     │  │   Mamdani Fuzzy   │
      │ • Iterative Deep.  │  │ • UCB1 Selection   │  │ • 4-Rule Base     │
      │ • Alpha-Pruning    │  │ • Rollout Sim      │  │ • Edge/Energy MFs │
      │ • Matrix Worst-Case│  │ • Simultaneous Opp.│  │ • Centroid Defuzz │
      └────────────────────┘  └────────────────────┘  └───────────────────┘
```

### 2.1 Ironclad AI (Minimax with Matrix Conservatism)
- **Mathematical Principle**: At each decision node, Ironclad evaluates all legal action pairs $(a_1, a_2) \in \mathcal{A}_1 \times \mathcal{A}_2$. For each candidate action $a_1$, it assumes the opponent selects the counter-action $a_2$ that minimizes Player 1's utility:
  $$\nu(a_1) = \min_{a_2 \in \mathcal{A}_2} \mathcal{H}(\text{resolve}(s, a_1, a_2))$$
  Ironclad then chooses the action maximizing this worst-case outcome:
  $$a_1^* = \arg\max_{a_1 \in \mathcal{A}_1} \nu(a_1)$$
- **Pruning & Iterative Deepening**: Alpha-pruning is applied across depth levels. An iterative deepening loop guarantees that if a search timeout occurs, the best action from the deepest fully completed depth level is returned.

### 2.2 Cyclone AI (Monte Carlo Tree Search)
- **Tree Policy**: Uses the Upper Confidence Bound for Trees (UCB1) formula to balance exploration and exploitation:
  $$\text{UCB1}(v) = \frac{Q(v)}{N(v)} + C \sqrt{\frac{\ln N(\text{parent})}{N(v)}}$$
- **Simultaneous Action Modeling**: Tree nodes represent simultaneous turn transitions. Opponent replies during rollout simulations are modeled using a lightweight stochastic simulation policy with isolated RNG seeding to guarantee thread and replay safety.

### 2.3 Mamdani Fuzzy Danger Estimation
- **Linguistic Inputs**:
  - `Energy Ratio`: Trapezoidal/Triangular membership functions (`LOW`, `MEDIUM`, `HIGH`).
  - `Edge Safety`: Proximity to the shrinking stadium boundary (`NEAR`, `MEDIUM`, `SAFE`).
- **Rulebase**:
  1. If Energy is LOW and Edge is NEAR $\to$ Danger is CRITICAL.
  2. If Energy is LOW and Edge is MEDIUM $\to$ Danger is HIGH.
  3. If Energy is MEDIUM and Edge is NEAR $\to$ Danger is HIGH.
  4. If Energy is HIGH and Edge is SAFE $\to$ Danger is LOW.
- **Defuzzification**: 201-point discretized Centroid defuzzification producing an interpretable continuous score $[0, 100]$ mapped to accessible non-color-only UI badges (`LOW`, `MED`, `HIGH`, `CRIT`).

---

## 3. Demonstration & Video Capture Checklist

For university presentation and demonstration submissions, record gameplay covering these five core scenarios:

### Scenario 1: Main Menu & Interactive Match Setup
- [ ] Launch application: `python main.py`.
- [ ] Show menu navigation via number keys (`1–5`) and mouse hover highlights.
- [ ] Select **Human vs AI** (`[1]`).
- [ ] Demonstrate interactive toggle controls:
  - Toggle Human starting side: Player 1 (Left) vs Player 2 (Right).
  - Select blade archetypes: Attacker vs Defender.
  - Select stadium variation: Ice Rink (1.25× movement/push) or Steep Bowl (inward drift).
- [ ] Press `[Enter]` or click "START MATCH".

### Scenario 2: Human vs AI Live Battle & Legality Enforcement
- [ ] Show real-time circular arena with rotating procedural tops.
- [ ] Show HUD elements: Energy and Stability progress bars, Mamdani danger rating badge (`LOW`/`MED`/`HIGH`/`CRIT`), round counter, and countdown timer.
- [ ] **Legality Demonstration**:
  - Show Action Buttons `[1]` to `[5]`.
  - Execute Special Spin (`[5]`), observe energy drop and immediate cooldown timer on the button (e.g. `CD: 2.1s`).
  - Attempt to click disabled action; verify action is rejected with explicit reason displayed on button.
- [ ] Show combat VFX: spark impact burst on collision, dodge ghost trails on evasion.
- [ ] Press `[P]` to pause/resume; press `[ESC]` to return to menu.

### Scenario 3: AI vs AI Autonomous Duel
- [ ] From Main Menu, select **AI vs AI** (`[2]`).
- [ ] Configure Ironclad (Minimax) vs Cyclone (MCTS) in Steep Bowl.
- [ ] Start match (`[Space]`).
- [ ] Demonstrate playback controls:
  - Press `[Space]` to pause and resume.
  - Press `[S]` to step forward exactly one round.
  - Click speed toggles `[1x]`, `[2x]`, `[4x]` to showcase high-speed automated evaluation.
  - Press `[W]` to demonstrate side swapping.
- [ ] Let match resolve to completion and observe victory banner and "VIEW MATCH RESULTS" button.

### Scenario 4: Post-Match Debriefing & Audit
- [ ] Inspect Result Screen:
  - Verify winner name and finish reason badge (Ring-Out, Burst, Spin-Out, Points Decision).
  - Show points score breakdown and round completion metrics.
  - Demonstrate "Play Again" (`[R]`), "Match Setup" (`[S]`), and "Main Menu" (`[ESC]`).

### Scenario 5: In-App Tournament Benchmark & Export
- [ ] From Main Menu, select **Tournament** (`[3]`).
- [ ] Select match count (e.g. 10 matches), Ironclad vs Cyclone, and start batch (`[Space]`).
- [ ] Observe live progress bar and dynamic scorecard updating per frame without UI freeze.
- [ ] Click `[C]` Cancel to demonstrate graceful partial run preservation.
- [ ] Click `[E]` Export to generate `tournament_summary.csv` and `summary.json`.

---

## 4. Benchmark Summary Table

Results from the standardized 50-match evaluation between Ironclad (Minimax) and Cyclone (MCTS) on Balanced blades in Classic Dish (seeds $1000–1049$):

| Evaluation Metric | Ironclad (Minimax, $d=1$) | Cyclone (MCTS, $N=50$) | Notes |
| :--- | :--- | :--- | :--- |
| **Wins** | **36** (72.0%) | **9** (18.0%) | 5 Draws (10.0% simultaneous) |
| **Wins as P1 (Left)** | **19 / 25** (76.0%) | **7 / 25** (28.0%) | P1 advantage mitigated by swap |
| **Wins as P2 (Right)** | **17 / 25** (68.0%) | **2 / 25** (8.0%) | Symmetrical starting distance |
| **Mean Decision Latency** | **2.88 ms** | **12.03 ms** | Ironclad is $4.18\times$ faster |
| **Primary Victory Cause** | Stability Burst (25) | Points Decision (19) | Minimax minimizes damage |

---

## 5. Quality Assurance & Verification Summary

### Automated Testing Suite
- **Total Test Cases**: 338 passing tests in `tests/`.
- **Execution Time**: ~18 seconds.
- **Coverage Scope**:
  - Models & Immutability: `test_game_state.py`, `test_blade_definitions.py`, `test_settings.py`.
  - Rules & Mechanics: `test_actions.py`, `test_geometry.py`, `test_movement.py`, `test_combat.py`, `test_win_conditions.py`, `test_stadium_variations.py`.
  - AI Engines: `test_fuzzy_danger.py`, `test_ai_heuristic.py`, `test_ironclad_minimax.py`, `test_cyclone_mcts.py`.
  - Orchestration & Batch: `test_match_controller.py`, `test_game_modes.py`, `test_tournament.py`.
  - Presentation & App Shell: `test_app_smoke.py`, `test_ui_interface.py`.

### Headless Verification Commands
```powershell
# Run full automated test suite
.\.venv\Scripts\python.exe -m pytest -v

# Run application headless smoke test (60 frames)
.\.venv\Scripts\python.exe main.py --smoke-test

# Run headless 10-match benchmark batch with log export
.\.venv\Scripts\python.exe main.py --batch 10 --save-logs
```

---

## 6. Submission & Delivery Packaging

1. **Repository Cleanliness**:
   - Ensure virtual environment (`.venv/`) and bytecode (`__pycache__/`) are excluded via `.gitignore`.
   - Verify `requirements.txt` contains only runtime dependencies (`pygame-ce`) and `requirements-dev.txt` contains test dependencies (`pytest`).
2. **Execution Independence**:
   - The game engine and AI algorithms have zero dependencies on Pygame and can be executed headlessly or embedded in automated grading harnesses.
3. **Reproducibility**:
   - Every experiment, batch match, and simulation rollout is deterministically reproducible from integer seeds.
