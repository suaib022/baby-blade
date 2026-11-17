# BLADE ARENA — Classic Stadium Geometry and Movement

> **Status Notice:** This document specifies **Module 6: Classic Stadium, Geometry and Movement**. It defines the 2D Cartesian coordinate system, stadium shrinking schedule, pure vector geometry, toward-target movement calculations, overshoot prevention, dodge candidate selection, and boundary evasion checks. Action execution, collision physics, stability damage, recoil deduction, knockback momentum, and match result awarding are **not implemented** in this module.

---

## 1. 2D Coordinate System and Stadium Setup

BLADE ARENA simulates combat inside a circular dish defined on a continuous 2D Cartesian plane:

- **Arena Origin / Center:** `Position(0.0, 0.0)`.
- **Horizontal Axis ($X$):** Positive to the right, negative to the left.
- **Vertical Axis ($Y$):** Positive upward, negative downward.
- **Initial Combatant Coordinates:**
  - Player 1 starts at `Position(-2.0, 0.0)` (left side).
  - Player 2 starts at `Position(2.0, 0.0)` (right side).
- **Initial Stadium Radius:** `10.0` arena units (`INITIAL_STADIUM_RADIUS = 10.0`).
- **Minimum Stadium Radius:** `6.0` arena units (`MIN_STADIUM_RADIUS = 6.0`).
- **Numerical Tolerance:** Comparisons near boundaries use `DEFAULT_GEOMETRY_EPSILON = 1e-9`.

---

## 2. Stadium Shrinking Schedule

The arena perimeter shrinks inward dynamically over match progression:

- **Shrink Interval:** Every `6` completed rounds (`SHRINK_INTERVAL_ROUNDS = 6`).
- **Shrink Decrement:** `1.0` arena units per step (`SHRINK_DECREMENT = 1.0`).
- **Mathematical Formula:**
  $$\text{shrink\_steps} = \left\lfloor \frac{\text{completed\_rounds}}{6} \right\rfloor$$
  $$r(\text{completed\_rounds}) = \max\left(r_{\text{min}}, r_0 - \text{shrink\_steps} \times \Delta r\right)$$

### Milestone Radius Progression

| Completed Rounds | Arena Radius ($r$) | Logical Elapsed Time | Notes |
| :---: | :---: | :---: | :--- |
| **0 – 5** | **10.0** | 0.0s – 15.0s | Starting arena dimensions |
| **6 – 11** | **9.0** | 18.0s – 33.0s | First perimeter shrink |
| **12 – 17** | **8.0** | 36.0s – 51.0s | Second perimeter shrink |
| **18 – 23** | **7.0** | 54.0s – 69.0s | Third perimeter shrink |
| **24+** | **6.0** | 72.0s+ | Final shrink milestone; clamped at minimum radius |

> [!NOTE]
> The stadium radius is calculated as an idempotent pure function of `initial_radius` and `completed_rounds`. This guarantees that state reconstructions and AI rollout evaluations cannot accidentally double-shrink or drift.

---

## 3. Boundary Conventions and Ring-Out Definition

Boundary queries evaluate the Euclidean distance between a position and the arena center:

$$d(P) = \sqrt{(P_x - C_x)^2 + (P_y - C_y)^2}$$
$$\text{boundary\_margin}(P) = r - d(P)$$

- **Inside Arena (`is_inside_stadium`):**
  A blade is inside or on the boundary if $d(P) \le r + \epsilon$ (or $\text{margin} \ge -\epsilon$). Equality is explicitly treated as inside.
- **Outside Arena / Ring-Out Territory (`is_outside_stadium`):**
  A blade center is strictly outside the boundary if $d(P) > r + \epsilon$ (or $\text{margin} < -\epsilon$).
- **No Result Awarding:**
  While `is_outside_stadium()` provides the pure containment query, Module 6 does **not** terminate matches or award victory results. Result assignment belongs strictly to Module 8.

---

## 4. Movement Tuning Assumptions (Proposed Values)

Movement distances in arena units are calibrated starting values (labeled *proposed* in the project specification, rather than immutable PDF laws):

| Action | Target Destination | Move Distance | Overshoot Prevention | Dodge Success |
| :--- | :--- | :---: | :---: | :---: |
| **`Charge`** | Arena center `(0.0, 0.0)` | `1.0` | Capped at center `(0, 0)` | Always `False` |
| **`Attack`** | Opponent pre-round position | `1.6` | Capped at opponent | Always `False` |
| **`Guard`** | Stationary (no movement) | `0.0` | N/A | Always `False` |
| **`Dodge`** | Selected orthogonal lateral candidate | `1.4` | Fixed travel step | Evaluated by margin |
| **`Special Spin`**| Opponent pre-round position | `2.0` | Capped at opponent | Always `False` |

