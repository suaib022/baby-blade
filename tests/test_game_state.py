"""Unit tests for BLADE ARENA core game state models and initial state factory."""

import dataclasses
import math
import subprocess
import sys

import pytest

from blade_arena.game.initial_state import (
    DEFAULT_PLAYER_1_ID,
    DEFAULT_PLAYER_1_POS,
    DEFAULT_PLAYER_2_ID,
    DEFAULT_PLAYER_2_POS,
    DEFAULT_STADIUM_CENTER,
    DEFAULT_STADIUM_RADIUS,
    INITIAL_ENERGY,
    INITIAL_SPECIAL_READY_AT,
    INITIAL_STABILITY,
    MAX_ENERGY,
    MAX_STABILITY,
    create_default_match,
)
from blade_arena.game.models import (
    SECONDS_PER_ROUND,
    STANDARD_MAX_ROUNDS,
    Action,
    BladeState,
    BladeType,
    FinishReason,
    MatchResult,
    MatchState,
    MatchStatus,
    Position,
    StadiumState,
    StadiumType,
)

# ==============================================================================
# A. ACTIONS
# ==============================================================================


def test_action_enum_contains_exactly_five_actions() -> None:
    """Verify exactly the five specified actions exist."""
    expected_actions = {"CHARGE", "ATTACK", "GUARD", "DODGE", "SPECIAL_SPIN"}
    action_names = {action.name for action in Action}
    assert action_names == expected_actions
    assert len(Action) == 5


def test_action_names_and_values_are_unique() -> None:
    """Verify all action names and values are distinct."""
    names = [a.name for a in Action]
    values = [a.value for a in Action]
    assert len(names) == len(set(names))
    assert len(values) == len(set(values))


# ==============================================================================
# B. POSITION
# ==============================================================================


def test_position_stores_coordinates() -> None:
    """Verify Position stores provided coordinates accurately."""
    pos = Position(3.5, -4.2)
    assert pos.x == 3.5
    assert pos.y == -4.2


def test_position_distance_from_center() -> None:
    """Verify distance_from_center computes Euclidean distance from origin (0, 0)."""
    assert Position(0.0, 0.0).distance_from_center() == 0.0
    assert math.isclose(Position(3.0, 4.0).distance_from_center(), 5.0)
    assert math.isclose(Position(-6.0, 8.0).distance_from_center(), 10.0)


def test_position_distance_to_another_position() -> None:
    """Verify distance_to computes Euclidean distance between two points."""
    p1 = Position(1.0, 2.0)
    p2 = Position(4.0, 6.0)
    assert math.isclose(p1.distance_to(p2), 5.0)
    assert math.isclose(p2.distance_to(p1), 5.0)


def test_position_rejects_non_finite_coordinates() -> None:
    """Verify NaN, Inf, and -Inf are rejected with ValueError."""
    with pytest.raises(ValueError, match="Position coordinate 'x' must be finite"):
        Position(float("nan"), 0.0)

    with pytest.raises(ValueError, match="Position coordinate 'y' must be finite"):
        Position(0.0, float("inf"))

    with pytest.raises(ValueError, match="Position coordinate 'x' must be finite"):
        Position(float("-inf"), 0.0)


def test_position_rejects_non_numeric_coordinates() -> None:
    """Verify strings, booleans, and other non-numeric types are rejected."""
    with pytest.raises(TypeError, match="must be numeric"):
        Position("1.0", 2.0)  # type: ignore

    with pytest.raises(TypeError, match="must be numeric"):
        Position(True, 2.0)  # type: ignore

    with pytest.raises(TypeError, match="Expected Position instance"):
        Position(0.0, 0.0).distance_to((1.0, 2.0))  # type: ignore


# ==============================================================================
# C. BLADE STATE
# ==============================================================================


