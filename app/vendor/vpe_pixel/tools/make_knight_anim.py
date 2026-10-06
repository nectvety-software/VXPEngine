"""Draw the animation test set: a 32x32 knight with sword + shield.

This is the sample that exercises the editor's multi-frame (.vpea) container:
five character animations, three reusable effect animations, and one still.

  knight_idle    4 f  220 ms   breathing guard stance
  knight_walk    4 f  140 ms   2-frame leg cycle with bob
  knight_attack  8 f   90 ms   guard -> windup -> 3-blade arc slash -> recover
  knight_block   3 f   70 ms   shield raise, impact flash, hold
  knight_skill   6 f  100 ms   crouch, leap, spin, ground slam + shockwave
  fx_slash_arc   4 f   60 ms   crescent trail, drawn on its own layer
  fx_shield_flash 3 f  55 ms   spokes + ring for a parried hit
  fx_shockwave   5 f   80 ms   expanding ground ring + dust

VPE reserves 0xFFFF as the transparent key, so highlights go through
``safe_light``/``SPARK`` and never reach pure white. Everything is procedural
and seeded, so re-running rewrites byte-identical frames.

Writes (new folders only, existing library files are never touched):
  Documents\\VPE Pixel\\sprite\\characters\\knight\\*.vpea + knight_guard.vpe
  Documents\\VPE Pixel\\sprite\\vfx\\knight\\fx_*.vpea
  Documents\\VPE Pixel\\exports\\knight\\<anim>_strip.png
  Documents\\VPE Pixel\\exports\\knight_sheet_all.png   (review sheet)

Run from the repo root:
  python tools/make_knight_anim.py [--only attack,skill] [--scale 4] [--no-sheet]
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

from vpx_editor.gallery import category_dir  # noqa: E402
from vpx_editor.vpe import save_vpe  # noqa: E402
from vpx_editor.vpea import save_vpea  # noqa: E402
from vpx_editor.paths import export_dir  # noqa: E402
import make_samples as ms  # noqa: E402
from make_vqeaf_icons import encode_png_rgba  # noqa: E402

Img = ms.Img
rgb, WHITE = ms.rgb, ms.WHITE
SIZE = 32

# ------------------------------------------------------------------ palette
OUT = rgb(14, 18, 28)          # silhouette rim
STEEL = rgb(150, 160, 176)
STEEL_HI = ms.safe_light(STEEL, 34)
STEEL_MID = rgb(112, 122, 140)
STEEL_LO = rgb(74, 84, 100)
STEEL_DK = rgb(44, 50, 64)
GOLD = rgb(222, 178, 66)
GOLD_LO = rgb(150, 110, 30)
LEATHER = rgb(96, 66, 40)
BOOT = rgb(64, 48, 34)
PLUME = rgb(196, 58, 70)
PLUME_LO = rgb(126, 32, 48)
TABARD = rgb(46, 96, 168)
TABARD_LO = rgb(28, 62, 118)
SHIELD = rgb(40, 88, 160)
SHIELD_HI = ms.safe_light(SHIELD, 34)
SPARK = rgb(240, 248, 250)     # brightest allowed (r-field stays below 31)
ARC = rgb(150, 226, 244)
ARC_LO = rgb(74, 156, 200)
ARC_DK = rgb(38, 92, 140)
EMBER = rgb(252, 176, 60)
DUST = rgb(150, 140, 128)
DUST_LO = rgb(96, 88, 78)

# Body anchors in the 32x32 cell, before pose offsets. ``bob`` moves the whole
# silhouette, ``FEET`` stays as the ground line so a leap reads as airborne.
X0 = 11                        # left edge of the helm
TOP = 6                        # top of the helm at bob 0
HAND = (19, 15)                # sword pivot, right-facing knight
BLADE_LEN = 12
FEET = 27                      # ground row
SHIELD_AT = {"high": (1, 12), "out": (0, 13), "mid": (2, 14), "low": (3, 16)}
LABEL_H = 6

# One span per slash frame: (trail start, blade angle). The blade is at the
# second value, so the crescent never appears before the swing starts.
TRAIL: List[Tuple[float, float]] = [(-152, -104), (-152, -46), (-120, 14),
                                    (-96, 58)]


# --------------------------------------------------------------- primitives
def tip_at(hx: int, hy: int, ang: float, length: int = BLADE_LEN) -> Tuple[int, int]:
    """Where the blade point lands for a swing - used to anchor impact FX."""
    a = math.radians(ang)
    return round(hx + math.cos(a) * length), round(hy + math.sin(a) * length)


def blade(img: Img, hx: int, hy: int, ang: float,
          length: int = BLADE_LEN) -> Tuple[float, float]:
    """Solid 3px blade from the hand at `ang` degrees (0 = right, -90 = up)."""
    a = math.radians(ang)
    dx, dy = math.cos(a), math.sin(a)
    nx, ny = -dy, dx
    up = -1.0 if ny >= 0 else 1.0          # sign of the normal that points up
    tip = (hx + dx * length, hy + dy * length)
    for t in range(1, length + 1):
        left = length - t
        if left == 0:
            img.set(round(tip[0]), round(tip[1]), SPARK)
            continue
        px, py = hx + dx * t, hy + dy * t
        half = 1.0 if left > 2 else 0.5
        img.set(round(px + nx * half * up), round(py + ny * half * up), STEEL_HI)
        img.set(round(px), round(py), STEEL_HI if left > 1 else SPARK)
        img.set(round(px - nx * half * up), round(py - ny * half * up), STEEL_MID)
    # crossguard, grip, pommel
    for off in (-2, -1, 0, 1, 2):
        img.set(round(hx + nx * off), round(hy + ny * off), GOLD)
    for t in range(1, 4):
        img.set(round(hx - dx * t), round(hy - dy * t), LEATHER)
    img.set(round(hx - dx * 4), round(hy - dy * 4), GOLD_LO)
    return tip


def shield(img: Img, x: int, y: int, rim: int = GOLD, field: int = SHIELD,
           boss: int = GOLD) -> None:
    """Heater shield, 8 wide x 10 tall, point down, gold rim + boss."""
    img.stamp(x, y, [
        ".RRRRRR.",
        "RHH##HHR",
        "RHH###HR",
        "R##GG##R",
        "R#GGGG#R",
        "R#GGGG#R",
        "R##GG##R",
        ".R####R.",
        "..R##R..",
        "...RR...",
    ], {".": None, "R": rim, "#": field, "H": SHIELD_HI, "G": boss})


def armor(img: Img, bob: int, step: int, dx: int,
          plume_sway: int = 0) -> None:
    """Knight body (no weapons) on the 32x32 grid; ground stays at FEET."""
    top = TOP + bob
    x0 = X0 + dx
    # helmet
    ms.rrect(img, x0, top, 9, 8, STEEL)
    img.rect(x0 + 1, top + 1, 1, 3, STEEL_HI)         # crown sheen
    img.rect(x0 + 2, top + 4, 6, 2, STEEL_DK)         # visor slit
    img.set(x0 + 6, top + 4, SPARK)                   # eye glint
    img.set(x0 + 7, top + 5, ARC)
    img.rect(x0, top + 7, 9, 1, GOLD)                 # brow band
    img.rect(x0 - 1, top + 1, 1, 5, STEEL_LO)         # back plate
    # plume
    img.rect(x0 + 3 + plume_sway, top - 3, 3, 2, PLUME)
    img.rect(x0 + 2 + plume_sway, top - 1, 4, 2, PLUME)
    img.rect(x0 + 2 - plume_sway, top, 3, 1, PLUME_LO)
    # torso + pauldrons
    ms.rrect(img, x0 - 2, top + 8, 12, 7, STEEL_MID)
    img.circle(x0 - 1, top + 9, 2, STEEL_HI, filled=True)
    img.circle(x0 + 8, top + 9, 2, STEEL, filled=True)
    img.rect(x0 + 1, top + 10, 6, 4, STEEL)
    img.rect(x0 + 2, top + 11, 4, 5, TABARD)          # tabard down the front
    img.rect(x0 + 2, top + 13, 4, 1, TABARD_LO)
    img.rect(x0 + 1, top + 14, 6, 1, GOLD_LO)         # belt
    img.rect(x0 + 3, top + 14, 2, 1, GOLD)
    # arms (shoulder to hand)
    img.rect(x0 - 2, top + 11, 2, 5, STEEL_LO)        # shield arm
    img.rect(x0 + 8, top + 11, 2, 4, STEEL_LO)        # sword arm
    img.rect(x0 + 7, top + 8, 3, 3, LEATHER)          # gauntlet at HAND
    # legs: 3px wide, gold knee, boots planted on the FEET row. The near leg is
    # lit and the far leg shaded, so swapping them reads as a step from the side.
    legs = {
        0: [(x0 + 1, 0, STEEL_LO), (x0 + 5, 0, STEEL_MID)],   # neutral guard
        1: [(x0 - 1, 0, STEEL_LO), (x0 + 7, 0, STEEL_MID)],   # stride, near fwd
        2: [(x0 + 1, -2, STEEL_LO), (x0 + 5, 0, STEEL_MID)],  # far heel lifted
        3: [(x0 + 7, 0, STEEL_LO), (x0 - 1, 0, STEEL_MID)],   # stride, far fwd
        4: [(x0 + 1, 0, STEEL_LO), (x0 + 5, -2, STEEL_MID)],  # near heel lifted
    }[step]
    for lx, lift, tone in legs:
        yy = top + 15
        foot = FEET + bob + lift
        img.rect(lx, yy, 3, foot - 3 - yy, tone)
        img.rect(lx + 2, yy, 1, foot - 3 - yy, ms.darken(tone, 0.72))  # inner edge
        img.rect(lx, yy + 1, 3, 1, GOLD_LO)                        # knee trim
        img.rect(lx - 1, foot - 2, 4, 3, BOOT)                     # boot
        img.rect(lx - 1, foot - 2, 4, 1, ms.lighten(BOOT, 26))


# ------------------------------------------------------------------- poses
POSES: Dict[str, List[Dict]] = {
    "idle": [
        dict(bob=0, step=0, dx=0, ang=-18, shield="high", sway=0),
        dict(bob=0, step=0, dx=0, ang=-15, shield="high", sway=1),
        dict(bob=1, step=0, dx=0, ang=-18, shield="high", sway=1),
        dict(bob=1, step=0, dx=0, ang=-21, shield="high", sway=0),
    ],
    "walk": [
        dict(bob=0, step=1, dx=0, ang=-22, shield="mid", sway=0),
        dict(bob=1, step=2, dx=0, ang=-18, shield="mid", sway=1),
        dict(bob=0, step=3, dx=0, ang=-22, shield="mid", sway=0),
        dict(bob=1, step=4, dx=0, ang=-18, shield="mid", sway=-1),
    ],
    "attack": [
        dict(bob=0, step=0, dx=0, ang=-18, shield="high", sway=0),
        dict(bob=-1, step=0, dx=-1, ang=-152, shield="high", sway=-1),
        dict(bob=-1, step=0, dx=0, ang=-104, shield="mid", sway=0,
             arc=TRAIL[0]),
        dict(bob=0, step=0, dx=0, ang=-46, shield="mid", sway=1, arc=TRAIL[1]),
        dict(bob=0, step=1, dx=1, ang=14, shield="low", sway=1, arc=TRAIL[2]),
        dict(bob=1, step=1, dx=1, ang=58, shield="low", sway=0,
             arc=TRAIL[3]),
        dict(bob=0, step=0, dx=0, ang=26, shield="mid", sway=0),
        dict(bob=0, step=0, dx=0, ang=-18, shield="high", sway=0),
    ],
    "block": [
        dict(bob=0, step=0, dx=-1, ang=-64, shield="out", sway=0),
        dict(bob=1, step=1, dx=-1, ang=-70, shield="out", sway=0, flash=0),
        dict(bob=0, step=0, dx=0, ang=-30, shield="high", sway=0, flash=1),
    ],
    "skill": [
        dict(bob=2, step=0, dx=0, ang=40, shield="low", sway=0, charge=0),
        dict(bob=-2, step=2, dx=0, ang=-140, shield="out", sway=-1, charge=1,
             puff=0),
        dict(bob=-3, step=4, dx=1, ang=-58, shield="out", sway=1,
             arc=(-140, -58), puff=1),
        dict(bob=1, step=1, dx=1, ang=64, shield="low", sway=0, wave=0),
        dict(bob=1, step=1, dx=1, ang=66, shield="low", sway=0, wave=1),
        dict(bob=0, step=0, dx=0, ang=52, shield="high", sway=0, wave=4),
    ],
}


def charge_glow(img: Img, frame: int, pivot: Tuple[int, int]) -> None:
    """Skill wind-up: a hot core with sparks pulled in from around it."""
    rnd = random.Random(70 + frame)
    r = [6, 3][min(frame, 1)]
    for _ in range(8):
        a = rnd.uniform(0, math.tau)
        d = rnd.uniform(r * 0.9, r + 1.5)
        img.set(round(pivot[0] + d * math.cos(a)),
                round(pivot[1] + d * math.sin(a)),
                rnd.choice([ARC, ARC_LO, EMBER]))
    img.circle(pivot[0], pivot[1], max(1, r // 2), ARC, filled=True)
    img.circle(pivot[0], pivot[1], max(1, r // 4), SPARK, filled=True)


def takeoff_puff(img: Img, cx: int, strength: int) -> None:
    """Dust left on the ground while the knight is airborne."""
    rnd = random.Random(90 + strength)
    gy = FEET + 1
    img.ellipse(cx, gy, 7 + strength * 3, 2, DUST_LO)
    img.ellipse(cx, gy, 5 + strength * 2, 1, DUST)
    for _ in range(4 + strength * 2):
        px = cx + rnd.randint(-9 - strength * 3, 9 + strength * 3)
        img.rect(px, gy - rnd.randint(0, 2), 2, 2,
                 DUST if rnd.random() < 0.6 else DUST_LO)


def knight(pose: str, sub: int) -> Img:
    """One character frame: armor + shield + sword, plus its skill effects."""
    p = POSES[pose][sub]
    img = Img(SIZE, SIZE, WHITE)
    bob, dx = p["bob"], p["dx"]
    sx, sy = HAND[0] + dx, HAND[1] + bob
    tip = tip_at(sx, sy, p["ang"])
    shield_xy = (SHIELD_AT[p["shield"]][0] + dx, SHIELD_AT[p["shield"]][1] + bob)
    if "wave" in p:
        # Keep the burst inside the cell: the ring is wide, the ground is low.
        shockwave(img, p["wave"], (max(12, min(tip[0], 18)), FEET),
                  mask=True, spread=0.78)
    if "arc" in p:
        slash_arc(img, p["arc"], (sx, sy))            # trail behind the silhouette
    if "puff" in p:
        takeoff_puff(img, 16 + dx, p["puff"])
    armor(img, bob, p["step"], dx, p.get("sway", 0))
    shield(img, *shield_xy)
    blade(img, sx, sy, p["ang"])
    if "charge" in p:
        charge_glow(img, p["charge"], tip)
    if "flash" in p:
        shield_flash(img, p["flash"], (shield_xy[0] + 4, shield_xy[1] + 4))
    ms.shade(img, STEEL_DK)
    ms.outline(img, OUT)
    return img


# ---------------------------------------------------------------- effects
def slash_arc(img: Img, span: Tuple[float, float], pivot: Tuple[int, int],
              radius: int = BLADE_LEN) -> None:
    """Swept crescent hugging the blade path, brightest at the leading angle."""
    a0, a1 = span
    cx, cy = pivot
    steps = max(30, int(abs(a1 - a0) * 2.6))
    outer = radius + 1
    for i in range(steps + 1):
        t = i / steps
        a = math.radians(a0 + (a1 - a0) * t)
        band = 3 + int(9 * t * t)                     # thin tail, fat head
        inner = outer - band
        cos, sin = math.cos(a), math.sin(a)
        for r in range(inner, outer + 1):
            k = (r - inner) / band                    # 0 inner, 1 outer edge
            if t > 0.8 and k > 0.6:
                c = SPARK
            elif k > 0.78:
                c = ARC
            elif k > 0.34:
                c = ARC_LO
            else:
                c = ARC_DK
            img.set(round(cx + r * cos), round(cy + r * sin), c)
    if a1 > -20:                                      # chips fly off the tip
        rnd = random.Random(int(a0) * 7 + int(a1))
        for _ in range(8):
            d = rnd.uniform(2, 9)
            spread = rnd.uniform(-0.35, 0.35)
            img.set(round(cx + (outer + d * 0.5) * math.cos(a1 + spread)),
                    round(cy + (outer + d * 0.5) * math.sin(a1 + spread)),
                    rnd.choice([EMBER, SPARK, ARC]))


def shield_flash(img: Img, frame: int, center: Tuple[int, int]) -> None:
    """Parry impact: a hot core with thin spokes, biggest on first contact."""
    cx, cy = center
    f = min(frame, 2)
    outer = [8, 5, 3][f]
    core = [3, 1, 1][f]
    for i in range(8):
        a = math.radians(i * 45 + (10 if f else 0))
        reach = outer if i % 2 == 0 else outer - 3
        for k in range(core + 1, reach + 1):
            img.set(round(cx + k * math.cos(a)), round(cy + k * math.sin(a)),
                    ARC if k < reach - 1 else ARC_LO)
    img.circle(cx, cy, core, SPARK, filled=True)
    img.circle(cx, cy, core + 1, ARC)
    if not f:
        rnd = random.Random(5)
        for _ in range(7):
            a = rnd.uniform(0, math.tau)
            d = rnd.uniform(outer + 1, outer + 4)
            img.set(round(cx + d * math.cos(a)), round(cy + d * math.sin(a)),
                    rnd.choice([EMBER, SPARK, ARC]))


def band(img: Img, cx: int, cy: int, rx: int, ry: int, w: int, c: int,
         mask: bool = False) -> None:
    """Solid elliptical ring: outer (rx, ry) minus an inner hole of width w."""
    if rx <= 0 or ry <= 0:
        return
    irx, iry = rx - w, max(1, ry - max(1, w // 2))
    for j in range(-ry, ry + 1):
        for i in range(-rx, rx + 1):
            d = (i / rx) ** 2 + (j / ry) ** 2
            if d > 1.0 or d == 0.0:
                continue
            if irx > 0 and ((i / irx) ** 2 + (j / iry) ** 2) < 1.0:
                continue
            if mask and img.get(cx + i, cy + j) != WHITE:
                continue
            img.set(cx + i, cy + j, c)


def shockwave(img: Img, frame: int, impact: Tuple[int, int],
              mask: bool = False, spread: float = 1.0) -> None:
    """Ground slam: solid ring spreading from the impact point, dust, then fade."""
    gx, gy = impact
    f = min(frame, 4)
    rx = int([7, 11, 15, 19, 22][f] * spread)
    ry = max(3, int(rx * 0.34))
    ry = min(ry, max(2, SIZE - 1 - gy))               # keep the ring inside the cell
    tone = [SPARK, ARC, ARC_LO, STEEL_LO, ARC_LO][f]
    band(img, gx, gy, rx, ry, 2, tone, mask)
    if rx > 8:
        band(img, gx, gy, rx - 4, max(1, ry - 2), 2,
             ARC if f < 3 else STEEL_MID, mask)
    if f == 0:                                        # contact burst
        img.ellipse(gx, gy, 5, 2, SPARK, filled=True)
        for y in range(gy - 9, gy):
            if not mask or img.get(gx, y) == WHITE:
                img.rect(gx - 1, y, 3, 1, ARC)
                img.set(gx, y, SPARK)
        for i in range(12):
            a = math.radians(i * 30 + 15)
            for k in (4, 6, 8):
                img.set(round(gx + k * math.cos(a) * 0.8),
                        round(gy + k * math.sin(a) * 0.5),
                        SPARK if k < 7 else ARC)
    rnd = random.Random(40 + f)
    for _ in range([2, 4, 5, 3, 2][f]):
        side = rnd.choice((-1, 1))
        px = gx + side * rnd.randint(2, max(2, rx))
        py = gy - ry - rnd.randint(0, 1 + f // 2)
        img.rect(px, py, 2, 2, DUST if rnd.random() < 0.7 else DUST_LO)


def standalone_fx(name: str) -> List[Img]:
    """Effect-only loops, drawn on the same 32x32 grid for engine reuse."""
    out: List[Img] = []
    if name == "slash_arc":
        pivot = (17, 17)
        for span in TRAIL:
            img = Img(SIZE, SIZE, WHITE)
            slash_arc(img, span, pivot, radius=14)
            out.append(img)
    elif name == "shield_flash":
        for f in range(3):
            img = Img(SIZE, SIZE, WHITE)
            shield_flash(img, f, (16, 15))
            out.append(img)
    elif name == "shockwave":
        for f in range(5):
            img = Img(SIZE, SIZE, WHITE)
            shockwave(img, f, (16, 22), spread=0.72)
            out.append(img)
    for img in out:
        ms.outline(img, ARC_LO)
    return out


# ------------------------------------------------------------------- output
# name -> (delay ms, loop)
TIMING: Dict[str, Tuple[int, bool]] = {
    "knight_idle": (220, True),
    "knight_walk": (140, True),
    "knight_attack": (90, False),
    "knight_block": (70, False),
    "knight_skill": (100, False),
    "fx_slash_arc": (60, False),
    "fx_shield_flash": (55, False),
    "fx_shockwave": (80, False),
}


def folder_for(name: str) -> Path:
    """sprite/characters/knight and sprite/vfx/knight - both new sub-folders."""
    root = category_dir("sprite", create=True) / ("vfx" if name.startswith("fx_")
                                                  else "characters") / "knight"
    root.mkdir(parents=True, exist_ok=True)
    return root


def build(name: str) -> List[Img]:
    if name.startswith("fx_"):
        return standalone_fx(name[3:])
    return _frames(name[len("knight_"):])


def _frames(pose: str) -> List[Img]:
    return [knight(pose, i) for i in range(len(POSES[pose]))]


def concat(frames: Sequence[Img]) -> Tuple[int, int, List[int]]:
    """Frames laid out left to right, one row - a spritesheet."""
    w, h = SIZE * len(frames), SIZE
    buf = [WHITE] * (w * h)
    for i, f in enumerate(frames):
        for y in range(h):
            row = y * w + i * SIZE
            buf[row:row + SIZE] = f.px[y * SIZE:(y + 1) * SIZE]
    return w, h, buf


def write(name: str, out_dir: Path) -> Tuple[Path, List[Img]]:
    delay, loop = TIMING[name]
    frames = build(name)
    path = folder_for(name) / f"{name}.vpea"
    save_vpea(path, SIZE, SIZE, [f.px for f in frames], delay, loop)
    w, h, buf = concat(frames)
    encode_png_rgba(out_dir / f"{name}_strip.png", w, h, buf)
    return path, frames


def scaled(img: Img, s: int) -> List[int]:
    out = [0] * (img.w * s * img.h * s)
    for y in range(img.h):
        for x in range(img.w):
            c = img.px[y * img.w + x]
            for j in range(s):
                row = (y * s + j) * img.w * s
                for i in range(s):
                    out[row + x * s + i] = c
    return out


def draw_sheet(rows: List[Tuple[str, List[Img]]], scale: int,
               pad: int = 3) -> Tuple[int, int, List[int]]:
    """Review sheet: dark checker bed, one labelled row per animation."""
    label_cols = max(label_w(n) for n, _f in rows) * scale
    cell = (SIZE + pad) * scale
    row_h = (LABEL_H + SIZE + pad) * scale
    widest = max(len(f) for _n, f in rows)
    W = pad * scale + label_cols + widest * cell + pad * scale
    H = pad * scale + len(rows) * row_h + pad * scale
    grid = [0] * (W * H)
    a, b = rgb(26, 30, 40), rgb(34, 38, 50)
    block = 4 * scale
    for y in range(H):
        for x in range(W):
            grid[y * W + x] = a if ((x // block) + (y // block)) % 2 else b

    def paste(px: List[int], pw: int, ph: int, ox: int, oy: int) -> None:
        for j in range(ph):
            if oy + j >= H:
                return
            row = (oy + j) * W + ox
            for i in range(min(pw, W - ox)):
                c = px[j * pw + i]
                if c != WHITE:
                    grid[row + i] = c

    for r, (name, frames) in enumerate(rows):
        y0 = pad * scale + r * row_h
        title = Img(label_w(name), LABEL_H, WHITE)
        title.text(0, 1, name, rgb(214, 224, 240))
        paste(scaled(title, scale), title.w * scale, title.h * scale,
              pad * scale, y0)
        for i, img in enumerate(frames):
            paste(scaled(img, scale), SIZE * scale, SIZE * scale,
                  pad * scale + label_cols + i * cell,
                  y0 + (LABEL_H + pad) * scale)
    return W, H, grid


def label_w(name: str) -> int:
    return len(name) * 4 + 2


def main(argv: Sequence[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--only", default="",
                    help="comma list of names without prefix, e.g. attack,skill")
    ap.add_argument("--scale", type=int, default=4, help="sheet zoom factor")
    ap.add_argument("--no-sheet", action="store_true")
    ap.add_argument("--out", default="", help="export folder (default: exports/knight)")
    args = ap.parse_args(argv)

    wanted = list(TIMING)
    if args.only:
        keys = {k.strip() for k in args.only.split(",") if k.strip()}
        wanted = [n for n in wanted
                  if n.split("_", 1)[1] in keys or n in keys]
    out_dir = Path(args.out) if args.out else export_dir(create=True) / "knight"
    out_dir.mkdir(parents=True, exist_ok=True)

    written: List[Tuple[str, List[Img]]] = []
    for name in wanted:
        path, frames = write(name, out_dir)
        print(f"  {path}  {len(frames)} frames {SIZE}x{SIZE} "
              f"@ {TIMING[name][0]} ms")
        written.append((name, frames))

    # One still frame for the plain .vpe library convention.
    guard = knight("attack", 0)
    still = folder_for("knight_attack") / "knight_guard.vpe"
    save_vpe(still, SIZE, SIZE, guard.px)
    w, h, buf = concat([guard])
    encode_png_rgba(out_dir / "knight_guard.png", w, h, buf)
    print(f"  {still}  1 frame")

    if not args.no_sheet and written:
        s = max(2, args.scale)
        for name, frames in written:                      # one row each
            W, H, grid = draw_sheet([(name, frames)], s)
            one = out_dir / f"sheet_{name}.png"
            encode_png_rgba(one, W, H, grid)
            print(f"  sheet {one}  {W}x{H}")
        W, H, grid = draw_sheet(written, s)
        sheet = export_dir(create=True) / "knight_sheet_all.png"
        encode_png_rgba(sheet, W, H, grid)
        print(f"  sheet {sheet}  {W}x{H}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
