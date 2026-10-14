#!/usr/bin/env python3
"""Generate TacticsVanguard2D's terrain, unit and portrait art as baked RGB565.

The reference (tmp/tactics_ref/g00.png and the frames around it) is a 16-px
tactical map: yellow-green grass with speckle, tan roads, clumpy two-tone pine
forests, faceted grey mountains with snow peaks, a blue lake with wave dashes
and a dithered sand shore, golden keeps and orange-roofed cottages, plus 16x26
cel-outlined knights that overflow their tile upward. Colours below come from
that frame's histogram, not from memory.

    python tools/generate_tacticsvanguard_assets.py            # header + preview
    python tools/generate_tacticsvanguard_assets.py --preview  # preview only

Terrain tiles are baked opaque (a full 16x16 block always covers its cell);
units and the cut-in portrait carry a 1-bit visibility mask.

Usage:
  python tools/generate_tacticsvanguard_assets.py
"""
import os
import sys

TILE = 16
OUT_HEADER = "examples/TacticsVanguard2D/src/assets_gen.h"
PREVIEW = "tmp/tactics_terrain_preview.png"
UNITS_PREVIEW = "tmp/tactics_units_preview.png"
CREST_PREVIEW = "tmp/tactics_crest_preview.png"


def c565(c):
    r, g, b = c
    return ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3)


def mix(a, b, t):
    return tuple(int(a[i] * (1 - t) + b[i] * t) for i in range(3))


def shade(c, k):
    return tuple(min(255, max(0, int(v * k))) for v in c)


# ---- palette, measured off the reference histogram -------------------------
GRASS      = (0x88, 0xB1, 0x3F)   # #88b13f, the single most common colour
GRASS_HI   = (0x9C, 0xB0, 0x4D)   # #9cb04d sunned patches
GRASS_LO   = (0x7E, 0xA7, 0x3C)   # #7ea73c
GRASS_SH   = (0x52, 0x7A, 0x2D)   # #527a2d shadow cast on grass
ROAD       = (0xBD, 0xB8, 0x8F)   # #bdb88f
ROAD_HI    = (0xD6, 0xC7, 0x94)   # #d6c794
ROAD_LO    = (0xAE, 0xAD, 0x86)   # #aead86
ROAD_SP    = (0x8B, 0x97, 0x63)   # #897863-ish flecks
SAND       = (0xDD, 0xC6, 0x86)   # #ddc686
WATER      = (0x1E, 0x5E, 0xA3)   # #1e5ea3
WATER_HI   = (0x39, 0x7B, 0xB6)   # #397bb6 wave crests
WATER_LO   = (0x08, 0x43, 0x98)   # #084398 depth
WATER_SH   = (0x22, 0x65, 0xAE)   # #2265ae mid
TREE_HI    = (0x3D, 0x97, 0x0C)   # #3d970c crown light
TREE_MID   = (0x1D, 0x71, 0x0C)   # #1d710c crown
TREE_DK    = (0x0D, 0x39, 0x0C)   # #0d390c crown shadow
TRUNK      = (0x6B, 0x5C, 0x4F)   # #6b5c4f
TRUNK_DK   = (0x35, 0x27, 0x1E)   # #35271e
ROCK_HI    = (0x9A, 0x93, 0x8C)
ROCK       = (0x7E, 0x76, 0x6E)
ROCK_LO    = (0x5A, 0x53, 0x4C)
ROCK_DK    = (0x35, 0x27, 0x1E)
SNOW       = (0xE6, 0xE0, 0xB1)   # #e6e0b1 (the reference's "white" is warm)
GOLD       = (0xD9, 0xA8, 0x2C)   # keep walls
GOLD_HI    = (0xF0, 0xC8, 0x5A)
GOLD_LO    = (0xA8, 0x77, 0x1E)
ROOF       = (0xC8, 0x6A, 0x2A)   # cottage roofs
ROOF_LO    = (0x8E, 0x44, 0x1C)
WALL       = (0xD8, 0xC0, 0x90)
WALL_LO    = (0xA8, 0x94, 0x68)
DOOR       = (0x2A, 0x4A, 0x8C)
LINE       = (0x05, 0x02, 0x04)   # #050204 the outline black
IVORY      = (0xF2, 0xEC, 0xD0)   # arrow / popup body
NAVY       = (0x30, 0x3E, 0x6D)   # popup text, dark trim
SEAM       = (0x6E, 0x8E, 0x33)   # faint tile seam on grass


class Raster:
    """A small RGB canvas with `None` for transparent; deterministic hash noise."""

    def __init__(self, w, h, fill=None):
        self.w, self.h = w, h
        self.d = [[fill for _ in range(w)] for _ in range(h)]

    def set(self, x, y, c):
        if 0 <= x < self.w and 0 <= y < self.h and c is not None:
            self.d[y][x] = c

    def get(self, x, y):
        if 0 <= x < self.w and 0 <= y < self.h:
            return self.d[y][x]
        return None

    def rect(self, x0, y0, w, h, c):
        for y in range(y0, y0 + h):
            for x in range(x0, x0 + w):
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

    def disc(self, cx, cy, r, c):
        for y in range(cy - r, cy + r + 1):
            for x in range(cx - r, cx + r + 1):
                if abs(x - cx) + abs(y - cy) <= r * 1.25:
                    self.set(x, y, c)

    def ellipse(self, cx, cy, rx, ry, c):
        for y in range(cy - ry, cy + ry + 1):
            for x in range(cx - rx, cx + rx + 1):
                dx, dy = (x - cx) / float(rx), (y - cy) / float(ry)
                if dx * dx + dy * dy <= 1.05:
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
        """1-px dark border around every opaque run (keeps sprites crisp)."""
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
        """Paste non-transparent pixels onto another raster."""
        for y in range(self.h):
            for x in range(self.w):
                c = self.d[y][x]
                if c is not None:
                    dst.set(ox + x, oy + y, c)

    def bake(self):
        px, mk = [], []
        for y in range(self.h):
            for x in range(self.w):
                c = self.d[y][x]
                px.append(0 if c is None else c565(c))
        bits = []
        for y in range(self.h):
            row = []
            for x in range(self.w):
                row.append(1 if self.d[y][x] is not None else 0)
            for i in range(0, self.w, 8):
                byte = 0
                for j in range(8):
                    if i + j < self.w and row[i + j]:
                        byte |= 0x80 >> j
                bits.append(byte)
        return px, bits