def test_default_balanced_blade_values() -> None:
    """Verify default Balanced blade properties match specifications."""
    blade = BladeState(
        player_id="p1",
        blade_type=BladeType.BALANCED,
        current_energy=100.0,
        max_energy=100.0,
        current_stability=100.0,
        max_stability=100.0,
        position=Position(0.0, 0.0),
        special_ready_at=0.0,
    )
    assert blade.player_id == "p1"
    assert blade.blade_type == BladeType.BALANCED
    assert blade.current_energy == 100.0
    assert blade.max_energy == 100.0
    assert blade.current_stability == 100.0
    assert blade.max_stability == 100.0
    assert blade.position == Position(0.0, 0.0)
    assert blade.special_ready_at == 0.0


def test_blade_accepts_zero_energy_and_zero_stability() -> None:
    """Verify zero energy and stability are valid model values."""
    blade = BladeState(
        player_id="p1",
        blade_type=BladeType.BALANCED,
        current_energy=0.0,
        max_energy=100.0,
        current_stability=0.0,
        max_stability=100.0,
        position=Position(0.0, 0.0),
        special_ready_at=0.0,
    )
    assert blade.current_energy == 0.0
    assert blade.current_stability == 0.0


def test_blade_rejects_negative_current_energy() -> None:
    """Verify negative current energy raises ValueError."""
    with pytest.raises(ValueError, match="current_energy must be non-negative"):
        BladeState(
            player_id="p1",
            blade_type=BladeType.BALANCED,
            current_energy=-0.1,
            max_energy=100.0,
            current_stability=100.0,
            max_stability=100.0,
            position=Position(0.0, 0.0),
            special_ready_at=0.0,
        )


def test_blade_rejects_negative_current_stability() -> None:
    """Verify negative current stability raises ValueError."""
    with pytest.raises(ValueError, match="current_stability must be non-negative"):
        BladeState(
            player_id="p1",
            blade_type=BladeType.BALANCED,
            current_energy=100.0,
            max_energy=100.0,
            current_stability=-1.0,
            max_stability=100.0,
            position=Position(0.0, 0.0),
            special_ready_at=0.0,
        )


def test_blade_rejects_current_values_exceeding_maximum() -> None:
    """Verify current values greater than their maximum are rejected."""
    with pytest.raises(ValueError, match="current_energy .* cannot exceed max_energy"):
        BladeState(
            player_id="p1",
            blade_type=BladeType.BALANCED,
            current_energy=101.0,
            max_energy=100.0,
            current_stability=100.0,
            max_stability=100.0,
            position=Position(0.0, 0.0),
            special_ready_at=0.0,
        )

    with pytest.raises(ValueError, match="current_stability .* cannot exceed max_stability"):
        BladeState(
            player_id="p1",
            blade_type=BladeType.BALANCED,
            current_energy=100.0,
            max_energy=100.0,
            current_stability=105.0,
            max_stability=100.0,
            position=Position(0.0, 0.0),
            special_ready_at=0.0,
        )


def test_blade_rejects_non_positive_maximum_values() -> None:
    """Verify maximum energy and stability must be strictly positive."""
    with pytest.raises(ValueError, match="max_energy must be strictly positive"):
        BladeState(
            player_id="p1",
            blade_type=BladeType.BALANCED,
            current_energy=0.0,
            max_energy=0.0,
            current_stability=100.0,
            max_stability=100.0,
            position=Position(0.0, 0.0),
            special_ready_at=0.0,
        )

    with pytest.raises(ValueError, match="max_stability must be strictly positive"):
        BladeState(
            player_id="p1",
            blade_type=BladeType.BALANCED,
            current_energy=10.0,
            max_energy=100.0,
            current_stability=0.0,
            max_stability=-5.0,
            position=Position(0.0, 0.0),
            special_ready_at=0.0,
        )


def test_blade_rejects_invalid_special_ready_times() -> None:
    """Verify special_ready_at must be finite and non-negative."""
    with pytest.raises(ValueError, match="special_ready_at must be non-negative"):
        BladeState(
            player_id="p1",
            blade_type=BladeType.BALANCED,
            current_energy=100.0,
            max_energy=100.0,
            current_stability=100.0,
            max_stability=100.0,
            position=Position(0.0, 0.0),
            special_ready_at=-0.5,
        )

    with pytest.raises(ValueError, match="special_ready_at must be a finite number"):
        BladeState(
            player_id="p1",
            blade_type=BladeType.BALANCED,
            current_energy=100.0,
            max_energy=100.0,
            current_stability=100.0,
            max_stability=100.0,
            position=Position(0.0, 0.0),
            special_ready_at=float("nan"),
        )


