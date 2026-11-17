"""Reusable UI widgets for BLADE ARENA.

Provides accessible, modular GUI components built directly on Pygame surfaces:
- Button: Clickable, keyboard-shortcut-enabled, with normal/hover/pressed/disabled states and legality tooltips.
- ProgressBar: Visual bar for Energy, Stability, and Timers.
- Panel: Framed container with optional header bar.
- ToggleGroup: Radio-style selector for match options.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Tuple

import pygame

from blade_arena.ui.theme import (
    BUTTON_STYLE_ACTIVE,
    BUTTON_STYLE_DISABLED,
    BUTTON_STYLE_HOVER,
    BUTTON_STYLE_NORMAL,
    COLOR_PANEL_BG,
    COLOR_PANEL_BORDER,
    COLOR_PANEL_HEADER,
    COLOR_TEXT_GOLD,
    COLOR_TEXT_MUTED,
    COLOR_TEXT_SUBTITLE,
    COLOR_TEXT_WHITE,
    get_font,
)


class Button:
    """Interactive button supporting mouse clicks, hover, hotkeys, and disabled reasons."""

    def __init__(
        self,
        rect: pygame.Rect,
        text: str,
        shortcut_text: Optional[str] = None,
        shortcut_key: Optional[int] = None,
        enabled: bool = True,
        disabled_reason: Optional[str] = None,
        callback: Optional[Callable[[], None]] = None,
        font_size: int = 18,
        custom_bg: Optional[Tuple[int, int, int]] = None,
        custom_border: Optional[Tuple[int, int, int]] = None,
    ) -> None:
        self.rect: pygame.Rect = pygame.Rect(rect)
        self.text: str = text
        self.shortcut_text: Optional[str] = shortcut_text
        self.shortcut_key: Optional[int] = shortcut_key
        self.enabled: bool = enabled
        self.disabled_reason: Optional[str] = disabled_reason
        self.callback: Optional[Callable[[], None]] = callback
        self.font_size: int = font_size
        self.custom_bg: Optional[Tuple[int, int, int]] = custom_bg
        self.custom_border: Optional[Tuple[int, int, int]] = custom_border

        self.hovered: bool = False
        self.pressed: bool = False

    def handle_event(self, event: pygame.event.Event) -> bool:
        """Process an input event.

        Returns:
            True if the button was activated (click or hotkey), False otherwise.
        """
        if event.type == pygame.MOUSEMOTION:
            self.hovered = self.rect.collidepoint(event.pos)
            return False

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.hovered and self.enabled:
                self.pressed = True
                return False

        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            was_pressed = self.pressed
            self.pressed = False
            if (was_pressed or self.rect.collidepoint(event.pos)) and self.enabled:
                if self.rect.collidepoint(event.pos):
                    if self.callback is not None:
                        self.callback()
                    return True
            return False

        if event.type == pygame.KEYDOWN:
            if (
                self.enabled
                and self.shortcut_key is not None
                and event.key == self.shortcut_key
            ):
                if self.callback is not None:
                    self.callback()
                return True

        return False

    def draw(self, screen: pygame.Surface) -> None:
        """Render the button to the target surface."""
        # Determine visual style
        if not self.enabled:
            style = BUTTON_STYLE_DISABLED
        elif self.pressed:
            style = BUTTON_STYLE_ACTIVE
        elif self.hovered:
            style = BUTTON_STYLE_HOVER
        else:
            style = BUTTON_STYLE_NORMAL

        bg_color = self.custom_bg if (self.custom_bg and self.enabled) else style["bg"]
        border_color = (
            self.custom_border if (self.custom_border and self.enabled) else style["border"]
        )

        # Draw button box
        pygame.draw.rect(screen, bg_color, self.rect, border_radius=4)
        pygame.draw.rect(screen, border_color, self.rect, width=2, border_radius=4)

        # Draw text + shortcut
        font = get_font(self.font_size, bold=True)
        text_surf = font.render(self.text, True, style["text"])

        if self.shortcut_text:
            sc_font = get_font(max(12, self.font_size - 4), bold=False)
            sc_color = COLOR_TEXT_GOLD if self.enabled else COLOR_TEXT_MUTED
            sc_surf = sc_font.render(self.shortcut_text, True, sc_color)
            total_w = text_surf.get_width() + sc_surf.get_width() + 8
            start_x = self.rect.centerx - total_w // 2

            text_rect = text_surf.get_rect(
                midleft=(start_x, self.rect.centery - (4 if self.disabled_reason else 0))
            )
            sc_rect = sc_surf.get_rect(
                midleft=(
                    text_rect.right + 8,
                    self.rect.centery - (4 if self.disabled_reason else 0),
                )
            )
            screen.blit(text_surf, text_rect)
            screen.blit(sc_surf, sc_rect)
        else:
            text_rect = text_surf.get_rect(
                center=(
                    self.rect.centerx,
                    self.rect.centery - (5 if self.disabled_reason else 0),
                )
            )
            screen.blit(text_surf, text_rect)

        # Render disabled reason if disabled and reason supplied
        if not self.enabled and self.disabled_reason:
            reason_font = get_font(12, bold=False)
            reason_surf = reason_font.render(
                self.disabled_reason[:36], True, (210, 80, 80)
            )
            reason_rect = reason_surf.get_rect(
                center=(self.rect.centerx, self.rect.bottom - 10)
            )
            screen.blit(reason_surf, reason_rect)


class ProgressBar:
    """Resource bar displaying numeric and proportional gauge data."""

    def __init__(
        self,
        rect: pygame.Rect,
        current_value: float,
        max_value: float,
        fill_color: Tuple[int, int, int],
        bg_color: Tuple[int, int, int] = (20, 24, 34),
        border_color: Tuple[int, int, int] = (45, 55, 80),
        text_override: Optional[str] = None,
        font_size: int = 14,
    ) -> None:
        self.rect: pygame.Rect = pygame.Rect(rect)
        self.current_value: float = current_value
        self.max_value: float = max(max_value, 0.001)
        self.fill_color: Tuple[int, int, int] = fill_color
        self.bg_color: Tuple[int, int, int] = bg_color
        self.border_color: Tuple[int, int, int] = border_color
        self.text_override: Optional[str] = text_override
        self.font_size: int = font_size

    def set_values(
        self, current: float, maximum: float, text_override: Optional[str] = None
    ) -> None:
        """Update bar values."""
        self.current_value = current
        self.max_value = max(maximum, 0.001)
        if text_override is not None:
            self.text_override = text_override

    def draw(self, screen: pygame.Surface) -> None:
        """Render the progress bar."""
        # Background
        pygame.draw.rect(screen, self.bg_color, self.rect, border_radius=3)

        # Fill
        ratio = max(0.0, min(1.0, self.current_value / self.max_value))
        if ratio > 0.0:
            fill_width = int(self.rect.width * ratio)
            fill_rect = pygame.Rect(
                self.rect.x, self.rect.y, fill_width, self.rect.height
            )
            pygame.draw.rect(screen, self.fill_color, fill_rect, border_radius=3)

        # Border
        pygame.draw.rect(screen, self.border_color, self.rect, width=1, border_radius=3)

        # Overlay text
        font = get_font(self.font_size, bold=True)
        display_str = (
            self.text_override
            if self.text_override is not None
            else f"{int(self.current_value)} / {int(self.max_value)}"
        )
        text_surf = font.render(display_str, True, COLOR_TEXT_WHITE)
        text_rect = text_surf.get_rect(center=self.rect.center)
        screen.blit(text_surf, text_rect)


class Panel:
    """Structured container panel with optional title banner."""

    def __init__(
        self,
        rect: pygame.Rect,
        title: Optional[str] = None,
        bg_color: Tuple[int, int, int] = COLOR_PANEL_BG,
        border_color: Tuple[int, int, int] = COLOR_PANEL_BORDER,
        header_color: Tuple[int, int, int] = COLOR_PANEL_HEADER,
    ) -> None:
        self.rect: pygame.Rect = pygame.Rect(rect)
        self.title: Optional[str] = title
        self.bg_color: Tuple[int, int, int] = bg_color
        self.border_color: Tuple[int, int, int] = border_color
        self.header_color: Tuple[int, int, int] = header_color

    def draw(self, screen: pygame.Surface) -> None:
        """Render the panel."""
        pygame.draw.rect(screen, self.bg_color, self.rect, border_radius=6)
        pygame.draw.rect(screen, self.border_color, self.rect, width=2, border_radius=6)

        if self.title:
            header_rect = pygame.Rect(
                self.rect.x, self.rect.y, self.rect.width, 28
            )
            pygame.draw.rect(
                screen,
                self.header_color,
                header_rect,
                border_top_left_radius=6,
                border_top_right_radius=6,
            )
            pygame.draw.line(
                screen,
                self.border_color,
                (self.rect.x, self.rect.y + 28),
                (self.rect.right, self.rect.y + 28),
                width=1,
            )
            font = get_font(15, bold=True)
            text_surf = font.render(self.title, True, COLOR_TEXT_WHITE)
            text_rect = text_surf.get_rect(midleft=(self.rect.x + 12, self.rect.y + 14))
            screen.blit(text_surf, text_rect)


class ToggleGroup:
    """Radio-button style selection group for matching choices."""

    def __init__(
        self,
        rect: pygame.Rect,
        options: List[Tuple[str, Any]],
        initial_value: Any,
        on_change: Optional[Callable[[Any], None]] = None,
        horizontal: bool = True,
    ) -> None:
        self.rect: pygame.Rect = pygame.Rect(rect)
        self.options: List[Tuple[str, Any]] = options
        self.selected_value: Any = initial_value
        self.on_change: Optional[Callable[[Any], None]] = on_change
        self.horizontal: bool = horizontal
        self._buttons: List[Tuple[pygame.Rect, str, Any]] = []
        self._layout()

    def _layout(self) -> None:
        """Compute child button geometry."""
        self._buttons.clear()
        n = len(self.options)
        if n == 0:
            return

        if self.horizontal:
            spacing = 4
            btn_w = (self.rect.width - spacing * (n - 1)) // n
            for i, (label, val) in enumerate(self.options):
                x = self.rect.x + i * (btn_w + spacing)
                btn_rect = pygame.Rect(x, self.rect.y, btn_w, self.rect.height)
                self._buttons.append((btn_rect, label, val))
        else:
            spacing = 4
            btn_h = (self.rect.height - spacing * (n - 1)) // n
            for i, (label, val) in enumerate(self.options):
                y = self.rect.y + i * (btn_h + spacing)
                btn_rect = pygame.Rect(self.rect.x, y, self.rect.width, btn_h)
                self._buttons.append((btn_rect, label, val))

    def handle_event(self, event: pygame.event.Event) -> bool:
        """Handle clicks on toggle options."""
        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            for btn_rect, _label, val in self._buttons:
                if btn_rect.collidepoint(event.pos):
                    if self.selected_value != val:
                        self.selected_value = val
                        if self.on_change is not None:
                            self.on_change(val)
                        return True
        return False

    def draw(self, screen: pygame.Surface) -> None:
        """Draw the toggle group buttons."""
        font = get_font(14, bold=True)
        for btn_rect, label, val in self._buttons:
            is_active = val == self.selected_value
            if is_active:
                bg = (40, 75, 120)
                border = (80, 160, 240)
                text_col = COLOR_TEXT_WHITE
            else:
                bg = (24, 30, 44)
                border = (45, 55, 75)
                text_col = COLOR_TEXT_MUTED

            pygame.draw.rect(screen, bg, btn_rect, border_radius=4)
            pygame.draw.rect(screen, border, btn_rect, width=2 if is_active else 1, border_radius=4)

            text_surf = font.render(label, True, text_col)
            text_rect = text_surf.get_rect(center=btn_rect.center)
            screen.blit(text_surf, text_rect)
