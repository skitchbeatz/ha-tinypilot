"""Diagnostics support for TinyPilot."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant

from .const import CONF_FINGERPRINT
from .coordinator import TinyPilotConfigEntry

TO_REDACT = {CONF_API_KEY, CONF_FINGERPRINT}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: TinyPilotConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data
    return {
        "entry_data": async_redact_data(dict(entry.data), TO_REDACT),
        "scripts": coordinator.scripts,
        "status": coordinator.data,
    }
