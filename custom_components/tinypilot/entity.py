"""Base entity for TinyPilot: wires every platform entity to one HA device."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import TinyPilotDataUpdateCoordinator


class TinyPilotEntity(CoordinatorEntity[TinyPilotDataUpdateCoordinator]):
    """Base entity tying every TinyPilot entity to a single device."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: TinyPilotDataUpdateCoordinator,
        entry_id: str,
        unique_id_suffix: str,
    ) -> None:
        """Initialize the entity and its DeviceInfo."""
        super().__init__(coordinator)
        status = coordinator.data or {}
        hostname = status.get("hostname", entry_id)
        self._attr_unique_id = f"{entry_id}_{unique_id_suffix}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            name=hostname,
            manufacturer=MANUFACTURER,
            model="Voyager / Hobbyist",
            sw_version=status.get("tinypilot_version"),
            configuration_url=f"https://{coordinator.config_entry.data['host']}",
        )
