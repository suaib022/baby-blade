# BLADE ARENA — Game Modes and Headless Orchestration

> **Status Notice:** This document specifies **Module 13: Game Modes and Headless Orchestration**. It defines reusable session coordination for **Human vs. AI** and **AI vs. AI** modes, participant abstractions, lifecycle management, action privacy guarantees, and the headless batch runner. Graphical user interface (GUI) rendering is delivered in **Module 15**, and full tournament analytics and logging are delivered in **Module 16**.

---

## 1. Architectural Overview

The orchestration layer bridges pure domain rules (the `MatchController` and `ClassicDishRoundResolver`) and player decision entities (human operators and autonomous AI agents).

```
                        +----------------------+
                        |     MatchSession     |
                        +----------+-----------+
                                   |
         +-------------------------+-------------------------+
         |                                                   |
         v                                                   v
+------------------+                               +------------------+
|  Participant 1   |                               |  Participant 2   |
| (Human / AI Bot) |                               | (Human / AI Bot) |
+--------+---------+                               +--------+---------+
         |                                                   |
         | Action a1 (via snapshot S)                       | Action a2 (via snapshot S)
         |                                                   |
         +-------------------------+-------------------------+
                                   |
                                   v
                        +----------------------+
                        |   MatchController    |
                        | (Enforces Legality,  |
                        | Resolves via Rules)  |
                        +----------------------+
```

### Core Design Principles
1. **Pygame Independence:** The orchestration layer operates strictly in pure Python without importing or initializing Pygame, enabling fast headless simulations, automated testing, and CI batch runs.
2. **Action Privacy Guarantee:** Both participants deliberate using an identical pre-round immutable `MatchState` snapshot. Neither participant's committed action is disclosed or leaked to the opponent prior to simultaneous resolution.
3. **Non-Blocking Operation:** `HumanParticipant` does not halt execution waiting for console or keyboard input. The caller stages an action via `queue_action()` or passes `human_action` directly to `step_round()`.
4. **Resilient Error Recovery:** Illegal action submissions are rejected immediately via `IllegalParticipantActionError`, leaving pre-round state unmodified and allowing action re-selection without corrupting the session.

---

## 2. Participant Abstraction

All combat decision-makers implement the `Participant` protocol:

```python
class Participant(Protocol):
    @property
    def name(self) -> str: ...
    @property
    def is_human(self) -> bool: ...
    @property
    def last_diagnostics(self) -> Optional[Any]: ...
    def choose_action(self, state: MatchState, player_id: str) -> Action: ...
```

### Concrete Implementations

- **`HumanParticipant`**:
  - Represents a human operator.
  - Caller stages actions via `queue_action(action: Action)`.
  - `choose_action()` consumes the staged action. If no action was staged, it raises `HumanActionRequiredError`.
- **`AIParticipant`**:
  - Wraps autonomous agents (`IroncladAgent`, `CycloneAgent`, or any custom callable).
  - Dynamically aligns agent perspective with `player_id`.
  - Captures full diagnostic telemetry (`IroncladDecision` or `CycloneDecision`) in `last_diagnostics`.

### Participant Factory

The helper `create_ai_participant()` constructs configured AI participants across difficulty profiles:

```python
participant = create_ai_participant(
    name="CycloneBot",
    agent_type="cyclone",       # 'ironclad' or 'cyclone'
    difficulty="medium",        # 'easy', 'medium', 'hard'
    seed=42,                    # Optional RNG seed for stochastic agents
    player_id="player_2",
)
```

---

## 3. Supported Game Modes

### 1. Human vs. AI (`GameMode.HUMAN_VS_AI`)
- Accommodates a human player competing against either Ironclad or Cyclone.
- **Flexible Side Selection:** The human player may control Player 1 (left spawn at $x = -2.0$) or Player 2 (right spawn at $x = 2.0$).
- **Strict Legality Validation:** Staged actions are validated against the authoritative `check_action_legality()` API before submission.
- **No Silent Fallbacks:** Illegal human actions raise `IllegalParticipantActionError` with descriptive rationale (e.g. insufficient energy or active cooldown). State is preserved for reselection.

