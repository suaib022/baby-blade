"""Entry point for the BLADE ARENA game shell.

Usage:
    python main.py              # Launch interactive window
    python main.py --smoke-test # Run headless verification for 60 frames
    python main.py --batch 10   # Run headless tournament batch of 10 matches
    python main.py --batch 10 --save-logs --out-dir tournament_results
"""

import argparse
import os
import sys
from typing import Sequence


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="BLADE ARENA — 2D spinning-top battle game shell."
    )
    parser.add_argument(
        "--smoke-test",
        action="store_true",
        help="Run headless smoke test for a fixed number of frames and exit cleanly.",
    )
    parser.add_argument(
        "--frames",
        type=int,
        default=None,
        help="Optional maximum number of frames to run before exiting.",
    )
    parser.add_argument(
        "--shot",
        type=str,
        default=None,
        help="Optional file path to save a screenshot before exiting.",
    )
    parser.add_argument(
        "--batch",
        type=int,
        default=None,
        metavar="COUNT",
        help="Run a headless batch of N tournament matches between AI agents.",
    )
    parser.add_argument(
        "--agent1",
        type=str,
        default="ironclad",
        help="Architecture for Agent 1 ('ironclad' or 'cyclone', default: ironclad).",
    )
    parser.add_argument(
        "--agent2",
        type=str,
        default="cyclone",
        help="Architecture for Agent 2 ('ironclad' or 'cyclone', default: cyclone).",
    )
    parser.add_argument(
        "--diff1",
        type=str,
        default="easy",
        help="Difficulty for Agent 1 ('easy', 'medium', 'hard', default: easy).",
    )
    parser.add_argument(
        "--diff2",
        type=str,
        default="easy",
        help="Difficulty for Agent 2 ('easy', 'medium', 'hard', default: easy).",
    )
    parser.add_argument(
        "--blade1",
        type=str,
        default="balanced",
        choices=["balanced", "attacker", "defender", "stamina"],
        help="Blade archetype for Agent 1 (default: balanced).",
    )
    parser.add_argument(
        "--blade2",
        type=str,
        default="balanced",
        choices=["balanced", "attacker", "defender", "stamina"],
        help="Blade archetype for Agent 2 (default: balanced).",
    )
    parser.add_argument(
        "--stadium",
        type=str,
        default="classic_dish",
        choices=["classic_dish", "ice_rink", "steep_bowl"],
        help="Stadium archetype ('classic_dish', 'ice_rink', 'steep_bowl', default: classic_dish).",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Base random seed for reproducible rollouts (default: 42).",
    )
    parser.add_argument(
        "--out-dir",
        type=str,
        default=None,
        help="Output directory to save per-match JSON logs and CSV summary.",
    )
    parser.add_argument(
        "--save-logs",
        action="store_true",
        help="Enable exporting per-match JSON logs and CSV summary.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """Configure environment and execute the application loop or headless mode."""
    args = parse_args(argv)

    if args.batch is not None:
        from blade_arena.game.models import BladeType, StadiumType
        from blade_arena.orchestration import export_tournament_results, run_headless_batch

        stadium_enum = StadiumType(args.stadium.upper())
        blade_1_enum = BladeType(args.blade1.upper())
        blade_2_enum = BladeType(args.blade2.upper())

        name1 = f"{args.agent1.title()} ({args.diff1})"
        name2 = f"{args.agent2.title()} ({args.diff2})"

        print(
            f"Running headless tournament batch of {args.batch} matches in {args.stadium}: "
            f"{name1} vs {name2}..."
        )

        out_dir = args.out_dir if args.out_dir is not None else ("tournament_results" if args.save_logs else None)
        save_logs = (args.save_logs or args.out_dir is not None)

        summary = run_headless_batch(
            total_matches=args.batch,
            agent_a=args.agent1,
            agent_b=args.agent2,
            agent_a_name=name1,
            agent_b_name=name2,
            agent_a_difficulty=args.diff1,
            agent_b_difficulty=args.diff2,
            blade_a=blade_1_enum,
            blade_b=blade_2_enum,
            stadium_type=stadium_enum,
            base_seed=args.seed,
            output_dir=out_dir,
            save_logs=save_logs,
        )

        print("=" * 68)
        print("HEADLESS TOURNAMENT BATCH SUMMARY")
        print("=" * 68)
        print(f"Total Matches  : {summary.completed_matches} / {summary.total_matches}")
        print(f"{summary.agent_a_name} Wins  : {summary.agent_a_wins} ({summary.agent_a_win_rate * 100:.1f}%)")
        print(f"  As P1 (Left) : {summary.agent_a_as_p1_wins} / {summary.agent_a_as_p1_matches} ({summary.agent_a_as_p1_win_rate * 100:.1f}%)")
        print(f"  As P2 (Right): {summary.agent_a_as_p2_wins} / {summary.agent_a_as_p2_matches} ({summary.agent_a_as_p2_win_rate * 100:.1f}%)")
        print(f"{summary.agent_b_name} Wins  : {summary.agent_b_wins} ({summary.agent_b_win_rate * 100:.1f}%)")
        print(f"  As P1 (Left) : {summary.agent_b_as_p1_wins} / {summary.agent_b_as_p1_matches} ({summary.agent_b_as_p1_win_rate * 100:.1f}%)")
        print(f"  As P2 (Right): {summary.agent_b_as_p2_wins} / {summary.agent_b_as_p2_matches} ({summary.agent_b_as_p2_win_rate * 100:.1f}%)")
        print(f"Draws          : {summary.draws} ({summary.draw_rate * 100:.1f}%)")
        print("-" * 68)
        print("FINISH REASONS:")
        print(f"  Ring-Out Ejections : {summary.ring_out_count}")
        print(f"  Stability Bursts   : {summary.burst_count}")
        print(f"  Energy Spin-Outs   : {summary.spin_out_count}")
        print(f"  Points Decisions   : {summary.points_decision_count}")
        print(f"  Simultaneous Draws : {summary.simultaneous_elimination_count}")
        print("-" * 68)
        print("TIMING & TELEMETRY:")
        print(f"  Average Completed Rounds : {summary.average_completed_rounds:.1f} rounds")
        print(f"  Average Logical Duration : {summary.average_logical_duration_seconds:.1f}s")
        print(f"  Total Wall-Clock Time    : {summary.total_wall_clock_duration_seconds:.2f}s")
        print(f"  {summary.agent_a_name} Mean Decision : {summary.agent_a_mean_decision_time * 1000.0:.2f} ms ({summary.agent_a_total_decisions} decisions)")
        print(f"  {summary.agent_b_name} Mean Decision : {summary.agent_b_mean_decision_time * 1000.0:.2f} ms ({summary.agent_b_total_decisions} decisions)")
        if out_dir is not None:
            print("-" * 68)
            print(f"Logs successfully exported to '{out_dir}/'")
        print("=" * 68)
        return 0

    if args.smoke_test:
        # Configure SDL dummy drivers before Pygame initializes
        os.environ["SDL_VIDEODRIVER"] = "dummy"
        os.environ["SDL_AUDIODRIVER"] = "dummy"
        max_frames = args.frames if args.frames is not None else 60
    else:
        max_frames = args.frames

    from blade_arena.app import BladeArenaApp

    app = BladeArenaApp(max_frames=max_frames, screenshot_path=args.shot)
    return app.run()


if __name__ == "__main__":
    sys.exit(main())
