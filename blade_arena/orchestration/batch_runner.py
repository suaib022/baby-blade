"""Headless tournament batch runner and reproducible AI evaluation engine for BLADE ARENA.

Executes configurable batches of matches between autonomous AI agents with:
- Exact seed assignment per match for reproducible stochastic rollouts.
- Alternating starting sides (Player 1 / Player 2) ensuring fair evaluation.
- High-resolution decision timing and per-agent telemetry tracking.
- Per-match detailed JSON audit logs and aggregate CSV summary reporting.
- Metric calculation: wins/losses/draws, explicit-denominator win percentages,
  finish cause tallies, average rounds and durations, and side-by-side breakdowns.
- Step-by-step runner interface supporting interactive GUI integration and graceful cancellation.
"""

from __future__ import annotations

import csv
import json
import os
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple, Union

from blade_arena.game.models import (
    BladeType,
    FinishReason,
    MatchResult,
    MatchState,
    StadiumType,
)
from blade_arena.game.win_conditions import calculate_blade_points
from blade_arena.orchestration.participants import (
    AgentType,
    AIParticipant,
    Participant,
    create_ai_participant,
)
from blade_arena.orchestration.session import (
    GameMode,
    IterationGuardError,
    MatchSession,
    SessionConfig,
    StepRecord,
)

ENGINE_VERSION: str = "1.0.0"


@dataclass(frozen=True)
class BatchMatchResult:
    """Outcome, score audit, and telemetry for a single match in a tournament series."""

    match_index: int
    seed: int
    player_1_name: str
    player_2_name: str
    player_1_blade: BladeType
    player_2_blade: BladeType
    stadium_type: StadiumType
    winner_player_id: Optional[str]
    winner_name: Optional[str]
    finish_reason: Optional[FinishReason]
    completed_rounds: int
    elapsed_logical_time: float
    p1_points: float
    p2_points: float
    wall_clock_duration_seconds: float
    round_count: int

    # Telemetry and side tracking
    agent_a_role: str = "P1"  # "P1" or "P2"
    agent_b_role: str = "P2"  # "P2" or "P1"
    p1_decision_count: int = 0
    p1_total_decision_time: float = 0.0
    p1_mean_decision_time: float = 0.0
    p2_decision_count: int = 0
    p2_total_decision_time: float = 0.0
    p2_mean_decision_time: float = 0.0
    agent_a_budget: Optional[int] = None
    agent_b_budget: Optional[int] = None
    p1_causes: Tuple[FinishReason, ...] = ()
    p2_causes: Tuple[FinishReason, ...] = ()
    step_records: Tuple[StepRecord, ...] = ()


