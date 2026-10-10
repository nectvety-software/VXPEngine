# SSH Web Bridge

SSH Web Bridge is a small, self-hosted remote-operations console intended to
work in a low-bandwidth mobile browser (including the browser on an MRE phone).
It includes a native 240x320 VXPEngine/MRE keypad client in `VXPClient/` as well
as the browser dashboard. The gateway performs SSH; the phone never receives
SSH credentials or raw shell access.

## Security model

- The gateway binds to `127.0.0.1:8765` by default. Keep it behind a TLS reverse
  proxy for remote access; never expose the development HTTP listener directly.
- API access requires a random bearer token configured in the environment.
- Targets and key paths come from a local JSON configuration file.
- SSH host keys must already be present in `known_hosts`; unknown or changed
  keys are rejected. Password authentication and agent forwarding are disabled.
- The API exposes named actions, not a command parameter. Read-only diagnostics
  are available by default. Service restarts can only address services listed
  in the local config and require the operator to type `RESTART`.
- Responses, connection times and request rates are bounded. Audit logs omit
  tokens, key material and command output.
- The VXP client pairs with an 8-12 digit code and holds a random session token
  in RAM for at most 30 minutes; it never writes that token to cache/storage.
- IoT macros are structured MQTT publishes or fixed admin-installed scripts.
  Macro IDs, topics, payloads and script basenames are validated; no shell text
  comes from the phone. The gate and sleep macros ask for a second confirmation.

## Run locally

1. Install Python 3.10+ and the pinned dependency range:

   ```powershell
   py -m venv .venv
   .\.venv\Scripts\python -m pip install -r requirements.txt
   ```

2. Copy `config.example.json` to a private location and fill in target host,
   username, private-key path, known-hosts path and the allowed service names.
   Create a strong random token and set:

   ```powershell
   $env:SSHWB_TOKEN = (py -c "import secrets; print(secrets.token_urlsafe(32))")
   $env:SSHWB_CONFIG = "C:\secure\sshwb-config.json"
   .\.venv\Scripts\python run.py
   ```

3. Open `http://127.0.0.1:8765`. For the phone, publish this service through a
   TLS reverse proxy on a trusted network and open its HTTPS URL in the phone's
   browser. Use firewall rules and VPN access where possible.

To pair the VXP phone client, also set `SSHWB_PAIR_CODE` to an 8-12 digit code
and restart the gateway. Keep this short code private and rotate it after
pairing. It is rate-limited to five attempts per ten minutes per client IP.

Before enabling remote access, add the SSH host key to the configured
`known_hosts` file and verify its fingerprint with the server administrator.
Copy `gateway_actions/get_temp.py` to
`/usr/local/lib/sshwebbridge/actions/get_temp.py` on the target and make it
executable by the SSH account. Store its Home Assistant URL, long-lived token
and entity ID in `/etc/sshwebbridge/home-assistant.json`, readable only by that
SSH account. Configure the target's local Mosquitto broker and restrict MQTT
topics to the intended devices. The sample config sends `TOGGLE` for lights,
`OPEN` for the gate and `SLEEP` for the sleep scene.

`SSHWB_HOST` and `SSHWB_PORT` may override the bind address and port. Do not set
the host to `0.0.0.0` unless a firewall and TLS reverse proxy are already in
place. The app deliberately has no default token or demo SSH endpoint.

## API

- `GET /api/targets` — configured target IDs and labels.
- `GET /api/actions` — action IDs and whether an action is read-only.
- `POST /api/run` — JSON `{ "target": "prod", "action": "health" }`.
- `POST /api/run` restart example: `{ "target": "prod", "action":
  "restart_service", "service": "nginx", "confirm": "RESTART" }`.
- `POST /api/pair` — JSON `{ "code": "12345678" }`; returns a RAM-only bearer
  session token valid for 30 minutes when device pairing is enabled.

Every API request requires `Authorization: Bearer <SSHWB_TOKEN>`. The browser
keeps the token in session storage only. Responses are capped to 8 KiB.

## Checks

Run `python -m unittest discover -s tests -v` from this folder. Tests cover
authorization, validation, action allowlisting, output bounds and host-key
verification configuration without contacting a real server.

## Build the VXP client

Open `VXPClient/project.vxp.json` in VXPEngine or run `VXPClient/build_arm.bat`.
The resulting installable package is `VXPClient/build-arm/main/ssh_bridge.vxp`.
Run `VXPClient/run_vxpemu.bat` to build and launch in VXPEmu. The phone asks for
the gateway HTTPS URL, target ID (default `homelab`) and pairing code. Keys 1-4
send the configured actions: toggle all lights, open garage gate, house temperature
and sleep mode. Gate and sleep mode require pressing the same key twice within
about 4.5 seconds. Key 0 edits gateway/target and pairs again; `*` re-pairs
against the current gateway. Back exits.

The client requires the MRE HTTP stack to support HTTPS and trust the gateway's
certificate chain. Test that on the target handset; emulator smoke tests only
confirm that the package starts. Do not switch the app to plain HTTP because
the pairing code and session bearer token must stay encrypted in transit.

## Bluetooth mouse feasibility

The VXP client has a RetroMRE-inspired Bluetooth information page (use left/right
to switch tabs). The MRE SDK bundled with this VXPEngine checkout exposes
Bluetooth Classic connection management and SPP serial APIs, but no Bluetooth
HID Device profile or mouse-report API. As a result, this VXP cannot pair
directly as a plug-and-play mouse with a computer or phone. A computer would
need a separate SPP-to-pointer helper, and a phone would need a companion app
with the required accessibility/input-control permission. The UI states this
limitation instead of reporting a false connected-mouse state.
