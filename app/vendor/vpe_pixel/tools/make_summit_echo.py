#!/usr/bin/env python3
"""make_summit_echo.py — detailed SummitEcho art per docs/ai_ui_design.

Style (PROMPTS.md B2):
  8/16-bit retro sprite, bold 1px black outline, two-tone highlight/shadow,
  chibi-readable on 240x320, RGB565-safe palette.

Outputs:
  Documents\\VPE Pixel\\summitecho\\{sprite,tile,texture,titleset}\\*.png|.vpe
  <SummitEcho>\\assets\\preview\\summit_echo_{sheet,mock}.png
  <SummitEcho>\\src\\pixel_art_data.lua

Run:  python tools/make_summit_echo.py [--only a,b] [--no-sheet] [--no-vpe] [--no-lua]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

TOOLROOT = Path(__file__).resolve().parent
SYSROOT = TOOLROOT.parent
for _p in (str(SYSROOT), str(TOOLROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from PIL import Image, ImageDraw  # noqa: E402

from vpx_editor import vpe as VPE  # noqa: E402

GAME = Path(r"C:\Users\doxuanhop\Documents\LuaS30 Projects\SummitEcho")
ROOT = Path.home() / "Documents" / "VPE Pixel" / "summitecho"
SHEET = GAME / "assets" / "preview" / "summit_echo_sheet.png"
MOCK = GAME / "assets" / "preview" / "summit_echo_mock.png"
LUA_OUT = GAME / "src" / "pixel_art_data.lua"

# ---------------------------------------------------------------- palette
# Tight RGB565-safe set: outline + base + shadow + highlight (+ accents).
OUT = (8, 10, 14)            # bold black outline
WHITE = (236, 240, 228)
INK = (18, 22, 28)

# sky / far
SKY1 = (108, 142, 162)
SKY2 = (128, 156, 168)
SKY3 = (154, 176, 176)
CLOUD = (198, 214, 214)
CLOUD_HI = (232, 238, 230)
CLOUD_SH = (150, 168, 170)
FAR = (98, 104, 100)
FAR_HI = (132, 132, 112)
FAR_DK = (68, 76, 74)
SNOW = (230, 236, 228)
SNOW_SH = (170, 186, 186)

# forest
FOREST = (42, 72, 64)
FOREST_HI = (64, 108, 82)
FOREST_DK = (24, 48, 44)

# stone / moss
STONE = (36, 50, 50)
STONE_HI = (58, 76, 72)
STONE_DK = (22, 32, 34)
MOSS = (78, 124, 52)
MOSS_HI = (128, 168, 72)
MOSS_DK = (42, 82, 42)

# wood
WOOD = (122, 86, 48)
WOOD_HI = (168, 124, 72)
WOOD_DK = (78, 52, 30)

# metal / ice
STEEL = (168, 180, 180)
STEEL_HI = (214, 222, 218)
STEEL_DK = (100, 116, 118)
ICE = (150, 210, 220)
ICE_HI = (210, 240, 246)
ICE_DK = (60, 130, 160)

# character
HAIR = (172, 62, 48)
HAIR_HI = (214, 96, 72)
HAIR_DK = (112, 36, 32)
SKIN = (230, 186, 130)
SKIN_SH = (186, 132, 92)
COAT = (72, 96, 140)
COAT_HI = (108, 140, 180)
COAT_DK = (42, 58, 92)
PANTS = (48, 56, 72)
PANTS_HI = (72, 82, 100)
BOOT = (40, 36, 34)
BOOT_HI = (72, 64, 56)
GOLD = (228, 188, 72)
GOLD_HI = (246, 220, 130)
RED = (196, 72, 56)
RED_HI = (230, 110, 88)


def new(w: int, h: int) -> Image.Image:
    return Image.new("RGBA", (w, h), (0, 0, 0, 0))


def px(im: Image.Image, x: int, y: int, c) -> None:
    if 0 <= x < im.width and 0 <= y < im.height:
        if len(c) == 4:
            im.putpixel((x, y), c)
        else:
            im.putpixel((x, y), (c[0], c[1], c[2], 255))


def rect(im: Image.Image, x: int, y: int, w: int, h: int, c) -> None:
    for yy in range(y, y + h):
        for xx in range(x, x + w):
            px(im, xx, yy, c)


def hline(im: Image.Image, x: int, y: int, w: int, c) -> None:
    rect(im, x, y, w, 1, c)


def vline(im: Image.Image, x: int, y: int, h: int, c) -> None:
    rect(im, x, y, 1, h, c)


def frame(im: Image.Image, x: int, y: int, w: int, h: int, c) -> None:
    hline(im, x, y, w, c)
    hline(im, x, y + h - 1, w, c)
    vline(im, x, y, h, c)
    vline(im, x + w - 1, y, h, c)


def outline(im: Image.Image, color=OUT) -> None:
    """1px bold outline around every opaque cluster (ai_ui_design B2)."""
    w, h = im.size
    src = im.copy()
    sp = src.load()
    op = im.load()
    for y in range(h):
        for x in range(w):
            if sp[x, y][3] >= 128:
                continue
            for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                nx, ny = x + dx, y + dy
                if 0 <= nx < w and 0 <= ny < h and sp[nx, ny][3] >= 128:
                    op[x, y] = (color[0], color[1], color[2], 255)
                    break


def shade_block(im, x, y, w, h, base, hi=None, dk=None):
    """Two-tone block: base fill, top/left highlight, bottom/right shadow."""
    rect(im, x, y, w, h, base)
    if hi:
        hline(im, x, y, w, hi)
        vline(im, x, y, h, hi)
    if dk:
        hline(im, x, y + h - 1, w, dk)
        vline(im, x + w - 1, y, h, dk)


# ---------------------------------------------------------------- player


def player_base(pose: str) -> Image.Image:
    """18x22 chibi climber, facing right. Bold outline, two-tone shading."""
    im = new(18, 22)

    # ---- boots (grounded variants spread feet)
    if pose in ("run0",):
        rect(im, 2, 18, 5, 3, BOOT)
        rect(im, 11, 17, 5, 3, BOOT)
    elif pose in ("run1",):
        rect(im, 4, 17, 5, 3, BOOT)
        rect(im, 10, 18, 5, 3, BOOT)
    elif pose == "jump":
        rect(im, 2, 18, 5, 3, BOOT)
        rect(im, 11, 16, 5, 3, BOOT)
    elif pose == "dash":
        rect(im, 3, 18, 6, 3, BOOT)
        rect(im, 11, 18, 5, 3, BOOT)
    elif pose == "wall":
        rect(im, 4, 18, 5, 3, BOOT)
        rect(im, 10, 17, 5, 3, BOOT)
    else:
        rect(im, 3, 18, 5, 3, BOOT)
        rect(im, 10, 18, 5, 3, BOOT)
    hline(im, 3, 20, 4, BOOT_HI)
    hline(im, 10, 20, 4, BOOT_HI)

    # ---- legs / pants
    if pose in ("run0",):
        rect(im, 3, 14, 4, 5, PANTS)
        rect(im, 11, 13, 4, 5, PANTS)
    elif pose in ("run1",):
        rect(im, 5, 13, 4, 5, PANTS)
        rect(im, 10, 14, 4, 5, PANTS)
    elif pose == "jump":
        rect(im, 3, 13, 4, 6, PANTS)
        rect(im, 11, 12, 4, 5, PANTS)
    elif pose == "dash":
        rect(im, 4, 14, 5, 5, PANTS)
        rect(im, 11, 14, 4, 5, PANTS)
    else:
        rect(im, 4, 13, 4, 6, PANTS)
        rect(im, 10, 13, 4, 6, PANTS)
    px(im, 4, 13, PANTS_HI)
    px(im, 10, 13, PANTS_HI)

    # ---- torso coat
    shade_block(im, 3, 7, 12, 7, COAT, COAT_HI, COAT_DK)
    # zipper / seam
    vline(im, 9, 8, 5, COAT_DK)
    # belt
    hline(im, 3, 13, 12, WOOD_DK)
    px(im, 8, 13, GOLD)
    px(im, 9, 13, GOLD_HI)
    # scarf
    rect(im, 3, 6, 12, 2, RED)
    hline(im, 3, 6, 12, RED_HI)
    px(im, 2, 7, RED)
    px(im, 15, 7, RED)

    # ---- arms
    if pose in ("run0", "dash"):
        shade_block(im, 13, 8, 3, 5, COAT, COAT_HI, COAT_DK)
        px(im, 14, 12, SKIN)
        px(im, 15, 12, SKIN_SH)
    elif pose == "run1":
        shade_block(im, 1, 8, 3, 5, COAT, COAT_HI, COAT_DK)
        px(im, 1, 12, SKIN)
        px(im, 2, 12, SKIN_SH)
    elif pose == "jump":
        shade_block(im, 13, 5, 3, 4, COAT, COAT_HI, COAT_DK)
        shade_block(im, 1, 6, 3, 4, COAT, COAT_HI, COAT_DK)
        px(im, 14, 8, SKIN)
        px(im, 1, 9, SKIN)
    elif pose == "wall":
        shade_block(im, 14, 7, 3, 6, COAT, COAT_HI, COAT_DK)
        px(im, 15, 12, SKIN)
    else:
        shade_block(im, 13, 8, 2, 5, COAT, COAT_HI, COAT_DK)
        px(im, 13, 12, SKIN)

    # ---- head (chibi, larger)
    shade_block(im, 4, 2, 11, 7, SKIN, SKIN, SKIN_SH)
    # cheek
    px(im, 5, 6, SKIN_SH)
    px(im, 6, 7, SKIN_SH)

    # eyes: white sclera + dark pupil
    if pose == "hurt":
        # X eyes
        for dx, dy in ((0, 0), (1, 1), (1, -1), (-1, 1), (-1, -1)):
            px(im, 9 + dx, 5 + dy, OUT)
            px(im, 13 + dx, 5 + dy, OUT)
    else:
        # left eye
        rect(im, 8, 4, 3, 3, WHITE)
        px(im, 9, 5, OUT)
        px(im, 10, 5, OUT)
        # right eye
        rect(im, 12, 4, 3, 3, WHITE)
        px(im, 13, 5, OUT)
        px(im, 14, 5, OUT)
        # brow
        hline(im, 8, 3, 3, HAIR_DK)
        hline(im, 12, 3, 3, HAIR_DK)

    # mouth
    if pose == "hurt":
        hline(im, 10, 8, 4, OUT)
    elif pose in ("dash", "jump"):
        rect(im, 11, 7, 3, 2, RED)
        px(im, 11, 7, RED_HI)
    else:
        hline(im, 11, 7, 3, SKIN_SH)

    # ---- hair: bold red mass + sweep
    rect(im, 3, 0, 13, 3, HAIR)
    hline(im, 3, 0, 13, HAIR_HI)
    # fringe / sweep to the right
    rect(im, 3, 2, 3, 5, HAIR)
    px(im, 3, 2, HAIR_DK)
    px(im, 3, 6, HAIR_DK)
    rect(im, 14, 1, 3, 3, HAIR)
    px(im, 16, 1, HAIR_HI)
    if pose in ("run0", "dash", "jump"):
        # wind-blown tuft
        rect(im, 0, 2, 3, 2, HAIR)
        px(im, 0, 2, HAIR_HI)
        px(im, 1, 1, HAIR_HI)
    if pose == "wall":
        rect(im, 15, 3, 2, 3, HAIR_DK)

    # ---- dash glint
    if pose == "dash":
        px(im, 6, -0 if False else 0, ICE_HI)  # keep in-bounds
        px(im, 7, 0, ICE_HI)
        px(im, 8, 0, ICE)

    outline(im)
    return im


def player_sprites() -> dict[str, Image.Image]:
    return {
        "player_idle": player_base("idle"),
        "player_run0": player_base("run0"),
        "player_run1": player_base("run1"),
        "player_jump": player_base("jump"),
        "player_wall": player_base("wall"),
        "player_dash": player_base("dash"),
        "player_hurt": player_base("hurt"),
    }


# ---------------------------------------------------------------- tiles


def platform_tiles() -> dict[str, Image.Image]:
    out = {}

    def base_tile() -> Image.Image:
        t = new(16, 16)
        # stone body with brick joints
        rect(t, 0, 0, 16, 16, STONE)
        hline(t, 0, 4, 16, STONE_DK)
        hline(t, 0, 8, 16, STONE_DK)
        hline(t, 0, 12, 16, STONE_DK)
        vline(t, 5, 5, 3, STONE_DK)
        vline(t, 11, 9, 3, STONE_DK)
        vline(t, 3, 13, 3, STONE_DK)
        # brick highlights
        hline(t, 1, 5, 3, STONE_HI)
        hline(t, 7, 9, 3, STONE_HI)
        hline(t, 9, 13, 3, STONE_HI)
        # moss crown with scallop
        rect(t, 0, 0, 16, 5, MOSS)
        hline(t, 0, 0, 16, MOSS_HI)
        hline(t, 0, 4, 16, MOSS_DK)
        for x in (0, 3, 6, 9, 12, 15):
            px(t, x, 5, MOSS_DK)
        for x in (1, 4, 7, 10, 13):
            px(t, x, 1, MOSS_HI)
            px(t, x + 1, 2, MOSS_DK)
        # small grass blades on crown
        for x, hgt in ((2, 2), (8, 3), (14, 2)):
            for i in range(hgt):
                px(t, x, 1 - i if i else 0, MOSS_HI if i == 0 else MOSS)
        return t

    t = base_tile()
    out["plat_top"] = t

    L = base_tile()
    vline(L, 0, 0, 16, OUT)
    vline(L, 1, 5, 11, STONE_HI)
    # left moss drip
    px(L, 1, 5, MOSS_DK)
    px(L, 1, 6, MOSS)
    out["plat_left"] = L

    R = base_tile()
    vline(R, 15, 0, 16, OUT)
    vline(R, 14, 5, 11, STONE_HI)
    px(R, 14, 5, MOSS_DK)
    out["plat_right"] = R

    f = new(16, 16)
    rect(f, 0, 0, 16, 16, STONE)
    for y in (0, 5, 10, 15):
        hline(f, 0, y, 16, STONE_DK)
    for y, xs in ((1, (2, 10)), (6, (7, 14)), (11, (1, 9))):
        for x in xs:
            vline(f, x, y, 4, STONE_DK)
            px(f, x + 1, y, STONE_HI)
    out["plat_fill"] = f

    tuft = new(14, 10)
    # clumped grass blades with outline support
    for i, (x, hgt, col) in enumerate((
        (1, 5, MOSS), (3, 7, MOSS_HI), (5, 6, MOSS), (7, 8, MOSS_HI),
        (9, 5, MOSS), (11, 4, MOSS_HI), (12, 3, MOSS),
    )):
        y0 = 10 - hgt
        for j in range(hgt):
            px(tuft, x, y0 + j, col if j > 0 else MOSS_HI)
        px(tuft, x, y0 - 1 if y0 > 0 else 0, MOSS_HI)
    # dirt dots at root
    px(tuft, 2, 9, MOSS_DK)
    px(tuft, 8, 9, MOSS_DK)
    outline(tuft, MOSS_DK)
    out["moss_tuft"] = tuft
    return out


def ladder_seg() -> Image.Image:
    im = new(14, 18)
    # rails
    shade_block(im, 1, 0, 3, 18, WOOD, WOOD_HI, WOOD_DK)
    shade_block(im, 10, 0, 3, 18, WOOD, WOOD_HI, WOOD_DK)
    # rungs with highlight
    for y in (3, 9, 15):
        shade_block(im, 3, y, 8, 2, WOOD, WOOD_HI, WOOD_DK)
    # grain
    for y in (1, 7, 13):
        px(im, 2, y, WOOD_DK)
        px(im, 11, y + 2, WOOD_DK)
    outline(im)
    return im


def crate() -> Image.Image:
    im = new(18, 18)
    shade_block(im, 1, 1, 16, 16, WOOD, WOOD_HI, WOOD_DK)
    # panel inset
    frame(im, 3, 3, 12, 12, WOOD_DK)
    rect(im, 4, 4, 10, 10, WOOD)
    hline(im, 4, 4, 10, WOOD_HI)
    # diagonal braces
    for i in range(5):
        px(im, 5 + i, 5 + i, WOOD_HI)
        px(im, 12 - i, 5 + i, WOOD_HI)
        px(im, 5 + i, 6 + i, WOOD_DK)
    # corner nails
    for x, y in ((3, 3), (13, 3), (3, 13), (13, 13)):
        px(im, x, y, STEEL)
        px(im, x, y + 1, STEEL_DK)
    outline(im)
    return im


def spike() -> Image.Image:
    im = new(10, 12)
    # three-tone metal spike
    px(im, 4, 0, STEEL_HI)
    px(im, 5, 0, STEEL_HI)
    rect(im, 3, 1, 4, 2, STEEL)
    rect(im, 2, 3, 6, 3, STEEL)
    rect(im, 1, 6, 8, 3, STEEL)
    # highlight edge
    px(im, 3, 1, STEEL_HI)
    px(im, 4, 2, STEEL_HI)
    vline(im, 3, 2, 3, STEEL_HI)
    # shadow side
    px(im, 6, 2, STEEL_DK)
    vline(im, 7, 5, 3, STEEL_DK)
    # base plate
    rect(im, 0, 9, 10, 3, STEEL_DK)
    hline(im, 0, 9, 10, STEEL)
    hline(im, 0, 11, 10, OUT)
    outline(im)
    return im


def shard() -> Image.Image:
    im = new(12, 18)
    # crystal body
    px(im, 5, 0, ICE_HI)
    px(im, 6, 0, ICE_HI)
    rect(im, 4, 1, 4, 2, ICE_HI)
    rect(im, 3, 3, 6, 5, ICE)
    rect(im, 4, 8, 4, 6, ICE)
    rect(im, 5, 14, 2, 3, ICE_DK)
    # facets / sparkle
    px(im, 4, 2, WHITE)
    px(im, 3, 4, ICE_HI)
    px(im, 4, 5, ICE_HI)
    px(im, 7, 4, ICE_DK)
    px(im, 8, 5, ICE_DK)
    px(im, 5, 9, ICE_HI)
    px(im, 6, 10, WHITE)
    px(im, 5, 12, ICE_HI)
    # ground glow dots
    px(im, 1, 15, ICE_DK)
    px(im, 10, 14, ICE_DK)
    px(im, 2, 16, ICE)
    px(im, 9, 16, ICE)
    outline(im)
    return im


def checkpoint(active: bool) -> Image.Image:
    im = new(22, 36)
    # pole with grain
    shade_block(im, 3, 2, 4, 32, WOOD, WOOD_HI, WOOD_DK)
    px(im, 4, 6, WOOD_DK)
    px(im, 4, 14, WOOD_DK)
    px(im, 4, 22, WOOD_DK)
    # flag
    if active:
        base, hi, dk, inner = GOLD, GOLD_HI, WOOD_DK, WOOD_DK
    else:
        base, hi, dk, inner = STEEL, STEEL_HI, STEEL_DK, PANEL if False else STEEL_DK
    shade_block(im, 7, 4, 13, 12, base, hi, dk)
    rect(im, 9, 6, 9, 8, WOOD_DK if active else STEEL_DK)
    rect(im, 10, 7, 7, 6, GOLD if active else STEEL)
    if active:
        # star badge
        px(im, 13, 9, GOLD_HI)
        px(im, 12, 10, GOLD)
        px(im, 13, 10, GOLD_HI)
        px(im, 14, 10, GOLD)
        px(im, 13, 11, GOLD)
    else:
        hline(im, 11, 10, 5, STEEL_HI)
        px(im, 13, 9, WHITE)
    # flag tip pennant
    px(im, 19, 4, hi)
    px(im, 20, 5, hi)
    # foot wedge
    rect(im, 2, 30, 6, 5, WOOD)
    px(im, 2, 34, WOOD_DK)
    px(im, 7, 34, WOOD_DK)
    outline(im)
    return im


def goal() -> Image.Image:
    im = new(32, 40)
    # twin posts
    shade_block(im, 2, 2, 5, 36, WOOD, WOOD_HI, WOOD_DK)
    shade_block(im, 25, 2, 5, 36, WOOD, WOOD_HI, WOOD_DK)
    # gold top bar
    shade_block(im, 2, 2, 28, 6, GOLD, GOLD_HI, WOOD_DK)
    # banner
    shade_block(im, 7, 9, 18, 14, COAT, COAT_HI, COAT_DK)
    rect(im, 9, 11, 14, 10, COAT_DK)
    # mountain glyph
    for i, w in enumerate((2, 4, 6, 8, 10)):
        hline(im, 16 - w // 2, 13 + i, w, COAT_HI)
    px(im, 15, 12, SNOW)
    px(im, 16, 12, SNOW)
    # gold footings
    shade_block(im, 0, 34, 8, 5, GOLD, GOLD_HI, WOOD_DK)
    shade_block(im, 24, 34, 8, 5, GOLD, GOLD_HI, WOOD_DK)
    # little flags on posts
    px(im, 2, 1, GOLD_HI)
    px(im, 29, 1, GOLD_HI)
    outline(im)
    return im


def pine() -> Image.Image:
    im = new(22, 34)
    # trunk
    shade_block(im, 8, 24, 5, 10, WOOD, WOOD_HI, WOOD_DK)
    # layered boughs with light/dark
    layers = (
        (9, 20, 4, FOREST, FOREST_HI, FOREST_DK),
        (8, 15, 5, FOREST, FOREST_HI, FOREST_DK),
        (6, 10, 5, FOREST, FOREST_HI, FOREST_DK),
        (4, 5, 5, FOREST, FOREST_HI, FOREST_DK),
        (2, 1, 4, FOREST, FOREST_HI, FOREST_DK),
    )
    for half, top, rows, base, hi, dk in layers:
        for r in range(rows):
            y = top + r
            w = half * 2 + 1
            x = 11 - half
            rect(im, x, y, w, 1, base)
            if r == 0:
                hline(im, x, y, w, hi)
            if r == rows - 1:
                hline(im, x, y, w, dk)
            # side tips
            px(im, x, y, dk)
            px(im, x + w - 1, y, dk)
    # snow flecks on boughs
    for x, y in ((9, 3), (7, 8), (13, 8), (6, 13), (15, 13), (8, 18), (13, 18)):
        px(im, x, y, SNOW)
    outline(im)
    return im


def pine_far() -> Image.Image:
    im = new(14, 22)
    shade_block(im, 5, 16, 3, 6, WOOD_DK, WOOD, WOOD_DK)
    for half, top in ((5, 11), (4, 7), (3, 4), (2, 1)):
        for r in range(4):
            y = top + r
            x = 7 - half
            w = half * 2 + 1
            rect(im, x, y, w, 1, FOREST)
            if r == 0:
                hline(im, x, y, w, FOREST_HI)
            if r == 3:
                hline(im, x, y, w, FOREST_DK)
    outline(im, FOREST_DK)
    return im


def cloud(w: int = 52, h: int = 16) -> Image.Image:
    im = new(w, h)
    cy = h // 2
    # puffy mass
    rect(im, 8, cy - 3, w - 16, 8, CLOUD)
    rect(im, 12, cy - 5, 18, 7, CLOUD)
    rect(im, 22, cy - 7, 18, 9, CLOUD)
    rect(im, 34, cy - 4, 12, 7, CLOUD)
    # highlight tops
    hline(im, 14, cy - 5, 14, CLOUD_HI)
    hline(im, 24, cy - 7, 14, CLOUD_HI)
    px(im, 13, cy - 4, CLOUD_HI)
    px(im, 36, cy - 3, CLOUD_HI)
    # soft underside
    hline(im, 10, cy + 4, w - 20, CLOUD_SH)
    hline(im, 16, cy + 5, w - 32, CLOUD_SH)
    outline(im, CLOUD_SH)
    return im


def cloud_small() -> Image.Image:
    return cloud(30, 12)


def mountain_far() -> Image.Image:
    """96x78 detailed distant massif with snow caps."""
    im = new(96, 78)
    # main peak
    for y in range(78):
        frac = y / 77
        half = int(44 * frac)
        cx = 48
        ypix = y
        rect(im, cx - half, ypix, half * 2 + 1, 1, FAR)
        if 8 < y < 42:
            snow = max(1, int(half * 0.30))
            rect(im, cx - half, ypix, snow, 1, SNOW if y < 22 else SNOW_SH)
        if y > 55:
            rect(im, cx - half, ypix, half * 2 + 1, 1, FAR_DK)
        if y % 7 == 3 and half > 4:
            # ridge striations
            rect(im, cx - half + 2, ypix, max(1, half // 3), 1, FAR_HI)
    # secondary peak left
    for y in range(48):
        frac = y / 47
        half = int(22 * frac)
        cx = 18
        rect(im, cx - half, 30 + y, half * 2 + 1, 1, FAR_DK)
        if 32 < y + 30 < 48:
            rect(im, cx - half, 30 + y, max(1, half // 3), 1, FAR_HI)
    # secondary peak right
    for y in range(40):
        frac = y / 39
        half = int(18 * frac)
        cx = 82
        rect(im, cx - half, 38 + y, half * 2 + 1, 1, FAR_DK)
    return im


def dash_trail() -> Image.Image:
    im = new(18, 8)
    # streak with two-tone
    rect(im, 1, 3, 4, 2, ICE_DK)
    rect(im, 5, 2, 5, 3, ICE)
    rect(im, 10, 2, 5, 3, ICE_HI)
    rect(im, 15, 3, 2, 2, WHITE)
    px(im, 2, 2, ICE)
    px(im, 12, 1, ICE_HI)
    px(im, 3, 5, ICE_DK)
    outline(im, ICE_DK)
    return im


def hud_shard() -> Image.Image:
    im = new(10, 10)
    px(im, 4, 0, ICE_HI)
    rect(im, 3, 1, 4, 2, ICE)
    rect(im, 3, 3, 3, 4, ICE)
    px(im, 3, 1, WHITE)
    px(im, 4, 7, ICE_DK)
    outline(im, ICE_DK)
    return im


def logo_mark() -> Image.Image:
    """Mountain emblem for splash/title — outlined two-tone peaks."""
    im = new(48, 28)
    # left peak
    for i, w in enumerate((8, 12, 16, 20, 24)):
        hline(im, 14 - w // 2, 12 + i, w, FAR_HI if i < 2 else FAR)
    # snow cap left
    hline(im, 12, 12, 4, SNOW)
    hline(im, 11, 13, 6, SNOW)
    px(im, 14, 12, WHITE)
    # right peak
    for i, w in enumerate((6, 10, 14, 18)):
        hline(im, 32 - w // 2, 10 + i, w, FAR if i < 2 else FAR_DK)
    hline(im, 30, 10, 4, SNOW)
    hline(im, 29, 11, 6, SNOW_SH)
    # sun
    rect(im, 36, 2, 8, 8, GOLD)
    rect(im, 37, 3, 6, 6, GOLD_HI)
    px(im, 38, 4, WHITE)
    # ground moss line
    hline(im, 4, 23, 40, MOSS)
    hline(im, 6, 24, 36, MOSS_HI)
    hline(im, 8, 25, 32, MOSS_DK)
    # tiny pines
    for x in (6, 12, 38):
        px(im, x, 21, FOREST_DK)
        px(im, x, 20, FOREST)
        px(im, x, 19, FOREST_HI)
    outline(im)
    return im


def build_all() -> dict[str, tuple[str, Image.Image]]:
    A: dict[str, tuple[str, Image.Image]] = {}

    def add(name: str, folder: str, im: Image.Image) -> None:
        A[name] = (folder, im)

    for n, im in player_sprites().items():
        add(n, "sprite", im)
    for n, im in platform_tiles().items():
        add(n, "tile", im)
    add("ladder", "tile", ladder_seg())
    add("crate", "sprite", crate())
    add("spike", "tile", spike())
    add("shard", "sprite", shard())
    add("checkpoint_off", "sprite", checkpoint(False))
    add("checkpoint_on", "sprite", checkpoint(True))
    add("goal", "sprite", goal())
    add("pine", "sprite", pine())
    add("pine_far", "sprite", pine_far())
    add("cloud", "sprite", cloud())
    add("cloud_small", "sprite", cloud_small())
    add("mountain_far", "texture", mountain_far())
    add("dash_trail", "sprite", dash_trail())
    add("hud_shard", "sprite", hud_shard())
    add("logo_mark", "titleset", logo_mark())
    return A


# ---------------------------------------------------------------- export


def save_one(name: str, folder: str, im: Image.Image, want_vpe: bool = True) -> None:
    d = ROOT / folder
    d.mkdir(parents=True, exist_ok=True)
    im.save(d / f"{name}.png")
    if want_vpe:
        w, h = im.size
        pxl = im.load()
        pix = []
        for y in range(h):
            for x in range(w):
                r, g, b, a = pxl[x, y]
                pix.append(0xFFFF if a < 128 else VPE.rgb_to_565(r, g, b))
        VPE.save_vpe(d / f"{name}.vpe", w, h, pix)


def contact_sheet(items: list[tuple[str, Image.Image]]) -> None:
    SHEET.parent.mkdir(parents=True, exist_ok=True)
    S = 3
    cols = 8
    cell_w = 56 * S // 2 + 16
    cell_h = 40 * S // 2 + 22
    rows = (len(items) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * cell_w, rows * cell_h), (22, 28, 36))
    dd = ImageDraw.Draw(sheet)
    for i, (name, im) in enumerate(items):
        cx, cy = (i % cols) * cell_w, (i // cols) * cell_h
        big = im.convert("RGBA").resize((im.width * S, im.height * S), Image.NEAREST)
        bg = Image.new("RGBA", big.size, (32, 38, 46, 255))
        bp = bg.load()
        for yy in range(0, big.height, 8):
            for xx in range(0, big.width, 8):
                c = (40, 48, 56, 255) if ((xx // 8) + (yy // 8)) % 2 else (32, 38, 46, 255)
                for oy in range(8):
                    for ox in range(8):
                        if xx + ox < big.width and yy + oy < big.height:
                            bp[xx + ox, yy + oy] = c
        sheet.paste(bg, (cx + 8, cy + 18))
        sheet.paste(big, (cx + 8, cy + 18), big)
        dd.text((cx + 6, cy + 4), f"{name} {im.width}x{im.height}", fill=(220, 230, 160))
    sheet.save(SHEET)


def mock_scene(A: dict[str, tuple[str, Image.Image]]) -> None:
    W, H = 240, 320
    im = new(W, H)
    rect(im, 0, 0, W, 70, SKY1)
    rect(im, 0, 70, W, 60, SKY2)
    rect(im, 0, 130, W, 70, SKY3)
    mf = A["mountain_far"][1]
    im.alpha_composite(mf, (0, 100))
    im.alpha_composite(mf, (130, 92))
    rect(im, 0, 184, W, 72, FOREST)
    pines = A["pine_far"][1]
    for i in range(-1, 12):
        im.alpha_composite(pines, (i * 22, 166))
    rect(im, 0, 228, W, 92, INK)
    im.alpha_composite(A["cloud"][1], (16, 36))
    im.alpha_composite(A["cloud_small"][1], (150, 52))
    plat = A["plat_top"][1]
    fill = A["plat_fill"][1]
    left = A["plat_left"][1]
    right = A["plat_right"][1]

    def draw_plat(x: int, y: int, w: int, h: int) -> None:
        tiles = max(1, (w + 15) // 16)
        for i in range(tiles):
            tw = 16 if i < tiles - 1 else max(4, w - i * 16)
            src = left if i == 0 else (right if i == tiles - 1 else plat)
            piece = src.crop((0, 0, tw, 16))
            im.alpha_composite(piece, (x + i * 16, y))
        for yy in range(y + 16, y + h, 16):
            for i in range(tiles):
                tw = 16 if i < tiles - 1 else max(4, w - i * 16)
                piece = fill.crop((0, 0, tw, 16))
                im.alpha_composite(piece, (x + i * 16, min(yy, y + h - 1)))

    draw_plat(0, 250, 140, 70)
    draw_plat(160, 230, 80, 90)
    draw_plat(70, 188, 70, 22)
    lad = A["ladder"][1]
    for i in range(3):
        im.alpha_composite(lad, (188, 176 + i * 18))
    im.alpha_composite(A["crate"][1], (208, 212))
    im.alpha_composite(A["spike"][1], (98, 238))
    im.alpha_composite(A["spike"][1], (108, 238))
    im.alpha_composite(A["spike"][1], (118, 238))
    im.alpha_composite(A["shard"][1], (86, 158))
    im.alpha_composite(A["checkpoint_on"][1], (38, 214))
    im.alpha_composite(A["goal"][1], (178, 190))
    im.alpha_composite(A["pine"][1], (8, 216))
    im.alpha_composite(A["player_idle"][1], (118, 228))
    im.alpha_composite(A["player_run0"][1], (150, 228))
    im.alpha_composite(A["logo_mark"][1], (96, 16))
    MOCK.parent.mkdir(parents=True, exist_ok=True)
    im.convert("RGB").save(MOCK)


# ---------------------------------------------------------------- Lua RLE


def rgb_to_565(c) -> int:
    return VPE.rgb_to_565(c[0], c[1], c[2])


def encode_sprite_rle(im: Image.Image, palette: list[int], color_index: dict[int, int]):
    w, h = im.size
    pxl = im.load()
    grid = [[-1] * w for _ in range(h)]
    for y in range(h):
        for x in range(w):
            r, g, b, a = pxl[x, y]
            if a < 128:
                continue
            key = rgb_to_565((r, g, b))
            if key not in color_index:
                color_index[key] = len(palette) + 1
                palette.append(key)
            grid[y][x] = color_index[key]
    used = [[False] * w for _ in range(h)]
    rects = []
    for y in range(h):
        x = 0
        while x < w:
            if used[y][x] or grid[y][x] < 0:
                x += 1
                continue
            col = grid[y][x]
            x2 = x
            while x2 < w and not used[y][x2] and grid[y][x2] == col:
                x2 += 1
            rw = x2 - x
            rh = 1
            while y + rh < h:
                ok = True
                for xx in range(x, x2):
                    if used[y + rh][xx] or grid[y + rh][xx] != col:
                        ok = False
                        break
                if not ok:
                    break
                rh += 1
            for yy in range(y, y + rh):
                for xx in range(x, x2):
                    used[yy][xx] = True
            rects.append((x, y, rw, rh, col))
            x = x2
    return w, h, rects


def lua_escape_bytes(data: bytes) -> str:
    out = []
    for b in data:
        if 32 <= b < 127 and b not in (34, 39, 92):
            out.append(chr(b))
        else:
            out.append("\\%03d" % b)
    return "".join(out)


def write_lua(A: dict[str, tuple[str, Image.Image]]) -> None:
    palette: list[int] = []
    color_index: dict[int, int] = {}
    sprites = {}
    for name, (_folder, im) in sorted(A.items()):
        w, h, rects = encode_sprite_rle(im, palette, color_index)
        blob = bytearray()
        for x, y, rw, rh, idx in rects:
            blob.extend((x, y, rw, rh, idx))
        sprites[name] = (w, h, bytes(blob))

    lines = [
        "-- Compiled from Pixel_Editor tools/make_summit_echo.py (VPE565).",
        "-- Style: ai_ui_design B2 — black outline, two-tone shading, RGB565-safe.",
        "-- Transparent pixels omitted; each rect is x,y,w,h,paletteIndex (1-based).",
        "return {",
        '  format="se-rle565-v2",',
        "  palette={%s}," % ",".join(str(v) for v in palette),
        "  sprites={",
    ]
    for name in sorted(sprites):
        w, h, blob = sprites[name]
        lines.append("    %s={w=%d,h=%d,r='%s'}," % (name, w, h, lua_escape_bytes(blob)))
    lines += ["  },", "}"]
    LUA_OUT.parent.mkdir(parents=True, exist_ok=True)
    LUA_OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    total = sum(len(b) for _, _, b in sprites.values())
    print(f"  lua  -> {LUA_OUT}  ({len(sprites)} sprites, {len(palette)} colors, {total} RLE bytes)")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    ap.add_argument("--no-sheet", action="store_true")
    ap.add_argument("--no-vpe", action="store_true")
    ap.add_argument("--no-lua", action="store_true")
    args = ap.parse_args()
    only = {s.strip() for s in args.only.split(",") if s.strip()}

    A = build_all()
    n = 0
    filtered = {}
    for name, (folder, im) in sorted(A.items()):
        if only and name not in only:
            continue
        save_one(name, folder, im, want_vpe=not args.no_vpe)
        filtered[name] = (folder, im)
        n += 1
    print(f"OK {n} asset -> {ROOT}")
    if not args.no_sheet and filtered:
        contact_sheet([(k, v[1]) for k, v in sorted(filtered.items())])
        mock_scene(A if not only else filtered)
        print(f"  sheet -> {SHEET}")
        print(f"  mock  -> {MOCK}")
    if not args.no_lua:
        write_lua(A if not only else filtered)


if __name__ == "__main__":
    main()