@dataclass(frozen=True)
class BatchSummary:
    """Aggregated results, finish cause tallies, and side breakdowns across a batch series."""

    total_matches: int
    completed_matches: int
    agent_a_name: str
    agent_b_name: str
    agent_a_wins: int
    agent_b_wins: int
    draws: int
    matches: Tuple[BatchMatchResult, ...]
    is_cancelled: bool = False

    # Side breakdown counts
    agent_a_as_p1_matches: int = 0
    agent_a_as_p1_wins: int = 0
    agent_a_as_p2_matches: int = 0
    agent_a_as_p2_wins: int = 0
    agent_b_as_p1_matches: int = 0
    agent_b_as_p1_wins: int = 0
    agent_b_as_p2_matches: int = 0
    agent_b_as_p2_wins: int = 0

    # Finish reason tallies
    ring_out_count: int = 0
    burst_count: int = 0
    spin_out_count: int = 0
    simultaneous_elimination_count: int = 0
    points_decision_count: int = 0

    # Aggregate telemetry
    total_wall_clock_duration_seconds: float = 0.0
    average_completed_rounds: float = 0.0
    average_logical_duration_seconds: float = 0.0
    agent_a_total_decisions: int = 0
    agent_a_total_decision_time: float = 0.0
    agent_a_mean_decision_time: float = 0.0
    agent_b_total_decisions: int = 0
    agent_b_total_decision_time: float = 0.0
    agent_b_mean_decision_time: float = 0.0

    # --------------------------------------------------------------------------
    # Win / Draw Rates (Denominator explicitly total completed matches)
    # --------------------------------------------------------------------------

    @property
    def denominator(self) -> int:
        """Effective completed matches denominator for rates."""
        return self.completed_matches

    @property
    def agent_a_win_rate(self) -> float:
        """Fraction of completed matches won by Agent A."""
        return self.agent_a_wins / self.denominator if self.denominator > 0 else 0.0

    @property
    def agent_b_win_rate(self) -> float:
        """Fraction of completed matches won by Agent B."""
        return self.agent_b_wins / self.denominator if self.denominator > 0 else 0.0

    @property
    def draw_rate(self) -> float:
        """Fraction of completed matches resulting in a draw."""
        return self.draws / self.denominator if self.denominator > 0 else 0.0

    @property
    def agent_a_as_p1_win_rate(self) -> float:
        """Fraction of matches won by Agent A when playing as Player 1 (Left)."""
        return (
            self.agent_a_as_p1_wins / self.agent_a_as_p1_matches
            if self.agent_a_as_p1_matches > 0
            else 0.0
        )

    @property
    def agent_a_as_p2_win_rate(self) -> float:
        """Fraction of matches won by Agent A when playing as Player 2 (Right)."""
        return (
            self.agent_a_as_p2_wins / self.agent_a_as_p2_matches
            if self.agent_a_as_p2_matches > 0
            else 0.0
        )

    @property
    def agent_b_as_p1_win_rate(self) -> float:
        """Fraction of matches won by Agent B when playing as Player 1 (Left)."""
        return (
            self.agent_b_as_p1_wins / self.agent_b_as_p1_matches
            if self.agent_b_as_p1_matches > 0
            else 0.0
        )

    @property
    def agent_b_as_p2_win_rate(self) -> float:
        """Fraction of matches won by Agent B when playing as Player 2 (Right)."""
        return (
            self.agent_b_as_p2_wins / self.agent_b_as_p2_matches
            if self.agent_b_as_p2_matches > 0
            else 0.0
        )


ParticipantFactory = Callable[[int, str], Participant]


def _make_factory(
    agent_spec: Union[str, AgentType, ParticipantFactory, Participant],
    default_name: str,
    difficulty: str = "medium",
    budget: Optional[int] = None,
) -> ParticipantFactory:
    """Normalize agent specifications into a callable factory f(seed, player_id) -> Participant."""
    if callable(agent_spec) and not isinstance(agent_spec, type):
        # Factory callable: inspect whether it accepts player_id
        import inspect

        sig = inspect.signature(agent_spec)
        if len(sig.parameters) >= 2:
            return agent_spec  # type: ignore[return-value]
        return lambda seed, player_id: agent_spec(seed)  # type: ignore[call-arg]

    if isinstance(agent_spec, (str, AgentType)):
        extra_kwargs: Dict[str, Any] = {}
        spec_str = (
            agent_spec.value.lower()
            if isinstance(agent_spec, AgentType)
            else str(agent_spec).lower()
        )
        if budget is not None:
            if spec_str == "ironclad":
                extra_kwargs["max_depth"] = budget
            elif spec_str == "cyclone":
                extra_kwargs["iterations"] = budget

        return lambda seed, player_id: create_ai_participant(
            name=default_name,
            agent_type=agent_spec,
            difficulty=difficulty,
            seed=seed,
            player_id=player_id,
            **extra_kwargs,
        )

    if isinstance(agent_spec, Participant):
        return lambda seed, player_id: agent_spec

    raise TypeError(f"Unsupported agent specification: {agent_spec}")


