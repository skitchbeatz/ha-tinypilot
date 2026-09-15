"""Buttons for TinyPilot: one per allowlisted user script."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import TinyPilotConfigEntry
from .entity import TinyPilotEntity

# Friendlier default names/icons for known scripts; anything else falls back
# to a title-cased version of the script name with a generic icon.
_SCRIPT_DISPLAY: dict[str, tuple[str, str]] = {
    "calendar-extractor": ("Calendar Extractor", "mdi:calendar-camera"),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TinyPilotConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up one button per script the device allowlisted for the API."""
    coordinator = entry.runtime_data
    async_add_entities(
        TinyPilotScriptButton(coordinator, entry.entry_id, script_name)
        for script_name in coordinator.scripts
    )


class TinyPilotScriptButton(TinyPilotEntity, ButtonEntity):
    """Runs a single allowlisted TinyPilot user script."""

    def __init__(self, coordinator, entry_id: str, script_name: str) -> None:
        """Initialize the button."""
        super().__init__(coordinator, entry_id, f"script_{script_name}")
        self._script_name = script_name
        name, icon = _SCRIPT_DISPLAY.get(
            script_name, (script_name.replace("-", " ").replace("_", " ").title(), "mdi:script-text-play-outline")
        )
        self._attr_name = name
        self._attr_icon = icon

    async def async_press(self) -> None:
        """Run the script."""
        await self.coordinator.client.run_script(self._script_name)
