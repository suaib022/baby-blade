# BLADE ARENA — Stadium Variations and Geometry

> **Status Notice:** This document specifies **Module 14: Additional Stadium Variations**. It defines the three arena archetypes from the proposal — **Classic Dish**, **Ice Rink**, and **Steep Bowl** — including balance parameters, order of operations, inward center drift, dodge consistency, and shrink dynamics.

---

## 1. Overview and Core Principles

In BLADE ARENA, stadium variations introduce distinct physical and tactical environments while adhering to the single shared, deterministic rules engine. Both human match controllers and autonomous AI simulation rollouts (Ironclad Minimax and Cyclone MCTS) use the exact same calculations.

### Core Design Principles
1. **Deterministic Purity:** No nondeterministic physics, floating-point randomness, or continuous Pygame collision routines are introduced. All displacements are computed via pure 2D vector geometry.
2. **Order Consistency:** Multipliers and drift displacements occur at strictly defined stages of the simultaneous round resolution pipeline.
3. **AI Transparency:** AI search trees directly evaluate game states under the active stadium's modifiers without heuristics or approximation tables.

---

## 2. Stadium Specifications Matrix

| Attribute | Classic Dish | Ice Rink | Steep Bowl | Implementation Source |
| :--- | :---: | :---: | :---: | :--- |
| **Enum Identifier** | `CLASSIC_DISH` | `ICE_RINK` | `STEEP_BOWL` | `blade_arena.game.models.StadiumType` |
| **Display Name** | Classic Dish | Ice Rink | Steep Bowl | `blade_arena.game.stadium_definitions` |
| **Action Movement Multiplier** | $1.00\times$ | $1.25\times$ | $1.00\times$ | `StadiumDefinition.movement_multiplier` |
| **Attack Knockback Push Multiplier** | $1.00\times$ | $1.25\times$ | $1.00\times$ | `StadiumDefinition.push_multiplier` |
| **Inward Center Drift** | $0.0\text{ units}$ | $0.0\text{ units}$ | $0.3\text{ units}$ | `StadiumDefinition.center_drift` |
| **Initial Radius** | $10.0\text{ units}$ | $10.0\text{ units}$ | $10.0\text{ units}$ | Standard arena radius |
| **Minimum Radius** | $6.0\text{ units}$ | $6.0\text{ units}$ | $6.0\text{ units}$ | Minimum shrunk radius |
| **Shrink Interval** | $6\text{ rounds}$ | $6\text{ rounds}$ | $6\text{ rounds}$ | Elapsed round trigger |
| **Shrink Decrement** | $1.0\text{ units}$ | $1.0\text{ units}$ | $1.0\text{ units}$ | Decrement per shrink milestone |

---

## 3. Order of Operations in Combat Resolution

Round resolution processes movement, arena modifiers, hit checks, and knockback in a strict sequence:

```
[Pre-Round State]
        │
        ▼
1. Action Movement (Scaled by Arena Movement Multiplier)
        │
        ▼
2. Steep Center Drift (Up to 0.3 Inward toward (0,0), Capped at Center)
        │
        ▼
3. Clash & Hit Range Detection (Measured at Post-Movement, Post-Drift Positions)
        │
        ▼
4. Dodge Evasion Margin Evaluation (>= 0.5 Margin Inside Boundary)
        │
        ▼
5. Hit Damage & Knockback Push Calculation (Scaled by Arena Push Multiplier)
        │
        ▼
6. Simultaneous Push Displacements Applied
        │
        ▼
7. Resource Progression (Costs, Recoveries, Passive Loss, Cooldowns)
        │
        ▼
8. Stadium Shrink Evaluation (Every 6 Completed Rounds)
        │
        ▼
9. Terminal Evaluation (Ring-out, Burst, Spin-out, Round 40 Points)
```

---

## 4. Detailed Stadium Mechanics

