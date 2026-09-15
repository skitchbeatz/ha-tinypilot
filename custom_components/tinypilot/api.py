"""Thin async client for the TinyPilot custom REST API.

Connects over HTTPS pinned to a specific server certificate fingerprint
(the device uses a self-signed cert, so we deliberately don't trust the
system CA store -- we trust the one cert we were shown and confirmed
during config flow).
"""

from __future__ import annotations

import hashlib
import logging
import socket
import ssl
from typing import Any

import aiohttp
from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

DEFAULT_TIMEOUT = aiohttp.ClientTimeout(total=10)
FINGERPRINT_TIMEOUT = 10


def _fetch_der_certificate(host: str, port: int) -> bytes:
    """Blocking: open a TLS connection and return the peer cert (DER bytes).

    Verification is deliberately disabled here -- this is how we *discover*
    a certificate to pin, not how we trust one. Every subsequent API call
    uses aiohttp.Fingerprint to pin to exactly this certificate.
    """
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    with socket.create_connection((host, port), timeout=FINGERPRINT_TIMEOUT) as sock:
        with ctx.wrap_socket(sock, server_hostname=host) as tls_sock:
            return tls_sock.getpeercert(binary_form=True)


async def async_fetch_fingerprint(
    hass: HomeAssistant, host: str, port: int
) -> tuple[bytes, str]:
    """Return (raw sha256 digest bytes, hex string) of the device's TLS cert.

    Raises OSError/ssl.SSLError on connection failure -- callers translate
    that into a config-flow error.
    """
    der = await hass.async_add_executor_job(_fetch_der_certificate, host, port)
    digest = hashlib.sha256(der).digest()
    return digest, digest.hex()


class TinyPilotError(Exception):
    """Base error for TinyPilot API failures."""


class TinyPilotAuthError(TinyPilotError):
    """Raised when the API rejects the configured Bearer token."""


class TinyPilotConnectionError(TinyPilotError):
    """Raised when the device can't be reached."""


class TinyPilotFingerprintMismatch(TinyPilotConnectionError):
    """Raised when the live TLS cert no longer matches the pinned one.

    This means either the device's cert was regenerated (e.g. reinstall)
    or something else is answering at that host/port -- either way, the
    stored pin can no longer be trusted automatically and needs the user
    to re-confirm via reauth.
    """


class TinyPilotClient:
    """Async client for a single TinyPilot device's REST API."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        host: str,
        api_key: str,
        fingerprint: bytes,
    ) -> None:
        """Initialize the client.

        `fingerprint` is the raw SHA-256 digest bytes of the server's
        certificate, as pinned during config flow.
        """
        self._session = session
        self._base_url = f"https://{host}/api/v1"
        self._headers = {"Authorization": f"Bearer {api_key}"}
        self._ssl = aiohttp.Fingerprint(fingerprint)

    async def _request(
        self, method: str, path: str, **kwargs: Any
    ) -> dict[str, Any]:
        url = f"{self._base_url}{path}"
        try:
            async with self._session.request(
                method,
                url,
                headers=self._headers,
                ssl=self._ssl,
                timeout=DEFAULT_TIMEOUT,
                **kwargs,
            ) as resp:
                if resp.status == 401:
                    raise TinyPilotAuthError(f"{method} {path}: invalid API key")
                resp.raise_for_status()
                if resp.content_type == "application/json":
                    return await resp.json()
                return {"_raw": await resp.read()}
        except aiohttp.ServerFingerprintMismatch as err:
            raise TinyPilotFingerprintMismatch(
                f"TLS certificate fingerprint mismatch for {host_from_url(url)}"
            ) from err
        except TinyPilotAuthError:
            raise
        except aiohttp.ClientResponseError as err:
            raise TinyPilotError(f"{method} {path} failed: HTTP {err.status}") from err
        except (aiohttp.ClientError, TimeoutError) as err:
            raise TinyPilotConnectionError(f"{method} {path} failed: {err}") from err

    async def get_status(self) -> dict[str, Any]:
        """Fetch device status: online state, versions, jiggler, HID readiness."""
        return await self._request("GET", "/status")

    async def get_jiggler(self) -> bool:
        """Return whether the mouse jiggler is enabled."""
        result = await self._request("GET", "/jiggler")
        return bool(result["enabled"])

    async def set_jiggler(self, enabled: bool) -> bool:
        """Set the mouse jiggler state. Returns the resulting state."""
        result = await self._request("PUT", "/jiggler", json={"enabled": enabled})
        return bool(result["enabled"])

    async def list_scripts(self) -> list[str]:
        """List the user scripts allowlisted for run_script."""
        result = await self._request("GET", "/scripts")
        return list(result.get("scripts", []))

    async def run_script(self, name: str) -> None:
        """Run an allowlisted user script."""
        await self._request("POST", f"/scripts/{name}")

    async def paste_text(
        self, text: str, language: str = "en-US", delay_ms: float = 5.0
    ) -> None:
        """Type text onto the target machine via HID keyboard."""
        await self._request(
            "POST",
            "/paste",
            json={"text": text, "language": language, "delay_ms": delay_ms},
        )

    async def send_keystroke(
        self,
        code: str | None = None,
        key: str | None = None,
        ctrl: bool = False,
        shift: bool = False,
        alt: bool = False,
        meta: bool = False,
    ) -> None:
        """Send a single hardware keystroke or key combination."""
        await self._request(
            "POST",
            "/keystroke",
            json={
                "code": code,
                "key": key,
                "ctrlLeft": ctrl,
                "shiftLeft": shift,
                "altLeft": alt,
                "metaLeft": meta,
            },
        )


def host_from_url(url: str) -> str:
    """Best-effort host extraction for error messages."""
    return url.split("://", 1)[-1].split("/", 1)[0]
