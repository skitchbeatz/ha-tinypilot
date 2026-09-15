"""Unit tests for the TinyPilot API client (no real network)."""

from __future__ import annotations

import pytest
from aioresponses import aioresponses


def _last_request_kwargs(mocked, method: str, url: str):
    """aioresponses keys requests by (method, yarl.URL) -- match by str()."""
    for (req_method, req_url), calls in mocked.requests.items():
        if req_method == method and str(req_url) == url:
            return calls[-1].kwargs
    raise AssertionError(f"No recorded {method} request to {url}")

from custom_components.tinypilot.api import (
    TinyPilotAuthError,
    TinyPilotClient,
    TinyPilotError,
)

FINGERPRINT = b"\xab" * 32
BASE = "https://10.10.10.110/api/v1"


@pytest.fixture
async def client(hass):
    """A TinyPilotClient using HA's shared session."""
    from homeassistant.helpers.aiohttp_client import async_get_clientsession

    session = async_get_clientsession(hass, verify_ssl=False)
    return TinyPilotClient(session, "10.10.10.110", "secret-token", FINGERPRINT)


async def test_get_status_sends_bearer_token(client) -> None:
    """The client attaches the configured Bearer token to every request."""
    with aioresponses() as mocked:
        mocked.get(
            f"{BASE}/status",
            payload={"status": "ok", "jiggler_enabled": True},
        )
        result = await client.get_status()

    assert result["jiggler_enabled"] is True
    kwargs = _last_request_kwargs(mocked, "GET", f"{BASE}/status")
    assert kwargs["headers"]["Authorization"] == "Bearer secret-token"


async def test_401_raises_auth_error(client) -> None:
    """A 401 response is translated into TinyPilotAuthError."""
    with aioresponses() as mocked:
        mocked.get(f"{BASE}/status", status=401)
        with pytest.raises(TinyPilotAuthError):
            await client.get_status()


async def test_set_jiggler_puts_enabled_flag(client) -> None:
    """PUT /jiggler sends the requested state and returns the result."""
    with aioresponses() as mocked:
        mocked.put(f"{BASE}/jiggler", payload={"enabled": True})
        result = await client.set_jiggler(True)

    assert result is True
    kwargs = _last_request_kwargs(mocked, "PUT", f"{BASE}/jiggler")
    assert kwargs["json"] == {"enabled": True}


async def test_run_script_posts_to_named_path(client) -> None:
    """run_script posts to /scripts/{name} with no body."""
    with aioresponses() as mocked:
        mocked.post(f"{BASE}/scripts/calendar-extractor", payload={"status": "success"})
        await client.run_script("calendar-extractor")


async def test_server_error_raises_generic_error(client) -> None:
    """A 500 response is translated into the generic TinyPilotError."""
    with aioresponses() as mocked:
        mocked.get(f"{BASE}/status", status=500)
        with pytest.raises(TinyPilotError):
            await client.get_status()
