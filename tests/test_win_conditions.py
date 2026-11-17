"""Unit and integration tests for BLADE ARENA win conditions, elimination, and match results."""

import dataclasses
import pytest

from blade_arena.game.blade_definitions import create_blade_state
from blade_arena.game.combat import ClassicDishRoundResolver
from blade_arena.game.initial_state import create_default_match, create_initial_match
from blade_arena.game.match_controller import MatchController, MatchFinishedError
from blade_arena.game.models import (
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
from blade_arena.game.win_conditions import (
    DEFAULT_POINTS_WEIGHT_ENERGY,
    DEFAULT_POINTS_WEIGHT_POSITION,
    DEFAULT_POINTS_WEIGHT_STABILITY,
    ELIMINATION_CAUSE_PRIORITY,
    POINTS_DECISION_TOLERANCE,
    calculate_blade_points,
    evaluate_match_termination,
    get_blade_elimination_causes,
    is_match_terminal,
)


def test_points_weights_and_tolerances() -> None:
    """Verify points weights sum to 1.0 and tolerance matches specification."""
    total_weight = (
        DEFAULT_POINTS_WEIGHT_ENERGY
        + DEFAULT_POINTS_WEIGHT_STABILITY
        + DEFAULT_POINTS_WEIGHT_POSITION
    )
    assert total_weight == pytest.approx(1.00)
    assert POINTS_DECISION_TOLERANCE == 1e-6
    assert ELIMINATION_CAUSE_PRIORITY == (
        FinishReason.RING_OUT,
        FinishReason.BURST,
        FinishReason.SPIN_OUT,
    )


def test_calculate_blade_points_values() -> None:
    """Verify points formula: 0.4*(E/Emax) + 0.4*(S/Smax) + 0.2*max(0, 1 - dist/r)."""
    # Full resources at arena center (dist = 0)
    b_center = create_blade_state("p1", BladeType.BALANCED, position=Position(0.0, 0.0))
    score_full = calculate_blade_points(b_center, stadium_radius=10.0)
    # 0.40(1) + 0.40(1) + 0.20(1 - 0) = 1.00
    assert score_full == pytest.approx(1.00)

    # Half resources at midpoint (dist = 5.0 in r=10.0 arena)
    b_half = BladeState(
        player_id="p1",
        blade_type=BladeType.BALANCED,
        current_energy=50.0,
        max_energy=100.0,
        current_stability=50.0,
        max_stability=100.0,
        position=Position(5.0, 0.0),
        special_ready_at=0.0,
    )
    score_half = calculate_blade_points(b_half, stadium_radius=10.0)
    # 0.40(0.5) + 0.40(0.5) + 0.20(1 - 0.5) = 0.20 + 0.20 + 0.10 = 0.50
    assert score_half == pytest.approx(0.50)

    # Outside arena (dist = 12.0 in r=10.0 arena) -> position score clamped at 0.0
    b_outside = BladeState(
        player_id="p1",
        blade_type=BladeType.BALANCED,
        current_energy=100.0,
        max_energy=100.0,
        current_stability=100.0,
        max_stability=100.0,
        position=Position(12.0, 0.0),
        special_ready_at=0.0,
    )
    score_outside = calculate_blade_points(b_outside, stadium_radius=10.0)
    # 0.40(1) + 0.40(1) + 0.20(0) = 0.80
    assert score_outside == pytest.approx(0.80)


def test_individual_elimination_causes() -> None:
    """Verify detection of individual elimination causes."""
    radius = 10.0

    # Healthy blade inside arena -> no causes
    b_healthy = create_blade_state("p1", BladeType.BALANCED, position=Position(2.0, 0.0))
    assert get_blade_elimination_causes(b_healthy, radius) == ()

    # Ring-out alone
    b_ringout = create_blade_state("p1", BladeType.BALANCED, position=Position(10.5, 0.0))
    assert get_blade_elimination_causes(b_ringout, radius) == (FinishReason.RING_OUT,)

    # Burst alone (stability <= 0)
    b_burst = BladeState(
        player_id="p1",
        blade_type=BladeType.BALANCED,
        current_energy=100.0,
        max_energy=100.0,
        current_stability=0.0,
        max_stability=100.0,
        position=Position(2.0, 0.0),
        special_ready_at=0.0,
    )
    assert get_blade_elimination_causes(b_burst, radius) == (FinishReason.BURST,)

    # Spin-out alone (energy <= 0)
    b_spinout = BladeState(
        player_id="p1",
        blade_type=BladeType.BALANCED,
        current_energy=0.0,
        max_energy=100.0,
        current_stability=100.0,
        max_stability=100.0,
        position=Position(2.0, 0.0),
        special_ready_at=0.0,
    )
    assert get_blade_elimination_causes(b_spinout, radius) == (FinishReason.SPIN_OUT,)


def test_multiple_elimination_causes_priority() -> None:
    """Verify priority ordering: RING_OUT > BURST > SPIN_OUT when a blade triggers multiple."""
    radius = 10.0

    # Blade with all 3 causes: outside arena, 0 stability, 0 energy
    b_all = BladeState(
        player_id="p1",
        blade_type=BladeType.BALANCED,
        current_energy=0.0,
        max_energy=100.0,
        current_stability=0.0,
        max_stability=100.0,
        position=Position(11.0, 0.0),
        special_ready_at=0.0,
    )
    causes_all = get_blade_elimination_causes(b_all, radius)
    assert causes_all == (
        FinishReason.RING_OUT,
        FinishReason.BURST,
        FinishReason.SPIN_OUT,
    )
    # Highest priority is Ring-out
    assert causes_all[0] == FinishReason.RING_OUT

    # Blade with 2 causes: burst and spinout (inside arena)
    b_two = BladeState(
        player_id="p1",
        blade_type=BladeType.BALANCED,
        current_energy=0.0,
        max_energy=100.0,
        current_stability=0.0,
        max_stability=100.0,
        position=Position(2.0, 0.0),
        special_ready_at=0.0,
    )
    causes_two = get_blade_elimination_causes(b_two, radius)
    assert causes_two == (FinishReason.BURST, FinishReason.SPIN_OUT)
    # Highest priority is Burst
    assert causes_two[0] == FinishReason.BURST


def test_single_elimination_winner_and_reason() -> None:
    """Verify when only one player is eliminated, the other wins with the correct primary cause."""
    default = create_default_match()

    # Case A: Player 1 Ring-out -> Player 2 wins by RING_OUT
    p1_ringout = dataclasses.replace(default.player_1_blade, position=Position(10.5, 0.0))
    state_a = dataclasses.replace(default, player_1_blade=p1_ringout)
    res_a = evaluate_match_termination(state_a)
    assert res_a is not None
    assert res_a.winner == "player_2"
    assert res_a.reason == FinishReason.RING_OUT
    assert res_a.player_1_causes == (FinishReason.RING_OUT,)
    assert res_a.player_2_causes == ()

    # Case B: Player 2 Burst -> Player 1 wins by BURST
    p2_burst = dataclasses.replace(default.player_2_blade, current_stability=0.0)
    state_b = dataclasses.replace(default, player_2_blade=p2_burst)
    res_b = evaluate_match_termination(state_b)
    assert res_b is not None
    assert res_b.winner == "player_1"
    assert res_b.reason == FinishReason.BURST
    assert res_b.player_1_causes == ()
    assert res_b.player_2_causes == (FinishReason.BURST,)

    # Case C: Player 2 Spin-out -> Player 1 wins by SPIN_OUT
    p2_spinout = dataclasses.replace(default.player_2_blade, current_energy=0.0)
    state_c = dataclasses.replace(default, player_2_blade=p2_spinout)
    res_c = evaluate_match_termination(state_c)
    assert res_c is not None
    assert res_c.winner == "player_1"
    assert res_c.reason == FinishReason.SPIN_OUT


def test_simultaneous_elimination_produces_draw() -> None:
    """Verify when both blades are eliminated in the same round, a Draw is returned."""
    default = create_default_match()

    # P1 bursts, P2 spins out in the same round
    p1_burst = dataclasses.replace(default.player_1_blade, current_stability=0.0)
    p2_spinout = dataclasses.replace(default.player_2_blade, current_energy=0.0)
    state = dataclasses.replace(default, player_1_blade=p1_burst, player_2_blade=p2_spinout)

    result = evaluate_match_termination(state)
    assert result is not None
    assert result.winner is None
    assert result.reason == FinishReason.SIMULTANEOUS_ELIMINATION
    assert result.player_1_causes == (FinishReason.BURST,)
    assert result.player_2_causes == (FinishReason.SPIN_OUT,)


def test_shrink_caused_ring_out() -> None:
    """Verify that arena shrinking can cause a ring-out for a blade outside the new radius."""
    # Place Player 1 at distance 9.4 from center (inside radius 10.0, but outside shrunk radius 9.0)
    # Round 5: P1 at (9.4, 0.0), P2 at (0.0, 0.0). Both Guard (stay in place).
    # Round 6 completes -> stadium shrinks to 9.0!
    # P1 is at 9.4 > 9.0 -> Ring-out!
    b1 = create_blade_state("player_1", BladeType.BALANCED, position=Position(9.4, 0.0))
    b2 = create_blade_state("player_2", BladeType.BALANCED, position=Position(0.0, 0.0))
    match_r5 = MatchState(
        player_1_blade=b1,
        player_2_blade=b2,
        stadium=StadiumState(StadiumType.CLASSIC_DISH, Position(0.0, 0.0), 10.0),
        completed_rounds=5,
        status=MatchStatus.IN_PROGRESS,
    )

    resolver = ClassicDishRoundResolver()
    next_state = resolver.resolve_round(match_r5, Action.GUARD, Action.GUARD)

    assert next_state.completed_rounds == 6
    assert next_state.stadium.radius == pytest.approx(9.0)
    # Match is now FINISHED due to shrink-induced ring-out!
    assert next_state.status == MatchStatus.FINISHED
    assert next_state.result is not None
    assert next_state.result.winner == "player_2"
    assert next_state.result.reason == FinishReason.RING_OUT


def test_exact_zero_resources_and_boundary_edge() -> None:
    """Verify exact numerical boundaries for elimination conditions."""
    radius = 10.0

    # Exactly 0.0 stability is burst
    b_exact_burst = BladeState(
        player_id="p1",
        blade_type=BladeType.BALANCED,
        current_energy=50.0,
        max_energy=100.0,
        current_stability=0.0,
        max_stability=100.0,
        position=Position(0.0, 0.0),
        special_ready_at=0.0,
    )
    assert FinishReason.BURST in get_blade_elimination_causes(b_exact_burst, radius)

    # Barely positive stability is NOT burst
    b_alive = dataclasses.replace(b_exact_burst, current_stability=0.0001)
    assert FinishReason.BURST not in get_blade_elimination_causes(b_alive, radius)

    # Exactly on boundary is inside (NOT ring-out)
    b_on_edge = create_blade_state("p1", BladeType.BALANCED, position=Position(10.0, 0.0))
    assert FinishReason.RING_OUT not in get_blade_elimination_causes(b_on_edge, radius)

    # Within tolerance is inside (NOT ring-out)
    b_near_edge = create_blade_state("p1", BladeType.BALANCED, position=Position(10.0 + 1e-10, 0.0))
    assert FinishReason.RING_OUT not in get_blade_elimination_causes(b_near_edge, radius)

    # Beyond tolerance is ring-out
    b_out = create_blade_state("p1", BladeType.BALANCED, position=Position(10.001, 0.0))
    assert FinishReason.RING_OUT in get_blade_elimination_causes(b_out, radius)


def test_round_40_points_decision_winner() -> None:
    """Verify round 40 points decision awards victory to the blade with higher points."""
    # Create match at completed_rounds = 40 with neither eliminated
    # P1 has higher energy (80 vs 50) and higher stability (90 vs 60)
    b1 = BladeState(
        player_id="player_1",
        blade_type=BladeType.BALANCED,
        current_energy=80.0,
        max_energy=100.0,
        current_stability=90.0,
        max_stability=100.0,
        position=Position(1.0, 0.0),
        special_ready_at=0.0,
    )
    b2 = BladeState(
        player_id="player_2",
        blade_type=BladeType.BALANCED,
        current_energy=50.0,
        max_energy=100.0,
        current_stability=60.0,
        max_stability=100.0,
        position=Position(3.0, 0.0),
        special_ready_at=0.0,
    )
    state = MatchState(
        player_1_blade=b1,
        player_2_blade=b2,
        stadium=StadiumState(StadiumType.CLASSIC_DISH, Position(0.0, 0.0), 6.0),
        completed_rounds=40,
        status=MatchStatus.IN_PROGRESS,
    )

    result = evaluate_match_termination(state)
    assert result is not None
    assert result.winner == "player_1"
    assert result.reason == FinishReason.POINTS_DECISION
    assert result.scores is not None
    assert result.scores[0] > result.scores[1]


def test_round_40_points_decision_draw_and_near_ties() -> None:
    """Verify round 40 produces a draw when score difference <= 1e-6."""
    # Symmetrically identical blades at equal distance from center
    b1 = create_blade_state("player_1", BladeType.BALANCED, position=Position(-2.0, 0.0))
    b2 = create_blade_state("player_2", BladeType.BALANCED, position=Position(2.0, 0.0))
    state = MatchState(
        player_1_blade=b1,
        player_2_blade=b2,
        stadium=StadiumState(StadiumType.CLASSIC_DISH, Position(0.0, 0.0), 6.0),
        completed_rounds=40,
        status=MatchStatus.IN_PROGRESS,
    )

    result = evaluate_match_termination(state)
    assert result is not None
    assert result.winner is None
    assert result.reason == FinishReason.POINTS_DECISION
    assert result.scores is not None
    assert abs(result.scores[0] - result.scores[1]) <= 1e-6


def test_round_40_elimination_takes_priority_over_points() -> None:
    """Verify that an elimination occurring in round 40 takes precedence over a points decision."""
    # At round 40, Player 1 has 0 stability (BURST)
    b1_burst = BladeState(
        player_id="player_1",
        blade_type=BladeType.BALANCED,
        current_energy=80.0,
        max_energy=100.0,
        current_stability=0.0,  # Burst!
        max_stability=100.0,
        position=Position(0.0, 0.0),
        special_ready_at=0.0,
    )
    b2_healthy = create_blade_state("player_2", BladeType.BALANCED, position=Position(2.0, 0.0))
    state = MatchState(
        player_1_blade=b1_burst,
        player_2_blade=b2_healthy,
        stadium=StadiumState(StadiumType.CLASSIC_DISH, Position(0.0, 0.0), 6.0),
        completed_rounds=40,
        status=MatchStatus.IN_PROGRESS,
    )

    result = evaluate_match_termination(state)
    assert result is not None
    # Must be BURST knockout, NOT POINTS_DECISION
    assert result.winner == "player_2"
    assert result.reason == FinishReason.BURST


def test_no_premature_finish_at_round_39() -> None:
    """Verify that round 39 does not prematurely conclude if neither blade is eliminated."""
    b1 = create_blade_state("player_1", BladeType.BALANCED, position=Position(-2.0, 0.0))
    b2 = create_blade_state("player_2", BladeType.BALANCED, position=Position(2.0, 0.0))
    state_r39 = MatchState(
        player_1_blade=b1,
        player_2_blade=b2,
        stadium=StadiumState(StadiumType.CLASSIC_DISH, Position(0.0, 0.0), 6.0),
        completed_rounds=39,
        status=MatchStatus.IN_PROGRESS,
    )

    result = evaluate_match_termination(state_r39)
    assert result is None
    assert is_match_terminal(state_r39) is False


def test_no_41st_round_allowed() -> None:
    """Verify controller strictly rejects submissions and resolutions on a finished match."""
    match = create_default_match()
    resolver = ClassicDishRoundResolver()
    controller = MatchController(match, resolver)

    # Force match to finished status
    finished_state = dataclasses.replace(
        match,
        completed_rounds=40,
        status=MatchStatus.FINISHED,
        result=MatchResult(winner="player_1", reason=FinishReason.POINTS_DECISION),
    )
    controller._state = finished_state

    assert controller.is_finished is True
    with pytest.raises(MatchFinishedError, match="match is already finished"):
        controller.submit_action("player_1", Action.CHARGE)

    with pytest.raises(MatchFinishedError, match="match is already finished"):
        controller.resolve_round()


def test_complete_headless_scripted_match() -> None:
    """Run an entire match from round 0 to finish headlessly and verify terminal state."""
    match = create_default_match()
    resolver = ClassicDishRoundResolver()
    controller = MatchController(match, resolver)

    # Run consecutive Attack rounds until combat concludes
    max_turns = 40
    for _ in range(max_turns):
        if controller.is_finished:
            break
        controller.submit_action("player_1", Action.ATTACK)
        controller.submit_action("player_2", Action.ATTACK)
        controller.resolve_round()

    # Match must have concluded cleanly
    assert controller.is_finished is True
    assert controller.state.status == MatchStatus.FINISHED
    assert controller.state.result is not None
    assert controller.state.completed_rounds <= 40
    assert len(controller.round_history) == controller.state.completed_rounds


def test_both_player_orderings_symmetric() -> None:
    """Verify player order symmetry: swapping players produces inverse winner assignment."""
    b1_dead = BladeState(
        player_id="player_1",
        blade_type=BladeType.BALANCED,
        current_energy=0.0,
        max_energy=100.0,
        current_stability=100.0,
        max_stability=100.0,
        position=Position(-2.0, 0.0),
        special_ready_at=0.0,
    )
    b2_alive = create_blade_state("player_2", BladeType.BALANCED, position=Position(2.0, 0.0))

    # P1 dead, P2 alive -> P2 wins
    s1 = MatchState(
        player_1_blade=b1_dead,
        player_2_blade=b2_alive,
        stadium=StadiumState(StadiumType.CLASSIC_DISH, Position(0.0, 0.0), 10.0),
        completed_rounds=1,
        status=MatchStatus.IN_PROGRESS,
    )
    r1 = evaluate_match_termination(s1)
    assert r1 is not None and r1.winner == "player_2"

    # Swap: P1 alive, P2 dead -> P1 wins
    b1_alive = create_blade_state("player_1", BladeType.BALANCED, position=Position(-2.0, 0.0))
    b2_dead = dataclasses.replace(b1_dead, player_id="player_2")
    s2 = MatchState(
        player_1_blade=b1_alive,
        player_2_blade=b2_dead,
        stadium=StadiumState(StadiumType.CLASSIC_DISH, Position(0.0, 0.0), 10.0),
        completed_rounds=1,
        status=MatchStatus.IN_PROGRESS,
    )
    r2 = evaluate_match_termination(s2)
    assert r2 is not None and r2.winner == "player_1"
    assert r1.reason == r2.reason
