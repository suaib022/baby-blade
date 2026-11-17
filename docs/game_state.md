# BLADE ARENA — Core Game State & Data Models

> **Status Notice:** This document specifies **Module 2: Core Game State and Data Models**. The data models define the pure-Python representation of the arena, combatants, actions, and match lifecycle. Combat mechanics, collision handling, action resolution, and AI decision systems remain unbuilt until subsequent modules.

---

## 1. Purpose of the Core State Models

The primary architectural goal of BLADE ARENA's state models is to provide an **immutable, deterministic, pure-Python state representation** that is decoupled entirely from Pygame rendering and hardware devices.

This separation ensures:
- **AI Readiness:** Search algorithms (Minimax with iterative deepening for Ironclad AI, Monte Carlo Tree Search for Cyclone AI) can explore branching simulation paths rapidly by copying or deriving states without side effects.
- **Headless Simulation:** Tournaments and automated regression test suites can execute at maximum CPU speed without needing a display or audio subsystem.
- **State Integrity:** Immutable (frozen) dataclasses prevent accidental mutations across game loops, UI overlays, or parallel evaluation trees.

---

## 2. Model Specifications

All models are located in `blade_arena/game/models.py`.

### A. `Position`
Represents 2D Cartesian coordinates in stadium space:
- `x: float` — Horizontal coordinate (finite numeric).
- `y: float` — Vertical coordinate (finite numeric).

Methods:
- `distance_to(other: Position) -> float`: Calculates Euclidean distance between two points ($\sqrt{(x_1 - x_2)^2 + (y_1 - y_2)^2}$).
- `distance_from_center() -> float`: Calculates distance from the origin $(0, 0)$.

### B. `Action` (Enum)
Represents the five canonical simultaneous action choices:
- `CHARGE`: Accumulates energy/stability.
- `ATTACK`: Direct offensive collision against the opponent.
- `GUARD`: Defensive posture mitigating incoming impact.
- `DODGE`: Evasive displacement to avoid contact.
- `SPECIAL_SPIN`: High-impact signature technique subject to availability cooldown.

*(Note: Action costs, effects, and resolution matrices are deferred to Module 4.)*

### C. `BladeState`
Represents the physical and tactical state of an individual spinning top:
- `player_id: str` — Unique, non-empty identifier (e.g. `"player_1"`).
- `blade_type: BladeType` — Archetype classification (`BladeType.BALANCED`).
- `current_energy: float` — Current rotational energy reservoir ($\ge 0.0, \le \text{max\_energy}$).
- `max_energy: float` — Upper limit for rotational energy ($> 0.0$).
- `current_stability: float` — Angular balance and tilt resistance ($\ge 0.0, \le \text{max\_stability}$).
- `max_stability: float` — Maximum stability rating ($> 0.0$).
- `position: Position` — Current coordinate in the stadium.
- `special_ready_at: float` — Earliest logical game time (in seconds) when Special Spin becomes eligible for selection ($\ge 0.0$).

### D. `StadiumState`
Represents the circular battle dish:
- `stadium_type: StadiumType` — Layout variant (`StadiumType.CLASSIC_DISH`).
- `center: Position` — Origin coordinate of the dish (default `(0.0, 0.0)`).
- `radius: float` — Current boundary radius in arena units ($> 0.0$).

### E. `MatchResult`
Holds final outcome details for completed matches:
- `winner: Optional[str]` — Player ID of victorious combatant, or `None` if a draw occurred.
- `reason: FinishReason` — Enum representing the conclusion cause:
  - `RING_OUT`: Blade expelled beyond the active stadium radius.
  - `BURST`: Critical stability breakdown under impact shock.
  - `SPIN_OUT`: Depletion of all rotational energy.
  - `SIMULTANEOUS_ELIMINATION`: Mutual expulsion or concurrent resource exhaustion.
  - `POINTS_DECISION`: Match concluded at the 40-round time ceiling and resolved on points/remaining resources.

### F. `MatchState`
Top-level container encapsulating the complete match context:
- `player_1_blade: BladeState` — State of Player 1's blade.
- `player_2_blade: BladeState` — State of Player 2's blade.
- `stadium: StadiumState` — Current arena boundary.
- `completed_rounds: int` — Authoritative count of concluded turn cycles ($\ge 0$).
- `status: MatchStatus` — Lifecycle phase (`IN_PROGRESS` or `FINISHED`).
- `result: Optional[MatchResult]` — Outcome details (`None` while `IN_PROGRESS`, required when `FINISHED`).