def test_blade_rejects_invalid_player_id_and_types() -> None:
    """Verify empty player_id, wrong blade_type, and wrong position types are rejected."""
    with pytest.raises(ValueError, match="player_id must be a non-empty string"):
        BladeState(
            player_id="   ",
            blade_type=BladeType.BALANCED,
            current_energy=100.0,
            max_energy=100.0,
            current_stability=100.0,
            max_stability=100.0,
            position=Position(0.0, 0.0),
            special_ready_at=0.0,
        )

    with pytest.raises(TypeError, match="blade_type must be a BladeType enum"):
        BladeState(
            player_id="p1",
            blade_type="BALANCED",  # type: ignore
            current_energy=100.0,
            max_energy=100.0,
            current_stability=100.0,
            max_stability=100.0,
            position=Position(0.0, 0.0),
            special_ready_at=0.0,
        )

    with pytest.raises(TypeError, match="position must be a Position instance"):
        BladeState(
            player_id="p1",
            blade_type=BladeType.BALANCED,
            current_energy=100.0,
            max_energy=100.0,
            current_stability=100.0,
            max_stability=100.0,
            position=(0.0, 0.0),  # type: ignore
            special_ready_at=0.0,
        )


# ==============================================================================
# D. STADIUM STATE
# ==============================================================================


def test_default_stadium_state_values() -> None:
    """Verify default StadiumState fields."""
    stadium = StadiumState(
        stadium_type=StadiumType.CLASSIC_DISH,
        center=Position(0.0, 0.0),
        radius=10.0,
    )
    assert stadium.stadium_type == StadiumType.CLASSIC_DISH
    assert stadium.center == Position(0.0, 0.0)
    assert stadium.radius == 10.0


def test_stadium_rejects_non_positive_and_non_finite_radii() -> None:
    """Verify zero, negative, NaN, and infinite radii are rejected."""
    with pytest.raises(ValueError, match="radius must be finite and positive"):
        StadiumState(
            stadium_type=StadiumType.CLASSIC_DISH,
            center=Position(0.0, 0.0),
            radius=0.0,
        )

    with pytest.raises(ValueError, match="radius must be finite and positive"):
        StadiumState(
            stadium_type=StadiumType.CLASSIC_DISH,
            center=Position(0.0, 0.0),
            radius=-10.0,
        )

    with pytest.raises(ValueError, match="radius must be finite and positive"):
        StadiumState(
            stadium_type=StadiumType.CLASSIC_DISH,
            center=Position(0.0, 0.0),
            radius=float("nan"),
        )

    with pytest.raises(ValueError, match="radius must be finite and positive"):
        StadiumState(
            stadium_type=StadiumType.CLASSIC_DISH,
            center=Position(0.0, 0.0),
            radius=float("inf"),
        )


def test_stadium_rejects_invalid_types() -> None:
    """Verify stadium rejects invalid types for radius, center, and type."""
    with pytest.raises(TypeError, match="radius must be numeric"):
        StadiumState(
            stadium_type=StadiumType.CLASSIC_DISH,
            center=Position(0.0, 0.0),
            radius="10.0",  # type: ignore
        )

    with pytest.raises(TypeError, match="stadium_type must be StadiumType"):
        StadiumState(
            stadium_type="CLASSIC_DISH",  # type: ignore
            center=Position(0.0, 0.0),
            radius=10.0,
        )

    with pytest.raises(TypeError, match="center must be Position"):
        StadiumState(
            stadium_type=StadiumType.CLASSIC_DISH,
            center=(0.0, 0.0),  # type: ignore
            radius=10.0,
        )


