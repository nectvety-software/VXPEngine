"""Draw a reusable skill-effect animation set for the .vpea library.

Seven 32x32 effect loops, each one a self-contained layer an engine can blend
over a character sprite:

  fx_fireball     6 f  60 ms   travelling flame with tail + hot core
  fx_explosion    7 f  55 ms   flash -> ring + 8 shards -> embers
  fx_lightning    5 f  45 ms   jagged bolt, glow, fading sparks
  fx_cast_circle  8 f  70 ms   rotating rune ring + rising motes (loops)
  fx_ice_shards   5 f  60 ms   central burst, 6 splinters flying out
  fx_poison_cloud 6 f  90 ms   billowing gas puffs (loops)
  fx_heal_sparkle 5 f  80 ms   cross + sparkles drifting up (loops)

VPE reserves 0xFFFF as the transparent key, so every highlight goes through
``ms.safe_light`` and never reaches pure white. All randomness is seeded per
effect name, so re-running rewrites byte-identical frames.

Writes (new folders only; existing library files are never touched):
  Documents\\VPE Pixel\\sprite\\effect\\fx_*.vpea
  Documents\\VPE Pixel\\exports\\effect\\<fx>_strip.png
  Documents\\VPE Pixel\\exports\\effect_sheet_all.png   (review sheet)

Run from the repo root:
  python tools/make_effect_anim.py [--only fireball,explosion] [--scale 4]
"""

from __future__ import annotations

import argparse
import math
import random
import sys
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