# ---- terrain ---------------------------------------------------------------
def base_grass(r, salt=0):
    r.rect(0, 0, TILE, TILE, GRASS)
    # broad sunned/shaded patches, then fine flecks: the reference grass is never flat
    for y in range(TILE):
        for x in range(TILE):
            h = r.hash(x, y, salt)
            if h < 0.11:
                r.set(x, y, GRASS_LO)
            elif h < 0.19:
                r.set(x, y, GRASS_HI)
            elif h < 0.215:
                r.set(x, y, mix(GRASS, GRASS_SH, 0.55))
    r.speckle(3, mix(GRASS, LINE, 0.18), salt + 7)


def tile_grass(variant=0):
    r = Raster(TILE, TILE)
    base_grass(r, variant * 31)
    if variant == 1:                      # a tuft of blades
        r.line(6, 11, 5, 8, GRASS_SH)
        r.line(8, 11, 8, 7, mix(GRASS_HI, LINE, 0.12))
        r.line(10, 11, 11, 8, GRASS_SH)
    if variant == 2:                      # pebbles
        r.disc(4, 12, 1, mix(ROAD_LO, LINE, 0.25))
        r.disc(12, 5, 1, mix(ROAD_LO, LINE, 0.2))
    if variant == 3:                      # a fallen log
        r.rect(3, 9, 10, 3, TRUNK)
        r.rect(3, 9, 10, 1, mix(TRUNK, (255, 255, 255), 0.25))
        r.rect(3, 11, 10, 1, TRUNK_DK)
        r.set(3, 10, TRUNK_DK)
        r.set(12, 10, TRUNK_DK)
    return r


