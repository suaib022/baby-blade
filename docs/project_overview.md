# BLADE ARENA — Project Overview

> **Status Notice:** This project has completed **all 16 modules** of the master specification. An interactive 2D visual application powered by Pygame Community Edition (`pygame-ce`) is fully functional alongside complete headless AI engines, tournament batch evaluation, telemetry logging, and exhaustive automated test suites.

---

## 1. High-Level Vision

**BLADE ARENA** is an AI-oriented university laboratory project featuring a 2D spinning-top battle game built in Python with **Pygame Community Edition (`pygame-ce`)**.

Two spinning blades duel inside a circular battle stadium under dynamic physical and tactical constraints. Rather than twitch-reflex arcade controls, BLADE ARENA combines physical simulation with simultaneous turn-based decision making, where blade combatants balance energy, angular stability, positioning, and arena shrinkage.

---

## 2. Intended Game Modes

The final architecture will support three distinct game modes:

1. **Human vs. AI:** A human operator commands one blade via simultaneous action selection against an AI opponent.
2. **AI vs. AI:** Two autonomous agents compete head-to-head under controlled initial conditions to benchmark algorithmic strategies.
3. **Tournament Mode:** Automated round-robin or bracketed tournament series with aggregate performance statistics, telemetry logging, and win-rate analytics.

---

## 3. Intended AI Techniques

In accordance with the project specification and laboratory requirements, AI agents will adhere strictly to dedicated algorithmic methods:

- **Ironclad AI (Minimax):** Depth-limited adversarial tree search enhanced with iterative deepening and heuristic evaluation of stability, position, and ring-out threat.
- **Cyclone AI (MCTS):** Monte Carlo Tree Search employing selection, expansion, rollouts (simulation), and backpropagation to evaluate high-uncertainty state spaces.
- **Danger Assessment (Mamdani Fuzzy Inference System):** A formal fuzzy logic engine assessing situational risk based on stadium proximity, residual angular stability, and relative velocity.

*Note: As mandated by the project guidelines, these algorithms will be built directly and will not be replaced by generic third-party neural networks or off-the-shelf AI services.*

---

## 4. Planned Game Rules and Source of Truth

The primary source of truth for the game rules, attributes, and victory conditions is the official project proposal/PDF specification:

- **Five Turn Actions:** Charge, Attack, Guard, Dodge, and Special Spin.
- **Victory Conditions:** Ring-out (ejected from stadium), Burst (catastrophic stability loss), Spin-out (depleted rotational energy), and Draw.
- **Stadium Dynamics:** Circular boundary with progressive shrinkage over elapsed match rounds.
- **Numeric Calibration:** All balance values (mass, friction, knockback vectors, energy decay, stability thresholds) will be explicitly documented and calibrated in their respective feature documentation before implementation.

---

## 5. Modular Engineering Roadmap

The project is structured into incremental, verifiable modules adhering to the 16-module master specification:

- **Module 1 (Completed):** Project foundation, settings centralization, runnable shell, and headless smoke verification.
- **Module 2 (Completed):** Core game state and data models (pure-Python immutable representations for positions, blades, stadium, actions, and match lifecycle).
- **Module 3 (Completed):** Turn and match flow coordination (simultaneous action collection, round resolver interface, pause/resume/restart, and failure handling).
- **Module 4 (Completed):** Blade types and archetype statistics (Balanced, Attacker, Defender, Stamina specifications, factories, and controller integration).
- **Module 5 (Completed):** Action definitions and legality queries (energy costs, cooldown checks, canonical action ordering, and pure-function legality validation).
- **Module 6 (Completed):** Classic stadium, geometry, boundary containment, shrink schedule, and pure pairwise planned movement.
- **Module 7 (Completed):** Combat and simultaneous round resolution (interaction matrix, clash, damage, knockback, recovery, passive loss, and stadium shrink).
- **Module 8 (Completed):** Win conditions and match results (ring-out, burst, spin-out, timeout points evaluation, simultaneous elimination draws, and lifecycle finalization).
- **Module 9 (Completed):** Mamdani fuzzy danger estimation (interpretable, deterministic fuzzy inference system for dynamic threat assessment).
- **Module 10 (Completed):** Shared AI heuristic evaluation function (perspective-aware state scoring, terminal dominance, and MCTS rollout rewards).
- **Module 11 (Completed):** Ironclad AI (depth-limited Minimax with iterative deepening, alpha-pruning, and simultaneous-action conservatism).
- **Module 12 (Completed):** Cyclone AI (Monte Carlo Tree Search with simultaneous-action modeling, UCB1 selection, simulation rollouts, and isolated RNG).
- **Module 13 (Completed):** Game modes and headless match orchestration (Human vs AI, AI vs AI, session lifecycle, side swapping, and batch runner).
- **Module 14 (Completed):** Additional stadium variations (Classic Dish, Ice Rink, and Steep Bowl balance parameters, scaling, and center drift).
- **Module 15 (Completed):** Pygame interface, visual experience, HUD, procedural tops, combat VFX, and interactive controls.
- **Module 16 (Completed):** Tournament evaluation, reproducible AI comparison, structured telemetry logging (JSON/CSV), final QA, and delivery packaging.
