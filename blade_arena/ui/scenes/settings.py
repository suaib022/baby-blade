"""Settings and Environment Information scene for BLADE ARENA."""

from __future__ import annotations

from typing import Optional

import pygame

from blade_arena.ui.scenes.base import Scene
from blade_arena.ui.theme import (
    COLOR_BG,
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


class SettingsScene(Scene):
    """Configuration, display parameters, and engine environment diagnostics."""

    def __init__(self) -> None:
        self.btn_back = Button(
            rect=pygame.Rect(SCREEN_WIDTH // 2 - 100, 520, 200, 46),
            text="Back to Menu",
            shortcut_text="[ESC]",
            shortcut_key=pygame.K_ESCAPE,
            font_size=16,
        )

    def handle_event(self, event: pygame.event.Event) -> Optional[Scene]:
        """Handle navigation input."""
        if self.btn_back.handle_event(event):
            from blade_arena.ui.scenes.main_menu import MainMenuScene

            return MainMenuScene()
        return None

    def update(self, dt: float) -> Optional[Scene]:
        """Animation update."""
        return None

    def render(self, screen: pygame.Surface) -> None:
        """Render settings and diagnostics."""
        screen.fill(COLOR_BG)

        center_x = SCREEN_WIDTH // 2

        # Title
        font_t = get_font(32, bold=True)
        title_surf = font_t.render("ENGINE SETTINGS & SYSTEM INFO", True, COLOR_TEXT_WHITE)
        screen.blit(title_surf, title_surf.get_rect(center=(center_x, 50)))

        # Panel
        panel_rect = pygame.Rect(center_x - 340, 110, 680, 370)
        Panel(panel_rect, title="DISPLAY & RUNTIME CONFIGURATION").draw(screen)

        font_label = get_font(15, bold=False)
        font_val = get_font(15, bold=True)

        rows = [
            ("Display Resolution", f"{SCREEN_WIDTH} x {SCREEN_HEIGHT} (Fixed 2D Viewport)"),
            ("Target Framerate", "60 FPS (V-Sync Capped)"),
            ("Rendering Engine", "Pygame Community Edition (pygame-ce 2.5.8)"),
            ("Simulation Architecture", "Synchronous Deterministic Rules Engine"),
            ("AI Decision Models", "Ironclad (Minimax) & Cyclone (MCTS)"),
            ("Fuzzy Danger Inference", "Mamdani 4-Rule Mamdani Defuzzifier"),
            ("Stadium Variations", "Classic Dish, Ice Rink (1.25x), Steep Bowl (Drift)"),
            ("Logical Step Budget", "3.0s / Round (40 Rounds / 120.0s Limit)"),
            ("Coordinate System", "Cartesian (Center (0,0), Radius 10.0m -> 6.0m)"),
        ]

        y = 160
        for label, val in rows:
            screen.blit(font_label.render(label + ":", True, COLOR_TEXT_SUBTITLE), (panel_rect.x + 35, y))
            screen.blit(font_val.render(val, True, COLOR_TEXT_WHITE), (panel_rect.x + 250, y))
            y += 30

        # Back Button
        self.btn_back.draw(screen)
