#!/usr/bin/env python3
"""Generate VampireVeilDemo's tiles, parallax bands, characters and HUD art.

Reference: tmp/veil_ref/ (frames pulled from the Vampire's Veil trailer). The
colours below are histograms of those frames, not guesses:

    ground body   #0d1a51  (62% of the lower band of f_011)
    sky           #6fdaf2 / #55caee, pale #cef0ec
    far ridge     #4a83c2, haze #bae8f2
    mid pines     #2b627d / #2d5276 against #0e1e60 gaps
    near pines    #272b55 / #363a66
    cobble edge   #fff248 highlight, #d1ce2b body, #a99158 shadow
    moss fringe   #d73aee light, #af00dc body
    blood/whip    #ea0017 / #d20000 / #bc0006
    minimap panel #1e0050

Layout of the output header:

  * one opaque 16x16 RGB565 tile atlas for the ground layer, so VxpTilemap2D
    keeps its copy_tile fast path (cell id 0 is the blank tile),
  * one masked 16x16 atlas for the ledges and pillars that need air around them,
  * masked sprites (VvSprite) for the hero, enemies, props, pickups and FX,
  * three tileable, opaque parallax bands for the background.

The ground lip is drawn in the tile's TOP rows because VxpBody2D supports a body
on a solid tile's top edge; a lip anywhere else makes the hero float.

Masks are packed exactly the way vxpe2d_blit reads them: one bit per source
pixel, MSB first, bit index y*width+x, no row padding.

    py -3 tools/generate_vampireveil_assets.py           # header + sheets
    py -3 tools/generate_vampireveil_assets.py --preview # sheets only

`-3` matters on this machine: the shebang below makes a bare `py` pick a
Python without Pillow installed.
"""
import math
import os
import sys

OUT_HEADER = "examples/VampireVeilDemo/src/assets_gen.h"
TILE = 16
SHEET_TILES = "tmp/veil_tiles_sheet.png"
SHEET_TILES2 = "tmp/veil_tiles2_sheet.png"
SHEET_BANDS = "tmp/veil_bands_sheet.png"
SHEET_HERO = "tmp/veil_hero_sheet.png"
SHEET_ACTORS = "tmp/veil_actors_sheet.png"
SHEET_PROPS = "tmp/veil_props_sheet.png"
SHEET_HUD = "tmp/veil_hud_sheet.png"


def c565(c):
    r, g, b = c
    return ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3)


def mix(a, b, t):
    return tuple(int(a[i] * (1 - t) + b[i] * t) for i in range(3))


def shade(c, k):
    return tuple(min(255, max(0, int(v * k))) for v in c)


# ---- palette, measured off tmp/veil_ref frames -----------------------------
SKY_TOP    = (0xCE, 0xF0, 0xEC)
SKY        = (0x6F, 0xDA, 0xF2)
SKY_LO     = (0x55, 0xCA, 0xEE)
SKY_DEEP   = (0x4A, 0x83, 0xC2)
HAZE       = (0xBA, 0xE8, 0xF2)

PINE_FAR   = (0x6B, 0x9F, 0xC8)
PINE_MID   = (0x2B, 0x62, 0x7D)
PINE_MID_L = (0x3D, 0x7B, 0x92)
PINE_MID_D = (0x1C, 0x44, 0x63)
PINE_NEAR  = (0x27, 0x2B, 0x55)
PINE_NEAR_L = (0x36, 0x3A, 0x66)
PINE_NEAR_D = (0x18, 0x1B, 0x3A)
GAP        = (0x0E, 0x1E, 0x60)

ROCK       = (0x0D, 0x1A, 0x51)
ROCK_HI    = (0x1A, 0x28, 0x66)
ROCK_LO    = (0x08, 0x11, 0x38)
COBB_H     = (0xFF, 0xF2, 0x48)
COBB       = (0xE8, 0xD2, 0x3A)
COBB_LO    = (0xA9, 0x91, 0x58)
COBB_D     = (0x6B, 0x57, 0x33)
MOSS_H     = (0xD7, 0x3A, 0xEE)
MOSS       = (0xAF, 0x00, 0xDC)
MOSS_LO    = (0x62, 0x00, 0x86)
FLOWER     = (0xFF, 0xF2, 0x48)
# the retaining wall and pillars are stone the same colour family as the rock
# body; only the picket fence keeps the bright blue-grey of the trailer
WALL_HI    = (0x33, 0x44, 0x78)
WALL       = (0x22, 0x2E, 0x5A)
WALL_LO    = (0x13, 0x1B, 0x3E)
FENCE_HI   = (0x6F, 0x9F, 0xC8)
FENCE      = (0x4A, 0x83, 0xC2)
FENCE_LO   = (0x27, 0x2B, 0x55)
BAT_D      = (0x14, 0x0E, 0x2C)
BAT_W      = (0x4A, 0x1E, 0x78)
BAT_W_HI   = (0x6A, 0x32, 0xA6)

RED_H      = (0xEA, 0x00, 0x17)
RED        = (0xD2, 0x00, 0x00)
RED_LO     = (0xBC, 0x00, 0x06)
RED_D      = (0x6E, 0x00, 0x14)
SKIN       = (0xF2, 0xD8, 0xC4)
SKIN_LO    = (0xC8, 0xA2, 0x8E)
HAIR       = (0x2A, 0x1E, 0x30)
HAIR_HI    = (0x4A, 0x38, 0x52)
CLOTH      = (0x2C, 0x24, 0x40)
CLOTH_LO   = (0x17, 0x14, 0x28)
GOLD       = (0xE0, 0xB0, 0x3A)
IVORY      = (0xF2, 0xEC, 0xD0)
LINE       = (0x05, 0x02, 0x04)
WOOD       = (0x8A, 0x5F, 0x38)
WOOD_LO    = (0x4E, 0x33, 0x1E)
IRON       = (0x3A, 0x3E, 0x52)
IRON_HI    = (0x6C, 0x72, 0x8C)
PURP       = (0xB0, 0x4A, 0xE0)
PURP_LO    = (0x6A, 0x1E, 0x96)
PANEL      = (0x1E, 0x00, 0x50)
OWL_HI     = (0xE8, 0xE2, 0xD8)
OWL        = (0x9A, 0x7A, 0x58)
OWL_LO     = (0x5E, 0x44, 0x2E)
IMP        = (0x3C, 0x2A, 0x44)
IMP_LO     = (0x22, 0x18, 0x2A)
EYE        = (0xFF, 0xE2, 0x4A)