def compute_tournament_summary(
    total_scheduled: int,
    agent_a_name: str,
    agent_b_name: str,
    matches: Sequence[BatchMatchResult],
    is_cancelled: bool = False,
) -> BatchSummary:
    """Compute aggregate tournament metrics from individual match outcomes.

    Handles zero matches, draws, odd/even side swaps, and missing timings safely.
    """
    completed_matches = len(matches)
    agent_a_wins = 0
    agent_b_wins = 0
    draws = 0

    # Side breakdowns
    a_p1_m = 0
    a_p1_w = 0
    a_p2_m = 0
    a_p2_w = 0
    b_p1_m = 0
    b_p1_w = 0
    b_p2_m = 0
    b_p2_w = 0

    # Finish reasons
    ring_out_cnt = 0
    burst_cnt = 0
    spin_out_cnt = 0
    simul_cnt = 0
    points_cnt = 0

    total_rounds = 0
    total_logical_time = 0.0
    total_wall_clock = 0.0

    a_decisions = 0
    a_decision_time = 0.0
    b_decisions = 0
    b_decision_time = 0.0

    for m in matches:
        total_rounds += m.completed_rounds
        total_logical_time += m.elapsed_logical_time
        total_wall_clock += m.wall_clock_duration_seconds

        # Finish reason tally
        if m.finish_reason == FinishReason.RING_OUT:
            ring_out_cnt += 1
        elif m.finish_reason == FinishReason.BURST:
            burst_cnt += 1
        elif m.finish_reason == FinishReason.SPIN_OUT:
            spin_out_cnt += 1
        elif m.finish_reason == FinishReason.SIMULTANEOUS_ELIMINATION:
            simul_cnt += 1
        elif m.finish_reason == FinishReason.POINTS_DECISION:
            points_cnt += 1

        # Outcome accounting
        if m.winner_name == agent_a_name:
            agent_a_wins += 1
        elif m.winner_name == agent_b_name:
            agent_b_wins += 1
        else:
            draws += 1

        # Side assignments
        if m.agent_a_role == "P1":
            a_p1_m += 1
            b_p2_m += 1
            if m.winner_name == agent_a_name:
                a_p1_w += 1
            elif m.winner_name == agent_b_name:
                b_p2_w += 1
            # Telemetry
            a_decisions += m.p1_decision_count
            a_decision_time += m.p1_total_decision_time
            b_decisions += m.p2_decision_count
            b_decision_time += m.p2_total_decision_time
        else:
            a_p2_m += 1
            b_p1_m += 1
            if m.winner_name == agent_a_name:
                a_p2_w += 1
            elif m.winner_name == agent_b_name:
                b_p1_w += 1
            # Telemetry
            a_decisions += m.p2_decision_count
            a_decision_time += m.p2_total_decision_time
            b_decisions += m.p1_decision_count
            b_decision_time += m.p1_total_decision_time

    # Means
    avg_rounds = total_rounds / completed_matches if completed_matches > 0 else 0.0
    avg_logical = total_logical_time / completed_matches if completed_matches > 0 else 0.0
    a_mean_dt = a_decision_time / a_decisions if a_decisions > 0 else 0.0
    b_mean_dt = b_decision_time / b_decisions if b_decisions > 0 else 0.0

    return BatchSummary(
        total_matches=total_scheduled,
        completed_matches=completed_matches,
        agent_a_name=agent_a_name,
        agent_b_name=agent_b_name,
        agent_a_wins=agent_a_wins,
        agent_b_wins=agent_b_wins,
        draws=draws,
        matches=tuple(matches),
        is_cancelled=is_cancelled,
        agent_a_as_p1_matches=a_p1_m,
        agent_a_as_p1_wins=a_p1_w,
        agent_a_as_p2_matches=a_p2_m,
        agent_a_as_p2_wins=a_p2_w,
        agent_b_as_p1_matches=b_p1_m,
        agent_b_as_p1_wins=b_p1_w,
        agent_b_as_p2_matches=b_p2_m,
        agent_b_as_p2_wins=b_p2_w,
        ring_out_count=ring_out_cnt,
        burst_count=burst_cnt,
        spin_out_count=spin_out_cnt,
        simultaneous_elimination_count=simul_cnt,
        points_decision_count=points_cnt,
        total_wall_clock_duration_seconds=total_wall_clock,
        average_completed_rounds=avg_rounds,
        average_logical_duration_seconds=avg_logical,
        agent_a_total_decisions=a_decisions,
        agent_a_total_decision_time=a_decision_time,
        agent_a_mean_decision_time=a_mean_dt,
        agent_b_total_decisions=b_decisions,
        agent_b_total_decision_time=b_decision_time,
        agent_b_mean_decision_time=b_mean_dt,
    )


