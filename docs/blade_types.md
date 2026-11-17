# BLADE ARENA — Blade Types and Archetype Statistics

> **Status Notice:** This document specifies **Module 4: Blade Types and Statistics**. It establishes the pure-Python definition models, archetype statistics, and initial state generation for the four canonical blade types. Combat resolution, passive energy decay, attack multipliers, and recovery mechanics are defined as data only; their execution is deferred to subsequent modules.

---

## 1. Purpose of Blade Definitions

`BladeDefinition` (`blade_arena/game/blade_definitions.py`) acts as the **single immutable source of truth** for blade archetypes in BLADE ARENA.

Decoupling static archetype configurations from dynamic match values ensures:
- **Zero Inconsistency:** Statistics like passive energy loss rate, attack multipliers, and recovery amounts exist in exactly one central registry rather than being scattered across resolution logic or AI modules.
- **AI Accessibility:** Search algorithms (Minimax, MCTS) and heuristic evaluators (Mamdani fuzzy inference) can query archetype multipliers and limits without instantiating full match objects.
- **State Integrity:** Definitions are frozen dataclasses and cannot be accidentally mutated during simulation branches.

---

## 2. Archetype Statistics Matrix

The four blade types derive directly from the project specification PDF:

| Blade Type | Presentation Name | Max Energy | Starting Stability | Max Stability | Passive Energy Loss / Round | Attack Power Multiplier | Guard Stability Recovery | Charge Energy Recovery |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **`BALANCED`** | Balanced | 100 | 100 | 100 | 3 | 1.00× | +5 | +20 |
| **`ATTACKER`** | Striker | 100 | 90 | 90 | 4 | 1.25× | +5 | +20 |
| **`DEFENDER`** | Bulwark | 100 | 120 | 120 | 3 | 0.85× | +10 | +20 |
| **`STAMINA`**  | Stamina | 100 | 100 | 100 | 2 | 1.00× | +5 | +25 |

### Archetype Profiles:
- **Balanced:** The versatile baseline. Moderate stability (100) and standard energy consumption (3/round).
- **Attacker (Striker):** High offensive output (1.25× attack multiplier) balanced by lower stability (90) and faster passive energy drain (4/round).
- **Defender (Bulwark):** Fortified defense with the highest stability pool (120) and enhanced guard recovery (+10 stability), trading off offensive power (0.85× multiplier).
- **Stamina:** Longevity specialist with minimal passive energy loss (2/round) and the highest charge recovery (+25 energy).

---

## 3. BladeDefinition vs. BladeState

It is vital to distinguish between static archetype definitions and dynamic combatant states:

- **`BladeDefinition` (Static):**
  - Immutable specification of archetype parameters (e.g. `attack_power_multiplier`, `passive_energy_loss`).
  - Shared across all instances of that blade type.
  - Does not change over the course of a match.
- **`BladeState` (Dynamic):**
  - Specific to one player in one match.
  - Tracks transient values: `current_energy`, `current_stability`, `position`, and `special_ready_at`.
  - Initialized using the parameters in `BladeDefinition`, but mutates immutably across rounds via `dataclasses.replace`.

---

## 4. Retrieving Blade Definitions

Retrieve definitions using `get_blade_definition()` or inspect all registered archetypes:

```python
from blade_arena.game import BladeType, get_blade_definition, get_all_blade_definitions

# Retrieve single definition
attacker_def = get_blade_definition(BladeType.ATTACKER)
print(attacker_def.name)                    # "Attacker"
print(attacker_def.attack_power_multiplier) # 1.25
print(attacker_def.max_stability)           # 90.0

# Retrieve read-only mapping of all registered definitions
all_defs = get_all_blade_definitions()
print(list(all_defs.keys()))                # [BALANCED, ATTACKER, DEFENDER, STAMINA]
```

---

## 5. Creating a BladeState

Construct a combat-ready `BladeState` from an archetype and starting coordinates:

```python
from blade_arena.game import BladeType, Position, create_blade_state

defender = create_blade_state(
    player_id="player_1",
    blade_type=BladeType.DEFENDER,
    position=Position(-2.0, 0.0),
)

print(defender.current_energy)    # 100.0 (Full energy)
print(defender.current_stability) # 120.0 (Full archetype stability)
print(defender.special_ready_at)  # 0.0 (Ready at match start)
```

---

## 6. Creating a Match with Selected Blade Types

Match factories allow callers to assign different archetypes to each player:

```python
from blade_arena.game import BladeType, create_initial_match, create_default_match

# 1. Asymmetric match (Attacker vs Defender)
match = create_initial_match(
    player_1_blade_type=BladeType.ATTACKER,
    player_2_blade_type=BladeType.DEFENDER,
)
print(match.player_1_blade.max_stability) # 90.0
print(match.player_2_blade.max_stability) # 120.0

# 2. Default match (Both players use Balanced, backward compatible)
default_match = create_default_match()
print(default_match.player_1_blade.blade_type) # BladeType.BALANCED
print(default_match.player_2_blade.blade_type) # BladeType.BALANCED
```

---

## 7. Specification Tracing: PDF vs. Assumptions

### Directly Specified in Project PDF:
- Four blade types: Balanced, Attacker, Defender, Stamina.
- Initial energy: 100 for all blades.
- Maximum stability: Balanced 100, Attacker 90, Defender 120, Stamina 100.
- Passive energy loss: Balanced 3, Attacker 4, Defender 3, Stamina 2.
- Attack multiplier: Balanced 1.00×, Attacker 1.25×, Defender 0.85×, Stamina 1.00×.
- Guard stability recovery: Balanced +5, Attacker +5, Defender +10, Stamina +5.
- Charge energy recovery: Balanced +20, Attacker +20, Defender +20, Stamina +25.

### Implementation Assumptions:
- **Maximum Energy Ceiling:** The PDF specifies starting energy of 100. Setting `max_energy = 100.0` for all archetypes is a documented implementation assumption.
- **Internal Identifiers:** The official project PDF labels the archetypes as `ATTACKER` and `DEFENDER`. Slide decks and visual presentations refer to them informally as `Striker` and `Bulwark`. To maintain code clarity, the internal enum identifiers are `BladeType.ATTACKER` and `BladeType.DEFENDER`.

---

## 8. Deliberately Deferred (Not in Module 4)

- **Combat Application:** Passive energy loss is NOT automatically deducted on instantiation.
- **Action Execution:** Charge, Guard, Dodge, and Attack multipliers are NOT calculated during match initialization.
- **Blade Selection GUI:** No graphical selection menus, dropdowns, or Pygame buttons have been created. Selection is performed programmatically via match factories.
