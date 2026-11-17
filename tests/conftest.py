"""Pytest test suite configuration.

Ensures headless SDL drivers are set by default during automated test execution.
"""

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
