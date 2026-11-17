# BLADE ARENA — Win Conditions and Match Results

> **Status Notice:** This document specifies **Module 8: Win Conditions and Match Results**. It completes the core deterministic rules engine by defining elimination triggers (ring-out, burst, spin-out), evaluation timing, multiple cause priority hierarchy, simultaneous elimination draws, the 40-round points decision, and match lifecycle termination.

---

## 1. Overview and Core Invariants

A BLADE ARENA match concludes through one of two mechanisms:
1. **Knockout Elimination:** One or both blades are eliminated by losing containment or depleting essential resources.
2. **Points Decision:** If neither blade is eliminated after `40` completed rounds (`120.0` logical seconds), a normalized points formula resolves the victor.

Once a match reaches `MatchStatus.FINISHED`:
- `MatchState.result` is guaranteed to be a non-null `MatchResult`.
- Legal actions for both players become empty: `legal_actions(state, player_id) == ()`.
- Further action submissions or round resolution attempts raise `MatchFinishedError`.
- No 41st round can ever be resolved.

---

## 2. Elimination Criteria

| Elimination Type | Trigger Condition | Technical Check |
| :--- | :--- | :--- |
| **`RING_OUT`** | Blade center strictly outside current stadium radius. | `is_outside_stadium(position, radius, tolerance=1e-9)` |
| **`BURST`** | Blade angular stability reaches zero or less. | `current_stability <= 0.0` |
| **`SPIN_OUT`** | Blade rotational energy reaches zero or less. | `current_energy <= 0.0` |

### Boundary and Equality Convention
In accordance with Module 6 geometry rules:
- **Inside / Safe:** $d(P) \le r + \epsilon$ (equality is considered safe inside).
- **Ring-Out:** $d(P) > r + \epsilon$ (strictly outside the perimeter).

---

## 3. Evaluation Timing & Shrink-Induced Ring-Outs

Elimination checks occur strictly **after** all round events have resolved:
1. Planned displacements executed simultaneously.
2. Hit ranges evaluated and combat clashes resolved.
3. Stability damage, self-recoils, and guard counter-recoils applied.
4. Passive round energy loss applied.
5. Stadium radius shrunk (if round milestone reached, e.g. rounds 6, 12, 18, 24).
6. **Elimination Evaluated against Post-Shrink Stadium Radius.**

> [!IMPORTANT]
> Because elimination is evaluated against the *post-shrink* stadium radius, a blade that safely finishes its round at distance `9.4` in round 5 ($r = 10.0$) will suffer a **Ring-out** if round 6 shrinks the arena perimeter to $r = 9.0$.

---

## 4. Elimination Cause Priority Hierarchy

If a single blade satisfies multiple elimination conditions in the same round (for instance, knocked outside the arena while simultaneously taking fatal stability damage), the primary display reason follows a strict priority hierarchy:

$$\mathbf{1.\; RING\_OUT} \quad > \quad \mathbf{2.\; BURST} \quad > \quad \mathbf{3.\; SPIN\_OUT}$$

All applicable elimination causes are preserved in the extended `MatchResult.player_1_causes` and `MatchResult.player_2_causes` audit tuples.

---

## 5. Simultaneous Elimination and Draws

Because BLADE ARENA evaluates rounds simultaneously without player priority:
- If **both** combatants are eliminated in the same round (even through completely different causes, e.g. Player 1 bursts while Player 2 spins out):
  - `winner = None` (Draw).
  - `reason = FinishReason.SIMULTANEOUS_ELIMINATION`.
  - Both players' causes are preserved in `player_1_causes` and `player_2_causes`.
- If only **one** combatant is eliminated:
  - `winner` is assigned to the surviving player.
  - `reason` is set to the eliminated player's primary cause (`RING_OUT`, `BURST`, or `SPIN_OUT`).

---

## 6. 40-Round Points Decision (120 Logical Seconds)

Standard matches have a hard ceiling of `40` completed rounds (`STANDARD_MAX_ROUNDS = 40`).
With `SECONDS_PER_ROUND = 3.0s`, this establishes a `120.0`-second maximum logical match duration.

### Points Scoring Formula
If neither blade is eliminated upon concluding round 40, each blade receives a normalized score in $[0.0, 1.0]$:

$$\text{Score} = 0.40 \times \left(\frac{\text{energy}}{\text{max\_energy}}\right) + 0.40 \times \left(\frac{\text{stability}}{\text{max\_stability}}\right) + 0.20 \times \max\left(0, 1 - \frac{\text{distance\_from\_center}}{\text{current\_radius}}\right)$$

### Decision Rules
- Let $\Delta S = \text{Score}_1 - \text{Score}_2$.
- If $\Delta S > 10^{-6}$: Player 1 wins (`winner = player_1_id`, `reason = FinishReason.POINTS_DECISION`).
- If $\Delta S < -10^{-6}$: Player 2 wins (`winner = player_2_id`, `reason = FinishReason.POINTS_DECISION`).
- If $|\Delta S| \le 10^{-6}$: Draw (`winner = None`, `reason = FinishReason.POINTS_DECISION`).

> [!NOTE]
> **Knockout Priority:** A round-40 elimination takes strict precedence over a points decision. If a combatant bursts or spins out during round 40, the result is awarded as a knockout, not a points decision.

---

## 7. MatchResult Data Schema

```python
@dataclass(frozen=True)
class MatchResult:
    winner: Optional[str]                          # Winning player ID, or None for draws
    reason: FinishReason                           # RING_OUT, BURST, SPIN_OUT, SIMULTANEOUS_ELIMINATION, POINTS_DECISION
    player_1_causes: Tuple[FinishReason, ...] = () # All elimination causes affecting Player 1
    player_2_causes: Tuple[FinishReason, ...] = () # All elimination causes affecting Player 2
    scores: Optional[Tuple[float, float]] = None   # Final (p1_score, p2_score) if resolved by points
```

---

## 8. Public Win Condition API

```python
from blade_arena.game import (
    calculate_blade_points,
    evaluate_match_termination,
    get_blade_elimination_causes,
    is_match_terminal,
)

# 1. Inspect causes affecting an individual blade
causes = get_blade_elimination_causes(blade, stadium_radius=10.0)

# 2. Compute points score
score = calculate_blade_points(blade, stadium_radius=6.0)

# 3. Evaluate match state for terminality and outcome
result = evaluate_match_termination(match_state)
if result is not None:
    print(f"Match Concluded! Winner: {result.winner}, Reason: {result.reason.name}")
```