ROOT = Path(__file__).resolve().parent.parent
for _p in (str(ROOT), str(ROOT / "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import make_knight_anim as ka  # noqa: E402  (reuses band/concat/scaled/draw_sheet)
from make_vqeaf_icons import encode_png_rgba  # noqa: E402
from vpx_editor.gallery import category_dir  # noqa: E402
from vpx_editor.paths import export_dir  # noqa: E402
from vpx_editor.vpea import save_vpea  # noqa: E402
import make_samples as ms  # noqa: E402

Img, rgb, WHITE = ka.Img, ka.rgb, ka.WHITE
SIZE = ka.SIZE
C = SIZE // 2

# ------------------------------------------------------------------- timing
TIMING: Dict[str, Tuple[int, bool]] = {
    "fx_fireball": (60, False),
    "fx_explosion": (55, False),
    "fx_lightning": (45, False),
    "fx_cast_circle": (70, True),
    "fx_ice_shards": (60, False),
    "fx_poison_cloud": (90, True),
    "fx_heal_sparkle": (80, True),
}

# ------------------------------------------------------------------ palettes
RIM = rgb(16, 12, 20)

FIRE = [rgb(196, 44, 20), rgb(232, 96, 28), rgb(247, 158, 56), rgb(247, 214, 120)]
EMBER = rgb(150, 40, 26)
BOLT = rgb(196, 214, 255)
BOLT_HI = ms.safe_light(BOLT, 40)
BOLT_LO = rgb(84, 104, 176)
RUNE = rgb(120, 96, 224)
RUNE_HI = ms.safe_light(RUNE, 52)
RUNE_LO = rgb(58, 44, 120)
ICE = rgb(96, 178, 224)
ICE_HI = ms.safe_light(ICE, 46)
ICE_LO = rgb(40, 92, 140)
GAS = rgb(74, 158, 74)
GAS_HI = ms.safe_light(GAS, 44)
GAS_LO = rgb(34, 88, 48)
HEAL = rgb(56, 200, 150)
HEAL_HI = ms.safe_light(HEAL, 46)
HEAL_LO = rgb(24, 104, 86)


# ------------------------------------------------------------------ helpers
def glow(img: Img, cx: int, cy: int, r: int, colors: Sequence[int]) -> None:
    """Filled disc with radial falloff; colors run hot core -> cool edge."""
    n = len(colors)
    for y in range(cy - r, cy + r + 1):
        for x in range(cx - r, cx + r + 1):
            d = math.hypot(x - cx, y - cy)
            if d <= r:
                img.set(x, y, colors[min(n - 1, int(d / r * n))])


def trail(img: Img, x0: int, y0: int, x1: int, y1: int, c: int, w: int = 1) -> None:
    """Thick line: the antialiased look pixel art engines expect from a sprite."""
    img.line(x0, y0, x1, y1, c)
    if w > 1:
        for d in range(1, w):
            img.line(x0 + d, y0, x1 + d, y1, c)
            img.line(x0, y0 + d, x1, y1 + d, c)


BAYER = ((0, 8, 2, 10), (12, 4, 14, 6), (3, 11, 1, 9), (15, 7, 13, 5))


def paint(img: Img, x: int, y: int, c: int, level: int = 16) -> None:
    """Dithered set: `level` 0..16 is how many texels of a 4x4 cell survive."""
    if level >= 16:
        img.set(x, y, c)
    elif level > 0 and BAYER[int(y) & 3][int(x) & 3] < level:
        img.set(x, y, c)


def star4(img: Img, cx: int, cy: int, r: int, c: int) -> None:
    """Four-point twinkle - the sparkle every engine draws over a heal."""
    for i in range(-r, r + 1):
        img.set(cx + i, cy, c)
        img.set(cx, cy + i, c)
        if abs(i) <= 1:
            img.set(cx + i, cy + 1, c)
            img.set(cx + i, cy - 1, c)
            img.set(cx + 1, cy + i, c)
            img.set(cx - 1, cy + i, c)


def shard(img: Img, cx: int, cy: int, ang: float, ln: int, c: int, hi: int,
          w: int = 2) -> None:
    """A splinter pointing along `ang`, tapering to a lit tip."""
    dx, dy = math.cos(ang), math.sin(ang)
    nx, ny = -dy, dx
    for k in range(ln + 1):
        t = k / max(ln, 1)
        half = max(0, round(w * (1.0 - t)))
        bx, by = cx + dx * ln * t, cy + dy * ln * t
        for o in range(-half, half + 1):
            img.set(round(bx + nx * o), round(by + ny * o), hi if o >= 0 else c)
    img.set(round(cx + dx * ln), round(cy + dy * ln), hi)


def dashed_ring(img: Img, cx: int, cy: int, r: int, ry: float, c: int,
                ticks: int, level: int, skip: int = 2) -> None:
    """Broken halo: reads as an expanding shockwave, not a picture frame."""
    for k in range(ticks):
        if k % skip:
            continue
        a = k * math.tau / ticks
        paint(img, round(cx + math.cos(a) * r), round(cy + math.sin(a) * r * ry),
              c, level)


# ------------------------------------------------------------------- effects
def fireball(f: int, n: int) -> Img:
    img = Img(SIZE, SIZE, WHITE)
    t = f / (n - 1)
    cx = round(5 + t * (SIZE - 13))
    cy = C - 1 + round(math.sin(t * math.pi * 2) * 2)
    # tapered tail: hot where it leaves the head, cooling as it trails off
    for k in range(7):
        tx = cx - 3 - k * 2
        if tx < 1:
            break
        r = max(1, 6 - k)
        wob = round(math.sin((t * 7 + k) * 2.4) * (k / 3.0))
        cols = [FIRE[2], FIRE[1], FIRE[0]] if k < 4 else [FIRE[0], EMBER, EMBER]
        glow(img, tx, cy + wob, r, cols)
    head = 6 + (1 if f % 2 else 0)
    glow(img, cx, cy, head, [FIRE[3], FIRE[2], FIRE[1], FIRE[0]])
    glow(img, cx - 1, cy - 1, head - 3, [ms.safe_light(FIRE[3], 8), FIRE[3], FIRE[2]])
    # leading edge comes to a point so direction of travel is unambiguous
    img.set(cx + head, cy, FIRE[1])
    img.set(cx + head + 1, cy, EMBER)
    rnd = random.Random("fireball")
    for _ in range(10):
        sx = cx + rnd.randint(2, 6)
        sy = cy + rnd.randint(-5, 5)
        paint(img, sx, sy, FIRE[rnd.randint(1, 3)], 11)
    return img


def explosion(f: int, n: int) -> Img:
    img = Img(SIZE, SIZE, WHITE)
    t = f / (n - 1)
    if f == 0:
        glow(img, C, C, 6, [ms.safe_light(FIRE[3], 10), FIRE[3], FIRE[2], FIRE[1]])
        for k in range(8):
            shard(img, C, C, k * math.pi / 4, 7, FIRE[2], FIRE[3])
        return img
    r = round(4 + t * 11)
    tone = FIRE[2] if t < 0.5 else FIRE[1]
    if t < 0.6:
        ka.band(img, C, C, r, max(2, int(r * 0.94)), 3, tone)
        ka.band(img, C, C, max(1, r - 4), max(1, int((r - 4) * 0.9)), 2, FIRE[0])
    else:  # the fireball tears apart: the halo thins to embers, not a rim
        level = max(4, 16 - int((t - 0.6) * 34))
        dashed_ring(img, C, C, r, 0.94, tone, 30, level, 1)
        dashed_ring(img, C, C, max(1, r - 1), 0.94, FIRE[0], 30, level // 2, 1)
    for k in range(8):  # shards fly outward and shrink
        a = k * math.pi / 4 + 0.2
        shard(img, round(C + math.cos(a) * (r + 1)), round(C + math.sin(a) * (r + 1)),
              a, max(1, round(7 * (1 - t))), FIRE[1] if k % 2 else FIRE[0], FIRE[2])
    rnd = random.Random("explosion")
    if f >= 2:
        for _ in range(22):
            a = rnd.uniform(0, math.tau)
            d = rnd.uniform(0, r + 3)
            paint(img, round(C + math.cos(a) * d), round(C + math.sin(a) * d),
                  rnd.choice([EMBER, FIRE[0], FIRE[1]]), 13 if f < n - 1 else 9)
    return img


def _bolt_pts(rnd: random.Random, x0: int, y0: int, y1: int, segs: int,
              amp: float) -> List[Tuple[int, int]]:
    """Hard zigzag: a bolt kinks at its nodes, it never curves between them."""
    pts = [(x0, y0)]
    x = float(x0)
    for i in range(1, segs + 1):
        y = y0 + round((y1 - y0) * i / segs)
        x += (amp if i % 2 else -amp) + rnd.randint(-1, 1)
        pts.append((max(4, min(SIZE - 5, round(x))), y))
    return pts


def lightning(f: int, n: int) -> Img:
    img = Img(SIZE, SIZE, WHITE)
    rnd = random.Random("lightning")
    pts = _bolt_pts(rnd, C - 1, 1, SIZE - 3, 5, 5.5)
    segs = list(zip(pts, pts[1:]))
    foot = pts[-1]
    if f == 0:  # pre-flash: thin channel, charge gathering at both ends
        for (ax, ay), (bx, by) in segs:
            trail(img, ax, ay, bx, by, BOLT_LO, 1)
        star4(img, pts[0][0], 2, 3, BOLT)
        star4(img, foot[0], foot[1], 2, BOLT)
        return img
    if f >= 2:  # a fork branches off the second node, fading as the strike ends
        fork = _bolt_pts(random.Random("fork"), segs[1][0][0], segs[1][0][1],
                         SIZE - 10, 3, 3.5)
        level = 16 if f == 2 else 8
        for (ax, ay), (bx, by) in zip(fork, fork[1:]):
            for d in range(3):
                paint(img, ax + d, ay + d, BOLT_LO, level)
                paint(img, bx + d, by + d, BOLT_LO, level)
    live = segs if f < 3 else segs[1:4]  # late frames: the channel breaks up
    for (ax, ay), (bx, by) in live:
        if f < 3:
            trail(img, ax - 2, ay, bx - 2, by, BOLT_LO, 2)   # outer halo
            trail(img, ax + 2, ay, bx + 2, by, BOLT_LO, 2)
        trail(img, ax - 1, ay, bx - 1, by, BOLT if f < 3 else BOLT_LO, 2)
        if f < 2:
            trail(img, ax, ay, bx, by, BOLT_HI, 2)
    if f < 3:  # ground impact: flare plus sparks thrown back up
        star4(img, foot[0], foot[1], 7 - f, BOLT_HI)
        for k in range(6):
            shard(img, foot[0], foot[1], math.pi + k * math.pi / 5, 6 - f,
                  BOLT, BOLT_HI, 2)
    rnd2 = random.Random(f)
    for _ in range(6 if f < 3 else 12):
        paint(img, rnd2.randint(4, SIZE - 5), rnd2.randint(3, SIZE - 5),
              rnd2.choice([BOLT, BOLT_HI, BOLT_LO]), 12)
    return img


def cast_circle(f: int, n: int) -> Img:
    img = Img(SIZE, SIZE, WHITE)
    spin = f * (math.tau / n)
    ka.band(img, C, C, 13, 13, 1, RUNE_LO)
    ka.band(img, C, C, 11, 11, 2, RUNE)
    for k in range(16):  # outer ticks ride with the ring
        a = spin + k * math.tau / 16
        for rr, col in ((13, RUNE_HI if k % 4 == 0 else RUNE), (12, RUNE_LO)):
            img.set(round(C + math.cos(a) * rr), round(C + math.sin(a) * rr), col)
    tri = [-spin * 1.5 + k * math.tau / 3 for k in range(3)]
    for i, a in enumerate(tri):  # inscribed triangle counter-rotates
        b = tri[(i + 1) % 3]
        trail(img, round(C + math.cos(a) * 8), round(C + math.sin(a) * 8),
              round(C + math.cos(b) * 8), round(C + math.sin(b) * 8), RUNE_HI, 1)
    for k in range(4):  # rune pips in a diamond
        a = spin * 2 + k * math.tau / 4 + math.pi / 4
        x, y = round(C + math.cos(a) * 5), round(C + math.sin(a) * 5)
        img.set(x, y, RUNE_HI)
        img.set(x + 1, y, RUNE_LO)
        img.set(x - 1, y, RUNE_LO)
    star4(img, C, C, 3 + (1 if f % 2 else 0), ms.safe_light(RUNE_HI, 24))
    rnd = random.Random("cast")
    for i in range(6):  # motes climb the circle
        y = (rnd.randint(0, SIZE - 1) - f * 3) % SIZE
        x = C + round(math.cos(i * 1.9) * 9)
        paint(img, x, y, RUNE_HI if i % 2 else RUNE, 13)
    return img


def ice_shards(f: int, n: int) -> Img:
    img = Img(SIZE, SIZE, WHITE)
    t = f / (n - 1)
    if f == 0:
        glow(img, C, C, 5, [ICE_HI, ICE, ICE_LO])
        for k in range(6):
            shard(img, C, C, k * math.tau / 6 + 0.35, 6, ICE, ICE_HI)
        return img
    d = round(2 + t * 10)
    if t < 0.45:
        glow(img, C, C, max(2, 5 - int(t * 6)), [ICE_HI, ICE, ICE_LO])
    for k in range(6):
        a = k * math.tau / 6 + 0.35
        ln = max(4, round(12 - t * 5))
        shard(img, round(C + math.cos(a) * d), round(C + math.sin(a) * d),
              a, ln, ICE, ICE_HI, 3)
        # short mirror splinter keeps the burst from looking like a pinwheel
        shard(img, round(C + math.cos(a) * (d - 1)),
              round(C + math.sin(a) * (d - 1)), a + 0.52, max(2, ln // 2),
              ICE_LO, ICE, 2)
    dashed_ring(img, C, C, d + 4, 1.0, ICE_LO, 24, 16 if t < 0.5 else 9)
    if f == n - 1:
        rnd = random.Random("ice")
        for _ in range(14):
            a = rnd.uniform(0, math.tau)
            rr = rnd.uniform(4, 13)
            paint(img, round(C + math.cos(a) * rr), round(C + math.sin(a) * rr),
                  rnd.choice([ICE, ICE_HI, ICE_LO]), 10)
    return img


POISON_PUFFS = ((C - 6, C + 4, 8), (C + 5, C + 5, 7), (C - 1, C, 9),
                (C + 7, C - 3, 6), (C - 7, C - 2, 6), (C + 1, C + 7, 7),
                (C - 3, C - 5, 5))


def poison_cloud(f: int, n: int) -> Img:
    """Coverage-field gas: solid body, banded shading, Bayer-dithered edge."""
    img = Img(SIZE, SIZE, WHITE)
    t = f / (n - 1)
    rise = t * 4.0
    for y in range(SIZE):
        for x in range(SIZE):
            v, src = 0.0, (C, C)
            for i, (px, py, pr) in enumerate(POISON_PUFFS):
                r = pr * (1.0 + t * 0.45)
                wob = math.sin((t * 4 + i) * 1.7) * 1.6
                cx, cy = px + wob, py - rise * (0.6 + (i % 3) * 0.3)
                d = math.hypot(x - cx, y - cy)
                if 1.0 - d / r > v:
                    v, src = 1.0 - d / r, (cx, cy)
            v -= 0.10 * max(0.0, math.sin((x + y * 1.4) * 0.9 + t * 3.0))
            if v > 0.66 and (x - src[0]) + (y - src[1]) < -5:
                img.set(x, y, GAS_HI)           # light comes from the upper left
            elif v > 0.60:
                img.set(x, y, GAS)
            elif v > 0.46:
                img.set(x, y, GAS_LO)
            elif v > 0.34:
                paint(img, x, y, GAS_LO, 13)
            elif v > 0.25:
                paint(img, x, y, GAS_LO, 7)
    rnd = random.Random("poison")
    for _ in range(5):  # wisps breaking away from the crown
        paint(img, C + rnd.randint(-9, 9), 3 + ((f * 2 + rnd.randint(0, 6)) % 7),
              GAS if rnd.random() < 0.5 else GAS_LO, 9)
    return img


def heal_sparkle(f: int, n: int) -> Img:
    img = Img(SIZE, SIZE, WHITE)
    t = f / (n - 1)
    cx, cy = C, C + 1
    arm = 6 + (1 if f % 2 else 0)
    trail(img, cx - arm, cy, cx + arm, cy, HEAL_LO, 3)
    trail(img, cx, cy - arm, cx, cy + arm, HEAL_LO, 3)
    trail(img, cx - arm + 1, cy, cx + arm - 1, cy, HEAL, 2)
    trail(img, cx, cy - arm + 1, cx, cy + arm - 1, HEAL, 2)
    star4(img, cx, cy, 3 + (1 if f % 2 else 0), HEAL_HI)
    for i in range(6):  # sparkles rise on two sine paths
        x = cx + round(math.sin(i * 1.05 + t * math.tau) * (7 + (i % 3) * 2))
        y = (cy + 10 - ((f * 3 + i * 4) % 22)) % SIZE
        star4(img, x, y, 2 if i % 2 else 1, HEAL_HI if i % 2 else HEAL)
    dashed_ring(img, cx, cy + 6, 8 + round(t * 5), 0.4, HEAL_LO, 24,
                max(9, 18 - int(t * 9)), 1)
    return img


BUILDERS = {
    "fx_fireball": fireball,
    "fx_explosion": explosion,
    "fx_lightning": lightning,
    "fx_cast_circle": cast_circle,
    "fx_ice_shards": ice_shards,
    "fx_poison_cloud": poison_cloud,
    "fx_heal_sparkle": heal_sparkle,
}


FRAME_COUNTS = {"fx_fireball": 6, "fx_explosion": 7, "fx_lightning": 5,
                "fx_cast_circle": 8, "fx_ice_shards": 5, "fx_poison_cloud": 6,
                "fx_heal_sparkle": 5}


def build(name: str) -> List[Img]:
    n = FRAME_COUNTS[name]
    return [BUILDERS[name](f, n) for f in range(n)]


def effect_dir() -> Path:
    root = category_dir("sprite", create=True) / "effect"
    root.mkdir(parents=True, exist_ok=True)
    return root


def write(name: str, out_dir: Path) -> Tuple[Path, List[Img]]:
    delay, loop = TIMING[name]
    frames = build(name)
    path = effect_dir() / f"{name}.vpea"
    save_vpea(path, SIZE, SIZE, [f.px for f in frames], delay, loop)
    w, h, buf = ka.concat(frames)
    encode_png_rgba(out_dir / f"{name}_strip.png", w, h, buf)
    return path, frames


def main(argv: Sequence[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--only", default="",
                    help="comma list of names without the fx_ prefix")
    ap.add_argument("--scale", type=int, default=4, help="sheet zoom factor")
    ap.add_argument("--no-sheet", action="store_true")
    ap.add_argument("--out", default="", help="export folder (default: exports/effect)")
    args = ap.parse_args(argv)

    wanted = list(TIMING)
    if args.only:
        keys = {k.strip() for k in args.only.split(",") if k.strip()}
        wanted = [n for n in wanted if n[3:] in keys]
    out_dir = Path(args.out) if args.out else export_dir(create=True) / "effect"
    out_dir.mkdir(parents=True, exist_ok=True)

    rows: List[Tuple[str, List[Img]]] = []
    total = 0
    for name in wanted:
        path, frames = write(name, out_dir)
        total += len(frames)
        print(f"  {path}  {len(frames)} frames {SIZE}x{SIZE} @ {TIMING[name][0]} ms"
              f" loop={TIMING[name][1]}")
        rows.append((name, frames))

    if rows and not args.no_sheet:
        W, H, grid = ka.draw_sheet(rows, args.scale)
        sheet = export_dir(create=True) / "effect_sheet_all.png"
        encode_png_rgba(sheet, W, H, grid)
        print(f"  sheet {sheet}  {W}x{H}")
    print(f"  {len(rows)} effects, {total} frames -> {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