class TournamentBatchRunner:
    """Stateful batch tournament runner supporting incremental stepping, cancel, and export."""

    def __init__(
        self,
        total_matches: int,
        agent_a: Union[str, AgentType, ParticipantFactory, Participant],
        agent_b: Union[str, AgentType, ParticipantFactory, Participant],
        agent_a_name: str = "Ironclad",
        agent_b_name: str = "Cyclone",
        agent_a_difficulty: str = "medium",
        agent_b_difficulty: str = "medium",
        blade_a: BladeType = BladeType.BALANCED,
        blade_b: BladeType = BladeType.BALANCED,
        stadium_type: StadiumType = StadiumType.CLASSIC_DISH,
        base_seed: int = 42,
        seeds: Optional[Sequence[int]] = None,
        alternate_sides: bool = True,
        max_rounds_guard: int = 45,
        agent_a_budget: Optional[int] = None,
        agent_b_budget: Optional[int] = None,
    ) -> None:
        if total_matches <= 0:
            raise ValueError(f"total_matches must be positive, got {total_matches}")

        self.total_matches: int = total_matches
        self.agent_a_name: str = agent_a_name
        self.agent_b_name: str = agent_b_name
        self.agent_a_difficulty: str = agent_a_difficulty
        self.agent_b_difficulty: str = agent_b_difficulty
        self.blade_a: BladeType = blade_a
        self.blade_b: BladeType = blade_b
        self.stadium_type: StadiumType = stadium_type
        self.base_seed: int = base_seed
        self.seeds: Optional[Sequence[int]] = seeds
        self.alternate_sides: bool = alternate_sides
        self.max_rounds_guard: int = max_rounds_guard
        self.agent_a_budget: Optional[int] = agent_a_budget
        self.agent_b_budget: Optional[int] = agent_b_budget

        self._factory_a = _make_factory(
            agent_a, agent_a_name, agent_a_difficulty, budget=agent_a_budget
        )
        self._factory_b = _make_factory(
            agent_b, agent_b_name, agent_b_difficulty, budget=agent_b_budget
        )

        self.completed_results: List[BatchMatchResult] = []
        self.current_match_index: int = 0
        self.is_cancelled: bool = False

    @property
    def is_finished(self) -> bool:
        """True if all scheduled matches are complete or runner was cancelled."""
        return self.is_cancelled or (self.current_match_index >= self.total_matches)

    @property
    def progress(self) -> float:
        """Fraction of scheduled matches completed (0.0 to 1.0)."""
        return len(self.completed_results) / self.total_matches

    def cancel(self) -> None:
        """Gracefully stop future matches while preserving completed results."""
        self.is_cancelled = True

    def step_match(self) -> Optional[BatchMatchResult]:
        """Execute the next scheduled match in the series.

        Returns:
            The BatchMatchResult for the completed match, or None if already finished.
        """
        if self.is_finished:
            return None

        i = self.current_match_index
        match_seed = self.seeds[i] if self.seeds is not None else self.base_seed + i
        start_wall_time = time.perf_counter()

        swap = self.alternate_sides and (i % 2 == 1)

        if not swap:
            p1 = self._factory_a(match_seed, "player_1")
            p2 = self._factory_b(match_seed + 10000, "player_2")
            p1_name = self.agent_a_name
            p2_name = self.agent_b_name
            b1 = self.blade_a
            b2 = self.blade_b
            a_role, b_role = "P1", "P2"
        else:
            p1 = self._factory_b(match_seed + 10000, "player_1")
            p2 = self._factory_a(match_seed, "player_2")
            p1_name = self.agent_b_name
            p2_name = self.agent_a_name
            b1 = self.blade_b
            b2 = self.blade_a
            a_role, b_role = "P2", "P1"

        session = MatchSession(
            participant_1=p1,
            participant_2=p2,
            config=SessionConfig(
                mode=GameMode.AI_VS_AI,
                player_1_blade=b1,
                player_2_blade=b2,
                stadium_type=self.stadium_type,
                max_rounds_guard=self.max_rounds_guard,
            ),
        )

        final_state = session.run_to_completion(max_rounds=self.max_rounds_guard)
        wall_clock_duration = time.perf_counter() - start_wall_time

        result: Optional[MatchResult] = final_state.result
        winner_id = result.winner if result is not None else None
        reason = result.reason if result is not None else None

        winner_name: Optional[str] = None
        if winner_id == session.player_1_id:
            winner_name = p1_name
        elif winner_id == session.player_2_id:
            winner_name = p2_name

        if result is not None and result.scores is not None:
            p1_pts = result.scores[0]
            p2_pts = result.scores[1]
        else:
            p1_pts = calculate_blade_points(final_state.player_1_blade, final_state.stadium.radius)
            p2_pts = calculate_blade_points(final_state.player_2_blade, final_state.stadium.radius)

        # Telemetry from participants if AIParticipant
        p1_dec_cnt = getattr(p1, "decision_count", len(session.round_history))
        p1_tot_dt = getattr(p1, "total_decision_time", 0.0)
        p1_mean_dt = getattr(p1, "mean_decision_time", 0.0)

        p2_dec_cnt = getattr(p2, "decision_count", len(session.round_history))
        p2_tot_dt = getattr(p2, "total_decision_time", 0.0)
        p2_mean_dt = getattr(p2, "mean_decision_time", 0.0)

        p1_causes = result.player_1_causes if result else ()
        p2_causes = result.player_2_causes if result else ()

        match_res = BatchMatchResult(
            match_index=i,
            seed=match_seed,
            player_1_name=p1_name,
            player_2_name=p2_name,
            player_1_blade=b1,
            player_2_blade=b2,
            stadium_type=self.stadium_type,
            winner_player_id=winner_id,
            winner_name=winner_name,
            finish_reason=reason,
            completed_rounds=final_state.completed_rounds,
            elapsed_logical_time=final_state.elapsed_game_time,
            p1_points=p1_pts,
            p2_points=p2_pts,
            wall_clock_duration_seconds=wall_clock_duration,
            round_count=len(session.round_history),
            agent_a_role=a_role,
            agent_b_role=b_role,
            p1_decision_count=p1_dec_cnt,
            p1_total_decision_time=p1_tot_dt,
            p1_mean_decision_time=p1_mean_dt,
            p2_decision_count=p2_dec_cnt,
            p2_total_decision_time=p2_tot_dt,
            p2_mean_decision_time=p2_mean_dt,
            agent_a_budget=self.agent_a_budget,
            agent_b_budget=self.agent_b_budget,
            p1_causes=p1_causes,
            p2_causes=p2_causes,
            step_records=session.round_history,
        )

        self.completed_results.append(match_res)
        self.current_match_index += 1
        return match_res

    def run_all(self) -> BatchSummary:
        """Execute all remaining matches synchronously and return the summary."""
        while not self.is_finished:
            self.step_match()
        return self.get_summary()

    def get_summary(self) -> BatchSummary:
        """Compute the current BatchSummary based on completed matches."""
        return compute_tournament_summary(
            total_scheduled=self.total_matches,
            agent_a_name=self.agent_a_name,
            agent_b_name=self.agent_b_name,
            matches=self.completed_results,
            is_cancelled=self.is_cancelled,
        )


