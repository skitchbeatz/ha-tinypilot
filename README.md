# TinyPilot for Home Assistant

A [HACS](https://hacs.xyz/) custom integration for the license-free
[TinyPilot REST API companion service](https://github.com/skitchbeatz/tinypilot-automation),
giving your TinyPilot KVM a proper device in Home Assistant instead of SSH
polling.

## What you get

One device per TinyPilot, with:

| Entity | Type | Notes |
| :--- | :--- | :--- |
| Video source online | `binary_sensor` | Connectivity |
| Keyboard ready / Mouse ready | `binary_sensor` | Diagnostic, HID device availability |
| Mouse jiggler | `switch` | Idempotent on/off |
| One button per allowlisted script | `button` | e.g. "Calendar Extractor" |
| TinyPilot version / API version | `sensor` | Diagnostic |

Plus three services for use in automations/scripts:

- `tinypilot.paste_text` — type text via HID keyboard
- `tinypilot.send_keystroke` — a single key or combo (Ctrl/Shift/Alt/Meta)
- `tinypilot.run_script` — run any allowlisted user script by name

## Requirements

- TinyPilot 2.8.0+ with the [REST API companion service](https://github.com/skitchbeatz/tinypilot-automation) installed (`./install-api.sh` in that repo).
- The API's Bearer token from `/etc/tinypilot/custom-api.conf` on the device.
- Home Assistant 2025.1 or newer.

## Installing

1. HACS → the "⋮" menu → **Custom repositories** → add this repo's URL as type **Integration**.
2. Install **TinyPilot**, restart Home Assistant.
3. Settings → Devices & Services → **Add Integration** → search "TinyPilot".
4. Enter the device's host and the API key.

## TLS certificate pinning

TinyPilot uses a self-signed certificate, so this integration doesn't trust
the system CA store for it — that would mean trusting *any* certificate
signed by anything HA already trusts, which isn't meaningfully better than
no TLS at all for a self-signed device. Instead, on setup it:

1. Opens a TLS connection with verification off (this is how any client
   discovers a self-signed cert — there's no other way).
2. Computes the SHA-256 of the certificate it was shown.
3. Shows you that fingerprint and the device's reported hostname/version to
   confirm.
4. Pins exactly that certificate for all future requests
   (`aiohttp.Fingerprint`). Home Assistant will refuse to talk to the device
   if a different certificate shows up later.

If the device's certificate ever changes (TinyPilot reinstall, cert
regenerated, etc.), the integration can no longer verify it's still your
device — it raises a repair/reauth flow rather than silently trusting the
new certificate. Confirm the new fingerprint the same way to re-pin it.

A 401 (bad/rotated API key) triggers the same reauth flow.

## Development

```bash
python3.13 -m venv .venv
.venv/bin/pip install -r requirements_test.txt
.venv/bin/pytest tests/ -q
```

CI runs `hassfest`, the HACS validation action, and the test suite on every
push/PR (see `.github/workflows/validate.yml`).

## Security notes

- The API key is stored in HA's config entry storage (`.storage/core.config_entries`), not in YAML.
- Diagnostics (Settings → Devices → TinyPilot → Download diagnostics) redact the API key and pinned fingerprint.
- Pair this with the API-side hardening in
  [tinypilot-automation](https://github.com/skitchbeatz/tinypilot-automation):
  the service refuses to start without a real key, and nginx restricts
  `/api/v1/*` to an IP allowlist on top of the token.
