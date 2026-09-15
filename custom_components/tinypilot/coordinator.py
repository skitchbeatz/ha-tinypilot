"""DataUpdateCoordinator for TinyPilot: one poll of /status feeds every entity."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    TinyPilotAuthError,
    TinyPilotClient,
    TinyPilotConnectionError,
    TinyPilotFingerprintMismatch,
)
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)

type TinyPilotConfigEntry = ConfigEntry[TinyPilotDataUpdateCoordinator]


class TinyPilotDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Polls /api/v1/status and holds the device's allowlisted scripts."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: TinyPilotConfigEntry,
        client: TinyPilotClient,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN} ({entry.data['host']})",
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )
        self.client = client
        self.scripts: list[str] = []

    async def _async_setup(self) -> None:
        """Fetch the allowlisted scripts once at startup (rarely changes)."""
        try:
            self.scripts = await self.client.list_scripts()
        except TinyPilotAuthError as err:
            raise ConfigEntryAuthFailed("Invalid API key") from err
        except TinyPilotFingerprintMismatch as err:
            raise ConfigEntryAuthFailed(
                "TLS certificate no longer matches the pinned fingerprint"
            ) from err
        except TinyPilotConnectionError as err:
            raise UpdateFailed(str(err)) from err

    async def _async_update_data(self) -> dict[str, Any]:
        """Poll device status."""
        try:
            return await self.client.get_status()
        except TinyPilotAuthError as err:
            raise ConfigEntryAuthFailed("Invalid API key") from err
        except TinyPilotFingerprintMismatch as err:
            raise ConfigEntryAuthFailed(
                "TLS certificate no longer matches the pinned fingerprint"
            ) from err
        except TinyPilotConnectionError as err:
            raise UpdateFailed(str(err)) from err
