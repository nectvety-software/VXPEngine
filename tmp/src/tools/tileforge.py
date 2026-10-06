"""Procedural tilesheet forge — grid-exact terrain atlases in several art styles.

    python -m src.tools.tileforge                          # sheets/ + demo renders
    python -m src.tools.tileforge --out sheets --seed 7
    python -m src.tools.tileforge --only pixel,oil --no-demo

Every atlas is laid out on an exact CELL grid with blank separator columns, so
`TileSheet.open(cell="auto")` and the slicer skill work on them unchanged.
"""

from __future__ import annotations

import argparse
import math
import random
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

CELL = 32
COLS, ROWS = 12, 6
GAP_COLS = (4, 8)
SLOTS = (COLS - len(GAP_COLS)) * ROWS
STYLES = ("natural", "pixel", "oil")

# material -> (base RGB, lightness spread)
MATERIALS: dict[str, tuple[tuple[int, int, int], float]] = {
    "grass": ((86, 148, 62), .34), "grass_lit": ((112, 176, 74), .30),
    "grass_dim": ((62, 116, 50), .30), "moss": ((104, 140, 58), .28),
    "dirt": ((122, 92, 60), .28), "mud": ((86, 68, 52), .24),
    "sand": ((216, 192, 136), .22), "sand_wet": ((184, 158, 110), .22),
    "clay": ((176, 104, 72), .26), "strata": ((150, 116, 86), .28),
    "stone": ((134, 138, 146), .26), "stone_dark": ((92, 96, 104), .24),
    "ash": ((74, 72, 76), .22), "lava": ((214, 96, 34), .40),
    "snow": ((238, 244, 252), .12), "ice": ((168, 208, 232), .18),
    "water": ((56, 116, 178), .30), "water_deep": ((26, 66, 124), .26),
    "swamp": ((72, 96, 58), .30), "tundra": ((148, 158, 132), .24),
    "leaf": ((66, 132, 58), .34), "leaf_lit": ((104, 168, 66), .30),
    "pine": ((44, 102, 80), .30), "pine_lit": ((66, 132, 92), .28),
    "snow_pine": ((120, 150, 140), .22), "autumn": ((196, 120, 44), .32),
    "bark": ((104, 72, 48), .26), "reed": ((120, 150, 70), .30),
    "flower_r": ((214, 80, 80), .28), "flower_y": ((240, 204, 80), .26),
    "flower_w": ((236, 240, 248), .16),
}

GRASSY = {"grass", "grass_lit", "grass_dim", "moss", "tundra", "reed"}
WATERY = {"water", "water_deep", "swamp", "ice"}
ROCKY = {"stone", "stone_dark", "ash", "strata", "lava"}
SNOWY = {"snow"}

# low (wet) -> high (cold) so a demo map bands into lakes, shores, plains, peaks
ELEVATION = ("water_deep", "water", "swamp", "mud", "ice", "lava", "sand_wet", "sand",
             "clay", "grass", "grass_lit", "grass_dim", "reed", "moss", "tundra",
             "dirt", "strata", "stone", "stone_dark", "ash", "snow")

BAYER = np.array([[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]],
                 np.float32) / 16.0


@dataclass
class Ctx:
    rng: random.Random
    gen: np.random.Generator
    palette: list = field(default_factory=list)


# --------------------------------------------------------------------- colour


def ramp(base, steps, spread):
    out = []
    for i in range(steps):
        t = -1.0 + 2.0 * i / max(1, steps - 1)
        out.append(shade(base, 1.0 + t * spread))
    return out


def shade(rgb, f):
    return tuple(max(0, min(255, int(round(c * f)))) for c in rgb)


def opaque(rgb):
    return (int(rgb[0]), int(rgb[1]), int(rgb[2]), 255)


# -------------------------------------------------------------------- geometry


