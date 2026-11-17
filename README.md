# BLADE ARENA

A 2D spinning-top battle game in Python with Pygame Community Edition (`pygame-ce`), developed as a university AI Lab project.

> **Status Notice:** **All 16 modules** of the master specification are fully implemented and verified. The project includes an interactive 60 FPS Pygame GUI (Main Menu, Match Setup, Battle Viewport with live Mamdani fuzzy danger indicators, procedural spinning tops, combat VFX, HUD diagnostics, Results debriefing, and Tournament Dashboard) alongside pure headless AI engines (Ironclad Minimax, Cyclone MCTS), reproducible batch evaluation, and telemetry logging (JSON/CSV).

---

## 1. Software Requirements

- **Python:** 3.11 or 3.12 (64-bit recommended)
- **Game Engine:** Pygame Community Edition (`pygame-ce>=2.5.0,<2.6.0`)
- **Test Framework:** `pytest>=8.0.0,<10.0.0`

> **Important:** Always install `pygame-ce` and never `pygame`. Both share the `pygame` import namespace. Installing standard `pygame` alongside `pygame-ce` in the same virtual environment will corrupt the installation.

---

## 2. Environment Setup

### Windows (PowerShell)

```powershell
# Create a virtual environment with Python 3.11 or 3.12
python -m venv .venv

# Activate the virtual environment
.\.venv\Scripts\Activate.ps1

# Upgrade pip
python -m pip install --upgrade pip
```

### macOS and Linux (Bash/Zsh)

```bash
# Create a virtual environment with Python 3.11 or 3.12
python3 -m venv .venv

# Activate the virtual environment
source .venv/bin/activate

# Upgrade pip
python -m pip install --upgrade pip
```

---

## 3. Dependency Installation

### Runtime Dependencies Only

For running the game shell and graphical application:

```bash
pip install -r requirements.txt
```

### Development and Testing Dependencies

For developing and running test suites:

```bash
pip install -r requirements-dev.txt
```

---

## 4. Running the Application

### Interactive 2D Application

Launches the 960x640 visual interface running at a target 60 FPS:

```bash
python main.py
```

- **Main Menu Navigation:** Use number keys `1–5` or mouse clicks.
- **In-Battle Controls:**
  - Human Actions: `[1]` Charge, `[2]` Attack, `[3]` Guard, `[4]` Dodge, `[5]` Special Spin.
  - Utilities: `[P]` Pause / Resume, `[R]` Restart, `[ESC]` Menu.
  - AI vs AI: `[Space]` Play / Pause, `[S]` Step 1 Round, `[1x / 2x / 4x]` Speed toggles, `[W]` Swap Sides.
- **Exit:** Click the window close button (`X`) or press `ESC` on the main menu.

### Headless Tournament Batch CLI

Execute reproducible multi-match tournament experiments without physical display requirements:

```bash
# Run a 10-match series between Ironclad and Cyclone
python main.py --batch 10

# Run a 50-match benchmark with log exports
python main.py --batch 50 --agent1 ironclad --agent2 cyclone --diff1 easy --diff2 easy --seed 1000 --save-logs --out-dir docs/benchmark_results
```

### Headless Smoke Test

Runs the real game loop for a fixed number of frames (default: 60 frames) using SDL's dummy video and audio drivers:

```bash
python main.py --smoke-test
python main.py --smoke-test --frames 120
```

---

## 5. Running Automated Tests

Run the complete 338-test pytest suite:

```bash
python -m pytest -v
```

All automated tests use SDL's dummy drivers and run cleanly in headless environments (such as CI runners and remote servers).

---

## 6. Project Architecture and Directory Structure

