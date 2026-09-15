"""The TinyPilot integration."""

from __future__ import annotations

import logging

import voluptuous as vol
from homeassistant.const import CONF_API_KEY, CONF_HOST, Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import TinyPilotClient, TinyPilotError
from .const import (
    ATTR_ALT,
    ATTR_CODE,
    ATTR_CTRL,
    ATTR_DELAY_MS,
    ATTR_LANGUAGE,
    ATTR_META,
    ATTR_SCRIPT_NAME,
    ATTR_SHIFT,
    ATTR_TEXT,
    CONF_FINGERPRINT,
    DOMAIN,
    SERVICE_PASTE_TEXT,
    SERVICE_RUN_SCRIPT,
    SERVICE_SEND_KEYSTROKE,
)
from .coordinator import TinyPilotConfigEntry, TinyPilotDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.SENSOR,
    Platform.SWITCH,
]

_SERVICE_TARGET_SCHEMA = vol.Schema(
    {vol.Required("config_entry_id"): cv.string}, extra=vol.ALLOW_EXTRA
)


async def async_setup_entry(hass: HomeAssistant, entry: TinyPilotConfigEntry) -> bool:
    """Set up TinyPilot from a config entry."""
    session = async_get_clientsession(hass, verify_ssl=False)
    fingerprint = bytes.fromhex(entry.data[CONF_FINGERPRINT])
    client = TinyPilotClient(
        session, entry.data[CONF_HOST], entry.data[CONF_API_KEY], fingerprint
    )

    coordinator = TinyPilotDataUpdateCoordinator(hass, entry, client)
    # Raises ConfigEntryAuthFailed (bad key / cert mismatch) or
    # ConfigEntryNotReady (unreachable) as appropriate; both propagate
    # straight to HA's setup-retry/reauth handling.
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    _async_register_services(hass)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: TinyPilotConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


def _get_coordinator_for_call(
    hass: HomeAssistant, call: ServiceCall
) -> TinyPilotDataUpdateCoordinator:
    """Resolve the target device's coordinator from a service call."""
    entry_id = call.data["config_entry_id"]
    entry: TinyPilotConfigEntry | None = hass.config_entries.async_get_entry(entry_id)
    if entry is None or entry.domain != DOMAIN:
        raise vol.Invalid(f"Unknown TinyPilot config entry: {entry_id}")
    return entry.runtime_data


def _async_register_services(hass: HomeAssistant) -> None:
    """Register the tinypilot.* services once, shared across all entries."""
    if hass.services.has_service(DOMAIN, SERVICE_PASTE_TEXT):
        return

    async def async_paste_text(call: ServiceCall) -> None:
        coordinator = _get_coordinator_for_call(hass, call)
        try:
            await coordinator.client.paste_text(
                text=call.data[ATTR_TEXT],
                language=call.data.get(ATTR_LANGUAGE, "en-US"),
                delay_ms=call.data.get(ATTR_DELAY_MS, 5.0),
            )
        except TinyPilotError as err:
            raise HomeAssistantError(str(err)) from err

    async def async_send_keystroke(call: ServiceCall) -> None:
        coordinator = _get_coordinator_for_call(hass, call)
        try:
            await coordinator.client.send_keystroke(
                code=call.data.get(ATTR_CODE),
                ctrl=call.data.get(ATTR_CTRL, False),
                shift=call.data.get(ATTR_SHIFT, False),
                alt=call.data.get(ATTR_ALT, False),
                meta=call.data.get(ATTR_META, False),
            )
        except TinyPilotError as err:
            raise HomeAssistantError(str(err)) from err

    async def async_run_script(call: ServiceCall) -> None:
        coordinator = _get_coordinator_for_call(hass, call)
        try:
            await coordinator.client.run_script(call.data[ATTR_SCRIPT_NAME])
        except TinyPilotError as err:
            raise HomeAssistantError(str(err)) from err

    hass.services.async_register(
        DOMAIN,
        SERVICE_PASTE_TEXT,
        async_paste_text,
        schema=_SERVICE_TARGET_SCHEMA.extend(
            {
                vol.Required(ATTR_TEXT): cv.string,
                vol.Optional(ATTR_LANGUAGE): cv.string,
                vol.Optional(ATTR_DELAY_MS): vol.Coerce(float),
            }
        ),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SEND_KEYSTROKE,
        async_send_keystroke,
        schema=_SERVICE_TARGET_SCHEMA.extend(
            {
                vol.Optional(ATTR_CODE): cv.string,
                vol.Optional(ATTR_CTRL): cv.boolean,
                vol.Optional(ATTR_SHIFT): cv.boolean,
                vol.Optional(ATTR_ALT): cv.boolean,
                vol.Optional(ATTR_META): cv.boolean,
            }
        ),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_RUN_SCRIPT,
        async_run_script,
        schema=_SERVICE_TARGET_SCHEMA.extend({vol.Required(ATTR_SCRIPT_NAME): cv.string}),
    )
