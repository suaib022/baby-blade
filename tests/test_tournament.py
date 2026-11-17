"""Automated tests for BLADE ARENA tournament runner, metrics, logging, and UI.

Covers:
- Hand-constructed metrics fixtures (all finish reasons, draws, points, side swaps, zero decisions).
- Seed reproducibility of outcomes and action trajectories (excluding wall-clock durations).
- CSV and JSON export, schema validation, and round-trip parsing.
- Disambiguation and overwrite protection for output directories.
- Unwritable path error handling.
- Graceful cancellation preserving completed results with explicit denominators.
- Headless interactive TournamentScene lifecycle (setup, stepping, cancel, export, reset).
"""

import csv
import json
import os
import shutil
import tempfile
from typing import List

import pytest
import pygame

from blade_arena.game.models import BladeType, FinishReason, StadiumType
from blade_arena.orchestration.batch_runner import (
    BatchMatchResult,
    BatchSummary,
    TournamentBatchRunner,
    compute_tournament_summary,
    export_tournament_results,
    run_headless_batch,
)
from blade_arena.ui.scenes.main_menu import MainMenuScene
from blade_arena.ui.scenes.tournament import TournamentScene
from blade_arena.ui.theme import SCREEN_HEIGHT, SCREEN_WIDTH


@pytest.fixture(autouse=True)
def init_headless_pygame():
    """Ensure headless pygame initialization for UI testing."""
    os.environ["SDL_VIDEODRIVER"] = "dummy"
    os.environ["SDL_AUDIODRIVER"] = "dummy"
    from blade_arena.ui.theme import clear_font_cache

    pygame.init()
    pygame.font.init()
    clear_font_cache()
    surface = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    yield surface
    clear_font_cache()
    if pygame.get_init():
        pygame.quit()


# ------------------------------------------------------------------------------
# 1. Hand-Constructed Metrics Fixtures & Math Tests
# ------------------------------------------------------------------------------