def _texture(d, ctx, mat, cols, box):
    x0, y0, x1, y1 = box
    dark, light = cols[0], cols[-1]
    rnd = ctx.rng
    if mat in GRASSY:
        for _ in range(26):
            x = rnd.randint(x0 + 1, max(x0 + 1, x1 - 2))
            y = rnd.randint(min(y0 + 3, y1 - 1), y1 - 1)
            d.line([x, y, x + rnd.randint(-1, 1), y - rnd.randint(2, 4)],
                   fill=opaque(light))
    elif mat in WATERY:
        for _ in range(9):
            y = rnd.randint(y0, max(y0, y1 - 3))
            x = rnd.randint(x0, max(x0, x1 - 9))
            ln = rnd.randint(4, 9)
            d.line([x, y, x + ln, y], fill=opaque(light))
            d.line([x + 1, y + 2, x + ln - 2, y + 2], fill=opaque(dark))
    elif mat in SNOWY:
        for _ in range(7):
            y = rnd.randint(y0, y1 - 1)
            d.line([x0, y, x1 - 1, y + rnd.randint(-1, 1)], fill=opaque(cols[-2]))
    else:
        for _ in range(44):
            d.point((rnd.randint(x0, x1 - 1), rnd.randint(y0, y1 - 1)),
                    fill=opaque(rnd.choice([dark, light])))
        for _ in range(6):
            r = rnd.randint(1, 2)
            x, y = rnd.randint(x0 + 1, x1 - 2), rnd.randint(y0 + 1, y1 - 2)
            d.ellipse([x - r, y - r, x + r, y + r], fill=opaque(dark))


def _ground(img, d, ctx, mat, texture=True):
    base, spread = MATERIALS[mat]
    cols = ramp(base, 5, spread)
    ctx.palette += cols
    x0, y0, x1, y1 = 0, 0, CELL, CELL
    d.rectangle([x0, y0, x1 - 1, y1 - 1], fill=opaque(cols[2]))
    for _ in range(18):
        r = ctx.rng.randint(2, 6)
        cx, cy = ctx.rng.randint(x0, x1 - 1), ctx.rng.randint(y0, y1 - 1)
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=opaque(ctx.rng.choice(cols[:4])))
    if texture:
        _texture(d, ctx, mat, cols, (x0, y0, x1, y1))
    return cols


def _blob(d, cx, cy, rx, ry, fill, ring=1):
    line = opaque(shade(fill, .30))
    for dx in range(-ring, ring + 1):
        for dy in range(-ring, ring + 1):
            if dx or dy:
                d.ellipse([cx - rx + dx, cy - ry + dy, cx + rx + dx, cy + ry + dy], fill=line)
    d.ellipse([cx - rx, cy - ry, cx + rx, cy + ry], fill=opaque(fill))
    hx0, hy0, hx1, hy1 = cx - rx + 2, cy - ry + 1, cx - 1, cy - ry + 4
    if hx1 >= hx0 and hy1 >= hy0:
        d.ellipse([hx0, hy0, hx1, hy1], fill=opaque(shade(fill, 1.26)))


def _poly(d, pts, fill, ring=1):
    line = opaque(shade(fill, .30))
    for dx in range(-ring, ring + 1):
        for dy in range(-ring, ring + 1):
            if dx or dy:
                d.polygon([(x + dx, y + dy) for x, y in pts], fill=line)
    d.polygon(pts, fill=opaque(fill))


def _trunk(d, x, top, bottom, wide, mat="bark"):
    cols = ramp(MATERIALS[mat][0], 5, MATERIALS[mat][1])
    d.rectangle([x - wide, top, x + wide, bottom], fill=opaque(cols[0]))
    d.rectangle([x - wide + 1, top, x + wide - 1, bottom], fill=opaque(cols[2]))
    d.line([x - 1, top + 1, x - 1, bottom - 1], fill=opaque(cols[4]))


def _tree(img, d, ctx, leaf, soil):
    _ground(img, d, ctx, soil)
    cols = ramp(MATERIALS[leaf][0], 5, MATERIALS[leaf][1])
    ctx.palette += cols
    _trunk(d, 16, 18, 31, 2)
    _blob(d, 16, 12, 11, 9, cols[2])
    _blob(d, 8, 16, 6, 5, cols[1])
    _blob(d, 24, 16, 6, 5, cols[1])
    _blob(d, 13, 8, 5, 4, cols[3])


def _pine(img, d, ctx, leaf, soil):
    _ground(img, d, ctx, soil)
    cols = ramp(MATERIALS[leaf][0], 5, MATERIALS[leaf][1])
    ctx.palette += cols
    _trunk(d, 16, 24, 31, 2)
    _poly(d, [(16, 2), (24, 13), (20, 13), (27, 22), (19, 22), (19, 26),
              (13, 26), (13, 22), (5, 22), (12, 13), (8, 13)], cols[2])
    d.polygon([(16, 3), (21, 12), (13, 12)], fill=opaque(cols[4]))


