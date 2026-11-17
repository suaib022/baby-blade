# BLADE ARENA — Pygame Interface and Visual Experience

## 1. Overview and Architecture

Module 15 delivers a complete, interactive, and original 2D visual application built on **Pygame Community Edition** (`pygame-ce 2.5.8`). The UI directly interfaces with the authoritative match orchestration and rules engine without reimplementing game rules or displaying placeholder/mock data.

The application adheres to a clean separation of concerns:
- **Engine & Orchestration Layer** (`blade_arena/game/`, `blade_arena/orchestration/`): 100% pure Python, headless, deterministic, and immutable.
- **Visual Presentation Layer** (`blade_arena/ui/`): Handles rendering, input event routing, procedural top animations, combat VFX, and HUD diagnostics.
- **Application Shell** (`blade_arena/app.py`): Manages the Pygame lifecycle, frame limiting (60 FPS), scene transitions, and headless execution flags (`--smoke-test`, `--batch`).

---

## 2. Display Resolution and Theme

- **Window Dimensions**: 960 × 640 pixels (fixed 2D layout).
- **Target Framerate**: 60 FPS (V-Sync / clock-capped).
- **Typography**: Scalable system sans-serif font (`segoeui,helvetica,arial`) with centralized caching and automatic invalidation handling on display restarts.
- **Color Theme**: High-contrast dark arena palette:
  - Background: Deep Navy (`#0F121C`, `(15, 18, 28)`)
  - Container Panels: Midnight Blue (`#181D2C`, `(24, 29, 44)`) with borders (`#2D3750`)
  - Player 1 Accent: Electric Blue / Cyan (`#40A9FF`, `(64, 169, 255)`)
  - Player 2 Accent: Crimson / Coral (`#FF4D4F`, `(255, 77, 79)`)
  - Text: High-contrast white (`#F0F3F6`), gold highlights (`#FADB14`), and muted metadata (`#6E7D91`).

---

## 3. UI Scenes and Navigation Graph

The application uses an object-oriented Scene protocol (`blade_arena/ui/scenes/base.py`):

```
       ┌─────────────── MainMenuScene ───────────────┐
       │     (1: Human, 2: AI, 3: Tourn, 4: Set, 5: Quit)     │
       └───────┬──────────────┬──────────────┬───────┘
               │              │              │
               ▼              ▼              ▼
       MatchSetupScene  TournamentInfo  SettingsScene
               │        (Module 16 info)  (System stats)
       [Start Match]
               ▼
          BattleScene <───────┐
               │              │ [Play Again / Restart]
       [Match Concluded]      │
               ▼              │
          ResultScene ────────┘
```

### 3.1 Main Menu (`MainMenuScene`)
- Five accessible options with keyboard shortcuts:
  - `[1]` **Human vs AI**: Opens match setup pre-configured for player-vs-agent battles.
  - `[2]` **AI vs AI**: Opens match setup pre-configured for autonomous agent duels.
  - `[3]` **Tournament**: Displays headless batch runner availability and Module 16 preview.
  - `[4]` **Settings**: Displays resolution, framerate, and engine specifications.
  - `[5 / ESC]` **Quit**: Cleanly terminates the application loop.

### 3.2 Match Setup (`MatchSetupScene`)
- **Game Mode Toggle**: Switch between Human vs AI and AI vs AI.
- **Human vs AI Options**:
  - Human Starting Side: Player 1 (Left) or Player 2 (Right).
  - Human Blade Archetype: Balanced, Attacker, Defender, Stamina.
  - AI Opponent Architecture: Ironclad (Minimax) or Cyclone (MCTS).
  - AI Opponent Difficulty: Easy, Medium, Hard.
  - AI Blade Archetype: Balanced, Attacker, Defender, Stamina.
- **AI vs AI Options**:
  - Independent Agent 1 and Agent 2 Architecture, Difficulty, and Blade Archetypes.
- **Stadium Environment**:
  - Classic Dish (baseline).
  - Ice Rink (1.25× action movement and push distance).
  - Steep Bowl (0.3m inward slope drift capped at origin).
- **Controls**: `[Enter]` Start Match, `[ESC]` Back to Main Menu.

### 3.3 Battle Viewport (`BattleScene`)
- **Arena Rendering (`ArenaRenderer`)**:
  - Translates Cartesian arena units ($x, y$) to screen pixels ($1\text{ unit} = 24\text{px}$).
  - Draws stadium floor textures, concentric elevation rings, and live boundary circle based on `stadium.radius` ($10.0\text{m} \to 6.0\text{m}$).