# ==============================================================================
# E. MATCH STATE
# ==============================================================================


def test_default_match_properties() -> None:
    """Verify default initial match created by the factory."""
    match = create_default_match()

    # Identifiers
    assert match.player_1_blade.player_id == DEFAULT_PLAYER_1_ID
    assert match.player_2_blade.player_id == DEFAULT_PLAYER_2_ID
    assert match.player_1_blade.player_id != match.player_2_blade.player_id

    # Blade properties
    for blade in (match.player_1_blade, match.player_2_blade):
        assert blade.blade_type == BladeType.BALANCED
        assert blade.current_energy == INITIAL_ENERGY
        assert blade.max_energy == MAX_ENERGY
        assert blade.current_stability == INITIAL_STABILITY
        assert blade.max_stability == MAX_STABILITY
        assert blade.special_ready_at == INITIAL_SPECIAL_READY_AT

    # Default positions
    assert match.player_1_blade.position == DEFAULT_PLAYER_1_POS
    assert match.player_2_blade.position == DEFAULT_PLAYER_2_POS

    # Stadium properties
    assert match.stadium.stadium_type == StadiumType.CLASSIC_DISH
    assert match.stadium.center == DEFAULT_STADIUM_CENTER
    assert match.stadium.radius == DEFAULT_STADIUM_RADIUS

    # Rounds, timing, and status
    assert match.completed_rounds == 0
    assert match.elapsed_game_time == 0.0
    assert match.status == MatchStatus.IN_PROGRESS
    assert match.result is None


def test_elapsed_game_time_derivation() -> None:
    """Verify elapsed game time is derived as completed_rounds * 3.0 seconds."""
    match = create_default_match()
    assert match.elapsed_game_time == 0.0

    match_10 = dataclasses.replace(match, completed_rounds=10)
    assert match_10.elapsed_game_time == 30.0

    match_40 = dataclasses.replace(match, completed_rounds=STANDARD_MAX_ROUNDS)
    assert match_40.elapsed_game_time == 120.0


def test_match_state_rejects_duplicate_player_ids() -> None:
    """Verify player 1 and player 2 must have distinct identifiers."""
    default = create_default_match()
    duplicate_blade = dataclasses.replace(default.player_2_blade, player_id=default.player_1_blade.player_id)
    with pytest.raises(ValueError, match="must have distinct IDs"):
        dataclasses.replace(default, player_2_blade=duplicate_blade)


def test_match_state_rejects_invalid_completed_rounds() -> None:
    """Verify completed_rounds must be a non-negative integer."""
    default = create_default_match()

    with pytest.raises(ValueError, match="completed_rounds must be non-negative"):
        dataclasses.replace(default, completed_rounds=-1)

    with pytest.raises(TypeError, match="completed_rounds must be an integer"):
        dataclasses.replace(default, completed_rounds=5.5)  # type: ignore

    with pytest.raises(TypeError, match="completed_rounds must be an integer"):
        dataclasses.replace(default, completed_rounds=True)  # type: ignore


def test_match_state_in_progress_consistency() -> None:
    """Verify an in-progress match cannot hold a MatchResult."""
    default = create_default_match()
    result = MatchResult(winner="player_1", reason=FinishReason.BURST)

    with pytest.raises(ValueError, match="in-progress match must not have a result"):
        dataclasses.replace(default, status=MatchStatus.IN_PROGRESS, result=result)


def test_match_state_finished_consistency() -> None:
    """Verify a finished match must hold a valid MatchResult."""
    default = create_default_match()

    with pytest.raises(ValueError, match="finished match must have a result"):
        dataclasses.replace(default, status=MatchStatus.FINISHED, result=None)

    # Valid finished match
    result = MatchResult(winner="player_1", reason=FinishReason.RING_OUT)
    finished_match = dataclasses.replace(default, status=MatchStatus.FINISHED, result=result)
    assert finished_match.status == MatchStatus.FINISHED
    assert finished_match.result == result


