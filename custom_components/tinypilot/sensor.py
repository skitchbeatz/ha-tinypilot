"""Diagnostic version sensors for TinyPilot."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import TinyPilotConfigEntry
from .entity import TinyPilotEntity


@dataclass(frozen=True, kw_only=True)
class TinyPilotSensorDescription(SensorEntityDescription):
    """Describes a TinyPilot sensor backed by a field in /status."""

    value_fn: Callable[[dict[str, Any]], str | None]


SENSORS: tuple[TinyPilotSensorDescription, ...] = (
    TinyPilotSensorDescription(
        key="tinypilot_version",
        translation_key="tinypilot_version",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.get("tinypilot_version"),
    ),
    TinyPilotSensorDescription(
        key="api_version",
        translation_key="api_version",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.get("api_version"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TinyPilotConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up TinyPilot diagnostic sensors."""
    coordinator = entry.runtime_data
    async_add_entities(
        TinyPilotSensor(coordinator, entry.entry_id, description)
        for description in SENSORS
    )


class TinyPilotSensor(TinyPilotEntity, SensorEntity):
    """A TinyPilot diagnostic sensor backed by the status coordinator."""

    entity_description: TinyPilotSensorDescription

    def __init__(
        self,
        coordinator,
        entry_id: str,
        description: TinyPilotSensorDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry_id, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> str | None:
        """Return the current value."""
        return self.entity_description.value_fn(self.coordinator.data or {})
