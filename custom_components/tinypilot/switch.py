"""Mouse jiggler switch for TinyPilot."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import TinyPilotConfigEntry
from .entity import TinyPilotEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TinyPilotConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the TinyPilot jiggler switch."""
    coordinator = entry.runtime_data
    async_add_entities([TinyPilotJigglerSwitch(coordinator, entry.entry_id)])


class TinyPilotJigglerSwitch(TinyPilotEntity, SwitchEntity):
    """Switch controlling the mouse-jiggler cron entry on the device."""

    _attr_translation_key = "jiggler"
    _attr_icon = "mdi:mouse"

    def __init__(self, coordinator, entry_id: str) -> None:
        """Initialize the switch."""
        super().__init__(coordinator, entry_id, "jiggler")

    @property
    def is_on(self) -> bool | None:
        """Return whether the jiggler is currently enabled."""
        return (self.coordinator.data or {}).get("jiggler_enabled")

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable the mouse jiggler."""
        await self.coordinator.client.set_jiggler(True)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable the mouse jiggler."""
        await self.coordinator.client.set_jiggler(False)
        await self.coordinator.async_request_refresh()
