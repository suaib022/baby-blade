# BLADE ARENA — Match Flow and Turn Coordination

> **Status Notice:** This document specifies **Module 3: Turn and Match Flow**. It covers simultaneous action coordination, round resolution orchestration, match lifecycle states (pause, resume, restart), and error handling. Actual combat physics, action costs, legality rules, and AI agents remain deliberately unbuilt until future modules.

---

## 1. Controller Responsibilities

The `MatchController` (`blade_arena/game/match_controller.py`) is the central coordinator for match execution. It enforces the rules of engagement across rounds while remaining decoupled from rendering, physical devices, and domain combat logic:

1. **State Custody:** Holds the current immutable `MatchState` snapshot.
2. **Action Collection:** Collects exactly one `Action` per player per round.
3. **Simultaneous Secrecy:** Keeps submitted actions private until both combatants have committed.
4. **Resolution Orchestration:** Supplies the pre-round state and both actions to an injected `RoundResolver`.
5. **State Advancement Validation:** Verifies that the resolver advanced the match by exactly one round before committing the new state.
6. **Lifecycle Controls:** Supports pausing, resuming, and restarting.
7. **Terminal State Protection:** Rejects submissions and resolutions once a match is finished.

---

## 2. Simultaneous Action Model

BLADE ARENA combats feature **simultaneous action selection**. Although player inputs are gathered sequentially in code, they represent simultaneous tactical decisions made during the same round window:

```
[Round N Begins]
       │
       ├─► Player 1 observes State N  ──► commits Action P1
       │                                     │ (hidden)
       ├─► Player 2 observes State N  ──► commits Action P2
       │                                     │
       ▼                                     ▼
Both Committed? ───────── YES ────────► Pass (State N, P1, P2) to Resolver
                                             │
                                             ▼
                                      Return State N+1
                                             │
                                             ▼
                                    [Round N+1 Begins]
```

### Key Guarantees:
- **No Order Advantage:** Neither player's submission takes effect immediately. The order of submission (whether Player 1 commits first or Player 2 commits first) has no bearing on round resolution.
- **Symmetric Information:** Both players observe the exact same pre-round state.
- **Stable Dispatch:** Actions are always supplied to the resolver in stable player order: `(state, player_1_action, player_2_action)`.

---

## 3. Public Controller API

```python
class MatchController:
    def __init__(self, initial_state: MatchState, resolver: RoundResolver) -> None: ...

    # Inspection
    @property
    def state(self) -> MatchState: ...
    @property
    def is_paused(self) -> bool: ...
    @property
    def is_finished(self) -> bool: ...
    @property
    def round_history(self) -> Tuple[RoundRecord, ...]: ...

    # Player & Submission Status
    def get_valid_player_ids(self) -> Set[str]: ...
    def get_pending_players(self) -> Set[str]: ...
    def has_player_submitted(self, player_id: str) -> bool: ...
    def can_resolve(self) -> bool: ...

    # Actions & Resolution
    def submit_action(self, player_id: str, action: Action) -> None: ...
    def resolve_round(self) -> RoundRecord: ...

    # Lifecycle
    def pause(self) -> None: ...
    def resume(self) -> None: ...
    def restart(self, initial_state: Optional[MatchState] = None) -> None: ...
```

---

## 4. Keeping Actions Private Before Resolution

To prevent AI search agents or local players from snooping on opponent commitments:
- **No Actions in `MatchState`:** The `MatchState` object does not contain action fields.
- **Private Pending Buffer:** Submitted actions are held internally within `self._pending_actions` and are never exposed via properties or public methods prior to resolution.
- **Non-Leaking Inspection:** Methods like `has_player_submitted(player_id)` and `get_pending_players()` confirm *whether* a player has committed, but never *what* action was submitted.
- **Post-Resolution Auditing:** Only after successful resolution does `resolve_round()` return an immutable `RoundRecord` documenting both committed actions.

---

## 5. Round Resolver Interface and Round Ownership

The resolver interface is defined as a Python Protocol (`blade_arena/game/resolver.py`):