Derived Property:
- `elapsed_game_time: float` — Logical game time in seconds, computed directly as $\text{completed\_rounds} \times 3.0\,\text{s}$.

---

## 3. Match Status vs. Match Result

- **`MatchStatus`** tracks the active state machine phase:
  - `MatchStatus.IN_PROGRESS`: The match is actively accepting turn inputs. It is an error (`ValueError`) for `result` to be set while in progress.
  - `MatchStatus.FINISHED`: The match has concluded. It is an error (`ValueError`) for `result` to be `None` when finished.
- **`MatchResult`** provides post-match telemetry (`winner`, `reason`). It is generated only upon terminal transition and never invented for a newly initialized match.

---

## 4. Completed Rounds vs. Logical Game Time

- **Authoritative Value:** `completed_rounds: int` is the sole recorded time attribute in `MatchState`.
- **Game Time Conversion:** Each completed round advances logical game time by exactly **3.0 seconds** (`SECONDS_PER_ROUND = 3.0`).
- **Standard Ceiling:** Standard matches last at most **40 rounds** (120.0 seconds of logical game time).
- Decoupling logical rounds from physical rendering frames ensures game rules remain 100% deterministic regardless of host machine FPS or display refresh rates.

---

## 5. Default Match Creation

The factory function `create_default_match()` in `blade_arena/game/initial_state.py` generates a standard initial match:

```python
from blade_arena.game import create_default_match

match = create_default_match()
print(match.player_1_blade.current_energy)    # 100.0
print(match.player_2_blade.current_stability) # 100.0
print(match.stadium.radius)                   # 10.0
print(match.completed_rounds)                 # 0
print(match.status)                           # MatchStatus.IN_PROGRESS
print(match.result)                           # None
```

---

## 6. Immutable State Derivation

Because all state models are frozen dataclasses, states are derived without mutating predecessor states via standard `dataclasses.replace`:

```python
import dataclasses
from blade_arena.game import create_default_match

initial = create_default_match()

# Derive a state where Player 1 has sustained energy loss
damaged_p1 = dataclasses.replace(initial.player_1_blade, current_energy=65.0)

# Derive new match state advancing to round 1
next_state = dataclasses.replace(
    initial,
    player_1_blade=damaged_p1,
    completed_rounds=1
)

# Original state remains unaltered:
assert initial.player_1_blade.current_energy == 100.0
assert initial.completed_rounds == 0
assert initial.elapsed_game_time == 0.0

# Derived state reflects changes:
assert next_state.player_1_blade.current_energy == 65.0
assert next_state.completed_rounds == 1
assert next_state.elapsed_game_time == 3.0
```

---

## 7. Specification Tracing: PDF vs. Implementation Assumptions

### Directly Specified in Project PDF:
- **Two blades in a circular stadium.**
- **Initial energy:** 100 units.
- **Balanced blade initial stability:** 100 units.
- **Initial stadium radius:** 10.0 units.
- **Minimum stadium radius:** 6.0 units (shrinking mechanic).
- **Stadium type:** Classic Dish.
- **Round timing:** 3.0 seconds per round, 40 rounds max duration (120.0 seconds).
- **Five actions:** Charge, Attack, Guard, Dodge, Special Spin.
- **Outcome reasons:** Ring-out, Burst, Spin-out, Draw, Simultaneous elimination.

### Proposed Implementation Assumptions (Documented Defaults):
- **Maximum energy:** Fixed to 100.0 for default Balanced blades.
- **Stadium origin:** Centered at coordinate $(0.0, 0.0)$.
- **Initial combatant positions:** Symmetrically placed along the x-axis:
  - Player 1: $(-2.0, 0.0)$
  - Player 2: $(2.0, 0.0)$
- **Special Spin eligibility:** Begins ready at game time 0.0 seconds (`special_ready_at = 0.0`).
- **Player identifiers:** Default string labels `"player_1"` and `"player_2"`.

---

## 8. Deliberately Deferred (Not Implemented in Module 2)

The following mechanics are explicitly out of scope for Module 2 and will be introduced in subsequent modules:
- Action costs, energy deductions, or cooldown timers.
- Kinetic physics, velocity, momentum, and angular acceleration.
- Spatial collision detection between blades and circular perimeter containment.
- Turn selection input, simultaneous action matrices, and damage resolution.
- Stadium shrinking rate calculations.
- Win/loss outcome evaluation functions.
- Minimax, MCTS, and Mamdani fuzzy inference evaluation engines.
