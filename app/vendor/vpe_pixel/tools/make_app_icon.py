#!/usr/bin/env python3
"""Render installer/app.ico — the file icon for both the app and the setup exe.

PIL is a build-time tool only (it is excluded from the PyInstaller build), so run
this before building:  python tools/make_app_icon.py
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "installer" / "app.ico"
SIZES = (16, 24, 32, 48, 64, 128, 256)

BG = "#0B0E14"
BORDER = "#2A3448"
# Same 4x4 mark the in-app window icon paints (main.make_app_icon).
CELLS = [
    "#4C8DFF", "#7B61FF", "#2DD4A0", "#F5A524",
    "#FF5C7A", "#FFFFFF", "#E8EEF8", "#4C8DFF",
    "#2DD4A0", "#F5A524", "#7B61FF", "#FF5C7A",
    "#FFFFFF", "#4C8DFF", "#E8EEF8", "#2DD4A0",
]


def render(px: int) -> Image.Image:
    img = Image.new("RGBA", (px, px), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    radius = max(1, px // 8)
    d.rounded_rectangle((0, 0, px - 1, px - 1), radius=radius, fill=BG,
                        outline=BORDER, width=max(1, px // 64))
    pad = max(1, int(px * 0.14))
    gap = max(1, int(px * 0.03))
    side = (px - 2 * pad - 3 * gap) // 4
    for i, color in enumerate(CELLS):
        x = pad + (i % 4) * (side + gap)
        y = pad + (i // 4) * (side + gap)
        d.rectangle((x, y, x + side - 1, y + side - 1), fill=color)
    return img


def main() -> int:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    master = render(256)
    master.save(str(OUT), sizes=[(s, s) for s in SIZES])
    print(f"wrote {OUT} ({OUT.stat().st_size} bytes, {len(SIZES)} sizes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
