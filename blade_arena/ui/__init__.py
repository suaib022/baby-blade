"""Pygame User Interface and visual presentation for BLADE ARENA."""

from blade_arena.ui.renderer import ArenaRenderer, BladeRenderer, CombatVFX
from blade_arena.ui.theme import (
    ARCHETYPE_COLORS,
    COLOR_BG,
    COLOR_P1_PRIMARY,
    COLOR_P2_PRIMARY,
    COLOR_PANEL_BG,
    COLOR_PANEL_BORDER,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
    get_font,
)
from blade_arena.ui.widgets import Button, Panel, ProgressBar, ToggleGroup

__all__ = [
    "ArenaRenderer",
    "BladeRenderer",
    "CombatVFX",
    "Button",
    "Panel",
    "ProgressBar",
    "ToggleGroup",
    "get_font",
    "SCREEN_WIDTH",
    "SCREEN_HEIGHT",
    "COLOR_BG",
    "COLOR_PANEL_BG",
    "COLOR_PANEL_BORDER",
    "COLOR_P1_PRIMARY",
    "COLOR_P2_PRIMARY",
    "ARCHETYPE_COLORS",
]
