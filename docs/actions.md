# BLADE ARENA — Action Definitions and Legality Rules

> **Status Notice:** This document specifies **Module 5: Action Definitions and Legality**. It establishes the baseline costs, recoils, cooldown constraints, and pure legality queries for all five combat actions. Action application, kinetic movement, recoil deductions, recovery application, and combat damage remain unexecuted until subsequent modules.

---

## 1. Action Metadata Matrix

All five turn actions are registered in `blade_arena/game/actions.py` as immutable `ActionDefinition` records:

| Action | Display Name | Energy Cost | Stability Recoil | Requires Cooldown | Cooldown Duration | Tactical Role & Behavior |
| :--- | :--- | :---: | :---: | :---: | :---: | :--- |
| **`CHARGE`** | Charge | **0** | 0 | No | 0.0s | Advances toward stadium center; recovers energy. Vulnerable to attacks. |
| **`ATTACK`** | Attack | **8** | 0 | No | 0.0s | Advances toward opponent; inflicts stability damage and knockback push. |
| **`GUARD`** | Guard | **4** | 0 | No | 0.0s | Braces in place; recovers stability; mitigates incoming damage and push. |
| **`DODGE`** | Dodge | **8** | 0 | No | 0.0s | Sidesteps lateral to opponent line; evades normal and special attacks. |
| **`SPECIAL_SPIN`** | Special Spin | **35** | **10** | **Yes** | **3.0s** | Signature high-power attack; inflicts heavy damage/push with self-recoil. |

---

## 2. Archetype-Specific Recovery Integration

Recovery amounts for **Charge** and **Guard** are not hardcoded per action; they are defined in and retrieved from the combatant's **Module 4 Archetype Definition** (`BladeDefinition`):

| Blade Archetype | Charge Energy Recovery | Guard Stability Recovery |
| :--- | :---: | :---: |
| **`BALANCED`** | +20.0 energy | +5.0 stability |
| **`ATTACKER`** | +20.0 energy | +5.0 stability |
| **`DEFENDER`** | +20.0 energy | **+10.0 stability** |
| **`STAMINA`**  | **+25.0 energy** | +5.0 stability |

*Recovery values are queried via `get_action_recovery(blade_type, action)` and will be applied by the future round resolver, capped at the blade's maximum attributes.*

---

## 3. Pure Legality Query Rules

An action is legal for a combatant if and only if all following conditions are satisfied:

1. **Match Status:** The match must be `MatchStatus.IN_PROGRESS`. Finished matches offer **zero** legal actions.
2. **Energy Cost Payable:** The combatant's current energy must be greater than or equal to the action's energy cost (`blade.current_energy >= action_def.energy_cost`).
   - *Charge has energy cost 0, making it always payable even at 0 energy.*
3. **Cooldown Availability (Special Spin):** If `requires_cooldown` is True, current logical game time must have reached or passed the blade's ready timestamp (`state.elapsed_game_time >= blade.special_ready_at`).

### Boundary Nuance (Zero Resources):
- The legality query does **not** treat a blade with 0 stability or 0 energy as eliminated. In accordance with the modular architecture, outcome and victory determinations belong exclusively to Module 8.

---

## 4. Legality API

```python
from blade_arena.game import (
    Action,
    check_action_legality,
    is_action_legal,
    legal_actions,
)

# 1. Detailed legality evaluation with descriptive failure reasons
result = check_action_legality(match_state, "player_1", Action.SPECIAL_SPIN)
if not result.is_legal:
    print(result.reason) # e.g. "Insufficient energy for Special Spin: requires 35.0, available 20.0"

# 2. Simple boolean check
can_attack = is_action_legal(match_state, "player_1", Action.ATTACK)

# 3. Deterministic canonical list of legal choices
# Always ordered: CHARGE, ATTACK, GUARD, DODGE, SPECIAL_SPIN
available = legal_actions(match_state, "player_1")
```

---

## 5. Simultaneous Action Principle

In BLADE ARENA, both players select their actions simultaneously:
- **Identical Information:** Both players' legal actions are evaluated strictly against the **same pre-round state snapshot**.
- **No Hidden Opponent Knowledge:** Action legality queries depend only on public match state and the player's own blade attributes. Opponent pending commitments are completely excluded.
- **Determinism:** `legal_actions` always returns choices in canonical priority order (`ORDERED_ACTIONS`), ensuring deterministic evaluation across human UIs and AI search trees.

---

## 6. Cooldown Timing Specification

The project specification states:
> *"Special Spin: cooldown 3 seconds."*

Because each logical round advances game time by **3.0 seconds** (`SECONDS_PER_ROUND = 3.0`), a Special Spin executed at round start time $t$ sets the next ready timestamp to $t + 3.0\,\text{s}$ in the future round resolver.
Consequently:
- At round $N$ ($t = 0.0\,\text{s}$), Special Spin is executed.
- Next ready-at is stamped to $t + 3.0 = 3.0\,\text{s}$.
- At round $N+1$ ($t = 3.0\,\text{s}$), `elapsed_game_time >= 3.0` is satisfied, making Special Spin eligible again.

This follows the literal text of the PDF specification directly without introducing arbitrary round counters.

---

## 7. MatchController Integration Contract

To maintain full backward compatibility with test scaffolding from Modules 3 and 4 while enabling strict enforcement:

- **Default Behavior (`enforce_legality=False`):** `MatchController` accepts any valid `Action` enum instance submitted by a valid player, allowing test fixtures to simulate arbitrary sequences without micro-managing energy.
- **Strict Enforcement Mode (`enforce_legality=True`):** When instantiated with `enforce_legality=True`, `controller.submit_action()` invokes `check_action_legality()`. Submitting an illegal action raises an immediate `ActionSubmissionError`.
- **Query Helper:** Regardless of enforcement mode, `controller.get_legal_actions(player_id)` is available to query the legal actions for any player in the current round.

---

## 8. Deliberately Deferred (Not in Module 5)

- **Action Application:** Energy costs and stability recoils are not deducted upon querying.
- **Recovery Application:** Guard stability gains and Charge energy gains are not added to state.
- **Kinematic Movement:** Vector displacements (toward center, toward opponent, lateral dodge) are deferred to Module 6.
- **Combat Resolution:** Hit detection, damage multipliers, guard recoils, and push vectors are deferred to Module 7.
