"""Main Menu scene for BLADE ARENA."""

from __future__ import annotations

from typing import List, Optional

import pygame

from blade_arena.orchestration.session import GameMode
from blade_arena.ui.scenes.base import Scene
from blade_arena.ui.theme import (
    COLOR_BG,
    COLOR_P1_PRIMARY,
    COLOR_TEXT_GOLD,
    COLOR_TEXT_MUTED,
    COLOR_TEXT_SUBTITLE,
    COLOR_TEXT_WHITE,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
    get_font,
)
from blade_arena.ui.widgets import Button


class MainMenuScene(Scene):
    """Primary navigation menu for BLADE ARENA."""

    def __init__(self) -> None:
        self.buttons: List[Button] = []
        self._init_buttons()

    def _init_buttons(self) -> None:
        """Create menu buttons positioned centrally."""
        center_x = SCREEN_WIDTH // 2
        btn_width = 320
        btn_height = 46
        start_y = 230
        spacing = 16

        items = [
            ("Human vs AI", "[1]", pygame.K_1),
            ("AI vs AI", "[2]", pygame.K_2),
            ("Tournament", "[3]", pygame.K_3),
            ("Settings", "[4]", pygame.K_4),
            ("Quit", "[5 / ESC]", pygame.K_5),
        ]

        self.buttons.clear()
        for i, (text, sc_text, sc_key) in enumerate(items):
            rect = pygame.Rect(
                center_x - btn_width // 2,
                start_y + i * (btn_height + spacing),
                btn_width,
                btn_height,
            )
            btn = Button(
                rect=rect,
                text=text,
                shortcut_text=sc_text,
                shortcut_key=sc_key,
                font_size=18,
            )
            self.buttons.append(btn)

    def handle_event(self, event: pygame.event.Event) -> Optional[Scene]:
        """Handle menu navigation and button activations."""
        # ESC on main menu triggers quit
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            pygame.event.post(pygame.event.Event(pygame.QUIT))
            return None

        # Check button activations
        for i, btn in enumerate(self.buttons):
            if btn.handle_event(event):
                if i == 0:
                    from blade_arena.ui.scenes.setup import MatchSetupScene

                    return MatchSetupScene(initial_mode=GameMode.HUMAN_VS_AI)
                elif i == 1:
                    from blade_arena.ui.scenes.setup import MatchSetupScene

                    return MatchSetupScene(initial_mode=GameMode.AI_VS_AI)
                elif i == 2:
                    from blade_arena.ui.scenes.tournament import TournamentInfoScene

                    return TournamentInfoScene()
                elif i == 3:
                    from blade_arena.ui.scenes.settings import SettingsScene

                    return SettingsScene()
                elif i == 4:
                    pygame.event.post(pygame.event.Event(pygame.QUIT))
                    return None

        return None

    def update(self, dt: float) -> Optional[Scene]:
        """Menu animation update."""
        return None

    def render(self, screen: pygame.Surface) -> None:
        """Render the main menu interface."""
        screen.fill(COLOR_BG)

        center_x = SCREEN_WIDTH // 2

        # 1. Main Title
        title_font = get_font(52, bold=True)
        title_surf = title_font.render("BLADE ARENA", True, COLOR_P1_PRIMARY)
        title_rect = title_surf.get_rect(center=(center_x, 90))
        screen.blit(title_surf, title_rect)

        # 2. Subtitle
        sub_font = get_font(22, bold=False)
        sub_surf = sub_font.render(
            "AI-Powered 2D Spinning-Top Battle Stadium", True, COLOR_TEXT_SUBTITLE
        )
        sub_rect = sub_surf.get_rect(center=(center_x, 140))
        screen.blit(sub_surf, sub_rect)

        # 3. Badge
        badge_font = get_font(14, bold=True)
        badge_surf = badge_font.render(
            "Simultaneous Combat Engine · Ironclad Minimax · Cyclone MCTS",
            True,
            COLOR_TEXT_GOLD,
        )
        badge_rect = badge_surf.get_rect(center=(center_x, 175))
        screen.blit(badge_surf, badge_rect)

        # 4. Buttons
        for btn in self.buttons:
            btn.draw(screen)

        # 5. Footer info
        foot_font = get_font(13, bold=False)
        foot_surf = foot_font.render(
            "Use Number Keys 1–5 or Mouse to Select · ESC to Quit", True, COLOR_TEXT_MUTED
        )
        foot_rect = foot_surf.get_rect(center=(center_x, SCREEN_HEIGHT - 35))
        screen.blit(foot_surf, foot_rect)