### Overshoot Prevention
When moving toward a target (Charge, Attack, Special Spin), travel distance is capped:
$$\text{actual\_step} = \min(\text{max\_distance}, \text{distance\_to\_target})$$
If $\text{distance\_to\_target} \le \text{max\_distance}$, the blade stops exactly at the target coordinates without crossing or oscillating past the destination.

---

## 5. Dodge Mechanics and Deterministic Tie-Breaking

Dodge allows a blade to sidestep orthogonally to the line of engagement.

### 1. Vector Orthogonality
Given the acting blade's position $P_{\text{self}}$ and opponent's position $P_{\text{opp}}$, the engagement vector is:
$$\vec{v} = P_{\text{opp}} - P_{\text{self}} = (\Delta x, \Delta y)$$
Normalized unit vector: $\hat{u} = (u_x, u_y)$.
The two orthogonal perpendicular directions in 2D space are:
- **Candidate 1 (Counter-Clockwise / Left):** $\hat{n}_1 = (-u_y, u_x)$
- **Candidate 2 (Clockwise / Right):** $\hat{n}_2 = (u_y, -u_x)$

Candidate destination coordinates ($d_{\text{dodge}} = 1.4$):
$$C_1 = P_{\text{self}} + 1.4 \times \hat{n}_1$$
$$C_2 = P_{\text{self}} + 1.4 \times \hat{n}_2$$

### 2. Candidate Selection (Inward Preference)
The system calculates the boundary margin for both candidates:
$$\text{margin}_1 = r - \sqrt{C_{1x}^2 + C_{1y}^2}$$
$$\text{margin}_2 = r - \sqrt{C_{2x}^2 + C_{2y}^2}$$

The candidate with the **larger boundary margin** (closer to arena center) is selected.

### 3. Deterministic Tie-Breaking Hierarchy
If $|\text{margin}_1 - \text{margin}_2| \le \epsilon$ (both candidates are equidistant from the arena boundary, such as along lines of symmetry):
1. **Higher $Y$ Coordinate:** Choose the candidate with greater $Y$ ($C_{1y} > C_{2y}$).
2. **Higher $X$ Coordinate:** If $Y$ coordinates are tied within tolerance, choose the candidate with greater $X$ ($C_{1x} > C_{2x}$).
3. **CCW Fallback:** If both coordinates coincide, choose Candidate 1 (CCW).

### 4. Dodge Evasion Threshold & Near-Edge Failure
- **Evasion Requirement:** Dodge succeeds only if its destination position satisfies:
  $$\text{boundary\_margin}(P_{\text{dodge}}) \ge 0.5 - \epsilon$$
  (`DODGE_EVASION_MARGIN_THRESHOLD = 0.5`).
- **Near-Edge Failure:** If the margin is less than 0.5 units, the blade still moves to the candidate position, but `dodge_success` is flagged as `False`. In future Module 7 combat resolution, this blade will not evade incoming attacks.

---

## 6. Coincident Positions and Edge Cases

- **Blade Coincidence ($P_1 = P_2$):**
  When two blades occupy the exact same position, the vector between them has length zero.
  - Attack and Special Spin: Distance is 0, capped at target (distance 0), so the blade remains stationary.
  - Dodge: Requires an engagement direction to construct perpendiculars. The system applies deterministic fallback vectors:
    - Player 1 Fallback: `(1.0, 0.0)` (facing +X).
    - Player 2 Fallback: `(-1.0, 0.0)` (facing -X).
    Perpendicular candidates and tie-breaks execute without division-by-zero errors.
- **Center Coincidence:**
  A blade at `Position(0.0, 0.0)` selecting Charge has distance 0 to the center and remains at `(0.0, 0.0)`.

---

## 7. Pairwise Simultaneous Planned Movement

Both combatants calculate their planned positions simultaneously using the common pre-round state snapshot:

```python
from blade_arena.game import (
    Action,
    calculate_match_planned_movement,
    calculate_planned_movement,
)

# Pairwise movement from MatchState
result = calculate_match_planned_movement(
    match_state=match,
    action_1=Action.ATTACK,
    action_2=Action.DODGE,
)

print(result.player_1_position)      # Destination for Player 1
print(result.player_2_position)      # Destination for Player 2
print(result.player_1_dodge_success) # False (Attack)
print(result.player_2_dodge_success) # True/False based on margin
```

Neither `MatchState` nor `BladeState` is mutated.

---

## 8. Scope Boundaries

The following systems are **not** implemented in Module 6:
- Attack hit-boxes and distance-to-hit checks (Module 7).
- Stability damage calculation and power modifiers (Module 7).
- Knockback push vectors and contact recoil (Module 7).
- Passive energy loss application (Module 7).
- Win condition checks and match result assignment (Module 8).
- Alternative arena variations, hazards, or friction modifiers (Module 14).
