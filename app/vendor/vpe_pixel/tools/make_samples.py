"""Procedurally draw sample game assets into the gallery category folders.

Run from the repo root:

    python tools/make_samples.py            # (re)generate all samples
    python tools/make_samples.py --only sprite

Assets are written as native VPE565 (.vpe) into:

    Documents\\VPE Pixel\\titleset   title screens, menus, HUD panels
    Documents\\VPE Pixel\\sprite     characters, items, FX frames
    Documents\\VPE Pixel\\texture     seamless surface sheets
    Documents\\VPE Pixel\\tile       16x16 map tiles

Every asset is deterministic (seeded), so re-running overwrites in place.
"""

from __future__ import annotations

import math
import random
import sys
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from vpx_editor.gallery import category_dir  # noqa: E402
from vpx_editor.vpe import save_vpe, c565_to_rgb  # noqa: E402


def rgb(r: int, g: int, b: int) -> int:
    return ((r & 0xFF) >> 3) << 11 | ((g & 0xFF) >> 2) << 5 | (b & 0xFF) >> 3


WHITE = rgb(255, 255, 255)
BLACK = rgb(0, 0, 0)


def mix(c1: Tuple[int, int, int], c2: Tuple[int, int, int], t: float) -> int:
    t = max(0.0, min(1.0, t))
    return rgb(
        int(c1[0] + (c2[0] - c1[0]) * t),
        int(c1[1] + (c2[1] - c1[1]) * t),
        int(c1[2] + (c2[2] - c1[2]) * t),
    )


