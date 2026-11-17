"""AI decision engines and algorithms for BLADE ARENA.

Provides approved classical game-AI implementations:
- Ironclad (Module 11): Minimax search with iterative deepening and simultaneous-action conservatism.
- Cyclone (Module 12): Monte Carlo Tree Search (MCTS) with selection, expansion, rollouts, and backpropagation.
"""

from blade_arena.ai.cyclone import (
    DIFFICULTY_ITERATIONS,
    CycloneAgent,
    CycloneConfig,
    CycloneDecision,
    CycloneDifficulty,
    choose_action as choose_cyclone_action,
    decide as decide_cyclone,
)
from blade_arena.ai.ironclad import (
    DIFFICULTY_DEPTHS,
    IroncladAgent,
    IroncladConfig,
    IroncladDecision,
    IroncladDifficulty,
    choose_action as choose_ironclad_action,
    decide as decide_ironclad,
)

__all__ = [
    "DIFFICULTY_DEPTHS",
    "DIFFICULTY_ITERATIONS",
    "CycloneAgent",
    "CycloneConfig",
    "CycloneDecision",
    "CycloneDifficulty",
    "IroncladAgent",
    "IroncladConfig",
    "IroncladDecision",
    "IroncladDifficulty",
    "choose_cyclone_action",
    "choose_ironclad_action",
    "decide_cyclone",
    "decide_ironclad",
]