def export_tournament_results(
    summary: BatchSummary,
    output_dir: str,
    overwrite: bool = False,
) -> Tuple[str, str]:
    """Save detailed per-match JSON logs and aggregate CSV summary to disk.

    Args:
        summary: The BatchSummary to export.
        output_dir: Target directory path for logs and summary files.
        overwrite: If False, auto-disambiguates existing non-empty directory.

    Returns:
        A tuple of (csv_path, matches_dir_path).

    Raises:
        OSError: If target directory cannot be created or is not writable.
    """
    target_path = Path(output_dir)

    # Disambiguate if directory exists, is non-empty, and overwrite is False
    if target_path.exists() and not overwrite and any(target_path.iterdir()):
        counter = 1
        while True:
            candidate = target_path.parent / f"{target_path.name}_{counter}"
            if not candidate.exists() or not any(candidate.iterdir()):
                target_path = candidate
                break
            counter += 1

    try:
        target_path.mkdir(parents=True, exist_ok=True)
        matches_dir = target_path / "matches"
        matches_dir.mkdir(parents=True, exist_ok=True)
    except Exception as exc:
        raise OSError(f"Cannot create tournament output directory '{target_path}': {exc}") from exc

    # 1. Export CSV summary
    csv_file = target_path / "tournament_summary.csv"
    try:
        with open(csv_file, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "match_index",
                "seed",
                "player_1_name",
                "player_2_name",
                "p1_blade",
                "p2_blade",
                "stadium",
                "winner_name",
                "winner_player_id",
                "finish_reason",
                "completed_rounds",
                "elapsed_logical_seconds",
                "p1_points",
                "p2_points",
                "wall_clock_seconds",
                "p1_decisions",
                "p1_mean_decision_seconds",
                "p2_decisions",
                "p2_mean_decision_seconds",
            ])
            for m in summary.matches:
                writer.writerow([
                    m.match_index + 1,
                    m.seed,
                    m.player_1_name,
                    m.player_2_name,
                    m.player_1_blade.name,
                    m.player_2_blade.name,
                    m.stadium_type.name,
                    m.winner_name or "DRAW",
                    m.winner_player_id or "NONE",
                    m.finish_reason.name if m.finish_reason else "N/A",
                    m.completed_rounds,
                    f"{m.elapsed_logical_time:.1f}",
                    f"{m.p1_points:.2f}",
                    f"{m.p2_points:.2f}",
                    f"{m.wall_clock_duration_seconds:.4f}",
                    m.p1_decision_count,
                    f"{m.p1_mean_decision_time:.4f}",
                    m.p2_decision_count,
                    f"{m.p2_mean_decision_time:.4f}",
                ])
    except Exception as exc:
        raise OSError(f"Failed writing CSV summary '{csv_file}': {exc}") from exc

    # 2. Export per-match detailed JSON logs
    for m in summary.matches:
        match_json_file = matches_dir / f"match_{m.match_index + 1:03d}.json"
        rounds_data = []
        for r in m.step_records:
            rounds_data.append({
                "round": r.round_number,
                "p1_action": r.player_1_action.name,
                "p2_action": r.player_2_action.name,
                "p1_stability": r.state_after.player_1_blade.current_stability,
                "p1_energy": r.state_after.player_1_blade.current_energy,
                "p2_stability": r.state_after.player_2_blade.current_stability,
                "p2_energy": r.state_after.player_2_blade.current_energy,
                "stadium_radius": r.state_after.stadium.radius,
            })

        payload = {
            "version": ENGINE_VERSION,
            "match_index": m.match_index + 1,
            "seed": m.seed,
            "timestamp": datetime.now().isoformat(),
            "configuration": {
                "stadium": m.stadium_type.name,
                "player_1": {
                    "name": m.player_1_name,
                    "blade": m.player_1_blade.name,
                    "budget": m.agent_a_budget if m.agent_a_role == "P1" else m.agent_b_budget,
                },
                "player_2": {
                    "name": m.player_2_name,
                    "blade": m.player_2_blade.name,
                    "budget": m.agent_a_budget if m.agent_a_role == "P2" else m.agent_b_budget,
                },
            },
            "outcome": {
                "winner_name": m.winner_name,
                "winner_id": m.winner_player_id,
                "finish_reason": m.finish_reason.name if m.finish_reason else None,
                "p1_causes": [c.name for c in m.p1_causes],
                "p2_causes": [c.name for c in m.p2_causes],
                "p1_final_points": m.p1_points,
                "p2_final_points": m.p2_points,
            },
            "timing": {
                "completed_rounds": m.completed_rounds,
                "elapsed_logical_seconds": m.elapsed_logical_time,
                "wall_clock_seconds": m.wall_clock_duration_seconds,
            },
            "telemetry": {
                "p1_decisions": m.p1_decision_count,
                "p1_total_decision_time": m.p1_total_decision_time,
                "p1_mean_decision_time": m.p1_mean_decision_time,
                "p2_decisions": m.p2_decision_count,
                "p2_total_decision_time": m.p2_total_decision_time,
                "p2_mean_decision_time": m.p2_mean_decision_time,
            },
            "rounds": rounds_data,
        }

        try:
            with open(match_json_file, mode="w", encoding="utf-8") as jf:
                json.dump(payload, jf, indent=2)
        except Exception as exc:
            raise OSError(f"Failed writing JSON log '{match_json_file}': {exc}") from exc

    # 3. Export aggregate summary JSON
    summary_json_file = target_path / "summary.json"
    summary_dict = {
        "engine_version": ENGINE_VERSION,
        "total_scheduled": summary.total_matches,
        "completed_matches": summary.completed_matches,
        "is_cancelled": summary.is_cancelled,
        "agent_a": {
            "name": summary.agent_a_name,
            "wins": summary.agent_a_wins,
            "win_rate": summary.agent_a_win_rate,
            "p1_matches": summary.agent_a_as_p1_matches,
            "p1_wins": summary.agent_a_as_p1_wins,
            "p1_win_rate": summary.agent_a_as_p1_win_rate,
            "p2_matches": summary.agent_a_as_p2_matches,
            "p2_wins": summary.agent_a_as_p2_wins,
            "p2_win_rate": summary.agent_a_as_p2_win_rate,
            "mean_decision_time": summary.agent_a_mean_decision_time,
        },
        "agent_b": {
            "name": summary.agent_b_name,
            "wins": summary.agent_b_wins,
            "win_rate": summary.agent_b_win_rate,
            "p1_matches": summary.agent_b_as_p1_matches,
            "p1_wins": summary.agent_b_as_p1_wins,
            "p1_win_rate": summary.agent_b_as_p1_win_rate,
            "p2_matches": summary.agent_b_as_p2_matches,
            "p2_wins": summary.agent_b_as_p2_wins,
            "p2_win_rate": summary.agent_b_as_p2_win_rate,
            "mean_decision_time": summary.agent_b_mean_decision_time,
        },
        "draws": summary.draws,
        "draw_rate": summary.draw_rate,
        "finish_causes": {
            "ring_out": summary.ring_out_count,
            "burst": summary.burst_count,
            "spin_out": summary.spin_out_count,
            "simultaneous_elimination": summary.simultaneous_elimination_count,
            "points_decision": summary.points_decision_count,
        },
        "averages": {
            "rounds": summary.average_completed_rounds,
            "logical_seconds": summary.average_logical_duration_seconds,
            "wall_clock_seconds": summary.total_wall_clock_duration_seconds,
        },
    }

    try:
        with open(summary_json_file, mode="w", encoding="utf-8") as sjf:
            json.dump(summary_dict, sjf, indent=2)
    except Exception as exc:
        raise OSError(f"Failed writing summary JSON '{summary_json_file}': {exc}") from exc

    return str(csv_file), str(matches_dir)