def test_match_result_validation() -> None:
    """Verify MatchResult validates winner and reason."""
    # Valid results
    win_result = MatchResult(winner="player_1", reason=FinishReason.SPIN_OUT)
    assert win_result.winner == "player_1"
    assert win_result.reason == FinishReason.SPIN_OUT

    draw_result = MatchResult(winner=None, reason=FinishReason.SIMULTANEOUS_ELIMINATION)
    assert draw_result.winner is None

    # Invalid cases
    with pytest.raises(ValueError, match="winner must be None .* or a non-empty player ID"):
        MatchResult(winner="   ", reason=FinishReason.POINTS_DECISION)

    with pytest.raises(TypeError, match="reason must be a FinishReason enum"):
        MatchResult(winner="player_1", reason="SPIN_OUT")  # type: ignore


# ==============================================================================
# F. INDEPENDENCE AND IMMUTABILITY
# ==============================================================================


def test_derived_blade_does_not_alter_original_blade() -> None:
    """Verify deriving a modified blade leaves the original state unchanged."""
    original_blade = create_default_match().player_1_blade
    derived_blade = dataclasses.replace(original_blade, current_energy=45.0)

    assert derived_blade.current_energy == 45.0
    assert original_blade.current_energy == 100.0
    assert original_blade is not derived_blade


def test_derived_match_does_not_alter_original_match() -> None:
    """Verify deriving a modified match leaves the original match intact."""
    original_match = create_default_match()
    new_blade = dataclasses.replace(original_match.player_1_blade, current_stability=70.0)
    derived_match = dataclasses.replace(original_match, player_1_blade=new_blade, completed_rounds=1)

    assert derived_match.player_1_blade.current_stability == 70.0
    assert derived_match.completed_rounds == 1
    assert derived_match.elapsed_game_time == 3.0

    assert original_match.player_1_blade.current_stability == 100.0
    assert original_match.completed_rounds == 0
    assert original_match.elapsed_game_time == 0.0


def test_models_are_frozen_against_direct_mutation() -> None:
    """Verify direct field assignment raises FrozenInstanceError."""
    match = create_default_match()

    with pytest.raises(dataclasses.FrozenInstanceError):
        match.completed_rounds = 5  # type: ignore

    with pytest.raises(dataclasses.FrozenInstanceError):
        match.player_1_blade.current_energy = 50.0  # type: ignore

    with pytest.raises(dataclasses.FrozenInstanceError):
        match.stadium.radius = 8.0  # type: ignore

    with pytest.raises(dataclasses.FrozenInstanceError):
        match.player_1_blade.position.x = 1.0  # type: ignore


def test_two_initial_matches_are_independent() -> None:
    """Verify independent factory calls produce independent values."""
    m1 = create_default_match()
    m2 = create_default_match()

    assert m1 == m2
    assert m1 is not m2
    assert m1.player_1_blade is not m2.player_1_blade
    assert m1.stadium is not m2.stadium


# ==============================================================================
# G. INTEGRATION AND REGRESSION
# ==============================================================================


def test_import_game_models_does_not_initialize_pygame() -> None:
    """Verify importing blade_arena.game does not initialize Pygame or open a window."""
    code = (
        "import blade_arena.game\n"
        "import pygame\n"
        "assert not pygame.get_init(), 'Pygame was initialized on importing game models'\n"
        "assert not pygame.display.get_init(), 'Pygame display was initialized'\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        timeout=5,
    )
    assert result.returncode == 0, f"Import side-effect detected: {result.stderr}"


def test_create_match_does_not_initialize_pygame() -> None:
    """Verify executing the match factory does not initialize Pygame or open a window."""
    code = (
        "from blade_arena.game import create_default_match\n"
        "import pygame\n"
        "m = create_default_match()\n"
        "assert m.completed_rounds == 0\n"
        "assert not pygame.get_init(), 'Pygame was initialized by match factory'\n"
        "assert not pygame.display.get_init(), 'Pygame display was initialized by match factory'\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        timeout=5,
    )
    assert result.returncode == 0, f"Match creation side-effect detected: {result.stderr}"
