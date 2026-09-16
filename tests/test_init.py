"""Tests for setup, entity creation, and reauth-on-401 during setup."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from custom_components.tinypilot.api import TinyPilotAuthError, TinyPilotConnectionError

STATUS_PAYLOAD = {
    "status": "ok",
    "hostname": "tinypilot",
    "tinypilot_version": "2.8.0",
    "api_version": "1.3.0",
    "video_online": False,
    "capture_online": True,
    "jiggler_enabled": False,
    "keyboard": {"ready": True},
    "mouse": {"ready": True},
}


async def test_setup_creates_entities(hass: HomeAssistant, mock_config_entry) -> None:
    """A successful setup populates entities for status, switch, sensors, and scripts."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "custom_components.tinypilot.api.TinyPilotClient.get_status",
        new=AsyncMock(return_value=STATUS_PAYLOAD),
    ), patch(
        "custom_components.tinypilot.api.TinyPilotClient.list_scripts",
        new=AsyncMock(return_value=["calendar-extractor"]),
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    assert hass.states.get("binary_sensor.tinypilot_video_signal").state == "off"
    assert hass.states.get("binary_sensor.tinypilot_video_capture_online").state == "on"
    assert hass.states.get("switch.tinypilot_mouse_jiggler").state == "off"
    assert hass.states.get("sensor.tinypilot_tinypilot_version").state == "2.8.0"
    assert hass.states.get("button.tinypilot_calendar_extractor") is not None

    assert hass.services.has_service("tinypilot", "paste_text")
    assert hass.services.has_service("tinypilot", "run_script")


async def test_setup_triggers_reauth_on_401(
    hass: HomeAssistant, mock_config_entry
) -> None:
    """A 401 during first refresh puts the entry into a reauth-needed state."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "custom_components.tinypilot.api.TinyPilotClient.get_status",
        new=AsyncMock(side_effect=TinyPilotAuthError("bad key")),
    ), patch(
        "custom_components.tinypilot.api.TinyPilotClient.list_scripts",
        new=AsyncMock(return_value=[]),
    ):
        result = await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert result is False
    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_setup_retries_on_connection_error(
    hass: HomeAssistant, mock_config_entry
) -> None:
    """An unreachable device puts the entry into setup-retry, not a hard failure."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "custom_components.tinypilot.api.TinyPilotClient.list_scripts",
        new=AsyncMock(side_effect=TinyPilotConnectionError("no route")),
    ):
        result = await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert result is False
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