def test_hand_constructed_metrics_fixtures():
    """Verify metrics calculation across diverse synthetic match outcomes."""
    # Construct 5 synthetic matches:
    # Match 0: Agent A (P1) wins by RING_OUT
    # Match 1: Agent B (P1) wins by BURST (Agent A was P2)
    # Match 2: Simultaneous draw
    # Match 3: Agent A (P2) wins by POINTS
    # Match 4: Draw by SPIN_OUT
    matches = [
        BatchMatchResult(
            match_index=0,
            seed=101,
            player_1_name="Agent_A",
            player_2_name="Agent_B",
            player_1_blade=BladeType.BALANCED,
            player_2_blade=BladeType.BALANCED,
            stadium_type=StadiumType.CLASSIC_DISH,
            winner_player_id="player_1",
            winner_name="Agent_A",
            finish_reason=FinishReason.RING_OUT,
            completed_rounds=10,
            elapsed_logical_time=30.0,
            p1_points=50.0,
            p2_points=10.0,
            wall_clock_duration_seconds=0.15,
            round_count=10,
            agent_a_role="P1",
            agent_b_role="P2",
            p1_decision_count=10,
            p1_total_decision_time=0.05,
            p1_mean_decision_time=0.005,
            p2_decision_count=10,
            p2_total_decision_time=0.08,
            p2_mean_decision_time=0.008,
        ),
        BatchMatchResult(
            match_index=1,
            seed=102,
            player_1_name="Agent_B",
            player_2_name="Agent_A",
            player_1_blade=BladeType.BALANCED,
            player_2_blade=BladeType.BALANCED,
            stadium_type=StadiumType.CLASSIC_DISH,
            winner_player_id="player_1",
            winner_name="Agent_B",
            finish_reason=FinishReason.BURST,
            completed_rounds=15,
            elapsed_logical_time=45.0,
            p1_points=40.0,
            p2_points=5.0,
            wall_clock_duration_seconds=0.20,
            round_count=15,
            agent_a_role="P2",
            agent_b_role="P1",
            p1_decision_count=15,
            p1_total_decision_time=0.12,
            p1_mean_decision_time=0.008,
            p2_decision_count=15,
            p2_total_decision_time=0.09,
            p2_mean_decision_time=0.006,
        ),
        BatchMatchResult(
            match_index=2,
            seed=103,
            player_1_name="Agent_A",
            player_2_name="Agent_B",
            player_1_blade=BladeType.BALANCED,
            player_2_blade=BladeType.BALANCED,
            stadium_type=StadiumType.CLASSIC_DISH,
            winner_player_id=None,
            winner_name=None,
            finish_reason=FinishReason.SIMULTANEOUS_ELIMINATION,
            completed_rounds=20,
            elapsed_logical_time=60.0,
            p1_points=0.0,
            p2_points=0.0,
            wall_clock_duration_seconds=0.25,
            round_count=20,
            agent_a_role="P1",
            agent_b_role="P2",
            p1_decision_count=20,
            p1_total_decision_time=0.10,
            p1_mean_decision_time=0.005,
            p2_decision_count=20,
            p2_total_decision_time=0.16,
            p2_mean_decision_time=0.008,
        ),
        BatchMatchResult(
            match_index=3,
            seed=104,
            player_1_name="Agent_B",
            player_2_name="Agent_A",
            player_1_blade=BladeType.BALANCED,
            player_2_blade=BladeType.BALANCED,
            stadium_type=StadiumType.CLASSIC_DISH,
            winner_player_id="player_2",
            winner_name="Agent_A",
            finish_reason=FinishReason.POINTS_DECISION,
            completed_rounds=40,
            elapsed_logical_time=120.0,
            p1_points=45.0,
            p2_points=65.0,
            wall_clock_duration_seconds=0.50,
            round_count=40,
            agent_a_role="P2",
            agent_b_role="P1",
            p1_decision_count=40,
            p1_total_decision_time=0.32,
            p1_mean_decision_time=0.008,
            p2_decision_count=40,
            p2_total_decision_time=0.20,
            p2_mean_decision_time=0.005,
        ),
        BatchMatchResult(
            match_index=4,
            seed=105,
            player_1_name="Agent_A",
            player_2_name="Agent_B",
            player_1_blade=BladeType.BALANCED,
            player_2_blade=BladeType.BALANCED,
            stadium_type=StadiumType.CLASSIC_DISH,
            winner_player_id=None,
            winner_name=None,
            finish_reason=FinishReason.SPIN_OUT,
            completed_rounds=25,
            elapsed_logical_time=75.0,
            p1_points=10.0,
            p2_points=10.0,
            wall_clock_duration_seconds=0.30,
            round_count=25,
            agent_a_role="P1",
            agent_b_role="P2",
            p1_decision_count=25,
            p1_total_decision_time=0.12,
            p1_mean_decision_time=0.0048,
            p2_decision_count=25,
            p2_total_decision_time=0.20,
            p2_mean_decision_time=0.008,
        ),
    ]

    summary = compute_tournament_summary(
        total_scheduled=5,
        agent_a_name="Agent_A",
        agent_b_name="Agent_B",
        matches=matches,
        is_cancelled=False,
    )

    # 1. Total matches and outcome sums
    assert summary.total_matches == 5
    assert summary.completed_matches == 5
    assert summary.agent_a_wins == 2
    assert summary.agent_b_wins == 1
    assert summary.draws == 2
    assert summary.agent_a_wins + summary.agent_b_wins + summary.draws == 5

    # 2. Rates with explicit denominator
    assert summary.denominator == 5
    assert summary.agent_a_win_rate == pytest.approx(2 / 5)
    assert summary.agent_b_win_rate == pytest.approx(1 / 5)
    assert summary.draw_rate == pytest.approx(2 / 5)

    # 3. Side breakdown
    # Agent A played P1 in matches 0, 2, 4 (3 matches, 1 win)
    assert summary.agent_a_as_p1_matches == 3
    assert summary.agent_a_as_p1_wins == 1
    assert summary.agent_a_as_p1_win_rate == pytest.approx(1 / 3)

    # Agent A played P2 in matches 1, 3 (2 matches, 1 win)
    assert summary.agent_a_as_p2_matches == 2
    assert summary.agent_a_as_p2_wins == 1
    assert summary.agent_a_as_p2_win_rate == pytest.approx(1 / 2)

    # Agent B played P1 in matches 1, 3 (2 matches, 1 win)
    assert summary.agent_b_as_p1_matches == 2
    assert summary.agent_b_as_p1_wins == 1
    assert summary.agent_b_as_p1_win_rate == pytest.approx(1 / 2)

    # Agent B played P2 in matches 0, 2, 4 (3 matches, 0 wins)
    assert summary.agent_b_as_p2_matches == 3
    assert summary.agent_b_as_p2_wins == 0
    assert summary.agent_b_as_p2_win_rate == 0.0

    # 4. Finish reason tallies
    assert summary.ring_out_count == 1
    assert summary.burst_count == 1
    assert summary.simultaneous_elimination_count == 1
    assert summary.points_decision_count == 1
    assert summary.spin_out_count == 1

    # 5. Durations and telemetry
    assert summary.average_completed_rounds == (10 + 15 + 20 + 40 + 25) / 5  # 22.0
    assert summary.average_logical_duration_seconds == 66.0
    assert summary.total_wall_clock_duration_seconds == pytest.approx(1.40)