class Raster:
    """RGB canvas with None for transparent; deterministic hash noise.

    wrap=True folds out-of-bounds writes back into the image, which is what the
    parallax bands need so they tile in x with no seam. Tiles and sprites use
    the default clipping instead, so a decoration drawn above row 0 disappears
    rather than reappearing at the bottom of the tile.
    """

    def __init__(self, w, h, fill=None, wrap=False):
        self.w, self.h = w, h
        self.wrap = wrap
        self.d = [[fill for _ in range(w)] for _ in range(h)]

    def set(self, x, y, c):
        if c is None:
            return
        if self.wrap:
            x %= self.w          # bands wrap so they tile without a seam
            y %= self.h
        elif not (0 <= x < self.w and 0 <= y < self.h):
            return
        self.d[y][x] = c

    def erase(self, x, y):
        if 0 <= x < self.w and 0 <= y < self.h:
            self.d[y][x] = None

    def get(self, x, y):
        if 0 <= x < self.w and 0 <= y < self.h:
            return self.d[y][x]
        return None

    def rect(self, x0, y0, w, h, c, wrap=False):
        for y in range(y0, y0 + h):
            for x in range(x0, x0 + w):
                if wrap or (0 <= x < self.w and 0 <= y < self.h):
                    self.set(x, y, c)

    def line(self, x0, y0, x1, y1, c, width=1):
        dx, dy = abs(x1 - x0), -abs(y1 - y0)
        sx, sy = (1 if x0 < x1 else -1), (1 if y0 < y1 else -1)
        err = dx + dy
        while True:
            for o in range(width):
                self.set(x0 + (0 if width == 1 else o), y0, c)
            if x0 == x1 and y0 == y1:
                break
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                x0 += sx
            if e2 <= dx:
                err += dx
                y0 += sy

    def circle(self, cx, cy, r, c):
        """True round fill - the |dx|+|dy| form reads as a diamond at these sizes."""
        for y in range(cy - r, cy + r + 1):
            for x in range(cx - r, cx + r + 1):
                dx, dy = x - cx, y - cy
                if dx * dx + dy * dy <= r * r + r * 0.7:
                    self.set(x, y, c)

    def ellipse(self, cx, cy, rx, ry, c):
        for y in range(cy - ry, cy + ry + 1):
            for x in range(cx - rx, cx + rx + 1):
                dx, dy = (x - cx) / float(rx), (y - cy) / float(ry)
                if dx * dx + dy * dy <= 1.05:
                    self.set(x, y, c)

    def sweep(self, cx, cy, r_mid, half_fn, a0, a1, c):
        """Filled crescent: at each degree the band spans r_mid +/- half_fn(t).

        half_fn takes t in 0..1 along the arc and returns the half thickness in
        pixels, so a whip can be thin at both tips and heavy through the middle.
        """
        span = float(a1 - a0)
        for deg in range(a0, a1 + 1):
            t = (deg - a0) / span
            th = math.radians(deg)
            half = half_fn(t)
            lo = int(round(r_mid - half))
            hi = int(round(r_mid + half))
            for rr in range(lo, hi + 1):
                x = int(round(cx + rr * math.cos(th)))
                y = int(round(cy + rr * 0.92 * math.sin(th)))
                self.set(x, y, c)

    def hash(self, x, y, salt=0):
        h = (x * 73856093) ^ (y * 19349663) ^ (salt * 83492791)
        h &= 0xFFFFFFFF
        h = (h ^ (h >> 13)) * 1274126177 & 0xFFFFFFFF
        return ((h ^ (h >> 16)) & 0x7FFFFFFF) % 1000 / 1000.0

    def speckle(self, n, c, salt=0, box=None):
        x0, y0, x1, y1 = box or (0, 0, self.w, self.h)
        for y in range(y0, y1):
            for x in range(x0, x1):
                if self.hash(x, y, salt) < n / 100.0:
                    self.set(x, y, c)

    def outline(self, color=LINE):
        add = []
        for y in range(self.h):
            for x in range(self.w):
                if self.get(x, y) is None:
                    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        if self.get(x + dx, y + dy) is not None:
                            add.append((x, y))
                            break
        for x, y in add:
            self.set(x, y, color)

    def compose(self, dst, ox=0, oy=0):
        for y in range(self.h):
            for x in range(self.w):
                c = self.d[y][x]
                if c is not None:
                    if 0 <= ox + x < dst.w and 0 <= oy + y < dst.h:
                        dst.set(ox + x, oy + y, c)

    def bake(self):
        """RGB565 pixels plus the packed mask in the order vxpe2d_blit reads it."""
        px = [0 if self.d[y][x] is None else c565(self.d[y][x])
              for y in range(self.h) for x in range(self.w)]
        bits = [1 if self.d[y][x] is not None else 0
                for y in range(self.h) for x in range(self.w)]
        mk = []
        for i in range(0, len(bits), 8):
            byte = 0
            for j in range(8):
                if i + j < len(bits) and bits[i + j]:
                    byte |= 0x80 >> j
            mk.append(byte)
        return px, mk


# ---- 16x16 tiles -----------------------------------------------------------
def tile_rock(variant=0):
    """The indigo rock body: rounded cobbles with a darker mortar."""
    r = Raster(TILE, TILE, ROCK)
    salt = 40 + variant * 7
    for cy in (3, 11):
        for cx in (3 + (0 if variant == 0 else 4), 11 - (0 if variant == 0 else 5)):
            r.ellipse(cx, cy, 3, 2, mix(ROCK, ROCK_HI, 0.55))
            r.ellipse(cx, cy - 1, 2, 1, ROCK_HI)
    r.ellipse(7, 7, 3, 2, mix(ROCK, ROCK_LO, 0.6))
    r.speckle(6, ROCK_HI, salt)
    r.speckle(5, ROCK_LO, salt + 3)
    return r


def tile_rock_deep():
    """Deeper fill under the surface: almost no highlight, keeps the pit dark."""
    r = Raster(TILE, TILE, mix(ROCK, ROCK_LO, 0.6))
    r.speckle(7, ROCK_LO, 11)
    r.speckle(4, mix(ROCK, GAP, 0.5), 17)
    return r


