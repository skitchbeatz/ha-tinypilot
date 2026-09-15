"""Config flow for TinyPilot.

Two steps on first setup:
  1. `user`   - host + API key; we connect once (cert verification off,
               that's the whole point) and fetch the live TLS cert's
               SHA-256 fingerprint plus /status.
  2. `confirm`- show that fingerprint and the device's hostname/version so
               the user can visually confirm before we pin it. Pinning
               without this step would make the integration trust
               whatever certificate happens to be presented on first
               connect, which defeats the purpose on an untrusted LAN.

Reauth (triggered by a 401, or by the live cert no longer matching the
pinned fingerprint) re-runs the same two steps against the existing entry.
"""

from __future__ import annotations

import logging
from typing import Any

import aiohttp
import voluptuous as vol
from homeassistant.config_entries import SOURCE_REAUTH, ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_KEY, CONF_HOST
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import (
    TinyPilotAuthError,
    TinyPilotClient,
    TinyPilotConnectionError,
    async_fetch_fingerprint,
)
from .const import CONF_FINGERPRINT, DEFAULT_PORT, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_API_KEY): str,
    }
)


class TinyPilotConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a TinyPilot config flow."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize flow state held between steps."""
        self._host: str | None = None
        self._api_key: str | None = None
        self._fingerprint_hex: str | None = None
        self._fingerprint_bytes: bytes | None = None
        self._device_hostname: str | None = None
        self._tinypilot_version: str | None = None

    async def _async_probe(self, host: str, api_key: str) -> dict[str, str]:
        """Fetch the cert fingerprint and confirm the key works. Returns errors dict."""
        errors: dict[str, str] = {}
        try:
            digest, digest_hex = await async_fetch_fingerprint(
                self.hass, host, DEFAULT_PORT
            )
        except (OSError, TimeoutError) as err:
            _LOGGER.debug("Fingerprint fetch failed for %s: %s", host, err)
            errors["base"] = "cannot_connect"
            return errors

        session = async_get_clientsession(self.hass, verify_ssl=False)
        client = TinyPilotClient(session, host, api_key, digest)
        try:
            status = await client.get_status()
        except TinyPilotAuthError:
            errors["base"] = "invalid_auth"
            return errors
        except TinyPilotConnectionError as err:
            _LOGGER.debug("Status probe failed for %s: %s", host, err)
            errors["base"] = "cannot_connect"
            return errors
        except aiohttp.ClientError as err:
            _LOGGER.debug("Unexpected client error probing %s: %s", host, err)
            errors["base"] = "unknown"
            return errors

        self._host = host
        self._api_key = api_key
        self._fingerprint_bytes = digest
        self._fingerprint_hex = digest_hex
        self._device_hostname = status.get("hostname", host)
        self._tinypilot_version = status.get("tinypilot_version")
        return errors

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Collect host + API key, then move to fingerprint confirmation."""
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = await self._async_probe(
                user_input[CONF_HOST], user_input[CONF_API_KEY]
            )
            if not errors:
                return await self.async_step_confirm()

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_SCHEMA, errors=errors
        )

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show the fetched cert fingerprint and device info for confirmation."""
        if user_input is not None:
            await self.async_set_unique_id(self._device_hostname)
            data = {
                CONF_HOST: self._host,
                CONF_API_KEY: self._api_key,
                CONF_FINGERPRINT: self._fingerprint_hex,
            }

            if self.source == SOURCE_REAUTH:
                reauth_entry = self._get_reauth_entry()
                self._abort_if_unique_id_mismatch()
                return self.async_update_reload_and_abort(reauth_entry, data=data)

            self._abort_if_unique_id_configured()
            return self.async_create_entry(title=self._device_hostname, data=data)

        return self.async_show_form(
            step_id="confirm",
            description_placeholders={
                "host": self._host,
                "hostname": self._device_hostname,
                "tinypilot_version": self._tinypilot_version or "unknown",
                "fingerprint": self._fingerprint_hex,
            },
        )

    async def async_step_reauth(
        self, entry_data: dict[str, Any]
    ) -> ConfigFlowResult:
        """Start reauth: re-collect host + key (fingerprint gets re-pinned)."""
        self._host = entry_data.get(CONF_HOST)
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for host + API key again, same as initial setup."""
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = await self._async_probe(
                user_input[CONF_HOST], user_input[CONF_API_KEY]
            )
            if not errors:
                return await self.async_step_confirm()

        schema = vol.Schema(
            {
                vol.Required(CONF_HOST, default=self._host): str,
                vol.Required(CONF_API_KEY): str,
            }
        )
        return self.async_show_form(
            step_id="reauth_confirm", data_schema=schema, errors=errors
        )
