"""Base Scene protocol and abstract definition for BLADE ARENA UI."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

import pygame


class Scene(ABC):
    """Abstract base class for all UI screens/views."""

    def on_enter(self) -> None:
        """Called when this scene becomes the active scene."""
        pass

    @abstractmethod
    def handle_event(self, event: pygame.event.Event) -> Optional[Scene]:
        """Process a single Pygame input event.

        Args:
            event: Input event to handle.

        Returns:
            A new Scene to transition to, or None to remain on this scene.
        """
        ...

    @abstractmethod
    def update(self, dt: float) -> Optional[Scene]:
        """Update scene logic and animations.

        Args:
            dt: Delta time in seconds since previous frame.

        Returns:
            A new Scene to transition to, or None to remain on this scene.
        """
        ...

    @abstractmethod
    def render(self, screen: pygame.Surface) -> None:
        """Render the scene to the display surface.

        Args:
            screen: Target pygame Surface.
        """
        ...