class Img:
    def __init__(self, w: int, h: int, fill: int = WHITE) -> None:
        self.w, self.h = w, h
        self.px: List[int] = [fill] * (w * h)

    def set(self, x: int, y: int, c: int) -> None:
        x, y = int(x), int(y)
        if 0 <= x < self.w and 0 <= y < self.h:
            self.px[y * self.w + x] = c

    def get(self, x: int, y: int) -> int:
        if 0 <= x < self.w and 0 <= y < self.h:
            return self.px[y * self.w + x]
        return BLACK

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
        self.ellipse(cx, cy, r, r, c, filled)

    def ellipse(self, cx: int, cy: int, rx: int, ry: int, c: int,
                filled: bool = False) -> None:
        rx, ry = max(rx, 0), max(ry, 0)
        if rx == 0 or ry == 0:
            return
        for j in range(-ry, ry + 1):
            for i in range(-rx, rx + 1):
                d = (i / rx) ** 2 + (j / ry) ** 2
                if d <= 1.0 if filled else 1.0 - 2.4 / max(rx, ry) <= d <= 1.0:
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

    def tri(self, x0, y0, x1, y1, x2, y2, c) -> None:
        minx, maxx = min(x0, x1, x2), max(x0, x1, x2)
        miny, maxy = min(y0, y1, y2), max(y0, y1, y2)

        def edge(ax, ay, bx, by, px, py):
            return (bx - ax) * (py - ay) - (by - ay) * (px - ax)

        for y in range(miny, maxy + 1):
            for x in range(minx, maxx + 1):
                d1 = edge(x0, y0, x1, y1, x, y)
                d2 = edge(x1, y1, x2, y2, x, y)
                d3 = edge(x2, y2, x0, y0, x, y)
                neg = (d1 < 0) or (d2 < 0) or (d3 < 0)
                pos = (d1 > 0) or (d2 > 0) or (d3 > 0)
                if not (neg and pos):
                    self.set(x, y, c)

    def vgrad(self, x: int, y: int, w: int, h: int,
              c1: Tuple[int, int, int], c2: Tuple[int, int, int],
              dither: bool = True) -> None:
        for j in range(h):
            t = j / max(1, h - 1)
            for i in range(w):
                if dither:
                    # Bayer-ish 2x2 threshold for a chunky retro banding look
                    cell = ((j % 2) * 2 + (i % 2)) / 4.0
                    self.set(x + i, y + j,
                             rgb(*c1) if t < cell else mix(c1, c2, t))
                else:
                    self.set(x + i, y + j, mix(c1, c2, t))

    def speckle(self, x: int, y: int, w: int, h: int, colors: Sequence[int],
                density: float, rnd: random.Random) -> None:
        for j in range(h):
            for i in range(w):
                if rnd.random() < density:
                    self.set(x + i, y + j, rnd.choice(list(colors)))

    def stamp(self, x: int, y: int, rows: Sequence[str], pal: Dict[str, int],
              scale: int = 1) -> None:
        for j, row in enumerate(rows):
            for i, ch in enumerate(row):
                c = pal.get(ch)
                if c is None:
                    continue
                if scale == 1:
                    self.set(x + i, y + j, c)
                else:
                    self.rect(x + i * scale, y + j * scale, scale, scale, c)

    def text(self, x: int, y: int, s: str, c: int, scale: int = 1,
             tracking: int = 1, shadow: int = None, shadow_off: int = 1) -> int:
        cx = x
        for ch in s.upper():
            glyph = FONT.get(ch)
            if glyph:
                if shadow is not None:
                    self.stamp(cx + shadow_off, y + shadow_off, glyph, {"#": shadow}, scale)
                self.stamp(cx, y, glyph, {"#": c}, scale)
            cx += (GLYPH_W + tracking) * scale
        return cx

    def center_text(self, y: int, s: str, c: int, scale: int = 1,
                    shadow: int = None) -> None:
        width = len(s) * (GLYPH_W + 1) * scale - scale
        self.text((self.w - width) // 2, y, s, c, scale, shadow=shadow)


GLYPH_W = 3
FONT: Dict[str, List[str]] = {
    "A": [".#.", "#.#", "###", "#.#", "#.#"],
    "B": ["##.", "#.#", "##.", "#.#", "##."],
    "C": [".##", "#..", "#..", "#..", ".##"],
    "D": ["##.", "#.#", "#.#", "#.#", "##."],
    "E": ["###", "#..", "##.", "#..", "###"],
    "F": ["###", "#..", "##.", "#..", "#.."],
    "G": [".##", "#..", "#.#", "#.#", ".##"],
    "H": ["#.#", "#.#", "###", "#.#", "#.#"],
    "I": ["###", ".#.", ".#.", ".#.", "###"],
    "J": ["..#", "..#", "..#", "#.#", ".#."],
    "K": ["#.#", "#.#", "##.", "#.#", "#.#"],
    "L": ["#..", "#..", "#..", "#..", "###"],
    "M": ["#.#", "###", "###", "#.#", "#.#"],
    "N": ["#.#", "###", "###", "###", "#.#"],
    "O": [".#.", "#.#", "#.#", "#.#", ".#."],
    "P": ["##.", "#.#", "##.", "#..", "#.."],
    "Q": [".#.", "#.#", "#.#", ".#.", "..#"],
    "R": ["##.", "#.#", "##.", "#.#", "#.#"],
    "S": [".##", "#..", ".#.", "..#", "##."],
    "T": ["###", ".#.", ".#.", ".#.", ".#."],
    "U": ["#.#", "#.#", "#.#", "#.#", ".##"],
    "V": ["#.#", "#.#", "#.#", "#.#", ".#."],
    "W": ["#.#", "#.#", "###", "###", "#.#"],
    "X": ["#.#", "#.#", ".#.", "#.#", "#.#"],
    "Y": ["#.#", "#.#", ".#.", ".#.", ".#."],
    "Z": ["###", "..#", ".#.", "#..", "###"],
    "0": ["###", "#.#", "#.#", "#.#", "###"],
    "1": [".#.", "##.", ".#.", ".#.", "###"],
    "2": ["###", "..#", "###", "#..", "###"],
    "3": ["###", "..#", ".##", "..#", "###"],
    "4": ["#.#", "#.#", "###", "..#", "..#"],
    "5": ["###", "#..", "###", "..#", "###"],
    "6": ["###", "#..", "###", "#.#", "###"],
    "7": ["###", "..#", ".#.", ".#.", ".#."],
    "8": ["###", "#.#", "###", "#.#", "###"],
    "9": ["###", "#.#", "###", "..#", "###"],
    ".": ["...", "...", "...", "...", ".#."],
    ",": ["...", "...", "...", ".#.", "#.."],
    "-": ["...", "...", "###", "...", "..."],
    ":": ["...", ".#.", "...", ".#.", "..."],
    "!": [".#.", ".#.", ".#.", "...", ".#."],
    "?": ["###", "..#", ".##", "...", ".#."],
    "/": ["..#", "..#", ".#.", "#..", "#.."],
    ">": ["#..", ".#.", "..#", ".#.", "#.."],
    "<": ["..#", ".#.", "#..", ".#.", "..#"],
    "+": ["...", ".#.", "###", ".#.", "..."],
    "*": ["#.#", ".#.", "###", ".#.", "#.#"],
    "'": [".#.", ".#.", "...", "...", "..."],
    " ": ["...", "...", "...", "...", "..."],
}


# --------------------------------------------------------------- sprites
PAL_HERO = {
    "K": rgb(24, 20, 32), "H": rgb(120, 68, 36), "S": rgb(238, 186, 148),
    "E": rgb(28, 28, 40), "A": rgb(46, 128, 84), "B": rgb(96, 62, 36),
    "C": rgb(212, 176, 66), "D": rgb(30, 78, 52),
}
HERO_IDLE = [
    "...KKKKK...",
    "..KHHHHHK..",
    "..KHHHHHK..",
    "..KSSSSSK..",
    "..KSEKSEK..",
    "..KSSSSSK..",
    "...KSSSK...",
    "..KKAAAKK..",
    ".KACAAACAK.",
    ".KAADAADAK.",
    "..KAAAAAK..",
    "..KABABAK..",
    "...KBBBK...",
    "...KB.BK...",
    "..KBB.BBK..",
]
HERO_WALK = [
    "...KKKKK...",
    "..KHHHHHK..",
    "..KHHHHHK..",
    "..KSSSSSK..",
    "..KSEKSEK..",
    "..KSSSSSK..",
    "...KSSSK...",
    "..KKAAAKK..",
    ".KACAAACAK.",
    ".KAADAADAK.",
    "..KAAAAAK..",
    "..KABABAK..",
    "...KBBBK...",
    "..KBK.KBK..",
    ".KBBK.KBBK.",
]
HERO_WIDE = [
    "...KKKKK...",
    "..KHHHHHK..",
    "..KHHHHHK..",
    "..KSSSSSK..",
    "..KSEKSEK..",
    "..KSSSSSK..",
    "...KSSSK...",
    "..KKAAAKK..",
    ".KACAAACAK.",
    ".KAADAADAK.",
    "..KAAAAAK..",
    "..KABABAK..",
    "...KBBBK...",
    "..KBB.BBK..",
    ".KBK...KBK.",
]

PAL_SLIME = {"K": rgb(16, 40, 28), "G": rgb(52, 190, 110), "L": rgb(140, 240, 170),
             "E": rgb(20, 26, 30), "W": rgb(255, 255, 255)}
SLIME_A = [
    "....KKK....",
    "..KKGGGKK..",
    ".KGLGGGGGK.",
    "KGLGGGGGGGK",
    "KGGGEGGEGGK",
    "KGGGEGGEGGK",
    "KGGGGGGGGGK",
    ".KGGGGGGGK.",
    "..KKKKKKK..",
]
SLIME_B = [
    "...........",
    "...KKKKK...",
    "..KGLGGGK..",
    ".KGLGGGGGK.",
    "KGGGEGGEGGK",
    "KGGGGGGGGGK",
    "KGGGGGGGGGK",
    ".KGGGGGGGK.",
    "..KKKKKKK..",
]

PAL_BAT = {"K": rgb(20, 16, 28), "P": rgb(120, 62, 168), "D": rgb(72, 32, 106),
           "E": rgb(255, 92, 122), "F": rgb(232, 208, 244)}
BAT_UP = [
    "K.........K",
    "KK...KK...KK",
    "KPK.KPPK.KPK",
    "KPPKPPPPKPPK",
    ".KPDPEEPDPK.",
    "..KPPPPPK...",
    "...KFEFK....",
    "....KKK.....",
]
BAT_DOWN = [
    "............",
    "...KKKKK....",
    "..KPPPPPK...",
    "K.KPDPEEPK.K",
    "KKKPPPPPPKKK",
    ".KPKPPPPKPK.",
    "..K.KFEFK...",
    "....KKK.....",
]

PAL_GHOST = {"K": rgb(28, 34, 56), "B": rgb(176, 208, 244), "L": rgb(232, 244, 255),
             "E": rgb(28, 34, 56), "M": rgb(120, 150, 200)}
GHOST_A = [
    "...KKKKK...",
    "..KBLLLBK..",
    ".KBLLLLLBK.",
    ".KBELLLEBK.",
    ".KBELLLLEK.",
    ".KBLLLLLLBK",
    ".KBMMLLMBK.",
    ".KBLLLLLLBK",
    ".K.KBKBK.K.",
]
GHOST_B = [
    "...KKKKK...",
    "..KBLLLBK..",
    ".KBLLLLLBK.",
    ".KBELLLLEK.",
    ".KBLLLLLLBK",
    ".KBMLLMLLBK",
    ".KBLLLLLLBK",
    ".KBBKBKBBK.",
    "..K.K.K.K..",
]


def sprite_canvas(size: int = 16) -> Img:
    return Img(size, size, WHITE)


def draw_hero(frame: int) -> Img:
    img = sprite_canvas(16)
    art = [HERO_IDLE, HERO_WALK, HERO_IDLE, HERO_WIDE][frame % 4]
    img.stamp(2, 0, art, PAL_HERO)
    return img


def draw_slime(frame: int) -> Img:
    img = sprite_canvas(16)
    img.stamp(2, 4, SLIME_A if frame % 2 == 0 else SLIME_B, PAL_SLIME)
    return img


def draw_bat(frame: int) -> Img:
    img = sprite_canvas(16)
    img.stamp(2, 4, BAT_UP if frame % 2 == 0 else BAT_DOWN, PAL_BAT)
    return img


def draw_ghost(frame: int) -> Img:
    img = sprite_canvas(16)
    img.stamp(2, 3, GHOST_A if frame % 2 == 0 else GHOST_B, PAL_GHOST)
    return img


def draw_coin(frame: int) -> Img:
    """Spin cycle: face-on disc -> narrower -> edge-on -> narrower."""
    img = sprite_canvas(8)
    gold, hi, lo, k = (rgb(252, 208, 60), rgb(255, 246, 190),
                       rgb(168, 116, 20), rgb(120, 80, 12))
    rx = [3, 2, 1, 2][frame % 4]
    cx, cy = 4, 4
    img.ellipse(cx, cy, rx, 3, k, filled=True)
    img.ellipse(cx, cy, max(1, rx - 1), 2, gold, filled=True)
    if rx >= 2:
        img.ellipse(cx - 1, cy - 1, max(1, rx - 2), 1, hi, filled=True)
        img.set(cx + 1, cy + 1, lo)
    if rx == 1:
        img.rect(cx, cy - 2, 1, 5, hi)
    return img


def draw_key() -> Img:
    img = sprite_canvas(16)
    g, gd = rgb(236, 196, 84), rgb(150, 110, 24)
    img.circle(5, 5, 3, g, filled=True)
    img.circle(5, 5, 1, WHITE, filled=True)
    img.line(7, 7, 13, 13, g)
    img.line(11, 13, 13, 11, gd)
    img.line(9, 13, 11, 11, gd)
    img.circle(5, 5, 3, gd)
    return img


def draw_potion(kind: str) -> Img:
    img = sprite_canvas(16)
    glass = rgb(190, 214, 236)
    liquid = {"red": rgb(226, 46, 78), "green": rgb(58, 200, 112),
              "blue": rgb(56, 122, 232)}[kind]
    img.rect(6, 1, 4, 3, rgb(150, 110, 40))
    img.rect(5, 4, 6, 2, glass)
    img.circle(8, 10, 4, glass, filled=True)
    img.circle(8, 10, 3, liquid, filled=True)
    img.rect(5, 9, 2, 3, mix((226, 46, 78), (255, 255, 255), 0.35) if kind == "red" else liquid)
    img.frame(4, 6, 8, 8, rgb(40, 44, 60))
    return img


def draw_sword(flip: bool) -> Img:
    img = sprite_canvas(16)
    blade, edge, shade = rgb(188, 200, 216), rgb(244, 248, 255), rgb(120, 132, 150)
    wood, gold, k = rgb(122, 78, 38), rgb(232, 190, 70), rgb(30, 30, 44)
    # 2px wide diagonal blade from bottom-left hilt to top-right tip
    for i in range(9):
        x, y = 4 + i, 11 - i
        img.set(x, y, edge)
        img.set(x + 1, y, blade)
        img.set(x, y + 1, shade)
    img.set(13, 2, edge)
    img.set(14, 2, blade)
    img.line(2, 13, 6, 9, gold)      # cross-guard
    img.line(3, 14, 7, 10, gold)
    img.line(1, 13, 3, 15, wood)     # grip
    img.line(0, 14, 2, 16, wood)
    img.set(0, 15, gold)             # pommel
    if flip:
        out = sprite_canvas(16)
        for y in range(16):
            for x in range(16):
                out.set(15 - x, y, img.get(x, y))
        return out
    return img


def draw_chest(opened: bool) -> Img:
    img = sprite_canvas(16)
    wood, wd, gold = rgb(150, 96, 46), rgb(96, 58, 26), rgb(232, 190, 70)
    rnd = random.Random(11)
    img.rect(1, 6, 14, 8, wood)
    img.speckle(1, 6, 14, 8, [wd], 0.18, rnd)
    img.frame(1, 6, 14, 8, wd)
    if opened:
        img.rect(1, 1, 14, 3, wd)
        img.rect(2, 2, 12, 1, wood)
        img.rect(2, 7, 12, 2, rgb(20, 16, 20))
        img.speckle(2, 8, 12, 1, [gold, rgb(255, 236, 140)], 0.6, rnd)
    else:
        img.rect(1, 3, 14, 4, wood)
        img.frame(1, 3, 14, 4, wd)
        img.speckle(1, 3, 14, 4, [wd], 0.14, rnd)
    img.rect(1, 6, 14, 1, gold)
    img.rect(7, 5, 2, 4, gold)
    img.set(7, 7, wd)
    return img


def draw_heart(full: bool) -> Img:
    img = sprite_canvas(16)
    red, hi = rgb(226, 40, 82), rgb(255, 128, 150)
    empty = rgb(58, 62, 84)
    body = red if full else empty
    art = [
        ".KK..KK.",
        "KRRKKRRK",
        "KRHRRRRK",
        "KRRRRRRK",
        ".KRRRRK.",
        "..KRRK..",
        "...KK...",
    ]
    pal = {"K": rgb(28, 12, 22) if full else rgb(20, 22, 34),
           "R": body, "H": hi if full else body}
    img.stamp(4, 4, art, pal)
    return img


def draw_ship() -> Img:
    img = sprite_canvas(16)
    hull, hull2, dark = rgb(206, 216, 232), rgb(132, 148, 178), rgb(52, 60, 80)
    glow, flame = rgb(96, 214, 255), rgb(252, 158, 60)
    # Nose cone
    img.tri(8, 0, 5, 6, 11, 6, hull)
    img.line(8, 1, 8, 6, hull2)
    # Body
    img.rect(5, 6, 7, 6, hull)
    img.rect(5, 6, 7, 1, hull2)
    img.frame(5, 6, 7, 6, dark)
    img.circle(8, 9, 2, glow, filled=True)
    img.circle(8, 9, 1, rgb(226, 250, 255), filled=True)
    # Wings
    img.tri(5, 8, 1, 14, 5, 14, hull2)
    img.tri(11, 8, 15, 14, 11, 14, hull2)
    img.line(1, 14, 5, 14, dark)
    img.line(11, 14, 15, 14, dark)
    # Engines
    img.rect(6, 12, 2, 2, dark)
    img.rect(9, 12, 2, 2, dark)
    img.rect(6, 14, 2, 2, flame)
    img.rect(9, 14, 2, 2, flame)
    return img


def draw_bullet(frame: int) -> Img:
    img = sprite_canvas(8)
    k = rgb(120, 60, 10)
    core = rgb(255, 250, 220) if frame % 2 == 0 else rgb(255, 214, 120)
    img.circle(4, 4, 2, k, filled=True)
    img.circle(4, 4, 1, core, filled=True)
    img.set(4, 4, rgb(255, 255, 255))
    return img


def draw_explosion(frame: int) -> Img:
    img = sprite_canvas(24)
    rnd = random.Random(40 + frame)
    rings = [
        (rgb(255, 252, 220), 2),
        (rgb(255, 196, 70), 5),
        (rgb(240, 96, 48), 8),
        (rgb(120, 40, 44), 11),
    ][: frame + 1]
    for c, r in reversed(rings):
        img.circle(12, 12, r + frame, c, filled=True)
    for _ in range(10 + frame * 6):
        a = rnd.uniform(0, math.tau)
        d = rnd.uniform(0, 4 + frame * 3.5)
        img.set(int(12 + math.cos(a) * d), int(12 + math.sin(a) * d),
                rnd.choice([rgb(255, 232, 150), rgb(255, 150, 60), rgb(90, 40, 40)]))
    return img


def draw_mushroom() -> Img:
    img = sprite_canvas(16)
    cap, cap2, dot, stem, k = (rgb(222, 62, 74), rgb(170, 38, 54),
                               rgb(252, 240, 224), rgb(236, 214, 186), rgb(46, 24, 30))
    img.rect(4, 4, 8, 1, cap)
    img.rect(3, 5, 10, 1, cap)
    img.rect(2, 6, 12, 3, cap)
    img.rect(3, 9, 10, 1, cap2)
    img.circle(5, 7, 1, dot, filled=True)
    img.circle(10, 6, 1, dot, filled=True)
    img.circle(8, 8, 1, dot, filled=True)
    img.rect(6, 10, 4, 4, stem)
    img.rect(6, 10, 1, 4, rgb(206, 182, 154))
    img.rect(5, 14, 6, 1, k)
    img.set(2, 6, k); img.set(13, 6, k)
    img.line(2, 8, 2, 8, k)
    return img


def draw_tree() -> Img:
    img = sprite_canvas(16)
    leaf, leaf2, trunk, k = rgb(46, 140, 74), rgb(78, 178, 96), rgb(120, 82, 44), rgb(20, 40, 24)
    img.circle(8, 5, 4, leaf, filled=True)
    img.circle(6, 6, 3, leaf, filled=True)
    img.circle(10, 6, 3, leaf, filled=True)
    img.circle(7, 4, 2, leaf2, filled=True)
    img.rect(7, 9, 2, 6, trunk)
    img.frame(7, 9, 2, 6, k)
    rnd = random.Random(7)
    img.speckle(3, 1, 11, 9, [k], 0.08, rnd)
    return img


# ------------------------------------------------------------------ tiles
def tile_base(color: Tuple[int, int, int], shade: float = 0.18, seed: int = 3) -> Tuple[Img, random.Random]:
    img = Img(16, 16, rgb(*color))
    rnd = random.Random(seed)
    dark = tuple(int(c * (1 - shade)) for c in color)
    # 255 on all three channels encodes to 0xFFFF, which the editor uses for
    # transparency - keep highlights one step below it.
    light = tuple(min(248, int(c * (1 + shade))) for c in color)
    img.speckle(0, 0, 16, 16, [rgb(*dark), rgb(*light)], 0.28, rnd)
    return img, rnd


def draw_grass() -> Img:
    img, rnd = tile_base((74, 158, 72), seed=21)
    for _ in range(26):
        x, y = rnd.randrange(16), rnd.randrange(16)
        img.set(x, y, rgb(120, 208, 110))
        img.set(x, max(0, y - 1), rgb(46, 118, 56))
    return img


def draw_dirt() -> Img:
    img, rnd = tile_base((126, 88, 52), seed=22)
    for _ in range(8):
        x, y = rnd.randrange(14), rnd.randrange(14)
        img.rect(x, y, 2, 2, rgb(92, 62, 36))
    return img


def draw_stone_floor() -> Img:
    img, rnd = tile_base((118, 124, 136), seed=23)
    img.line(0, 7, 15, 7, rgb(70, 76, 88))
    img.line(7, 0, 7, 6, rgb(70, 76, 88))
    img.line(3, 8, 3, 15, rgb(70, 76, 88))
    img.line(11, 8, 11, 15, rgb(70, 76, 88))
    return img


def draw_wall_brick() -> Img:
    img, rnd = tile_base((156, 76, 62), seed=24)
    mortar = rgb(206, 196, 176)
    img.rect(0, 0, 16, 1, mortar)
    img.rect(0, 7, 16, 1, mortar)
    img.rect(0, 15, 16, 1, mortar)
    img.rect(7, 1, 1, 6, mortar)
    img.rect(3, 8, 1, 7, mortar)
    img.rect(12, 8, 1, 7, mortar)
    return img


def draw_water(frame: int) -> Img:
    img, rnd = tile_base((46, 108, 196), seed=30 + frame)
    for row, alpha in ((3, 1.0), (9, 0.75), (13, 0.5)):
        c = mix((46, 108, 196), (176, 226, 255), alpha)
        for x in range(16):
            if (x + row * 3 + frame * 4) % 8 < 4:
                img.set(x, row, c)
                img.set(x, row + 1, mix((46, 108, 196), (120, 180, 236), alpha * 0.5))
    return img


def draw_lava(frame: int) -> Img:
    img, rnd = tile_base((96, 30, 20), seed=34 + frame)
    for _ in range(18):
        x, y = rnd.randrange(16), rnd.randrange(16)
        img.set(x, y, rnd.choice([rgb(252, 168, 40), rgb(238, 96, 24), rgb(160, 44, 18)]))
    for row in (4, 11):
        for x in range(16):
            if (x + row * 2 + frame * 3) % 11 < 5:
                img.set(x, row, rgb(255, 214, 96))
    return img


def draw_sand() -> Img:
    img, rnd = tile_base((214, 188, 128), seed=25)
    for _ in range(14):
        x, y = rnd.randrange(15), rnd.randrange(15)
        img.rect(x, y, 2, 1, rgb(238, 216, 160))
    return img


def draw_snow() -> Img:
    img, rnd = tile_base((226, 236, 248), seed=26)
    for _ in range(12):
        x, y = rnd.randrange(16), rnd.randrange(16)
        img.set(x, y, rgb(196, 214, 236))
    return img


def draw_spike() -> Img:
    img, _ = tile_base((88, 92, 104), seed=27)
    img.rect(0, 13, 16, 3, rgb(60, 64, 74))
    steel, tip, shade = rgb(176, 188, 204), rgb(240, 246, 255), rgb(96, 104, 120)
    for bx in (1, 6, 11):
        img.tri(bx, 14, bx + 2, 2, bx + 4, 14, steel)
        img.line(bx + 2, 2, bx + 2, 3, tip)
        img.line(bx + 1, 13, bx + 2, 4, shade)
    return img


def draw_ladder() -> Img:
    img = sprite_canvas(16)
    wood, wd = rgb(168, 118, 58), rgb(108, 72, 32)
    img.rect(3, 0, 2, 16, wood)
    img.rect(11, 0, 2, 16, wood)
    img.frame(3, 0, 2, 16, wd)
    img.frame(11, 0, 2, 16, wd)
    for y in (2, 7, 12):
        img.rect(3, y, 10, 2, wood)
        img.rect(3, y + 1, 10, 1, wd)
    return img


def draw_checkpoint() -> Img:
    img, _ = tile_base((104, 108, 122), seed=28)
    img.rect(7, 2, 2, 13, rgb(140, 96, 44))
    img.rect(9, 3, 6, 4, rgb(238, 62, 74))
    img.rect(9, 4, 6, 1, rgb(252, 140, 150))
    img.rect(6, 14, 4, 2, rgb(70, 74, 86))
    return img


def draw_hole() -> Img:
    img, rnd = tile_base((74, 158, 72), seed=29)
    img.circle(8, 8, 6, rgb(30, 24, 22), filled=True)
    img.circle(8, 8, 5, rgb(14, 12, 14), filled=True)
    img.speckle(2, 2, 12, 12, [rgb(52, 44, 40)], 0.1, rnd)
    return img


def draw_bridge() -> Img:
    img = Img(16, 16, WHITE)
    rnd = random.Random(33)
    wood, wd, rope = rgb(154, 106, 56), rgb(104, 68, 32), rgb(196, 172, 120)
    img.line(0, 2, 15, 4, rope)          # hand rope
    for x in range(0, 16, 4):
        img.line(x + 1, 3, x + 1, 7, rope)   # hangers
    img.rect(0, 7, 16, 6, wood)
    img.speckle(0, 7, 16, 6, [wd], 0.18, rnd)
    img.frame(0, 7, 16, 6, wd)
    for x in (3, 7, 11, 15):
        img.line(x, 7, x, 12, wd)        # plank gaps
    img.rect(0, 13, 16, 3, rgb(28, 30, 40))  # gap below the bridge
    return img


def draw_torch(frame: int) -> Img:
    img, _ = tile_base((118, 124, 136), seed=41)
    img.rect(7, 8, 2, 7, rgb(120, 82, 44))
    fire = rgb(255, 208, 90) if frame % 2 == 0 else rgb(252, 150, 46)
    img.circle(8, 6, 2, fire, filled=True)
    img.circle(8, 5, 1, rgb(255, 246, 190), filled=True)
    return img


def draw_door(state: str) -> Img:
    img, _ = tile_base((118, 124, 136), seed=42)
    wood, wd = rgb(146, 92, 44), rgb(88, 56, 26)
    img.rect(2, 1, 12, 15, wd)
    if state == "open":
        img.rect(3, 2, 10, 14, rgb(18, 16, 24))
    else:
        img.rect(3, 2, 10, 14, wood)
        img.frame(4, 3, 8, 5, wd)
        img.frame(4, 9, 8, 6, wd)
        img.circle(11, 9, 1, rgb(236, 196, 84), filled=True)
    return img


# -------------------------------------------------------------- textures
def draw_brick_wall(size: int = 64) -> Img:
    img = Img(size, size, rgb(150, 72, 58))
    rnd = random.Random(51)
    mortar = rgb(206, 196, 176)
    bh, bw = 8, 16
    for row in range(size // bh):
        y = row * bh
        img.rect(0, y, size, 1, mortar)
        offset = (bw // 2) if row % 2 else 0
        for col in range(-1, size // (bw // 1) + 2):
            x = col * bw + offset
            img.rect(x, y + 1, 1, bh - 1, mortar)
        for col in range(size // bw + 2):
            x = col * bw + offset
            img.speckle(x + 1, y + 2, bw - 2, bh - 3,
                        [rgb(122, 56, 46), rgb(172, 92, 70)], 0.25, rnd)
    return img


def draw_cobble(size: int = 64) -> Img:
    img = Img(size, size, rgb(78, 84, 96))
    rnd = random.Random(52)
    for _ in range(46):
        cx, cy = rnd.randrange(size), rnd.randrange(size)
        r = rnd.randrange(4, 9)
        tone = rnd.choice([(126, 132, 144), (104, 110, 122), (146, 152, 164)])
        img.circle(cx, cy, r, rgb(*tone), filled=True)
        img.circle(cx, cy, r, rgb(52, 56, 66))
    img.speckle(0, 0, size, size, [rgb(158, 164, 176), rgb(60, 64, 74)], 0.12, rnd)
    return img


def draw_wood(size: int = 64) -> Img:
    img = Img(size, size, rgb(140, 94, 48))
    rnd = random.Random(53)
    for plank in range(size // 16):
        y = plank * 16
        img.rect(0, y, size, 16, rgb(146 - plank * 6, 98 - plank * 4, 50))
        img.rect(0, y + 15, size, 1, rgb(84, 52, 24))
        for _ in range(30):
            gy = y + rnd.randrange(2, 14)
            gx = rnd.randrange(size)
            img.line(gx, gy, min(size - 1, gx + rnd.randrange(6, 26)), gy, rgb(112, 72, 36))
        for _ in range(3):
            kx, ky = rnd.randrange(size), y + rnd.randrange(3, 13)
            img.circle(kx, ky, 2, rgb(96, 60, 28), filled=True)
            img.circle(kx, ky, 1, rgb(126, 84, 42), filled=True)
    return img


def draw_metal(size: int = 64) -> Img:
    img = Img(size, size, rgb(132, 142, 158))
    rnd = random.Random(54)
    for y in range(size):
        c = mix((104, 114, 132), (176, 188, 204), abs(math.sin(y / 7.0)))
        img.rect(0, y, size, 1, c)
    img.speckle(0, 0, size, size, [rgb(96, 104, 118), rgb(196, 206, 220)], 0.08, rnd)
    img.frame(0, 0, size, size, rgb(64, 72, 86), 2)
    for rx, ry in ((6, 6), (size - 8, 6), (6, size - 8), (size - 8, size - 8),
                   (size // 2 - 1, 6), (size // 2 - 1, size - 8)):
        img.circle(rx, ry, 2, rgb(84, 92, 106), filled=True)
        img.set(rx, ry, rgb(206, 216, 228))
    return img


def draw_lava_flow(size: int = 64) -> Img:
    img = Img(size, size, rgb(64, 18, 14))
    rnd = random.Random(55)
    for y in range(size):
        for x in range(size):
            n = math.sin((x + y * 0.6) / 6.0) + math.sin((x * 0.5 - y) / 9.0)
            t = (n + 2) / 4.0
            if t > 0.72:
                c = mix((238, 108, 26), (255, 226, 110), (t - 0.72) / 0.28)
            elif t > 0.45:
                c = mix((140, 40, 20), (238, 108, 26), (t - 0.45) / 0.27)
            else:
                c = mix((40, 14, 14), (140, 40, 20), t / 0.45)
            img.set(x, y, c)
    img.speckle(0, 0, size, size, [rgb(28, 10, 10), rgb(255, 240, 160)], 0.05, rnd)
    return img


def draw_water_ripple(size: int = 64) -> Img:
    img = Img(size, size, rgb(28, 76, 148))
    for y in range(size):
        for x in range(size):
            n = math.sin(x / 5.0 + math.sin(y / 9.0) * 1.6) + math.cos(y / 7.0)
            t = (n + 2) / 4.0
            img.set(x, y, mix((24, 66, 132), (146, 214, 246), t ** 1.6))
    return img


def draw_grass_sheet(size: int = 64) -> Img:
    img = Img(size, size, rgb(58, 132, 62))
    rnd = random.Random(56)
    img.speckle(0, 0, size, size, [rgb(78, 158, 74), rgb(44, 108, 52), rgb(112, 188, 96)],
                0.5, rnd)
    for _ in range(140):
        x, y = rnd.randrange(size), rnd.randrange(size - 2)
        img.set(x, y, rgb(126, 200, 108))
        img.set(x, y + 1, rgb(40, 96, 46))
    return img


def draw_hud_bar(size: Tuple[int, int] = (240, 32)) -> Img:
    w, h = size
    img = Img(w, h, rgb(20, 24, 34))
    img.frame(0, 0, w, h, rgb(96, 176, 244), 1)
    img.vgrad(2, 2, w - 4, h - 4, (34, 44, 66), (16, 20, 30), dither=False)
    img.text(8, 9, "HP", rgb(252, 240, 200), 1)
    inner = w - 40
    img.frame(26, 8, inner, h - 16, rgb(64, 74, 94))
    filled = int(inner * 0.68) - 2
    img.vgrad(27, 9, filled, h - 18, (238, 74, 92), (150, 30, 46), dither=False)
    for x in range(27, 27 + filled, 8):
        img.line(x, 9, x + 3, h - 10, rgb(255, 168, 176))
    img.text(w - 34, 9, "68", rgb(252, 240, 200), 1)
    return img


def draw_menu_panel(size: Tuple[int, int] = (160, 128)) -> Img:
    w, h = size
    img = Img(w, h, rgb(18, 22, 32))
    img.vgrad(3, 3, w - 6, h - 6, (44, 58, 92), (20, 26, 40), dither=False)
    img.frame(0, 0, w, h, rgb(120, 190, 250), 2)
    img.frame(4, 4, w - 8, h - 8, rgb(52, 78, 128))
    img.rect(4, 16, w - 8, 2, rgb(88, 138, 208))
    img.center_text(6, "OPTIONS", rgb(236, 244, 255), 1, shadow=rgb(20, 26, 40))
    for i, label in enumerate(("SOUND ON", "GFX HIGH", "SPEED MID", "BACK")):
        y = 28 + i * 22
        img.rect(10, y - 3, w - 20, 14, rgb(36, 48, 76) if i % 2 else rgb(28, 38, 62))
        img.text(16, y, label, rgb(226, 236, 250), 1)
    img.text(3, 25, ">", rgb(252, 214, 96), 1)
    return img


# ------------------------------------------------------------- title sets
def stars(img: Img, count: int, rnd: random.Random, top: int = None) -> None:
    for _ in range(count):
        x, y = rnd.randrange(img.w), rnd.randrange(top or img.h)
        c = rnd.choice([rgb(255, 255, 255), rgb(196, 214, 244), rgb(140, 166, 210)])
        img.set(x, y, c)
        if rnd.random() < 0.12:
            img.set(x + 1, y, c)
            img.set(x, y + 1, c)


def title_rpg() -> Img:
    w, h = 240, 320
    img = Img(w, h, BLACK)
    rnd = random.Random(101)
    img.vgrad(0, 0, w, 190, (18, 22, 62), (232, 128, 74), dither=False)
    stars(img, 220, rnd, top=110)
    img.circle(168, 96, 22, rgb(255, 226, 140), filled=True)
    img.circle(160, 90, 20, rgb(255, 246, 200), filled=True)
    img.circle(176, 100, 20, mix((232, 128, 74), (255, 226, 140), 0.5), filled=True)
    for peak, htone in ((40, (36, 44, 84)), (120, (28, 36, 70)), (200, (40, 50, 92))):
        img.tri(peak - 60, 196, peak, 196 - htone[2] // 2, peak + 60, 196, rgb(*htone))
    img.rect(0, 190, w, h - 190, rgb(34, 84, 54))
    img.speckle(0, 190, w, h - 190, [rgb(46, 108, 62), rgb(26, 68, 44)], 0.4, rnd)
    for i in range(6):
        img.rect(0, 200 + i * 20, w, 1, rgb(28, 72, 46))
    img.rect(150, 150, 46, 60, rgb(64, 66, 88))
    img.rect(156, 138, 34, 14, rgb(84, 86, 108))
    for t in range(3):
        img.rect(152 + t * 14, 132, 6, 10, rgb(84, 86, 108))
    for wy in range(4):
        for wx in range(3):
            img.rect(158 + wx * 12, 158 + wy * 12, 6, 8, rgb(252, 214, 120))
    img.rect(86, 210, 24, 40, rgb(20, 30, 26))
    img.line(0, 196, 240, 196, rgb(20, 56, 38))
    img.stamp(16, 224, HERO_IDLE, PAL_HERO, 2)
    img.stamp(200, 232, SLIME_A, PAL_SLIME, 2)
    band_y, band_h = 44, 62
    img.rect(10, band_y, w - 20, band_h, rgb(20, 24, 44))
    img.frame(10, band_y, w - 20, band_h, rgb(232, 190, 70), 2)
    img.frame(14, band_y + 4, w - 28, band_h - 8, rgb(96, 84, 40))
    img.center_text(band_y + 12, "PIXEL", rgb(255, 244, 200), 4, shadow=rgb(60, 30, 12))
    img.center_text(band_y + 36, "QUEST", rgb(252, 214, 96), 4, shadow=rgb(60, 30, 12))
    for i, label in enumerate(("NEW GAME", "CONTINUE", "OPTIONS", "EXIT")):
        y = 128 + i * 18
        img.rect(70, y - 4, 100, 14, rgb(26, 32, 56) if i else rgb(48, 62, 104))
        img.text(80, y, label, rgb(226, 236, 250) if i else WHITE, 1)
    img.text(62, 128, ">", rgb(252, 214, 96), 1)
    img.center_text(300, "VXP 2026", rgb(150, 168, 200), 1)
    return img


def title_platformer() -> Img:
    w, h = 240, 320
    img = Img(w, h, rgb(88, 168, 236))
    rnd = random.Random(102)
    for band in range(6):
        img.rect(0, band * 26, w, 13, mix((88, 168, 236), (146, 206, 246), band / 6))
    for cx, cy, s in ((30, 40, 1), (150, 26, 1), (200, 62, 2)):
        img.circle(cx, cy, 8 * s, rgb(252, 252, 255), filled=True)
        img.circle(cx + 9 * s, cy + 1, 6 * s, rgb(252, 252, 255), filled=True)
        img.circle(cx - 9 * s, cy + 2, 5 * s, rgb(236, 244, 252), filled=True)
    img.rect(0, 190, w, 40, rgb(86, 176, 78))
    img.speckle(0, 190, w, 40, [rgb(106, 198, 92), rgb(64, 148, 62)], 0.4, rnd)
    img.rect(0, 230, w, h - 230, rgb(154, 96, 48))
    img.speckle(0, 230, w, h - 230, [rgb(124, 74, 36), rgb(178, 116, 60)], 0.35, rnd)
    for x in range(0, w, 32):
        img.rect(x, 230, 1, h - 230, rgb(110, 66, 32))
        img.rect(x + 16, 254, 1, h - 254, rgb(110, 66, 32))
        img.rect(x, 278, 1, h - 278, rgb(110, 66, 32))
    for bx in (18, 60, 170, 208):
        img.rect(bx, 150, 32, 16, rgb(232, 176, 48))
        img.frame(bx, 150, 32, 16, rgb(140, 96, 24))
        img.rect(bx + 4, 154, 6, 8, rgb(252, 224, 120))
    img.stamp(112, 168, HERO_WALK, PAL_HERO, 2)
    for i in range(5):
        img.circle(66 + i * 26, 120, 4, rgb(252, 208, 60), filled=True)
        img.circle(66 + i * 26, 120, 2, rgb(255, 244, 170), filled=True)
    img.rect(18, 34, w - 36, 52, rgb(28, 34, 62))
    img.frame(18, 34, w - 36, 52, rgb(252, 214, 96), 2)
    img.center_text(44, "SUNNY", rgb(255, 250, 230), 4, shadow=rgb(120, 60, 16))
    img.center_text(68, "DASH", rgb(252, 214, 96), 4, shadow=rgb(120, 60, 16))
    img.center_text(100, "PRESS START", rgb(255, 255, 255), 1)
    img.text(10, 300, "1UP 003250", rgb(255, 255, 255), 1, shadow=rgb(60, 40, 20))
    img.text(170, 300, "COINS 27", rgb(255, 244, 170), 1, shadow=rgb(60, 40, 20))
    return img


def title_shooter() -> Img:
    w, h = 240, 320
    img = Img(w, h, rgb(4, 6, 16))
    rnd = random.Random(103)
    stars(img, 420, rnd)
    img.circle(60, 250, 46, rgb(28, 62, 96), filled=True)
    img.circle(50, 240, 40, rgb(40, 96, 132), filled=True)
    for ring in range(3):
        img.circle(52, 244, 12 + ring * 10, rgb(64, 132, 168))
    img.rect(0, 236, w, 1, rgb(88, 208, 255))
    for y in (150, 170, 190):
        for x in range(0, w, 24):
            if (x + y) % 48 == 0:
                img.stamp(x, y, BAT_DOWN, PAL_BAT, 1)
    img.stamp(112, 268, ["..#..", ".###.", "#####", "#.#.#"], {"#": rgb(88, 208, 255)}, 1)
    img.stamp(110, 274, HERO_IDLE[:8], PAL_HERO, 1)
    img.line(120, 240, 120, 150, rgb(255, 92, 122))
    img.line(121, 240, 121, 150, rgb(255, 200, 214))
    img.line(96, 236, 88, 190, rgb(88, 208, 255))
    img.line(144, 236, 152, 190, rgb(88, 208, 255))
    img.circle(188, 120, 14, rgb(255, 150, 60), filled=True)
    img.circle(188, 120, 8, rgb(255, 226, 140), filled=True)
    img.rect(0, 0, w, 22, rgb(10, 16, 30))
    img.rect(0, 21, w, 1, rgb(88, 208, 255))
    img.text(6, 8, "SCORE 014820", rgb(226, 236, 250), 1)
    img.text(160, 8, "HI 999999", rgb(252, 214, 96), 1)
    for i in range(3):
        img.tri(200 + i * 14, 40, 194 + i * 14, 50, 206 + i * 14, 50, rgb(255, 92, 122))
    img.rect(8, 296, 120, 14, rgb(10, 16, 30))
    img.frame(8, 296, 120, 14, rgb(88, 208, 255))
    img.rect(10, 298, 74, 10, rgb(46, 160, 200))
    img.text(134, 300, "SHIELD", rgb(146, 206, 246), 1)
    img.center_text(64, "NEON", rgb(255, 255, 255), 5, shadow=rgb(120, 40, 160))
    img.center_text(90, "VOID", rgb(88, 208, 255), 5, shadow=rgb(20, 60, 120))
    img.center_text(120, "RETRY?", rgb(255, 92, 122), 1)
    return img


def title_puzzle() -> Img:
    w, h = 240, 320
    img = Img(w, h, rgb(24, 18, 44))
    rnd = random.Random(104)
    gem_colors = [(238, 74, 92), (88, 190, 255), (120, 226, 110),
                  (252, 214, 96), (196, 120, 244), (255, 158, 74)]
    cell, ox, oy = 30, 15, 96
    for row in range(6):
        for col in range(7):
            x, y = ox + col * cell, oy + row * cell
            c = gem_colors[(row * 3 + col * 2 + (row + col) % 3) % len(gem_colors)]
            img.rect(x + 2, y + 2, cell - 4, cell - 4, rgb(16, 12, 32))
            shape = (row + col) % 3
            cx, cy = x + cell // 2, y + cell // 2
            if shape == 0:
                img.circle(cx, cy, 9, rgb(*c), filled=True)
                img.circle(cx - 3, cy - 3, 3, rgb(*[min(255, v + 70) for v in c]), filled=True)
            elif shape == 1:
                img.tri(cx, cy - 10, cx - 10, cy + 8, cx + 10, cy + 8, rgb(*c))
                img.line(cx - 4, cy + 2, cx + 4, cy + 2, rgb(*[min(255, v + 70) for v in c]))
            else:
                img.stamp(cx - 8, cy - 8, [".#..#.", "###.##", "#####.", ".####.", "..##..", "...."],
                          {"#": rgb(*c)}, 3)
    img.rect(0, 0, w, 84, rgb(34, 24, 62))
    img.rect(0, 84, w, 2, rgb(196, 120, 244))
    img.center_text(10, "GEM", rgb(255, 255, 255), 4, shadow=rgb(90, 30, 140))
    img.center_text(36, "SHIFT", rgb(196, 120, 244), 4, shadow=rgb(90, 30, 140))
    img.text(12, 66, "MOVES 18", rgb(226, 236, 250), 1)
    img.text(150, 66, "BEST 4200", rgb(252, 214, 96), 1)
    img.rect(0, 282, w, 38, rgb(34, 24, 62))
    img.frame(6, 286, w - 12, 30, rgb(196, 120, 244))
    img.center_text(294, "MATCH 3 OR MORE", rgb(226, 236, 250), 1)
    return img


def screen_game_over() -> Img:
    w, h = 128, 128
    img = Img(w, h, rgb(12, 8, 12))
    rnd = random.Random(105)
    for y in range(h):
        for x in range(w):
            d = math.hypot(x - w / 2, y - h / 2) / (w / 2)
            img.set(x, y, mix((96, 16, 26), (10, 6, 10), min(1.0, d)))
    for _ in range(9):
        x0, y0 = rnd.randrange(w), rnd.randrange(h)
        x, y = x0, y0
        for _ in range(rnd.randrange(12, 34)):
            img.line(x, y, x + rnd.choice((-1, 0, 1)) * 4, y + rnd.choice((-1, 1)) * 4,
                     rgb(20, 12, 16))
            x, y = x + 2, y + 2
    img.center_text(38, "GAME", rgb(255, 236, 236), 3, shadow=rgb(60, 8, 14))
    img.center_text(64, "OVER", rgb(238, 74, 92), 3, shadow=rgb(60, 8, 14))
    img.center_text(96, "CONTINUE", rgb(226, 236, 250), 1)
    img.frame(20, 90, 88, 16, rgb(120, 40, 50))
    return img


def screen_pause() -> Img:
    w, h = 128, 128
    img = Img(w, h, rgb(20, 26, 40))
    rnd = random.Random(106)
    img.speckle(0, 0, w, h, [rgb(28, 36, 54), rgb(16, 22, 34)], 0.5, rnd)
    for i in range(0, h, 4):
        img.rect(0, i, w, 1, rgb(12, 16, 26))
    img.rect(12, 18, w - 24, h - 40, rgb(26, 34, 52))
    img.frame(12, 18, w - 24, h - 40, rgb(120, 190, 250), 2)
    img.center_text(28, "PAUSED", rgb(255, 255, 255), 2, shadow=rgb(20, 40, 80))
    img.rect(16, 48, w - 32, 2, rgb(60, 90, 140))
    for i, label in enumerate(("RESUME", "RESTART", "OPTIONS", "QUIT")):
        y = 58 + i * 14
        img.rect(20, y - 3, w - 40, 12, rgb(38, 52, 82) if i == 0 else rgb(30, 40, 64))
        img.text(28, y, label, rgb(236, 244, 255) if i == 0 else rgb(176, 196, 224), 1)
    img.text(16, 58, ">", rgb(252, 214, 96), 1)
    return img


# ------------------------------------------ arctic base defense (DRE) set
# Chunky "snow base defense" look: navy outline around every shape, ice-blue
# suits, orange machinery, snow-capped props. Shapes come from primitives and
# then share one outline + bottom-shade pass so the whole set reads as a family.

AR_OUT = rgb(11, 34, 62)      # outline navy
AR_NAVY = rgb(20, 62, 112)    # deep blue
AR_BLUE = rgb(47, 127, 209)   # suit / panel blue
AR_LBLUE = rgb(120, 186, 236)  # light blue
AR_SKY = rgb(168, 216, 246)   # sky blue
AR_SNOW = rgb(238, 247, 255)  # snow white
AR_SHAD = rgb(198, 222, 245)  # snow shadow
AR_ORNG = rgb(244, 146, 30)   # machine orange
AR_ODRK = rgb(186, 96, 10)    # orange shadow
AR_YLW = rgb(252, 208, 68)    # coin yellow
AR_GRN = rgb(63, 174, 90)     # button green
AR_GRDK = rgb(32, 118, 60)    # green shadow
AR_RED = rgb(232, 70, 90)     # alert red
AR_ROCK = rgb(168, 190, 210)  # ore grey
AR_ROCKD = rgb(110, 136, 166)  # ore shadow
AR_EYE = rgb(14, 24, 38)      # eyes / dark detail
AR_SKIN = rgb(240, 190, 130)  # face
AR_WOOD = rgb(128, 88, 52)    # posts
# brightest snow that is NOT 0xFFFF - the gallery keys pure white as transparent
AR_LIT = rgb(246, 252, 255)


def blit(dst: Img, src: Img, x: int, y: int, key: int = WHITE) -> None:
    """Paste `src` onto `dst`, treating `key` as transparent."""
    for j in range(src.h):
        for i in range(src.w):
            c = src.get(i, j)
            if c != key:
                dst.set(x + i, y + j, c)


def rrect(img: Img, x: int, y: int, w: int, h: int, c: int, bg: int = WHITE) -> None:
    img.rect(x, y, w, h, c)
    img.set(x, y, bg)
    img.set(x + w - 1, y, bg)
    img.set(x, y + h - 1, bg)
    img.set(x + w - 1, y + h - 1, bg)


def outline(img: Img, c: int = AR_OUT, key: int = WHITE) -> None:
    """Add a 1px rim of `c` around every shape - the signature of this set."""
    src = list(img.px)
    for y in range(img.h):
        for x in range(img.w):
            if src[y * img.w + x] != key:
                continue
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nx, ny = x + dx, y + dy
                if (0 <= nx < img.w and 0 <= ny < img.h
                        and src[ny * img.w + nx] != key):
                    img.set(x, y, c)
                    break


def shade(img: Img, dark: int, key: int = WHITE) -> None:
    """Darken the exposed bottom pixel of each column (cheap ambient occlusion)."""
    src = list(img.px)
    for x in range(img.w):
        for y in range(img.h - 1, -1, -1):
            if src[y * img.w + x] != key:
                if y + 1 < img.h and src[(y + 1) * img.w + x] == key:
                    img.set(x, y, dark)
                break


def snow_cap(img: Img, x: int, y: int, w: int, rnd: random.Random,
             n: int = 4) -> None:
    """Lumpy snow resting along the top edge of a prop."""
    for i in range(w):
        h = 1 + (2 if rnd.random() < 0.28 else 0)
        img.rect(x + i, y - h, 1, h + 1, AR_SNOW)
    for _ in range(n):
        cx = x + rnd.randrange(w)
        r = rnd.choice((2, 2, 3))
        img.ellipse(cx, y - 2, r, r - 1, AR_SNOW, filled=True)
    for _ in range(n):                        # a few drips over the front face
        cx = x + rnd.randrange(w)
        img.rect(cx, y + 1, rnd.choice((1, 2)), 1, AR_SNOW)


def darken(c: int, t: float = 0.68) -> int:
    r, g, b = c565_to_rgb(c)
    return rgb(int(r * t), int(g * t), int(b * t))


def lighten(c: int, t: int = 40) -> int:
    r, g, b = c565_to_rgb(c)
    return rgb(min(255, r + t), min(255, g + t), min(255, b + t))


def mini_coin(img: Img, x: int, y: int) -> None:
    """8x8 gold coin that fits inside buttons and price tags."""
    img.circle(x + 4, y + 4, 4, AR_ORNG, filled=True)
    img.circle(x + 4, y + 4, 3, AR_YLW, filled=True)
    img.rect(x + 3, y + 2, 2, 5, AR_ORNG)
    img.set(x + 2, y + 2, AR_SNOW)


def _worker(pose: str, suit: int, head: int, cap: int = 0) -> Img:
    """Base-defense character, 24x24, facing right.

    pose: idle | walk | dig | carry | aim
    """
    img = Img(24, 24, WHITE)
    dk = darken(suit)
    bob = 1 if pose == "walk" else 0
    top = 2 + bob
    # head + face
    rrect(img, 6, top, 11, 9, head)
    img.rect(7, top + 4, 9, 5, AR_SKIN)
    img.rect(6, top + 3, 11, 1, darken(head, 0.55))
    if cap:
        rrect(img, 6, top, 11, 4, cap)
        img.rect(4, top + 3, 15, 2, cap)
        img.rect(5, top + 5, 13, 1, darken(cap))
    if pose in ("idle", "aim", "carry"):
        img.rect(9, top + 5, 2, 2, AR_EYE)
        img.rect(13, top + 5, 2, 2, AR_EYE)
    else:
        img.rect(13, top + 5, 2, 2, AR_EYE)
    # torso
    rrect(img, 5, top + 9, 12, 8, suit)
    img.rect(5, top + 14, 12, 1, AR_NAVY)
    img.rect(6, top + 10, 3, 3, lighten(suit, 26))
    # arms
    if pose == "dig":
        img.rect(3, top + 10, 2, 6, dk)            # back arm down
        img.rect(16, top + 8, 2, 3, dk)
        img.rect(17, top + 6, 2, 3, dk)            # front arm raised
    elif pose == "carry":
        img.rect(3, top + 11, 2, 5, dk)
        img.rect(15, top + 11, 3, 3, dk)
    elif pose == "aim":
        img.rect(3, top + 11, 2, 5, dk)
        img.rect(16, top + 11, 4, 2, dk)           # both arms forward
    else:
        img.rect(3, top + 10, 2, 6, dk)
        img.rect(16, top + 10, 2, 6, dk)
    # legs + boots
    if pose == "walk":
        img.rect(6, top + 17, 3, 4, AR_NAVY)
        img.rect(14, top + 17, 3, 3, AR_NAVY)
        img.rect(5, top + 21, 4, 1, AR_OUT)
        img.rect(14, top + 20, 4, 1, AR_OUT)
    else:
        img.rect(7, top + 17, 3, 4, AR_NAVY)
        img.rect(12, top + 17, 3, 4, AR_NAVY)
        img.rect(6, top + 21, 4, 1, AR_OUT)
        img.rect(12, top + 21, 4, 1, AR_OUT)
    # held gear
    if pose == "carry":
        rrect(img, 7, top + 11, 9, 6, AR_ROCK)
        img.circle(10, top + 13, 2, AR_SNOW, filled=True)
        img.rect(12, top + 15, 2, 1, AR_LBLUE)
    if pose == "dig":
        img.line(18, top + 3, 21, top + 9, AR_WOOD)
        img.rect(17, top + 2, 5, 2, AR_ROCK)
        img.set(17, top + 1, AR_ROCKD)
        img.set(21, top + 1, AR_ROCKD)
    if pose == "aim":
        img.rect(20, top - 2, 1, 20, AR_WOOD)      # spear shaft
        img.tri(19, top - 2, 20, top - 5, 21, top - 2, AR_LBLUE)
        img.rect(16, top + 13, 5, 1, AR_YLW)
    shade(img, AR_NAVY)
    outline(img)
    return img


def draw_ar_worker(pose: str = "idle", frame: int = 0) -> Img:
    """Blue-suited worker with a yellow head; frame 1 mirrors the walk cycle."""
    p = "walk" if (pose == "walk" and frame % 2 == 0) else pose
    return _worker(p, AR_BLUE if frame < 2 else AR_ORNG, AR_YLW)


def draw_ar_miner_jacket(frame: int) -> Img:
    """Miner in an orange jacket with a blue hard hat."""
    return _worker("idle" if frame % 2 else "dig", AR_ORNG, AR_SKIN, cap=AR_BLUE)


def draw_ar_guard(frame: int) -> Img:
    """Guard in full blue uniform and cap, holding a spear."""
    img = _worker("aim" if frame else "idle", AR_BLUE, AR_SKIN, cap=AR_BLUE)
    return img


def draw_ar_bear(frame: int) -> Img:
    """Polar bear: 0 walk, 1 walk (legs swapped), 2 roaring."""
    img = Img(32, 24, WHITE)
    s = AR_SNOW
    img.ellipse(13, 12, 10, 7, s, filled=True)         # barrel body
    img.ellipse(24, 11, 6, 5, s, filled=True)          # head
    img.rect(27, 12, 4, 4, s)                          # snout
    img.ellipse(21, 5, 3, 3, s, filled=True)           # ear
    img.ellipse(10, 6, 3, 3, s, filled=True)           # back hump
    step = frame % 2
    for i, lx in enumerate((5, 11, 17, 23)):
        lift = 2 if (i % 2) == step else 0
        img.rect(lx, 15, 4, 7 - lift, s)
        img.rect(lx, 21 - lift, 4, 1, AR_SHAD)                  # paw
    img.rect(2, 10, 3, 3, s)                                    # tail
    img.line(9, 8, 17, 8, AR_SHAD)                              # shoulder seam
    img.rect(29, 13, 2, 2, AR_EYE)                              # nose
    img.set(25, 10, AR_EYE)                                     # eye
    if frame == 2:
        img.rect(26, 14, 6, 5, AR_RED)                 # open jaw
        img.rect(26, 14, 6, 1, s)
        img.rect(26, 18, 6, 1, s)
        for i in range(27, 31, 2):
            img.set(i, 15, s)
            img.set(i, 17, s)
        img.rect(21, 4, 1, 1, AR_SHAD)
    shade(img, AR_SHAD)
    outline(img)
    return img


def draw_ar_ore_pile(frame: int) -> Img:
    """Chunky ore deposit: faceted rocks, frame 1 adds a blue crystal chip."""
    img = Img(28, 20, WHITE)
    face = rgb(132, 156, 180)
    lit = rgb(186, 208, 226)
    dark = rgb(84, 108, 136)
    blobs = [(8, 13, 5), (19, 13, 5), (13, 9, 4)]
    if frame:
        blobs += [(23, 8, 3), (5, 8, 3)]
    for cx, cy, r in blobs:
        img.circle(cx, cy, r, face, filled=True)
        img.circle(cx - 1, cy - 2, max(1, r - 2), lit, filled=True)
        img.line(cx - r + 1, cy + r - 1, cx + r - 1, cy + r - 1, dark)
        img.line(cx - r + 2, cy + 2, cx + r - 2, cy + 2, dark)
        img.rect(cx - 1, cy - r + 1, 2, 1, AR_SNOW)
    if frame:
        img.tri(21, 7, 23, 1, 25, 7, AR_BLUE)
        img.tri(22, 6, 23, 2, 24, 6, AR_LBLUE)
    else:
        img.tri(11, 7, 13, 2, 15, 7, AR_LBLUE)
    outline(img)
    return img


def draw_ar_crystal(frame: int) -> Img:
    """Ice crystal cluster, 16x22."""
    img = Img(16, 22, WHITE)
    for cx, hgt, wd in ((5, 9 + frame, 3), (10, 14, 4), (13, 7, 2)):
        img.tri(cx - wd, 20, cx, 20 - hgt, cx + wd, 20, AR_BLUE)
        img.tri(cx - wd + 1, 19, cx, 20 - hgt + 2, cx, 19, AR_LBLUE)
    img.rect(1, 19, 14, 2, AR_ROCK)
    shade(img, AR_ROCKD)
    outline(img)
    return img


def draw_ar_machine(frame: int) -> Img:
    """Ore factory: blue body, orange hopper, side chute. frame 1 = running."""
    img = Img(34, 30, WHITE)
    rrect(img, 3, 10, 24, 17, AR_BLUE)
    img.rect(5, 13, 14, 9, AR_NAVY)                    # door / window
    img.rect(6, 14, 12, 3, AR_LBLUE)
    rrect(img, 9, 3, 12, 8, AR_ORNG)                   # hopper
    img.rect(10, 4, 10, 2, AR_YLW)
    rrect(img, 25, 14, 7, 13, AR_ROCKD)                # side chute
    img.rect(26, 16, 5, 3, AR_NAVY)
    if frame:
        img.rect(26, 20, 5, 3, AR_ROCK)                # ore coming out
        img.set(28, 25, AR_YLW)
    img.rect(2, 26, 26, 2, AR_NAVY)                    # base skid
    img.rect(19, 20, 6, 5, AR_ORNG)                    # control box
    img.rect(20, 21, 2, 2, AR_YLW if frame else AR_ODRK)
    snow_cap(img, 3, 10, 24, random.Random(11))
    shade(img, AR_NAVY)
    outline(img)
    return img


def draw_ar_truck(frame: int) -> Img:
    """Delivery truck, 48x26, facing right."""
    img = Img(48, 26, WHITE)
    rrect(img, 3, 6, 26, 14, AR_ORNG)                  # cargo box
    img.rect(4, 7, 24, 3, AR_YLW)
    rrect(img, 30, 10, 14, 10, AR_BLUE)                # cab
    rrect(img, 33, 11, 8, 6, AR_LBLUE)                 # window
    img.rect(30, 20, 14, 2, AR_NAVY)
    img.rect(43, 14, 3, 5, AR_YLW)                     # headlight
    for wx in (9, 19, 36):
        img.circle(wx, 21, 4, AR_OUT, filled=True)
        img.circle(wx, 21, 2, AR_ROCKD, filled=True)
    img.line(3, 20, 44, 20, AR_NAVY)
    if frame:
        img.rect(3, 3, 26, 2, AR_SNOW)                 # snow on the roof
    snow_cap(img, 3, 6, 26, random.Random(23))
    shade(img, AR_ODRK)
    outline(img)
    return img


def draw_ar_sign(label: str, plate: int, frame: int = 0) -> Img:
    """Snow-topped wooden sign board with a navy-rimmed plate."""
    img = Img(40, 26, WHITE)
    img.rect(7, 13, 3, 12, AR_WOOD)
    img.rect(30, 13, 3, 12, AR_WOOD)
    rrect(img, 1, 2, 38, 16, plate)
    img.frame(1, 2, 38, 16, AR_OUT, 1)
    img.frame(3, 4, 34, 12, AR_LBLUE if plate != AR_GRN else AR_GRDK, 1)
    if label:
        if label == "^":
            img.tri(12, 14, 20, 5, 28, 14, AR_SNOW)
            img.rect(17, 14, 6, 3, AR_SNOW)
        else:
            img.center_text(8, label, AR_SNOW, 1, shadow=AR_OUT)
    if frame:
        img.rect(6, 18, 28, 6, AR_OUT)              # status plate under the board
        img.rect(7, 19, 26, 4, AR_NAVY)
        img.rect(7, 19, int(26 * 0.6), 4, AR_GRN)
        img.rect(7, 19, int(26 * 0.6), 1, AR_LBLUE)
    snow_cap(img, 1, 2, 38, random.Random(31), n=6)
    outline(img)
    return img


def draw_ar_fence(frame: int) -> Img:
    img = Img(28, 18, WHITE)
    for px in (3, 12, 21):
        img.rect(px, 4, 3, 13, AR_WOOD)
    img.rect(1, 7, 25, 2, AR_WOOD)
    img.rect(1, 12, 25, 2, AR_WOOD)
    if frame:
        img.rect(2, 10, 24, 1, AR_ROCKD)
    snow_cap(img, 1, 7, 25, random.Random(41), n=5)
    for px in (3, 12, 21):
        img.rect(px, 2, 3, 2, AR_SNOW)
    shade(img, AR_WOOD)
    outline(img)
    return img


def draw_ar_lamp(frame: int) -> Img:
    img = Img(12, 26, WHITE)
    img.rect(5, 8, 2, 15, AR_NAVY)                  # pole
    img.rect(3, 23, 6, 2, AR_OUT)                   # base
    img.rect(4, 22, 4, 1, AR_NAVY)
    rrect(img, 3, 3, 6, 6, AR_ORNG)                 # housing
    img.rect(4, 4, 4, 4, AR_YLW if frame else AR_ODRK)
    img.rect(4, 1, 4, 2, AR_OUT)                    # cap
    img.rect(2, 2, 8, 1, AR_SNOW)                   # snow on the hood
    if frame:
        for dx, dy in ((-1, 0), (6, 0), (2, 7), (-1, 4), (6, 4)):
            img.set(5 + dx, 6 + dy, AR_YLW)
    outline(img)
    return img


def draw_ar_steps(frame: int) -> Img:
    """Orange/blue stair ramp between base levels, 20x20."""
    img = Img(20, 20, WHITE)
    for i in range(5):
        y = 3 + i * 3
        img.rect(2 + i * 3, y, 8, 3, AR_ORNG if i % 2 else AR_BLUE)
        img.rect(2 + i * 3, y, 8, 1, AR_YLW if i % 2 else AR_LBLUE)
    shade(img, AR_NAVY)
    outline(img)
    return img


def draw_ar_coin(frame: int) -> Img:
    """Popping ore-coin spin cycle: face disc -> edge-on, 12x12."""
    img = Img(12, 12, WHITE)
    rx = (5, 3, 1, 3)[frame % 4]
    cy = 6 - (frame % 3)
    img.ellipse(6, cy + 1, rx, 5, AR_ORNG, filled=True)
    if rx > 1:
        img.ellipse(6, cy + 1, rx - 1, 4, AR_YLW, filled=True)
        img.ellipse(5, cy, max(1, rx - 3), 1, AR_SNOW, filled=True)
        img.rect(6 - max(1, rx // 2), cy - 1, max(1, rx), 4, AR_ORNG)
    outline(img)
    return img


def draw_ar_snowflake(frame: int) -> Img:
    img = Img(10, 10, WHITE)
    c = AR_SNOW if frame % 2 == 0 else AR_LBLUE
    cx = 5
    img.line(cx, 1, cx, 9, c)
    img.line(1, cx, 9, cx, c)
    img.line(2, 2, 8, 8, c)
    img.line(8, 2, 2, 8, c)
    img.set(cx, cx, AR_SNOW)
    outline(img, AR_SKY)
    return img


def draw_ar_hp_bar(frame: int) -> Img:
    """Floating enemy health bar, 20x5."""
    img = Img(20, 5, WHITE)
    img.rect(0, 1, 20, 3, AR_OUT)
    fill = (20, 13, 7)[frame % 3]
    img.rect(1, 2, fill - 2, 1, AR_RED)
    return img


AR_ICONS = ("gold", "level", "wave", "heart", "bag", "ammo",
            "close", "play", "dpad", "ore", "crystal", "star")


def draw_ar_icon(kind: str) -> Img:
    """16x16 HUD badges."""
    img = Img(16, 16, WHITE)
    if kind == "gold":
        img.circle(8, 8, 7, AR_ORNG, filled=True)
        for a in range(0, 360, 45):
            dx = int(round(math.cos(math.radians(a)) * 7))
            dy = int(round(math.sin(math.radians(a)) * 7))
            img.set(8 + dx, 8 + dy, AR_ORNG)
        img.circle(8, 8, 5, AR_YLW, filled=True)
        img.rect(7, 4, 2, 8, AR_ORNG)
        img.rect(5, 7, 6, 2, AR_ORNG)
    elif kind == "level":
        rrect(img, 1, 1, 14, 14, AR_BLUE)
        img.frame(1, 1, 14, 14, AR_LBLUE, 1)
        img.text(3, 5, "LV", AR_SNOW, 1)
    elif kind == "wave":
        img.circle(8, 7, 6, AR_SNOW, filled=True)
        img.rect(4, 11, 8, 3, AR_SNOW)
        img.rect(5, 5, 2, 3, AR_EYE)
        img.rect(9, 5, 2, 3, AR_EYE)
        img.rect(7, 9, 2, 2, AR_EYE)
        for x in (5, 8, 11):
            img.rect(x, 13, 1, 2, AR_OUT)
    elif kind == "heart":
        img.circle(5, 6, 3, AR_RED, filled=True)
        img.circle(11, 6, 3, AR_RED, filled=True)
        img.tri(2, 7, 8, 15, 14, 7, AR_RED)
        img.rect(4, 4, 2, 2, rgb(255, 150, 165))
    elif kind == "bag":
        rrect(img, 2, 5, 12, 10, AR_ORNG)
        rrect(img, 5, 2, 6, 4, AR_ODRK)
        img.rect(6, 3, 4, 2, AR_ORNG)
        img.rect(2, 8, 12, 2, AR_ODRK)
        img.rect(7, 8, 2, 3, AR_YLW)
    elif kind == "ammo":
        for i, x in enumerate((2, 7, 12)):
            img.rect(x, 5, 3, 9, AR_YLW)
            img.tri(x, 5, x + 1, 1, x + 3, 5, AR_ORNG)
            img.rect(x, 12, 3, 2, AR_ODRK)
    elif kind == "close":
        rrect(img, 1, 1, 14, 14, AR_RED)
        img.frame(2, 2, 12, 12, rgb(255, 150, 165), 1)
        img.line(4, 4, 11, 11, AR_SNOW)
        img.line(11, 4, 4, 11, AR_SNOW)
    elif kind == "play":
        img.tri(3, 2, 14, 8, 3, 14, AR_YLW)
        img.line(3, 3, 3, 13, AR_ORNG)
    elif kind == "dpad":
        rrect(img, 5, 1, 6, 14, AR_SNOW)
        rrect(img, 1, 5, 14, 6, AR_SNOW)
        img.rect(7, 3, 2, 10, AR_SHAD)
        img.rect(3, 7, 10, 2, AR_SHAD)
        img.circle(8, 8, 1, AR_OUT, filled=True)
    elif kind == "ore":
        img.circle(5, 10, 4, AR_ROCK, filled=True)
        img.circle(11, 10, 3, AR_ROCKD, filled=True)
        img.circle(8, 6, 3, AR_ROCK, filled=True)
        img.set(7, 5, AR_SNOW)
    elif kind == "crystal":
        img.tri(3, 13, 8, 1, 13, 13, AR_BLUE)
        img.tri(5, 12, 8, 3, 8, 12, AR_LBLUE)
    elif kind == "star":
        img.rect(6, 1, 4, 14, AR_YLW)
        img.rect(1, 6, 14, 4, AR_YLW)
        img.line(3, 3, 12, 12, AR_YLW)
        img.line(12, 3, 3, 12, AR_YLW)
        img.circle(8, 8, 3, AR_ORNG, filled=True)
    if kind not in ("dpad", "close", "heart"):
        outline(img)
    else:
        outline(img, AR_OUT)
    return img


# ---------------------------------------------------------------- arctic tiles
def _ar_tile(seed: int, base: int = AR_SNOW, spec: int = AR_SHAD, n: int = 16) -> Img:
    img = Img(24, 24, base)
    rnd = random.Random(seed)
    # never speckle with pure WHITE here: the gallery keys 0xFFFF as transparent,
    # so white dots would punch holes in the tile
    img.speckle(0, 0, 24, 24, [spec, AR_LIT], n / 100.0 * 4, rnd)
    return img


def _stable(key: str) -> int:
    return sum(ord(ch) * (i + 3) for i, ch in enumerate(key)) % 997


def draw_ar_tile(kind: str, frame: int = 0) -> Img:
    img = _ar_tile(400 + _stable(kind) + frame)
    rnd = random.Random(500 + len(kind) + frame)
    if kind == "flat":
        pass
    elif kind == "dots":
        for _ in range(10):
            x, y = rnd.randrange(22), rnd.randrange(22)
            img.rect(x, y, 2, 1, AR_LBLUE)
    elif kind == "chip":
        for _ in range(4):
            x, y = rnd.randrange(19), rnd.randrange(19)
            img.tri(x, y + 3, x + 2, y, x + 4, y + 3, AR_ROCK)
            img.rect(x + 1, y + 3, 3, 1, AR_ROCKD)
    elif kind == "crack":
        for _ in range(3):
            x, y = rnd.randrange(6, 18), rnd.randrange(4, 20)
            img.line(x, y, x + rnd.randrange(-5, 6), y + rnd.randrange(2, 6), AR_LBLUE)
            img.line(x, y, x + rnd.randrange(-6, 5), y - rnd.randrange(1, 5), AR_SHAD)
    elif kind == "drift":
        for i in range(24):
            h = 3 + int(2.5 * math.sin(i / 3.0 + frame))
            img.rect(i, 24 - h, 1, h, AR_SHAD if h % 2 else AR_LBLUE)
            img.rect(i, 24 - h, 1, 2, AR_SNOW)
    elif kind == "ice":
        img.rect(0, 0, 24, 24, AR_LBLUE)
        img.vgrad(0, 0, 24, 24, (200, 236, 255), (96, 168, 220), dither=False)
        for _ in range(6):
            x, y = rnd.randrange(20), rnd.randrange(20)
            img.line(x, y, x + 4, y + 4, AR_SNOW)
    elif kind == "sea":
        img = Img(24, 24, AR_NAVY)
        img.vgrad(0, 0, 24, 24, (28, 88, 152), (12, 48, 96), dither=False)
        for _ in range(7):
            x, y = rnd.randrange(2, 18), rnd.randrange(2, 22)
            off = frame * 2 % 6
            img.rect(x + off, y, 4, 1, AR_BLUE)
            img.rect(x + off, y + 1, 2, 1, AR_LBLUE)
    return img


def draw_ar_edge(side: str, frame: int = 0) -> Img:
    """Snow island cliff edges: `side` in top | left | right | tl | tr."""
    img = _ar_tile(600 + ord(side[0]) + len(side) * 7, n=14)
    band = AR_BLUE
    if "t" in side:
        img.rect(0, 0, 24, 3, AR_SNOW)
        img.rect(0, 3, 24, 4, band)
        img.rect(0, 7, 24, 2, AR_NAVY)
        for x in range(0, 24, 3):
            img.set(x + (frame % 3), 6, AR_LBLUE)
    if side == "left":
        img.rect(0, 0, 6, 24, AR_SHAD)
        img.rect(6, 0, 3, 24, band)
        img.rect(9, 0, 2, 24, AR_NAVY)
    if side == "right":
        img.rect(18, 0, 6, 24, AR_SHAD)
        img.rect(15, 0, 3, 24, band)
        img.rect(13, 0, 2, 24, AR_NAVY)
    if side == "tl":
        img.rect(0, 0, 12, 12, WHITE)
        img.ellipse(14, 14, 11, 11, AR_SNOW, filled=True)
        img.ellipse(14, 14, 12, 12, AR_NAVY)
        img.ellipse(14, 14, 11, 11, AR_BLUE)
        img.ellipse(15, 15, 9, 9, AR_SNOW, filled=True)
    if side == "tr":
        img.rect(12, 0, 12, 12, WHITE)
        img.ellipse(9, 14, 11, 11, AR_SNOW, filled=True)
        img.ellipse(9, 14, 12, 12, AR_NAVY)
        img.ellipse(9, 14, 11, 11, AR_BLUE)
        img.ellipse(8, 15, 9, 9, AR_SNOW, filled=True)
    return img


# ------------------------------------------------------------ arctic textures
def ar_sky(img: Img, w: int, h: int, top: Tuple[int, int, int] = (96, 176, 232)) -> None:
    img.vgrad(0, 0, w, h, top, (222, 244, 255), dither=False)


def ar_peaks(img: Img, base_y: int, peaks: Sequence[Tuple[int, int, int]],
             ground: int = AR_SNOW) -> None:
    """Layered mountains: (centre x, half width, height) back-to-front."""
    for i, (cx, half, hgt) in enumerate(peaks):
        rock = (AR_LBLUE, AR_BLUE, AR_NAVY)[min(i, 2)] if i else AR_LBLUE
        if i == 0:
            rock = AR_LBLUE
        elif i == 1:
            rock = rgb(74, 148, 214)
        else:
            rock = AR_NAVY
        img.tri(cx - half, base_y, cx, base_y - hgt, cx + half, base_y, rock)
        cap_h = max(3, hgt // 3)
        cap_w = max(2, half * cap_h // max(hgt, 1))
        img.tri(cx - cap_w, base_y - hgt + cap_h, cx, base_y - hgt,
                cx + cap_w, base_y - hgt + cap_h, AR_SNOW)
        for k in range(cap_w, -1, -1):
            img.set(cx - k, base_y - hgt + cap_h + (k % 2), AR_SNOW)
            img.set(cx + k, base_y - hgt + cap_h + ((k + 1) % 2), AR_SNOW)
    img.rect(0, base_y, img.w, img.h - base_y, ground)


def ar_flakes(img: Img, w: int, h: int, count: int, seed: int = 9) -> None:
    rnd = random.Random(seed)
    for _ in range(count):
        x, y = rnd.randrange(w), rnd.randrange(h)
        r = rnd.choice((1, 1, 2))
        img.circle(x, y, r, AR_SNOW, filled=rnd.random() < .3)
        if r > 1:
            img.line(x - 2, y, x + 2, y, AR_SNOW)
            img.line(x, y - 2, x, y + 2, AR_SNOW)


def arc_top(img: Img, cx: int, cy: int, rx: int, ry: int, c: int) -> None:
    """Upper half of an ellipse - reads as the far rim of a snow shelf."""
    for i in range(-rx, rx + 1):
        t = max(0.0, 1.0 - (i / max(rx, 1)) ** 2)
        img.set(cx + i, cy - int(round(ry * math.sqrt(t))), c)


def ar_island(img: Img, x: int, y: int, w: int, h: int) -> None:
    """Snow-topped island shelf with a blue cliff skirt."""
    cx, cy = x + w // 2, y + h // 2
    img.ellipse(cx, cy, w // 2, h // 2, AR_NAVY, filled=True)
    img.ellipse(cx, cy - 2, w // 2 - 1, h // 2 - 1, AR_BLUE, filled=True)
    img.ellipse(cx, cy - 4, w // 2 - 2, h // 2 - 3, AR_SNOW, filled=True)
    arc_top(img, cx, cy - 4, w // 2 - 4, h // 2 - 5, AR_SHAD)
    rnd = random.Random(77)
    for _ in range(w * h // 90):
        px = cx + rnd.randrange(-w // 2 + 6, w // 2 - 5)
        py = cy - 6 + rnd.randrange(-h // 3, h // 4)
        img.circle(px, py, rnd.choice((1, 2)), AR_SHAD, filled=True)


def draw_ar_hud_bar() -> Img:
    """Top status strip: gold / level / wave / hp / bag / ammo cells."""
    w, h = 240, 32
    img = Img(w, h, AR_NAVY)
    img.vgrad(0, 0, w, h, (30, 92, 158), (14, 52, 98), dither=False)
    img.rect(0, h - 2, w, 2, AR_OUT)
    cells = (("gold", "120"), ("level", "1"), ("wave", "1"),
             ("heart", "3"), ("bag", "0/5"), ("ammo", "4"))
    cw = (w - 8) // len(cells)
    for i, (icon, value) in enumerate(cells):
        x = 4 + i * cw
        blit(img, draw_ar_icon(icon), x, 8)
        img.text(x + 18, 9, value, AR_YLW if i == 0 else AR_SNOW, 1,
                 shadow=AR_OUT)
        if i:
            img.rect(x - 4, 6, 1, h - 12, AR_BLUE)
    img.text(4 + 2 * cw + 18, 18, "3/4", AR_SNOW, 1, shadow=AR_OUT)
    for k in range(3):                              # hp pips under the heart
        px = 4 + 3 * cw + 18 + k * 6
        c = AR_RED if k < 2 else AR_NAVY
        img.rect(px, 20, 4, 2, c)
        img.set(px, 19, c)
        img.set(px + 3, 19, c)
        img.set(px + 1, 22, c)
        img.set(px + 2, 22, c)
    return img


def draw_ar_shop_panel() -> Img:
    """Shop overlay panel with snow-capped frame and five upgrade rows."""
    w, h = 176, 240
    img = Img(w, h, AR_NAVY)
    img.vgrad(3, 3, w - 6, h - 6, (56, 128, 196), (18, 58, 106), dither=False)
    img.frame(0, 0, w, h, AR_OUT, 2)
    img.frame(4, 4, w - 8, h - 8, AR_LBLUE, 1)
    snow_cap(img, 6, 6, w - 12, random.Random(5), n=10)
    # title plate
    rrect(img, 46, 1, 84, 20, AR_BLUE, bg=AR_NAVY)
    img.frame(46, 1, 84, 20, AR_OUT, 2)
    img.center_text(8, "SHOP", AR_SNOW, 2, shadow=AR_OUT)
    blit(img, draw_ar_icon("close"), 152, 6, key=WHITE)
    # wallet row
    img.rect(10, 26, w - 20, 16, AR_SKIN)
    img.rect(11, 27, w - 22, 14, rgb(250, 226, 160))
    blit(img, draw_ar_icon("gold"), 14, 27)
    img.text(34, 32, "120", AR_ODRK, 1)
    rows = (("bag", "BAG +3", "CARRY 3 MORE ORE", 50, 1),
            ("star", "MACHINE SPEED", "PRODUCE ORE FASTER", 75, 0),
            ("ammo", "GUARD AMMO", "START WITH MORE AMMO", 60, 0),
            ("level", "EXTRA GUARD", "ADD 1 MORE GUARD", 100, 0),
            ("ore", "MORE ORE", "EXPAND ORE DEPOSITS", 80, 0))
    for i, (icon, title, sub, cost, sel) in enumerate(rows):
        y = 48 + i * 32
        rrect(img, 10, y, w - 20, 28, AR_SNOW if not sel else rgb(252, 240, 190),
              bg=AR_NAVY)
        img.frame(10, y, w - 20, 28, AR_OUT if sel else AR_LBLUE, 2 if sel else 1)
        blit(img, draw_ar_icon(icon), 15, y + 6)
        img.text(38, y + 5, title, AR_NAVY, 1)
        img.text(38, y + 16, sub, AR_BLUE, 1)
        rrect(img, 114, y + 5, 22, 12, AR_BLUE, bg=AR_SNOW)
        img.frame(114, y + 5, 22, 12, AR_NAVY, 1)
        img.text(117, y + 8, "LV1", AR_SNOW, 1)
        bx = 140
        rrect(img, bx, y + 5, 28, 18, AR_GRN, bg=AR_SNOW)
        img.frame(bx, y + 5, 28, 18, AR_GRDK, 1)
        mini_coin(img, bx + 2, y + 10)
        img.text(bx + 12, y + 11, str(cost), AR_SNOW, 1, shadow=AR_GRDK)
    # key hints
    img.rect(10, h - 22, w - 20, 16, AR_OUT)
    for i, (k, label) in enumerate((("5", "BUY"), ("0", "CLOSE"))):
        x = 22 + i * 74
        img.frame(x, h - 20, 10, 12, AR_SNOW, 1)
        img.text(x + 3, h - 18, k, AR_SNOW, 1)
        img.text(x + 16, h - 18, label, AR_SNOW, 1)
        if i:
            img.line(x - 8, h - 16, x - 8, h - 10, AR_BLUE)
    return img


def draw_ar_mountain_sheet() -> Img:
    """Parallax backdrop: sky, three mountain rows, falling snow."""
    w, h = 240, 120
    img = Img(w, h, AR_SKY)
    ar_sky(img, w, h)
    ar_peaks(img, h - 6, [(30, 46, 74), (120, 60, 96), (206, 44, 68),
                          (76, 34, 52), (168, 30, 44)])
    ar_flakes(img, w, h - 20, 40, seed=3)
    img.rect(0, h - 6, w, 6, AR_SNOW)
    return img


def draw_ar_snow_sheet() -> Img:
    """64x64 seamless snow surface with drifts and chips."""
    w = h = 64
    img = Img(w, h, AR_SNOW)
    rnd = random.Random(1234)
    img.speckle(0, 0, w, h, [AR_SHAD, AR_LIT], 0.30, rnd)
    for _ in range(9):
        x, y = rnd.randrange(w), rnd.randrange(h)
        r = rnd.randrange(3, 8)
        img.circle(x, y, r, AR_SHAD, filled=True)
        img.circle(x, y - 1, r - 1, AR_SNOW, filled=True)
    for _ in range(14):
        x, y = rnd.randrange(w), rnd.randrange(h)
        img.tri(x, y + 2, x + 1, y - 1, x + 3, y + 2, AR_ROCK)
    for _ in range(6):
        x, y = rnd.randrange(w), rnd.randrange(h)
        img.line(x, y, x + 5, y + 3, AR_LBLUE)
    return img


# ----------------------------------------------------------- arctic screens
def _ar_scene(w: int, h: int) -> Img:
    """Shared play field: mountains, island, props, characters."""
    img = Img(w, h, AR_SKY)
    ar_sky(img, w, h)
    ar_peaks(img, 118, [(24, 40, 66), (96, 52, 86), (168, 38, 60),
                        (214, 34, 72), (60, 26, 40)], ground=rgb(216, 236, 251))
    ar_flakes(img, w, 112, 46, seed=17)
    # the island
    ar_island(img, 12, 122, w - 24, h - 176)
    # back fence + bears on the ridge
    blit(img, draw_ar_fence(0), 16, 108)
    blit(img, draw_ar_fence(1), 150, 108)
    blit(img, draw_ar_bear(0), 26, 94)
    blit(img, draw_ar_bear(2), 150, 90)
    blit(img, draw_ar_bear(1), 96, 98)
    blit(img, draw_ar_hp_bar(0), 30, 88)
    blit(img, draw_ar_hp_bar(1), 154, 84)
    # mid-field props
    blit(img, draw_ar_machine(1), 92, 152)
    blit(img, draw_ar_steps(0), 122, 138)
    blit(img, draw_ar_lamp(1), 178, 118)
    blit(img, draw_ar_ore_pile(1), 22, 178)
    blit(img, draw_ar_crystal(0), 44, 150)
    blit(img, draw_ar_ore_pile(0), 172, 188)
    blit(img, draw_ar_sign("ORE", AR_BLUE, 1), 12, 148)
    blit(img, draw_ar_sign("FACTORY", AR_NAVY), 94, 188)
    blit(img, draw_ar_sign("GUARD", AR_BLUE, 1), 156, 146)
    blit(img, draw_ar_sign("SELL", AR_GRN), 158, 198)
    blit(img, draw_ar_worker("idle", 0), 38, 172)
    blit(img, draw_ar_miner_jacket(0), 80, 178)
    blit(img, draw_ar_guard(0), 148, 128)
    blit(img, draw_ar_coin(1), 190, 178)
    return img


def _ar_hud(img: Img, w: int) -> None:
    blit(img, draw_ar_hud_bar(), 0, 0)
    img.rect(0, 32, w, 14, AR_BLUE)
    img.rect(0, 32, w, 1, AR_OUT)
    blit(img, draw_ar_icon("play"), 4, 33)
    img.text(20, 36, "DEFEND YOUR BASE!", AR_SNOW, 1, shadow=AR_NAVY)


def _ar_footer(img: Img, w: int, h: int) -> None:
    y = h - 46
    rrect(img, 6, y, w - 12, 28, AR_SNOW, bg=AR_SKY)
    img.frame(6, y, w - 12, 28, AR_OUT, 1)
    blit(img, draw_ar_truck(0), 10, y + 2)
    for x in (62, 100, 152):
        img.rect(x, y + 5, 1, 18, AR_SHAD)
    img.text(68, y + 10, "ORE 3/5", AR_NAVY, 1)
    img.text(106, y + 10, "SHOP 5", AR_NAVY, 1)
    img.text(158, y + 10, "PAUSE 0", AR_NAVY, 1)
    # key hint strip
    img.rect(0, h - 18, w, 18, AR_NAVY)
    blit(img, draw_ar_icon("dpad"), 6, h - 16)
    img.text(24, h - 12, "2/4/6/8 MOVE", AR_SNOW, 1)
    for i, (k, label) in enumerate((("5", "SHOP"), ("0", "PAUSE"))):
        x = 108 + i * 62
        img.frame(x, h - 15, 11, 12, AR_SNOW, 1)
        img.text(x + 4, h - 13, k, AR_SNOW, 1)
        img.text(x + 17, h - 13, label, AR_SNOW, 1)


def screen_arctic_title() -> Img:
    w, h = 240, 320
    img = Img(w, h, AR_SKY)
    ar_sky(img, w, h, top=(64, 148, 214))
    ar_peaks(img, 196, [(30, 44, 78), (110, 56, 100), (196, 42, 72), (70, 28, 46)])
    ar_flakes(img, w, 200, 70, seed=51)
    # logo plates
    img.rect(0, 40, w, 46, AR_NAVY)
    img.frame(0, 40, w, 46, AR_BLUE, 1)
    snow_cap(img, 8, 41, w - 16, random.Random(9), n=10)
    img.center_text(48, "DRE FACTORY", AR_YLW, 3, shadow=AR_OUT)
    img.center_text(72, "SNOW BASE DEFENSE", AR_SNOW, 1, shadow=AR_NAVY)
    # cast line-up on a snow shelf
    img.rect(0, 196, w, h - 196, AR_SNOW)
    img.rect(0, 196, w, 3, AR_SHAD)
    rnd = random.Random(3)
    img.speckle(0, 200, w, h - 200, [AR_SHAD], 0.05, rnd)
    blit(img, draw_ar_worker("idle", 0), 26, 176)
    blit(img, draw_ar_miner_jacket(1), 56, 178)
    blit(img, draw_ar_guard(1), 86, 172)
    blit(img, draw_ar_bear(2), 116, 176)
    blit(img, draw_ar_machine(0), 156, 168)
    blit(img, draw_ar_truck(1), 186, 210)
    blit(img, draw_ar_sign("SELL", AR_GRN), 150, 240)
    blit(img, draw_ar_ore_pile(1), 30, 214)
    blit(img, draw_ar_crystal(1), 66, 208)
    # start button
    rrect(img, 60, 264, 120, 28, AR_GRN, bg=AR_SNOW)
    img.frame(60, 264, 120, 28, AR_OUT, 2)
    img.frame(63, 267, 114, 22, AR_GRDK, 1)
    img.center_text(274, "PRESS 5 PLAY", AR_SNOW, 1, shadow=AR_GRDK)
    blit(img, draw_ar_icon("gold"), 40, 268)
    img.rect(148, 296, 88, 13, AR_NAVY)
    img.frame(148, 296, 88, 13, AR_BLUE, 1)
    img.text(153, 300, "VPE565 SAMPLE", AR_LBLUE, 1)
    return img


def screen_arctic_play() -> Img:
    w, h = 240, 320
    img = _ar_scene(w, h)
    _ar_hud(img, w)
    _ar_footer(img, w, h)
    return img


def screen_arctic_shop() -> Img:
    w, h = 240, 320
    img = _ar_scene(w, h)
    # dim the field behind the panel
    for i, v in enumerate(img.px):
        r, g, b = c565_to_rgb(v)
        img.px[i] = rgb(int(r * 0.45 + 8), int(g * 0.45 + 20), int(b * 0.45 + 40))
    _ar_hud(img, w)
    blit(img, draw_ar_shop_panel(), (w - 176) // 2, 32)
    _ar_footer(img, w, h)
    return img


# ============================================================ taxonomy families
# Groups below follow docs/ASSET_TAXONOMY.md: top-down RPG world tiles, side
# scroller platform tiles, parallax backgrounds, and the character/item/UI/VFX
# sprite layers that go with them.

def safe_light(c: int, t: int = 24) -> int:
    """Lighten an RGB565 colour without ever reaching 0xFFFF.

    0xFFFF is the editor's transparency key, so a highlight that rounds up to it
    punches holes into solid tiles. Capping any channel at 247 keeps the red
    field below full, which makes the collision impossible.
    """
    r, g, b = c565_to_rgb(c)
    return rgb(min(247, r + t), min(247, g + t), min(247, b + t))


def _tile16(base: int, seed: int, dark: float = 0.78, light: int = 22,
            dens: float = 0.30) -> Tuple[Img, random.Random]:
    img = Img(16, 16, base)
    rnd = random.Random(seed)
    img.speckle(0, 0, 16, 16, [darken(base, dark), safe_light(base, light)], dens, rnd)
    return img, rnd


def draw_td_terrain(kind: str) -> Img:
    if kind == "grass":
        g, gd, gl = rgb(74, 152, 66), rgb(44, 106, 50), rgb(122, 202, 106)
        img, rnd = _tile16(g, 141)
        for _ in range(20):
            x, y = rnd.randrange(16), rnd.randrange(2, 16)
            img.set(x, y, gl)
            img.set(x, y - 1, gd)
        return img
    if kind == "dirt":
        d, dd, dl = rgb(126, 88, 52), rgb(88, 58, 34), rgb(162, 120, 78)
        img, rnd = _tile16(d, 142)
        for _ in range(7):
            x, y = rnd.randrange(14), rnd.randrange(14)
            img.rect(x, y, 2, 2, dd)
            img.set(x, y, dl)
        return img
    if kind == "sand":
        s, sd, sl = rgb(226, 196, 128), rgb(184, 152, 92), rgb(244, 226, 176)
        img, rnd = _tile16(s, 143, dens=0.18)
        for y in (3, 8, 13):                       # wind ripples
            img.line(0, y, 6, y, sd)
            img.line(9, y, 15, y, sl)
        return img
    if kind == "snow":
        n, ns, nl = rgb(228, 240, 250), rgb(180, 204, 228), rgb(246, 252, 255)
        img, rnd = _tile16(n, 144, dark=0.86, light=10, dens=0.22)
        for _ in range(9):
            x, y = rnd.randrange(15), rnd.randrange(15)
            img.rect(x, y, 2, 1, nl)
            img.set(x + 2, y + 1, ns)
        return img
    if kind == "rock":
        r, rd, rl = rgb(128, 132, 144), rgb(84, 88, 100), rgb(172, 176, 188)
        img, rnd = _tile16(r, 145, dens=0.36)
        img.line(2, 0, 6, 7, rd)                   # cracks
        img.line(6, 7, 4, 15, rd)
        img.line(10, 1, 13, 9, rd)
        img.line(3, 11, 9, 13, rl)                 # mineral vein
        return img
    if kind == "water_deep":
        img = Img(16, 16, rgb(34, 82, 168))
        rnd = random.Random(146)
        for y in range(16):                        # depth banding, top lighter
            img.rect(0, y, 16, 1, mix((72, 132, 214), (18, 50, 116), y / 15.0))
        for _ in range(6):
            x, y = rnd.randrange(12), rnd.randrange(15)
            img.line(x, y, x + 3, y, safe_light(img.get(x, y), 26))
        return img
    if kind == "water_shallow":
        img = Img(16, 16, rgb(74, 156, 200))
        rnd = random.Random(147)
        for y in range(16):
            img.rect(0, y, 16, 1, mix((116, 196, 232), (52, 128, 184), y / 15.0))
        for _ in range(8):
            x, y = rnd.randrange(11), rnd.randrange(15)
            img.line(x, y, x + 4, y, rgb(196, 236, 250))
            img.set(x + 5, y, rgb(150, 208, 240))
        return img
    if kind == "swamp":
        m, md, ml = rgb(72, 106, 62), rgb(40, 66, 40), rgb(126, 158, 88)
        img, rnd = _tile16(m, 148, dens=0.34)
        for _ in range(4):                         # scum pools
            x, y = rnd.randrange(12), rnd.randrange(12)
            img.ellipse(x + 2, y + 2, 2, 2, md, filled=True)
            img.set(x + 2, y + 1, ml)
        for _ in range(5):                         # reeds
            x = rnd.randrange(15)
            img.line(x, 15, x + 1, 8, md)
            img.set(x + 1, 7, ml)
        return img
    if kind == "lava":
        img = Img(16, 16, rgb(196, 62, 18))
        rnd = random.Random(149)
        for y in range(16):
            img.rect(0, y, 16, 1, mix((244, 152, 40), (140, 26, 12), y / 15.0))
        for _ in range(6):                         # cooled crust rafts
            x, y = rnd.randrange(11), rnd.randrange(11)
            img.rect(x, y, rnd.choice((3, 4)), 2, rgb(72, 34, 30))
            img.rect(x + 1, y, 1, 1, rgb(120, 58, 34))
        for _ in range(10):                        # sparks
            img.set(rnd.randrange(16), rnd.randrange(16), rgb(252, 226, 120))
        return img
    raise KeyError(kind)


TD_TERRAIN = ("grass", "dirt", "sand", "snow", "rock",
              "water_deep", "water_shallow", "swamp", "lava")


def draw_td_road(kind: str) -> Img:
    if kind == "path_dirt":
        g, gd = rgb(74, 152, 66), rgb(44, 106, 50)
        img, rnd = _tile16(g, 151, dens=0.22)
        d, dd = rgb(140, 100, 60), rgb(102, 70, 40)
        img.rect(3, 0, 10, 16, d)
        img.speckle(3, 0, 10, 16, [dd], 0.24, rnd)
        for y in range(16):                        # ragged grass edge
            if y % 3 != 1:
                img.set(2, y, gd)
                img.set(13, y, gd)
        return img
    if kind == "road_asphalt":
        img, rnd = _tile16(rgb(84, 86, 92), 152, dark=0.82, light=16, dens=0.26)
        img.rect(0, 7, 16, 2, rgb(206, 196, 90))   # centre line
        for x in range(0, 16, 6):
            img.rect(x + 3, 7, 2, 2, rgb(84, 86, 92))
        img.line(0, 0, 15, 0, rgb(58, 60, 66))
        img.line(0, 15, 15, 15, rgb(58, 60, 66))
        return img
    if kind == "bridge_wood":
        w, wd, wr = rgb(150, 100, 54), rgb(104, 66, 32), rgb(196, 150, 92)
        img, rnd = _tile16(w, 153, dens=0.16)
        for y in range(0, 16, 4):                  # planks
            img.rect(0, y, 16, 1, wd)
            img.rect(0, y + 1, 16, 1, wr)
        img.rect(0, 0, 2, 16, wd)                  # side rails
        img.rect(14, 0, 2, 16, wd)
        for y in (2, 10):
            img.set(1, y, rgb(214, 200, 170))
            img.set(14, y + 4, rgb(214, 200, 170))
        return img
    if kind == "shore":
        img = Img(16, 16, rgb(226, 196, 128))
        rnd = random.Random(154)
        img.speckle(0, 0, 16, 16, [rgb(184, 152, 92)], 0.20, rnd)
        img.rect(0, 9, 16, 7, rgb(90, 168, 210))   # water
        img.vgrad(0, 9, 16, 7, (116, 196, 232), (52, 128, 184), dither=False)
        for x in range(0, 16, 2):                  # wet sand + foam
            if x % 4:
                img.set(x, 8, rgb(176, 150, 106))
            img.set(x, 9, rgb(236, 246, 252))
        return img
    if kind == "cliff_edge":
        img, rnd = _tile16(rgb(128, 132, 144), 155, dens=0.30)
        g, gd = rgb(74, 152, 66), rgb(44, 106, 50)
        img.rect(0, 0, 16, 5, g)
        img.speckle(0, 0, 16, 5, [gd], 0.24, rnd)
        for x in range(16):                        # ragged grass lip
            h = (x * 7 % 3)
            img.rect(x, 5 + h, 1, 1, gd)
        img.rect(0, 5, 16, 2, rgb(56, 58, 68))     # shadowed rim
        return img
    if kind == "rail":
        img, rnd = _tile16(rgb(74, 152, 66), 156, dens=0.22)
        wood, iron, il = rgb(112, 74, 40), rgb(122, 126, 136), rgb(196, 202, 212)
        for y in (2, 8, 14):
            img.rect(0, y, 16, 2, wood)
        img.rect(0, 4, 16, 1, iron)
        img.rect(0, 11, 16, 1, iron)
        for y in (4, 11):                          # rail heads catch light
            img.line(0, y, 15, y, il)
            img.line(0, y + 1, 15, y + 1, iron)
        return img
    raise KeyError(kind)


TD_ROADS = ("path_dirt", "road_asphalt", "bridge_wood", "shore", "cliff_edge", "rail")


def _brick_field(img: Img, body: int, mortar: int, bw: int, bh: int) -> None:
    """Running-bond brick/stone fill over the whole 16x16 tile."""
    row = 0
    for y in range(0, 16, bh):
        off = 0 if row % 2 == 0 else bw // 2
        for x in range(-bw, 16 + bw, bw):
            img.rect(x + off, y, bw - 1, bh - 1, body)
        img.rect(0, y + bh - 1, 16, 1, mortar)
        for x in range(-bw, 16 + bw, bw):
            img.set(x + off - 1, y, mortar)
        row += 1


def draw_td_arch(kind: str) -> Img:
    if kind in ("wall_brick", "wall_stone"):
        if kind == "wall_brick":
            body, mo = rgb(166, 76, 62), rgb(206, 196, 176)
            bw, bh = 8, 4
        else:
            body, mo = rgb(134, 138, 148), rgb(88, 92, 102)
            bw, bh = 6, 5
        img = Img(16, 16, mo)
        _brick_field(img, body, mo, bw, bh)
        rnd = random.Random(160 if kind == "wall_brick" else 161)
        img.speckle(0, 0, 16, 16, [darken(body, 0.84)], 0.10, rnd)
        img.rect(0, 0, 16, 1, safe_light(body, 18))   # top light
        img.rect(0, 15, 16, 1, darken(body, 0.6))     # ground shadow
        return img
    if kind == "wall_wood":
        w, wd, wl = rgb(132, 90, 52), rgb(92, 60, 34), rgb(170, 124, 76)
        img = Img(16, 16, w)
        rnd = random.Random(162)
        for y in range(0, 16, 4):
            img.rect(0, y, 16, 3, w)
            img.rect(0, y + 3, 16, 1, wd)
            img.rect(0, y, 16, 1, wl)
        img.speckle(0, 0, 16, 16, [wd], 0.07, rnd)
        img.rect(15, 0, 1, 16, wd)
        return img
    if kind == "roof":
        base, dark, lit = rgb(154, 58, 52), rgb(104, 34, 34), rgb(196, 96, 74)
        img = Img(16, 16, base)
        for y in range(0, 16, 3):
            img.rect(0, y, 16, 1, dark)
            img.rect(0, y + 1, 16, 2, base)
            for x in range(0, 16, 4):
                img.set(x + 2, y + 2, lit)
        img.rect(0, 0, 16, 1, lit)
        img.rect(0, 15, 16, 1, dark)
        return img
    if kind == "window":
        img = draw_td_arch("wall_brick")
        fr, fg, gl = rgb(96, 62, 34), rgb(30, 40, 58), rgb(120, 176, 214)
        img.rect(2, 3, 12, 10, fr)
        img.rect(3, 4, 10, 8, fg)
        img.rect(3, 4, 10, 4, gl)
        img.line(3, 11, 12, 11, fr)
        img.rect(7, 4, 2, 8, fr)                     # mullion
        img.rect(3, 7, 10, 2, fr)
        img.rect(1, 13, 14, 1, darken(fr, 0.7))      # sill shadow
        return img
    if kind in ("door_closed", "door_open"):
        img = draw_td_arch("wall_stone")
        w, wd, gold = rgb(138, 88, 44), rgb(92, 56, 26), rgb(226, 190, 90)
        if kind == "door_closed":
            img.rect(3, 1, 10, 15, wd)
            img.rect(4, 2, 8, 14, w)
            for y in range(4, 14, 3):
                img.rect(4, y, 8, 1, wd)
            img.rect(9, 8, 2, 2, gold)
        else:
            img.rect(3, 1, 10, 15, rgb(24, 22, 34))  # dark doorway
            img.rect(3, 1, 10, 1, wd)
            img.rect(3, 1, 2, 15, w)                # leaf swung open
            img.rect(4, 1, 1, 15, wd)
            img.set(4, 8, gold)
        img.rect(2, 0, 12, 1, darken(wd, 0.7))
        return img
    if kind == "stairs":
        img = Img(16, 16, rgb(120, 124, 134))
        for i in range(4):
            y = i * 4
            img.rect(0, y, 16, 3, rgb(150, 154, 164))
            img.rect(0, y + 3, 16, 1, rgb(74, 78, 88))
            img.rect(0, y, 16, 1, rgb(186, 190, 200))
        return img
    if kind == "fence":
        img, rnd = _tile16(rgb(74, 152, 66), 163, dens=0.22)
        w, wd, wl = rgb(150, 106, 60), rgb(104, 68, 34), rgb(190, 150, 96)
        img.rect(0, 5, 16, 2, w)
        img.rect(0, 10, 16, 2, w)
        img.rect(0, 5, 16, 1, wl)
        for x in (1, 7, 13):
            img.rect(x, 2, 2, 12, w)
            img.rect(x, 2, 1, 12, wl)
            img.tri(x, 2, x + 1, 0, x + 2, 2, wd)
        return img
    if kind == "pillar":
        img, rnd = _tile16(rgb(150, 154, 164), 165, dens=0.14)
        body, dk, lt = rgb(196, 190, 176), rgb(126, 120, 110), rgb(232, 228, 214)
        img.rect(4, 2, 8, 13, body)
        img.rect(4, 2, 2, 13, lt)
        img.rect(10, 2, 2, 13, dk)
        img.rect(3, 0, 10, 2, body)                 # capital
        img.rect(3, 0, 10, 1, lt)
        img.rect(3, 13, 10, 3, body)                # base
        img.rect(3, 15, 10, 1, dk)
        for y in (4, 7, 10):
            img.line(6, y, 9, y, dk)
        return img
    raise KeyError(kind)


TD_ARCH = ("wall_brick", "wall_wood", "wall_stone", "roof", "window",
           "door_closed", "door_open", "stairs", "fence", "pillar")


def draw_td_interior(kind: str) -> Img:
    if kind == "floor_wood":
        w, wd, wl = rgb(154, 112, 66), rgb(112, 76, 42), rgb(188, 146, 96)
        img = Img(16, 16, w)
        rnd = random.Random(170)
        for y in range(0, 16, 4):
            img.rect(0, y, 16, 3, w)
            img.rect(0, y + 3, 16, 1, wd)
            img.rect(0, y, 16, 1, wl)
            img.set((y * 5 + 3) % 16, y + 1, wd)
        img.speckle(0, 0, 16, 16, [wd], 0.05, rnd)
        return img
    if kind == "floor_tile":
        a, b, gr = rgb(198, 194, 182), rgb(150, 146, 138), rgb(110, 108, 102)
        img = Img(16, 16, a)
        for y in range(0, 16, 8):
            for x in range(0, 16, 8):
                if (x + y) % 16:
                    img.rect(x, y, 8, 8, b)
        img.rect(0, 0, 16, 1, gr)
        img.rect(0, 8, 16, 1, gr)
        img.rect(0, 0, 1, 16, gr)
        img.rect(8, 0, 1, 16, gr)
        return img
    if kind == "carpet":
        base, dk, pat = rgb(148, 36, 46), rgb(96, 22, 32), rgb(214, 178, 92)
        img = Img(16, 16, base)
        rnd = random.Random(171)
        img.speckle(1, 1, 14, 14, [dk], 0.16, rnd)
        img.frame(0, 0, 16, 16, dk)
        img.frame(2, 2, 12, 12, pat)
        for x in range(4, 12, 2):
            img.set(x, 2, base)
            img.set(x, 13, base)
        img.rect(7, 6, 2, 4, pat)
        img.rect(6, 7, 4, 2, pat)
        return img
    if kind == "bookshelf":
        w, wd = rgb(120, 80, 44), rgb(84, 54, 28)
        img = Img(16, 16, w)
        img.frame(0, 0, 16, 16, wd)
        for row, y in enumerate((2, 7, 12)):
            img.rect(1, y + 4, 14, 1, wd)
            x = 2
            while x < 14:
                bw = (3, 2, 4)[(x + row) % 3]
                c = (rgb(196, 74, 62), rgb(74, 128, 196), rgb(96, 172, 92),
                     rgb(214, 178, 92))[(x * 7 + row) % 4]
                img.rect(x, y, bw, 4, c)
                img.rect(x, y, bw, 1, safe_light(c, 20))
                x += bw + 1
        return img
    if kind == "table":
        w, wd, wl = rgb(150, 100, 54), rgb(104, 66, 32), rgb(190, 142, 84)
        img = draw_td_interior("floor_wood")
        img.rect(1, 1, 14, 14, w)
        img.frame(1, 1, 14, 14, wd)
        img.rect(2, 2, 12, 2, wl)
        for x, y in ((2, 2), (12, 2), (2, 12), (12, 12)):
            img.rect(x, y, 2, 2, wd)
        img.rect(6, 6, 4, 4, wl)
        return img
    if kind == "chair":
        w, wd = rgb(140, 94, 50), rgb(98, 62, 30)
        img = draw_td_interior("floor_wood")
        img.rect(4, 1, 8, 3, w)                     # back rest
        img.frame(4, 1, 8, 3, wd)
        img.rect(4, 4, 8, 7, wd)
        img.rect(5, 5, 6, 5, w)
        img.rect(4, 11, 2, 4, wd)                   # legs
        img.rect(10, 11, 2, 4, wd)
        return img
    if kind == "bed":
        frame, sheet, blanket, pil = (rgb(120, 78, 42), rgb(232, 232, 226),
                                      rgb(88, 128, 196), rgb(244, 244, 238))
        img = draw_td_interior("floor_wood")
        img.rect(2, 1, 12, 14, frame)
        img.rect(3, 2, 10, 12, sheet)
        img.rect(3, 2, 10, 3, pil)
        img.rect(3, 5, 10, 1, darken(pil, 0.86))
        img.rect(3, 6, 10, 8, blanket)
        for y in range(7, 14, 2):
            img.line(3, y, 12, y, darken(blanket, 0.82))
        img.rect(2, 1, 12, 1, safe_light(frame, 20))
        return img
    if kind == "torch":
        img = Img(16, 16, rgb(150, 154, 164))
        rnd = random.Random(175)
        img.speckle(0, 0, 16, 16, [rgb(110, 114, 124)], 0.24, rnd)
        wood, wd = rgb(126, 86, 48), rgb(88, 58, 30)
        img.rect(7, 6, 2, 9, wood)
        img.rect(8, 6, 1, 9, wd)
        img.rect(6, 14, 4, 2, wd)
        outer, core, hot = rgb(226, 92, 26), rgb(252, 190, 60), rgb(252, 240, 170)
        img.tri(5, 8, 8, 1, 11, 8, outer)
        img.tri(6, 8, 8, 3, 10, 8, core)
        img.rect(7, 6, 2, 2, hot)
        for _ in range(4):                          # light pool on the floor
            img.set(rnd.randrange(3, 13), rnd.randrange(9, 15),
                    mix((150, 154, 164), (252, 200, 120), 0.35))
        return img
    if kind == "spikes":
        img = Img(16, 16, rgb(110, 114, 124))
        rnd = random.Random(176)
        img.speckle(0, 0, 16, 16, [rgb(80, 84, 94)], 0.22, rnd)
        body, tip, k = rgb(176, 180, 190), rgb(232, 236, 244), rgb(56, 58, 66)
        for x in (1, 6, 11):
            img.tri(x, 15, x + 2, 3, x + 4, 15, body)
            img.line(x + 2, 3, x + 2, 15, k)
            img.set(x + 2, 3, tip)
            img.set(x + 1, 4, tip)
        return img
    if kind == "fireplace":
        img = draw_td_arch("wall_stone")
        hearth, hk = rgb(96, 92, 96), rgb(48, 44, 48)
        img.rect(2, 4, 12, 11, hk)
        img.rect(3, 5, 10, 9, rgb(24, 20, 26))
        img.rect(1, 14, 14, 2, hearth)              # hearth slab
        img.rect(1, 14, 14, 1, safe_light(hearth, 18))
        outer, core, hot = rgb(196, 62, 20), rgb(244, 148, 44), rgb(252, 226, 130)
        img.tri(4, 13, 8, 6, 12, 13, outer)
        img.tri(6, 13, 8, 8, 10, 13, core)
        img.rect(7, 11, 2, 2, hot)
        img.rect(5, 2, 6, 2, hk)                    # chimney breast
        return img
    raise KeyError(kind)


TD_INTERIOR = ("floor_wood", "floor_tile", "carpet", "bookshelf", "table",
               "chair", "bed", "torch", "spikes", "fireplace")


def draw_td_prop(kind: str) -> Img:
    """Flora and clutter that sit on top of a ground tile."""
    ground, gd = rgb(74, 152, 66), rgb(44, 106, 50)
    img, rnd = _tile16(ground, 180 + len(kind), dens=0.20)
    if kind == "bush":
        leaf, ld, ll = rgb(58, 132, 56), rgb(34, 88, 40), rgb(104, 186, 92)
        img.circle(6, 10, 5, ld, filled=True)
        img.circle(10, 9, 5, leaf, filled=True)
        img.circle(8, 7, 4, leaf, filled=True)
        img.circle(7, 6, 2, ll, filled=True)
        for _ in range(5):
            img.set(rnd.randrange(4, 13), rnd.randrange(5, 12), rgb(214, 74, 96))
        img.rect(2, 14, 12, 1, gd)
    elif kind == "flowers":
        for _ in range(7):
            x, y = rnd.randrange(2, 14), rnd.randrange(4, 15)
            c = (rgb(244, 226, 120), rgb(226, 96, 132), rgb(150, 190, 244))[x % 3]
            img.set(x, y, c)
            img.set(x - 1, y, c)
            img.set(x + 1, y, c)
            img.set(x, y - 1, c)
            img.set(x, y + 1, gd)
            img.set(x, y + 2, rgb(52, 118, 52))
    elif kind == "rock_small":
        body, dk, lt = rgb(146, 150, 160), rgb(96, 100, 110), rgb(196, 200, 208)
        img.circle(6, 11, 4, body, filled=True)
        img.circle(10, 12, 3, body, filled=True)
        img.circle(6, 11, 4, dk)
        img.circle(10, 12, 3, dk)
        img.circle(5, 10, 2, lt, filled=True)
        img.rect(3, 14, 10, 1, gd)
    elif kind == "stump":
        w, wd, rings = rgb(146, 104, 60), rgb(96, 62, 32), rgb(184, 146, 96)
        img.rect(4, 6, 8, 9, w)
        img.frame(4, 6, 8, 9, wd)
        img.ellipse(8, 7, 4, 2, rings, filled=True)
        img.ellipse(8, 7, 3, 1, wd)
        img.ellipse(8, 7, 1, 1, rings, filled=True)
        for x in (5, 9):
            img.rect(x, 15, 2, 1, wd)
        img.rect(2, 12, 2, 3, rgb(58, 132, 56))
    elif kind == "barrel":
        w, wd, hoop = rgb(146, 100, 54), rgb(104, 66, 32), rgb(74, 78, 88)
        img.rect(4, 3, 8, 12, w)
        img.rect(3, 5, 10, 8, w)
        img.frame(3, 5, 10, 8, wd)
        img.rect(4, 3, 8, 1, hoop)
        img.rect(3, 8, 10, 1, hoop)
        img.rect(4, 14, 8, 1, hoop)
        img.ellipse(8, 3, 4, 1, wd, filled=True)
        for x in (5, 7, 9):
            img.line(x, 4, x, 14, wd)
    elif kind == "pot":
        clay, cd, cl = rgb(178, 106, 66), rgb(126, 68, 40), rgb(214, 150, 100)
        img.rect(4, 6, 8, 8, clay)
        img.rect(3, 5, 10, 2, cd)
        img.rect(4, 6, 8, 1, cl)
        img.rect(5, 13, 6, 1, cd)
        img.frame(4, 6, 8, 8, cd)
        img.rect(6, 1, 4, 4, rgb(58, 132, 56))
        img.set(8, 0, rgb(104, 186, 92))
        img.set(6, 2, rgb(34, 88, 40))
    elif kind == "gravestone":
        stone, dk, lt = rgb(150, 154, 164), rgb(100, 104, 114), rgb(196, 200, 208)
        img.rect(4, 4, 8, 11, stone)
        img.ellipse(8, 5, 4, 3, stone, filled=True)
        img.ellipse(8, 5, 4, 3, dk)
        img.frame(4, 4, 8, 11, dk)
        img.line(6, 7, 10, 7, dk)
        img.line(6, 9, 10, 9, dk)
        img.line(8, 11, 8, 13, dk)
        img.line(6, 12, 10, 12, dk)
        img.rect(5, 5, 1, 9, lt)
        img.rect(2, 14, 12, 1, gd)
    else:
        raise KeyError(kind)
    return img


TD_PROPS = ("bush", "flowers", "rock_small", "stump", "barrel", "pot", "gravestone")


# ------------------------------------------------- side-scroller / platformer
def draw_sp_tile(kind: str, frame: int = 0) -> Img:
    dirt, dk = rgb(126, 88, 52), rgb(88, 58, 34)
    grass, gl = rgb(74, 152, 66), rgb(122, 202, 106)
    if kind.startswith("ground"):
        img, rnd = _tile16(dirt, 190 + len(kind), dens=0.28)
        for _ in range(6):
            x, y = rnd.randrange(14), rnd.randrange(6, 14)
            img.rect(x, y, 2, 2, dk)
        if kind == "ground_corner_l":
            for x in range(8, 16):
                img.rect(x, 0, 1, 4, grass)
            img.rect(4, 0, 4, 3, grass)
            img.rect(2, 0, 2, 2, grass)
        elif kind == "ground_corner_r":
            for x in range(0, 8):
                img.rect(x, 0, 1, 4, grass)
            img.rect(8, 0, 4, 3, grass)
            img.rect(12, 0, 2, 2, grass)
        else:
            img.rect(0, 0, 16, 4, grass)
        for x in range(16):                        # ragged grass lip
            if x % 3:
                img.set(x, 4, dk)
        img.rect(0, 0, 16, 1, gl)
        img.rect(0, 15, 16, 1, dk)
        return img
    if kind == "float_block":
        body, edge, bolt = rgb(176, 132, 74), rgb(112, 76, 40), rgb(226, 202, 150)
        img = Img(16, 16, body)
        rnd = random.Random(195)
        img.speckle(1, 1, 14, 14, [edge], 0.10, rnd)
        img.frame(0, 0, 16, 16, edge)
        img.rect(0, 0, 16, 1, safe_light(body, 22))
        img.rect(0, 15, 16, 1, darken(body, 0.6))
        for x, y in ((2, 2), (12, 2), (2, 12), (12, 12)):
            img.rect(x, y, 2, 2, bolt)
        img.line(3, 8, 12, 8, edge)
        return img
    if kind == "ice":
        body, deep, shine = rgb(150, 202, 236), rgb(96, 156, 208), rgb(226, 246, 255)
        img = Img(16, 16, body)
        img.rect(0, 0, 16, 3, shine)
        img.rect(0, 3, 16, 1, body)
        img.rect(0, 12, 16, 4, deep)
        for x in range(0, 16, 5):                  # facets
            img.line(x + 1, 4, x + 3, 11, shine)
            img.line(x + 3, 11, x + 1, 15, deep)
        img.rect(11, 5, 2, 1, shine)
        return img
    if kind == "mud":
        body, dk, wet = rgb(104, 74, 46), rgb(66, 44, 26), rgb(146, 112, 70)
        img, rnd = _tile16(body, 196, dark=0.72, light=14, dens=0.30)
        for _ in range(5):                         # sucking bubbles
            x, y = rnd.randrange(3, 13), rnd.randrange(3, 13)
            img.circle(x, y, 2, wet)
            img.set(x - 1, y - 1, safe_light(wet, 18))
            img.set(x, y, dk)
        img.rect(0, 0, 16, 1, dk)
        return img
    if kind == "conveyor":
        plate, belt, arrow = rgb(120, 124, 136), rgb(56, 58, 66), rgb(232, 190, 70)
        img = Img(16, 16, plate)
        img.rect(0, 3, 16, 10, belt)
        img.rect(0, 3, 16, 1, safe_light(plate, 18))
        img.rect(0, 12, 16, 1, darken(plate, 0.6))
        off = frame * 4 % 8
        for x in range(-8, 16, 8):                 # moving chevrons
            img.line(x + off, 6, x + off + 2, 8, arrow)
            img.line(x + off + 2, 8, x + off, 10, arrow)
        for x in (1, 5, 9, 13):                    # rollers under the lip
            img.circle(x + 1, 14, 1, darken(plate, 0.5), filled=True)
        return img
    raise KeyError(kind)


SP_TILES = ("ground_top", "ground_corner_l", "ground_corner_r",
            "float_block", "ice", "mud", "conveyor")


def draw_sp_hazard(kind: str, frame: int = 0) -> Img:
    if kind == "spikes":
        img, _ = _tile16(rgb(126, 88, 52), 197, dens=0.24)
        img.rect(0, 12, 16, 4, rgb(96, 66, 36))
        body, tip, k = rgb(176, 180, 190), rgb(236, 240, 248), rgb(56, 58, 66)
        for x in (1, 6, 11):
            img.tri(x, 12, x + 2, 3, x + 4, 12, body)
            img.line(x + 2, 3, x + 2, 12, k)
            img.set(x + 2, 3, tip)
            img.set(x + 1, 5, tip)
        img.rect(0, 15, 16, 1, k)
        return img
    img = Img(16, 16, WHITE)                       # spinning saw blade
    steel, rim, tooth, hub = (rgb(150, 156, 168), rgb(78, 84, 98),
                              rgb(198, 204, 216), rgb(48, 52, 64))
    a0 = frame * 22.5
    for i in range(8):                             # teeth reach past the disc
        a = math.radians(a0 + i * 45)
        img.tri(8 + int(5 * math.cos(a)), 8 + int(5 * math.sin(a)),
                8 + int(7 * math.cos(a - 0.26)), 8 + int(7 * math.sin(a - 0.26)),
                8 + int(6 * math.cos(a + 0.34)), 8 + int(6 * math.sin(a + 0.34)),
                tooth)
    img.circle(8, 8, 5, steel, filled=True)
    img.circle(8, 8, 5, rim)
    img.circle(8, 8, 2, hub, filled=True)
    for i in range(3):                             # motion glints
        a = math.radians(a0 + 30 + i * 120)
        img.set(8 + int(math.cos(a) * 4), 8 + int(math.sin(a) * 4), tooth)
    return img


SP_HAZARDS = ("spikes", "saw")


# ------------------------------------------------------- parallax backgrounds
def draw_bg_layer(kind: str, w: int = 240) -> Img:
    h = {"sky_day": 120, "clouds_far": 64, "mountains_mid": 96,
         "forest_near": 96, "night_moon": 120}[kind]
    img = Img(w, h, BLACK)
    rnd = random.Random(200 + _stable(kind))
    if kind == "sky_day":
        img.vgrad(0, 0, w, h, (96, 176, 232), (206, 236, 252), dither=True)
        for _ in range(5):                         # soft high cloud
            cx, cy = rnd.randrange(w), rnd.randrange(8, 34)
            for i in range(4):
                img.ellipse(cx + i * 7 - 10, cy + (i % 2) * 2, 9, 4,
                            rgb(232, 244, 252), filled=True)
        return img
    if kind == "clouds_far":
        img.vgrad(0, 0, w, h, (150, 200, 240), (206, 232, 248), dither=False)
        for _ in range(9):
            cx, cy = rnd.randrange(w), rnd.randrange(6, h - 8)
            body = rgb(238, 248, 255) if rnd.random() < 0.5 else rgb(206, 226, 244)
            for i in range(rnd.choice((3, 4))):
                img.ellipse(cx + i * 8, cy + (i % 2) * 3, rnd.randrange(7, 12),
                            rnd.randrange(4, 7), body, filled=True)
            img.rect(cx - 4, cy + 4, 26, 3, darken(body, 0.88))
        return img
    if kind == "mountains_mid":
        img.vgrad(0, 0, w, h, (110, 150, 196), (176, 206, 232), dither=True)
        for i, (cx, bh) in enumerate(((30, 46), (86, 62), (150, 40),
                                      (206, 58), (250, 44))):
            rock, lit = (rgb(84, 100, 132), rgb(126, 146, 176)) if i % 2 else \
                        (rgb(64, 80, 112), rgb(104, 124, 156))
            img.tri(cx - bh, h, cx, h - bh, cx + bh, h, rock)
            img.line(cx, h - bh, cx - bh, h, lit)
            cap = max(6, bh // 4)
            img.tri(cx - cap, h - bh + cap, cx, h - bh, cx + cap, h - bh + cap,
                    rgb(238, 247, 255))
        img.rect(0, h - 6, w, 6, rgb(52, 66, 94))
        return img
    if kind == "forest_near":
        img.rect(0, 0, w, h, rgb(28, 58, 44))
        for i in range(0, w, 14):                  # layered conifer row
            bh = 34 + (i * 7 % 26)
            tone = rgb(38, 84, 56) if (i // 14) % 2 else rgb(24, 62, 44)
            for k in range(3):
                y = h - bh + k * (bh // 3)
                half = 5 + k * 3
                img.tri(i - half, y + bh // 3 + 2, i, y, i + half,
                        y + bh // 3 + 2, tone)
            img.rect(i - 2, h - 10, 4, 10, rgb(58, 40, 28))
        img.rect(0, h - 8, w, 8, rgb(40, 30, 22))
        for _ in range(60):
            img.set(rnd.randrange(w), rnd.randrange(h - 14, h), rgb(58, 106, 68))
        return img
    # night_moon
    img.vgrad(0, 0, w, h, (16, 22, 58), (56, 70, 122), dither=True)
    for _ in range(70):
        x, y = rnd.randrange(w), rnd.randrange(h - 30)
        img.set(x, y, rgb(232, 238, 252) if rnd.random() < 0.3 else rgb(160, 178, 220))
    img.circle(180, 30, 14, rgb(244, 244, 226), filled=True)
    img.circle(176, 26, 11, rgb(252, 252, 240), filled=True)
    for cx, cy, r in ((174, 34, 3), (186, 24, 2), (182, 38, 2)):
        img.circle(cx, cy, r, rgb(206, 210, 200), filled=True)
    for i, (cx, bh) in enumerate(((40, 40), (110, 56), (190, 36))):
        img.tri(cx - bh, h, cx, h - bh, cx + bh, h, rgb(24, 30, 62))
    img.rect(0, h - 10, w, 10, rgb(16, 20, 44))
    return img


BG_LAYERS = ("sky_day", "clouds_far", "mountains_mid", "forest_near", "night_moon")


def draw_ui_dialogue_frame() -> Img:
    """160x96 nine-patch-friendly dialogue box."""
    w, h = 160, 96
    img = Img(w, h, rgb(24, 30, 52))
    edge, mid, lit = rgb(232, 236, 252), rgb(96, 130, 210), rgb(160, 190, 244)
    img.vgrad(0, 4, w, h - 8, (74, 104, 176), (28, 38, 74), dither=False)
    img.frame(0, 0, w, h, edge, t=1)
    img.frame(1, 1, w - 2, h - 2, mid)
    img.line(2, 2, w - 3, 2, lit)
    img.line(2, 2, 2, h - 3, lit)
    for cx, cy in ((2, 2), (w - 5, 2), (2, h - 5), (w - 5, h - 5)):
        img.rect(cx, cy, 3, 3, edge)
        img.set(cx + 1, cy + 1, mid)
    img.rect(6, 6, w - 12, 14, darken(mid, 0.7))   # name plate
    img.frame(6, 6, w - 12, 14, edge)
    for x in range(10, 60, 4):
        img.set(x, 12, lit)
    img.rect(w - 24, h - 18, 4, 4, edge)           # next-page arrow
    img.rect(w - 22, h - 14, 4, 4, edge)
    return img

# ------------------------------------------------- top-down character rig
def _pal(**kw) -> Dict[str, int]:
    base = dict(skin=rgb(240, 190, 140), hair=rgb(96, 58, 28),
                shirt=rgb(64, 120, 208), pants=rgb(48, 54, 84),
                shoe=rgb(28, 28, 40), out=rgb(18, 24, 38))
    base.update(kw)
    return base


def _td_person(d: int, action: str, frame: int, pal: Dict[str, int]) -> Img:
    """16x16 top-down humanoid. `d`: 0 down, 1 left, 2 up, 3 right."""
    img = Img(16, 16, WHITE)
    out = pal["out"]
    if action == "die":
        body = darken(pal["shirt"], 0.8)
        img.ellipse(8, 13, 6, 3, body, filled=True)
        img.ellipse(8, 13, 6, 3, out)
        img.circle(4 if d != 1 else 12, 12, 3, pal["skin"], filled=True)
        img.circle(4 if d != 1 else 12, 12, 3, out)
        for ex in ((3, 12), (5, 12)) if d != 1 else ((11, 12), (13, 12)):
            img.set(ex[0], ex[1], out)
        img.rect(1, 14, 14, 1, darken(pal["pants"], 0.7))
        return img
    prof = d in (1, 3)
    back = d == 2
    step = (0, 1, 0, -1)[frame % 4] if action == "walk" else \
        (1, -1)[frame % 2] if action == "run" else 0
    bob = 1 if (action in ("idle", "hurt") and frame % 2) or step else 0
    lean = (1 if d == 3 else -1) if action == "run" else 0
    if action == "hurt":                           # recoil away from the hit
        lean = (-1 if d == 3 else 1) if d in (1, 3) else 0
    x0, w0 = (6, 4) if prof else (5, 6)
    tx = x0 + lean                                   # torso column (run lean)
    hy, by = 1 - bob, 7 - bob
    # torso
    img.rect(tx, by, w0, 5, pal["shirt"])
    img.rect(tx, by, w0, 1, safe_light(pal["shirt"], 22))
    img.rect(tx, by + 4, w0, 1, darken(pal["shirt"], 0.7))
    img.frame(tx, by, w0, 5, out)
    # head
    img.rect(tx, hy, w0, 6, pal["skin"])
    img.frame(tx, hy, w0, 6, out)
    img.rect(tx + 1, hy, w0 - 2, 2, pal["hair"])
    if back:
        img.rect(tx + 1, hy, w0 - 2, 5, pal["hair"])
    elif prof:
        img.rect(tx + (1 if d == 3 else w0 - 2), hy, 1, 4, pal["hair"])
        img.set(tx + (w0 - 2 if d == 3 else 1), hy + 3, out)
    else:
        for ex in (tx + 1, tx + w0 - 2):
            img.set(ex, hy + 3, out)
    # legs: feet stay on the baseline, the swinging leg lifts and shifts
    for i, planted in enumerate((step != -1, step != 1)):
        lx = x0 + (0 if i == 0 else w0 - 2)
        lh = 4 if planted else 3
        if not planted and d in (1, 3):
            lx += 1 if d == 3 else -1
        img.rect(lx, 15 - lh, 2, lh, pal["pants"])
        img.rect(lx, 14, 2, 1, pal["shoe"])
        img.set(lx, 15 - lh, safe_light(pal["pants"], 14))
    # arms
    ay = by + 1
    arm = darken(pal["shirt"], 0.82)
    up = action in ("cast", "dig") and frame == 0
    for ax in ((tx - 2, tx + w0) if not prof else (tx - 1, tx + w0 - 1)):
        if up and ax == (tx + w0 if not prof else tx + w0 - 1):
            img.rect(ax, hy - 2, 2, 4, arm)
            img.rect(ax, hy - 2, 2, 1, pal["skin"])
        else:
            img.rect(ax, ay, 2, 4, arm)
            img.rect(ax, ay + 3, 2, 1, pal["skin"])
    if action == "hurt" and not prof:
        for ex in (tx + 1, tx + w0 - 2):
            img.set(ex, hy + 3, out)
            img.set(ex + 1, hy + 4, out)
    return img


TD_ACTIONS = {
    "idle": 2, "walk": 4, "run": 2, "attack": 2, "cast": 2, "hurt": 1,
    "die": 2, "pickup": 2, "push": 2, "dig": 2, "water": 2, "fish": 2,
}


def draw_td_player(d: int, action: str, frame: int) -> Img:
    """Farmer/adventurer doing one of the taxonomy's interaction actions."""
    pal = _pal()
    img = _td_person(d, action, frame, pal)
    steel, wood, gold = rgb(196, 206, 220), rgb(126, 86, 48), rgb(232, 190, 70)
    fx = {0: 0, 1: -1, 2: 0, 3: 1}[d]              # which side props sit on
    sgn = fx or 1
    cx = 8 + fx * 4                                # working hand column
    if action == "attack":
        for i in range(4):                         # blade pointing forward
            x = cx + sgn * i
            img.set(x, 6 - i, steel)
            img.set(x + sgn, 6 - i, safe_light(steel, 22))
        img.rect(min(cx, cx + sgn), 7, 2, 2, wood)
        if frame == 1:                             # swing arc
            for i in range(5):
                img.set(cx + sgn * (i - 1), 3 + abs(i - 2), rgb(244, 248, 255))
    elif action == "cast":
        cy = 2 if frame == 0 else 9
        img.circle(cx, cy, 2, rgb(120, 200, 252), filled=True)
        img.circle(cx, cy, 2, rgb(220, 244, 255))
        for i in range(3):
            img.set(cx + sgn * (2 + i), cy, rgb(96, 168, 236))
    elif action == "hurt":
        img.rect(7, 0, 2, 1, rgb(252, 246, 190))            # impact spark
        img.set(6, 1, rgb(252, 200, 90))
        img.set(9, 1, rgb(252, 200, 90))
    elif action == "dig":
        top = 2 if frame else 11                   # pick overhead -> struck
        img.line(cx - sgn * 2, 9, cx + sgn * 2, top + 2, wood)
        img.rect(cx - 1, top, 4, 2, steel)
        img.rect(cx - 1, top, 4, 1, safe_light(steel, 20))
        if not frame:
            for i in range(3):                     # dirt spray
                img.set(cx + sgn * (2 + i), 13 - i, rgb(112, 76, 42))
    elif action == "pickup":
        img.line(cx, 9, cx + sgn * 3, 13, darken(pal["shirt"], 0.82))
        img.circle(cx + sgn * 4, 13, 2, gold, filled=True)
        img.circle(cx + sgn * 4, 13, 2, darken(gold, 0.6))
    elif action == "push":
        x0 = cx + sgn if sgn > 0 else cx - 4
        img.rect(x0, 8, 4, 7, wood)
        img.frame(x0, 8, 4, 7, darken(wood, 0.6))
        img.line(x0, 11, x0 + 3, 11, darken(wood, 0.6))
    elif action == "water":
        x0 = cx + sgn if sgn > 0 else cx - 4
        img.rect(x0, 7, 4, 4, rgb(96, 150, 200))            # can body
        img.frame(x0, 7, 4, 4, rgb(40, 74, 122))
        img.rect(x0 + (4 if sgn > 0 else -2), 6, 2, 1, rgb(96, 150, 200))
        img.line(x0 + 1, 6, x0 + 2, 5, rgb(40, 74, 122))    # handle
        for i in range(3 if frame else 0):                  # droplets
            img.set(x0 + (5 if sgn > 0 else -3) - i, 8 + i * 2, rgb(150, 208, 240))
    elif action == "fish":
        tipx = cx + sgn * 5
        img.line(cx - sgn, 8, tipx, 2, wood)
        img.line(tipx, 2, tipx, 10 + frame * 2, rgb(226, 236, 252))
        img.circle(tipx, 12 + frame * 2, 1, rgb(226, 66, 66), filled=True)
    return img


def draw_td_enemy(kind: str, frame: int) -> Img:
    """Goblin / skeleton / orc / zombie / villager / merchant / dragon."""
    if kind == "dragon":
        img = Img(32, 24, WHITE)
        body, belly, spike = rgb(96, 158, 74), rgb(196, 214, 120), rgb(226, 196, 90)
        dk, out = darken(body, 0.7), rgb(18, 24, 38)
        lift = frame % 2
        for i, lx in enumerate((6, 12, 18, 24)):   # legs
            h = 5 - (1 if (i + lift) % 2 else 0)
            img.rect(lx, 17 - h, 3, h + 1, dk)
            img.rect(lx, 18, 3, 2, body)
        img.ellipse(16, 13, 9, 5, body, filled=True)
        img.rect(9, 12, 14, 3, belly)
        img.ellipse(16, 13, 9, 5, out)
        img.circle(25, 9, 4, body, filled=True)    # head
        img.circle(25, 9, 4, out)
        img.rect(28, 8, 3, 3, body)
        img.set(27, 8, rgb(244, 226, 120))         # eye
        img.set(26, 9, out)
        img.tri(22, 5, 24, 1, 26, 5, spike)        # horns
        img.tri(24, 14, 26, 18, 28, 14, spike)
        for x in range(8, 22, 4):                  # back spikes
            img.tri(x, 9, x + 2, 4, x + 4, 9, spike)
        img.line(7, 13, 1, 9 + (frame % 2) * 3, body)   # tail
        img.line(1, 9 + (frame % 2) * 3, 0, 7, dk)
        wing = rgb(150, 96, 176) if frame % 2 else rgb(120, 74, 148)
        img.tri(12, 10, 18, 2 + lift * 4, 22, 10, wing)
        img.tri(12, 10, 18, 2 + lift * 4, 22, 10, out)
        return img
    pals = {
        "goblin": _pal(skin=rgb(116, 186, 96), shirt=rgb(150, 112, 60),
                       pants=rgb(84, 62, 38), hair=rgb(64, 92, 52)),
        "skeleton": _pal(skin=rgb(226, 228, 220), shirt=rgb(186, 188, 178),
                         pants=rgb(150, 152, 144), hair=rgb(206, 208, 200)),
        "orc": _pal(skin=rgb(66, 112, 56), shirt=rgb(96, 52, 40),
                    pants=rgb(46, 38, 32), hair=rgb(34, 50, 30)),
        "zombie": _pal(skin=rgb(140, 168, 132), shirt=rgb(88, 106, 120),
                       pants=rgb(58, 66, 78), hair=rgb(70, 88, 74)),
        "villager": _pal(skin=rgb(232, 186, 138), shirt=rgb(160, 122, 74),
                         pants=rgb(88, 70, 56), hair=rgb(120, 82, 44)),
        "merchant": _pal(skin=rgb(236, 190, 142), shirt=rgb(196, 74, 96),
                         pants=rgb(64, 58, 88), hair=rgb(58, 44, 34)),
    }
    pal = pals[kind]
    act = "walk" if frame % 2 else "idle"
    img = _td_person(0, act, frame, pal)
    if kind == "skeleton":
        for y in range(8, 12, 2):                  # rib cage
            img.line(5, y, 10, y, rgb(150, 152, 144))
        img.set(6, 10, rgb(40, 44, 52))
        img.set(9, 10, rgb(40, 44, 52))
    if kind in ("goblin", "orc"):
        img.tri(3, 3, 1, 5, 4, 6, pal["skin"])     # ears
        img.tri(12, 3, 14, 5, 11, 6, pal["skin"])
        img.set(6, 11, rgb(244, 244, 236))         # tusks
        img.set(9, 11, rgb(244, 244, 236))
    if kind == "goblin":
        img.line(12, 9, 15, 5, rgb(196, 206, 220))   # dagger
        img.set(13, 9, rgb(126, 86, 48))
    if kind == "orc":
        img.rect(12, 5, 2, 7, rgb(126, 86, 48))      # club
        img.rect(11, 3, 4, 3, rgb(158, 112, 62))
        img.frame(11, 3, 4, 3, rgb(84, 56, 30))
    if kind == "zombie":
        img.rect(4, 8, 8, 2, darken(pal["shirt"], 0.7))
        img.set(6, 4, rgb(60, 80, 60))
        img.set(9, 5, rgb(60, 80, 60))
    if kind == "merchant":
        img.rect(4, 1, 8, 2, rgb(232, 190, 70))    # hat band
        img.rect(3, 0, 10, 1, rgb(150, 96, 46))
    return img


TD_ENEMIES = ("goblin", "skeleton", "orc", "zombie", "villager", "merchant",
              "dragon")


# ------------------------------------------------------------- item icons
def draw_td_icon(kind: str) -> Img:
    img = Img(16, 16, WHITE)
    steel, edge, dk = rgb(188, 198, 214), rgb(240, 246, 255), rgb(108, 118, 136)
    wood, wd, gold = rgb(146, 100, 54), rgb(104, 66, 32), rgb(232, 190, 70)
    out = rgb(24, 28, 42)
    if kind == "bow":
        img.ellipse(6, 8, 5, 6, wood)
        img.line(10, 2, 10, 14, rgb(226, 226, 210))
        img.line(6, 8, 13, 8, wood)
        img.tri(13, 6, 15, 8, 13, 10, steel)
        img.set(14, 8, edge)
    elif kind == "staff":
        img.line(3, 14, 11, 2, wood)
        img.line(4, 14, 12, 2, wd)
        img.circle(12, 2, 3, rgb(74, 128, 196), filled=True)
        img.circle(12, 2, 3, rgb(150, 208, 240))
        img.set(11, 1, rgb(226, 246, 255))
        img.rect(4, 11, 3, 1, gold)
    elif kind == "helmet":
        img.ellipse(8, 8, 6, 5, steel, filled=True)
        img.rect(2, 9, 12, 3, dk)
        img.ellipse(8, 8, 6, 5, out)
        img.line(3, 6, 8, 3, edge)
        img.rect(7, 1, 2, 4, gold)                 # crest
        img.rect(4, 9, 8, 1, rgb(30, 34, 48))      # visor slit
    elif kind == "armor":
        img.rect(3, 3, 10, 9, steel)
        img.frame(3, 3, 10, 9, out)
        img.rect(1, 2, 3, 4, steel)                # pauldrons
        img.rect(12, 2, 3, 4, steel)
        img.frame(1, 2, 3, 4, out)
        img.frame(12, 2, 3, 4, out)
        img.line(8, 4, 8, 11, dk)
        img.line(4, 7, 12, 7, dk)
        img.set(5, 5, edge)
    elif kind == "boots":
        leather, sole, lit = rgb(158, 108, 58), rgb(64, 52, 44), rgb(206, 160, 104)
        for x in (2, 9):
            img.rect(x, 2, 4, 6, leather)                # shaft
            img.rect(x - 1, 8, 6, 3, leather)            # foot
            img.frame(x - 1, 8, 6, 3, out)
            img.rect(x - 1, 10, 6, 1, sole)
            img.rect(x, 2, 1, 6, lit)
            img.rect(x, 5, 4, 1, gold)                   # buckle strap
    elif kind == "potion_mana":
        glass, liquid = rgb(190, 214, 236), rgb(56, 122, 232)
        img.rect(6, 1, 4, 2, rgb(150, 110, 40))
        img.rect(5, 3, 6, 2, glass)
        img.circle(8, 10, 4, glass, filled=True)
        img.circle(8, 10, 3, liquid, filled=True)
        img.frame(4, 6, 8, 9, out)
        img.set(6, 8, rgb(150, 200, 252))
    elif kind == "wood":
        for y, x in ((4, 2), (8, 4), (12, 1)):
            img.ellipse(x + 3, y, 3, 2, wood, filled=True)
            img.ellipse(x + 3, y, 3, 2, wd)
            img.circle(x + 3, y, 1, rgb(190, 150, 96), filled=True)
        img.line(11, 3, 14, 1, rgb(58, 132, 56))
    elif kind == "meat":
        img.ellipse(8, 9, 6, 5, rgb(196, 92, 84), filled=True)
        img.ellipse(8, 9, 6, 5, out)
        img.ellipse(6, 7, 3, 2, rgb(232, 140, 128), filled=True)
        img.rect(11, 3, 4, 3, rgb(236, 232, 220))  # bone
        img.frame(11, 3, 4, 3, out)
        img.set(3, 11, rgb(150, 62, 58))
    elif kind == "ore":
        face, lit, sh = rgb(132, 156, 180), rgb(186, 208, 226), rgb(84, 108, 136)
        img.tri(2, 14, 6, 4, 10, 14, face)
        img.tri(6, 14, 10, 6, 14, 14, sh)
        img.line(6, 4, 10, 14, out)
        img.line(2, 14, 14, 14, out)
        img.set(6, 6, lit)
        img.set(5, 9, lit)
        img.rect(9, 11, 2, 2, rgb(150, 208, 240))  # crystal inclusion
    elif kind == "gold":
        img.circle(8, 8, 6, gold, filled=True)
        img.circle(8, 8, 6, darken(gold, 0.6))
        img.circle(8, 8, 4, rgb(252, 226, 120), filled=True)
        img.rect(7, 4, 2, 8, gold)
        img.set(5, 6, rgb(252, 246, 190))
    else:
        raise KeyError(kind)
    return img


TD_ICONS = ("bow", "staff", "helmet", "armor", "boots", "potion_mana",
            "wood", "meat", "ore", "gold")


# ----------------------------------------------------------------- UI layer
def draw_td_ui(kind: str) -> Img:
    if kind == "cursor":
        img = Img(12, 14, WHITE)
        ink = rgb(244, 248, 255)
        for y in range(9):                         # arrowhead, tip at top-left
            img.rect(1, 1 + y, y + 1, 1, ink)
        img.rect(1, 10, 4, 1, ink)                 # flat head base, then the stem
        for y, w in enumerate((3, 3, 2, 1)):
            img.rect(1, 11 + y, w, 1, ink)
        outline(img, rgb(24, 28, 42))
        return img
    if kind == "button":
        img = Img(32, 14, WHITE)
        face, edge, lit = rgb(64, 140, 92), rgb(24, 52, 36), rgb(126, 202, 140)
        img.rect(0, 0, 32, 14, edge)
        img.rect(1, 1, 30, 12, face)
        img.rect(1, 1, 30, 1, lit)
        img.rect(1, 1, 1, 12, lit)
        img.rect(1, 12, 30, 1, darken(face, 0.6))
        img.center_text(5, "OK", rgb(244, 248, 255), 1, shadow=darken(face, 0.5))
        return img
    if kind == "slot":
        img = Img(16, 16, WHITE)
        plate, edge, lit = rgb(58, 62, 84), rgb(24, 28, 42), rgb(120, 126, 152)
        img.rect(0, 0, 16, 16, edge)
        img.rect(1, 1, 14, 14, plate)
        img.line(1, 1, 14, 1, lit)
        img.line(1, 1, 1, 14, lit)
        img.line(2, 13, 13, 13, darken(plate, 0.7))
        return img
    body, dk, tip = (rgb(226, 66, 78), rgb(120, 24, 40), rgb(252, 176, 176)) \
        if kind == "hp_bar" else (rgb(56, 122, 232), rgb(24, 66, 148), rgb(160, 214, 252))
    img = Img(40, 8, WHITE)
    img.rect(0, 0, 40, 8, rgb(24, 28, 42))
    img.rect(1, 1, 38, 6, rgb(48, 52, 70))
    img.rect(1, 1, 27, 6, body)
    img.rect(1, 1, 27, 1, tip)
    img.rect(1, 6, 27, 1, dk)
    for x in range(4, 38, 8):                      # segment ticks
        img.set(x, 1, rgb(24, 28, 42))
        img.set(x, 2, rgb(24, 28, 42))
    return img


TD_UI = ("cursor", "button", "slot", "hp_bar", "mp_bar")


# --------------------------------------------------------------- VFX layer
def draw_td_vfx(kind: str, frame: int) -> Img:
    if kind == "dust":
        img = Img(16, 16, WHITE)
        puff = rgb(214, 202, 176)
        n = (2, 3, 4, 3)[frame % 4]
        for i in range(n):
            r = 2 + (frame % 3)
            img.circle(3 + i * 4, 11 - (i % 2) * 2 - frame, r, puff, filled=True)
            img.circle(3 + i * 4, 11 - (i % 2) * 2 - frame, r, darken(puff, 0.86))
        return img
    if kind == "slash":
        img = Img(24, 24, WHITE)
        core, glow = rgb(244, 248, 255), rgb(150, 208, 240)
        rad, a1 = ((12, -35), (14, -5), (16, 12))[frame % 3]
        cx, cy, a0, n = 4, 20, -85.0, 34
        thick = (1.5, 2.3, 3.1)[frame % 3]
        for i in range(72):                        # crescent: thin-thick-thin
            t = i / 71.0
            a = math.radians(a0 + (a1 - a0) * t)
            half = thick * (0.34 + 0.66 * math.sin(math.pi * t))
            for k in range(-4, 5):
                d = k + 0.5
                if abs(d) > half:
                    continue
                img.set(cx + math.cos(a) * (rad + d), cy + math.sin(a) * (rad + d),
                        core if abs(d) < half * 0.55 else glow)
        return img
    if kind == "magic_bullet":
        img = Img(14, 10, WHITE)
        core, halo = rgb(226, 246, 255), rgb(96, 168, 236)
        off = frame * 2
        img.ellipse(7, 5, 5, 3, halo, filled=True)
        img.ellipse(7, 5, 3, 2, core, filled=True)
        for i in range(3):                         # trailing sparks
            img.set(1 - i + off // 2, 5 + (i % 2) - 1, halo)
        return img
    if kind == "sparkle":
        img = Img(12, 12, WHITE)
        r = (3, 5, 2)[frame % 3]
        c = rgb(252, 246, 190)
        img.line(6 - r, 6, 6 + r, 6, c)
        img.line(6, 6 - r, 6, 6 + r, c)
        img.set(6, 6, rgb(255, 255, 240))
        if r > 2:
            img.line(4, 4, 8, 8, darken(c, 0.8))
            img.line(8, 4, 4, 8, darken(c, 0.8))
        return img
    raise KeyError(kind)


TD_VFX = {"dust": 4, "slash": 3, "magic_bullet": 2, "sparkle": 3}


# ------------------------------------------------------------------ build
def build_all(only: str = "") -> Dict[str, List[str]]:
    made: Dict[str, List[str]] = {}

    def emit(category: str, name: str, img: Img, sub: str = "") -> None:
        if only and category != only:
            return
        folder = category_dir(category)
        if sub:
            folder = folder.joinpath(*sub.split("/"))
            folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"{name}.vpe"
        save_vpe(path, img.w, img.h, img.px)
        made.setdefault(category, []).append(name)

    titlesets = {
        "rpg_title_screen": title_rpg,
        "platformer_title_screen": title_platformer,
        "arcade_shooter_title": title_shooter,
        "match3_title_screen": title_puzzle,
        "game_over_screen": screen_game_over,
        "pause_menu_screen": screen_pause,
        "arctic_title_screen": screen_arctic_title,
        "arctic_play_screen": screen_arctic_play,
        "arctic_shop_screen": screen_arctic_shop,
    }
    for name, fn in titlesets.items():
        emit("titleset", name, fn())

    sprites = {
        "hero_idle": draw_hero(0), "hero_walk_0": draw_hero(1),
        "hero_walk_1": draw_hero(2), "hero_walk_2": draw_hero(3),
        "slime_0": draw_slime(0), "slime_1": draw_slime(1),
        "bat_0": draw_bat(0), "bat_1": draw_bat(1),
        "ghost_0": draw_ghost(0), "ghost_1": draw_ghost(1),
        "mushroom": draw_mushroom(), "tree": draw_tree(),
        "coin_0": draw_coin(0), "coin_1": draw_coin(1),
        "coin_2": draw_coin(2), "coin_3": draw_coin(3),
        "key": draw_key(), "potion_red": draw_potion("red"),
        "potion_green": draw_potion("green"), "potion_blue": draw_potion("blue"),
        "sword": draw_sword(False), "sword_flip": draw_sword(True),
        "chest_closed": draw_chest(False), "chest_open": draw_chest(True),
        "heart_full": draw_heart(True), "heart_empty": draw_heart(False),
        "player_ship": draw_ship(), "bullet_0": draw_bullet(0), "bullet_1": draw_bullet(1),
        "explosion_0": draw_explosion(0), "explosion_1": draw_explosion(1),
        "explosion_2": draw_explosion(2), "explosion_3": draw_explosion(3),
    }
    sprites.update({
        "ar_worker_idle_0": draw_ar_worker("idle", 0),
        "ar_worker_idle_1": draw_ar_worker("idle", 1),
        "ar_worker_walk_0": draw_ar_worker("walk", 0),
        "ar_worker_walk_1": draw_ar_worker("walk", 1),
        "ar_worker_dig": draw_ar_worker("dig"),
        "ar_worker_carry": draw_ar_worker("carry"),
        "ar_miner_jacket_0": draw_ar_miner_jacket(0),
        "ar_miner_jacket_1": draw_ar_miner_jacket(1),
        "ar_guard_idle": draw_ar_guard(0),
        "ar_guard_aim": draw_ar_guard(1),
        "ar_bear_0": draw_ar_bear(0),
        "ar_bear_1": draw_ar_bear(1),
        "ar_bear_roar": draw_ar_bear(2),
        "ar_ore_pile_0": draw_ar_ore_pile(0),
        "ar_ore_pile_1": draw_ar_ore_pile(1),
        "ar_crystal_0": draw_ar_crystal(0),
        "ar_crystal_1": draw_ar_crystal(1),
        "ar_machine_idle": draw_ar_machine(0),
        "ar_machine_run": draw_ar_machine(1),
        "ar_truck": draw_ar_truck(0),
        "ar_truck_snow": draw_ar_truck(1),
        "ar_sign_ore": draw_ar_sign("ORE", AR_BLUE),
        "ar_sign_factory": draw_ar_sign("FACTORY", AR_NAVY),
        "ar_sign_guard": draw_ar_sign("GUARD", AR_BLUE, 1),
        "ar_sign_sell": draw_ar_sign("SELL", AR_GRN),
        "ar_sign_arrow": draw_ar_sign("^", AR_BLUE),
        "ar_fence": draw_ar_fence(0),
        "ar_fence_worn": draw_ar_fence(1),
        "ar_lamp": draw_ar_lamp(0),
        "ar_lamp_lit": draw_ar_lamp(1),
        "ar_steps": draw_ar_steps(0),
        "ar_hp_bar": draw_ar_hp_bar(0),
        "ar_hp_bar_low": draw_ar_hp_bar(2),
        "ar_coin_0": draw_ar_coin(0),
        "ar_coin_1": draw_ar_coin(1),
        "ar_snowflake_0": draw_ar_snowflake(0),
        "ar_snowflake_1": draw_ar_snowflake(1),
    })
    for name, img in sprites.items():
        emit("sprite", name, img)

    for name in AR_ICONS:
        emit("sprite", f"ar_icon_{name}", draw_ar_icon(name))

    tiles = {
        "grass": draw_grass(), "dirt": draw_dirt(), "sand": draw_sand(),
        "snow": draw_snow(), "stone_floor": draw_stone_floor(),
        "wall_brick": draw_wall_brick(), "spike": draw_spike(),
        "ladder": draw_ladder(), "checkpoint": draw_checkpoint(),
        "hole": draw_hole(), "bridge": draw_bridge(),
        "water_0": draw_water(0), "water_1": draw_water(1),
        "lava_0": draw_lava(0), "lava_1": draw_lava(1),
        "torch_0": draw_torch(0), "torch_1": draw_torch(1),
        "door_closed": draw_door("closed"), "door_open": draw_door("open"),
    }
    for name in ("flat", "dots", "chip", "crack", "drift", "ice"):
        tiles[f"ar_snow_{name}"] = draw_ar_tile(name)
    tiles["ar_sea_0"] = draw_ar_tile("sea", 0)
    tiles["ar_sea_1"] = draw_ar_tile("sea", 1)
    for side in ("top", "left", "right", "tl", "tr"):
        tiles[f"ar_edge_{side}"] = draw_ar_edge(side)
    for name, img in tiles.items():
        emit("tile", name, img)

    textures = {
        "brick_wall": draw_brick_wall(), "cobble_stone": draw_cobble(),
        "wood_planks": draw_wood(), "metal_plate": draw_metal(),
        "lava_flow": draw_lava_flow(), "water_ripple": draw_water_ripple(),
        "grass_sheet": draw_grass_sheet(), "hud_health_bar": draw_hud_bar(),
        "ui_menu_panel": draw_menu_panel((160, 128)),
        "arctic_hud_bar": draw_ar_hud_bar(),
        "arctic_shop_panel": draw_ar_shop_panel(),
        "arctic_mountain_bg": draw_ar_mountain_sheet(),
        "arctic_snow_surface": draw_ar_snow_sheet(),
    }
    for name, img in textures.items():
        emit("texture", name, img)

    # ---- taxonomy families (docs/ASSET_TAXONOMY.md)
    td_groups = (
        ("topdown/terrain", TD_TERRAIN, draw_td_terrain),
        ("topdown/roads", TD_ROADS, draw_td_road),
        ("topdown/architecture", TD_ARCH, draw_td_arch),
        ("topdown/interior", TD_INTERIOR, draw_td_interior),
        ("topdown/flora", TD_PROPS, draw_td_prop),
    )
    for sub, kinds, fn in td_groups:
        for kind in kinds:
            emit("tile", f"td_{kind}", fn(kind), sub=sub)
    for kind in SP_TILES:
        if kind == "conveyor":
            continue
        emit("tile", f"sp_{kind}", draw_sp_tile(kind), sub="side/platform")
    for f in (0, 1):
        emit("tile", f"sp_conveyor_{f}", draw_sp_tile("conveyor", f),
             sub="side/platform")
    emit("tile", "sp_spikes", draw_sp_hazard("spikes"), sub="side/hazard")
    for f in (0, 1):
        emit("tile", f"sp_saw_{f}", draw_sp_hazard("saw", f), sub="side/hazard")

    for kind in BG_LAYERS:
        emit("texture", f"bg_{kind}", draw_bg_layer(kind), sub="background/parallax")
    emit("texture", "ui_dialogue_frame", draw_ui_dialogue_frame(), sub="ui")

    dirs = ("down", "left", "up", "right")
    for di, dname in enumerate(dirs):
        for action in ("idle", "walk", "run"):
            for f in range(TD_ACTIONS[action]):
                emit("sprite", f"td_hero_{dname}_{action}_{f}",
                     draw_td_player(di, action, f), sub="characters/player")
    for action in ("attack", "cast", "hurt", "die", "pickup", "push",
                   "dig", "water", "fish"):
        for f in range(TD_ACTIONS[action]):
            emit("sprite", f"td_hero_right_{action}_{f}",
                 draw_td_player(3, action, f), sub="characters/player")
    for kind in TD_ENEMIES:
        for f in range(2):
            emit("sprite", f"td_{kind}_{f}", draw_td_enemy(kind, f),
                 sub="enemies")
    for kind in TD_ICONS:
        emit("sprite", f"ic_{kind}", draw_td_icon(kind), sub="items/icons")
    for kind in TD_UI:
        emit("sprite", f"hud_{kind}", draw_td_ui(kind), sub="ui/hud")
    for kind, frames in TD_VFX.items():
        for f in range(frames):
            emit("sprite", f"fx_{kind}_{f}", draw_td_vfx(kind, f),
                 sub="vfx/particles")

    return made


def main(argv: Sequence[str]) -> int:
    only = ""
    if "--only" in argv:
        only = argv[argv.index("--only") + 1]
    made = build_all(only)
    total = sum(len(v) for v in made.values())
    print(f"Drew {total} sample assets into Documents\\VPE Pixel")
    for category in sorted(made):
        folder = category_dir(category)
        print(f"  {category:<9} {len(made[category]):>3}  {folder}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
