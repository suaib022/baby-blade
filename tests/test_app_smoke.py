"""Automated tests for BLADE ARENA application shell and smoke execution."""

import os
import subprocess
import sys

import pygame
import pytest

from blade_arena.app import BladeArenaApp
from blade_arena.settings import DEFAULT_SETTINGS


def test_import_app_does_not_open_window() -> None:
    """Verify importing blade_arena.app does not initialize display or open a window."""
    code = (
        "import blade_arena.app\n"
        "import pygame\n"
        "assert not pygame.display.get_init(), 'Display was initialized on import'\n"
        "assert pygame.display.get_surface() is None, 'Display surface was created on import'\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        timeout=5,
    )
    assert result.returncode == 0, f"Import check failed: {result.stderr}"


def test_smoke_test_command_starts_and_exits() -> None:
    """Verify python main.py --smoke-test executes headlessly and exits with code 0."""
    result = subprocess.run(
        [sys.executable, "main.py", "--smoke-test"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0, f"Smoke test failed: {result.stderr}"


def test_smoke_test_custom_frames() -> None:
    """Verify smoke test honors explicit frame count and exits cleanly."""
    result = subprocess.run(
        [sys.executable, "main.py", "--smoke-test", "--frames", "15"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0, f"Frames smoke test failed: {result.stderr}"


def test_quit_event_handling_terminates_loop() -> None:
    """Verify a pygame.QUIT event stops the loop cleanly without hanging."""
    app = BladeArenaApp(settings=DEFAULT_SETTINGS, max_frames=300)
    app.setup()
    try:
        assert app.running is True
        # Post QUIT event to the event queue
        pygame.event.post(pygame.event.Event(pygame.QUIT))
        keep_running = app.handle_events()
        assert keep_running is False
        assert app.running is False
    finally:
        app.teardown()


def test_escape_key_exits_loop() -> None:
    """Verify pressing Escape (pygame.K_ESCAPE) stops the loop cleanly."""
    app = BladeArenaApp(settings=DEFAULT_SETTINGS, max_frames=300)
    app.setup()
    try:
        assert app.running is True
        # Post Escape keydown event
        pygame.event.post(
            pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE, mod=0, scancode=0)
        )
        keep_running = app.handle_events()
        assert keep_running is False
        assert app.running is False
    finally:
        app.teardown()


def test_app_run_with_quit_event_completes() -> None:
    """Verify app.run() with a queued QUIT event exits cleanly with code 0."""
    app = BladeArenaApp(settings=DEFAULT_SETTINGS, max_frames=300)
    # Mock setup to pre-seed the event queue before entering the loop
    original_setup = app.setup

    def setup_with_quit() -> None:
        original_setup()
        pygame.event.post(pygame.event.Event(pygame.QUIT))

    app.setup = setup_with_quit
    exit_code = app.run()
    assert exit_code == 0
    assert not pygame.get_init(), "Pygame was not cleaned up after run()"


def test_app_run_with_escape_key_completes() -> None:
    """Verify app.run() with a queued Escape event exits cleanly with code 0."""
    app = BladeArenaApp(settings=DEFAULT_SETTINGS, max_frames=300)
    original_setup = app.setup

    def setup_with_escape() -> None:
        original_setup()
        pygame.event.post(
            pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE, mod=0, scancode=0)
        )

    app.setup = setup_with_escape
    exit_code = app.run()
    assert exit_code == 0
    assert not pygame.get_init(), "Pygame was not cleaned up after run()"