def tile_road(variant=0):
    r = Raster(TILE, TILE)
    # Neutral packed dirt: mixing toward grass green made it a third kind of
    # field tile, so the road is defined by its wheel ruts instead of its hue.
    base = mix(ROAD, (0x8E, 0x86, 0x72), 0.34)
    r.rect(0, 0, TILE, TILE, base)
    for y in range(TILE):
        for x in range(TILE):
            h = r.hash(x // 2, y // 2, variant * 17 + 3)
            if h < 0.10:
                r.rect(x, y, 2, 2, mix(base, LINE, 0.16))
            elif h < 0.20:
                r.rect(x, y, 2, 2, mix(base, (255, 255, 255), 0.22))
    r.speckle(2, mix(ROAD_LO, LINE, 0.5), salt=variant + 4)
    r.line(0, 5, 15, 4, mix(base, LINE, 0.26), 2)          # wheel ruts
    r.line(0, 12, 15, 13, mix(base, LINE, 0.2), 2)
    r.line(0, 4, 15, 3, mix(base, (255, 255, 255), 0.28))
    if variant:
        r.disc(3, 9, 1, mix(base, LINE, 0.4))
        r.disc(11, 9, 1, mix(base, LINE, 0.34))
        r.disc(7, 15, 1, mix(base, (255, 255, 255), 0.3))
    return r


def tile_sand():
    r = Raster(TILE, TILE)
    r.rect(0, 0, TILE, TILE, mix(SAND, (255, 255, 255), 0.08))
    for y in range(TILE):
        for x in range(TILE):
            h = r.hash(x, y, 21)
            if h < 0.09:
                r.set(x, y, mix(SAND, (0xC0, 0x96, 0x50), 0.6))
            elif h < 0.16:
                r.set(x, y, mix(SAND, (255, 255, 255), 0.35))
    # wind ripples: the reference's sand is banded, not speckled
    for y in (3, 8, 13):
        for x in range(TILE):
            if (x + y) % 5 < 2:
                r.set(x, y, mix(SAND, (0xC0, 0x96, 0x50), 0.45))
    return r


def tile_water(frame=0):
    r = Raster(TILE, TILE)
    r.rect(0, 0, TILE, TILE, WATER)
    for y in range(TILE):
        for x in range(TILE):
            h = r.hash(x // 2, y, 3)
            if h < 0.16:
                r.set(x, y, WATER_LO)
            elif h < 0.26:
                r.set(x, y, WATER_SH)
    # crest dashes: a 3-px lit dash plus a dark tail, drifting 2 px per frame
    for i, by in enumerate((2, 6, 10, 13)):
        x = (2 + i * 5 + frame * 2) % TILE
        for k in range(3):
            r.set((x + k) % TILE, by, WATER_HI)
        r.set((x + 3) % TILE, by, WATER_LO)
        r.set((x + 1) % TILE, by + 1, WATER_SH)
    return r


def tile_shore():
    """Dithered land->water edge (the reference shoreline is a checker, not a line)."""
    r = Raster(TILE, TILE)
    dry = mix(SAND, (255, 255, 255), 0.08)
    r.rect(0, 0, TILE, 9, dry)
    for y in range(9):
        for x in range(TILE):
            h = r.hash(x, y, 21)
            if h < 0.09:
                r.set(x, y, mix(SAND, (0xC0, 0x96, 0x50), 0.6))
            elif h < 0.14:
                r.set(x, y, mix(SAND, (255, 255, 255), 0.35))
    for y in range(9, 11):                # wet sand / foam checker
        for x in range(TILE):
            wob = int(1.6 * ((x * 5) % 7) / 6.0)
            if (x + y + wob) & 1:
                r.set(x, y, WATER_SH)
            else:
                r.set(x, y, mix(SAND, WATER, 0.4))
    for y in range(11, TILE):
        for x in range(TILE):
            r.set(x, y, WATER_LO if r.hash(x, y, 8) < 0.22 else WATER)
    r.line(2, 13, 5, 13, WATER_HI)        # one foam crest
    r.line(10, 14, 12, 14, WATER_HI)
    return r


def tree(c, cx, by, s):
    """A conifer drawn on a transparent canvas: pointed layered crown, three
    value bands (lit left, mid, dark right), short trunk. The caller outlines
    the whole canvas once so overlapping trees merge."""
    th = max(2, int(3 * s))
    top = by - th - int(11 * s)
    bot = by - th
    depth = max(1, bot - top)
    for y in range(bot + 1, by + 1):          # trunk
        c.set(cx - 1, y, TRUNK_DK)
        c.set(cx, y, TRUNK)
    for y in range(top, bot + 1):             # crown
        t = (y - top) / float(depth)
        half = int(round(s * (0.9 + 3.5 * t)))
        if (y - top) % 4 == 3:                # skirt notch
            half = max(1, half - 1)
        for x in range(cx - half, cx + half + 1):
            rel = (x - cx) / float(max(1, half))
            if y == bot:
                col = TREE_DK
            elif rel < -0.4:
                col = TREE_HI
            elif rel > 0.4:
                col = TREE_DK
            else:
                col = TREE_MID
            c.set(x, y, col)
    c.set(cx, top, mix(TREE_HI, (255, 255, 255), 0.3))   # lit tip
    c.set(cx - 1, top + 3, TREE_HI)


def tile_forest(variant=0):
    r = Raster(TILE, TILE)
    base_grass(r, 55 + variant)
    c = Raster(TILE, TILE)
    spots = ((5, 15, 1.0), (12, 15, 0.85)) if variant == 0 else \
            ((4, 14, 0.85), (11, 16, 1.0)) if variant == 1 else ((8, 16, 1.15),)
    for cx, by, s in spots:                   # contact shadows on the grass
        r.ellipse(cx, by, int(3.6 * s), max(1, int(1.4 * s)), GRASS_SH)
    for cx, by, s in spots:
        tree(c, cx, by, s)
    c.outline()
    c.compose(r)
    return r


def ridge(c, ax, ay, base, wl, wr):
    """One angular rock slab: lit left face, mid body, shaded right face."""
    for y in range(ay, base + 1):
        t = (y - ay) / float(max(1, base - ay))
        x0 = int(round(ax - wl * t))
        x1 = int(round(ax + wr * t))
        for x in range(x0, x1 + 1):
            if x <= ax - max(1, int((ax - x0) * 0.6)):
                col = ROCK_HI
            elif x >= ax + max(1, int((x1 - ax) * 0.55)):
                col = ROCK_LO
            else:
                col = ROCK
            if c.hash(x, y, 17) < 0.07:
                col = mix(col, LINE, 0.3)
            c.set(x, y, col)
    c.line(ax, ay + 1, ax - 1, base, ROCK_DK)
    c.line(ax + 2, ay + 3, ax + 3, base, ROCK_DK)


def tile_mountain(variant=0):
    r = Raster(TILE, TILE)
    base_grass(r, 71 + variant)
    c = Raster(TILE, TILE)
    if variant == 0:
        ridge(c, 6, 3, 15, 5, 5)
        ridge(c, 13, 8, 15, 3, 2)
    else:
        ridge(c, 4, 6, 15, 4, 4)
        ridge(c, 11, 3, 15, 4, 4)
    c.outline()
    c.compose(r)
    return r


def tile_peak():
    r = Raster(TILE, TILE)
    base_grass(r, 83)
    c = Raster(TILE, TILE)
    ridge(c, 8, 1, 15, 7, 7)
    for y in range(1, 5):                   # snow band on the lit shoulder
        t = (y - 1) / 14.0
        for x in range(int(round(8 - 7 * t)), 9):
            c.set(x, y, SNOW)
            if c.get(x + 1, y) is not None:
                c.set(x + 1, y, mix(SNOW, ROCK_HI, 0.5))
    c.outline()
    c.compose(r)
    return r


def tile_house():
    r = Raster(TILE, TILE)
    base_grass(r, 97)
    r.ellipse(8, 15, 7, 2, GRASS_SH)
    c = Raster(TILE, TILE)
    c.rect(3, 9, 11, 6, WALL)               # walls
    c.rect(11, 9, 3, 6, WALL_LO)
    for y in range(3, 10):                  # gabled roof, apex at (8, 3)
        half = int(round(1 + (y - 3) * 1.5))
        for x in range(8 - half, 8 + half + 1):
            col = ROOF if x <= 8 + half - 2 else ROOF_LO
            if y == 3 or (y % 3 == 0 and x < 8):
                col = mix(ROOF, (255, 255, 255), 0.22)
            c.set(x, y, col)
    c.rect(1, 9, 14, 1, ROOF_LO)            # eave line
    c.rect(6, 11, 3, 4, DOOR)               # door
    c.rect(6, 11, 3, 1, mix(DOOR, (255, 255, 255), 0.25))
    c.rect(10, 11, 2, 2, WATER_HI)          # window
    c.outline()
    c.compose(r)
    return r


def tile_keep():
    r = Raster(TILE, TILE)
    base_grass(r, 101)
    r.ellipse(8, 15, 7, 2, GRASS_SH)
    c = Raster(TILE, TILE)
    c.rect(3, 4, 11, 11, GOLD)
    c.rect(10, 4, 4, 11, GOLD_LO)
    for x in (3, 6, 9, 12):                 # battlements
        c.rect(x, 2, 2, 3, GOLD)
        c.rect(x, 2, 2, 1, GOLD_HI)
    c.rect(6, 10, 4, 5, DOOR)               # gate
    c.rect(6, 10, 4, 1, mix(DOOR, (255, 255, 255), 0.25))
    c.rect(4, 6, 2, 2, NAVY)                # arrow slits
    c.rect(11, 6, 2, 2, NAVY)
    c.outline()
    c.compose(r)
    return r


def tile_tent():
    r = Raster(TILE, TILE)
    base_grass(r, 107)
    r.ellipse(8, 15, 7, 2, GRASS_SH)
    c = Raster(TILE, TILE)
    for y in range(5, 15):
        half = 1 + (y - 5) // 2
        for x in range(8 - half, 8 + half + 1):
            col = IVORY if (y - 5) % 4 < 2 else mix(IVORY, ROAD_LO, 0.45)
            if x >= 8 + half - 1:
                col = mix(col, NAVY, 0.4)
            c.set(x, y, col)
    c.rect(8, 3, 1, 3, TRUNK_DK)            # pole and pennant
    c.rect(9, 3, 3, 1, DOOR)
    c.rect(6, 11, 4, 4, NAVY)               # entrance
    c.outline()
    c.compose(r)
    return r


def tile_rubble():
    r = Raster(TILE, TILE)
    base_grass(r, 113)
    c = Raster(TILE, TILE)
    for (x, y, w, h) in ((1, 11, 6, 4), (8, 12, 6, 3), (4, 7, 6, 4),
                         (11, 7, 4, 4)):
        c.rect(x, y, w, h, ROCK)
        c.rect(x, y, w, 1, ROCK_HI)
        c.rect(x, y + h - 1, w, 1, ROCK_LO)
        c.rect(x + w - 1, y, 1, h, ROCK_LO)
    c.outline()
    c.compose(r)
    return r


def tile_bridge():
    r = Raster(TILE, TILE)
    r.rect(0, 0, TILE, TILE, WATER)
    r.rect(0, 4, TILE, 8, TRUNK)
    r.rect(0, 4, TILE, 1, mix(TRUNK, (255, 255, 255), 0.3))
    r.rect(0, 11, TILE, 1, TRUNK_DK)
    for x in range(1, TILE, 4):
        r.line(x, 5, x, 11, TRUNK_DK)
    for x in (0, 5, 10, 15):                # rail posts
        r.rect(x, 2, 1, 3, TRUNK_DK)
        r.rect(x, 12, 1, 3, TRUNK_DK)
    r.rect(0, 3, TILE, 1, LINE)
    r.rect(0, 12, TILE, 1, LINE)
    return r


# ---- units -----------------------------------------------------------------
# 16x26 canvas, feet on y=25: a knight fills its 16-px tile and overflows 10 px
# upward, which is exactly how the reference reads at 16 px. Cavalry needs a
# wider box for the horse, so it gets its own canvas.
UW, UH = 16, 26
CW, CH = 24, 26

SKIN_C = (0xE8, 0xBE, 0x96)
METAL_C = (0xC8, 0xCE, 0xDA)
WOOD_C = (0x8A, 0x5F, 0x38)
LEATHER_C = (0x6B, 0x4A, 0x2E)
GOLD_C = (0xE0, 0xB0, 0x3A)
HORSE = (0x8A, 0x5A, 0x38)
HORSE_L = (0xA8, 0x72, 0x48)
HORSE_D = (0x5E, 0x3A, 0x24)
HORSE_DD = (0x34, 0x22, 0x18)


def pal(armour, cloth, accent, hair, cape=None):
    """Material slots for one army. Light/dark steps are derived, so both sides
    keep the same value structure and only the hue changes."""
    return {
        "ARM": armour, "ARM_L": shade(armour, 1.45), "ARM_D": shade(armour, 0.62),
        "ARM_DD": shade(armour, 0.42),
        "CLOTH": cloth, "CLOTH_D": shade(cloth, 0.68),
        "ACCENT": accent, "ACCENT_L": shade(accent, 1.3),
        "SKIN": SKIN_C, "SKIN_D": shade(SKIN_C, 0.72),
        "HAIR": hair, "HAIR_D": shade(hair, 0.66),
        "METAL": METAL_C, "METAL_L": shade(METAL_C, 1.18),
        "METAL_D": shade(METAL_C, 0.6),
        "WOOD": WOOD_C, "WOOD_D": shade(WOOD_C, 0.66),
        "LEATHER": LEATHER_C, "LEATHER_D": shade(LEATHER_C, 0.68),
        "CAPE": cape or cloth, "CAPE_D": shade(cape or cloth, 0.7),
    }


ARMIES = {
    # the reference's player side is blue plate over navy; the opposing side is
    # crimson here so the two armies stay separable at 16 px on a 240-px screen
    "blue": pal((0x3C, 0x6E, 0xB8), (0x2A, 0x38, 0x62), GOLD_C, (0x4A, 0x35, 0x28)),
    "red":  pal((0xA8, 0x38, 0x38), (0x4A, 0x24, 0x2C), (0xD8, 0xD8, 0xE0),
                (0x2E, 0x24, 0x22)),
}


def _head(c, p, cx, opt):
    """Helmet, face and crest for rows 1..10."""
    crest = opt.get("crest", "comb")
    if crest == "hood":
        for y, w in ((4, 3), (5, 4), (6, 4), (7, 4), (8, 4), (9, 5), (10, 5)):
            c.rect(cx - w, y, 2 * w + 1, 1, p["CLOTH"] if y < 8 else p["CLOTH_D"])
        c.rect(cx - 2, 7, 5, 3, (0x14, 0x14, 0x1E))      # shadowed face
        c.set(cx + 1, 8, p["SKIN"])
        c.set(cx - 1, 8, p["SKIN"])
        return
    for y, w in ((3, 3), (4, 4), (5, 4), (6, 4), (7, 4), (8, 4)):
        c.rect(cx - w, y, 2 * w + 1, 1, p["ARM"])
    c.rect(cx - 4, 4, 2, 4, p["ARM_L"])                  # lit left shoulder of helm
    c.rect(cx + 3, 4, 2, 5, p["ARM_D"])
    c.rect(cx - 2, 6, 5, 3, p["SKIN"])                   # face
    c.rect(cx + 2, 6, 1, 3, p["SKIN_D"])
    c.rect(cx - 1, 6, 1, 3, p["ARM_D"])                  # nasal guard
    c.set(cx + 1, 7, LINE)                               # eye
    c.set(cx - 2, 7, LINE)
    c.rect(cx - 3, 9, 7, 2, p["ARM_D"])                  # chin / neck
    c.rect(cx - 2, 9, 5, 1, p["ARM_DD"])
    if crest == "comb":
        c.rect(cx - 2, 1, 5, 2, p["ACCENT"])
        c.rect(cx - 2, 1, 5, 1, p["ACCENT_L"])
    elif crest == "plume":
        c.rect(cx - 1, 1, 3, 2, p["ACCENT"])
        c.rect(cx - 1, 1, 3, 1, p["ACCENT_L"])
        c.rect(cx, 0, 1, 1, p["ACCENT_L"])
        c.rect(cx - 2, 3, 5, 1, p["ARM_L"])              # helm brow
    elif crest == "horns":
        c.rect(cx - 5, 3, 2, 2, p["ACCENT"])
        c.rect(cx + 4, 3, 2, 2, p["ACCENT"])
        c.rect(cx - 1, 2, 3, 2, p["ARM_L"])
    if opt.get("hair"):                                  # hair spilling out back
        c.rect(cx - 5, 8, 2, 4, p["HAIR"])
        c.rect(cx - 6, 10, 2, 4, p["HAIR_D"])


def _torso(c, p, cx, opt, bob):
    top = 11 + bob
    if opt.get("robe"):
        for i, w in enumerate((4, 5, 5, 6, 6, 7, 7, 8)):
            y = top + i
            c.rect(cx - w, y, 2 * w + 1, 1,
                   p["CLOTH"] if i < 5 else p["CAPE"])
            c.rect(cx + w - 1, y, 2, 1, p["CLOTH_D"])
        c.rect(cx - 4, top + 1, 9, 1, p["ACCENT"])       # sash
        return top + 8
    c.rect(cx - 4, top, 9, 3, p["ARM"])                  # shoulders/chest
    c.rect(cx - 5, top, 2, 3, p["ARM_L"])                # pauldron (lit)
    c.rect(cx + 4, top, 2, 3, p["ARM_D"])                # pauldron (shade)
    c.rect(cx + 3, top + 1, 2, 6, p["ARM_D"])
    c.rect(cx - 3, top + 3, 7, 4, p["ARM"])              # waist
    c.rect(cx - 3, top + 3, 2, 4, p["ARM_L"])
    c.rect(cx - 3, top + 6, 7, 1, p["LEATHER"])          # belt
    c.rect(cx - 1, top + 6, 2, 1, p["ACCENT"])
    if opt.get("cape"):
        c.rect(cx - 6, top + 1, 3, 8, p["CAPE"])
        c.rect(cx - 7, top + 4, 3, 6, p["CAPE_D"])
    for i, w in enumerate((4, 4, 5, 5)):                 # tunic skirt
        c.rect(cx - w, top + 7 + i, 2 * w + 1, 1, p["CLOTH"])
        c.rect(cx + w - 1, top + 7 + i, 2, 1, p["CLOTH_D"])
    return top + 11


def _legs(c, p, cx, y, pose, opt):
    if opt.get("robe"):
        c.rect(cx - 3, y, 7, 25 - y, p["CLOTH_D"])
        c.rect(cx - 3, 24, 3, 2, p["LEATHER_D"])
        c.rect(cx + 1, 24, 3, 2, p["LEATHER"])
        return
    front = pose == "step"
    lx = cx - 3 + (1 if front else 0)
    rx = cx + 1 - (1 if front else 0)
    for x, lit in ((lx, False), (rx, True)):
        c.rect(x, y, 3, 24 - y, p["ARM"] if lit else p["ARM_D"])
        c.rect(x, 24, 3, 2, p["LEATHER"] if lit else p["LEATHER_D"])
        c.rect(x - 1 if not lit else x, 25, 4, 1, p["LEATHER_D"])


def _sword(c, p, cx, pose, side=1):
    x = cx + 6 * side
    y0 = 4 if pose == "attack" else 7
    c.rect(x - 1, y0, 2, 11, p["METAL"])
    c.rect(x - 1, y0, 1, 11, p["METAL_L"])
    c.rect(x, y0 + 1, 1, 10, p["METAL_D"])
    c.rect(x - 3, y0 + 11, 6, 1, p["ACCENT"])            # crossguard
    c.rect(x - 1, y0 + 12, 2, 3, p["WOOD_D"])            # grip
    c.disc(x, y0 + 15, 1, p["ACCENT"])                   # pommel


def _axe(c, p, cx, pose, side=1):
    """Broad-axe held out to the right: the blade must stay clear of the helm,
    which is where a crescent centred on the shaft put it in the first pass."""
    x = cx + 2
    y0 = 2 if pose == "attack" else 5
    c.rect(x, y0 + 1, 2, 15, p["WOOD"])
    c.rect(x, y0 + 1, 1, 15, p["WOOD_D"])
    for i, w in enumerate((2, 4, 5, 5, 4, 2)):           # crescent head
        yy = y0 + i
        for k in range(w):
            col = p["METAL_L"] if k == w - 1 else p["METAL"]
            c.set(x + 1 + k, yy, col)
    c.set(x + 1, y0, p["METAL_D"])
    c.set(x + 1, y0 + 5, p["METAL_D"])
    c.rect(x - 1, y0 + 14, 4, 1, p["ACCENT"])            # haft guard


def _lance(c, p, cx, pose, side=1):
    y0 = 0 if pose == "attack" else 2
    x0 = cx + 6 if pose == "attack" else cx + 5
    c.line(x0, y0 + 3, x0 - 1, 22, p["WOOD"], 2)
    c.line(x0 - 1, y0 + 4, x0 - 1, 22, p["WOOD_D"])
    c.rect(x0 - 2, y0, 4, 4, p["METAL_L"])               # head
    c.rect(x0 - 1, y0 - 1, 2, 2, p["METAL"])
    c.rect(x0 - 2, y0 + 5, 4, 1, p["ACCENT"])            # quota
    c.rect(x0 - 2, y0 + 1, 1, 3, (0xF0, 0xF4, 0xFA))     # lit edge


def _shield(c, p, cx, side=-1):
    x = cx + 5 * side
    for i, w in enumerate((1, 2, 3, 3, 2)):
        c.rect(x - w, 12 + i * 2, 2 * w + 1, 2, p["ARM_L"] if i < 2 else p["ARM"])
    c.rect(x + 1, 12, 3, 10, p["ARM_D"])
    c.disc(x, 16, 1, p["ACCENT"])


def _bow(c, p, cx, pose, side=1):
    x = cx + 6 * side
    for a in range(-6, 7):
        yy = 13 + int(round(a * 0.9))
        xx = x + int(round(5 * (1 - (a / 6.0) ** 2) ** 0.5))
        c.set(xx, yy, p["WOOD"])
        c.set(xx + 1, yy, p["WOOD_D"])
    c.line(x + 5, 7, x + 5, 19, IVORY)                   # string
    for i in range(3):                                   # quiver on the back
        c.rect(cx - 6 + i, 12 - i, 1, 6, p["WOOD_D"])
        c.set(cx - 6 + i, 11 - i, p["ACCENT"])


def _staff(c, p, cx, pose, side=1):
    x = cx + 6 * side
    c.rect(x, 4, 2, 19, p["WOOD"])
    c.rect(x, 4, 1, 19, p["WOOD_D"])
    c.disc(x, 3, 2, WATER_HI)
    c.disc(x, 3, 1, (0xE8, 0xF4, 0xFF))
    c.set(x + 2, 1, WATER_HI)


WEAPONS = {"sword": _sword, "axe": _axe, "lance": _lance, "bow": _bow,
           "staff": _staff}

CLASSES = {
    "sword":  {"crest": "comb",  "weapon": "sword",  "cape": False},
    "axe":    {"crest": "horns", "weapon": "axe",    "cape": True},
    "lance":  {"crest": "plume", "weapon": "lance",  "shield": True},
    "bow":    {"crest": "none",  "weapon": "bow",    "hair": True},
    "mage":   {"crest": "hood",  "weapon": "staff",  "robe": True},
}
POSES = ("idle", "step", "attack")


def build_unit(cls, pose, p):
    c = Raster(UW, UH)
    opt = CLASSES[cls]
    cx = 7 if cls == "bow" else 8
    bob = 1 if pose == "step" else 0
    _head(c, p, cx, opt)
    y = _torso(c, p, cx, opt, bob)
    _legs(c, p, cx, y, pose, opt)
    # rear arm first so the weapon arm draws over it
    c.rect(cx - 6, 12 + bob, 2, 6, p["ARM_DD"])
    c.rect(cx - 6, 17 + bob, 2, 2, p["LEATHER_D"])
    if opt.get("shield"):
        _shield(c, p, cx)
    WEAPONS[opt["weapon"]](c, p, cx, pose)
    c.rect(cx + 4, 12 + bob, 2, 5, p["ARM_L"])           # weapon arm
    c.rect(cx + 4, 16 + bob, 2, 2, p["SKIN"])
    if pose == "attack":                                 # slash arc
        for i, (dx, dy) in enumerate(((9, 4), (10, 6), (11, 9), (11, 12))):
            c.set(cx + dx - 8, dy, IVORY)
            c.set(cx + dx - 8, dy + 1, mix(IVORY, LINE, 0.25))
    c.outline()
    return c


def build_fox(pose):
    """The reference's companion animal: orange, white-tipped tail, dark legs."""
    c = Raster(UW, 16)
    body = (0xD8, 0x74, 0x2A)
    lift = 1 if pose == "step" else 0
    c.ellipse(8, 10, 5, 3, body)
    c.rect(3, 8, 10, 5, body)
    c.rect(11, 6, 4, 5, body)                            # head
    c.rect(14, 7, 2, 2, (0xF0, 0xE8, 0xE0))              # muzzle
    c.rect(12, 3, 2, 4, body)                            # ears
    c.rect(15, 4, 1, 3, body)
    c.set(13, 8, LINE)                                   # eye
    c.rect(2, 6, 4, 4, (0xF0, 0xE8, 0xE0))               # tail, white tip
    c.rect(4, 8, 3, 3, body)
    for x in (5, 8, 11, 13):                             # legs
        c.rect(x, 12 - lift, 2, 4 - lift, (0x3A, 0x2A, 0x24))
    c.rect(3, 12, 11, 1, shade(body, 0.72))
    c.outline()
    return c


def build_cavalry(pose, p):
    """24x26 mounted knight. The first pass tinted the horse with the army
    colour, so rider and mount merged into one blob; here the horse is always a
    bay and the army shows through the caparison and the rider's plate."""
    c = Raster(CW, CH)
    lift = 1 if pose == "step" else 0
    c.ellipse(10, 17, 8, 4, HORSE)                       # barrel
    c.rect(3, 14, 15, 6, HORSE)
    c.rect(3, 14, 15, 2, HORSE_L)
    c.rect(3, 18, 15, 2, HORSE_D)
    c.disc(4, 16, 3, HORSE)                              # chest
    c.disc(16, 16, 3, HORSE)                             # rump
    c.line(16, 14, 20, 7, HORSE, 3)                      # neck
    c.line(16, 14, 20, 7, HORSE_D, 1)
    c.rect(18, 4, 5, 4, HORSE)                           # head
    c.rect(21, 5, 2, 3, HORSE_L)                         # muzzle
    c.rect(21, 7, 2, 1, HORSE_DD)
    c.rect(18, 2, 2, 3, HORSE_D)                         # ears
    c.set(20, 5, LINE)                                   # eye
    c.line(17, 5, 19, 12, HORSE_DD)                      # mane
    c.rect(2, 13, 2, 6, HORSE_DD)                        # tail
    c.rect(1, 16, 2, 5, HORSE_DD)
    for x in (4, 8, 13, 17):                             # legs
        c.rect(x, 19 - lift, 2, 6 - lift, HORSE_DD)
        c.rect(x, 24, 2, 2, (0x2A, 0x20, 0x1E))
    c.rect(6, 14, 8, 6, p["CLOTH"])                      # caparison
    c.rect(6, 14, 8, 1, p["ACCENT"])
    c.rect(12, 15, 2, 5, p["CLOTH_D"])
    for x in (7, 10):                                    # trim notch
        c.set(x, 19, p["ACCENT"])
    rx = 8                                               # rider
    _head_at(c, p, rx, 1)
    c.rect(rx - 3, 7, 7, 6, p["ARM"])
    c.rect(rx - 3, 7, 2, 6, p["ARM_L"])
    c.rect(rx + 2, 7, 2, 6, p["ARM_D"])
    c.rect(rx - 4, 6, 2, 3, p["ARM_L"])                  # pauldron
    c.rect(rx - 5, 8, 2, 5, p["ARM_DD"])                 # rear arm
    c.rect(rx - 3, 12, 8, 2, p["LEATHER"])               # saddle
    c.rect(rx + 3, 12, 2, 2, p["ACCENT"])
    c.rect(rx + 1, 13, 3, 6, p["ARM_DD"])                # rider leg
    c.rect(rx + 1, 18, 3, 1, p["LEATHER_D"])
    y0 = 0 if pose == "attack" else 2                    # couched lance
    c.line(rx + 3, 8 + y0, 22, 1 + y0, p["WOOD"], 2)
    c.line(rx + 3, 9 + y0, 22, 2 + y0, p["WOOD_D"])
    c.rect(20, y0, 4, 3, p["METAL_L"])
    c.rect(22, y0 - 1, 2, 2, p["METAL"])
    c.rect(rx + 2, 7 + y0, 3, 2, p["SKIN"])              # rein hand
    c.outline()
    return c


def _head_at(c, p, cx, top):
    """Small helmet + face at an arbitrary origin (cavalry rider)."""
    c.rect(cx - 2, top, 5, 3, p["ARM"])
    c.rect(cx - 2, top, 2, 3, p["ARM_L"])
    c.rect(cx + 2, top, 1, 3, p["ARM_D"])
    c.rect(cx - 1, top + 3, 4, 2, p["SKIN"])
    c.set(cx + 1, top + 4, LINE)
    c.rect(cx - 1, top - 2, 3, 2, p["ACCENT"])           # plume


UNITS = []
for _cls, _opt in CLASSES.items():
    for _army in ("blue", "red"):
        for _pose in POSES:
            UNITS.append(("%s_%s_%s" % (_army, _cls, _pose),
                          lambda c=_cls, a=_army, po=_pose: build_unit(
                              c, po, ARMIES[a])))
for _army in ("blue", "red"):
    for _pose in POSES:
        UNITS.append(("%s_cav_%s" % (_army, _pose),
                      lambda a=_army, po=_pose: build_cavalry(po, ARMIES[a])))
for _i, _pose in enumerate(("idle", "step")):
    UNITS.append(("fox_%s" % _pose, lambda po=_pose: build_fox(po)))


TERRAIN = [
    ("grass0", tile_grass, (0,)),
    ("grass1", tile_grass, (1,)),
    ("grass2", tile_grass, (2,)),
    ("grass3", tile_grass, (3,)),
    ("road0", tile_road, (0,)),
    ("road1", tile_road, (1,)),
    ("sand", tile_sand, ()),
    ("water0", tile_water, (0,)),
    ("water1", tile_water, (1,)),
    ("water2", tile_water, (2,)),
    ("shore", tile_shore, ()),
    ("forest0", tile_forest, (0,)),
    ("forest1", tile_forest, (1,)),
    ("forest2", tile_forest, (2,)),
    ("mount0", tile_mountain, (0,)),
    ("mount1", tile_mountain, (1,)),
    ("peak", tile_peak, ()),
    ("house", tile_house, ()),
    ("keep", tile_keep, ()),
    ("tent", tile_tent, ()),
    ("rubble", tile_rubble, ()),
    ("bridge", tile_bridge, ()),
]


# ---- army crests -----------------------------------------------------------
# 8x8 shield badges for the action popup, HP bars and the splash emblem. The
# popup is only ~20 px tall, so these read at 1:1 without any detail loss.
def crest(field, border, device):
    c = Raster(8, 8)
    for y, w in ((0, 3), (1, 3), (2, 3), (3, 3), (4, 2), (5, 2), (6, 1), (7, 0)):
        c.rect(4 - w - 1, y, 2 * w + 2, 1, field)
    for y, w in ((0, 3), (1, 3), (2, 3), (3, 3), (4, 2), (5, 2), (6, 1), (7, 0)):
        c.set(4 - w - 1, y, border)
        c.set(4 + w, y, border)
    c.rect(0, 0, 8, 1, border)
    c.rect(1, 7, 6, 1, border)
    # Upright sword: the blade has to reach the shield's top edge or the whole
    # device reads as a plain letter T once it is blown up 5x on the splash.
    c.rect(3, 1, 2, 4, device)
    c.rect(2, 5, 4, 1, device)
    c.rect(3, 6, 2, 1, shade(device, 0.72))
    c.set(3, 6, shade(device, 0.55))
    c.outline()
    return c


CRESTS = [
    ("blue", lambda: crest(ARMIES["blue"]["ARM"], GOLD_C, IVORY)),
    ("red",  lambda: crest(ARMIES["red"]["ARM"], (0xB6, 0xB2, 0xA6), IVORY)),
]


def build_units():
    return [(name, fn()) for name, fn in UNITS] + \
           [("crest_%s" % n, fn()) for n, fn in CRESTS]


def write_sheet(items, path, scale=5, cols=6, cell=None):
    """Contact sheet judged by eye; `cell` is (w, h) or None to use each raster."""
    from PIL import Image, ImageDraw
    cell = cell or (TILE, TILE)
    rows = (len(items) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * cell[0] * scale + (cols + 1) * 6,
                              rows * (cell[1] * scale + 12) + 12), (24, 26, 34))
    d = ImageDraw.Draw(sheet)
    for i, (name, r) in enumerate(items):
        img = Image.new("RGB", (r.w, r.h), (0, 0, 0))
        px = img.load()
        for y in range(r.h):
            for x in range(r.w):
                px[x, y] = r.get(x, y) or (36, 38, 48)
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


def emit_header(tiles, sprites):
    L = ["/* Generated by tools/generate_tacticsvanguard_assets.py - do not edit.\n"
         " *\n"
         " * TacticsVanguard2D art. Terrain is 16x16 RGB565 baked opaque; units and\n"
         " * army crests carry a 1-bit visibility mask (MSB first, row-padded).\n"
         " * Colours are sampled from the reference frame's histogram. */\n",
         "#ifndef VXPE_TACTICSVANGUARD_ASSETS_GEN_H\n"
         "#define VXPE_TACTICSVANGUARD_ASSETS_GEN_H\n\n"
         "#include <stdint.h>\n\n"
         "#define TV_TILE 16\n"
         "#define TV_UNIT_W 16\n"
         "#define TV_UNIT_H 26\n"
         "#define TV_CAV_W 24\n\n"
         "/* A masked sprite in this file's tables. w is a multiple of 8, so the\n"
         " * mask stride is w/8 bytes with no leftover bits. */\n"
         "typedef struct TvSprite {\n"
         "    const uint16_t* px;\n"
         "    const uint8_t* mask;\n"
         "    uint8_t w;\n"
         "    uint8_t h;\n"
         "} TvSprite;\n"]

    for name, r in tiles:
        px, _ = r.bake()
        L.append("static const uint16_t tv_tile_%s[TV_TILE * TV_TILE] = {" % name)
        for j in range(0, len(px), 10):
            L.append("  " + ", ".join("0x%04X" % v for v in px[j:j + 10]) + ",")
        L.append("};\n")

    for name, r in sprites:
        px, mk = r.bake()
        L.append("static const uint16_t tv_us_%s[%d] = {  /* %dx%d */"
                 % (name, len(px), r.w, r.h))
        for j in range(0, len(px), 10):
            L.append("  " + ", ".join("0x%04X" % v for v in px[j:j + 10]) + ",")
        L.append("};")
        L.append("static const uint8_t tv_um_%s[%d] = {" % (name, len(mk)))
        for j in range(0, len(mk), 12):
            L.append("  " + ", ".join("0x%02X" % v for v in mk[j:j + 12]) + ",")
        L.append("};\n")

    L.append("enum {")
    for i, (name, _) in enumerate(tiles):
        L.append("    TV_T_%s = %d," % (name.upper(), i))
    L.append("    TV_NTILE = %d\n};\n" % len(tiles))
    L.append("static const uint16_t* TV_TILES[TV_NTILE] = {")
    L.append("    " + ", ".join("tv_tile_%s" % n for n, _ in tiles) + "};\n")

    L.append("enum {")
    for i, (name, _) in enumerate(sprites):
        L.append("    TV_US_%s = %d," % (name.upper(), i))
    L.append("    TV_NSPRITE = %d\n};\n" % len(sprites))
    L.append("static const TvSprite TV_SPRITES[TV_NSPRITE] = {")
    for name, r in sprites:
        L.append("    { tv_us_%s, tv_um_%s, %d, %d }," % (name, name, r.w, r.h))
    L.append("};\n")
    L.append("#endif /* VXPE_TACTICSVANGUARD_ASSETS_GEN_H */")

    folder = os.path.dirname(OUT_HEADER)
    if folder:
        os.makedirs(folder, exist_ok=True)
    with open(OUT_HEADER, "w", newline="\n") as f:
        f.write("\n".join(L) + "\n")
    total = sum(len(r.bake()[0]) * 2 + len(r.bake()[1]) for _, r in tiles)
    total += sum(len(r.bake()[0]) * 2 + len(r.bake()[1]) for _, r in sprites)
    print("header ->", OUT_HEADER, "(%d bytes, %d tiles, %d sprites)"
          % (total, len(tiles), len(sprites)))


def main():
    tiles = [(name, fn(*args)) for name, fn, args in TERRAIN]
    sprites = build_units()
    if "--preview" not in sys.argv:
        emit_header(tiles, sprites)
    write_sheet(tiles, PREVIEW, scale=5, cols=6)
    write_sheet([s for s in sprites if not s[0].startswith("crest_")],
                UNITS_PREVIEW, scale=4, cols=6, cell=(CW, UH))
    write_sheet([s for s in sprites if s[0].startswith("crest_")],
                CREST_PREVIEW, scale=8, cols=4, cell=(8, 8))


if __name__ == "__main__":
    main()
