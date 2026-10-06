"""Draw VQEAF OS system icons with the VXP Pixel Editor VPE565 pipeline.

Retro Utility palette (matches VQEAF_OS Theme.h RetroUtility):
  white  #FFFFFF  primary strokes
  amber  #FFCF00  accent / focus
  grey   #BDBDBD  secondary
  white  0xFFFF   VPE transparent key (exported as alpha)

Writes:
  Documents/VPE Pixel/tile/<name>_24.vpe
  Documents/VPE Pixel/sprite/<name>_36.vpe
  Documents/VPE Pixel/exports/vqeaf_icons_<24|36>.png   (RGBA, white keyed)
  Documents/VPE Pixel/exports/vqeaf_icons_sheet.png     contact sheet

Run from Pixel_Editor root:
  python tools/make_vqeaf_icons.py
"""

from __future__ import annotations

import struct
import sys
import zlib
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from vpx_editor.vpe import rgb_to_565, save_vpe  # noqa: E402

# --- Retro Utility tokens (RGB565) -----------------------------------------
# VPE uses 0xFFFF as the transparent key, so primary ink must NOT be pure white.
# Near-white #FFFFF0 packs to 0xFFDE and still reads as white on the black OS chrome.
INK = rgb_to_565(255, 255, 240)       # near-white stroke
ACCENT = rgb_to_565(255, 207, 0)      # amber #FFCF00 -> 0xFE60
DIM = rgb_to_565(189, 189, 189)       # grey  #BDBDBD -> 0xBDF7
CLEAR = 0xFFFF                        # VPE transparent key

PAL: Dict[str, int] = {".": CLEAR, "#": INK, "A": ACCENT, "G": DIM}


class Img:
    """Minimal RGB565 canvas (same contract as tools/make_samples.Img)."""

    def __init__(self, w: int, h: int, fill: int = CLEAR) -> None:
        self.w, self.h = w, h
        self.px: List[int] = [fill] * (w * h)

    def set(self, x: int, y: int, c: int) -> None:
        x, y = int(x), int(y)
        if 0 <= x < self.w and 0 <= y < self.h:
            self.px[y * self.w + x] = c

    def rect(self, x: int, y: int, w: int, h: int, c: int) -> None:
        for j in range(int(h)):
            for i in range(int(w)):
                self.set(x + i, y + j, c)

    def frame(self, x: int, y: int, w: int, h: int, c: int, t: int = 1) -> None:
        for i in range(w):
            for k in range(t):
                self.set(x + i, y + k, c)
                self.set(x + i, y + h - 1 - k, c)
        for j in range(h):
            for k in range(t):
                self.set(x + k, y + j, c)
                self.set(x + w - 1 - k, y + j, c)

    def circle(self, cx: int, cy: int, r: int, c: int, filled: bool = False) -> None:
        for j in range(-r, r + 1):
            for i in range(-r, r + 1):
                d = i * i + j * j
                if filled:
                    if d <= r * r + r:
                        self.set(cx + i, cy + j, c)
                else:
                    lo = (r - 1) * (r - 1) - (r - 1)
                    hi = r * r + r
                    if lo <= d <= hi:
                        self.set(cx + i, cy + j, c)

    def line(self, x0: int, y0: int, x1: int, y1: int, c: int) -> None:
        dx, dy = abs(x1 - x0), -abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx + dy
        while True:
            self.set(x0, y0, c)
            if x0 == x1 and y0 == y1:
                return
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                x0 += sx
            if e2 <= dx:
                err += dx
                y0 += sy

    def stamp(self, x: int, y: int, rows: Sequence[str], scale: int = 1) -> None:
        for j, row in enumerate(rows):
            for i, ch in enumerate(row):
                c = PAL.get(ch)
                if c is None or c == CLEAR:
                    continue
                if scale == 1:
                    self.set(x + i, y + j, c)
                else:
                    self.rect(x + i * scale, y + j * scale, scale, scale, c)