```python
class RoundResolver(Protocol):
    def resolve_round(
        self,
        state: MatchState,
        player_1_action: Action,
        player_2_action: Action,
    ) -> MatchState:
        ...
```

### Ownership of Round Advancement:
- **The Resolver Owns Advancement:** The resolver is explicitly responsible for computing the subsequent `MatchState` with `completed_rounds == state.completed_rounds + 1`.
- **The Controller Validates Advancement:** The controller verifies that `next_state.completed_rounds == pre_state.completed_rounds + 1`. If the resolver fails to advance or advances by more than one round, the controller rejects the result and raises `RoundResolutionError`.
- **No Double Increments:** The controller never modifies or increments the round count itself.

---

## 6. Pause, Resume, and Restart Behavior

### Pause (`pause()`)
- Sets `is_paused = True`.
- Idempotent: repeated calls have no negative effect.
- Disallows new action submissions (`MatchPausedError`) and round resolutions (`MatchPausedError`).
- Leaves game state and any already-submitted actions intact.

### Resume (`resume()`)
- Sets `is_paused = False`.
- Idempotent.
- Re-enables submission and resolution.
- Does not alter game state, advance rounds, or discard pending submissions.

### Restart (`restart()`)
- Restores the match to its original `initial_state` snapshot (or a newly provided `initial_state`).
- Clears all pending actions.
- Clears the paused flag (`is_paused = False`).
- Clears the `round_history` audit log.
- Operates cleanly at any time, including after the match is `FINISHED`.

---

## 7. Resolver Failure and Error Handling

If a resolver raises an exception or returns an invalid state (non-`MatchState` or incorrect round increment):
1. **State Preservation:** The controller retains its original pre-round `state`.
2. **Pending Actions Preserved:** Neither player's committed action is discarded.
3. **Audit History Intact:** No corrupted record is logged.
4. **Exception Raised:** A descriptive `RoundResolutionError` is raised.
5. **Retry / Recovery:** Because pending actions are preserved, calling code can address transient conditions and retry `resolve_round()`, or invoke `restart()`.

---

## 8. Test-Only Resolvers

Because combat and movement rules belong to future modules, the test suite (`tests/test_match_controller.py`) utilizes test fixtures to exercise coordination mechanics:

- **`RecordingResolver`:** Records all arguments passed to it and returns a derived state with `completed_rounds = state.completed_rounds + 1`.
- **`FinishingResolver`:** Simulates a knockout/burst ending by returning `status = MatchStatus.FINISHED` and a valid `MatchResult`.
- **`FailingResolver`:** Deliberately raises an unhandled exception to test rollback and action preservation.
- **`InvalidTypeResolver`:** Deliberately returns a non-`MatchState` value to verify output type validation.
- **`NoAdvanceResolver` & `DoubleAdvanceResolver`:** Deliberately return states with invalid round increments (0 and 2) to test round-advancement enforcement.

> *Note: These fixtures are strictly test scaffolding. They do not implement real gameplay or physics.*

---

## 9. Deliberately Deferred (Not in Module 3)

The following capabilities are out of scope for Module 3:
- Action energy costs and stability adjustments.
- Action recovery and cooldown countdowns.
- Collision detection, spatial kinematics, and ring-out boundary checks.
- Turn selection UI (menus, HUD prompts, keybindings).
- Autonomous AI decision engines (Minimax, MCTS, Mamdani fuzzy logic).
- Tournament management or round-robin scoring.

---

## 10. Future Mode Integration

Future game modes will wrap the `MatchController` cleanly:
- **Human vs. AI:** A human input handler collects the player's action from GUI/keyboard events and calls `submit_action()`, while an AI worker calls `submit_action()` for the opponent. Once `can_resolve()` is True, the game shell triggers `resolve_round()`.
- **AI vs. AI:** Two autonomous agents query `controller.state`, independently formulate actions, and submit them without access to each other's choice.
- **Tournament Mode:** A headless loop iterates over `submit_action()` and `resolve_round()` across hundreds of matches without any graphical display overhead.
