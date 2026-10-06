"""Reject incomplete VPE Pixel payloads before freezing and before MSI harvest."""
import hashlib
import json
import sys
from pathlib import Path


def verify_bundle(root):
    root = Path(root)
    counts = {}
    for name in ("library", "tools"):
        entries = json.loads((root / f"{name}-manifest.json").read_text(encoding="utf-8"))["files"]
        if not entries:
            raise ValueError(f"Empty VPE Pixel {name}")
        for entry in entries:
            relative = Path(entry["path"])
            if relative.is_absolute() or ".." in relative.parts:
                raise ValueError("Invalid VPE Pixel payload path")
            data = (root / name / relative).read_bytes()
            if len(data) != entry["size"] or hashlib.sha256(data).hexdigest() != entry["sha256"]:
                raise ValueError(f"VPE Pixel payload mismatch: {name}/{relative}")
        counts[name] = len(entries)
    for name in ("dark.qss", "light.qss"):
        if not (root / "style" / name).is_file():
            raise ValueError(f"Missing VPE Pixel style: {name}")
    return counts


if __name__ == "__main__":
    print(verify_bundle(sys.argv[1]))