# 12x12 design tiles. Near-white stroke, amber accent, grey secondary.
# Scale 2 -> 24x24, scale 3 -> 36x36.
ICONS: Dict[str, List[str]] = {
    "wifi": [
        "............",
        "....####....",
        "..##....##..",
        ".#........#.",
        "#....##....#",
        "#...#..#...#",
        ".#..#..#..#.",
        "..#.#..#.#..",
        "...#.AA.#...",
        "....#..#....",
        ".....AA.....",
        "............",
    ],
    "bluetooth": [
        "............",
        ".....###....",
        ".....#A#....",
        "....##A##...",
        "....#.#A#...",
        "....##A##...",
        "....##A##...",
        "....#.#A#...",
        "....##A##...",
        ".....#A#....",
        ".....###....",
        "............",
    ],
    "music": [
        "............",
        ".........##.",
        ".........#A.",
        ".........#A.",
        ".........#A.",
        ".........#A.",
        ".........#A.",
        ".####....#A.",
        "#AAAA#...#A.",
        "#AAA#######.",
        "#AAA#.......",
        ".###........",
    ],
    "files": [
        "............",
        ".#####......",
        ".#AAA######.",
        ".#AAA......#",
        ".#.........#",
        ".#.........#",
        ".#.........#",
        ".#.........#",
        ".#.........#",
        ".##########.",
        "............",
        "............",
    ],
    "gallery": [
        "............",
        "############",
        "#..........#",
        "#....AA....#",
        "#...AAAA...#",
        "#..AA..AA..#",
        "#....##....#",
        "#...####...#",
        "#..######..#",
        "############",
        "............",
        "............",
    ],
    "internet": [
        "............",
        "....####....",
        "..##....##..",
        ".#...##...#.",
        "#....##....#",
        "#...####...#",
        "#....##....#",
        ".#...##...#.",
        "..##....##..",
        "....####....",
        ".....AA.....",
        "............",
    ],
    "shell": [
        "............",
        "############",
        "#..........#",
        "#.##.......#",
        "#...#......#",
        "#...#......#",
        "#.##.......#",
        "#..........#",
        "#....AAAAA.#",
        "############",
        "............",
        "............",
    ],
    "recovery": [
        "............",
        "....####....",
        "..##....##..",
        ".#...AA...#.",
        "#....AA....#",
        "#...#AA#...#",
        "#...####...#",
        ".#........#.",
        "..##....##..",
        "....####....",
        ".....AA.....",
        "............",
    ],
    "settings": [
        "............",
        "....#..#....",
        "...#....#...",
        "..##.##.##..",
        ".#..####..#.",
        ".#.##AA##.#.",
        ".#..####..#.",
        "..##.##.##..",
        "...#....#...",
        "....#..#....",
        "............",
        "............",
    ],
    "themes": [
        "............",
        "...######...",
        "..#......#..",
        ".#..A..G..#.",
        "#...A...G..#",
        "#.........A#",
        "#..........#",
        ".#........#.",
        "..#......#..",
        "...######...",
        "............",
        "............",
    ],
    "apps": [
        "............",
        "######.#####",
        "#....#.#...#",
        "#.AA.#.#.A.#",
        "#....#.#...#",
        "######.#####",
        "######.#####",
        "#....#.#...#",
        "#.AA.#.#.A.#",
        "#....#.#...#",
        "######.#####",
        "............",
    ],
    "library": [
        "............",
        "############",
        "#..........#",
        "#.########.#",
        "#.#......#.#",
        "#.#.AAAA.#.#",
        "#.#......#.#",
        "#.########.#",
        "#..........#",
        "############",
        "............",
        "............",
    ],
}


def draw_icon(name: str, size: int) -> Img:
    """Render a 12x12 stamp centered on a size x size canvas."""
    rows = ICONS[name]
    scale = size // 12
    if scale * 12 != size:
        raise ValueError(f"size {size} is not a multiple of 12")
    img = Img(size, size, CLEAR)
    img.stamp((size - 12 * scale) // 2, (size - 12 * scale) // 2, rows, scale)
    return img


def encode_png_rgba(path: Path, w: int, h: int, pixels: Sequence[int]) -> None:
    """Write RGBA PNG; 0xFFFF becomes fully transparent."""
    raw = bytearray()
    for y in range(h):
        raw.append(0)  # filter: none
        for x in range(w):
            c = pixels[y * w + x] & 0xFFFF
            if c == 0xFFFF:
                raw.extend((0, 0, 0, 0))
                continue
            r = ((c >> 11) & 31) * 255 // 31
            g = ((c >> 5) & 63) * 255 // 63
            b = (c & 31) * 255 // 31
            raw.extend((r, g, b, 255))

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    ihdr = struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0)
    blob = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
        + chunk(b"IEND", b"")
    )
    path.write_bytes(blob)


def main() -> int:
    names = list(ICONS.keys())
    tile_dir = Path.home() / "Documents" / "VPE Pixel" / "tile"
    sprite_dir = Path.home() / "Documents" / "VPE Pixel" / "sprite"
    export_dir = Path.home() / "Documents" / "VPE Pixel" / "exports"
    for d in (tile_dir, sprite_dir, export_dir):
        d.mkdir(parents=True, exist_ok=True)

    sheet_cell = 48
    sheet_cols = 6
    sheet_rows = 4  # 24-row + 36-row pairs
    sheet = Img(sheet_cols * sheet_cell, sheet_rows * sheet_cell, rgb_to_565(12, 12, 16))

    for name in names:
        for size, folder in ((24, tile_dir), (36, sprite_dir)):
            img = draw_icon(name, size)
            vpe_path = folder / f"{name}_{size}.vpe"
            save_vpe(vpe_path, size, size, img.px)
            png_path = export_dir / f"{name}_{size}.png"
            encode_png_rgba(png_path, size, size, img.px)

        # contact sheet: 24 then 36, two rows
        i = names.index(name)
        col = i % sheet_cols
        row24 = (i // sheet_cols) * 2
        row36 = row24 + 1
        im24 = draw_icon(name, 24)
        im36 = draw_icon(name, 36)
        ox24 = col * sheet_cell + (sheet_cell - 24) // 2
        oy24 = row24 * sheet_cell + (sheet_cell - 24) // 2
        ox36 = col * sheet_cell + (sheet_cell - 36) // 2
        oy36 = row36 * sheet_cell + (sheet_cell - 36) // 2
        for y in range(24):
            for x in range(24):
                c = im24.px[y * 24 + x]
                if c != CLEAR:
                    sheet.set(ox24 + x, oy24 + y, c)
        for y in range(36):
            for x in range(36):
                c = im36.px[y * 36 + x]
                if c != CLEAR:
                    sheet.set(ox36 + x, oy36 + y, c)
        print(f"OK {name}_24.vpe  {name}_36.vpe")

    encode_png_rgba(export_dir / "vqeaf_icons_sheet.png", sheet.w, sheet.h, sheet.px)
    print(f"sheet {export_dir / 'vqeaf_icons_sheet.png'}")
    print(f"vpe   {tile_dir}")
    print(f"vpe   {sprite_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
