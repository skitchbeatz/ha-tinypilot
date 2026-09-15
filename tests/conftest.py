"""Fixtures for TinyPilot tests."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.tinypilot.const import CONF_FINGERPRINT, DOMAIN

pytest_plugins = "pytest_homeassistant_custom_component"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable custom integrations for every test in this suite."""
    yield


@pytest.fixture(autouse=True)
def mock_fingerprint():
    """Stub out the real TLS socket probe used by config flow / reauth."""
    with patch(
        "custom_components.tinypilot.config_flow.async_fetch_fingerprint",
        return_value=(b"\xab" * 32, "ab" * 32),
    ) as mock:
        yield mock


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """A pre-built config entry for a device named 'tinypilot'."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id="tinypilot",
        title="tinypilot",
        data={
            "host": "10.10.10.110",
            "api_key": "secret-token",
            CONF_FINGERPRINT: "ab" * 32,
        },
    )