### 1. Classic Dish (`CLASSIC_DISH`)
- Baseline standard arena.
- Movement distances:
  - `CHARGE`: Up to $1.0\text{ units}$ toward arena center $(0, 0)$.
  - `ATTACK`: Up to $1.6\text{ units}$ toward opponent pre-round position.
  - `GUARD`: $0.0\text{ units}$ (stationary).
  - `DODGE`: $1.4\text{ units}$ sideways toward interior.
  - `SPECIAL_SPIN`: Up to $2.0\text{ units}$ toward opponent pre-round position.
- Knockback push:
  - Normal Attack base: $1.2\text{ units}$.
  - Special Spin base: $2.0\text{ units}$.

### 2. Ice Rink (`ICE_RINK`)
- Low-friction arena amplifying linear velocity and collision impact.
- **Action Movement (1.25x):**
  - `CHARGE`: $1.0 \times 1.25 = 1.25\text{ units}$.
  - `ATTACK`: $1.6 \times 1.25 = 2.00\text{ units}$.
  - `GUARD`: $0.0 \times 1.25 = 0.00\text{ units}$.
  - `DODGE`: $1.4 \times 1.25 = 1.75\text{ units}$.
  - `SPECIAL_SPIN`: $2.0 \times 1.25 = 2.50\text{ units}$.
- **Attack Push (1.25x):**
  - Normal Attack base: $1.2 \times 1.25 = 1.50\text{ units}$.
  - Special Spin base: $2.0 \times 1.25 = 2.50\text{ units}$.
  - Push is scaled exactly once during hit effect calculation.

### 3. Steep Bowl (`STEEP_BOWL`)
- Funnel-shaped dish where gravitational gradient pulls combatants toward the center.
- **Center Drift:**
  - After action movement, an inward radial displacement of up to $0.3\text{ units}$ is applied toward $(0, 0)$.
  - **Center Cap:** If distance to center $d \le 0.3$, the blade is placed directly at $(0, 0)$. It never overshoots or oscillates past the origin.
  - Calculated independently for both blades from the same post-action stage.
- **Dodge Consistency:**
  - When evaluating perpendicular dodge candidates ($C_1, C_2$), the $0.3$ center drift is applied to each candidate *prior* to boundary margin comparison:
    $$C'_i = \text{apply\_center\_drift}(C_i, 0.3)$$
  - The blade selects the candidate whose post-drift position yields the greatest interior margin. This guarantees that candidate comparison, final blade position, and the dodge evasion threshold check ($0.5\text{ margin}$) remain completely consistent.

---

## 5. Shrink Schedule Across All Stadiums

All three stadium variations follow the identical shrink milestone schedule:

| Completed Rounds | Logical Game Time | Stadium Radius |
| :---: | :---: | :---: |
| **0 – 5** | $0.0\text{s} - 15.0\text{s}$ | $10.0\text{ units}$ |
| **6 – 11** | $18.0\text{s} - 33.0\text{s}$ | $9.0\text{ units}$ |
| **12 – 17** | $36.0\text{s} - 51.0\text{s}$ | $8.0\text{ units}$ |
| **18 – 23** | $54.0\text{s} - 69.0\text{s}$ | $7.0\text{ units}$ |
| **24 – 40** | $72.0\text{s} - 120.0\text{s}$ | $6.0\text{ units}$ (Minimum) |

---

## 6. API and Match Integration

### Factory Creation
```python
from blade_arena.game.initial_state import create_initial_match
from blade_arena.game.models import BladeType, StadiumType

# Create an Ice Rink match
match = create_initial_match(
    player_1_blade_type=BladeType.ATTACKER,
    player_2_blade_type=BladeType.DEFENDER,
    stadium_type=StadiumType.ICE_RINK,
)
```

### CLI Batch Execution
```bash
# Run headless batch in Steep Bowl
python main.py --batch 5 --stadium steep_bowl --agent1 ironclad --agent2 cyclone
```
