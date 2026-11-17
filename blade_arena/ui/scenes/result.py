"""Match Result scene for BLADE ARENA.

Presents authoritative post-match outcome: winner or draw, finish reason,
points breakdown (if applicable), round statistics, and navigation options.
"""

from __future__ import annotations

from typing import List, Optional

import pygame

from blade_arena.game.models import FinishReason, MatchResult, MatchState
from blade_arena.orchestration.session import MatchSession
from blade_arena.ui.scenes.base import Scene
from blade_arena.ui.theme import (
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
from blade_arena.ui.widgets import Button, Panel


class ResultScene(Scene):
    """Post-match debriefing and outcome inspection screen."""

    def __init__(self, session: MatchSession) -> None:
        self.session: MatchSession = session
        self.state: MatchState = session.state
        self.result: Optional[MatchResult] = session.state.result

        self.buttons: List[Button] = []
        self._init_buttons()

    def _init_buttons(self) -> None:
        """Create navigation buttons."""
        center_x = SCREEN_WIDTH // 2
        btn_y = 540

        self.btn_play_again = Button(
            rect=pygame.Rect(center_x - 280, btn_y, 160, 46),
            text="Play Again",
            shortcut_text="[R]",
            shortcut_key=pygame.K_r,
            font_size=16,
            custom_bg=(30, 90, 60),
            custom_border=(60, 180, 100),
        )
        self.btn_setup = Button(
            rect=pygame.Rect(center_x - 90, btn_y, 180, 46),
            text="Match Setup",
            shortcut_text="[S]",
            shortcut_key=pygame.K_s,
            font_size=16,
        )
        self.btn_menu = Button(
            rect=pygame.Rect(center_x + 120, btn_y, 160, 46),
            text="Main Menu",
            shortcut_text="[ESC]",
            shortcut_key=pygame.K_ESCAPE,
            font_size=16,
        )
        self.buttons.extend([self.btn_play_again, self.btn_setup, self.btn_menu])

    def handle_event(self, event: pygame.event.Event) -> Optional[Scene]:
        """Handle navigation inputs."""
        if self.btn_play_again.handle_event(event):
            from blade_arena.ui.scenes.battle import BattleScene

            self.session.restart()
            return BattleScene(session=self.session)

        if self.btn_setup.handle_event(event):
            from blade_arena.ui.scenes.setup import MatchSetupScene

            return MatchSetupScene(initial_mode=self.session.mode)

        if self.btn_menu.handle_event(event):
            from blade_arena.ui.scenes.main_menu import MainMenuScene

            return MainMenuScene()

        return None

    def update(self, dt: float) -> Optional[Scene]:
        """Animation update."""
        return None

    def render(self, screen: pygame.Surface) -> None:
        """Render victory debriefing."""
        screen.fill(COLOR_BG)

        center_x = SCREEN_WIDTH // 2

        # 1. Title Banner
        font_hdr = get_font(32, bold=True)
        hdr_surf = font_hdr.render("MATCH CONCLUDED", True, COLOR_TEXT_WHITE)
        screen.blit(hdr_surf, hdr_surf.get_rect(center=(center_x, 45)))

        # 2. Main Outcome Announcement
        if self.result is not None and self.result.winner is not None:
            if self.result.winner == "player_1":
                win_text = f"VICTORY: {self.session.participant_1.name.upper()}"
                win_color = COLOR_P1_PRIMARY
            else:
                win_text = f"VICTORY: {self.session.participant_2.name.upper()}"
                win_color = COLOR_P2_PRIMARY
        else:
            win_text = "MATCH DRAW (SIMULTANEOUS ELIMINATION)"
            win_color = COLOR_TEXT_GOLD

        font_win = get_font(30, bold=True)
        win_surf = font_win.render(win_text, True, win_color)
        screen.blit(win_surf, win_surf.get_rect(center=(center_x, 100)))

        # 3. Finish Reason Badge
        reason_name = (
            self.result.reason.name.replace("_", " ").title()
            if self.result
            else "Points Decision"
        )
        font_sub = get_font(18, bold=False)
        sub_surf = font_sub.render(f"Finish Reason: {reason_name}", True, COLOR_TEXT_SUBTITLE)
        screen.blit(sub_surf, sub_surf.get_rect(center=(center_x, 140)))

        # 4. Debriefing Panel
        panel_rect = pygame.Rect(center_x - 340, 180, 680, 320)
        Panel(panel_rect, title="MATCH STATISTICS & FINAL AUDIT").draw(screen)

        font_stat = get_font(15, bold=False)
        font_bld = get_font(15, bold=True)

        y = 230
        line_spacing = 30

        # Rounds & Logical Time
        screen.blit(font_stat.render("Completed Rounds:", True, COLOR_TEXT_SUBTITLE), (panel_rect.x + 30, y))
        screen.blit(font_bld.render(f"{self.state.completed_rounds} / 40", True, COLOR_TEXT_WHITE), (panel_rect.x + 220, y))

        screen.blit(font_stat.render("Logical Match Time:", True, COLOR_TEXT_SUBTITLE), (panel_rect.x + 380, y))
        screen.blit(font_bld.render(f"{self.state.elapsed_game_time:.1f}s / 120.0s", True, COLOR_TEXT_WHITE), (panel_rect.x + 550, y))

        y += line_spacing

        # Stadium Environment
        stadium_name = self.state.stadium.stadium_type.name.replace("_", " ").title()
        screen.blit(font_stat.render("Stadium Arena:", True, COLOR_TEXT_SUBTITLE), (panel_rect.x + 30, y))
        screen.blit(font_bld.render(f"{stadium_name} (final radius: {self.state.stadium.radius:.1f}m)", True, COLOR_TEXT_WHITE), (panel_rect.x + 220, y))

        y += line_spacing + 5
        pygame.draw.line(screen, COLOR_PANEL_BORDER, (panel_rect.x + 20, y), (panel_rect.right - 20, y), 1)
        y += 15

        # Player 1 Final Stats
        p1_b = self.state.player_1_blade
        screen.blit(font_bld.render(f"P1: {self.session.participant_1.name} ({p1_b.blade_type.name})", True, COLOR_P1_PRIMARY), (panel_rect.x + 30, y))
        y += 24
        p1_stats = f"Stability: {p1_b.current_stability:.1f} / {p1_b.max_stability:.0f}   |   Energy: {p1_b.current_energy:.1f} / {p1_b.max_energy:.0f}"
        screen.blit(font_stat.render(p1_stats, True, COLOR_TEXT_WHITE), (panel_rect.x + 40, y))

        y += line_spacing

        # Player 2 Final Stats
        p2_b = self.state.player_2_blade
        screen.blit(font_bld.render(f"P2: {self.session.participant_2.name} ({p2_b.blade_type.name})", True, COLOR_P2_PRIMARY), (panel_rect.x + 30, y))
        y += 24
        p2_stats = f"Stability: {p2_b.current_stability:.1f} / {p2_b.max_stability:.0f}   |   Energy: {p2_b.current_energy:.1f} / {p2_b.max_energy:.0f}"
        screen.blit(font_stat.render(p2_stats, True, COLOR_TEXT_WHITE), (panel_rect.x + 40, y))

        y += line_spacing

        # Points Breakdown if applicable
        if self.result is not None and self.result.scores is not None:
            p1_pts, p2_pts = self.result.scores
            pts_str = f"Points Score Breakdown:   P1: {p1_pts:.1f} pts   vs   P2: {p2_pts:.1f} pts"
            screen.blit(font_bld.render(pts_str, True, COLOR_TEXT_GOLD), (panel_rect.x + 30, y))

        # 5. Buttons
        for b in self.buttons:
            b.draw(screen)