def _dead(img, d, ctx, soil):
    _ground(img, d, ctx, soil)
    cols = ramp(MATERIALS["bark"][0], 5, MATERIALS["bark"][1])
    ctx.palette += cols
    _trunk(d, 16, 8, 31, 2)
    for x0, y0, x1, y1 in ((16, 12, 8, 4), (16, 15, 24, 7), (16, 20, 9, 15),
                           (16, 22, 25, 17), (16, 9, 19, 2)):
        d.line([x0, y0, x1, y1], fill=opaque(cols[1]), width=2)
        d.line([x0, y0, x1, y1], fill=opaque(cols[3]))


def _bush(img, d, ctx, leaf, soil):
    _ground(img, d, ctx, soil)
    cols = ramp(MATERIALS[leaf][0], 5, MATERIALS[leaf][1])
    ctx.palette += cols
    _blob(d, 11, 22, 7, 6, cols[1])
    _blob(d, 21, 22, 7, 6, cols[2])
    _blob(d, 16, 17, 7, 6, cols[3])


def _flower(img, d, ctx, petal, soil):
    _ground(img, d, ctx, soil)
    cols = ramp(MATERIALS[petal][0], 5, MATERIALS[petal][1])
    ctx.palette += cols
    for _ in range(ctx.rng.randint(2, 4)):
        cx, cy = ctx.rng.randint(6, CELL - 7), ctx.rng.randint(7, CELL - 6)
        d.line([cx, cy + 3, cx, cy + 8], fill=opaque(shade(MATERIALS["grass"][0], .8)))
        for a in range(0, 360, 72):
            px = cx + int(round(2.7 * math.cos(math.radians(a))))
            py = cy + int(round(2.7 * math.sin(math.radians(a))))
            d.ellipse([px - 2, py - 2, px + 2, py + 2], fill=opaque(cols[3]))
        d.ellipse([cx - 1, cy - 1, cx + 1, cy + 1], fill=opaque((246, 220, 120)))


def _rock(img, d, ctx, stone, soil):
    _ground(img, d, ctx, soil)
    cols = ramp(MATERIALS[stone][0], 5, MATERIALS[stone][1])
    ctx.palette += cols
    cx = ctx.rng.randint(13, 19)
    cy = ctx.rng.randint(17, 21)
    _poly(d, [(cx - 10, cy + 7), (cx - 7, cy - 4), (cx, cy - 8), (cx + 8, cy - 3),
              (cx + 10, cy + 7)], cols[2])
    d.polygon([(cx - 7, cy - 4), (cx, cy - 8), (cx + 4, cy - 3), (cx - 3, cy)],
              fill=opaque(cols[4]))
    d.polygon([(cx - 10, cy + 7), (cx - 3, cy + 1), (cx + 10, cy + 7)],
              fill=opaque(cols[0]))


