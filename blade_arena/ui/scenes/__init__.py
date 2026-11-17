"""UI scenes package for BLADE ARENA."""

from blade_arena.ui.scenes.base import Scene
from blade_arena.ui.scenes.battle import BattleScene
from blade_arena.ui.scenes.main_menu import MainMenuScene
from blade_arena.ui.scenes.result import ResultScene
from blade_arena.ui.scenes.setup import MatchSetupScene
from blade_arena.ui.scenes.settings import SettingsScene
from blade_arena.ui.scenes.tournament import TournamentInfoScene, TournamentScene

__all__ = [
    "Scene",
    "MainMenuScene",
    "MatchSetupScene",
    "BattleScene",
    "ResultScene",
    "TournamentInfoScene",
    "TournamentScene",
    "SettingsScene",
]
