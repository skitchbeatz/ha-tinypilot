"""Tests for the TinyPilot config flow."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant import config_entries
from homeassistant.const import CONF_API_KEY, CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.tinypilot.api import TinyPilotAuthError, TinyPilotConnectionError
from custom_components.tinypilot.const import CONF_FINGERPRINT, DOMAIN

STATUS_PAYLOAD = {
    "status": "ok",
    "hostname": "tinypilot",
    "tinypilot_version": "2.8.0",
    "api_version": "1.2.0",
}


async def test_full_flow_success(hass: HomeAssistant) -> None:
    """Happy path: user step -> confirm step -> entry created and pinned."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with patch(
        "custom_components.tinypilot.config_flow.TinyPilotClient.get_status",
        new=AsyncMock(return_value=STATUS_PAYLOAD),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "10.10.10.110", CONF_API_KEY: "secret-token"},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm"
    assert result["description_placeholders"]["hostname"] == "tinypilot"
    assert result["description_placeholders"]["fingerprint"] == "ab" * 32

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "tinypilot"
    assert result["data"] == {
        CONF_HOST: "10.10.10.110",
        CONF_API_KEY: "secret-token",
        CONF_FINGERPRINT: "ab" * 32,
    }


async def test_invalid_auth_shows_error(hass: HomeAssistant) -> None:
    """A 401 from the device surfaces as invalid_auth and stays on the user step."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "custom_components.tinypilot.config_flow.TinyPilotClient.get_status",
        new=AsyncMock(side_effect=TinyPilotAuthError("bad key")),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "10.10.10.110", CONF_API_KEY: "wrong"},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "invalid_auth"}


async def test_cannot_connect_shows_error(hass: HomeAssistant) -> None:
    """A connection failure surfaces as cannot_connect."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "custom_components.tinypilot.config_flow.TinyPilotClient.get_status",
        new=AsyncMock(side_effect=TinyPilotConnectionError("unreachable")),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "10.10.10.110", CONF_API_KEY: "secret-token"},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_fingerprint_fetch_failure_shows_cannot_connect(
    hass: HomeAssistant, mock_fingerprint
) -> None:
    """If we can't even open the TLS socket, that's cannot_connect too."""
    mock_fingerprint.side_effect = OSError("no route to host")
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "10.10.10.110", CONF_API_KEY: "secret-token"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_duplicate_device_aborts(hass: HomeAssistant, mock_config_entry) -> None:
    """Re-adding a device with the same hostname aborts as already_configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    with patch(
        "custom_components.tinypilot.config_flow.TinyPilotClient.get_status",
        new=AsyncMock(return_value=STATUS_PAYLOAD),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "10.10.10.110", CONF_API_KEY: "secret-token"},
        )
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reauth_on_fingerprint_mismatch_repins(
    hass: HomeAssistant, mock_config_entry, mock_fingerprint
) -> None:
    """Reauth re-probes and, on success, updates the pinned fingerprint."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["step_id"] == "reauth_confirm"

    mock_fingerprint.return_value = (b"\xcd" * 32, "cd" * 32)
    with patch(
        "custom_components.tinypilot.config_flow.TinyPilotClient.get_status",
        new=AsyncMock(return_value=STATUS_PAYLOAD),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "10.10.10.110", CONF_API_KEY: "new-token"},
        )
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data[CONF_FINGERPRINT] == "cd" * 32
    assert mock_config_entry.data[CONF_API_KEY] == "new-token"
