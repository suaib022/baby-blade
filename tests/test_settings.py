"""Unit tests for BLADE ARENA configuration settings."""

import pytest

from blade_arena import settings
from blade_arena.settings import DEFAULT_SETTINGS, Settings


def test_window_width_and_height_are_positive_integers() -> None:
    """Verify default window dimensions are strictly positive integers."""
    assert isinstance(settings.WINDOW_WIDTH, int)
    assert isinstance(settings.WINDOW_HEIGHT, int)
    assert settings.WINDOW_WIDTH > 0
    assert settings.WINDOW_HEIGHT > 0

    assert isinstance(DEFAULT_SETTINGS.window_width, int)
    assert isinstance(DEFAULT_SETTINGS.window_height, int)
    assert DEFAULT_SETTINGS.window_width > 0
    assert DEFAULT_SETTINGS.window_height > 0


def test_target_fps_is_positive_integer() -> None:
    """Verify target frames per second is a strictly positive integer."""
    assert isinstance(settings.TARGET_FPS, int)
    assert settings.TARGET_FPS > 0

    assert isinstance(DEFAULT_SETTINGS.target_fps, int)
    assert DEFAULT_SETTINGS.target_fps > 0


def test_window_title_is_non_empty_string() -> None:
    """Verify window title matches project requirements."""
    assert isinstance(settings.WINDOW_TITLE, str)
    assert settings.WINDOW_TITLE == "BLADE ARENA"
    assert DEFAULT_SETTINGS.window_title == "BLADE ARENA"


def test_color_palettes_are_valid_rgb() -> None:
    """Verify color configurations are valid RGB tuples."""
    colors = [
        settings.BG_COLOR,
        settings.TEXT_COLOR,
        settings.SUBTITLE_COLOR,
        settings.BADGE_COLOR,
        settings.INSTRUCTION_COLOR,
    ]
    for color in colors:
        assert isinstance(color, tuple)
        assert len(color) == 3
        for channel in color:
            assert isinstance(channel, int)
            assert 0 <= channel <= 255


def test_settings_validation_rejects_non_positive_values() -> None:
    """Verify Settings rejects invalid dimensions or frame rates."""
    with pytest.raises(ValueError, match="window_width must be positive"):
        Settings(window_width=0)

    with pytest.raises(ValueError, match="window_height must be positive"):
        Settings(window_height=-10)

    with pytest.raises(ValueError, match="target_fps must be positive"):
        Settings(target_fps=0)