```text
blade-arena/
├── .agents/
│   └── skills/                  # Installed agent development skills
├── blade_arena/
│   ├── __init__.py              # Package initialization
│   ├── app.py                   # Application shell and scene manager
│   ├── settings.py              # Centralized configuration and display settings
│   ├── ai/                      # Classical AI decision agents
│   │   ├── __init__.py
│   │   ├── cyclone.py           # Monte Carlo Tree Search AI with UCB1 and isolated RNG
│   │   └── ironclad.py          # Minimax AI with iterative deepening and alpha-pruning
│   ├── game/                    # Pure-Python domain models and match coordinator
│   │   ├── __init__.py
│   │   ├── actions.py           # Action definitions, costs, cooldowns, and legality
│   │   ├── blade_definitions.py # Single source of truth for blade archetypes
│   │   ├── combat.py            # Combat resolution, hit detection, damage, knockback
│   │   ├── fuzzy_danger.py      # Mamdani fuzzy danger inference engine
│   │   ├── geometry.py          # Vector math, boundary queries, stadium shrink schedule
│   │   ├── heuristic.py         # Shared AI heuristic evaluation and MCTS rewards
│   │   ├── initial_state.py     # Match and blade factory functions
│   │   ├── match_controller.py  # Simultaneous turn coordination and lifecycle
│   │   ├── models.py            # Positions, blade states, stadium, actions, results
│   │   ├── movement.py          # Pure planned movement, dodge candidate selection, evasion
│   │   ├── resolver.py          # RoundResolver protocol and RoundRecord
│   │   ├── stadium_definitions.py# Single source of truth for stadium variations
│   │   └── win_conditions.py    # Terminal state evaluation, points decision, tiebreaks
│   ├── orchestration/           # Session management and multi-agent coordination
│   │   ├── __init__.py
│   │   ├── batch_runner.py      # Headless tournament batch runner and CSV/JSON exporter
│   │   ├── participants.py      # Participant protocol, Human/AI wrappers, agent factories
│   │   └── session.py           # MatchSession, lifecycle controls, side swap, step execution
│   └── ui/                      # Pygame visual experience and interactive scenes
│       ├── __init__.py
│       ├── renderer.py          # ArenaRenderer, BladeRenderer, CombatVFX particle systems
│       ├── theme.py             # Colors, typography, fonts, danger styles, button themes
│       ├── widgets.py           # Button, Panel, ProgressBar, ToggleGroup components
│       └── scenes/              # Scene state machine views
│           ├── __init__.py
│           ├── base.py          # Scene abstract base class
│           ├── battle.py        # BattleScene with real-time arena, tops, HUD, and controls
│           ├── main_menu.py     # MainMenuScene with keyboard navigation (1-5, ESC)
│           ├── result.py        # ResultScene debriefing, statistics, and replay
│           ├── settings.py      # SettingsScene runtime parameters and specs
│           ├── setup.py         # MatchSetupScene interactive match configuration
│           └── tournament.py    # TournamentScene interactive batch runner and dashboard
├── docs/
│   ├── actions.md               # Action definitions, costs, and legality contract
│   ├── ai_heuristic.md          # Shared AI heuristic, terminal dominance, MCTS rewards
│   ├── blade_types.md           # Archetype definitions and statistics matrix
│   ├── combat.md                # Combat resolution, hit detection, damage formulas
│   ├── cyclone_mcts.md          # Cyclone MCTS architecture, UCB1, rollouts, benchmarks
│   ├── final_showcase.md        # University submission checklist, demo scenarios, QA summary
│   ├── fuzzy_danger.md          # Mamdani fuzzy danger estimation system and rules
│   ├── game_modes.md            # Human vs AI, AI vs AI, session lifecycle, batch runner
│   ├── game_state.md            # Core data models and immutability specifications
│   ├── ironclad_minimax.md      # Ironclad Minimax, MAX/MIN formulation, and benchmarks
│   ├── match_flow.md            # Turn flow, simultaneous actions, and resolver API
│   ├── match_results.md         # Win conditions, elimination priority, and points formula
│   ├── project_overview.md      # High-level architecture and AI Lab vision
│   ├── pygame_interface.md      # UI architecture, scenes, HUD, procedural tops, VFX
│   ├── stadium_and_movement.md  # Stadium geometry, boundary margins, planned movement
│   ├── stadium_types.md         # Stadium variations: Classic Dish, Ice Rink, Steep Bowl
│   └── tournament_evaluation.md # Tournament metrics, side fairness, and 50-match benchmark
├── tests/
│   ├── conftest.py              # Pytest headless environment setup
│   ├── test_actions.py          # Action legality, costs, cooldowns, ordering tests
│   ├── test_ai_heuristic.py     # AI heuristic, terminal dominance, MCTS scaling tests
│   ├── test_app_smoke.py        # Subprocess and lifecycle smoke tests
│   ├── test_blade_definitions.py# Blade statistics, validation, and factory tests
│   ├── test_combat.py           # Combat resolution, clashes, recoils, 25 pairs
│   ├── test_cyclone_mcts.py     # Cyclone MCTS, UCB1, reproducibility, and headless match tests
│   ├── test_fuzzy_danger.py     # Fuzzy membership, rules, defuzzification, and monotonicity
│   ├── test_game_modes.py       # Orchestration, Human/AI modes, lifecycle, batch tests
│   ├── test_game_state.py       # Data model validation and immutability tests
│   ├── test_geometry.py         # Vector math, shrink schedule, boundary checks
│   ├── test_ironclad_minimax.py # Ironclad Minimax, iterative deepening, pruning, and fallbacks
│   ├── test_match_controller.py # Turn flow, resolution, and error handling tests
│   ├── test_movement.py         # Toward-target movement, dodge selection, evasion tests
│   ├── test_settings.py         # Configuration integrity unit tests
│   ├── test_stadium_variations.py# Stadium definitions, drift, scaling, and duels
│   ├── test_tournament.py       # Tournament runner, metrics, JSON/CSV logs, and UI tests
│   ├── test_ui_interface.py     # UI widgets, scenes, battle HUD, controls, and VFX tests
│   └── test_win_conditions.py   # Terminal win condition, points, priority, and tiebreak tests
├── .gitignore                   # Python and environment ignore rules
├── main.py                      # CLI and application entry point
├── README.md                    # Project documentation and quickstart
├── requirements.txt             # Runtime dependencies
└── requirements-dev.txt         # Developer and test dependencies
```

