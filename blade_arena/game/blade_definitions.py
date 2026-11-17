"""Single source of truth for blade type definitions and archetype statistics.

Provides immutable specifications for Balanced, Attacker, Defender, and Stamina blades,
along with helper factories to construct initial BladeState instances.
"""

from __future__ import annotations

import math
import types
from dataclasses import dataclass
from typing import Mapping

from blade_arena.game.models import BladeState, BladeType, Position


@dataclass(frozen=True)
class BladeDefinition:
    """Immutable archetype configuration specifying baseline characteristics of a blade type."""

    blade_type: BladeType
    name: str
    max_energy: float
    max_stability: float
    passive_energy_loss: float
    attack_power_multiplier: float
    guard_stability_recovery: float
    charge_energy_recovery: float

    def __post_init__(self) -> None:
        if not isinstance(self.blade_type, BladeType):
            raise TypeError(f"blade_type must be a BladeType enum, got {type(self.blade_type).__name__}")

        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("name must be a non-empty string")

        # Validate numeric attributes
        numeric_fields = [
            ("max_energy", self.max_energy),
            ("max_stability", self.max_stability),
            ("passive_energy_loss", self.passive_energy_loss),
            ("attack_power_multiplier", self.attack_power_multiplier),
            ("guard_stability_recovery", self.guard_stability_recovery),
            ("charge_energy_recovery", self.charge_energy_recovery),
        ]
        for field_name, value in numeric_fields:
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise TypeError(f"{field_name} must be numeric, got {type(value).__name__}")
            if not math.isfinite(value):
                raise ValueError(f"{field_name} must be finite, got {value}")

        if self.max_energy <= 0.0:
            raise ValueError(f"max_energy must be strictly positive, got {self.max_energy}")
        if self.max_stability <= 0.0:
            raise ValueError(f"max_stability must be strictly positive, got {self.max_stability}")
        if self.passive_energy_loss < 0.0:
            raise ValueError(f"passive_energy_loss must be non-negative, got {self.passive_energy_loss}")
        if self.attack_power_multiplier <= 0.0:
            raise ValueError(
                f"attack_power_multiplier must be strictly positive, got {self.attack_power_multiplier}"
            )
        if self.guard_stability_recovery < 0.0:
            raise ValueError(
                f"guard_stability_recovery must be non-negative, got {self.guard_stability_recovery}"
            )
        if self.charge_energy_recovery < 0.0:
            raise ValueError(
                f"charge_energy_recovery must be non-negative, got {self.charge_energy_recovery}"
            )


# ------------------------------------------------------------------------------
# Archetype Definitions Registry (Project Specification)
# ------------------------------------------------------------------------------

_BLADE_DEFINITIONS: dict[BladeType, BladeDefinition] = {
    BladeType.BALANCED: BladeDefinition(
        blade_type=BladeType.BALANCED,
        name="Balanced",
        max_energy=100.0,
        max_stability=100.0,
        passive_energy_loss=3.0,
        attack_power_multiplier=1.00,
        guard_stability_recovery=5.0,
        charge_energy_recovery=20.0,
    ),
    BladeType.ATTACKER: BladeDefinition(
        blade_type=BladeType.ATTACKER,
        name="Attacker",
        max_energy=100.0,
        max_stability=90.0,
        passive_energy_loss=4.0,
        attack_power_multiplier=1.25,
        guard_stability_recovery=5.0,
        charge_energy_recovery=20.0,
    ),
    BladeType.DEFENDER: BladeDefinition(
        blade_type=BladeType.DEFENDER,
        name="Defender",
        max_energy=100.0,
        max_stability=120.0,
        passive_energy_loss=3.0,
        attack_power_multiplier=0.85,
        guard_stability_recovery=10.0,
        charge_energy_recovery=20.0,
    ),
    BladeType.STAMINA: BladeDefinition(
        blade_type=BladeType.STAMINA,
        name="Stamina",
        max_energy=100.0,
        max_stability=100.0,
        passive_energy_loss=2.0,
        attack_power_multiplier=1.00,
        guard_stability_recovery=5.0,
        charge_energy_recovery=25.0,
    ),
}


def get_blade_definition(blade_type: BladeType) -> BladeDefinition:
    """Retrieve the immutable BladeDefinition for a given BladeType.

    Args:
        blade_type: The BladeType enum member to look up.

    Returns:
        The corresponding BladeDefinition.

    Raises:
        KeyError: If the blade_type is unsupported or not registered.
        TypeError: If blade_type is not a BladeType instance.
    """
    if not isinstance(blade_type, BladeType):
        raise TypeError(f"Expected BladeType enum, got {type(blade_type).__name__}: {blade_type}")
    if blade_type not in _BLADE_DEFINITIONS:
        raise KeyError(f"Unsupported blade type: {blade_type}")
    return _BLADE_DEFINITIONS[blade_type]


def get_all_blade_definitions() -> Mapping[BladeType, BladeDefinition]:
    """Retrieve a read-only mapping of all registered blade definitions."""
    return types.MappingProxyType(_BLADE_DEFINITIONS)


def create_blade_state(
    player_id: str,
    blade_type: BladeType,
    position: Position,
) -> BladeState:
    """Construct an initial BladeState for a player using its archetype definition.

    Args:
        player_id: Unique player identifier.
        blade_type: Archetype to instantiate.
        position: Starting stadium coordinates.

    Returns:
        A new BladeState initialized to full energy and full stability for its type,
        with Special Spin ready at game time 0.0s.
    """
    definition = get_blade_definition(blade_type)
    return BladeState(
        player_id=player_id,
        blade_type=blade_type,
        current_energy=definition.max_energy,
        max_energy=definition.max_energy,
        current_stability=definition.max_stability,
        max_stability=definition.max_stability,
        position=position,
        special_ready_at=0.0,
    )


# Convenient alias
create_blade = create_blade_state
