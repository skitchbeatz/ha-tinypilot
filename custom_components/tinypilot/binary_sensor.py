"""Binary sensors for TinyPilot: video source, keyboard/mouse HID readiness."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import TinyPilotConfigEntry
from .entity import TinyPilotEntity


@dataclass(frozen=True, kw_only=True)
class TinyPilotBinarySensorDescription(BinarySensorEntityDescription):
    """Describes a TinyPilot binary sensor backed by a field in /status."""

    is_on_fn: Callable[[dict[str, Any]], bool | None]


BINARY_SENSORS: tuple[TinyPilotBinarySensorDescription, ...] = (
    TinyPilotBinarySensorDescription(
        key="video_online",
        translation_key="video_online",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        is_on_fn=lambda data: data.get("video_online"),
    ),
    TinyPilotBinarySensorDescription(
        key="keyboard_ready",
        translation_key="keyboard_ready",
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on_fn=lambda data: (data.get("keyboard") or {}).get("ready"),
    ),
    TinyPilotBinarySensorDescription(
        key="mouse_ready",
        translation_key="mouse_ready",
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on_fn=lambda data: (data.get("mouse") or {}).get("ready"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TinyPilotConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up TinyPilot binary sensors."""
    coordinator = entry.runtime_data
    async_add_entities(
        TinyPilotBinarySensor(coordinator, entry.entry_id, description)
        for description in BINARY_SENSORS
    )


class TinyPilotBinarySensor(TinyPilotEntity, BinarySensorEntity):
    """A TinyPilot binary sensor backed by the status coordinator."""

    entity_description: TinyPilotBinarySensorDescription

    def __init__(
        self,
        coordinator,
        entry_id: str,
        description: TinyPilotBinarySensorDescription,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator, entry_id, description.key)
        self.entity_description = description

    @property
    def is_on(self) -> bool | None:
        """Return the current state."""
        return self.entity_description.is_on_fn(self.coordinator.data or {})