---

## 7. Project Roadmap — All 16 Modules Completed

1. **Module 01 (Completed):** Project Foundation and Runnable Game Shell
2. **Module 02 (Completed):** Core Game State and Immutable Data Models
3. **Module 03 (Completed):** Turn and Match Flow Coordination
4. **Module 04 (Completed):** Blade Types and Archetype Statistics
5. **Module 05 (Completed):** Action Definitions and Legality Queries
6. **Module 06 (Completed):** Classic Stadium, Geometry and Movement
7. **Module 07 (Completed):** Combat and Simultaneous Round Resolution
8. **Module 08 (Completed):** Win Conditions and Match Results
9. **Module 09 (Completed):** Mamdani Fuzzy Danger Estimation
10. **Module 10 (Completed):** Shared AI Heuristic Evaluation
11. **Module 11 (Completed):** Ironclad — Minimax AI
12. **Module 12 (Completed):** Cyclone — Monte Carlo Tree Search AI
13. **Module 13 (Completed):** Game Modes and Headless Orchestration
14. **Module 14 (Completed):** Additional Stadium Variations
15. **Module 15 (Completed):** Pygame Interface and Visual Experience
16. **Module 16 (Completed):** Tournament Evaluation, Logs, Final QA and Delivery

---

## 8. Licenses and Asset Attribution

- **Source Code**: Developed from scratch under pure Python 3.12 and Pygame Community Edition standards for academic laboratory delivery.
- **Visual Assets**: 100% original procedurally generated vectors and shapes rendered using Pygame drawing primitives (rotors, rims, accents, particles). No external copyrighted sprites or proprietary art assets were used.
- **Installed Skills**:
  - `pygame-core`, `game-ui-ux`, `create-game-assets`, `game-docs`: Apache-2.0 / MIT licenses.
  - `python-testing`: MIT license.
