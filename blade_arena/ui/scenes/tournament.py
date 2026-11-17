"""Tournament Evaluation and AI benchmark scene for BLADE ARENA.

Provides an accessible, interactive tournament UI that configures match batches,
runs them incrementally without freezing the Pygame event loop, displays live analytics
(win rates, side breakdowns, finish causes, decision times), supports graceful cancel,
and exports per-match JSON logs and CSV summaries to disk.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import List, Optional

import pygame

from blade_arena.game.models import BladeType, StadiumType
from blade_arena.orchestration.batch_runner import (
    BatchSummary,
    TournamentBatchRunner,
    export_tournament_results,
)
from blade_arena.ui.scenes.base import Scene
from blade_arena.ui.theme import (
    ARCHETYPE_COLORS,
    COLOR_BG,
    COLOR_P1_PRIMARY,
    COLOR_P2_PRIMARY,
    COLOR_PANEL_BG,
    COLOR_PANEL_BORDER,
    COLOR_TEXT_GOLD,
    COLOR_TEXT_MUTED,
    COLOR_TEXT_SUBTITLE,
    COLOR_TEXT_WHITE,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
    get_font,
)
from blade_arena.ui.widgets import Button, Panel, ProgressBar, ToggleGroup


class TournamentScene(Scene):
    """Interactive tournament runner, progress monitor, and analytics dashboard."""

    def __init__(self) -> None:
        # Configuration parameters
        self.match_count: int = 10
        self.agent_a_type: str = "ironclad"
        self.agent_a_diff: str = "easy"
        self.agent_a_blade: BladeType = BladeType.BALANCED
        self.agent_b_type: str = "cyclone"
        self.agent_b_diff: str = "easy"
        self.agent_b_blade: BladeType = BladeType.BALANCED
        self.stadium: StadiumType = StadiumType.CLASSIC_DISH

        # Runner & state
        self.runner: Optional[TournamentBatchRunner] = None
        self.summary: Optional[BatchSummary] = None
        self.is_running: bool = False
        self.status_message: str = "Configured for tournament comparison"
        self.export_message: Optional[str] = None
        self.start_wall_time: float = 0.0

        # UI elements
        self.setup_toggles: List[ToggleGroup] = []
        self.buttons: List[Button] = []
        self._build_widgets()

    def _build_widgets(self) -> None:
        """Construct interactive UI elements."""
        self.setup_toggles.clear()
        self.buttons.clear()

        if not self.is_running and self.summary is None:
            # ------------------------------------------------------------------
            # Setup View Controls
            # ------------------------------------------------------------------
            # Match count toggle
            count_opts = [("5 Matches", 5), ("10 Matches", 10), ("20 Matches", 20)]
            self.tg_count = ToggleGroup(
                rect=pygame.Rect(80, 140, 360, 32),
                options=count_opts,
                initial_value=self.match_count,
                on_change=lambda val: setattr(self, "match_count", val),
            )
            self.setup_toggles.append(self.tg_count)

            # Stadium toggle
            stadium_opts = [
                ("Classic Dish", StadiumType.CLASSIC_DISH),
                ("Ice Rink (1.25x)", StadiumType.ICE_RINK),
                ("Steep Bowl", StadiumType.STEEP_BOWL),
            ]
            self.tg_stadium = ToggleGroup(
                rect=pygame.Rect(520, 140, 360, 32),
                options=stadium_opts,
                initial_value=self.stadium,
                on_change=lambda val: setattr(self, "stadium", val),
            )
            self.setup_toggles.append(self.tg_stadium)

            # Agent A toggles
            agent_opts = [("Ironclad (Minimax)", "ironclad"), ("Cyclone (MCTS)", "cyclone")]
            diff_opts = [("Easy", "easy"), ("Medium", "medium"), ("Hard", "hard")]
            blade_opts = [
                ("Balanced", BladeType.BALANCED),
                ("Attacker", BladeType.ATTACKER),
                ("Defender", BladeType.DEFENDER),
                ("Stamina", BladeType.STAMINA),
            ]

            self.tg_a_arch = ToggleGroup(
                rect=pygame.Rect(80, 240, 360, 30),
                options=agent_opts,
                initial_value=self.agent_a_type,
                on_change=lambda val: setattr(self, "agent_a_type", val),
            )
            self.tg_a_diff = ToggleGroup(
                rect=pygame.Rect(80, 305, 360, 30),
                options=diff_opts,
                initial_value=self.agent_a_diff,
                on_change=lambda val: setattr(self, "agent_a_diff", val),
            )
            self.tg_a_blade = ToggleGroup(
                rect=pygame.Rect(80, 370, 360, 30),
                options=blade_opts,
                initial_value=self.agent_a_blade,
                on_change=lambda val: setattr(self, "agent_a_blade", val),
            )
            self.setup_toggles.extend([self.tg_a_arch, self.tg_a_diff, self.tg_a_blade])

            # Agent B toggles
            self.tg_b_arch = ToggleGroup(
                rect=pygame.Rect(520, 240, 360, 30),
                options=agent_opts,
                initial_value=self.agent_b_type,
                on_change=lambda val: setattr(self, "agent_b_type", val),
            )
            self.tg_b_diff = ToggleGroup(
                rect=pygame.Rect(520, 305, 360, 30),
                options=diff_opts,
                initial_value=self.agent_b_diff,
                on_change=lambda val: setattr(self, "agent_b_diff", val),
            )
            self.tg_b_blade = ToggleGroup(
                rect=pygame.Rect(520, 370, 360, 30),
                options=blade_opts,
                initial_value=self.agent_b_blade,
                on_change=lambda val: setattr(self, "agent_b_blade", val),
            )
            self.setup_toggles.extend([self.tg_b_arch, self.tg_b_diff, self.tg_b_blade])

            # Buttons
            self.btn_start = Button(
                rect=pygame.Rect(SCREEN_WIDTH // 2 - 130, 530, 260, 46),
                text="START TOURNAMENT",
                shortcut_text="[Space]",
                shortcut_key=pygame.K_SPACE,
                font_size=16,
                custom_bg=(30, 100, 60),
                custom_border=(60, 190, 100),
                callback=self._start_tournament,
            )
            self.btn_back = Button(
                rect=pygame.Rect(50, 530, 160, 46),
                text="Main Menu",
                shortcut_text="[ESC]",
                shortcut_key=pygame.K_ESCAPE,
                font_size=15,
            )
            self.buttons.extend([self.btn_start, self.btn_back])

        else:
            # ------------------------------------------------------------------
            # Execution / Results View Controls
            # ------------------------------------------------------------------
            if self.is_running:
                self.btn_cancel = Button(
                    rect=pygame.Rect(SCREEN_WIDTH // 2 - 100, 560, 200, 44),
                    text="Cancel Batch",
                    shortcut_text="[C]",
                    shortcut_key=pygame.K_c,
                    font_size=15,
                    custom_bg=(140, 35, 45),
                    custom_border=(220, 70, 80),
                    callback=self._cancel_tournament,
                )
                self.buttons.append(self.btn_cancel)
            else:
                self.btn_export = Button(
                    rect=pygame.Rect(SCREEN_WIDTH // 2 - 240, 560, 210, 44),
                    text="Export Logs (CSV+JSON)",
                    shortcut_text="[E]",
                    shortcut_key=pygame.K_e,
                    font_size=15,
                    custom_bg=(40, 80, 130),
                    custom_border=(80, 160, 240),
                    callback=self._export_logs,
                )
                self.btn_reset = Button(
                    rect=pygame.Rect(SCREEN_WIDTH // 2 + 10, 560, 160, 44),
                    text="New Batch",
                    shortcut_text="[R]",
                    shortcut_key=pygame.K_r,
                    font_size=15,
                    callback=self._reset_tournament,
                )
                self.buttons.extend([self.btn_export, self.btn_reset])

            self.btn_back = Button(
                rect=pygame.Rect(50, 560, 150, 44),
                text="Main Menu",
                shortcut_text="[ESC]",
                shortcut_key=pygame.K_ESCAPE,
                font_size=15,
            )
            self.buttons.append(self.btn_back)

    def _start_tournament(self) -> None:
        """Initialize the batch runner and start execution."""
        name_a = f"{self.agent_a_type.title()} ({self.agent_a_diff})"
        name_b = f"{self.agent_b_type.title()} ({self.agent_b_diff})"

        self.runner = TournamentBatchRunner(
            total_matches=self.match_count,
            agent_a=self.agent_a_type,
            agent_b=self.agent_b_type,
            agent_a_name=name_a,
            agent_b_name=name_b,
            agent_a_difficulty=self.agent_a_diff,
            agent_b_difficulty=self.agent_b_diff,
            blade_a=self.agent_a_blade,
            blade_b=self.agent_b_blade,
            stadium_type=self.stadium,
            alternate_sides=True,
        )
        self.is_running = True
        self.start_wall_time = time.perf_counter()
        self.status_message = "Running tournament matches..."
        self.export_message = None
        self._build_widgets()

    def _cancel_tournament(self) -> None:
        """Cancel active batch runner while keeping completed results intact."""
        if self.runner is not None:
            self.runner.cancel()
            self.is_running = False
            self.summary = self.runner.get_summary()
            self.status_message = f"CANCELLED (Partial: {self.summary.completed_matches}/{self.match_count} matches)"
            self._build_widgets()

    def _reset_tournament(self) -> None:
        """Reset runner and return to configuration view."""
        self.runner = None
        self.summary = None
        self.is_running = False
        self.status_message = "Configured for tournament comparison"
        self.export_message = None
        self._build_widgets()

    def _export_logs(self) -> None:
        """Save results to disk."""
        if self.summary is None:
            return
        try:
            csv_path, match_dir = export_tournament_results(
                self.summary, output_dir="tournament_results", overwrite=False
            )
            folder_name = Path(csv_path).parent.name
            self.export_message = f"Logs successfully exported to '{folder_name}/'!"
        except Exception as exc:
            self.export_message = f"Export failed: {exc}"

    def handle_event(self, event: pygame.event.Event) -> Optional[Scene]:
        """Process user interaction and button clicks."""
        for t in self.setup_toggles:
            t.handle_event(event)

        for b in self.buttons:
            if b.handle_event(event):
                if b == self.btn_back:
                    from blade_arena.ui.scenes.main_menu import MainMenuScene

                    return MainMenuScene()
                return None

        # ESC always returns to main menu
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            from blade_arena.ui.scenes.main_menu import MainMenuScene

            return MainMenuScene()

        return None

    def update(self, dt: float) -> Optional[Scene]:
        """Incremental match stepping during active batch execution."""
        if self.is_running and self.runner is not None:
            if not self.runner.is_finished:
                # Step exactly one match per frame to keep UI 60 FPS responsive
                self.runner.step_match()
                self.summary = self.runner.get_summary()
                cur = self.summary.completed_matches
                tot = self.match_count
                self.status_message = f"Executing match {cur}/{tot} ({self.runner.progress * 100:.0f}%)..."
            else:
                self.is_running = False
                self.summary = self.runner.get_summary()
                if self.runner.is_cancelled:
                    self.status_message = f"CANCELLED (Partial: {self.summary.completed_matches}/{self.match_count} matches)"
                else:
                    self.status_message = f"COMPLETED ({self.summary.completed_matches}/{self.match_count} matches finished)"
                self._build_widgets()

        return None

    def render(self, screen: pygame.Surface) -> None:
        """Render the tournament interface."""
        screen.fill(COLOR_BG)
        center_x = SCREEN_WIDTH // 2

        # Header Title
        font_t = get_font(28, bold=True)
        title_surf = font_t.render("TOURNAMENT EVALUATION & BENCHMARK", True, COLOR_TEXT_WHITE)
        screen.blit(title_surf, title_surf.get_rect(center=(center_x, 32)))

        if not self.is_running and self.summary is None:
            self._render_setup_view(screen)
        else:
            self._render_results_view(screen)

        # Draw active buttons
        for b in self.buttons:
            b.draw(screen)

    def _render_setup_view(self, screen: pygame.Surface) -> None:
        """Render setup view with configuration options."""
        font_hdr = get_font(15, bold=True)
        font_lbl = get_font(13, bold=False)

        # Match parameters Panel
        Panel(pygame.Rect(50, 75, 420, 115), title="SERIES PARAMETERS").draw(screen)
        screen.blit(font_lbl.render("Match Count:", True, COLOR_TEXT_SUBTITLE), (80, 115))

        # Stadium Panel
        Panel(pygame.Rect(490, 75, 420, 115), title="ARENA STADIUM").draw(screen)
        screen.blit(font_lbl.render("Stadium Environment:", True, COLOR_TEXT_SUBTITLE), (520, 115))

        # Agent A Panel
        Panel(pygame.Rect(50, 205, 420, 215), title="AGENT A (STARTS AS P1)").draw(screen)
        screen.blit(font_lbl.render("Architecture:", True, COLOR_TEXT_SUBTITLE), (80, 222))
        screen.blit(font_lbl.render("Difficulty:", True, COLOR_TEXT_SUBTITLE), (80, 287))
        screen.blit(font_lbl.render("Blade Archetype:", True, COLOR_TEXT_SUBTITLE), (80, 352))

        # Agent B Panel
        Panel(pygame.Rect(490, 205, 420, 215), title="AGENT B (STARTS AS P2)").draw(screen)
        screen.blit(font_lbl.render("Architecture:", True, COLOR_TEXT_SUBTITLE), (520, 222))
        screen.blit(font_lbl.render("Difficulty:", True, COLOR_TEXT_SUBTITLE), (520, 287))
        screen.blit(font_lbl.render("Blade Archetype:", True, COLOR_TEXT_SUBTITLE), (520, 352))

        # Methodology notice
        font_note = get_font(12, bold=False)
        note_text = "• Alternating starting sides ensure fairness • Seeded RNG enables exact reproducibility • Shared rules engine"
        note_surf = font_note.render(note_text, True, COLOR_TEXT_MUTED)
        screen.blit(note_surf, note_surf.get_rect(center=(SCREEN_WIDTH // 2, 455)))

        # Draw toggles
        for t in self.setup_toggles:
            t.draw(screen)

    def _render_results_view(self, screen: pygame.Surface) -> None:
        """Render live progress, scorecards, finish causes, and telemetry."""
        if self.summary is None and self.runner is not None:
            self.summary = self.runner.get_summary()

        summary = self.summary
        if summary is None:
            return

        # 1. Progress Bar & Status Banner
        prog_rect = pygame.Rect(50, 65, SCREEN_WIDTH - 100, 24)
        prog_ratio = (
            self.runner.progress
            if self.runner is not None
            else summary.completed_matches / max(summary.total_matches, 1)
        )
        ProgressBar(
            rect=prog_rect,
            current_value=summary.completed_matches,
            max_value=summary.total_matches,
            fill_color=(50, 160, 90),
            text_override=f"{summary.completed_matches} / {summary.total_matches} Matches ({prog_ratio * 100:.0f}%)",
            font_size=13,
        ).draw(screen)

        # Status text
        font_stat = get_font(13, bold=True)
        stat_col = (250, 140, 50) if self.is_running else COLOR_TEXT_GOLD
        stat_surf = font_stat.render(self.status_message, True, stat_col)
        screen.blit(stat_surf, (50, 95))

        if self.export_message:
            font_exp = get_font(13, bold=True)
            exp_surf = font_exp.render(self.export_message, True, (100, 220, 140))
            screen.blit(exp_surf, (SCREEN_WIDTH - exp_surf.get_width() - 50, 95))

        # 2. Scorecard & Side Breakdown Panel (Left)
        Panel(pygame.Rect(50, 125, 420, 235), title="MATCH OUTCOMES & SIDE BREAKDOWN").draw(screen)
        font_row = get_font(13, bold=False)
        font_bld = get_font(13, bold=True)

        y = 160
        # Agent A overall
        a_str = f"{summary.agent_a_name}: {summary.agent_a_wins} Wins ({summary.agent_a_win_rate * 100:.1f}%)"
        screen.blit(font_bld.render(a_str, True, COLOR_P1_PRIMARY), (70, y))
        y += 22
        # Agent A side breakdown
        a_sides = f"  As P1 (Left): {summary.agent_a_as_p1_wins}/{summary.agent_a_as_p1_matches} ({summary.agent_a_as_p1_win_rate * 100:.1f}%)  |  As P2: {summary.agent_a_as_p2_wins}/{summary.agent_a_as_p2_matches} ({summary.agent_a_as_p2_win_rate * 100:.1f}%)"
        screen.blit(font_row.render(a_sides, True, COLOR_TEXT_SUBTITLE), (70, y))

        y += 28
        # Agent B overall
        b_str = f"{summary.agent_b_name}: {summary.agent_b_wins} Wins ({summary.agent_b_win_rate * 100:.1f}%)"
        screen.blit(font_bld.render(b_str, True, COLOR_P2_PRIMARY), (70, y))
        y += 22
        # Agent B side breakdown
        b_sides = f"  As P1 (Left): {summary.agent_b_as_p1_wins}/{summary.agent_b_as_p1_matches} ({summary.agent_b_as_p1_win_rate * 100:.1f}%)  |  As P2: {summary.agent_b_as_p2_wins}/{summary.agent_b_as_p2_matches} ({summary.agent_b_as_p2_win_rate * 100:.1f}%)"
        screen.blit(font_row.render(b_sides, True, COLOR_TEXT_SUBTITLE), (70, y))

        y += 28
        # Draws
        d_str = f"Draws (Simultaneous): {summary.draws} ({summary.draw_rate * 100:.1f}%)"
        screen.blit(font_bld.render(d_str, True, COLOR_TEXT_GOLD), (70, y))
        y += 20
        denom_note = f"Denominator: exactly {summary.denominator} completed matches"
        screen.blit(font_row.render(denom_note, True, COLOR_TEXT_MUTED), (70, y))

        # 3. Finish Cause Breakdown & Durations Panel (Right)
        Panel(pygame.Rect(490, 125, 420, 235), title="FINISH CAUSES & MATCH TIMING").draw(screen)
        y = 160
        screen.blit(font_row.render("Ring-Out Ejections:", True, COLOR_TEXT_SUBTITLE), (510, y))
        screen.blit(font_bld.render(f"{summary.ring_out_count}", True, COLOR_TEXT_WHITE), (740, y))
        y += 24
        screen.blit(font_row.render("Stability Bursts:", True, COLOR_TEXT_SUBTITLE), (510, y))
        screen.blit(font_bld.render(f"{summary.burst_count}", True, COLOR_TEXT_WHITE), (740, y))
        y += 24
        screen.blit(font_row.render("Energy Spin-Outs:", True, COLOR_TEXT_SUBTITLE), (510, y))
        screen.blit(font_bld.render(f"{summary.spin_out_count}", True, COLOR_TEXT_WHITE), (740, y))
        y += 24
        screen.blit(font_row.render("Points Decisions (40 Rnds):", True, COLOR_TEXT_SUBTITLE), (510, y))
        screen.blit(font_bld.render(f"{summary.points_decision_count}", True, COLOR_TEXT_WHITE), (740, y))
        y += 24
        screen.blit(font_row.render("Simultaneous Draws:", True, COLOR_TEXT_SUBTITLE), (510, y))
        screen.blit(font_bld.render(f"{summary.simultaneous_elimination_count}", True, COLOR_TEXT_WHITE), (740, y))

        y += 30
        pygame.draw.line(screen, COLOR_PANEL_BORDER, (510, y), (890, y), 1)
        y += 10
        # Durations
        dur_str = f"Avg Rounds: {summary.average_completed_rounds:.1f}   |   Avg Logical: {summary.average_logical_duration_seconds:.1f}s   |   Wall Clock: {summary.total_wall_clock_duration_seconds:.2f}s"
        screen.blit(font_row.render(dur_str, True, COLOR_TEXT_MUTED), (510, y))

        # 4. Telemetry & Decision Diagnostics Panel (Bottom full width)
        Panel(pygame.Rect(50, 375, 860, 165), title="AGENT DECISION BENCHMARK & TELEMETRY").draw(screen)
        y = 410

        # Agent A stats
        a_tel = f"Agent A: {summary.agent_a_name}"
        screen.blit(font_bld.render(a_tel, True, COLOR_P1_PRIMARY), (70, y))
        y += 22
        a_dt_str = f"Total Decisions: {summary.agent_a_total_decisions}   |   Total Time: {summary.agent_a_total_decision_time:.3f}s   |   Mean Time/Decision: {summary.agent_a_mean_decision_time * 1000.0:.2f} ms"
        screen.blit(font_row.render(a_dt_str, True, COLOR_TEXT_WHITE), (70, y))

        y += 28
        # Agent B stats
        b_tel = f"Agent B: {summary.agent_b_name}"
        screen.blit(font_bld.render(b_tel, True, COLOR_P2_PRIMARY), (70, y))
        y += 22
        b_dt_str = f"Total Decisions: {summary.agent_b_total_decisions}   |   Total Time: {summary.agent_b_total_decision_time:.3f}s   |   Mean Time/Decision: {summary.agent_b_mean_decision_time * 1000.0:.2f} ms"
        screen.blit(font_row.render(b_dt_str, True, COLOR_TEXT_WHITE), (70, y))

        y += 26
        note_tel = "• Decision timing measured across live match actions • Algorithm budgets strictly held constant"
        screen.blit(font_row.render(note_tel, True, COLOR_TEXT_MUTED), (70, y))


# Retain backwards compatibility for any tests or imports referencing TournamentInfoScene
TournamentInfoScene = TournamentScene
