"""Generate the production art slots through Sprite Fusion's documented API.

Requires SPRITE_FUSION_API_KEY in the process environment or project .env.
Every SSE output is recorded; index 0 becomes the project source PNG. Existing
PNG files are versioned instead of silently discarded.
"""
from __future__ import annotations

import json
import os
import shutil
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLAN_PATH = ROOT / "assets" / "spritefusion-plan.json"
OUT = ROOT / "assets" / "spritefusion"
HISTORY = OUT / "generation-history.json"


def api_key() -> str:
    value = os.environ.get("SPRITE_FUSION_API_KEY", "").strip()
    env_path = ROOT / ".env"
    if not value and env_path.is_file():
        for raw in env_path.read_text(encoding="utf-8").splitlines():
            if raw.strip().startswith("SPRITE_FUSION_API_KEY="):
                value = raw.split("=", 1)[1].strip().strip("\"'")
                break
    if not value:
        raise SystemExit("Missing SPRITE_FUSION_API_KEY (environment or project .env).")
    return value


def request_sse(base: str, key: str, payload: dict) -> tuple[str, list[dict]]:
    request = urllib.request.Request(
        f"{base}/generate",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        method="POST",
    )
    outputs: list[dict] = []; request_id = ""
    try:
        with urllib.request.urlopen(request, timeout=300) as response:
            completed = False
            for raw in response:
                line = raw.decode("utf-8").strip()
                if not line.startswith("data:"):
                    continue
                event = json.loads(line[5:].lstrip())
                if event.get("type") == "started": request_id = str(event.get("request_id", ""))
                elif event.get("type") == "output": outputs.append(dict(event["asset"]))
                elif event.get("type") == "completed":
                    completed = True
                    if event.get("status") != "succeeded": raise RuntimeError(str(event.get("error", event)))
            if not completed: raise RuntimeError("Sprite Fusion stream interrupted; inspect account history before retrying.")
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"Sprite Fusion HTTP {exc.code}: {exc.read().decode('utf-8', 'replace')}") from exc
    if not outputs: raise RuntimeError("Sprite Fusion returned no usable output.")
    return request_id, outputs


def download(url: str, destination: Path) -> None:
    if destination.exists():
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        shutil.copy2(destination, destination.with_name(f"{destination.stem}-{stamp}{destination.suffix}"))
    with urllib.request.urlopen(url, timeout=120) as response:
        destination.write_bytes(response.read())


def main() -> None:
    key = api_key(); plan = json.loads(PLAN_PATH.read_text(encoding="utf-8")); base = plan["api"]
    OUT.mkdir(parents=True, exist_ok=True); anchor_id = ""; records = []
    for spec in plan["assets"]:
        payload = {"operation": spec["operation"], "prompt": spec["prompt"], "size": spec["size"]}
        if spec["operation"] == "style-reference":
            if not anchor_id: raise RuntimeError("Style anchor must be generated first.")
            payload["inputs"] = [{"asset_id": anchor_id}]
        request_id, outputs = request_sse(base, key, payload)
        if spec["name"] == plan["style_anchor"]: anchor_id = outputs[0]["id"]
        download(outputs[0]["assetUrl"], OUT / f"{spec['name']}.png")
        records.append({"request_id":request_id,"name":spec["name"],"operation":spec["operation"],"prompt":spec["prompt"],"outputs":outputs})
        print(f"{spec['name']}: {len(outputs)} output(s), selected index 0")
    HISTORY.write_text(json.dumps({"generated_at":datetime.now(timezone.utc).isoformat(),"requests":records}, indent=2), encoding="utf-8")
    print("Run build_arm.bat to normalize and pack the selected PNG files.")


if __name__ == "__main__":
    main()
