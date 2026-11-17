# BLADE ARENA — Complete Antigravity Module Prompts

**16 modules · Python 3.11/3.12 · Pygame Community Edition · pytest**

This file contains a complete, standalone prompt for every module. Paste **one module prompt at a time** into Antigravity, in order. Each prompt repeats the essential project constraints, self-testing requirements and reporting instructions so it can be used independently. Complete and review the current module before moving on. If a previous module is incomplete, tell the agent about the failure rather than pretending it passed.

The PDF is the primary source for gameplay requirements; the presentation is a visual/product reference. PDFs and slides from the Notion chat are not automatically visible to Antigravity. Attach them there if you want it to inspect the originals; the prompts carry the needed rules. Numeric values marked *proposed* are initial tuning choices, not requirements in the PDF. Source differences include Charge and the project/alternate blade names; follow the PDF for gameplay.

## Optional workspace skills

Install selected skills under `.agents/skills/<skill-name>/` before starting, after reviewing their contents and licenses. Copy complete folders with any required references; do not automatically run third-party scripts or hooks. If Antigravity does not discover them, reload the workspace.

- [pygame-core](https://github.com/gamedev-skills/awesome-gamedev-agent-skills/tree/main/skills/other-engines/pygame-core)
- [game-ui-ux](https://github.com/gamedev-skills/awesome-gamedev-agent-skills/tree/main/skills/disciplines/game-ui-ux)
- [create-game-assets](https://github.com/gamedev-skills/awesome-gamedev-agent-skills/tree/main/skills/disciplines/create-game-assets)
- [game-docs](https://github.com/gamedev-skills/awesome-gamedev-agent-skills/tree/main/skills/workflows/game-docs)
- [python-testing](https://github.com/Paldom/python-skills/tree/main/skills/python-testing)

The game-dev collection is Apache-2.0 and the Python skills collection MIT; review their current LICENSE and NOTICE files. Skills guide the work but cannot override the module's requirements.

## Module index

1. Project Foundation and Runnable Game Shell
2. Core Game State and Data Models
3. Turn and Match Flow
4. Blade Types and Statistics
5. Action Definitions and Legality
6. Classic Stadium, Geometry and Movement
7. Combat and Simultaneous Round Resolution
8. Win Conditions and Match Results
9. Mamdani Fuzzy Danger Estimation
10. Shared AI Heuristic Evaluation
11. Ironclad — Minimax AI
12. Cyclone — Monte Carlo Tree Search AI
13. Game Modes and Headless Orchestration
14. Additional Stadium Variations
15. Pygame Interface and Visual Experience
16. Tournament Evaluation, Logs, Final QA and Delivery

---

## Module 01 — Project Foundation and Runnable Game Shell

Copy the complete prompt below into Antigravity.

```text
MODULE 01 OF 16 — PROJECT FOUNDATION AND RUNNABLE GAME SHELL

You are my senior Python game developer and technical lead. Build BLADE ARENA, a university AI Lab 2D spinning-top game, one module at a time. Work only in the current workspace. Preserve existing user files, installed skills and previously working behavior; inspect the code, current documentation and tests first. Run a baseline full test suite and existing headless smoke test before changes when they exist. Report existing failures and fix only those directly related or necessary; do not silently remove assertions or tests.

Use Python 3.11/3.12, pygame-ce (imported as pygame), and pytest. Never install pygame and pygame-ce in the same environment. Keep the pure game engine, AI and headless orchestration independent of Pygame. The final game uses simultaneous actions, one shared deterministic rules engine, Ironclad Minimax, Cyclone MCTS and Mamdani fuzzy logic. Restrict AI algorithms to the course-approved set; do not substitute black-box AI, external APIs or unrelated algorithms. Read relevant installed `pygame-core`, `python-testing`, `game-docs`, `game-ui-ux` or `create-game-assets` skills if available, but do not add tools or run skill scripts automatically. State which skills you actually used.

Do not open an external browser for testing. Do not delete or overwrite unrelated work, push to GitHub, commit, publish, use paid services or start the next module unless explicitly asked. Follow the existing code's actual names where practical, keeping prior public APIs compatible. Document any necessary migration. Clearly label future capabilities and numerical assumptions; do not claim that unfinished features work.

## Objective
Create a clean Python project and a minimal working Pygame window. This is a foundation, not a playable game.

## Scope and implementation
- Inspect the workspace first; preserve `.agents/skills` and any existing user files. Adapt to what exists instead of overwriting work.
- Use Python 3.11 or 3.12, `pygame-ce` imported as `pygame`, and `pytest`. Never install `pygame` and `pygame-ce` together. Keep runtime and test dependencies separate in `requirements.txt` and `requirements-dev.txt`, with documented compatible versions.
- Create a small package such as `blade_arena/` containing `app.py` and `settings.py`; a small root `main.py`; `tests/`; `docs/project_overview.md`; `README.md`; and a Python-appropriate `.gitignore`. Preserve installed skills and do not ignore `.agents/skills` by default.
- Display a 960 × 640 window titled `BLADE ARENA`, at a target 60 FPS, with a dark background and readable text: project title, “AI-Powered Spinning-Top Battle Stadium”, “Module 1: Project Foundation”, and “Press ESC to quit”. No fake gameplay or menus.
- Implement event/update/render loop, frame limiting, QUIT and Escape handling, and Pygame cleanup even on exceptions. Importing a module must not open a window or initialize the display.
- Centralize title, dimensions, FPS and colors in settings. Keep UI code small and extensible without building a scene framework.
- Provide `python main.py --smoke-test`: set SDL's dummy video driver before display initialization, run the real loop for a fixed small number of frames without input, then exit 0; do not swallow exceptions. Normal `python main.py` remains interactive.
- README: Windows and macOS/Linux setup, dependency install, normal run, smoke test, pytest, current structure, planned modules and explicit prototype status. `docs/project_overview.md`: vision, intended modes, AI techniques and architecture; state clearly that gameplay and AI are not implemented. If the attached proposal files are available, inspect them locally without altering them; otherwise rely on this prompt and report the limitation.

## Verification and acceptance
Test positive dimensions/FPS; importing the app in a fresh process does not open a display; smoke mode exits with code 0 under a subprocess timeout; QUIT and Escape close the loop. Run full pytest and smoke command. A visual check on a real display is separate from the headless smoke test. Complete only when requirements work and documentation accurately labels the prototype.

## Scope boundary
Do not implement combat, AI, game models, menus, database, web server, cloud service, generated assets or future features.
## Mandatory self-testing — no external browser
1. Run this module's tests, the complete existing test suite, and the project's documented headless application smoke test. Run any other commands specified above. Use timeouts for commands that can hang.
2. Test normal operation, invalid inputs, important edge cases, and integration with previous modules. Verify every acceptance item above and fix any discovered failures; rerun the affected checks.
3. Test the Pygame application locally, not in an external browser. If a graphical display is available, inspect the relevant local window and controls; if not, explicitly say visual inspection could not be performed. A dummy-driver smoke test is not visual verification.
4. Do not mark a module fully complete if a required test or acceptance criterion failed or could not be verified. State precisely what remains unresolved. Never invent test, benchmark or visual results.

## Final report
Report: files created/changed; skills actually read and used; public APIs and assumptions; exact commands executed; pass/fail/not-run result of each meaningful check; whether local visual inspection occurred; defects fixed; failures and environment limitations; acceptance criteria status; and the exact command to run the full test suite. Stop after this module.
```

---

## Module 02 — Core Game State and Data Models

Copy the complete prompt below into Antigravity.

```text
MODULE 02 OF 16 — CORE GAME STATE AND DATA MODELS

You are my senior Python game developer and technical lead. Build BLADE ARENA, a university AI Lab 2D spinning-top game, one module at a time. Work only in the current workspace. Preserve existing user files, installed skills and previously working behavior; inspect the code, current documentation and tests first. Run a baseline full test suite and existing headless smoke test before changes when they exist. Report existing failures and fix only those directly related or necessary; do not silently remove assertions or tests.

Use Python 3.11/3.12, pygame-ce (imported as pygame), and pytest. Never install pygame and pygame-ce in the same environment. Keep the pure game engine, AI and headless orchestration independent of Pygame. The final game uses simultaneous actions, one shared deterministic rules engine, Ironclad Minimax, Cyclone MCTS and Mamdani fuzzy logic. Restrict AI algorithms to the course-approved set; do not substitute black-box AI, external APIs or unrelated algorithms. Read relevant installed `pygame-core`, `python-testing`, `game-docs`, `game-ui-ux` or `create-game-assets` skills if available, but do not add tools or run skill scripts automatically. State which skills you actually used.

Do not open an external browser for testing. Do not delete or overwrite unrelated work, push to GitHub, commit, publish, use paid services or start the next module unless explicitly asked. Follow the existing code's actual names where practical, keeping prior public APIs compatible. Document any necessary migration. Clearly label future capabilities and numerical assumptions; do not claim that unfinished features work.

## Objective
Create immutable, pure-Python models for game state, independent of Pygame and usable by future AI and headless tests.

## Scope and implementation
- Inspect and preserve Module 1. Prefer frozen dataclasses, enums, type hints, finite numeric validation, and no nested shared mutable state. Never open a window on import.
- Define exactly the five actions: `CHARGE`, `ATTACK`, `GUARD`, `DODGE`, `SPECIAL_SPIN`; these are names only at this stage.
- Define a position with finite x and y and distance to a supplied center; no `pygame.Vector2` dependency.
- Define a blade state with stable player identifier, blade type, current and maximum energy, current and maximum stability, position and `special_ready_at` logical seconds. Initial Balanced values: energy/max 100, stability/max 100, ready-at 0. Zero current energy/stability is valid data; reject negatives, current values above maximum, invalid maxima, and non-finite values, without silently clamping.
- Define stadium state: `CLASSIC_DISH`, center `(0, 0)`, initial radius 10, positive finite radius. Minimum 6 is documented but not applied yet.
- Define a match with two distinct player IDs, stadium, nonnegative integer completed rounds, `IN_PROGRESS` or `FINISHED`, and optional result. Results can represent player 1 win, player 2 win or draw, with a finish-reason representation for ring-out, burst, spin-out, simultaneous elimination or points. An in-progress state has no result; a finished state has one. No winner calculation yet.
- Store completed rounds as the authoritative time; expose elapsed logical seconds as completed rounds × 3. Document the future 40-round/120-second limit, but do not enforce it yet.
- Provide a factory for a default match with two Balanced blades at `(-2, 0)` and `(2, 0)`; these starting positions and the energy cap of 100 are implementation assumptions, not explicit PDF values. Calls must have no shared mutable data. Show how to derive a changed state using `dataclasses.replace` or equivalent without altering the original.
- Create `docs/game_state.md`, document fields, initial state, specified rules versus assumptions, immutable derivation, and what is not implemented; update README.

## Verification and acceptance
Test all five action names; position distance and invalid non-finite values; blade zero, negative and over-max cases; invalid maximum values; stadium radius; distinct player IDs; initial values and result/status invariants; round and time validation including rejection of boolean or non-integer round counts; independently derived state; and headless imports. Run previous tests and smoke mode.

## Scope boundary
Do not implement action effects, legality, movement, shrinking, combat, termination, AI or UI beyond Module 1.
## Mandatory self-testing — no external browser
1. Run this module's tests, the complete existing test suite, and the project's documented headless application smoke test. Run any other commands specified above. Use timeouts for commands that can hang.
2. Test normal operation, invalid inputs, important edge cases, and integration with previous modules. Verify every acceptance item above and fix any discovered failures; rerun the affected checks.
3. Test the Pygame application locally, not in an external browser. If a graphical display is available, inspect the relevant local window and controls; if not, explicitly say visual inspection could not be performed. A dummy-driver smoke test is not visual verification.
4. Do not mark a module fully complete if a required test or acceptance criterion failed or could not be verified. State precisely what remains unresolved. Never invent test, benchmark or visual results.

## Final report
Report: files created/changed; skills actually read and used; public APIs and assumptions; exact commands executed; pass/fail/not-run result of each meaningful check; whether local visual inspection occurred; defects fixed; failures and environment limitations; acceptance criteria status; and the exact command to run the full test suite. Stop after this module.
```

---

## Module 03 — Turn and Match Flow

Copy the complete prompt below into Antigravity.

```text
MODULE 03 OF 16 — TURN AND MATCH FLOW

You are my senior Python game developer and technical lead. Build BLADE ARENA, a university AI Lab 2D spinning-top game, one module at a time. Work only in the current workspace. Preserve existing user files, installed skills and previously working behavior; inspect the code, current documentation and tests first. Run a baseline full test suite and existing headless smoke test before changes when they exist. Report existing failures and fix only those directly related or necessary; do not silently remove assertions or tests.

Use Python 3.11/3.12, pygame-ce (imported as pygame), and pytest. Never install pygame and pygame-ce in the same environment. Keep the pure game engine, AI and headless orchestration independent of Pygame. The final game uses simultaneous actions, one shared deterministic rules engine, Ironclad Minimax, Cyclone MCTS and Mamdani fuzzy logic. Restrict AI algorithms to the course-approved set; do not substitute black-box AI, external APIs or unrelated algorithms. Read relevant installed `pygame-core`, `python-testing`, `game-docs`, `game-ui-ux` or `create-game-assets` skills if available, but do not add tools or run skill scripts automatically. State which skills you actually used.

Do not open an external browser for testing. Do not delete or overwrite unrelated work, push to GitHub, commit, publish, use paid services or start the next module unless explicitly asked. Follow the existing code's actual names where practical, keeping prior public APIs compatible. Document any necessary migration. Clearly label future capabilities and numerical assumptions; do not claim that unfinished features work.

## Objective
Create a headless match controller that collects two simultaneous choices and delegates a complete round to an injected resolver. The production resolver does not yet exist.

## Scope and implementation
- Inspect existing models and tests. Keep the controller independent of Pygame and retain immutable game-state snapshots.
- Define a resolver protocol equivalent to `resolve_round(state, player_1_action, player_2_action) -> GameState`. Its input is the pre-round state; both actions are supplied together in stable player order. The resolver returns a new state with exactly one additional completed round and must not mutate the input. The resolver owns the round increment; the controller must not increment it a second time.
- Provide a controller API to read the current state, identify which player IDs still need to submit, submit one defined action per player, resolve once both have submitted, pause, resume, restart, and inspect pause status. A player's supported observation API must not reveal the opponent's pending action. This prevents accidental leakage, not malicious access to Python internals.
- Both players receive the same pre-round snapshot whether player 1 or 2 submits first. Reject unknown player IDs, non-action values, duplicate submission, submission/resolution while paused, and play after the game is finished. Module 3 validates action type only; energy and cooldown legality come later.
- On successful resolution validate the returned object and exactly-one-round advancement, store it and clear pending choices. A finished result ends play. If resolution raises or returns invalid state, keep the old state and pending actions for retry; surface a clear error. Do not expose hidden action details in public status or errors.
- Pausing preserves pending actions; resume does not advance time. Make repeated pause/resume idempotent and document it. Restart restores the original initial snapshot and selections, clears pending actions and pause, and works after completion.
- Use recording, finishing, failing and invalid resolvers **only as test fixtures**, not as real game mechanics. Provide `docs/match_flow.md` and update README: no action effects, gameplay legality or production resolver exists yet.

## Verification and acceptance
Test each submission order; same pre-round observation; pending secrecy; duplicate and invalid inputs; cannot resolve early; resolver arguments; exact single increment and original immutability; pending reset; error and invalid result atomicity with retry; pause/resume; restart; finished-match handling; imports without a display. Run full existing tests and smoke mode.

## Scope boundary
Do not implement costs, movement, damage, shrinking, win decisions, AI, tournament, or on-screen controls.
## Mandatory self-testing — no external browser
1. Run this module's tests, the complete existing test suite, and the project's documented headless application smoke test. Run any other commands specified above. Use timeouts for commands that can hang.
2. Test normal operation, invalid inputs, important edge cases, and integration with previous modules. Verify every acceptance item above and fix any discovered failures; rerun the affected checks.
3. Test the Pygame application locally, not in an external browser. If a graphical display is available, inspect the relevant local window and controls; if not, explicitly say visual inspection could not be performed. A dummy-driver smoke test is not visual verification.
4. Do not mark a module fully complete if a required test or acceptance criterion failed or could not be verified. State precisely what remains unresolved. Never invent test, benchmark or visual results.

## Final report
Report: files created/changed; skills actually read and used; public APIs and assumptions; exact commands executed; pass/fail/not-run result of each meaningful check; whether local visual inspection occurred; defects fixed; failures and environment limitations; acceptance criteria status; and the exact command to run the full test suite. Stop after this module.
```

---

## Module 04 — Blade Types and Statistics

Copy the complete prompt below into Antigravity.

```text
MODULE 04 OF 16 — BLADE TYPES AND STATISTICS

You are my senior Python game developer and technical lead. Build BLADE ARENA, a university AI Lab 2D spinning-top game, one module at a time. Work only in the current workspace. Preserve existing user files, installed skills and previously working behavior; inspect the code, current documentation and tests first. Run a baseline full test suite and existing headless smoke test before changes when they exist. Report existing failures and fix only those directly related or necessary; do not silently remove assertions or tests.

Use Python 3.11/3.12, pygame-ce (imported as pygame), and pytest. Never install pygame and pygame-ce in the same environment. Keep the pure game engine, AI and headless orchestration independent of Pygame. The final game uses simultaneous actions, one shared deterministic rules engine, Ironclad Minimax, Cyclone MCTS and Mamdani fuzzy logic. Restrict AI algorithms to the course-approved set; do not substitute black-box AI, external APIs or unrelated algorithms. Read relevant installed `pygame-core`, `python-testing`, `game-docs`, `game-ui-ux` or `create-game-assets` skills if available, but do not add tools or run skill scripts automatically. State which skills you actually used.

Do not open an external browser for testing. Do not delete or overwrite unrelated work, push to GitHub, commit, publish, use paid services or start the next module unless explicitly asked. Follow the existing code's actual names where practical, keeping prior public APIs compatible. Document any necessary migration. Clearly label future capabilities and numerical assumptions; do not claim that unfinished features work.

## Objective
Define four selectable blade types as immutable data, and initialize matches from those definitions. Do not apply their abilities yet.

## Required statistics
Use this exact table:

| Type | Max energy | Max stability | Passive energy loss/round | Attack power | Guard recovery | Charge recovery |
|---|---:|---:|---:|---:|---:|---:|
| Balanced | 100 | 100 | 3 | 1.00 | 5 | 20 |
| Attacker | 100 | 90 | 4 | 1.25 | 5 | 20 |
| Defender | 100 | 120 | 3 | 0.85 | 10 | 20 |
| Stamina | 100 | 100 | 2 | 1.00 | 5 | 25 |

Maximum energy 100 for all types is an implementation assumption; initial energy 100 is specified. Full initial stability equals each type's maximum. The presentation's Striker/Bulwark names differ from the PDF's Attacker/Defender: use the PDF names internally and document the difference.

## Scope and implementation
- Extend the existing blade type enum with the four unique identifiers while maintaining Balanced compatibility.
- Define immutable blade-type definitions with display name and all values above. Put them in one central pure-Python registry. Protect shared definitions from mutation; validate finite positive maxima and multipliers, nonnegative losses/recoveries and nonempty names. Clearly reject unsupported types.
- Provide lookup and a factory creating a BladeState from player ID, blade type and position: full energy/stability, appropriate maxima and ready-at time 0. Definitions describe base stats; BladeState holds current values.
- Extend the initial-match factory to optionally choose each player's type. A no-argument call still creates two Balanced blades at the existing starting positions in Classic Dish. Support mixed types. Preserve match controller behavior and restart of original blade selections.
- Document `docs/blade_types.md`: values, lookup/factory, current state versus type, assumptions, alternate names and that abilities are not applied yet. Update README.

## Verification and acceptance
Test the exact four types and all table values; validation and mutation protection; each factory and default state; mixed Attacker/Defender initialization and position/player identity; controller collection and test-only resolver; restart restores selected types; creation never deducts energy or applies effects. Update old tests that intentionally assumed Balanced was the only possible type, retaining all other regression checks. Run full tests and smoke mode.

## Scope boundary
Do not implement passive loss, Charge, Guard, attack calculations, movement, action legality, selection UI, AI or tournament.
## Mandatory self-testing — no external browser
1. Run this module's tests, the complete existing test suite, and the project's documented headless application smoke test. Run any other commands specified above. Use timeouts for commands that can hang.
2. Test normal operation, invalid inputs, important edge cases, and integration with previous modules. Verify every acceptance item above and fix any discovered failures; rerun the affected checks.
3. Test the Pygame application locally, not in an external browser. If a graphical display is available, inspect the relevant local window and controls; if not, explicitly say visual inspection could not be performed. A dummy-driver smoke test is not visual verification.
4. Do not mark a module fully complete if a required test or acceptance criterion failed or could not be verified. State precisely what remains unresolved. Never invent test, benchmark or visual results.

## Final report
Report: files created/changed; skills actually read and used; public APIs and assumptions; exact commands executed; pass/fail/not-run result of each meaningful check; whether local visual inspection occurred; defects fixed; failures and environment limitations; acceptance criteria status; and the exact command to run the full test suite. Stop after this module.
```

---

## Module 05 — Action Definitions and Legality

Copy the complete prompt below into Antigravity.

```text
MODULE 05 OF 16 — ACTION DEFINITIONS AND LEGALITY

You are my senior Python game developer and technical lead. Build BLADE ARENA, a university AI Lab 2D spinning-top game, one module at a time. Work only in the current workspace. Preserve existing user files, installed skills and previously working behavior; inspect the code, current documentation and tests first. Run a baseline full test suite and existing headless smoke test before changes when they exist. Report existing failures and fix only those directly related or necessary; do not silently remove assertions or tests.

Use Python 3.11/3.12, pygame-ce (imported as pygame), and pytest. Never install pygame and pygame-ce in the same environment. Keep the pure game engine, AI and headless orchestration independent of Pygame. The final game uses simultaneous actions, one shared deterministic rules engine, Ironclad Minimax, Cyclone MCTS and Mamdani fuzzy logic. Restrict AI algorithms to the course-approved set; do not substitute black-box AI, external APIs or unrelated algorithms. Read relevant installed `pygame-core`, `python-testing`, `game-docs`, `game-ui-ux` or `create-game-assets` skills if available, but do not add tools or run skill scripts automatically. State which skills you actually used.

Do not open an external browser for testing. Do not delete or overwrite unrelated work, push to GitHub, commit, publish, use paid services or start the next module unless explicitly asked. Follow the existing code's actual names where practical, keeping prior public APIs compatible. Document any necessary migration. Clearly label future capabilities and numerical assumptions; do not claim that unfinished features work.

## Objective
Define the five actions' data and implement a pure legality query. Do not apply actions or resolve a round yet.

## Required rules
- Charge: cost 0, recover 20 energy (Stamina 25); move toward center; vulnerable to attacks.
- Attack: cost 8 energy; move toward opponent; may deal stability damage and push.
- Guard: cost 4 energy; recover 5 stability (Defender 10); reduce incoming effects.
- Dodge: cost 8 energy; move sideways; may avoid normal and special attacks.
- Special Spin: cost 35 energy, 10 stability recoil on use, requires cooldown availability; move toward opponent; stronger damage/push; cooldown 3 logical seconds.
- Definitions and base values belong in a single immutable registry. Blade-specific recovery comes from Module 4 definitions, not duplicated per blade.

## Scope and implementation
- Provide action metadata for display and future resolver, and `legal_actions(state, player_id)` plus a single-action check returning a clear reason for illegality. Use the same API for future UI and AI.
- Energy cost is payable if current energy is at least the cost; Special additionally requires `elapsed_game_time >= special_ready_at`. Charge has no energy cost. A finished match offers no legal actions. Reject unknown player/action clearly. Do not infer match terminality just because a raw model has zero resources; outcome logic belongs to Module 8.
- Recovery is capped at the blade maximum when later applied, but do not change the state in this module. Return deterministic ordering matching the five listed actions. No hidden opponent information is used.
- Respect the current controller boundary: either leave it as type-only submission and document the later integration, or add an optional injected legality checker that does not mutate state. Do not silently make the existing test-only resolver behave as combat. Document the selected contract.
- Cooldown timing: a Special used at round start `t` sets ready-at to `t+3` in the future resolver. With 3 logical seconds per round it is ready at the next decision. This follows the PDF literally; no arbitrary 3-round cooldown.
- Write `docs/actions.md` including values, legality, simultaneous action principle, assumptions, and what remains unimplemented.

## Verification and acceptance
Test every action's metadata; energy values below/equal/above each cost; zero-cost Charge; Special at/before ready time; finished state and unknown IDs; legal action ordering; no state mutation; blade-specific recovery lookup; controller compatibility as documented. Full pytest and smoke mode.

## Scope boundary
No action application, movement, recoil, attack resolution, passive loss, AI or UI.
## Mandatory self-testing — no external browser
1. Run this module's tests, the complete existing test suite, and the project's documented headless application smoke test. Run any other commands specified above. Use timeouts for commands that can hang.
2. Test normal operation, invalid inputs, important edge cases, and integration with previous modules. Verify every acceptance item above and fix any discovered failures; rerun the affected checks.
3. Test the Pygame application locally, not in an external browser. If a graphical display is available, inspect the relevant local window and controls; if not, explicitly say visual inspection could not be performed. A dummy-driver smoke test is not visual verification.
4. Do not mark a module fully complete if a required test or acceptance criterion failed or could not be verified. State precisely what remains unresolved. Never invent test, benchmark or visual results.

## Final report
Report: files created/changed; skills actually read and used; public APIs and assumptions; exact commands executed; pass/fail/not-run result of each meaningful check; whether local visual inspection occurred; defects fixed; failures and environment limitations; acceptance criteria status; and the exact command to run the full test suite. Stop after this module.
```

---

## Module 06 — Classic Stadium, Geometry and Movement

Copy the complete prompt below into Antigravity.

```text
MODULE 06 OF 16 — CLASSIC STADIUM, GEOMETRY AND MOVEMENT

You are my senior Python game developer and technical lead. Build BLADE ARENA, a university AI Lab 2D spinning-top game, one module at a time. Work only in the current workspace. Preserve existing user files, installed skills and previously working behavior; inspect the code, current documentation and tests first. Run a baseline full test suite and existing headless smoke test before changes when they exist. Report existing failures and fix only those directly related or necessary; do not silently remove assertions or tests.

Use Python 3.11/3.12, pygame-ce (imported as pygame), and pytest. Never install pygame and pygame-ce in the same environment. Keep the pure game engine, AI and headless orchestration independent of Pygame. The final game uses simultaneous actions, one shared deterministic rules engine, Ironclad Minimax, Cyclone MCTS and Mamdani fuzzy logic. Restrict AI algorithms to the course-approved set; do not substitute black-box AI, external APIs or unrelated algorithms. Read relevant installed `pygame-core`, `python-testing`, `game-docs`, `game-ui-ux` or `create-game-assets` skills if available, but do not add tools or run skill scripts automatically. State which skills you actually used.

Do not open an external browser for testing. Do not delete or overwrite unrelated work, push to GitHub, commit, publish, use paid services or start the next module unless explicitly asked. Follow the existing code's actual names where practical, keeping prior public APIs compatible. Document any necessary migration. Clearly label future capabilities and numerical assumptions; do not claim that unfinished features work.

## Objective
Implement deterministic geometry and pure movement calculations for the Classic Dish and the arena shrinking schedule. Do not wire up full combat or finish logic.

## Rules and initial tuning assumptions
- Arena center `(0, 0)`, radius starts at 10, minimum 6. After every sixth completed round radius decreases by 1: after rounds 6/12/18/24 radius 9/8/7/6; clamp at 6.
- Ring-out means the blade center is strictly outside radius; equality is inside. Expose a pure boundary query, but do not award a result in this module.
- Proposed movement distances in arena units: Charge 1.0 toward center, Attack 1.6 toward the opponent, Guard 0, Dodge 1.4 sideways, Special Spin 2.0 toward the opponent. Toward-target movement is capped to avoid overshooting. All are tunable assumptions, not PDF-specified values.
- Movement for both players is calculated from the same pre-round positions. Dodge considers the two perpendicular directions to the opponent direction and chooses the candidate farther inside the arena; use a documented deterministic tie-break. Dodge succeeds only if its final position is at least 0.5 units inside the current boundary; near-edge dodge may still move but does not evade. Boundary comparisons use a documented numerical tolerance consistently.

## Implementation
- Build pure functions for distance, vector normalization, move-toward, dodge candidate selection, boundary margin, outside check, and radius after a specified number of completed rounds. Use finite values; handle center/target coincidence and zero-length vectors without division by zero.
- Provide a pairwise planned-movement calculation using the common pre-round state. Return next positions and dodge-success information without mutating the state. Select stable fallback directions if blades coincide; document them and test the behavior. No randomness or Pygame dependency.
- Define whether stadium shrink is applied using the initial configured radius and completed rounds, not by repeatedly decrementing in ways that can double-shrink. The actual round resolver will invoke it later.
- Add `docs/stadium_and_movement.md`: coordinate system, timings, values labeled proposed, boundary convention, edge and coincidence cases, and that result calculation is not implemented.

## Verification and acceptance
Test toward-center and toward-opponent moves, no overshoot, Guard, both dodge directions and ties, near-edge failure and exact threshold, zero vector and coincident positions, symmetric representative positions, each shrink milestone and minimum, exact/on/outside boundary, no mutation and headless use. Run full tests and smoke mode.

## Scope boundary
No attack hit detection, damage, resource changes, result setting or Ice/Steep modifiers.
## Mandatory self-testing — no external browser
1. Run this module's tests, the complete existing test suite, and the project's documented headless application smoke test. Run any other commands specified above. Use timeouts for commands that can hang.
2. Test normal operation, invalid inputs, important edge cases, and integration with previous modules. Verify every acceptance item above and fix any discovered failures; rerun the affected checks.
3. Test the Pygame application locally, not in an external browser. If a graphical display is available, inspect the relevant local window and controls; if not, explicitly say visual inspection could not be performed. A dummy-driver smoke test is not visual verification.
4. Do not mark a module fully complete if a required test or acceptance criterion failed or could not be verified. State precisely what remains unresolved. Never invent test, benchmark or visual results.

## Final report
Report: files created/changed; skills actually read and used; public APIs and assumptions; exact commands executed; pass/fail/not-run result of each meaningful check; whether local visual inspection occurred; defects fixed; failures and environment limitations; acceptance criteria status; and the exact command to run the full test suite. Stop after this module.
```

---

## Module 07 — Combat and Simultaneous Round Resolution

Copy the complete prompt below into Antigravity.

```text
MODULE 07 OF 16 — COMBAT AND SIMULTANEOUS ROUND RESOLUTION

You are my senior Python game developer and technical lead. Build BLADE ARENA, a university AI Lab 2D spinning-top game, one module at a time. Work only in the current workspace. Preserve existing user files, installed skills and previously working behavior; inspect the code, current documentation and tests first. Run a baseline full test suite and existing headless smoke test before changes when they exist. Report existing failures and fix only those directly related or necessary; do not silently remove assertions or tests.

Use Python 3.11/3.12, pygame-ce (imported as pygame), and pytest. Never install pygame and pygame-ce in the same environment. Keep the pure game engine, AI and headless orchestration independent of Pygame. The final game uses simultaneous actions, one shared deterministic rules engine, Ironclad Minimax, Cyclone MCTS and Mamdani fuzzy logic. Restrict AI algorithms to the course-approved set; do not substitute black-box AI, external APIs or unrelated algorithms. Read relevant installed `pygame-core`, `python-testing`, `game-docs`, `game-ui-ux` or `create-game-assets` skills if available, but do not add tools or run skill scripts automatically. State which skills you actually used.

Do not open an external browser for testing. Do not delete or overwrite unrelated work, push to GitHub, commit, publish, use paid services or start the next module unless explicitly asked. Follow the existing code's actual names where practical, keeping prior public APIs compatible. Document any necessary migration. Clearly label future capabilities and numerical assumptions; do not claim that unfinished features work.

## Objective
Replace the test-only round behavior with the first real, shared Classic Dish round resolver. Both human and future AI simulations must eventually use this same pure rules engine.

## Explicit proposed tuning values
Normal Attack: base stability damage 12, base push 1.2, hit range 1.2 after movement. Special Spin: base stability damage 25, base push 2.0, same hit range; self-recoil 10 stability whether it hits or misses. A charging defender receives 1.25× damage and push. Guard multiplies incoming normal attack damage and push by 0.50; it multiplies Special Spin damage and push by 0.70. A normal attack that hits Guard causes 3 stability recoil to the attacker. Multiply outgoing stability damage by the attacker's blade power; do not apply blade power to push. These numbers are proposed starting values, not facts in the PDF. Place them in a central immutable combat configuration.

## Round contract and legality
- Implement the Module 3 resolver interface. Validate both action choices against the same pre-round state using Module 5. If either is illegal, reject the entire round with a clear error; neither action, state nor pending selection is altered. Provide a safe way for the controller to discard/reselect an invalid pending action after a resolver rejection, without exposing the opponent's selection; test this workflow. Integrate controller-side legality precheck if useful, but the resolver must remain authoritative for direct AI calls.
- Maintain per-blade resource bounds: start from valid state; subtract costs; apply Charge/Guard recovery capped at the respective maximum; resolve all hit damage and recoil; apply passive energy loss once per blade; clamp resulting energy/stability to zero for valid returned model values. Charge effect is recovery only, not an attack. Special ready-at becomes pre-round logical time + 3 seconds even on a miss.
- Calculate both movements from the same pre-round snapshot using Module 6. Guard stays in place, Charge moves centerward, attack/special moves opponentward, Dodge sideways. Determine Dodge success from its resulting position and pre-shrink radius.
- Determine attack range from positions after movement and before pushes. A successful defender Dodge causes incoming Attack or Special to miss. Evaluate both attacks against the same intermediate snapshot; simultaneous attacks may both hit. For each hit, calculate damage/push modifiers by defender action, and normal-Attack-on-Guard attacker recoil. Apply both attacks, both recoils and aggregated push vectors simultaneously; no automatic player priority.
- Push direction points from attacker toward defender using post-movement positions; if coincident, use pre-movement relative direction and then a documented stable fallback. Do not rely on graphics. Treat guard and charge modifiers consistently for both damage and push. Shrink after every sixth completed round using Module 6, then increment exactly once as required by the resolver protocol.
- Return a new immutable state. At this module, do not declare winners; zero resources/outside positions can be represented until Module 8 adds terminal checks. Clearly label the resolver as incomplete until termination is added. Keep a concise round event representation if useful but do not change the established resolver return contract without updating callers/tests.
- Document operation order and config in `docs/combat.md`, including all assumptions and simultaneous-action edge cases.

## Verification and acceptance
Test all 25 action pairs with parametrization for legal representative states, including Attack/Charge, Attack/Guard, Special/Guard, successful and failed Dodge, Attack/Attack, Special/Special, misses and range boundaries; cooldown and exact-energy legality; clamped recovery and damage; blade multipliers; self/guard recoil; passive loss; equal-coordinate fallback; movement, push and shrink; both-submission orders; atomic rejection and reselection; no mutation; deterministic replay; exactly one round increment. Test controller with the real resolver and all earlier tests plus smoke mode.

## Scope boundary
Do not implement winner detection, points, fuzzy logic, AI, UI, or tournament yet.
## Mandatory self-testing — no external browser
1. Run this module's tests, the complete existing test suite, and the project's documented headless application smoke test. Run any other commands specified above. Use timeouts for commands that can hang.
2. Test normal operation, invalid inputs, important edge cases, and integration with previous modules. Verify every acceptance item above and fix any discovered failures; rerun the affected checks.
3. Test the Pygame application locally, not in an external browser. If a graphical display is available, inspect the relevant local window and controls; if not, explicitly say visual inspection could not be performed. A dummy-driver smoke test is not visual verification.
4. Do not mark a module fully complete if a required test or acceptance criterion failed or could not be verified. State precisely what remains unresolved. Never invent test, benchmark or visual results.

## Final report
Report: files created/changed; skills actually read and used; public APIs and assumptions; exact commands executed; pass/fail/not-run result of each meaningful check; whether local visual inspection occurred; defects fixed; failures and environment limitations; acceptance criteria status; and the exact command to run the full test suite. Stop after this module.
```

---

## Module 08 — Win Conditions and Match Results

Copy the complete prompt below into Antigravity.

```text
MODULE 08 OF 16 — WIN CONDITIONS AND MATCH RESULTS

You are my senior Python game developer and technical lead. Build BLADE ARENA, a university AI Lab 2D spinning-top game, one module at a time. Work only in the current workspace. Preserve existing user files, installed skills and previously working behavior; inspect the code, current documentation and tests first. Run a baseline full test suite and existing headless smoke test before changes when they exist. Report existing failures and fix only those directly related or necessary; do not silently remove assertions or tests.

Use Python 3.11/3.12, pygame-ce (imported as pygame), and pytest. Never install pygame and pygame-ce in the same environment. Keep the pure game engine, AI and headless orchestration independent of Pygame. The final game uses simultaneous actions, one shared deterministic rules engine, Ironclad Minimax, Cyclone MCTS and Mamdani fuzzy logic. Restrict AI algorithms to the course-approved set; do not substitute black-box AI, external APIs or unrelated algorithms. Read relevant installed `pygame-core`, `python-testing`, `game-docs`, `game-ui-ux` or `create-game-assets` skills if available, but do not add tools or run skill scripts automatically. State which skills you actually used.

Do not open an external browser for testing. Do not delete or overwrite unrelated work, push to GitHub, commit, publish, use paid services or start the next module unless explicitly asked. Follow the existing code's actual names where practical, keeping prior public APIs compatible. Document any necessary migration. Clearly label future capabilities and numerical assumptions; do not claim that unfinished features work.

## Objective
Finish the core engine by evaluating elimination after all effects and arena shrinking, then apply the documented 40-round points decision.

## Rules
- Ring-out: blade center strictly outside the current radius under the same boundary/tolerance convention as Module 6. Burst: stability <= 0. Spin-out: energy <= 0.
- Evaluate both players after the entire simultaneous round, passive energy loss and shrink. If both are eliminated in that round, return a draw; do not decide early based on player order. If only one is eliminated the other wins. Record every applicable elimination cause when the existing result schema permits; if extending the schema, preserve compatible callers. For one display label on a player with multiple causes, use documented priority ring-out, burst, spin-out. A simultaneous elimination's displayed match reason is simultaneous elimination.
- If neither is eliminated after completed round 40, use proposed normalized points: `0.40*(energy/max_energy) + 0.40*(stability/max_stability) + 0.20*max(0, 1-distance_from_center/current_radius)`. Higher wins. Absolute score difference <= 1e-6 is a draw. Label this a points decision, not a knockout. Store enough score/cause detail for later logs if practical.
- No extra round is allowed after `FINISHED`. A 40th-round elimination takes priority over points. Avoid multiple independent sources of truth for status.

## Implementation
Add a pure terminal evaluator and integrate it into the real resolver after all current round effects and shrink. Return a valid immutable finished state with a result. Keep Module 3's controller rules intact; direct resolution of a finished state must be rejected. Document elimination timing, boundary, cause priority, simultaneous draw, points, assumptions and 120-second logical limit in `docs/match_results.md`.

## Verification and acceptance
Test each finish, exact zero resources and boundary edge, shrink-caused ring-out, both eliminated through different causes, multiple causes for one blade, 40th-round elimination vs points, points winner and exact/near ties, no premature finish at 39, no 41st round, both player orderings, and immutable inputs. Run a complete headless match using deterministic scripted legal actions and verify its final state, then full tests and smoke mode.

## Scope boundary
Do not implement fuzzy logic, AI, tournament, additional stadiums or graphical game screens.
## Mandatory self-testing — no external browser
1. Run this module's tests, the complete existing test suite, and the project's documented headless application smoke test. Run any other commands specified above. Use timeouts for commands that can hang.
2. Test normal operation, invalid inputs, important edge cases, and integration with previous modules. Verify every acceptance item above and fix any discovered failures; rerun the affected checks.
3. Test the Pygame application locally, not in an external browser. If a graphical display is available, inspect the relevant local window and controls; if not, explicitly say visual inspection could not be performed. A dummy-driver smoke test is not visual verification.
4. Do not mark a module fully complete if a required test or acceptance criterion failed or could not be verified. State precisely what remains unresolved. Never invent test, benchmark or visual results.

## Final report
Report: files created/changed; skills actually read and used; public APIs and assumptions; exact commands executed; pass/fail/not-run result of each meaningful check; whether local visual inspection occurred; defects fixed; failures and environment limitations; acceptance criteria status; and the exact command to run the full test suite. Stop after this module.
```

---

## Module 09 — Mamdani Fuzzy Danger Estimation

Copy the complete prompt below into Antigravity.

```text
MODULE 09 OF 16 — MAMDANI FUZZY DANGER ESTIMATION

You are my senior Python game developer and technical lead. Build BLADE ARENA, a university AI Lab 2D spinning-top game, one module at a time. Work only in the current workspace. Preserve existing user files, installed skills and previously working behavior; inspect the code, current documentation and tests first. Run a baseline full test suite and existing headless smoke test before changes when they exist. Report existing failures and fix only those directly related or necessary; do not silently remove assertions or tests.

Use Python 3.11/3.12, pygame-ce (imported as pygame), and pytest. Never install pygame and pygame-ce in the same environment. Keep the pure game engine, AI and headless orchestration independent of Pygame. The final game uses simultaneous actions, one shared deterministic rules engine, Ironclad Minimax, Cyclone MCTS and Mamdani fuzzy logic. Restrict AI algorithms to the course-approved set; do not substitute black-box AI, external APIs or unrelated algorithms. Read relevant installed `pygame-core`, `python-testing`, `game-docs`, `game-ui-ux` or `create-game-assets` skills if available, but do not add tools or run skill scripts automatically. State which skills you actually used.

Do not open an external browser for testing. Do not delete or overwrite unrelated work, push to GitHub, commit, publish, use paid services or start the next module unless explicitly asked. Follow the existing code's actual names where practical, keeping prior public APIs compatible. Document any necessary migration. Clearly label future capabilities and numerical assumptions; do not claim that unfinished features work.

## Objective
Implement an interpretable, deterministic Mamdani fuzzy inference system for each blade's danger and make it independently testable. Do not use a black-box AI model.

## Inputs and outputs
- `energy_ratio = energy / maximum_energy` in [0,1].
- `edge_safety = clamp((stadium_radius - distance_from_center) / stadium_radius, 0, 1)`. Zero is at/outside the edge; one is at center.
- Output a continuous danger score 0–100 and a readable low/medium/high label. Low energy OR being near the edge must increase danger. Fuzzy score informs future AI and UI but must not replace match-ending rules.

## Explicit, tunable initial membership design
Use piecewise-linear triangular/trapezoidal membership functions with full endpoint coverage; implement degenerate shoulder endpoints carefully. Suggested input sets on [0,1]: low/near = trapezoid (0,0,0.15,0.40), medium = triangle (0.20,0.50,0.80), high/safe = trapezoid (0.60,0.85,1,1). Output sets on [0,100]: low = trapezoid (0,0,15,40), medium = triangle (20,50,80), high = trapezoid (60,85,100,100). Expose parameters centrally and document them as proposed, not supplied PDF values.
- Rules: (1) near edge OR low energy => high; (2) medium edge safety AND medium energy => medium; (3) medium edge safety AND high energy => medium; (4) safe edge AND medium energy => medium; (5) safe edge AND high energy => low. Use MAX for OR, MIN for AND and implication, MAX for aggregation. Centroid-defuzzify over a documented fixed grid, e.g. 0 through 100 inclusive at 0.5 intervals. Compute an area-weighted centroid; guard against zero denominator with an explicit documented fallback/error strategy. Confirm input/rule coverage with a grid test.
- Provide a pure evaluator returning score, label and optionally input memberships/rule strengths for the future AI panel. Define deterministic score-label thresholds, e.g. low < 35, medium 35–<65, high >=65, labeled as display thresholds. Terminal state handling remains with the rules engine.
- Explain fuzzification, rule evaluation, aggregation, centroid, parameter shapes, sampling precision and limitations in `docs/fuzzy_danger.md`. No external fuzzy library is necessary.

## Verification and acceptance
Test exact endpoints, peaks/slopes and shoulder functions; MAX OR and MIN AND; rule aggregation and centroid against known synthetic outputs; full input-grid coverage/no division by zero; score 0–100; high risk near edge or low energy versus safe/full-energy representative states; same input gives same output; correct use of actual stadium radius; headless purity and no mutation. Full tests and smoke mode.

## Scope boundary
No AI decision-making or graphical danger indicator yet.
## Mandatory self-testing — no external browser
1. Run this module's tests, the complete existing test suite, and the project's documented headless application smoke test. Run any other commands specified above. Use timeouts for commands that can hang.
2. Test normal operation, invalid inputs, important edge cases, and integration with previous modules. Verify every acceptance item above and fix any discovered failures; rerun the affected checks.
3. Test the Pygame application locally, not in an external browser. If a graphical display is available, inspect the relevant local window and controls; if not, explicitly say visual inspection could not be performed. A dummy-driver smoke test is not visual verification.
4. Do not mark a module fully complete if a required test or acceptance criterion failed or could not be verified. State precisely what remains unresolved. Never invent test, benchmark or visual results.

## Final report
Report: files created/changed; skills actually read and used; public APIs and assumptions; exact commands executed; pass/fail/not-run result of each meaningful check; whether local visual inspection occurred; defects fixed; failures and environment limitations; acceptance criteria status; and the exact command to run the full test suite. Stop after this module.
```

---

## Module 10 — Shared AI Heuristic Evaluation

Copy the complete prompt below into Antigravity.

```text
MODULE 10 OF 16 — SHARED AI HEURISTIC EVALUATION

You are my senior Python game developer and technical lead. Build BLADE ARENA, a university AI Lab 2D spinning-top game, one module at a time. Work only in the current workspace. Preserve existing user files, installed skills and previously working behavior; inspect the code, current documentation and tests first. Run a baseline full test suite and existing headless smoke test before changes when they exist. Report existing failures and fix only those directly related or necessary; do not silently remove assertions or tests.

Use Python 3.11/3.12, pygame-ce (imported as pygame), and pytest. Never install pygame and pygame-ce in the same environment. Keep the pure game engine, AI and headless orchestration independent of Pygame. The final game uses simultaneous actions, one shared deterministic rules engine, Ironclad Minimax, Cyclone MCTS and Mamdani fuzzy logic. Restrict AI algorithms to the course-approved set; do not substitute black-box AI, external APIs or unrelated algorithms. Read relevant installed `pygame-core`, `python-testing`, `game-docs`, `game-ui-ux` or `create-game-assets` skills if available, but do not add tools or run skill scripts automatically. State which skills you actually used.

Do not open an external browser for testing. Do not delete or overwrite unrelated work, push to GitHub, commit, publish, use paid services or start the next module unless explicitly asked. Follow the existing code's actual names where practical, keeping prior public APIs compatible. Document any necessary migration. Clearly label future capabilities and numerical assumptions; do not claim that unfinished features work.

## Objective
Implement a shared, transparent state evaluation for both future agents. Terminal utility must dominate every possible nonterminal score.

## Proposed evaluation
For a blade calculate normalized energy, normalized stability, positional safety `clamp(1 - distance_to_center/radius, 0, 1)`, Special availability as 1 if legal by energy/cooldown and 0 otherwise, and fuzzy danger/100. Define:
`blade_value = .30*energy_ratio + .30*stability_ratio + .20*position_safety + .05*special_availability - .15*danger_ratio`.
Nonterminal state score from a given player's perspective is own blade value minus opponent blade value. For terminal states return +100 for that player's win, -100 for loss, 0 for draw. Compute a reward-scaled nonterminal value for MCTS rollouts via documented bounded scaling, without letting it outrank terminal outcomes. Values and weights are proposed starting points, not proof of optimal play.

## Implementation
- Pure function `evaluate_state(state, player_id)` or equivalent; derive all features from current state, common blade/action definitions and fuzzy system. Reject invalid player IDs.
- Keep parameters in a single immutable config. Provide optional breakdown for explaining decisions without recomputing inconsistent metrics. The score is perspective-aware: swapping perspective negates the score; test this, including terminal utility.
- Document components, scale, terminal priority, assumptions, and potential double-counting of position/energy through fuzzy danger in `docs/ai_heuristic.md`. No game-state mutation or Pygame requirement.

## Verification and acceptance
Test terminal win/loss/draw and dominance over nonterminal score; swapped perspective; higher own energy/stability and better position in carefully controlled examples; Special availability under cost/cooldown; danger contribution; bounded rollout scaling and no invalid numeric results; reproducibility and headless use. Run full suite and smoke mode.

## Scope boundary
Do not implement Minimax, MCTS, training, learned models, or GUI AI panels yet.
## Mandatory self-testing — no external browser
1. Run this module's tests, the complete existing test suite, and the project's documented headless application smoke test. Run any other commands specified above. Use timeouts for commands that can hang.
2. Test normal operation, invalid inputs, important edge cases, and integration with previous modules. Verify every acceptance item above and fix any discovered failures; rerun the affected checks.
3. Test the Pygame application locally, not in an external browser. If a graphical display is available, inspect the relevant local window and controls; if not, explicitly say visual inspection could not be performed. A dummy-driver smoke test is not visual verification.
4. Do not mark a module fully complete if a required test or acceptance criterion failed or could not be verified. State precisely what remains unresolved. Never invent test, benchmark or visual results.

## Final report
Report: files created/changed; skills actually read and used; public APIs and assumptions; exact commands executed; pass/fail/not-run result of each meaningful check; whether local visual inspection occurred; defects fixed; failures and environment limitations; acceptance criteria status; and the exact command to run the full test suite. Stop after this module.
```

---

## Module 11 — Ironclad — Minimax AI

Copy the complete prompt below into Antigravity.

```text
MODULE 11 OF 16 — IRONCLAD — MINIMAX AI

You are my senior Python game developer and technical lead. Build BLADE ARENA, a university AI Lab 2D spinning-top game, one module at a time. Work only in the current workspace. Preserve existing user files, installed skills and previously working behavior; inspect the code, current documentation and tests first. Run a baseline full test suite and existing headless smoke test before changes when they exist. Report existing failures and fix only those directly related or necessary; do not silently remove assertions or tests.

Use Python 3.11/3.12, pygame-ce (imported as pygame), and pytest. Never install pygame and pygame-ce in the same environment. Keep the pure game engine, AI and headless orchestration independent of Pygame. The final game uses simultaneous actions, one shared deterministic rules engine, Ironclad Minimax, Cyclone MCTS and Mamdani fuzzy logic. Restrict AI algorithms to the course-approved set; do not substitute black-box AI, external APIs or unrelated algorithms. Read relevant installed `pygame-core`, `python-testing`, `game-docs`, `game-ui-ux` or `create-game-assets` skills if available, but do not add tools or run skill scripts automatically. State which skills you actually used.

Do not open an external browser for testing. Do not delete or overwrite unrelated work, push to GitHub, commit, publish, use paid services or start the next module unless explicitly asked. Follow the existing code's actual names where practical, keeping prior public APIs compatible. Document any necessary migration. Clearly label future capabilities and numerical assumptions; do not claim that unfinished features work.

## Objective
Implement Ironclad using depth-limited Minimax, explicit MAX/MIN roles, iterative deepening and the shared heuristic/rules engine. Both choices are simultaneous; the AI must never see the opponent's actual hidden choice.

## Algorithm and contract
- Common agent API `choose_action(state, player_id)` returns a legal action plus optional decision diagnostics; never mutate the state. Search action pairs from the same state: MAX proposes its action; MIN examines all possible legal opponent actions; resolve them together using the production resolver. Take the minimum value over opponent replies, then maximize across own actions. Recurse one depth per complete resolved round, evaluating terminal states first and nonterminal cutoff with Module 10.
- Iterate depths 1..configured maximum; retain only the last fully completed iteration if an optional deadline or node budget interrupts the next one. For reproducible tests and tournaments prefer fixed depth/node budgets, not wall-clock cutoffs. Ensure an immediately legal fallback exists if interrupted before depth 1. Handle terminal states explicitly and reject requests for an action after completion.
- Starting difficulty targets: Easy depth 1, Medium 2, Hard 3 complete rounds if profiling permits. These are tunable budgets, not promises of speed. Use deterministic tie-breaking based on action order. Avoid claiming opponent is able to observe the chosen action: MIN is a conservative model of all replies.
- Report completed depth, evaluated nodes, chosen value and measured decision time. Time is diagnostics, not part of deterministic game state. Protect the interface from hidden controller actions.
- Document MAX/MIN, ACTIONS/RESULT/TERMINAL/UTILITY, iterative deepening, complexity and simultaneous-action conservatism in `docs/ironclad_minimax.md`.

## Verification and acceptance
Use small controlled game trees or injectable rules in tests to verify MAX/MIN, terminal utilities, depth cutoffs, iterative deepening, fallback on interrupted iterations, deterministic ties and no hidden choice. Verify real game state returns legal actions, leaves input unchanged and handles finished state. Measure and report search timing at sample budgets, without asserting Hard is stronger. Run full suite and smoke mode.

## Scope boundary
No MCTS, external AI services, unapproved search algorithms or GUI integration yet.
## Mandatory self-testing — no external browser
1. Run this module's tests, the complete existing test suite, and the project's documented headless application smoke test. Run any other commands specified above. Use timeouts for commands that can hang.
2. Test normal operation, invalid inputs, important edge cases, and integration with previous modules. Verify every acceptance item above and fix any discovered failures; rerun the affected checks.
3. Test the Pygame application locally, not in an external browser. If a graphical display is available, inspect the relevant local window and controls; if not, explicitly say visual inspection could not be performed. A dummy-driver smoke test is not visual verification.
4. Do not mark a module fully complete if a required test or acceptance criterion failed or could not be verified. State precisely what remains unresolved. Never invent test, benchmark or visual results.

## Final report
Report: files created/changed; skills actually read and used; public APIs and assumptions; exact commands executed; pass/fail/not-run result of each meaningful check; whether local visual inspection occurred; defects fixed; failures and environment limitations; acceptance criteria status; and the exact command to run the full test suite. Stop after this module.
```

---

## Module 12 — Cyclone — Monte Carlo Tree Search AI

Copy the complete prompt below into Antigravity.

```text
MODULE 12 OF 16 — CYCLONE — MONTE CARLO TREE SEARCH AI

You are my senior Python game developer and technical lead. Build BLADE ARENA, a university AI Lab 2D spinning-top game, one module at a time. Work only in the current workspace. Preserve existing user files, installed skills and previously working behavior; inspect the code, current documentation and tests first. Run a baseline full test suite and existing headless smoke test before changes when they exist. Report existing failures and fix only those directly related or necessary; do not silently remove assertions or tests.

Use Python 3.11/3.12, pygame-ce (imported as pygame), and pytest. Never install pygame and pygame-ce in the same environment. Keep the pure game engine, AI and headless orchestration independent of Pygame. The final game uses simultaneous actions, one shared deterministic rules engine, Ironclad Minimax, Cyclone MCTS and Mamdani fuzzy logic. Restrict AI algorithms to the course-approved set; do not substitute black-box AI, external APIs or unrelated algorithms. Read relevant installed `pygame-core`, `python-testing`, `game-docs`, `game-ui-ux` or `create-game-assets` skills if available, but do not add tools or run skill scripts automatically. State which skills you actually used.

Do not open an external browser for testing. Do not delete or overwrite unrelated work, push to GitHub, commit, publish, use paid services or start the next module unless explicitly asked. Follow the existing code's actual names where practical, keeping prior public APIs compatible. Document any necessary migration. Clearly label future capabilities and numerical assumptions; do not claim that unfinished features work.

## Objective
Implement reproducible MCTS as Cyclone using the same production rules, state model, heuristic and legal action API as Ironclad.

## Algorithm
- Implement Selection, Expansion, Simulation and Backpropagation. Use UCB1 `Q + C*sqrt(ln(N)/n)` for visited action children; explore unvisited actions first. Start with C=1.4 as a configurable tuning value.
- For simultaneous actions use a clearly documented opponent model: sample the opponent uniformly from its legal actions at every simulated decision, without seeing the opponent's actual hidden action. The Cyclone decision tree selects Cyclone's action; the sampled opponent action is part of the modeled environment. Different sampled outcomes of one action must remain distinct outcomes in the tree or be correctly resampled; do not incorrectly cache a single opponent reply as the only future for that action.
- Roll out with legal sampled actions to terminal or a bounded horizon. Use rewards win +1, draw 0, loss -1 from Cyclone's perspective; for truncated rollout use Module 10's bounded scaled heuristic strictly within terminal reward extremes. Backpropagate consistently in Cyclone's perspective. Pick final action by highest visit count with a documented deterministic tie-break.
- Accept an injected/local random number generator or seed; never mutate global RNG. Fixed seeds and iteration counts give repeatable action and diagnostics on the same code/configuration. Return a legal fallback if iteration budget is zero or interrupted before one simulation; reject finished matches. Report iterations, per-action visits/rewards and decision time.
- Suggested starting budgets Easy 50, Medium 200, Hard 500 iterations; measure on target hardware and make configurable. Common agent interface should be compatible with Ironclad, without leaking actual choices.
- Document UCB, node/outcome model, four phases, rollout, seed, constraints and limits of a uniform-opponent model in `docs/cyclone_mcts.md`. Do not claim MCTS predicts the real hidden action.

## Verification and acceptance
Test unvisited-node selection, UCB math, expansion and branching across sampled opponent replies, terminal reward/backpropagation, cutoff heuristic, same-seed reproducibility, legal action/fallback, zero budget, finished-state behavior, no state/global-RNG mutation, and multiple real headless games using the shared resolver. Profile sample iteration budgets, report actual timing. Run full tests and smoke mode.

## Scope boundary
Do not add neural networks, reinforcement-learning training, hidden-action access, or graphical modes yet.
## Mandatory self-testing — no external browser
1. Run this module's tests, the complete existing test suite, and the project's documented headless application smoke test. Run any other commands specified above. Use timeouts for commands that can hang.
2. Test normal operation, invalid inputs, important edge cases, and integration with previous modules. Verify every acceptance item above and fix any discovered failures; rerun the affected checks.
3. Test the Pygame application locally, not in an external browser. If a graphical display is available, inspect the relevant local window and controls; if not, explicitly say visual inspection could not be performed. A dummy-driver smoke test is not visual verification.
4. Do not mark a module fully complete if a required test or acceptance criterion failed or could not be verified. State precisely what remains unresolved. Never invent test, benchmark or visual results.

## Final report
Report: files created/changed; skills actually read and used; public APIs and assumptions; exact commands executed; pass/fail/not-run result of each meaningful check; whether local visual inspection occurred; defects fixed; failures and environment limitations; acceptance criteria status; and the exact command to run the full test suite. Stop after this module.
```

---

## Module 13 — Game Modes and Headless Orchestration

Copy the complete prompt below into Antigravity.

```text
MODULE 13 OF 16 — GAME MODES AND HEADLESS ORCHESTRATION

You are my senior Python game developer and technical lead. Build BLADE ARENA, a university AI Lab 2D spinning-top game, one module at a time. Work only in the current workspace. Preserve existing user files, installed skills and previously working behavior; inspect the code, current documentation and tests first. Run a baseline full test suite and existing headless smoke test before changes when they exist. Report existing failures and fix only those directly related or necessary; do not silently remove assertions or tests.

Use Python 3.11/3.12, pygame-ce (imported as pygame), and pytest. Never install pygame and pygame-ce in the same environment. Keep the pure game engine, AI and headless orchestration independent of Pygame. The final game uses simultaneous actions, one shared deterministic rules engine, Ironclad Minimax, Cyclone MCTS and Mamdani fuzzy logic. Restrict AI algorithms to the course-approved set; do not substitute black-box AI, external APIs or unrelated algorithms. Read relevant installed `pygame-core`, `python-testing`, `game-docs`, `game-ui-ux` or `create-game-assets` skills if available, but do not add tools or run skill scripts automatically. State which skills you actually used.

Do not open an external browser for testing. Do not delete or overwrite unrelated work, push to GitHub, commit, publish, use paid services or start the next module unless explicitly asked. Follow the existing code's actual names where practical, keeping prior public APIs compatible. Document any necessary migration. Clearly label future capabilities and numerical assumptions; do not claim that unfinished features work.

## Objective
Implement reusable orchestration for Human vs AI and AI vs AI using the match controller, both agents and the same production rules. Establish a basic batch runner; detailed tournament analytics come in Module 16. UI integration comes in Module 15.

## Implementation
- Define a small participant interface for human action input and AI agents. Human action is supplied by the caller; never block tests waiting for keyboard input. Both participants choose from the same pre-round immutable snapshot. An AI must not receive the human's or other AI's committed action.
- AI vs AI supports Ironclad versus Cyclone, side swapping, start, pause, resume, restart, and one-round stepping. One step collects exactly one legal decision from each agent and resolves at most one round; it is rejected or documented as a no-op when paused or finished. AI budgets are separate from animation speed.
- Human vs AI accepts a human action and asks selected Ironclad or Cyclone with configured difficulty, without passing the hidden human action. Validate choices with shared legality API. Permit human to play either side. Do not silently substitute illegal human or AI actions; return a clear error. Maintain recovery/reselection on resolver errors.
- Provide a basic headless batch entry/API to run a configurable count of matches with explicit seeds and alternating starting sides; return per-match result data. Do not claim full statistics/export yet. Ensure completion through real terminal logic; add a defensive iteration guard that reports errors rather than fabricating a result.
- Keep orchestration independent of Pygame; add a small CLI or documented Python example if helpful, without forcing an interactive shell. Avoid worker threads until needed. Record action, logical game time and optional AI diagnostics in a compact round record. Don't expose pending choices prematurely.
- Document APIs, lifecycle, difficulty configuration, seeds, privacy, and current lack of GUI in `docs/game_modes.md`.

## Verification and acceptance
Test both AI pairings and human side choices; controlled stub agents observe identical pre-round state; no hidden-action leak; invalid action, pause/resume, one-step, restart, finished state, side swap, deterministic seeds and iteration guard. Run at least one complete real AI-vs-AI headless match with practical low budgets and a small headless batch. Full tests and smoke mode.

## Scope boundary
Do not build the final interface, detailed statistics exports, external servers or bracket tournaments.
## Mandatory self-testing — no external browser
1. Run this module's tests, the complete existing test suite, and the project's documented headless application smoke test. Run any other commands specified above. Use timeouts for commands that can hang.
2. Test normal operation, invalid inputs, important edge cases, and integration with previous modules. Verify every acceptance item above and fix any discovered failures; rerun the affected checks.
3. Test the Pygame application locally, not in an external browser. If a graphical display is available, inspect the relevant local window and controls; if not, explicitly say visual inspection could not be performed. A dummy-driver smoke test is not visual verification.
4. Do not mark a module fully complete if a required test or acceptance criterion failed or could not be verified. State precisely what remains unresolved. Never invent test, benchmark or visual results.

## Final report
Report: files created/changed; skills actually read and used; public APIs and assumptions; exact commands executed; pass/fail/not-run result of each meaningful check; whether local visual inspection occurred; defects fixed; failures and environment limitations; acceptance criteria status; and the exact command to run the full test suite. Stop after this module.
```

---

## Module 14 — Additional Stadium Variations

Copy the complete prompt below into Antigravity.

```text
MODULE 14 OF 16 — ADDITIONAL STADIUM VARIATIONS

You are my senior Python game developer and technical lead. Build BLADE ARENA, a university AI Lab 2D spinning-top game, one module at a time. Work only in the current workspace. Preserve existing user files, installed skills and previously working behavior; inspect the code, current documentation and tests first. Run a baseline full test suite and existing headless smoke test before changes when they exist. Report existing failures and fix only those directly related or necessary; do not silently remove assertions or tests.

Use Python 3.11/3.12, pygame-ce (imported as pygame), and pytest. Never install pygame and pygame-ce in the same environment. Keep the pure game engine, AI and headless orchestration independent of Pygame. The final game uses simultaneous actions, one shared deterministic rules engine, Ironclad Minimax, Cyclone MCTS and Mamdani fuzzy logic. Restrict AI algorithms to the course-approved set; do not substitute black-box AI, external APIs or unrelated algorithms. Read relevant installed `pygame-core`, `python-testing`, `game-docs`, `game-ui-ux` or `create-game-assets` skills if available, but do not add tools or run skill scripts automatically. State which skills you actually used.

Do not open an external browser for testing. Do not delete or overwrite unrelated work, push to GitHub, commit, publish, use paid services or start the next module unless explicitly asked. Follow the existing code's actual names where practical, keeping prior public APIs compatible. Document any necessary migration. Clearly label future capabilities and numerical assumptions; do not claim that unfinished features work.

## Objective
Add the proposal's initial stadium selection: Classic Dish, Ice Rink and Steep Bowl. Keep all effects in the shared game engine so AI sees the same outcomes as players.

## Rules
- Classic Dish: existing movement/push unchanged.
- Ice Rink: proposed 1.25× action movement and 1.25× attack push distance.
- Steep Bowl: proposed additional movement of up to 0.3 units toward center after the action movement and before hit checks. Cap at the center; calculate both blades independently from the same stage of the round.
- These modifiers are assumptions for balancing; the PDF specifies qualitative characteristics only. All stadiums use the same initial radius 10, shrink every six completed rounds to minimum 6, unless a future specification changes this. Rough Ground is future scope, not required here.

## Implementation
- Extend the stadium enum/definition registry without breaking the Classic default. Add immutable type definitions and allow optional stadium selection in the initial match factory. Preserve player selections and stadium across restart.
- Modify shared movement/combat rules at well-defined stages: scale Ice movement/push once; apply Steep center drift after action movement before attack range and successful-dodge margin checks; then hit/push, passive loss, shrink and terminal evaluation as already documented. Keep Dodge direction selection and safety test consistent with actual final movement; state precisely whether candidate comparison includes drift and implement consistently. Neither arena may bypass boundary checks or simultaneously resolved attacks.
- Make stadium definitions available to AI simulations, headless match modes and future UI. Document initial assumptions, order and their differences in `docs/stadium_types.md`. Do not introduce Pygame physics or nondeterministic movement.

## Verification and acceptance
Test all three types, Classic no-regression, Ice movement and push scaling exactly once, Steep drift and no overshoot, dodge near edge in each, hits and elimination after movement/push/shrink, early and min-radius milestones, configured match creation and restart, same outcomes through controller and direct resolver, AI simulations use selected stadium. Run representative headless matches, full suite and smoke mode.

## Scope boundary
Do not implement Rough Ground, obstacles, visual assets or a selection screen yet.
## Mandatory self-testing — no external browser
1. Run this module's tests, the complete existing test suite, and the project's documented headless application smoke test. Run any other commands specified above. Use timeouts for commands that can hang.
2. Test normal operation, invalid inputs, important edge cases, and integration with previous modules. Verify every acceptance item above and fix any discovered failures; rerun the affected checks.
3. Test the Pygame application locally, not in an external browser. If a graphical display is available, inspect the relevant local window and controls; if not, explicitly say visual inspection could not be performed. A dummy-driver smoke test is not visual verification.
4. Do not mark a module fully complete if a required test or acceptance criterion failed or could not be verified. State precisely what remains unresolved. Never invent test, benchmark or visual results.

## Final report
Report: files created/changed; skills actually read and used; public APIs and assumptions; exact commands executed; pass/fail/not-run result of each meaningful check; whether local visual inspection occurred; defects fixed; failures and environment limitations; acceptance criteria status; and the exact command to run the full test suite. Stop after this module.
```

---

## Module 15 — Pygame Interface and Visual Experience

Copy the complete prompt below into Antigravity.

```text
MODULE 15 OF 16 — PYGAME INTERFACE AND VISUAL EXPERIENCE

You are my senior Python game developer and technical lead. Build BLADE ARENA, a university AI Lab 2D spinning-top game, one module at a time. Work only in the current workspace. Preserve existing user files, installed skills and previously working behavior; inspect the code, current documentation and tests first. Run a baseline full test suite and existing headless smoke test before changes when they exist. Report existing failures and fix only those directly related or necessary; do not silently remove assertions or tests.

Use Python 3.11/3.12, pygame-ce (imported as pygame), and pytest. Never install pygame and pygame-ce in the same environment. Keep the pure game engine, AI and headless orchestration independent of Pygame. The final game uses simultaneous actions, one shared deterministic rules engine, Ironclad Minimax, Cyclone MCTS and Mamdani fuzzy logic. Restrict AI algorithms to the course-approved set; do not substitute black-box AI, external APIs or unrelated algorithms. Read relevant installed `pygame-core`, `python-testing`, `game-docs`, `game-ui-ux` or `create-game-assets` skills if available, but do not add tools or run skill scripts automatically. State which skills you actually used.

Do not open an external browser for testing. Do not delete or overwrite unrelated work, push to GitHub, commit, publish, use paid services or start the next module unless explicitly asked. Follow the existing code's actual names where practical, keeping prior public APIs compatible. Document any necessary migration. Clearly label future capabilities and numerical assumptions; do not claim that unfinished features work.

## Objective
Turn the existing project into a usable, original 2D application. Wire the real modes and rules; never display placeholder data as if it were live.

## Interface requirements
- Main menu: Human vs AI, AI vs AI, Tournament, Settings, Quit. A tournament screen may say “batch runner available; detailed results coming in Module 16” until the next module delivers full analytics; do not fake a tournament.
- Match setup: choose mode, agent opponent and difficulty where relevant, each blade type, stadium and side. Clearly label settings. Start a real match using the selected data.
- Battle screen: draw a circular arena with correctly scaled current radius and actual blade positions; two visually distinct original tops using simple generated shapes or properly licensed assets. Show each blade's type, energy/max, stability/max, danger number and label, Special availability, round 0–40, logical remaining time, recent event log and relevant AI decision diagnostics.
- Human controls: five labeled buttons and keys 1–5. Use shared legal-actions API to disable invalid actions and explain why. AI must not see the human selection. Offer pause/resume/restart and a route back to menu.
- AI vs AI controls: start/pause/resume, restart, adjustable playback speed, single-step exactly one round, and side swap before starting or by clearly restarting. Speed affects animation/display timing only, not logical game time or AI budgets. Handle window close/Escape intentionally.
- Result screen: winner/draw, finish reason, points if applicable, restart/back menu. Reflect actual game result and event records. Never expose pending opponent choices.
- Use consistent resolution/layout, legible text, non-color-only danger labels, keyboard access where reasonable, no copyrighted marks. Support the default window; handle resize or use a documented fixed size. Separate application scenes/views, input, render and controller/engine; no rule reimplementation in UI. Keep event loop responsive; if AI work is expensive, use an appropriate safe technique such as incremental decisions or a worker with immutable snapshots, without concurrent access to mutable Pygame state. Avoid unnecessary abstractions.
- Include simple visual feedback for attacks, dodge and shrinking only if driven by actual events. Use only local original or explicitly licensed assets; document attribution. No external browser for testing. Update README controls, setup and limitations.

## Verification and acceptance
Automate headless screen/navigation, event dispatch, legality/button disabled state, action mapping, drawn coordinates/radius calculations, pause/step/speed/restart/side swap, results, both real modes and regression. Use Pygame dummy driver and short AI budgets. If graphical display is available, personally run the local game and check readability, both modes, inputs and close; otherwise report visual validation as blocked, not passed. Full pytest and smoke mode. Document measured AI responsiveness and any limitations.

## Scope boundary
Do not fake tournament analytics, add a 3D engine, fetch copyrighted art, or replace game rules for display.
## Mandatory self-testing — no external browser
1. Run this module's tests, the complete existing test suite, and the project's documented headless application smoke test. Run any other commands specified above. Use timeouts for commands that can hang.
2. Test normal operation, invalid inputs, important edge cases, and integration with previous modules. Verify every acceptance item above and fix any discovered failures; rerun the affected checks.
3. Test the Pygame application locally, not in an external browser. If a graphical display is available, inspect the relevant local window and controls; if not, explicitly say visual inspection could not be performed. A dummy-driver smoke test is not visual verification.
4. Do not mark a module fully complete if a required test or acceptance criterion failed or could not be verified. State precisely what remains unresolved. Never invent test, benchmark or visual results.

## Final report
Report: files created/changed; skills actually read and used; public APIs and assumptions; exact commands executed; pass/fail/not-run result of each meaningful check; whether local visual inspection occurred; defects fixed; failures and environment limitations; acceptance criteria status; and the exact command to run the full test suite. Stop after this module.
```

---

## Module 16 — Tournament Evaluation, Logs, Final QA and Delivery

Copy the complete prompt below into Antigravity.

```text
MODULE 16 OF 16 — TOURNAMENT EVALUATION, LOGS, FINAL QA AND DELIVERY

You are my senior Python game developer and technical lead. Build BLADE ARENA, a university AI Lab 2D spinning-top game, one module at a time. Work only in the current workspace. Preserve existing user files, installed skills and previously working behavior; inspect the code, current documentation and tests first. Run a baseline full test suite and existing headless smoke test before changes when they exist. Report existing failures and fix only those directly related or necessary; do not silently remove assertions or tests.

Use Python 3.11/3.12, pygame-ce (imported as pygame), and pytest. Never install pygame and pygame-ce in the same environment. Keep the pure game engine, AI and headless orchestration independent of Pygame. The final game uses simultaneous actions, one shared deterministic rules engine, Ironclad Minimax, Cyclone MCTS and Mamdani fuzzy logic. Restrict AI algorithms to the course-approved set; do not substitute black-box AI, external APIs or unrelated algorithms. Read relevant installed `pygame-core`, `python-testing`, `game-docs`, `game-ui-ux` or `create-game-assets` skills if available, but do not add tools or run skill scripts automatically. State which skills you actually used.

Do not open an external browser for testing. Do not delete or overwrite unrelated work, push to GitHub, commit, publish, use paid services or start the next module unless explicitly asked. Follow the existing code's actual names where practical, keeping prior public APIs compatible. Document any necessary migration. Clearly label future capabilities and numerical assumptions; do not claim that unfinished features work.

## Objective
Complete the required tournament mode, reproducible AI comparison, reporting and submission readiness. Integrate with the real game and UI, not a mock.

## Tournament runner
- Run a user-configurable positive number of Ironclad vs Cyclone matches headlessly using the shared state, rules, agent interfaces and seeded RNG. Alternate/swapped starting sides, including fair handling of an odd count; record actual side counts. Accept blade types, stadium and AI depth/iteration budgets. Do not modify AI budgets when changing display speed.
- Save per-match JSON logs and a CSV summary under a configurable output directory. Record version/configuration, seed, side assignment, chosen blades/stadium, winner/draw, primary and applicable finish causes, completed rounds, logical seconds, per-agent decision count and timing, and algorithm budgets. If the engine has not retained needed events, extend it without changing its rules. Provide safe filenames, clear errors for unwritable paths, and avoid overwriting prior results by default.
- Compute wins/losses/draws; win and draw percentages with denominator explicitly total matches; average rounds/logical duration; mean decision time per agent over actual decisions; and finish counts including points and simultaneous draws. Check counts sum correctly and handle zero decisions/division by zero without fabricated values. Label wall-clock and logical time distinctly. Provide both AI side breakdowns and overall results.
- Add an accessible tournament UI that configures and runs the batch, shows progress, supports cancel without corrupting already completed results, and displays/export results. Keep Pygame responsive during long batches; avoid unsafe concurrent mutation. Clearly mark partial/cancelled runs and denominators. The tournament means repeated AI comparison; bracket mode is optional, not a prerequisite.

## Evaluation and final documentation
- Document a reproducible experiment with fixed seeds, explicit side swaps, Balanced/Classic baseline, exact depth and iteration settings, machine/Python/version, number of games and timing methodology. Aim for 100 matches only if feasible; if fewer were actually run, report the real count. Do not claim a universal winner or equal compute from depth/iteration budgets; report measured time and limitations of Cyclone's opponent model. Do not invent benchmark results.
- Complete README: installation Windows/macOS/Linux, run, controls, modes, tests, project structure, original/third-party asset and skills licenses, rules vs tuning assumptions, reproducible evaluation and known limitations. Add `docs/final_showcase.md` with demo/video capture checklist, algorithm explanation, results and GitHub submission steps, without claiming uploads or video creation occurred. Summarize manual and automated QA.

## Verification and acceptance
Test metrics with hand-constructed fixtures including all draws, points, simultaneous eliminations, missing decision timings, odd/even side assignment, cancellation and path errors; seed reproducibility excluding wall-clock durations; CSV/JSON round-trip; no duplicated or overwritten output; full games and result totals. Run a small real tournament with feasible budgets and report actual result counts and settings; perform the stated larger experiment only if time permits. Test UI headlessly, and visually check on a local display if available; otherwise report visual QA blocked. Run complete pytest, application smoke, both modes, representative stadiums and blades. Report actual commands, output paths, test outcomes and unresolved limitations; do not invent visual verification or user-facing files.

## Scope boundary
Do not publish to GitHub, record video, install services, or use an external browser without explicit authorization. Do not claim unexecuted work.
## Mandatory self-testing — no external browser
1. Run this module's tests, the complete existing test suite, and the project's documented headless application smoke test. Run any other commands specified above. Use timeouts for commands that can hang.
2. Test normal operation, invalid inputs, important edge cases, and integration with previous modules. Verify every acceptance item above and fix any discovered failures; rerun the affected checks.
3. Test the Pygame application locally, not in an external browser. If a graphical display is available, inspect the relevant local window and controls; if not, explicitly say visual inspection could not be performed. A dummy-driver smoke test is not visual verification.
4. Do not mark a module fully complete if a required test or acceptance criterion failed or could not be verified. State precisely what remains unresolved. Never invent test, benchmark or visual results.

## Final report
Report: files created/changed; skills actually read and used; public APIs and assumptions; exact commands executed; pass/fail/not-run result of each meaningful check; whether local visual inspection occurred; defects fixed; failures and environment limitations; acceptance criteria status; and the exact command to run the full test suite. Stop after this module.
```

---