def test_zero_matches_division_safety():
    """Verify metrics handle zero matches and zero decisions without ZeroDivisionError."""
    summary = compute_tournament_summary(
        total_scheduled=10,
        agent_a_name="Agent_A",
        agent_b_name="Agent_B",
        matches=[],
        is_cancelled=True,
    )
    assert summary.completed_matches == 0
    assert summary.agent_a_win_rate == 0.0
    assert summary.agent_b_win_rate == 0.0
    assert summary.draw_rate == 0.0
    assert summary.average_completed_rounds == 0.0
    assert summary.average_logical_duration_seconds == 0.0
    assert summary.agent_a_mean_decision_time == 0.0
    assert summary.agent_b_mean_decision_time == 0.0


# ------------------------------------------------------------------------------
# 2. Seed Reproducibility Test
# ------------------------------------------------------------------------------

def test_seed_reproducibility():
    """Verify identical random seeds produce 100% deterministic tournament outcomes."""
    runner1 = TournamentBatchRunner(
        total_matches=2,
        agent_a="ironclad",
        agent_b="cyclone",
        agent_a_difficulty="easy",
        agent_b_difficulty="easy",
        base_seed=12345,
    )
    sum1 = runner1.run_all()

    runner2 = TournamentBatchRunner(
        total_matches=2,
        agent_a="ironclad",
        agent_b="cyclone",
        agent_a_difficulty="easy",
        agent_b_difficulty="easy",
        base_seed=12345,
    )
    sum2 = runner2.run_all()

    assert sum1.completed_matches == sum2.completed_matches
    assert sum1.agent_a_wins == sum2.agent_a_wins
    assert sum1.agent_b_wins == sum2.agent_b_wins
    assert sum1.draws == sum2.draws

    for m1, m2 in zip(sum1.matches, sum2.matches):
        assert m1.winner_name == m2.winner_name
        assert m1.finish_reason == m2.finish_reason
        assert m1.completed_rounds == m2.completed_rounds
        assert m1.p1_points == m2.p1_points
        assert m1.p2_points == m2.p2_points
        assert len(m1.step_records) == len(m2.step_records)
        for r1, r2 in zip(m1.step_records, m2.step_records):
            assert r1.player_1_action == r2.player_1_action
            assert r1.player_2_action == r2.player_2_action


# ------------------------------------------------------------------------------
# 3. CSV and JSON Export & Round-Trip Tests
# ------------------------------------------------------------------------------

def test_csv_and_json_export_and_round_trip():
    """Verify log export creates valid CSV summary, JSON summary, and per-match JSONs."""
    tmp_dir = tempfile.mkdtemp(prefix="tourn_test_")
    try:
        runner = TournamentBatchRunner(
            total_matches=2,
            agent_a="ironclad",
            agent_b="cyclone",
            agent_a_difficulty="easy",
            agent_b_difficulty="easy",
            base_seed=42,
        )
        summary = runner.run_all()

        csv_file, match_dir = export_tournament_results(summary, output_dir=tmp_dir, overwrite=True)

        # 1. Check CSV summary
        assert os.path.exists(csv_file)
        with open(csv_file, mode="r", encoding="utf-8") as f:
            reader = list(csv.reader(f))
            assert len(reader) == 3  # Header + 2 match rows
            header = reader[0]
            assert "match_index" in header
            assert "winner_name" in header
            assert "finish_reason" in header

        # 2. Check summary JSON
        summary_json = os.path.join(tmp_dir, "summary.json")
        assert os.path.exists(summary_json)
        with open(summary_json, mode="r", encoding="utf-8") as f:
            data = json.load(f)
            assert data["total_scheduled"] == 2
            assert data["completed_matches"] == 2
            assert "agent_a" in data
            assert "agent_b" in data
            assert "finish_causes" in data

        # 3. Check per-match JSONs
        m1_file = os.path.join(match_dir, "match_001.json")
        m2_file = os.path.join(match_dir, "match_002.json")
        assert os.path.exists(m1_file)
        assert os.path.exists(m2_file)

        with open(m1_file, mode="r", encoding="utf-8") as f:
            m1_data = json.load(f)
            assert m1_data["match_index"] == 1
            assert "configuration" in m1_data
            assert "outcome" in m1_data
            assert "telemetry" in m1_data
            assert "rounds" in m1_data
            assert len(m1_data["rounds"]) > 0

    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_export_no_overwrite_disambiguation():
    """Verify export creates a disambiguated folder when directory already has content."""
    tmp_parent = tempfile.mkdtemp(prefix="tourn_disambig_")
    try:
        target_dir = os.path.join(tmp_parent, "results")
        os.makedirs(target_dir, exist_ok=True)
        # Pre-seed with existing file
        with open(os.path.join(target_dir, "existing.txt"), "w") as f:
            f.write("prior")

        summary = compute_tournament_summary(1, "A", "B", [])
        csv_file, _ = export_tournament_results(summary, output_dir=target_dir, overwrite=False)

        # Should have created target_dir_1
        assert "results_1" in csv_file
        assert os.path.exists(csv_file)
    finally:
        shutil.rmtree(tmp_parent, ignore_errors=True)