def cobble_lip(r, y0=0, x0=0, x1=TILE, moss=None):
    """The golden cobble edge, drawn along the tile's TOP rows.

    VxpBody2D supports a body on a solid tile's top edge (tile_row * tile_h),
    so the walkable surface has to sit at row 0. A lip drawn lower makes every
    hero float a third of a tile above the ground it is standing on.
    """
    for x in range(x0, x1):
        h = 3 + (x * 37) % 2                     # 3..4 px of stone
        for dy in range(h):
            c = COBB_H if dy == 0 else (COBB if dy < h - 1 else COBB_LO)
            r.set(x, y0 + dy, c)
    for cx in range(x0 + 2, x1, 4):              # joint lines between cobbles
        r.set(cx, y0 + 1, COBB_LO)
        r.set(cx, y0 + 2, COBB_D)
    r.rect(x0, y0 + 4, x1 - x0, 1, COBB_D)       # the shadow the lip casts
    if moss:
        # moss overgrows the top face in patches, and hangs a pixel or two down
        # the front. Quantised on x//3 so it forms clumps instead of a zipper.
        for x in range(x0, x1):
            if r.hash(x // 3, 0, 71) < 0.55:
                r.set(x, y0, mix(moss, COBB_H, 0.25))
                r.set(x, y0 + 1, moss)
                if r.hash(x, 1, 13) < 0.4:
                    r.set(x, y0 + 2, MOSS_LO)
            if r.hash(x // 2, 2, 29) < 0.25:
                r.set(x, y0, MOSS_H)


def rock_body(r, y0=5, y1=TILE, variant=0):
    """The indigo mass under the lip, so a surface tile matches the body tiles."""
    r.rect(0, y0, TILE, y1 - y0, ROCK)
    for cy in (y0 + 4,):
        for cx in ((3, 11) if variant == 0 else (6, 14)):
            r.ellipse(cx, cy, 3, 2, mix(ROCK, ROCK_HI, 0.5))
    r.speckle(5, ROCK_LO, 3 + variant * 5, box=(0, y0, TILE, y1))


def tile_top(kind):
    """Surface tile: lip at the top, rock body below. kind = cobble/moss/flowers."""
    r = Raster(TILE, TILE, ROCK)
    cobble_lip(r, moss=MOSS if kind else None)
    rock_body(r, variant=1 if kind == "flowers" else 0)
    if kind == "moss":
        for x in range(TILE):
            if (x * 29) % 5 < 2:
                r.set(x, 5, MOSS_LO)
    elif kind == "flowers":
        # lichen crusts on the lip's face: row 0 is the walkable plane, so
        # anything drawn above it would leave the tile
        for cx in (2, 7, 12):
            r.set(cx, 2, FLOWER)
            r.set(cx - 1, 2, mix(FLOWER, MOSS_H, 0.5))
            r.set(cx + 1, 2, mix(FLOWER, MOSS_H, 0.5))
            r.set(cx, 3, MOSS_H)
    return r


def tile_wall_cobble():
    """The retaining wall behind the fence line: dark stone blocks."""
    r = Raster(TILE, TILE, WALL_LO)
    for row, yo in enumerate((0, 5, 10)):
        off = 0 if row % 2 == 0 else 4
        for x in range(-4, TILE, 8):
            r.rect(x + off, yo, 7, 4, WALL)
            r.rect(x + off, yo, 7, 1, WALL_HI)
            r.rect(x + off, yo + 3, 7, 1, mix(WALL, WALL_LO, 0.7))
    r.speckle(4, WALL_HI, 31)
    return r


# ---- masked tiles: floating ledges and pillars ------------------------------
# A second, non-opaque atlas so a ledge can have air around it. The core takes
# the copy_tile fast path only for an opaque atlas, so keeping the ground mass
# in the first atlas and these few cells in the second costs blits only where
# the level actually needs transparency.
def tile_blank_masked():
    return Raster(TILE, TILE)


def tile_plat(kind):
    """One-way ledge: 9 px of stone with the same lip as the ground.

    kind: 'mid' spans the cell, 'left'/'right' round off that end.
    """
    r = Raster(TILE, TILE)
    slab_bottom = 9
    if kind == "mid":
        x0, x1 = 0, TILE
    elif kind == "left":
        x0, x1 = 3, TILE
    else:
        x0, x1 = 0, TILE - 3
    cobble_lip(r, x0=x0, x1=x1, moss=MOSS if kind == "left" else None)
    r.rect(x0, 5, x1 - x0, slab_bottom - 5, ROCK)
    for x in range(x0, x1):
        r.set(x, slab_bottom - 1, mix(ROCK, ROCK_LO, 0.7))
    for cx in range(x0 + 3, x1, 5):
        r.set(cx, 6, ROCK_HI)
    if kind != "mid":
        # taper the underside up to the rounded end
        for i in range(3):
            x = x0 + i if kind == "left" else x1 - 1 - i
            for y in range(slab_bottom - i - 1, slab_bottom):
                r.erase(x, y)
        edge = x0 if kind == "left" else x1 - 1
        for y in range(1, 4):
            r.set(edge, y, COBB_LO)
    return r


def tile_post():
    """A broken stone pillar, masked so it can stand in front of the ground."""
    r = Raster(TILE, TILE)
    r.rect(4, 0, 8, 16, WALL)
    r.rect(4, 0, 2, 16, WALL_HI)
    r.rect(10, 0, 2, 16, WALL_LO)
    r.rect(3, 12, 10, 4, mix(WALL, WALL_LO, 0.3))
    r.rect(3, 12, 10, 1, WALL_HI)
    r.rect(3, 0, 10, 2, mix(WALL, WALL_HI, 0.5))
    r.speckle(6, WALL_LO, 41)
    return r


TILES = [
    ("blank", lambda: Raster(TILE, TILE, (0, 0, 0))),
    ("rock", lambda: tile_rock(0)),
    ("rock_alt", lambda: tile_rock(1)),
    ("rock_deep", tile_rock_deep),
    ("top_cobble", lambda: tile_top("")),
    ("top_moss", lambda: tile_top("moss")),
    ("top_flowers", lambda: tile_top("flowers")),
    ("wall_cobble", tile_wall_cobble),
]

TILES_MASKED = [
    ("blank", tile_blank_masked),
    ("plat", lambda: tile_plat("mid")),
    ("plat_l", lambda: tile_plat("left")),
    ("plat_r", lambda: tile_plat("right")),
    ("post", tile_post),
]


# ---- parallax bands (tileable in x, opaque) --------------------------------
def band_far(w=96, h=48):
    """Sky and the far ridge the trailer shows behind the pines.

    No moon here: the band tiles horizontally, so a disc baked into it
    multiplies across the sky. The game blits VV_SP_MOON once at a fixed offset.
    """
    r = Raster(w, h, SKY, wrap=True)
    for y in range(h):
        t = y / float(h - 1)
        r.rect(0, y, w, 1, mix(SKY_TOP, SKY_LO, min(1.0, t * 1.35)))
    # faint stars in the upper sky only
    r.speckle(1, mix(SKY_TOP, IVORY, 0.7), 9, box=(0, 0, w, 12))
    # far ridge: two overlapping ranges in haze
    for base, col, amp, ph in ((h - 2, mix(SKY_DEEP, HAZE, 0.45), 9, 0),
                               (h, SKY_DEEP, 6, 23)):
        for x in range(w):
            k = amp - int(amp * abs(((x * 7 + ph * 31) % 64) - 32) / 32.0)
            for y in range(base - k, base + 1):
                r.set(x, y, col)
    # pine combs on the ridge line, very pale
    for x in range(0, w, 4):
        top = h - 6 - ((x * 17) % 5)
        for dy in range(4):
            r.rect(x, top + dy, 4 - dy, 1, mix(SKY_DEEP, PINE_FAR, 0.5))
    r.speckle(2, HAZE, 5, box=(0, h - 10, w, h))
    return r


def build_moon():
    """20x20 moon, drawn once by the game behind the pines.

    A plain soft-edged disc: the first pass added two halo rings and an outline
    and read as a target. The two outer rings are just darker ivory, which gives
    the glow without drawing a circle the sky cannot hide.
    """
    w, h = 20, 20
    r = Raster(w, h)
    cx = cy = 10
    r.circle(cx, cy, 8, mix(SKY_TOP, IVORY, 0.45))
    r.circle(cx, cy, 7, mix(SKY_TOP, IVORY, 0.7))
    r.circle(cx, cy, 6, IVORY)
    # craters keep it from reading as a light bulb
    r.circle(cx - 2, cy - 1, 2, mix(IVORY, SKY_TOP, 0.45))
    r.circle(cx + 3, cy + 3, 1, mix(IVORY, SKY_TOP, 0.5))
    r.circle(cx + 1, cy - 4, 1, mix(IVORY, SKY_TOP, 0.4))
    return r


def band_mid(w=96, h=56):
    """The desaturated blue pine comb that fills most of the screen."""
    r = Raster(w, h, mix(GAP, SKY_DEEP, 0.35), wrap=True)
    for y in range(h):
        r.rect(0, y, w, 1, mix(mix(GAP, SKY_DEEP, 0.35), PINE_MID_D, y / float(h)))
    for i in range(9):
        cx = (i * 11 + 4) % w
        hh = 30 + (i * 7) % 13
        base = h - 2 - (i % 3)
        for k in range(hh):
            y = base - k
            half = max(1, int((hh - k) * 0.42))
            r.rect(cx - half, y, 2 * half + 1, 1, PINE_MID)
            if k % 4 == 0:
                r.rect(cx - half, y, 2 * half + 1, 1, PINE_MID_L)
        r.rect(cx - 1, base + 1, 3, 4, PINE_MID_D)
    r.speckle(3, PINE_MID_L, 13, box=(0, 0, w, h - 18))
    return r


def band_near(w=96, h=64):
    """Foreground pines: dark, big, with visible trunks."""
    r = Raster(w, h, mix(PINE_NEAR, GAP, 0.4), wrap=True)
    for y in range(h):
        r.rect(0, y, w, 1, mix(mix(PINE_NEAR, GAP, 0.4), PINE_NEAR_D, y / float(h)))
    for i in range(5):
        cx = (i * 19 + 8) % w
        hh = 44 + (i * 11) % 12
        base = h - 1
        r.rect(cx - 1, base - hh // 3, 3, hh // 3 + 4, mix(WOOD_LO, PINE_NEAR_D, 0.5))
        for k in range(hh):
            y = base - k
            half = max(1, int((hh - k) * 0.34))
            col = PINE_NEAR if k % 3 else PINE_NEAR_L
            r.rect(cx - half, y, 2 * half + 1, 1, col)
            if half > 2:
                r.set(cx - half, y, PINE_NEAR_D)
                r.set(cx + half, y, PINE_NEAR_D)
    r.speckle(2, PINE_NEAR_L, 29, box=(0, 0, w, h - 24))
    return r


# ---- hero ------------------------------------------------------------------
HERO_W, HERO_H = 16, 26


def hero_parts(r, ox, oy, pose, phase):
    """Draw the vampire hunter facing right; ox/oy put her feet at (ox, oy).

    At 16x26 the silhouette has to carry the read, so the shape is: dark hair
    block, small pale face, red cloak over a dark tunic, then boots. Anything
    lighter than the cloak (a white collar, a big hand) turns into a blob at
    this size and the character stops reading as a person.
    """
    if pose == "idle":
        bob = (0, 1)[phase % 2]
    elif pose == "run":
        bob = (0, -1, 0, -1)[phase % 4]
    else:
        bob = {"jump": -1, "fall": 0, "attack": 0, "hurt": 1, "cast": -1}[pose]
    hy = oy - 22 + bob            # head top row
    ty = oy - 16 + bob            # torso top row
    ly = oy - 6                 # legs top row
    lean = -1 if pose == "run" else 0

    # cloak behind the body: a wedge that flares out when moving
    flare = 4 if pose in ("run", "fall", "jump") else 2
    for dy in range(11):
        wdt = flare + (1 if dy > 6 else 0)
        top = hy + 4 + dy
        r.rect(ox - 2 - wdt, top, wdt, 1, RED if dy < 5 else RED_LO)
        r.set(ox - 3 - wdt, top, RED_D)          # the trailing edge is darkest
    if pose in ("run", "jump", "fall"):
        r.rect(ox - 6, hy + 8, 3, 3, RED)
        r.rect(ox - 7, hy + 9, 2, 2, RED_D)

    # legs and boots: the 4-frame run cycle has to differ by more than a pixel
    # or the animation reads as a slide
    if pose == "run":
        ph = phase % 4
        reach = (2, 1, -1, -2)[ph]
        lift = (0, 0, 1, 0)[ph]
        r.rect(ox - 2, ly, 2, 6, CLOTH_LO)                    # far leg
        r.rect(ox - 3, oy - 1, 3, 1, mix(WOOD, LINE, 0.5))    # far boot
        r.rect(ox - 2 + reach, ly, 2, 6 - lift, CLOTH)        # near leg
        r.rect(ox - 3 + reach, oy - 1 - lift, 3, 1, WOOD_LO)  # near boot
    elif pose in ("jump", "fall"):
        spread = 1 if pose == "fall" else 0
        r.rect(ox - 2 - spread, ly, 2, 4, CLOTH)
        r.rect(ox + 1 + spread, ly, 2, 4, CLOTH_LO)
        r.rect(ox - 3 - spread, oy - 1, 3, 1, WOOD_LO)
        r.rect(ox + 1 + spread, oy - 1, 3, 1, WOOD_LO)
    else:
        r.rect(ox - 2, ly, 2, 6, CLOTH)
        r.rect(ox + 1, ly, 2, 6, CLOTH_LO)
        r.rect(ox - 3, oy - 1, 3, 1, WOOD_LO)
        r.rect(ox + 1, oy - 1, 3, 1, WOOD_LO)

    # torso: dark tunic, cloak lapels over the shoulders, one gold clasp
    r.rect(ox - 2, ty + lean, 5, 11, CLOTH)
    r.rect(ox - 2, ty + lean, 1, 11, RED)          # cloak edge on the chest
    r.rect(ox + 2, ty + lean, 1, 11, RED_LO)
    r.rect(ox - 1, ty + lean, 3, 2, RED_H)         # the collar, kept narrow
    r.set(ox, ty + 3 + lean, GOLD)
    r.rect(ox + 2, ty + 5 + lean, 1, 6, CLOTH_LO)

    # arm: forward on the attack poses, swinging opposite the legs when running
    if pose in ("attack", "cast"):
        r.rect(ox + 2, ty + 4, 4, 2, CLOTH)        # sleeve, not bare skin
        r.rect(ox + 6, ty + 4, 2, 2, SKIN)
        r.rect(ox + 2, ty + 3, 2, 1, RED)
    elif pose == "hurt":
        r.rect(ox - 4, ty + 1, 3, 2, CLOTH)
        r.rect(ox + 2, ty + 2, 2, 2, SKIN_LO)
    elif pose == "run":
        arm = (-1, 0, 1, 0)[phase % 4]
        r.rect(ox + 2 + arm, ty + 5, 2, 4, CLOTH_LO)
        r.set(ox + 3 + arm, ty + 9, SKIN_LO)
    else:
        r.rect(ox + 2, ty + 5, 2, 4, CLOTH_LO)
        r.set(ox + 3, ty + 9, SKIN_LO)

    # head: hair block first, then the face punched into its lower half
    r.rect(ox - 2, hy, 5, 6, HAIR)
    r.rect(ox - 1, hy + 2, 4, 4, SKIN)
    r.rect(ox - 2, hy, 5, 2, HAIR)
    r.rect(ox - 3, hy + 1, 1, 4, HAIR)             # hair behind the cheek
    r.rect(ox + 2, hy, 1, 2, HAIR)
    r.set(ox + 1, hy + 1, HAIR_HI)
    r.rect(ox + 2, hy + 4, 2, 2, HAIR)             # ponytail off the neck
    r.set(ox - 1, hy + 3, LINE)                    # eye
    r.set(ox + 1, hy + 3, LINE)
    r.set(ox + 1, hy + 5, RED_LO)                  # mouth
    r.rect(ox - 1, hy + 6, 3, 1, CLOTH_LO)         # neck shadow
    if pose == "hurt":
        r.set(ox - 1, hy + 3, RED_H)
        r.set(ox + 1, hy + 3, RED_H)


def build_hero(pose, phase):
    r = Raster(HERO_W, HERO_H)
    hero_parts(r, 7, HERO_H - 1, pose, phase)
    r.outline()
    return r


def build_whip(phase):
    """The red crescent the reference swings: three sweep sizes.

    Filled rather than outlined - a 1 px arc at r=7 leaves gaps once it is
    quantised to whole pixels, which reads as confetti instead of a swing.
    """
    w, h = 32, 26
    r = Raster(w, h)
    cx, cy = 4, 13
    rad, sweep = [(9, 118), (13, 128), (17, 136)][phase]
    a0, a1 = -sweep // 2, sweep // 2

    def heavy(t):                       # thin at both tips, thick mid-swing
        return 0.6 + 2.4 * math.sin(math.pi * min(1.0, max(0.0, t)))

    r.sweep(cx, cy, rad + 2, lambda t: heavy(t) + 0.9, a0, a1, RED_D)
    r.sweep(cx, cy, rad, heavy, a0, a1, RED)
    r.sweep(cx, cy, rad - 1, lambda t: max(0.0, heavy(t) - 1.4), a0 + 4, a1 - 4, RED_H)
    # the grip stays put while the head of the whip travels
    r.rect(cx - 1, cy - 1, 5, 2, IRON)
    r.rect(cx - 1, cy - 1, 5, 1, IRON_HI)
    tip = (cx + int(rad * math.cos(math.radians(a1))),
           cy + int((rad + 2) * 0.92 * math.sin(math.radians(a1))))
    r.circle(tip[0], tip[1], 2, RED_H)
    r.outline()
    return r


# ---- enemies and NPCs ------------------------------------------------------
def build_bat(frame):
    """The winged enemy: a dark body with a violet membrane and red eyes.

    Red wings made the first pass read as a flame. The reference bat is almost
    black with a violet membrane, so only the eyes are bright. Each wing is a
    leading-edge finger with a scalloped trailing edge, which keeps a 6-pixel
    wing from turning into a solid triangle.
    """
    w, h = 16, 12
    r = Raster(w, h)
    up = frame == 0
    # body: head, chest, tapered tail
    r.circle(8, 6, 2, BAT_D)
    r.rect(7, 6, 3, 3, BAT_D)
    r.rect(8, 9, 1, 2, BAT_D)
    r.rect(7, 2, 1, 2, BAT_D)                     # ears
    r.rect(9, 2, 1, 2, BAT_D)
    r.set(7, 5, RED_H)                            # eyes
    r.set(9, 5, RED_H)
    for i in range(1, 7):                          # i = reach from the body
        if up:
            y = 6 - (i * 5) // 6
            r.rect(8 - i, y, i, 1, BAT_W)
            r.rect(9, y, i, 1, BAT_W)
            r.set(8 - i, y, BAT_W_HI)
            r.set(9 + i - 1, y, BAT_W_HI)
            if i % 2 == 0:                         # trailing-edge scallop
                r.rect(8 - i + 1, y + 1, 2, 1, BAT_W)
                r.rect(9 + i - 3, y + 1, 2, 1, BAT_W)
        else:
            y = 6 + (i * 4) // 6
            r.rect(8 - i, y - 2, i, 2, BAT_W)
            r.rect(9, y - 2, i, 2, BAT_W)
            r.set(8 - i, y - 1, BAT_W_HI)
            r.set(9 + i - 1, y - 1, BAT_W_HI)
            if i % 2 == 0:
                r.rect(8 - i + 1, y, 2, 1, BAT_W)
                r.rect(9 + i - 3, y, 2, 1, BAT_W)
    r.outline()
    return r


def build_imp(frame):
    """The ground crawler: small, horned, carrying a club."""
    w, h = 16, 22
    r = Raster(w, h)
    bob = frame
    top = 3 + bob
    body = mix(IMP, RED_LO, 0.18)
    # horns then the head, so the pale tips stand above the skull
    r.rect(4, top - 1, 1, 2, IVORY)
    r.rect(11, top - 1, 1, 2, IVORY)
    r.rect(5, top + 1, 6, 4, body)
    r.rect(5, top + 1, 6, 1, mix(body, IVORY, 0.2))
    r.set(6, top + 3, EYE)
    r.set(9, top + 3, EYE)
    r.rect(6, top + 4, 4, 1, LINE)                # a mouthful of teeth
    r.set(7, top + 4, IVORY)
    r.set(9, top + 4, IVORY)
    # torso, wings-as-arms, club arm
    r.rect(5, top + 5, 6, 6, body)
    r.rect(5, top + 5, 6, 2, mix(body, IVORY, 0.12))
    r.rect(4, top + 6, 1, 4, IMP_LO)
    r.rect(11, top + 6, 3, 2, IMP)
    r.rect(13, top + 3, 2, 6, WOOD)
    r.rect(13, top + 3, 2, 2, WOOD_LO)
    r.rect(12, top + 1, 4, 3, WOOD_LO)
    r.rect(14, top + 1, 1, 3, WOOD)
    step = 1 if frame else 0
    r.rect(5 - step, h - 4, 2, 4, IMP_LO)
    r.rect(9 + step, h - 4, 2, 4, IMP)
    r.rect(4 - step, h - 1, 3, 1, LINE)
    r.rect(9 + step, h - 1, 3, 1, LINE)
    r.outline()
    return r


def build_owl(frame):
    """The swooping owl: round head, ear tufts, wings high or low."""
    w, h = 24, 22
    r = Raster(w, h)
    hx, hy = 12, 7
    # body under the head so the bird is one mass, not a cross
    r.ellipse(12, 13, 4, 5, OWL)
    r.ellipse(12, 14, 3, 3, OWL_HI)
    r.ellipse(hx, hy, 5, 4, OWL)
    r.rect(hx - 5, hy - 3, 2, 3, OWL_LO)          # ear tufts
    r.rect(hx + 4, hy - 3, 2, 3, OWL_LO)
    r.circle(hx - 2, hy, 2, OWL_HI)
    r.circle(hx + 2, hy, 2, OWL_HI)
    r.set(hx - 2, hy, EYE)
    r.set(hx + 2, hy, EYE)
    r.set(hx - 2, hy + 1, LINE)
    r.set(hx + 2, hy + 1, LINE)
    r.rect(hx, hy + 2, 1, 2, GOLD)                # beak
    if frame:
        # wings up: raised above the head, tips out
        for i in range(8):
            y = hy - 4 - (i * 2) // 8
            r.rect(2 + i, y, 3, 3, OWL if i % 2 else OWL_LO)
            r.rect(19 - i, y, 3, 3, OWL if i % 2 else OWL_LO)
        r.rect(1, hy - 6, 4, 4, OWL_LO)
        r.rect(19, hy - 6, 4, 4, OWL_LO)
    else:
        # wings down and back, tail fanned
        for i in range(7):
            y = hy + 1 + i
            r.rect(3 + i // 2, y, 5 - i // 2, 2, OWL_LO)
            r.rect(16 - i // 2, y, 5 - i // 2, 2, OWL_LO)
        r.rect(10, h - 4, 4, 4, OWL_LO)
        r.rect(10, h - 4, 4, 1, OWL)
    r.rect(9, h - 2, 2, 2, GOLD)
    r.rect(13, h - 2, 2, 2, GOLD)
    r.outline()
    return r


def build_villager():
    """The crouching hooded NPC by the fence: shop and save marker."""
    w, h = 16, 22
    r = Raster(w, h)
    robe = mix(CLOTH, PURP_LO, 0.35)
    # the robe is a trapezoid: narrow at the shoulders, wide at the hem
    for dy in range(12):
        half = 3 + dy // 4
        r.rect(8 - half, 9 + dy, 2 * half, 1, robe)
    r.rect(4, 9, 8, 2, mix(robe, IVORY, 0.12))
    r.rect(3, 19, 10, 3, mix(robe, LINE, 0.45))   # hem shadow
    # hood: a dome with the face sunk into shadow
    r.rect(3, 2, 10, 7, mix(robe, LINE, 0.25))
    r.rect(4, 1, 8, 2, robe)
    r.rect(5, 0, 6, 1, mix(robe, IVORY, 0.15))
    r.rect(5, 4, 6, 4, LINE)
    r.set(6, 5, EYE)
    r.set(9, 5, EYE)
    r.rect(2, 3, 1, 5, robe)
    r.rect(13, 3, 1, 5, robe)
    # the lantern the trailer has them holding
    r.rect(13, 9, 3, 4, IRON)
    r.rect(14, 10, 1, 2, FLOWER)
    r.rect(14, 8, 1, 1, IRON_HI)
    r.outline()
    return r


# ---- props -----------------------------------------------------------------
def build_fence():
    """Picket fence: three pointed slats on two rails, air between them.

    The first pass filled the whole cell with WALL, so a fence tile looked like
    a blue brick. Keeping the gaps transparent is what makes it read as a fence.
    """
    w, h = 16, 20
    r = Raster(w, h)
    for x in (1, 6, 11):
        r.rect(x, 3, 3, 16, FENCE)
        r.rect(x, 3, 1, 16, FENCE_HI)
        r.rect(x + 2, 3, 1, 16, FENCE_LO)
        r.rect(x, 2, 3, 1, FENCE_HI)              # the point
        r.set(x + 1, 0, FENCE_HI)
        r.rect(x, 1, 3, 1, FENCE)
        r.set(x, 1, FENCE_LO)
        r.set(x + 2, 1, FENCE_LO)
    r.rect(0, 6, w, 2, FENCE_LO)
    r.rect(0, 6, w, 1, mix(FENCE, FENCE_HI, 0.5))
    r.rect(0, 14, w, 2, FENCE_LO)
    r.speckle(5, FENCE_HI, 3, box=(0, 3, w, h))
    return r


def build_lamp():
    w, h = 10, 34
    r = Raster(w, h)
    r.rect(4, 8, 2, 26, IRON)
    r.rect(3, 8, 1, 26, IRON_HI)
    r.rect(2, 32, 6, 2, IRON)
    r.rect(3, 1, 4, 1, IRON_HI)
    r.rect(2, 2, 6, 6, IRON)
    r.rect(3, 3, 4, 4, RED_H)
    r.rect(4, 4, 2, 2, mix(RED_H, FLOWER, 0.5))
    r.rect(2, 0, 6, 1, IRON)
    r.rect(1, 7, 8, 1, IRON_HI)
    r.outline()
    return r


def build_grave():
    """Rounded tombstone with an engraved cross and a mound at its foot."""
    w, h = 14, 16
    stone = mix(WALL, IVORY, 0.30)
    r = Raster(w, h)
    r.rect(4, 1, 6, 2, stone)
    r.rect(3, 2, 8, 11, stone)
    r.set(3, 2, mix(stone, LINE, 0.3))
    r.set(10, 2, mix(stone, LINE, 0.3))
    r.rect(4, 1, 4, 1, mix(stone, IVORY, 0.6))    # the lit shoulder
    r.rect(6, 4, 2, 6, WALL_LO)                   # cross: upright
    r.rect(4, 6, 6, 2, WALL_LO)                   # cross: arm
    r.rect(1, 13, 12, 3, mix(ROCK, ROCK_LO, 0.4))  # the mound
    r.rect(1, 13, 12, 1, mix(ROCK, ROCK_HI, 0.5))
    r.speckle(7, mix(stone, WALL, 0.5), 7, box=(3, 1, w, 13))
    r.outline()
    return r


def build_statue():
    """The hooded monolith the trailer plants at the end of a terrace."""
    w, h = 20, 40
    r = Raster(w, h)
    # plinth
    r.rect(2, 34, 16, 6, mix(WALL, WALL_LO, 0.4))
    r.rect(1, 33, 18, 1, WALL_HI)
    r.rect(2, 34, 16, 1, mix(WALL, WALL_HI, 0.5))
    r.rect(4, 37, 12, 1, WALL_LO)
    # robed figure: shoulders, then a robe that widens to the plinth
    r.rect(6, 12, 8, 22, WALL)
    r.rect(4, 16, 12, 18, WALL)
    r.rect(3, 20, 14, 14, mix(WALL, WALL_LO, 0.25))
    r.rect(6, 12, 2, 22, WALL_HI)                 # the lit left edge
    r.rect(13, 14, 2, 20, WALL_LO)                # the shaded right edge
    for dy in range(0, 18, 3):                    # carved folds
        r.rect(5, 22 + dy, 11, 1, mix(WALL, WALL_LO, 0.6))
    # hood with the face lost in shadow
    r.rect(6, 4, 8, 8, WALL)
    r.rect(7, 3, 6, 1, WALL_HI)
    r.rect(5, 6, 10, 5, WALL)
    r.rect(7, 6, 6, 4, mix(LINE, WALL_LO, 0.35))
    r.set(8, 8, PURP)
    r.set(11, 8, PURP)
    r.rect(6, 11, 8, 2, WALL_LO)
    r.speckle(5, WALL_LO, 19, box=(1, 3, w, 34))
    r.outline()
    return r


# ---- pickups, FX and HUD art ----------------------------------------------
def build_heart(frame=0):
    """The life counter pip. frame 0 is full, frame 1 the spent outline."""
    w, h = 8, 8
    r = Raster(w, h)
    if frame:
        # spent heart: the same silhouette in the panel's dark violet so the
        # row keeps its shape as lives drain
        shell = mix(PURP_LO, PANEL, 0.45)
        r.rect(1, 2, 3, 1, shell)
        r.rect(4, 2, 3, 1, shell)
        r.rect(1, 1, 2, 1, shell)
        r.rect(5, 1, 2, 1, shell)
        r.rect(0, 2, 1, 2, shell)
        r.rect(7, 2, 1, 2, shell)
        r.rect(1, 4, 1, 1, shell)
        r.rect(6, 4, 1, 1, shell)
        r.rect(2, 5, 1, 1, shell)
        r.rect(5, 5, 1, 1, shell)
        r.rect(3, 6, 2, 1, shell)
        r.rect(4, 7, 1, 1, shell)
        r.outline(mix(LINE, PANEL, 0.5))
        return r
    r.rect(1, 2, 3, 1, RED_H)
    r.rect(4, 2, 3, 1, RED_H)
    r.rect(1, 1, 2, 1, RED_H)
    r.rect(5, 1, 2, 1, RED_H)
    r.rect(0, 2, 8, 2, RED)
    r.rect(1, 4, 6, 1, RED)
    r.rect(2, 5, 4, 1, RED_LO)
    r.rect(3, 6, 2, 1, RED_LO)
    r.rect(4, 7, 1, 1, RED_D)
    r.rect(1, 1, 2, 2, mix(RED_H, IVORY, 0.55))
    r.outline()
    return r


def build_coin():
    """Gold disc with a struck rim, so it does not read as a spark."""
    w, h = 8, 8
    r = Raster(w, h)
    r.circle(4, 4, 3, shade(GOLD, 0.55))
    r.circle(4, 4, 2, GOLD)
    r.rect(3, 2, 2, 1, mix(GOLD, IVORY, 0.7))
    r.set(2, 3, mix(GOLD, IVORY, 0.4))
    r.set(5, 5, shade(GOLD, 0.7))
    r.set(4, 4, mix(GOLD, IVORY, 0.25))
    r.outline()
    return r


def build_orb():
    w, h = 8, 8
    r = Raster(w, h)
    r.circle(4, 4, 3, PURP_LO)
    r.circle(4, 4, 2, PURP)
    r.set(3, 3, mix(PURP, IVORY, 0.6))
    r.set(4, 2, mix(PURP, IVORY, 0.35))
    r.outline()
    return r


def build_spark():
    w, h = 9, 9
    r = Raster(w, h)
    r.rect(4, 1, 1, 7, FLOWER)
    r.rect(1, 4, 7, 1, FLOWER)
    r.rect(4, 0, 1, 1, mix(FLOWER, IVORY, 0.5))
    r.rect(4, 8, 1, 1, mix(FLOWER, IVORY, 0.5))
    r.rect(0, 4, 1, 1, mix(FLOWER, IVORY, 0.5))
    r.rect(8, 4, 1, 1, mix(FLOWER, IVORY, 0.5))
    r.circle(4, 4, 2, mix(FLOWER, IVORY, 0.4))
    r.circle(4, 4, 1, IVORY)
    r.outline()
    return r


def build_blood():
    w, h = 5, 6
    r = Raster(w, h)
    r.circle(2, 3, 2, RED)
    r.set(2, 0, RED_H)
    r.rect(2, 1, 1, 2, RED_H)
    r.set(1, 4, RED_LO)
    r.outline()
    return r


def build_soul():
    """The wisp that lifts out of a killed enemy: bright core, tapering tail."""
    w, h = 8, 12
    r = Raster(w, h)
    r.circle(4, 4, 3, mix(SKY, IVORY, 0.4))
    r.circle(4, 3, 2, IVORY)
    r.set(4, 1, mix(IVORY, SKY, 0.3))
    r.rect(3, 8, 3, 2, mix(SKY, IVORY, 0.2))
    r.rect(4, 10, 1, 2, mix(SKY, IVORY, 0.1))
    r.outline()
    return r


def build_portrait():
    """24x24 face for the HUD portrait plate."""
    w, h = 24, 24
    r = Raster(w, h, mix(PANEL, LINE, 0.4))
    r.ellipse(12, 13, 7, 8, SKIN)
    r.ellipse(12, 11, 7, 6, SKIN)
    r.rect(16, 8, 3, 12, SKIN_LO)                 # one-sided key light
    r.rect(4, 2, 16, 6, HAIR)
    r.rect(3, 4, 3, 12, HAIR)
    r.rect(18, 4, 3, 12, HAIR)
    r.rect(5, 2, 10, 1, HAIR_HI)
    r.rect(6, 9, 5, 2, LINE)
    r.rect(13, 9, 5, 2, LINE)
    r.rect(7, 10, 2, 1, RED_H)
    r.rect(15, 10, 2, 1, RED_H)
    r.rect(11, 13, 2, 3, SKIN_LO)
    r.rect(10, 17, 4, 2, RED)
    r.rect(6, 19, 12, 5, RED_LO)
    r.rect(8, 18, 8, 2, IVORY)
    r.rect(11, 20, 2, 2, GOLD)
    return r


def build_emblem():
    """Bat wings the reference puts behind the portrait."""
    w, h = 24, 14
    r = Raster(w, h)
    for i in range(11):
        y = 2 + (i * 3) // 4
        r.rect(1 + i, y, 1, 9 - y, PURP)
        r.rect(22 - i, y, 1, 9 - y, PURP)
        r.rect(1 + i, y, 1, 2, mix(PURP, IVORY, 0.4))
    r.rect(4, 10, 16, 2, PURP_LO)
    r.rect(9, 4, 6, 8, PURP_LO)
    r.rect(10, 5, 4, 4, PANEL)
    r.outline()
    return r


SPRITES = [
    ("hero_idle0", lambda: build_hero("idle", 0)),
    ("hero_idle1", lambda: build_hero("idle", 1)),
    ("hero_run0", lambda: build_hero("run", 0)),
    ("hero_run1", lambda: build_hero("run", 1)),
    ("hero_run2", lambda: build_hero("run", 2)),
    ("hero_run3", lambda: build_hero("run", 3)),
    ("hero_jump", lambda: build_hero("jump", 0)),
    ("hero_fall", lambda: build_hero("fall", 0)),
    ("hero_attack0", lambda: build_hero("attack", 0)),
    ("hero_attack1", lambda: build_hero("cast", 0)),
    ("hero_hurt", lambda: build_hero("hurt", 0)),
    ("whip0", lambda: build_whip(0)),
    ("whip1", lambda: build_whip(1)),
    ("whip2", lambda: build_whip(2)),
    ("bat0", lambda: build_bat(0)),
    ("bat1", lambda: build_bat(1)),
    ("imp0", lambda: build_imp(0)),
    ("imp1", lambda: build_imp(1)),
    ("owl0", lambda: build_owl(0)),
    ("owl1", lambda: build_owl(1)),
    ("villager", build_villager),
    ("moon", build_moon),
    ("fence", build_fence),
    ("lamp", build_lamp),
    ("grave", build_grave),
    ("statue", build_statue),
    ("heart", lambda: build_heart(0)),
    ("heart_empty", lambda: build_heart(1)),
    ("coin", build_coin),
    ("orb", build_orb),
    ("spark", build_spark),
    ("blood", build_blood),
    ("soul", build_soul),
    ("portrait", build_portrait),
    ("emblem", build_emblem),
]


# ---- previews --------------------------------------------------------------
def write_sheet(items, path, scale=4, cols=6, cell=None, bg=(36, 38, 48)):
    from PIL import Image, ImageDraw
    if cell is None:
        cell = (max((r.w for _, r in items), default=TILE),
                max((r.h for _, r in items), default=TILE))
    cw = max(cell[0], max((r.w for _, r in items), default=TILE))
    ch = max(cell[1], max((r.h for _, r in items), default=TILE))
    cell = (cw, ch)
    rows = (len(items) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * cell[0] * scale + (cols + 1) * 6,
                              rows * (cell[1] * scale + 12) + 12), (24, 26, 34))
    d = ImageDraw.Draw(sheet)
    for i, (name, r) in enumerate(items):
        img = Image.new("RGB", (r.w, r.h), bg)
        px = img.load()
        for y in range(r.h):
            for x in range(r.w):
                c = r.get(x, y)
                if c is not None:
                    px[x, y] = c
        img = img.resize((r.w * scale, r.h * scale), Image.NEAREST)
        x = 6 + (i % cols) * (cell[0] * scale + 6)
        y = 6 + (i // cols) * (cell[1] * scale + 12)
        sheet.paste(img, (x, y))
        d.text((x + 2, y + r.h * scale + 2), name, fill=(210, 215, 230))
    folder = os.path.dirname(path)
    if folder:
        os.makedirs(folder, exist_ok=True)
    sheet.save(path)
    print("sheet ->", path, sheet.size, "(%d items)" % len(items))


def write_scene(path):
    """One 240x320 mock frame: bands + ground + hero + props, judged by eye.

    The ground surface is drawn where VxpBody2D will actually put the feet
    (tile_row * 16), so if the lip and the collision plane disagree this frame
    shows the hero floating or sunk in instead of hiding it.
    """
    from PIL import Image
    far, mid, near = band_far(), band_mid(), band_near()
    W, H = 240, 320
    img = Image.new("RGB", (W, H), SKY)
    px = img.load()

    def blit(r, ox, oy):
        for y in range(r.h):
            for x in range(r.w):
                c = r.get(x, y)
                if c is None:
                    continue
                dx, dy = ox + x, oy + y
                if 0 <= dx < W and 0 <= dy < H:
                    px[dx, dy] = c

    surface = 15 * TILE                       # y of the walkable plane
    # One vertical sky gradient behind everything, pale at the top and closing
    # to the forest dark at the horizon. The bands are shorter than the space
    # they cover, so this - not another band - is what fills between them.
    for y in range(surface):
        t = y / float(surface - 1)
        col = mix(SKY_TOP, GAP, t / 0.62) if t < 0.62 else \
            mix(GAP, PINE_NEAR_D, (t - 0.62) / 0.38)
        for x in range(W):
            px[x, y] = col
    for tile, oy in ((far, 30), (mid, 78), (near, surface - near.h)):
        for rep in range(-1, W // tile.w + 2):
            blit(tile, rep * tile.w, oy)
    blit(build_moon(), 150, 32)
    tops = [tile_top("moss"), tile_top(""), tile_top("flowers")]
    for i, x in enumerate(range(0, W, TILE)):
        blit(tops[i % 3], x, surface)
        body = tile_rock(i % 2)
        for y in range(surface + TILE, H, TILE):
            blit(body, x, y)
    # a pit on the right, and a ledge over it
    for x in range(176, 208):
        for y in range(surface, H):
            px[x, y] = mix(GAP, LINE, 0.55)
    plat, plat_l, plat_r = (tile_plat("mid"), tile_plat("left"), tile_plat("right"))
    blit(plat_l, 160, 184)
    blit(plat, 176, 184)
    blit(plat_r, 192, 184)
    blit(tile_post(), 224, 176)

    blit(build_fence(), 20, surface - 20)
    blit(build_fence(), 36, surface - 20)
    blit(build_grave(), 60, surface - 16)
    blit(build_lamp(), 120, surface - 34)
    blit(build_statue(), 216, surface - 40)
    blit(build_villager(), 140, surface - 22)
    blit(build_hero("run", 1), 90, surface - HERO_H + 1)
    blit(build_whip(1), 90 + 4, surface - HERO_H + 3)
    blit(build_bat(0), 176, 150)
    blit(build_owl(1), 40, 120)
    blit(build_imp(0), 176, 184 - 22 + 1)
    blit(build_heart(), 78, surface - 10)
    blit(build_coin(), 100, surface - 40)
    img.save(path)
    print("scene ->", path)


# ---- header ----------------------------------------------------------------
def emit_atlas(L, tag, enum_prefix, tiles, cols, opaque):
    """Emit one tile atlas: pixels, optional mask, the VxpeSprite565, cell enum.

    opaque=False makes the core take the masked blit path, which is what the
    ledge and pillar cells need; the ground atlas stays opaque for copy_tile.
    Returns the const bytes the block contributes.
    """
    rows = (len(tiles) + cols - 1) // cols
    cells = rows * cols
    L.append("#define %s_COLS %d\n#define %s_ROWS %d\n" % (tag, cols, tag, rows))
    L.append("/* %s cells are %d wide; cell (col,row) starts at\n"
             " * (row*VV_TILE*%s_COLS + col)*VV_TILE pixels. Cell 0 is never drawn. */\n"
             % (tag, cols, tag))
    L.append("static const uint16_t %s_PX[%s_COLS * %s_ROWS * VV_TILE * VV_TILE] = {"
             % (tag, tag, tag))

    def cell_at(idx):
        return tiles[idx][1] if idx < len(tiles) else tiles[0][1]

    for row in range(rows):
        L.append("  /* row %d */" % row)
        line = []
        for y in range(TILE):
            for col in range(cols):
                r = cell_at(row * cols + col)
                for x in range(TILE):
                    v = r.get(x, y)
                    line.append("0x%04X" % (0 if v is None else c565(v)))
        for j in range(0, len(line), 10):
            L.append("  " + ", ".join(line[j:j + 10]) + ",")
    L.append("};\n")

    mask_bytes = 0
    if not opaque:
        # one mask for the whole atlas image, in the row-major pixel order
        # vxpe2d_blit walks: bit y*(cols*TILE)+x, MSB first, no row padding.
        bits = []
        for row in range(rows):
            for y in range(TILE):
                for col in range(cols):
                    r = cell_at(row * cols + col)
                    bits += [1 if r.get(x, y) is not None else 0
                             for x in range(TILE)]
        mk = []
        for i in range(0, len(bits), 8):
            byte = 0
            for j in range(8):
                if i + j < len(bits) and bits[i + j]:
                    byte |= 0x80 >> j
            mk.append(byte)
        mask_bytes = len(mk)
        L.append("static const uint8_t %s_MK[%d] = {" % (tag, len(mk)))
        for j in range(0, len(mk), 12):
            L.append("  " + ", ".join("0x%02X" % v for v in mk[j:j + 12]) + ",")
        L.append("};\n")

    L.append("static const VxpeSprite565 %s = {\n"
             "    %s_PX, %s, %d * VV_TILE,\n"
             "    %d * VV_TILE, %d * VV_TILE, %d\n};\n"
             % (tag, tag, ("%s_MK" % tag) if not opaque else "0",
                cols, rows, cols, 1 if opaque else 0))
    L.append("enum {")
    for i, (name, _) in enumerate(tiles):
        L.append("    %s%s = %d," % (enum_prefix, name.upper(), i))
    L.append("    %sN_TILE = %d\n};\n" % (enum_prefix, len(tiles)))
    return cells * TILE * TILE * 2 + mask_bytes


def emit_header(tiles, tiles_masked, sprites, bands):
    L = ["/* Generated by tools/generate_vampireveil_assets.py - do not edit.\n"
         " *\n"
         " * Vampire Veil: Night Hunt art. The opaque 16x16 atlas feeds the ground\n"
         " * layer (copy_tile fast path), the masked one the ledges and pillars that\n"
         " * need air around them; both are VxpTilemap2D atlases with cell 0 blank.\n"
         " * Characters, props, FX and HUD art are masked sprites, and the three\n"
         " * bands are opaque, horizontally tileable background strips.\n"
         " * Colours are histograms of tmp/veil_ref, the reference trailer frames.\n"
         " *\n"
         " * Masks are packed the way vxpe2d_blit reads them: bit y*width+x, MSB\n"
         " * first, no row padding, ceil(width*height/8) bytes. */\n",
         "#ifndef VXPE_VAMPIREVEIL_ASSETS_GEN_H\n"
         "#define VXPE_VAMPIREVEIL_ASSETS_GEN_H\n\n"
         "#include <stdint.h>\n"
         "#include <graphics/VxpRender2D.h>\n\n"
         "#define VV_TILE 16\n"]
    total = emit_atlas(L, "VV_ATLAS", "VV_T_", tiles, 8, True)
    total += emit_atlas(L, "VV_ATLAS2", "VV_P_", tiles_masked, 4, False)

    L.append("/* A masked sprite: mask stride is (w + 7) / 8 bytes per row only in the\n"
             " * packed sense above, so VxpeSprite565 can point at it unchanged. */\n"
             "typedef struct VvSprite {\n"
             "    const uint16_t* px;\n"
             "    const uint8_t* mask;\n"
             "    uint8_t w;\n"
             "    uint8_t h;\n"
             "} VvSprite;\n")

    for name, r in sprites:
        px, mk = r.bake()
        L.append("static const uint16_t vv_sp_%s_px[%d] = {  /* %dx%d */"
                 % (name, len(px), r.w, r.h))
        for j in range(0, len(px), 10):
            L.append("  " + ", ".join("0x%04X" % v for v in px[j:j + 10]) + ",")
        L.append("};")
        L.append("static const uint8_t vv_sp_%s_mk[%d] = {" % (name, len(mk)))
        for j in range(0, len(mk), 12):
            L.append("  " + ", ".join("0x%02X" % v for v in mk[j:j + 12]) + ",")
        L.append("};\n")
        total += len(px) * 2 + len(mk)

    L.append("enum {")
    for i, (name, _) in enumerate(sprites):
        L.append("    VV_SP_%s = %d," % (name.upper(), i))
    L.append("    VV_NSPRITE = %d\n};\n" % len(sprites))
    L.append("static const VvSprite VV_SPRITES[VV_NSPRITE] = {")
    for name, r in sprites:
        L.append("    { vv_sp_%s_px, vv_sp_%s_mk, %d, %d }," % (name, name, r.w, r.h))
    L.append("};\n")

    for tag, r in bands:
        px, _ = r.bake()
        total += len(px) * 2
        L.append("#define VV_BAND_%s_W %d" % (tag.upper(), r.w))
        L.append("#define VV_BAND_%s_H %d" % (tag.upper(), r.h))
        L.append("static const uint16_t VV_BAND_%s[VV_BAND_%s_W * VV_BAND_%s_H] = {"
                 % (tag.upper(), tag.upper(), tag.upper()))
        for j in range(0, len(px), 10):
            L.append("  " + ", ".join("0x%04X" % v for v in px[j:j + 10]) + ",")
        L.append("};\n")
        L.append("static const VxpeSprite565 VV_BAND_%s_SPRITE = {\n"
                 "    VV_BAND_%s, 0, VV_BAND_%s_W, VV_BAND_%s_H, VV_BAND_%s_W, 1\n};\n"
                 % (tag.upper(), tag.upper(), tag.upper(), tag.upper(), tag.upper()))

    L.append("#endif /* VXPE_VAMPIREVEIL_ASSETS_GEN_H */")

    folder = os.path.dirname(OUT_HEADER)
    if folder:
        os.makedirs(folder, exist_ok=True)
    with open(OUT_HEADER, "w", newline="\n") as f:
        f.write("\n".join(L) + "\n")

    print("header -> %s (%d bytes const, %d+%d tiles, %d sprites, %d bands)"
          % (OUT_HEADER, total, len(tiles), len(tiles_masked), len(sprites),
             len(bands)))


def main():
    tiles = [(n, fn()) for n, fn in TILES]
    tiles2 = [(n, fn()) for n, fn in TILES_MASKED]
    sprites = [(n, fn()) for n, fn in SPRITES]
    bands = [("far", band_far()), ("mid", band_mid()), ("near", band_near())]
    if "--preview" not in sys.argv:
        emit_header(tiles, tiles2, sprites, bands)
    write_sheet(tiles, SHEET_TILES, scale=5, cols=5, cell=(TILE, TILE))
    write_sheet(tiles2, SHEET_TILES2, scale=5, cols=5, cell=(TILE, TILE))
    write_sheet(bands, SHEET_BANDS, scale=2, cols=1,
                cell=(max(b[1].w for b in bands), max(b[1].h for b in bands)))
    write_sheet([s for s in sprites if s[0].startswith("hero")],
                SHEET_HERO, scale=5, cols=6, cell=(HERO_W, HERO_H))
    write_sheet([s for s in sprites if s[0].startswith(("whip", "bat", "imp",
                                                        "owl", "villager"))],
                SHEET_ACTORS, scale=4, cols=4, cell=(32, 26))
    write_sheet([s for s in sprites if s[0] in ("fence", "lamp", "grave",
                                                "statue", "coin", "orb",
                                                "spark", "blood", "soul")],
                SHEET_PROPS, scale=4, cols=5, cell=(20, 34))
    write_sheet([s for s in sprites if s[0] in ("portrait", "emblem", "moon",
                                                "heart", "heart_empty")],
                SHEET_HUD, scale=6, cols=3, cell=(24, 28))
    write_scene("tmp/veil_scene_preview.png")


if __name__ == "__main__":
    main()
