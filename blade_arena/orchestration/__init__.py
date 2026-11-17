"""Game mode and headless orchestration for BLADE ARENA.

Coordinates match execution for:
- Human vs AI
- AI vs AI
- Headless batch evaluation with alternating sides and reproducible seeds
"""

from blade_arena.orchestration.batch_runner import (
    BatchMatchResult,
    BatchSummary,
    TournamentBatchRunner,
    export_tournament_results,
    run_headless_batch,
)
from blade_arena.orchestration.participants import (
    AgentType,
    AIParticipant,
    HumanActionRequiredError,
    HumanParticipant,
    IllegalParticipantActionError,
    Participant,
    ParticipantError,
    create_ai_participant,
)
from blade_arena.orchestration.session import (
    GameMode,
    IterationGuardError,
    MatchSession,
    OrchestrationError,
    SessionConfig,
    StepRecord,
)

__all__ = [
    "AgentType",
    "AIParticipant",
    "BatchMatchResult",
    "BatchSummary",
    "GameMode",
    "HumanActionRequiredError",
    "HumanParticipant",
    "IllegalParticipantActionError",
    "IterationGuardError",
    "MatchSession",
    "OrchestrationError",
    "Participant",
    "ParticipantError",
    "SessionConfig",
    "StepRecord",
    "TournamentBatchRunner",
    "create_ai_participant",
    "export_tournament_results",
    "run_headless_batch",
]