def test_export_unwritable_path_raises_oserror():
    """Verify exporting to an invalid/unwritable path raises OSError."""
    summary = compute_tournament_summary(1, "A", "B", [])
    # On Windows, path with illegal characters like '???' raises OSError
    with pytest.raises(OSError):
        export_tournament_results(summary, output_dir="invalid:\x00forbidden", overwrite=True)


# ------------------------------------------------------------------------------
# 4. Cancellation & Progress Tests
# ------------------------------------------------------------------------------

def test_runner_cancellation_preserves_matches():
    """Verify cancellation stops future matches while retaining completed records."""
    runner = TournamentBatchRunner(
        total_matches=6,
        agent_a="ironclad",
        agent_b="cyclone",
        agent_a_difficulty="easy",
        agent_b_difficulty="easy",
        base_seed=42,
    )

    # Step 2 matches
    m0 = runner.step_match()
    m1 = runner.step_match()
    assert m0 is not None
    assert m1 is not None
    assert runner.progress == pytest.approx(2 / 6)

    # Cancel runner
    runner.cancel()
    assert runner.is_cancelled is True
    assert runner.is_finished is True

    # Further step attempts return None
    assert runner.step_match() is None

    # Summary correctly reflects partial state
    summary = runner.get_summary()
    assert summary.is_cancelled is True
    assert summary.completed_matches == 2
    assert summary.total_matches == 6
    assert summary.denominator == 2
    assert len(summary.matches) == 2


# ------------------------------------------------------------------------------
# 5. Interactive TournamentScene UI Headless Lifecycle
# ------------------------------------------------------------------------------

def test_tournament_scene_headless_lifecycle(init_headless_pygame):
    """Verify TournamentScene configuration, stepping, cancellation, export, and reset."""
    screen = init_headless_pygame
    scene = TournamentScene()
    scene.match_count = 5
    scene.agent_a_diff = "easy"
    scene.agent_b_diff = "easy"

    # 1. Render setup screen
    scene.render(screen)
    assert scene.is_running is False
    assert scene.summary is None

    # 2. Start tournament
    scene.btn_start.callback()
    assert scene.is_running is True
    assert scene.runner is not None

    # 3. Step 2 matches via update loop
    scene.update(0.016)
    assert scene.runner.current_match_index == 1
    scene.update(0.016)
    assert scene.runner.current_match_index == 2

    # Render running frame
    scene.render(screen)

    # 4. Cancel tournament
    scene.btn_cancel.callback()
    assert scene.is_running is False
    assert scene.summary is not None
    assert scene.summary.completed_matches == 2
    assert scene.summary.is_cancelled is True

    # Render cancelled / results view
    scene.render(screen)

    # 5. Test Export Logs
    scene._export_logs()
    assert scene.export_message is not None
    assert "successfully exported" in scene.export_message

    # 6. Test Reset
    scene.btn_reset.callback()
    assert scene.is_running is False
    assert scene.summary is None
    assert scene.runner is None

    # 7. Navigation test: ESC returns MainMenuScene
    esc_event = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE)
    next_s = scene.handle_event(esc_event)
    assert isinstance(next_s, MainMenuScene)
