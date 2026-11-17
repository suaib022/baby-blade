"""Participant abstraction and wrappers for BLADE ARENA match orchestration.

Provides a unified interface for both human decision-makers and AI agents:
- Participant protocol with choose_action(state, player_id).
- HumanParticipant for non-blocking caller-supplied input.
- AIParticipant wrapping Ironclad, Cyclone, or custom agent callables.
- Factory helpers for standard AI agents across difficulty profiles.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Callable, Optional, Protocol, Union, runtime_checkable

from blade_arena.ai.cyclone import CycloneAgent, CycloneConfig, CycloneDifficulty
from blade_arena.ai.ironclad import IroncladAgent, IroncladConfig, IroncladDifficulty
from blade_arena.game.models import Action, MatchState


class ParticipantError(ValueError):
    """Base exception for participant-related domain errors."""

    pass


class HumanActionRequiredError(ParticipantError):
    """Raised when a human participant is asked to choose an action but none was supplied."""

    pass


class IllegalParticipantActionError(ParticipantError):
    """Raised when a participant chooses an illegal action under current game rules."""

    pass


class AgentType(str, Enum):
    """Supported built-in AI agent architectures."""

    IRONCLAD = "ironclad"
    CYCLONE = "cyclone"


@runtime_checkable
class Participant(Protocol):
    """Protocol satisfied by any match participant (Human or AI)."""

    @property
    def name(self) -> str:
        """Human-readable participant display name."""
        ...

    @property
    def is_human(self) -> bool:
        """True if the participant requires external human input."""
        ...

    @property
    def last_diagnostics(self) -> Optional[Any]:
        """Optional diagnostics payload from the most recent decision."""
        ...

    def choose_action(self, state: MatchState, player_id: str) -> Action:
        """Select a legal action given an immutable pre-round state snapshot.

        Args:
            state: The pre-round MatchState snapshot.
            player_id: Identifier of the blade controlled by this participant.

        Returns:
            The selected Action.
        """
        ...


class HumanParticipant:
    """Participant representing a human operator.

    Does not block for console or keyboard input. The caller queues an Action
    prior to stepping the round, ensuring complete headless and test-friendly
    execution.
    """

    def __init__(self, name: str = "Human") -> None:
        self._name: str = name
        self._queued_action: Optional[Action] = None

    @property
    def name(self) -> str:
        return self._name

    @property
    def is_human(self) -> bool:
        return True

    @property
    def last_diagnostics(self) -> Optional[Any]:
        return None

    @property
    def has_queued_action(self) -> bool:
        """True if an action is currently staged for the upcoming round."""
        return self._queued_action is not None

    def queue_action(self, action: Action) -> None:
        """Stage an action for the upcoming round."""
        if not isinstance(action, Action):
            raise TypeError(f"Expected Action enum instance, got {type(action).__name__}")
        self._queued_action = action

    def clear_queued_action(self) -> None:
        """Clear any currently staged action."""
        self._queued_action = None

    def choose_action(self, state: MatchState, player_id: str) -> Action:
        """Retrieve and consume the staged action for this round.

        Raises:
            HumanActionRequiredError: If no action has been staged.
        """
        if self._queued_action is None:
            raise HumanActionRequiredError(
                f"Participant '{self._name}' ({player_id}) has no queued action for this round."
            )
        action = self._queued_action
        self._queued_action = None
        return action


class AIParticipant:
    """Participant wrapper for autonomous AI agents.

    Wraps an IroncladAgent, CycloneAgent, or any compatible agent object or callable.
    Saves diagnostics from agent.decide() if available, and tracks high-resolution
    decision timing telemetry.
    """

    def __init__(self, name: str, agent: Any) -> None:
        self._name: str = name
        self._agent: Any = agent
        self._last_diagnostics: Optional[Any] = None
        self._decision_times: List[float] = []

    @property
    def name(self) -> str:
        return self._name

    @property
    def is_human(self) -> bool:
        return False

    @property
    def agent(self) -> Any:
        """Underlying AI agent instance."""
        return self._agent

    @property
    def last_diagnostics(self) -> Optional[Any]:
        """Diagnostics from the most recent decision (e.g. IroncladDecision or CycloneDecision)."""
        return self._last_diagnostics

    @property
    def decision_times(self) -> Tuple[float, ...]:
        """Chronological recorded decision times (seconds) for this participant."""
        return tuple(self._decision_times)

    @property
    def decision_count(self) -> int:
        """Total number of action decisions made by this participant."""
        return len(self._decision_times)

    @property
    def total_decision_time(self) -> float:
        """Sum of all recorded decision times in seconds."""
        return sum(self._decision_times)

    @property
    def mean_decision_time(self) -> float:
        """Mean decision duration in seconds, or 0.0 if zero decisions made."""
        if not self._decision_times:
            return 0.0
        return sum(self._decision_times) / len(self._decision_times)

    def clear_telemetry(self) -> None:
        """Reset decision timing and telemetry counters."""
        self._decision_times.clear()
        self._last_diagnostics = None

    def choose_action(self, state: MatchState, player_id: str) -> Action:
        """Query the underlying agent for an action given the state snapshot."""
        import time

        t_start = time.perf_counter()

        # Align perspective if agent wraps player_id
        if hasattr(self._agent, "player_id"):
            try:
                self._agent.player_id = player_id
            except (AttributeError, TypeError):
                pass

        if hasattr(self._agent, "decide"):
            try:
                decision = self._agent.decide(state)
            except TypeError:
                decision = self._agent.decide(state, player_id)
            self._last_diagnostics = decision
            t_elapsed = time.perf_counter() - t_start
            # Use agent's measured decision time if available, otherwise perf_counter
            reported_time = getattr(decision, "decision_time_seconds", t_elapsed)
            self._decision_times.append(float(reported_time))
            if hasattr(decision, "action"):
                return decision.action
            raise TypeError(f"Agent {self._name}.decide() returned object without an action field: {decision}")

        if hasattr(self._agent, "choose_action"):
            try:
                res = self._agent.choose_action(state)
            except TypeError:
                res = self._agent.choose_action(state, player_id)
            t_elapsed = time.perf_counter() - t_start
            self._decision_times.append(t_elapsed)
            if isinstance(res, tuple):
                self._last_diagnostics = res[1]
                return res[0]
            self._last_diagnostics = None
            return res

        if callable(self._agent):
            try:
                res = self._agent(state, player_id)
            except TypeError:
                res = self._agent(state)
            t_elapsed = time.perf_counter() - t_start
            self._decision_times.append(t_elapsed)
            self._last_diagnostics = None
            return res

        raise TypeError(
            f"Agent '{self._name}' of type {type(self._agent).__name__} does not implement "
            f"decide(), choose_action(), or __call__"
        )


def create_ai_participant(
    name: str,
    agent_type: Union[str, AgentType],
    difficulty: Union[str, IroncladDifficulty, CycloneDifficulty] = "medium",
    seed: Optional[int] = None,
    player_id: str = "player_1",
    **kwargs: Any,
) -> AIParticipant:
    """Factory creating an AIParticipant with standard difficulty profiles.

    Args:
        name: Participant display name.
        agent_type: 'ironclad' or 'cyclone' (or AgentType enum).
        difficulty: 'easy', 'medium', 'hard', or respective Difficulty enum.
        seed: Random seed for stochastic agents (Cyclone).
        player_id: Default acting player perspective identifier.
        **kwargs: Extra parameters passed to the underlying agent configuration.

    Returns:
        Configured AIParticipant.
    """
    if isinstance(agent_type, str):
        try:
            agent_enum = AgentType(agent_type.lower())
        except ValueError:
            raise ValueError(f"Unknown agent type '{agent_type}'. Supported: {[t.value for t in AgentType]}")
    else:
        agent_enum = agent_type

    diff_str = difficulty.value.lower() if isinstance(difficulty, (IroncladDifficulty, CycloneDifficulty)) else str(difficulty).lower()

    if agent_enum == AgentType.IRONCLAD:
        try:
            config = IroncladConfig.for_difficulty(diff_str, **kwargs)
        except (ValueError, KeyError):
            raise ValueError(f"Unknown Ironclad difficulty '{difficulty}'. Supported: 'easy', 'medium', 'hard'")
        agent = IroncladAgent(player_id=player_id, config=config)
        return AIParticipant(name=name, agent=agent)

    if agent_enum == AgentType.CYCLONE:
        if seed is not None:
            kwargs["seed"] = seed
        try:
            config = CycloneConfig.for_difficulty(diff_str, **kwargs)
        except (ValueError, KeyError):
            raise ValueError(f"Unknown Cyclone difficulty '{difficulty}'. Supported: 'easy', 'medium', 'hard'")
        agent = CycloneAgent(player_id=player_id, config=config)
        return AIParticipant(name=name, agent=agent)

    raise ValueError(f"Unsupported agent type: {agent_enum}")
