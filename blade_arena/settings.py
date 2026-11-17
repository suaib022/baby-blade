"""Centralized configuration settings for BLADE ARENA.

Provides default constants and a typed Settings configuration object.
Does not import Pygame or initialize any resources.
"""

from dataclasses import dataclass
from typing import Tuple

# Type alias for RGB color representation
Color = Tuple[int, int, int]

# Window and display settings
WINDOW_TITLE: str = "BLADE ARENA"
WINDOW_WIDTH: int = 960
WINDOW_HEIGHT: int = 640
TARGET_FPS: int = 60

# Visual theme (high-contrast dark palette)
BG_COLOR: Color = (15, 18, 28)
TEXT_COLOR: Color = (240, 243, 246)
SUBTITLE_COLOR: Color = (160, 175, 195)
BADGE_COLOR: Color = (72, 187, 120)
INSTRUCTION_COLOR: Color = (180, 190, 205)


@dataclass(frozen=True)
class Settings:
    """Immutable application configuration."""

    window_title: str = WINDOW_TITLE
    window_width: int = WINDOW_WIDTH
    window_height: int = WINDOW_HEIGHT
    target_fps: int = TARGET_FPS
    bg_color: Color = BG_COLOR
    text_color: Color = TEXT_COLOR
    subtitle_color: Color = SUBTITLE_COLOR
    badge_color: Color = BADGE_COLOR
    instruction_color: Color = INSTRUCTION_COLOR

    def __post_init__(self) -> None:
        if self.window_width <= 0:
            raise ValueError(f"window_width must be positive, got {self.window_width}")
        if self.window_height <= 0:
            raise ValueError(f"window_height must be positive, got {self.window_height}")
        if self.target_fps <= 0:
            raise ValueError(f"target_fps must be positive, got {self.target_fps}")


DEFAULT_SETTINGS = Settings()
