"""Tests for diagnostics redaction."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant

from custom_components.tinypilot.const import CONF_FINGERPRINT
from custom_components.tinypilot.diagnostics import async_get_config_entry_diagnostics

STATUS_PAYLOAD = {"status": "ok", "hostname": "tinypilot", "tinypilot_version": "2.8.0"}


async def test_diagnostics_redacts_secrets(hass: HomeAssistant, mock_config_entry) -> None:
    """The API key and pinned fingerprint never appear in diagnostics output."""
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

    diagnostics = await async_get_config_entry_diagnostics(hass, mock_config_entry)

    assert diagnostics["entry_data"][CONF_API_KEY] == "**REDACTED**"
    assert diagnostics["entry_data"][CONF_FINGERPRINT] == "**REDACTED**"
    assert diagnostics["scripts"] == ["calendar-extractor"]
    assert diagnostics["status"]["hostname"] == "tinypilot"
