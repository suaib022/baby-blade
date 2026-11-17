"""Main application loop and UI scene host for BLADE ARENA.

Importing this module does not initialize Pygame or open a display window.
"""

from __future__ import annotations

import logging
from typing import Optional

import pygame

from blade_arena.settings import DEFAULT_SETTINGS, Settings
from blade_arena.ui.scenes.base import Scene
from blade_arena.ui.scenes.main_menu import MainMenuScene

logger = logging.getLogger(__name__)


class BladeArenaApp:
    """Manages the Pygame lifecycle, event processing, scene routing, and frame rendering."""

    def __init__(
        self,
        settings: Optional[Settings] = None,
        max_frames: Optional[int] = None,
        screenshot_path: Optional[str] = None,
        initial_scene: Optional[Scene] = None,
    ) -> None:
        self.settings: Settings = settings or DEFAULT_SETTINGS
        self.max_frames: Optional[int] = max_frames
        self.screenshot_path: Optional[str] = screenshot_path

        self.running: bool = False
        self.frame_count: int = 0
        self.screen: Optional[pygame.Surface] = None
        self.clock: Optional[pygame.time.Clock] = None

        # Scene management
        self.current_scene: Optional[Scene] = initial_scene

        # Retained text surfaces for backwards compatibility
        self._title_surface: Optional[pygame.Surface] = None
        self._title_rect: Optional[pygame.Rect] = None
        self._subtitle_surface: Optional[pygame.Surface] = None
        self._subtitle_rect: Optional[pygame.Rect] = None
        self._badge_surface: Optional[pygame.Surface] = None
        self._badge_rect: Optional[pygame.Rect] = None
        self._instruction_surface: Optional[pygame.Surface] = None
        self._instruction_rect: Optional[pygame.Rect] = None

    def setup(self) -> None:
        """Initialize Pygame subsystems, display window, and active scene."""
        pygame.init()
        pygame.font.init()

        self.screen = pygame.display.set_mode(
            (self.settings.window_width, self.settings.window_height)
        )
        pygame.display.set_caption(self.settings.window_title)
        self.clock = pygame.time.Clock()

        self._prepare_text_surfaces()

        if self.current_scene is None:
            self.current_scene = MainMenuScene()
        self.current_scene.on_enter()

        self.frame_count = 0
        self.running = True

    def _prepare_text_surfaces(self) -> None:
        """Pre-render legacy text elements for backwards compatibility."""
        center_x = self.settings.window_width // 2

        font_title = pygame.font.Font(None, 52)
        font_title.set_bold(True)
        self._title_surface = font_title.render(
            self.settings.window_title, True, self.settings.text_color
        )
        self._title_rect = self._title_surface.get_rect(center=(center_x, 220))

        font_sub = pygame.font.Font(None, 28)
        self._subtitle_surface = font_sub.render(
            "AI-Powered Spinning-Top Battle Stadium", True, self.settings.subtitle_color
        )
        self._subtitle_rect = self._subtitle_surface.get_rect(center=(center_x, 280))

        font_badge = pygame.font.Font(None, 24)
        self._badge_surface = font_badge.render(
            "Module 15: Pygame Interface", True, self.settings.badge_color
        )
        self._badge_rect = self._badge_surface.get_rect(center=(center_x, 340))

        font_instr = pygame.font.Font(None, 22)
        self._instruction_surface = font_instr.render(
            "Press ESC to quit", True, self.settings.instruction_color
        )
        self._instruction_rect = self._instruction_surface.get_rect(center=(center_x, 420))

    def handle_events(self) -> bool:
        """Drain the Pygame event queue and route to the active scene.

        Returns:
            True if the application should keep running, False if it should quit.
        """
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
                return False

            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                if isinstance(self.current_scene, MainMenuScene) or self.current_scene is None:
                    self.running = False
                    return False

            if self.current_scene is not None:
                next_scene = self.current_scene.handle_event(event)
                if next_scene is not None:
                    self.current_scene = next_scene
                    self.current_scene.on_enter()

        return self.running

    def update(self, dt: float) -> None:
        """Advance scene logic and check frame limits.

        Args:
            dt: Delta time in seconds since the previous frame.
        """
        self.frame_count += 1
        if self.max_frames is not None and self.frame_count >= self.max_frames:
            self.running = False
            return

        if self.current_scene is not None:
            next_scene = self.current_scene.update(dt)
            if next_scene is not None:
                self.current_scene = next_scene
                self.current_scene.on_enter()

    def render(self) -> None:
        """Draw the active scene onto the display surface."""
        if self.screen is None:
            return

        if self.current_scene is not None:
            self.current_scene.render(self.screen)
        else:
            self.screen.fill(self.settings.bg_color)
            if self._title_surface and self._title_rect:
                self.screen.blit(self._title_surface, self._title_rect)

        pygame.display.flip()

    def teardown(self) -> None:
        """Save optional screenshots and release all Pygame resources."""
        if self.screenshot_path and self.screen is not None:
            try:
                pygame.image.save(self.screen, self.screenshot_path)
            except Exception as exc:  # pragma: no cover
                logger.warning("Failed to save screenshot: %s", exc)

        if pygame.get_init():
            pygame.quit()

    def run(self) -> int:
        """Execute the main application loop.

        Returns:
            Process exit code (0 for clean termination).
        """
        try:
            self.setup()
            while self.running:
                dt = min(self.clock.tick(self.settings.target_fps) / 1000.0, 0.05)
                if not self.handle_events():
                    break
                self.update(dt)
                self.render()
            return 0
        finally:
            self.teardown()
