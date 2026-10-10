#!/usr/bin/env python3
"""Print one Home Assistant temperature entity for the SSH bridge client."""

import json
import os
import urllib.error
import urllib.request
from pathlib import Path


def main() -> int:
    # Keep this file root-readable only when the bridge invokes it through sudo.
    # It contains the Home Assistant token and must never be copied to the phone.
    config_path = Path(os.environ.get("SSHWB_HA_CONFIG", "/etc/sshwebbridge/home-assistant.json"))
    config = json.loads(config_path.read_text(encoding="utf-8"))
    base = config["url"].rstrip("/")
    entity = config.get("temperature_entity", "sensor.house_temperature")
    token = config["token"]
    if not entity.startswith("sensor."):
        raise ValueError("temperature_entity must be a Home Assistant sensor")
    request = urllib.request.Request(
        base + "/api/states/" + entity,
        headers={"Authorization": "Bearer " + token, "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            state = json.loads(response.read(8192).decode("utf-8"))
    except (urllib.error.URLError, TimeoutError) as exc:
        print("Home Assistant unavailable")
        return 2
    value = state.get("state", "unknown")
    unit = state.get("attributes", {}).get("unit_of_measurement", "")
    print("House temperature: {} {}".format(value, unit).strip())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
