"""Visual styling, color palettes, typography, and theme definitions for BLADE ARENA UI.

Provides centralized font caching, high-contrast dark color palettes, danger level
mappings, and layout coordinates for 960x640 display resolution.
"""

from __future__ import annotations

from typing import Dict, Tuple

import pygame

# Color type alias
Color = Tuple[int, int, int]

# Window layout geometry
SCREEN_WIDTH: int = 960
SCREEN_HEIGHT: int = 640

# Base UI Palette
COLOR_BG: Color = (15, 18, 28)
COLOR_PANEL_BG: Color = (24, 29, 44)
COLOR_PANEL_BORDER: Color = (45, 55, 80)
COLOR_PANEL_HEADER: Color = (32, 38, 58)

# Typography Colors
COLOR_TEXT_WHITE: Color = (240, 243, 246)
COLOR_TEXT_SUBTITLE: Color = (160, 175, 195)
COLOR_TEXT_MUTED: Color = (110, 125, 145)
COLOR_TEXT_GOLD: Color = (250, 219, 20)

# Player Accents
COLOR_P1_PRIMARY: Color = (64, 169, 255)
COLOR_P1_DARK: Color = (20, 80, 140)
COLOR_P1_LIGHT: Color = (186, 231, 255)

COLOR_P2_PRIMARY: Color = (255, 77, 79)
COLOR_P2_DARK: Color = (168, 28, 38)
COLOR_P2_LIGHT: Color = (255, 204, 199)

# Archetype Theme Accents
ARCHETYPE_COLORS: Dict[str, Color] = {
    "BALANCED": (82, 196, 26),      # Green
    "ATTACKER": (250, 84, 28),      # Orange-Red
    "DEFENDER": (24, 144, 255),     # Blue
    "STAMINA": (250, 173, 20),      # Gold
}

# Stadium Surface Palettes
STADIUM_THEMES: Dict[str, Dict[str, Color]] = {
    "CLASSIC_DISH": {
        "fill": (22, 28, 42),
        "floor_ring": (30, 38, 56),
        "rim": (80, 105, 145),
        "accent": (72, 187, 120),
    },
    "ICE_RINK": {
        "fill": (18, 34, 52),
        "floor_ring": (28, 50, 75),
        "rim": (120, 200, 245),
        "accent": (100, 220, 255),
    },
    "STEEP_BOWL": {
        "fill": (30, 24, 20),
        "floor_ring": (48, 36, 28),
        "rim": (205, 115, 55),
        "accent": (250, 140, 60),
    },
}

# Danger Levels (Non-color-only text labels with accessible palette)
DANGER_THEMES: Dict[str, Dict[str, object]] = {
    "LOW": {"color": (82, 196, 26), "label": "LOW", "bg": (20, 45, 25)},
    "MEDIUM": {"color": (250, 173, 20), "label": "MED", "bg": (55, 42, 15)},
    "HIGH": {"color": (250, 84, 28), "label": "HIGH", "bg": (55, 25, 15)},
    "CRITICAL": {"color": (245, 34, 45), "label": "CRIT", "bg": (60, 15, 20)},
}

# Button State Styles
BUTTON_STYLE_NORMAL: Dict[str, Color] = {
    "bg": (35, 45, 68),
    "border": (65, 82, 118),
    "text": (240, 243, 246),
}
BUTTON_STYLE_HOVER: Dict[str, Color] = {
    "bg": (52, 68, 102),
    "border": (110, 140, 195),
    "text": (255, 255, 255),
}
BUTTON_STYLE_ACTIVE: Dict[str, Color] = {
    "bg": (25, 33, 50),
    "border": (50, 65, 95),
    "text": (200, 210, 225),
}
BUTTON_STYLE_DISABLED: Dict[str, Color] = {
    "bg": (20, 24, 34),
    "border": (35, 42, 56),
    "text": (85, 95, 112),
}

# Font cache to avoid redundant surface re-creation
_FONT_CACHE: Dict[Tuple[int, bool], pygame.font.Font] = {}


def clear_font_cache() -> None:
    """Clear cached font surfaces and instances."""
    _FONT_CACHE.clear()


def get_font(size: int, bold: bool = False) -> pygame.font.Font:
    """Retrieve or instantiate a cached system font at the requested size."""
    if not pygame.font.get_init():
        pygame.font.init()
        _FONT_CACHE.clear()

    key = (size, bold)
    font = _FONT_CACHE.get(key)
    if font is not None:
        try:
            font.get_height()
            return font
        except Exception:
            _FONT_CACHE.clear()

    try:
        # Prefer standard system sans-serif font
        font = pygame.font.SysFont("segoeui,helvetica,arial", size, bold=bold)
    except Exception:
        font = pygame.font.Font(None, size)
        if bold:
            font.set_bold(True)
    _FONT_CACHE[key] = font

    return _FONT_CACHE[key]