def _stump(img, d, ctx, mat, soil):
    _ground(img, d, ctx, soil)
    cols = ramp(MATERIALS[mat][0], 5, MATERIALS[mat][1])
    ctx.palette += cols
    _blob(d, 16, 22, 8, 6, cols[1], ring=1)
    for r in (5, 3, 1):
        d.ellipse([16 - r, 22 - r // 2 - 1, 16 + r, 22 + r // 2 + 1],
                  outline=opaque(shade(cols[0], .9)))


def _log(img, d, ctx, mat, soil):
    _ground(img, d, ctx, soil)
    cols = ramp(MATERIALS[mat][0], 5, MATERIALS[mat][1])
    ctx.palette += cols
    d.rounded_rectangle([5, 17, 27, 25], 4, fill=opaque(cols[2]),
                        outline=opaque(shade(cols[2], .3)))
    d.line([7, 20, 25, 20], fill=opaque(cols[4]))
    _blob(d, 26, 21, 3, 4, cols[1], ring=1)
    d.ellipse([25, 19, 27, 23], outline=opaque(shade(cols[0], .8)))


def _reed(img, d, ctx, leaf, water):
    _ground(img, d, ctx, water)
    cols = ramp(MATERIALS[leaf][0], 5, MATERIALS[leaf][1])
    ctx.palette += cols
    for _ in range(7):
        x = ctx.rng.randint(4, CELL - 5)
        h = ctx.rng.randint(12, 22)
        d.line([x, 30, x + ctx.rng.randint(-2, 2), 30 - h], fill=opaque(shade(cols[1], .55)),
               width=2)
        d.line([x, 30, x + ctx.rng.randint(-2, 2), 30 - h], fill=opaque(cols[2]))
        d.ellipse([x - 2, 28 - h, x + 2, 32 - h], fill=opaque(cols[4]))


def _cactus(img, d, ctx, leaf, sand):
    _ground(img, d, ctx, sand)
    cols = ramp(MATERIALS[leaf][0], 5, MATERIALS[leaf][1])
    ctx.palette += cols
    _poly(d, [(13, 30), (13, 9), (15, 5), (18, 5), (20, 9), (20, 30)], cols[2])
    _poly(d, [(20, 22), (24, 22), (25, 18), (25, 13), (23, 13), (22, 17), (20, 17)], cols[1])
    _poly(d, [(13, 25), (9, 25), (8, 21), (8, 17), (10, 17), (11, 20), (13, 20)], cols[1])
    d.line([16, 8, 16, 29], fill=opaque(cols[4]))


def _pebble(img, d, ctx, stone, soil):
    _ground(img, d, ctx, soil)
    cols = ramp(MATERIALS[stone][0], 5, MATERIALS[stone][1])
    ctx.palette += cols
    for _ in range(ctx.rng.randint(4, 7)):
        _blob(d, ctx.rng.randint(6, CELL - 7), ctx.rng.randint(10, CELL - 6),
              ctx.rng.randint(2, 4), ctx.rng.randint(2, 3), ctx.rng.choice(cols), ring=1)


def _mushroom(img, d, ctx, cap, soil):
    _ground(img, d, ctx, soil)
    cols = ramp(MATERIALS[cap][0], 5, MATERIALS[cap][1])
    ctx.palette += cols
    for _ in range(ctx.rng.randint(2, 3)):
        cx = ctx.rng.randint(7, CELL - 8)
        cy = ctx.rng.randint(16, CELL - 8)
        d.rectangle([cx - 1, cy, cx + 1, cy + 5], fill=opaque((232, 224, 206)))
        _blob(d, cx, cy - 1, 5, 4, cols[3], ring=1)
        d.point((cx - 2, cy - 2), fill=opaque(cols[4]))
        d.point((cx + 2, cy - 1), fill=opaque(cols[4]))


def _vent(img, d, ctx, mat):
    cols = ramp(MATERIALS[mat][0], 5, MATERIALS[mat][1])
    ctx.palette += cols
    _ground(img, d, ctx, "ash")
    _poly(d, [(8, 30), (13, 18), (19, 18), (24, 30)], cols[0])
    d.polygon([(13, 18), (19, 18), (16, 12)], fill=opaque(cols[4]))
    for _ in range(5):
        x = ctx.rng.randint(12, 20)
        d.line([x, 14, x + ctx.rng.randint(-4, 4), ctx.rng.randint(1, 8)],
               fill=opaque(cols[3]), width=2)


def _icicle(img, d, ctx, mat, soil):
    cols = ramp(MATERIALS[mat][0], 5, MATERIALS[mat][1])
    ctx.palette += cols
    _ground(img, d, ctx, soil)
    d.rectangle([0, 0, CELL - 1, 6], fill=opaque(cols[3]))
    for x in range(2, CELL - 3, 4):
        h = ctx.rng.randint(6, 18)
        _poly(d, [(x, 5), (x + 3, 5), (x + 1, 5 + h)], cols[2], ring=1)


GEOM = {"tree": _tree, "pine": _pine, "dead": _dead, "bush": _bush, "shrub": _bush,
        "flower": _flower, "rock": _rock, "stump": _stump, "log": _log, "reed": _reed,
        "cactus": _cactus, "pebble": _pebble, "mushroom": _mushroom, "fern": _bush,
        "vent": _vent, "icicle": _icicle}


def _geom(kind, ctx):
    img = Image.new("RGBA", (CELL, CELL), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    tag, *args = kind.split(":")
    if tag == "g":
        _ground(img, d, ctx, args[0], texture=False)
    elif tag == "t":
        _ground(img, d, ctx, args[0])
    elif tag == "x":
        a, b = args
        img = _geom(f"t:{a}", ctx)
        other = _geom(f"t:{b}", ctx)
        phase = ctx.rng.uniform(0, math.tau)
        edge = [(CELL * 0.55 + math.sin(y * 0.42 + phase) * 4.0, float(y))
                for y in range(-2, CELL + 3)]
        mask = Image.new("L", (CELL, CELL), 0)
        ImageDraw.Draw(mask).polygon([(CELL + 4, -4)] + edge + [(CELL + 4, CELL + 4)],
                                     fill=255)
        img.paste(other, (0, 0), mask)
    elif tag == "vent":
        GEOM[tag](img, d, ctx, args[0])
    elif tag == "icicle":
        GEOM[tag](img, d, ctx, args[0], args[1])
    elif tag == "dead":
        GEOM[tag](img, d, ctx, args[0])
    else:
        GEOM[tag](img, d, ctx, args[0], args[1])
    return img


# --------------------------------------------------------------- style passes


def _keep_alpha(img, before):
    arr = np.asarray(img).copy()
    arr[:, :, 3] = np.asarray(before)[:, :, 3]
    return Image.fromarray(arr, "RGBA")


def _pass_natural(img, ctx):
    src = np.asarray(img)
    noise = ctx.gen.integers(-9, 10, (CELL, CELL, 1)).astype(np.int16)
    rgb = np.clip(src[:, :, :3].astype(np.int16) + noise, 0, 255).astype(np.uint8)
    out = Image.fromarray(np.dstack([rgb, src[:, :, 3]]), "RGBA")
    return _keep_alpha(out.filter(ImageFilter.GaussianBlur(0.4)), src)


def _pass_pixel(img, ctx):
    src = np.asarray(img)
    pal = _palette(ctx)
    rgb = src[:, :, :3].astype(np.float32)
    step = _spread(pal)
    tile = np.tile(BAYER, (CELL // 4 + 1, CELL // 4 + 1))[:CELL, :CELL]
    shifted = np.clip(rgb + (tile - 0.5)[:, :, None] * step * 1.35, 0, 255)
    idx = ((shifted[:, :, None, :] - pal[None, None, :, :]) ** 2).sum(3).argmin(2)
    arr = src.copy()
    arr[:, :, :3] = pal[idx]
    return Image.fromarray(arr, "RGBA")


def _pass_oil(img, ctx):
    src = np.asarray(img)
    strokes = Image.new("RGBA", (CELL, CELL), (0, 0, 0, 0))
    sd = ImageDraw.Draw(strokes)
    solid = np.argwhere(src[:, :, 3] > 200)
    if len(solid) < 8:
        return img
    for _ in range(150):
        y, x = solid[ctx.gen.integers(len(solid))]
        f = ctx.rng.uniform(.76, 1.26)
        r, g, b = src[y, x, :3]
        col = (min(255, int(r * f)), min(255, int(g * f)), min(255, int(b * f)), 110)
        ang = ctx.rng.uniform(0, math.pi)
        ln = ctx.rng.uniform(3, 9) / 2
        sd.line([x - math.cos(ang) * ln, y - math.sin(ang) * ln,
                 x + math.cos(ang) * ln, y + math.sin(ang) * ln],
                fill=col, width=ctx.rng.choice((2, 2, 3)))
    out = Image.alpha_composite(img, strokes)
    arr = np.asarray(out).astype(np.float32)
    yy, xx = np.mgrid[0:CELL, 0:CELL].astype(np.float32)
    weave = 1.0 + .05 * np.sin(xx * math.pi / 1.6) + .05 * np.sin(yy * math.pi / 1.6)
    arr[:, :, :3] = np.clip(arr[:, :, :3] * weave[:, :, None], 0, 255)
    blended = Image.fromarray(arr.astype(np.uint8), "RGBA")
    return _keep_alpha(blended.filter(ImageFilter.GaussianBlur(0.65)), src)


def _palette(ctx, cap=16):
    uniq = sorted({c for c in ctx.palette},
                  key=lambda c: 0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2])
    if len(uniq) > cap:
        uniq = uniq[::(len(uniq) + cap - 1) // cap][:cap]
    return np.array(uniq, np.uint8)


def _spread(pal):
    if len(pal) < 2:
        return 24.0
    a = pal.astype(np.float32)
    dist = np.linalg.norm(a[:, None, :] - a[None, :, :], axis=2)
    np.fill_diagonal(dist, np.inf)
    return float(dist.min(1).mean())


PASSES = {"natural": _pass_natural, "pixel": _pass_pixel, "oil": _pass_oil}


# --------------------------------------------------------------------- sheets


def _grid(kinds):
    out, i = [], 0
    for _ in range(ROWS):
        row = []
        for c in range(COLS):
            if c in GAP_COLS:
                row.append("blank")
            else:
                row.append(kinds[i] if i < len(kinds) else "blank")
                i += 1
        out.append(row)
    return out


def build(style, kinds, name, seed):
    grid = _grid(kinds)
    atlas = Image.new("RGBA", (COLS * CELL, ROWS * CELL), (0, 0, 0, 0))
    for r, row in enumerate(grid):
        for c, kind in enumerate(row):
            if kind == "blank":
                continue
            ctx = Ctx(random.Random(f"{seed}|{name}|{r}|{c}"),
                      np.random.default_rng([seed, r, c, 0]))
            cell = PASSES[style](_geom(kind, ctx), ctx)
            atlas.paste(cell, (c * CELL, r * CELL))
    return atlas, grid


def _terrain_kinds():
    kinds = []
    for g in ("water_deep", "water", "grass", "grass_lit", "grass_dim", "moss", "dirt",
              "mud", "sand", "sand_wet", "stone", "snow"):
        kinds += [f"g:{g}", f"t:{g}"]
    kinds += ["x:grass:dirt", "x:grass:stone", "x:sand:water", "x:grass:sand",
              "x:stone:snow", "x:dirt:mud", "x:water:water_deep", "x:grass:moss"]
    kinds += ["tree:leaf:grass", "tree:leaf_lit:grass", "tree:autumn:grass_dim",
              "dead:dirt", "pine:pine:grass_dim", "pine:pine_lit:grass",
              "bush:leaf:grass", "bush:autumn:moss", "bush:pine:dirt",
              "flower:flower_r:grass", "flower:flower_y:grass_lit",
              "flower:flower_w:snow", "rock:stone:grass", "rock:stone_dark:snow",
              "rock:stone:sand", "stump:bark:grass", "reed:reed:water",
              "log:bark:dirt", "pebble:stone:dirt", "mushroom:flower_r:moss",
              "fern:leaf:grass", "icicle:ice:snow", "vent:lava"]
    return kinds


def _biome_kinds():
    kinds = []
    for g in ("lava", "ash", "strata", "swamp", "water", "clay", "ice", "tundra",
              "sand_wet", "mud", "moss"):
        kinds += [f"g:{g}", f"t:{g}"]
    kinds += ["x:lava:ash", "x:strata:clay", "x:swamp:water", "x:ice:snow",
              "x:tundra:grass", "x:tundra:snow", "x:sand:sand_wet", "x:mud:swamp"]
    kinds += ["cactus:leaf:sand", "cactus:pine:clay", "dead:mud", "dead:dirt",
              "reed:reed:swamp", "reed:reed:water", "bush:tundra:snow",
              "shrub:tundra:tundra", "rock:strata:clay", "rock:stone:ash",
              "mushroom:flower_r:moss", "mushroom:flower_y:swamp",
              "fern:leaf:mud", "pebble:ash:lava", "vent:lava", "icicle:ice:snow",
              "pine:snow_pine:snow", "tree:autumn:grass", "flower:flower_w:tundra",
              "log:bark:moss", "stump:bark:swamp", "rock:stone_dark:ash",
              "bush:autumn:grass_dim", "flower:flower_y:mud", "cactus:leaf:sand_wet"]
    return kinds


SHEETS = [("terrain_natural", "natural", _terrain_kinds),
          ("terrain_pixel", "pixel", _terrain_kinds),
          ("terrain_oil", "oil", _terrain_kinds),
          ("biomes_natural", "natural", _biome_kinds)]


# ----------------------------------------------------------------- demo maps


def _field(w, h, scale, seed):
    g = np.random.default_rng(seed).random((math.ceil(h / scale) + 2,
                                            math.ceil(w / scale) + 2))
    im = Image.fromarray((g * 255).astype(np.uint8)).resize((w, h), Image.BICUBIC)
    return np.asarray(im, np.float32) / 255.0


def demo(sheet_path, grid, out_path, seed, w=30, h=18):
    """Fill a map from the sheet's own tiles and export a render + a .terra.json."""
    from ..engine.project import Project
    from ..engine.tilemap import EMPTY

    cells = [(r * COLS + c, grid[r][c]) for r in range(ROWS) for c in range(COLS)
             if grid[r][c] != "blank" and not grid[r][c].startswith("x:")]
    grounds = [(i, k) for i, k in cells if k.split(":")[0] in ("g", "t")]
    picks = [(i, k) for i, k in grounds if k.startswith("t:")] or grounds
    picks.sort(key=lambda p: ELEVATION.index(p[1].split(":")[1])
               if p[1].split(":")[1] in ELEVATION else 99)
    submerged = {n for n, (_, k) in enumerate(picks)
                 if any(s in k for s in ("water", "swamp", "lava", "mud", "ice"))}
    decoys = [i for i, k in cells
              if k.split(":")[0] in ("tree", "pine", "bush", "shrub", "rock", "flower",
                                     "cactus", "reed", "mushroom", "dead", "fern")]

    project = Project.new(sheet_path, w, h, CELL)
    fmap = project.map
    ground = _field(w, h, 9, seed)
    shore = _field(w, h, 5, seed + 11)
    props = _field(w, h, 3, seed + 23)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    edge = np.maximum(xx / max(1, w - 1), yy / max(1, h - 1))
    edge = np.maximum(edge, np.maximum(1 - xx / max(1, w - 1), 1 - yy / max(1, h - 1)))
    ground = ground * (1.0 - 0.5 * edge ** 2)
    bands = np.zeros((h, w), np.int16)

    for y in range(h):
        for x in range(w):
            v = ground[y, x] + 0.25 * (shore[y, x] - 0.5)
            band = min(len(picks) - 1, max(0, int(v * len(picks))))
            bands[y, x] = band
            fmap.paint(x, y, picks[band][0], fmap.layer(0))
    if decoys:
        fmap.add_layer("Props")
        layer = fmap.active_layer
        for y in range(h):
            for x in range(w):
                if props[y, x] < 0.63 or (x + y) % 2 or int(bands[y, x]) in submerged:
                    continue
                near = [layer.get(x + dx, y + dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1)
                        if layer.inside(x + dx, y + dy)]
                if any(t != EMPTY for t in near):
                    continue
                fmap.paint(x, y, decoys[(x * 7 + y * 13) % len(decoys)], layer)
    project.export_png(out_path, scale=2)
    project.save(out_path.with_name(out_path.stem.replace("_demo", "") + ".terra.json"))
    stats = project.stats()
    stats["props"] = len(decoys)
    return stats


# ------------------------------------------------------------------------ cli


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="tileforge", description=__doc__.splitlines()[0])
    ap.add_argument("--out", default="sheets", help="output directory")
    ap.add_argument("--seed", type=int, default=20261006)
    ap.add_argument("--only", default="", help="comma list: natural,pixel,oil,biomes")
    ap.add_argument("--no-demo", action="store_true")
    a = ap.parse_args(argv)

    from ..engine.tilesheet import TileSheet

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    wanted = [w.strip() for w in a.only.split(",") if w.strip()]
    wrote = []
    for name, style, fn in SHEETS:
        if wanted and not any(w in name or w == style for w in wanted):
            continue
        kinds = fn()
        if len(kinds) > SLOTS:
            print(f"ERROR: range: {name} needs {len(kinds)} slots, atlas has {SLOTS}")
            return 1
        atlas, grid = build(style, kinds, name, a.seed)
        path = out / f"{name}.png"
        atlas.save(path)
        sheet = TileSheet.open(path, CELL)
        auto = TileSheet.open(path, "auto")
        note = ""
        if not a.no_demo:
            stats = demo(path, grid, out / f"{name}_demo.png", a.seed)
            note = (f" demo={stats['map']} @{stats['tile_size']} "
                    f"placed={stats['placed']} distinct={stats['distinct_tiles']}")
        print(f"OK  {name:16s} {style:8s} {atlas.width}x{atlas.height} cell={CELL} "
              f"solid={len(sheet.solid)}/{sheet.count} unique={sheet.unique_count()}"
              f"{note}")
        if auto.cell[0] != CELL:
            print(f"    WARN: detect_cell() says {auto.cell[0]} for this atlas; open "
                  f"{name}.terra.json or pass --cell {CELL}")
        wrote.append(path)
    if not wrote:
        print("ERROR: value: nothing matched --only")
        return 1
    print(f"OK  {len(wrote)} sheets -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