### 2. AI vs. AI (`GameMode.AI_VS_AI`)
- Runs autonomous agent pairings (Ironclad vs. Cyclone, Ironclad vs. Ironclad, Cyclone vs. Cyclone, or custom agents).
- **Single-Round Stepping:** `step_round()` collects exactly one decision per participant and resolves at most one combat round.
- **Compute Decoupling:** AI search budgets (Minimax depth, MCTS iterations) are independent of frame rates or animation timings.

---

## 4. Session Lifecycle Controls

`MatchSession` provides deterministic lifecycle management:

| Method | Behavior | Constraints & Notes |
| :--- | :--- | :--- |
| `start()` | Unpauses session if paused; idempotent. | Can step rounds once active. |
| `pause()` | Halts step execution; idempotent. | Calling `step_round()` raises `MatchPausedError`. |
| `resume()` | Restores step capability; idempotent. | Leaves round counter and blade states intact. |
| `restart()` | Resets match state to round 0 and clears step history. | Can be invoked at any time, including after match finish. |
| `swap_sides()` | Swaps player assignments (P1 $\leftrightarrow$ P2) and blade types. | Automatically restarts the session cleanly with inverted sides. |
| `step_round()` | Deliberates, validates legality, and resolves exactly one round. | Raises `MatchFinishedError` if match has concluded. |
| `run_to_completion()`| Continuously executes rounds until termination. | Guarded by `max_rounds_guard` (default: 45 rounds). |

### Iteration Guard
To defend against pathological infinite combat loops (such as mutual endless charging), `MatchSession` enforces a defensive bound `max_rounds_guard` (default: 45 rounds, exceeding the standard 40-round match limit). If a match fails to conclude within this limit, `IterationGuardError` is raised rather than fabricating a result.

---

## 5. Headless Batch Runner

The headless batch runner enables multi-match automated evaluation:

```python
from blade_arena.orchestration import run_headless_batch

summary = run_headless_batch(
    total_matches=10,
    agent_a="ironclad",
    agent_b="cyclone",
    agent_a_difficulty="easy",
    agent_b_difficulty="easy",
    base_seed=1000,
    alternate_sides=True,
    max_rounds_guard=45,
)
```

### Batch Characteristics
- **Seed Assignment:** Each match receives an explicit seed ($S_i = \text{base\_seed} + i$), guaranteeing 100% reproducible outcomes across identical environments.
- **Side Alternation:** On odd match indices ($i = 1, 3, 5, \dots$), Player 1 and Player 2 roles and blade archetypes swap automatically to prevent positional bias.
- **Summary Metrics:** Returns `BatchSummary` with win counts, win percentages, draw counts, and per-match `BatchMatchResult` telemetry (rounds, wall-clock duration, points, finish causes).

---

## 6. Command-Line Interface (CLI)

BLADE ARENA includes a headless batch CLI entry point via `main.py`:

```bash
# Run 10 headless matches between Ironclad and Cyclone
python main.py --batch 10 --agent1 ironclad --agent2 cyclone --diff1 easy --diff2 easy
```

### Sample CLI Output
```text
Running headless batch of 2 matches: Ironclad (easy) vs Cyclone (easy)...
============================================================
HEADLESS BATCH SUMMARY
============================================================
Total Matches : 2
Ironclad Wins : 2 (100.0%)
Cyclone Wins : 0 (0.0%)
Draws         : 0 (0.0%)
------------------------------------------------------------
Match #1: Winner=Ironclad (BURST) Rounds=24 Time=72.0s P1=Ironclad P2=Cyclone Wall=0.39s
Match #2: Winner=Ironclad (BURST) Rounds=30 Time=90.0s P1=Cyclone P2=Ironclad Wall=0.46s
============================================================
```

---

## 7. Current Lack of GUI

> [!NOTE]
> Module 13 delivers domain orchestration and headless batch automation. Graphical scene management, Pygame HUD rendering, visual top animations, and human input keybindings are delivered in **Module 15**.