def run_headless_batch(
    total_matches: int,
    agent_a: Union[str, AgentType, ParticipantFactory, Participant],
    agent_b: Union[str, AgentType, ParticipantFactory, Participant],
    agent_a_name: str = "Agent_A",
    agent_b_name: str = "Agent_B",
    agent_a_difficulty: str = "medium",
    agent_b_difficulty: str = "medium",
    blade_a: BladeType = BladeType.BALANCED,
    blade_b: BladeType = BladeType.BALANCED,
    stadium_type: StadiumType = StadiumType.CLASSIC_DISH,
    base_seed: int = 42,
    seeds: Optional[Sequence[int]] = None,
    alternate_sides: bool = True,
    max_rounds_guard: int = 45,
    output_dir: Optional[str] = None,
    save_logs: bool = False,
    agent_a_budget: Optional[int] = None,
    agent_b_budget: Optional[int] = None,
    overwrite: bool = False,
) -> BatchSummary:
    """Execute a series of headless matches between two agents.

    Backwards-compatible API that runs the batch via TournamentBatchRunner.
    """
    runner = TournamentBatchRunner(
        total_matches=total_matches,
        agent_a=agent_a,
        agent_b=agent_b,
        agent_a_name=agent_a_name,
        agent_b_name=agent_b_name,
        agent_a_difficulty=agent_a_difficulty,
        agent_b_difficulty=agent_b_difficulty,
        blade_a=blade_a,
        blade_b=blade_b,
        stadium_type=stadium_type,
        base_seed=base_seed,
        seeds=seeds,
        alternate_sides=alternate_sides,
        max_rounds_guard=max_rounds_guard,
        agent_a_budget=agent_a_budget,
        agent_b_budget=agent_b_budget,
    )

    summary = runner.run_all()

    if output_dir is not None and save_logs:
        export_tournament_results(summary, output_dir=output_dir, overwrite=overwrite)

    return summary