- **Blade Rendering (`BladeRenderer`)**:
  - Procedurally generated multi-layer spinning tops (no external image assets required).
  - Outer metallic notched rotor rim, colored player accent ring, and core archetype gem.
  - Angular velocity ($\omega$) dynamically scales with current stability, slowing down as stability wanes.
- **Combat Visual Effects (`CombatVFX`)**:
  - Attack impact spark rings and rays when blades clash or deal damage.
  - Dodge ghost trails showing evasion trajectories.
  - Boundary shrink warning pulses when stadium radius contracts.
- **HUD (Heads-Up Display)**:
  - Top Bar: Match mode, stadium type, round counter ($0–40$), and logical countdown ($120.0\text{s} \to 0.0\text{s}$).
  - P1 & P2 Panels: Archetype badges, Energy bars, Stability bars.
  - **Mamdani Fuzzy Danger**: Live numerical score ($0–100$) accompanied by an accessible, non-color-only text badge (`LOW`, `MED`, `HIGH`, `CRIT`).
  - Special Spin Status: Displays "READY" or active countdown (e.g. `CD: 3.2s`).
  - AI Diagnostics: Displays the AI's last action, evaluation score, or visit count.
  - Combat Log: Chronological audit trail of the last 7 combat events (clashes, pushes, dodges, damage, boundary shrinks).

### 3.4 Controls & Input Modes
- **Human vs AI Controls**:
  - 5 Action buttons and keys `[1]` Charge, `[2]` Attack, `[3]` Guard, `[4]` Dodge, `[5]` Special Spin.
  - **Shared Legality Enforcement**: Disables illegal action buttons and displays an explicit reason label (e.g., `"Insufficient energy for Attack: requires 8.0, available 2.0"` or `"Special Spin on cooldown (ready at 21.0s)"`).
  - **Secret Commit**: The human choice is queued privately; the AI decision is computed using the identical pre-round snapshot and never previews human input.
  - `[P]` Pause / Resume, `[R]` Restart, `[ESC]` Menu.
- **AI vs AI Controls**:
  - `[Space]` Play / Pause continuous execution.
  - `[S]` Single-step forward exactly one round.
  - `Speed Toggle [1x] [2x] [4x]`: Adjusts animation delay ($0.50\text{s}$, $0.25\text{s}$, $0.08\text{s}$ per round). Modifies display timing only—never affects logical match time, engine rules, or AI search budgets.
  - `[W]` Swap Sides (swaps player assignments and cleanly restarts).
  - `[R]` Restart Match.
  - `[ESC]` Menu.

### 3.5 Match Result (`ResultScene`)
- Displays authoritative match outcome from `state.result`.
- Winner banner with player accent colors or draw announcement.
- Primary finish reason: Ring-Out, Burst, Spin-Out, Simultaneous Elimination, or Points Decision.
- Points breakdown (P1 score vs P2 score) if match reached round 40.
- Final statistics: completed rounds, logical duration, and remaining energy/stability.
- Navigation buttons: `[R]` Play Again, `[S]` Match Setup, `[ESC]` Main Menu.

### 3.6 Tournament Information (`TournamentInfoScene`)
- Clearly informs the user:
  > *"Batch runner available; detailed results coming in Module 16."*
- Explains the CLI headless batch runner command (`python main.py --batch N`).
- Previews Module 16 interactive tournament dashboard and experiment logging without fabricating placeholder data.

### 3.7 Settings Screen (`SettingsScene`)
- Displays display resolution ($960 \times 640$), framerate (60 FPS), Pygame-ce version, rules engine specifications, and AI algorithms.

---

## 4. Headless Testing and Verification

- The entire visual experience is 100% testable headlessly via `SDL_VIDEODRIVER=dummy` and `SDL_AUDIODRIVER=dummy`.
- Automated test suite `tests/test_ui_interface.py` verifies:
  1. Widget states: Button hover, clicks, hotkeys, disabled tooltips, ProgressBars, Panels, and ToggleGroups.
  2. Coordinate mapping: bidirectional arena-to-screen and screen-to-arena conversions.
  3. All three stadium variations rendering without errors.
  4. Scene transitions across Main Menu, Setup, Battle, Result, Tournament, and Settings.
  5. Action legality validation and button disabling in Human vs AI mode.
  6. AI vs AI controls: single-step, speed toggles, side swap, pause/resume, and autoplay.
  7. Combat VFX update and expiration cycles.
  8. Application lifecycle integration and smoke test frame limits.
