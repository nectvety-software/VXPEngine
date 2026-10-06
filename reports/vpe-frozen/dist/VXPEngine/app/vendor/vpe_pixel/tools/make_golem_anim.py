"""Draw a stone golem boss as a playable .vpea set for the VPE library.

The second boss of `sprite/enemies/boss/`, next to the dragon. Where the dragon
is ellipses and membranes, this one is stacked rock: slabs and blocks with a
glowing amber core in the chest, so the two bosses share an outline colour and a
canvas but never a silhouette. (The 16x22 `fnynn/ma_golem` monster already in the
library is unrelated - this is a boss, not a re-skin of it.)

  golem_idle     4 f  200 ms  loop    settles on its legs, core pulses
  golem_walk     4 f  150 ms  loop    heavy alternate steps, dust at the feet
  golem_roar     4 f  120 ms  once    head back, jaw slabs drop, shock ring
  golem_slam     5 f   90 ms  once   both fists overhead, ground impact
  golem_boulder  6 f   80 ms  once   rips a rock out, hurls it off-frame
  golem_beam     6 f   70 ms  once   chest plate opens, amber beam
  golem_hurt     3 f  120 ms  once   recoil, chips break off
  golem_die      6 f  150 ms  once   cracks spread, core dies, collapses to rubble

38 frames, all through one parametric `golem()` pose function, with fills laid
down first and a single `rim()` pass bordering the union - the same trick the
dragon uses to keep one outline colour over a body built from a dozen blocks.
A union outline only separates parts that differ in colour, so every part owns
its own stone tone: lit rock on the torso, mid on the near limbs, dark on the
far ones. Light from the core is painted with `bleed()`, which refuses to touch
the transparent background - a glow disc on empty texels reads as an orange
decal stuck to the floor.

VPE reserves 0xFFFF as the transparent key, so highlights go through
``ms.safe_light`` and no palette constant is allowed to pack to it. Randomness
is seeded per scene name, so re-running is byte-identical.

Writes (new files only; the dragon scenes and the td_ stills are left alone):
  Documents\\VPE Pixel\\sprite\\enemies\\boss\\golem_<action>.vpea
  Documents\\VPE Pixel\\exports\\boss\\<scene>_strip.png
  Documents\\VPE Pixel\\exports\\golem_sheet_all.png   (review sheet)

Run from the repo root:
  python tools/make_golem_anim.py [--only idle,slam] [--scale 3] [--no-sheet]
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

import make_dragon_anim as dz  # noqa: E402  (SIZE, lerp, blank, shock, dust, sheet)
import make_effect_anim as ea  # noqa: E402  (star4)
from make_vqeaf_icons import encode_png_rgba  # noqa: E402
from vpx_editor.vpea import save_vpea  # noqa: E402
from vpx_editor.paths import export_dir  # noqa: E402
import make_samples as ms  # noqa: E402

Img, rgb, WHITE = ms.Img, ms.rgb, ms.WHITE
safe_light, darken = ms.safe_light, ms.darken
SIZE = dz.SIZE
lerp, blank = dz.lerp, dz.blank

TIMING: Dict[str, Tuple[int, int, bool]] = {   # frames, delay ms, loop
    "golem_idle": (4, 200, True),
    "golem_walk": (4, 150, True),
    "golem_roar": (4, 120, False),
    "golem_slam": (5, 90, False),
    "golem_boulder": (6, 80, False),
    "golem_beam": (6, 70, False),
    "golem_hurt": (3, 120, False),
    "golem_die": (6, 150, False),
}

# ----------------------------------------------------------------- palettes
STONE = {
    "rock": rgb(124, 130, 142),        # lit torso face
    "lit": rgb(158, 164, 176),         # top faces
    "mid": rgb(96, 102, 116),          # near limbs
    "dark": rgb(66, 72, 88),           # far limbs, undersides
    "edge": rgb(40, 46, 60),           # chipped edges, seams
    "moss": rgb(76, 114, 58),
    "moss2": rgb(52, 82, 44),
    "core": rgb(240, 168, 62),
    "core_hi": safe_light(rgb(246, 214, 128), 12),
    "core_lo": rgb(146, 64, 32),
    "socket": rgb(26, 28, 42),
    "eye": rgb(248, 206, 112),
    "out": rgb(18, 24, 38),            # same rim as the dragon boss
}
# rim() borders the union of these; the core and the eyes are painted after it
FILLS = ("rock", "lit", "mid", "dark", "edge", "moss", "moss2")
BEAM = (rgb(250, 232, 168), rgb(246, 196, 96), rgb(212, 128, 44), rgb(120, 56, 28))
FLASH = rgb(222, 208, 188)             # hurt: a pale dust flash, not a red one
SLATE = rgb(44, 48, 62)                # die: the stone goes dark as the core does

# --------------------------------------------------------------- geometry
# 48x48 = three tiles wide. The golem owns the middle band and leaves the right
# column free for the boulder and the beam to travel out of.
TORSO = (20, 25)      # centre of the rock block that reads as the chest
TX, TY = 11, 8        # half radii of that block
CORE = (26, 24)       # amber core, front of the chest
HEAD = (27, 11)       # head slab centre, sunk between the shoulders
SHLDR = (26, 19)      # near shoulder; the far one is 13 px further back
LEG_X = (14, 25)      # (0) is the off-side pillar
FOOT = 44


def jitter(seed: str) -> random.Random:
    return random.Random(seed)


def facet(img: Img, x: int, y: int, w: int, h: int, c: int, seed: str,
          density: float = 0.08) -> None:
    """Speckle a rock face so a flat block reads as chiselled stone."""
    img.speckle(x, y, w, h, (c, darken(c, 0.8)), density, jitter(seed))


def bleed(img: Img, cx: int, cy: int, r: int, colors: Sequence[int]) -> None:
    """Radial light that only lands on already-painted texels."""
    n = len(colors)
    for y in range(cy - r, cy + r + 1):
        for x in range(cx - r, cx + r + 1):
            if img.get(x, y) == WHITE:
                continue
            d = math.hypot(x - cx, y - cy)
            if d <= r:
                img.set(x, y, colors[min(n - 1, int(d / r * n))])


def limb(img: Img, pts: Sequence[Tuple[int, int]], r: int, c: int,
         seam: int = None) -> None:
    """A chain of discs through the joints - the golem's arms. `seam` paints the
    left silhouette of the chain, which is the only thing that separates a limb
    from the torso once `rim()` borders the union of the fills."""
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        steps = max(1, int(max(abs(x1 - x0), abs(y1 - y0))))
        for k in range(steps + 1):
            t = k / steps
            x, y = round(lerp(x0, x1, t)), round(lerp(y0, y1, t))
            img.circle(x, y, r, c, filled=True)
            if seam is not None:
                img.set(x - r, y, seam)
                img.set(x - r, y - 1, seam)


def hand(ang: float, fore: float, dy: int, far: bool = False) -> Tuple[int, int]:
    """Where the fist of a given arm pose lands - used to hold props on it."""
    sx = SHLDR[0] - (13 if far else 0)
    sy = SHLDR[1] + dy + (2 if far else 0)
    a1, a2 = math.radians(ang), math.radians(ang + fore)
    ex, ey = sx + math.cos(a1) * 7, sy + math.sin(a1) * 7
    return round(ex + math.cos(a2) * 7), round(ey + math.sin(a2) * 7)


def arm(img: Img, p: Dict, ang: float, fore: float, far: bool) -> None:
    """Shoulder -> elbow -> fist. `ang` is the upper arm, `fore` the elbow bend."""
    sx = SHLDR[0] - (13 if far else 0)
    sy = SHLDR[1] + p["dy"] + (2 if far else 0)
    a1, a2 = math.radians(ang), math.radians(ang + fore)
    ex, ey = round(sx + math.cos(a1) * 7), round(sy + math.sin(a1) * 7)
    hx, hy = round(ex + math.cos(a2) * 7), round(ey + math.sin(a2) * 7)
    col = p["dark"] if far else p["mid"]
    seam = None if far else p["edge"]
    limb(img, [(sx, sy), (ex, ey), (hx, hy)], 3, col, seam)
    img.circle(ex, ey, 3, p["dark"] if far else p["edge"], filled=True)
    r = 3 if far else 4
    img.rect(hx - r, hy - r + 1, r * 2, r * 2 - 1, col)         # fist slab
    img.line(hx - r, hy - r + 1, hx + r - 1, hy - r + 1,
             p["lit"] if not far else p["mid"])                 # lit knuckles
    img.rect(hx - r, hy + r - 1, r * 2, 1, p["edge"])
    if not far:
        img.line(sx, sy - 3, ex, ey - 3, p["lit"])              # shoulder cap
        img.line(hx - r, hy - r + 2, hx - r, hy + r - 2, p["edge"])


def legs(img: Img, p: Dict, lifts: Sequence[int], stride: int = 0) -> None:
    """Two stone pillars with slab feet; `lifts` raise a foot off the floor."""
    top = TORSO[1] + TY - 3
    for i, lx in enumerate(LEG_X):
        far = i == 0
        lift = lifts[i % len(lifts)]
        x = lx + (stride if not far else -stride)
        foot = min(FOOT + p["dy"] - lift, SIZE - 3)
        col = p["dark"] if far else p["rock"]
        w = 6 if far else 7
        img.rect(x - w // 2, top, w, max(2, foot - top), col)
        img.rect(x - w // 2 - 1, foot - 2, w + 2, 3, col)       # slab foot
        img.rect(x - w // 2 - 1, foot + 1, w + 2, 1, p["edge"])
        img.line(x - w // 2 - 1, foot - 2, x + w // 2, foot - 2,
                 p["edge"] if far else p["lit"])                # toe line
        img.line(x - w // 2, top + 1, x - w // 2, foot - 3,
                 p["edge"] if far else p["mid"])
        facet(img, x - w // 2 + 1, top + 2, w - 2,
              max(1, foot - top - 4), p["edge"] if far else p["dark"],
              f"Leg{i}{lift}", 0.12)


def torso(img: Img, p: Dict) -> None:
    tx, ty = TORSO[0], TORSO[1] + p["dy"]
    img.rect(tx - TX, ty - TY + 2, TX * 2, TY * 2 - 3, p["rock"])
    img.ellipse(tx, ty - TY + 4, TX - 1, 4, p["rock"], filled=True)
    img.rect(tx - TX + 3, ty + TY - 3, TX * 2 - 6, 4, p["mid"])     # tapered waist
    img.line(tx - TX + 1, ty - TY + 1, tx + TX - 2, ty - TY + 1, p["lit"])
    img.line(tx - TX, ty + 3, tx + TX - 1, ty + 3, p["edge"])       # block seam
    img.line(tx - TX + 3, ty + TY, tx + TX - 4, ty + TY, p["dark"])
    img.rect(tx + TX - 7, ty - TY - 1, 7, 7, p["rock"])             # near shoulder
    img.line(tx + TX - 7, ty - TY - 1, tx + TX - 1, ty - TY - 1, p["lit"])
    img.rect(tx - TX, ty - TY + 1, 6, 6, p["mid"])                  # far shoulder
    img.line(tx - TX, ty - TY + 1, tx - TX + 5, ty - TY + 1, p["lit"])
    img.line(tx - 3, ty - TY + 3, tx - 4, ty + 2, p["mid"])         # one joint
    img.line(tx + 5, ty + 4, tx + 4, ty + TY - 3, p["dark"])
    facet(img, tx - TX + 3, ty + 5, TX * 2 - 7, TY - 6, p["dark"], "Torso", 0.05)
    img.rect(tx - TX + 1, ty - TY - 1, 4, 2, p["moss"])             # moss pad
    img.set(tx - TX + 5, ty - TY, p["moss2"])
    # core socket: a sunk frame, so the crystal reads as set into the rock
    cx, cy = CORE[0], CORE[1] + p["dy"]
    img.rect(cx - 4, cy - 4, 9, 9, p["socket"])
    img.frame(cx - 4, cy - 4, 9, 9, p["edge"])


def core(img: Img, p: Dict, level: int) -> None:
    """The amber core, painted after rim() so nothing outlines the glow."""
    if level <= 0:
        return
    cx, cy = CORE[0], CORE[1] + p["dy"]
    img.rect(cx - 2, cy - 2, 5, 5, p["core_lo"])
    img.rect(cx - 1, cy - 1, 3, 3, p["core"])
    img.set(cx, cy, p["core_hi"])
    if level >= 2:
        for dx, dy in ((-2, 0), (2, 0), (0, -2), (0, 2)):
            img.set(cx + dx, cy + dy, p["core"])
    if level >= 3:
        bleed(img, cx, cy, 6, (p["core_hi"], p["core"], p["core_lo"]))
        img.rect(cx - 1, cy - 1, 3, 3, p["core"])
        img.set(cx, cy, p["core_hi"])


def head(img: Img, p: Dict, hx: int, hy: int, jaw: int, eye: str) -> None:
    """A loose slab on a block neck; the jaw drops with `jaw`."""
    img.rect(hx - 6, hy + 3, 11, 5, p["mid"])                  # neck block
    img.line(hx - 6, hy + 3, hx + 4, hy + 3, p["edge"])
    img.rect(hx - 7, hy - 4, 13, 8, p["rock"])                 # skull slab
    img.line(hx - 7, hy - 4, hx + 5, hy - 4, p["lit"])
    img.line(hx - 7, hy + 3, hx + 5, hy + 3, p["edge"])
    img.line(hx + 5, hy - 3, hx + 5, hy + 2, p["edge"])        # face plane
    img.rect(hx - 7, hy + 4 + jaw, 13, 3, p["mid"])            # jaw slab
    img.line(hx - 7, hy + 6 + jaw, hx + 5, hy + 6 + jaw, p["edge"])
    img.rect(hx - 6, hy - 5, 3, 1, p["moss"])                  # moss on the crown
    img.rect(hx + 1, hy - 6, 4, 2, p["mid"])                   # horn chip
    img.rect(hx - 4, hy - 3, 9, 2, p["socket"])                # eye band
    if eye == "shut":
        img.line(hx - 3, hy - 2, hx + 3, hy - 2, p["edge"])
    elif eye == "glow":
        img.rect(hx - 3, hy - 3, 2, 1, safe_light(p["eye"], 14))
        img.rect(hx + 1, hy - 3, 2, 1, safe_light(p["eye"], 14))
        bleed(img, hx, hy - 2, 2, (p["core_hi"], p["core_lo"]))
        img.rect(hx - 4, hy - 3, 9, 2, p["socket"])
        img.rect(hx - 3, hy - 3, 2, 1, safe_light(p["eye"], 14))
        img.rect(hx + 1, hy - 3, 2, 1, safe_light(p["eye"], 14))
    else:
        img.set(hx - 3, hy - 3, p["eye"])
        img.set(hx + 2, hy - 3, p["eye"])


def rim(img: Img, p: Dict) -> None:
    """One outline pass around the union of the rock fills."""
    fills = {p[k] for k in FILLS}
    edge = []
    for y in range(SIZE):
        for x in range(SIZE):
            if img.px[y * SIZE + x] not in fills:
                continue
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nx, ny = x + dx, y + dy
                if not (0 <= nx < SIZE and 0 <= ny < SIZE):
                    edge.append((x, y))
                    break
                if img.px[ny * SIZE + nx] not in fills:
                    edge.append((x, y))
                    break
    for x, y in edge:
        img.px[y * SIZE + x] = p["out"]


BASE: Dict = {
    "dx": 0, "dy": 0, "hx": 0, "hy": 0, "jaw": 0, "eye": "open",
    "arm": 52, "fore": 24, "arm2": 66, "fore2": 18,
    "legs": (0, 0), "stride": 0, "core": 2, "crack": 0,
    "tint": 0.0, "tint_to": FLASH,
}


def pose(**kw) -> Dict:
    q = dict(BASE)
    q.update(kw)
    return q


def golem(img: Img, p: Dict) -> None:
    """One boss frame from pose params - the only place the body is drawn."""
    c = dict(STONE)
    if p["tint"]:
        for key in FILLS:
            c[key] = dz.blend(c[key], p["tint_to"], p["tint"])
    c["dy"] = p["dy"]
    arm(img, c, p["arm2"], p["fore2"], far=True)
    legs(img, c, p["legs"], p["stride"])
    torso(img, c)
    head(img, c, HEAD[0] + p["hx"], HEAD[1] + p["hy"], p["jaw"], p["eye"])
    arm(img, c, p["arm"], p["fore"], far=False)
    rim(img, c)
    core(img, c, p["core"])
    if p["crack"]:
        cracks(img, c, p["crack"], p["dy"])


def cracks(img: Img, c: Dict, n: int, dy: int) -> None:
    """Charges of damage: dark seams that spread down the torso."""
    rnd = jitter(f"crack{n}")
    tx, ty = TORSO[0] + 1, TORSO[1] + dy
    for i in range(n):
        x = tx - TX + 4 + i * 5 + rnd.randint(-1, 1)
        y = ty - TY + 4
        for k in range(3 + i * 2):
            y += 1
            x += rnd.choice((-1, 0, 1))
            img.set(x, y, c["socket"] if k % 3 == 0 else c["edge"])


def stamp(p: Dict) -> Img:
    """Render the pose and apply the whole-frame offset (recoils, lunges)."""
    if not p["dx"]:
        out = blank()
        golem(out, p)
        return out
    tmp = blank()
    golem(tmp, p)
    out = blank()
    for y in range(SIZE):
        for x in range(SIZE):
            c = tmp.px[y * SIZE + x]
            if c != WHITE:
                out.set(x + p["dx"], y, c)
    return out


# ------------------------------------------------------------------ scenes
def boulder(img: Img, x: int, y: int, r: int, seed: str) -> None:
    """A thrown rock: blocky, lit from the top-left, with motion dashes."""
    for i in range(3):
        img.set(x - r - 3 - i * 2, y + i - 1, STONE["mid"])
    img.circle(x, y, r, STONE["mid"], filled=True)
    img.circle(x - 1, y - 1, max(1, r - 2), STONE["rock"], filled=True)
    img.line(x - r, y + 2, x + r - 1, y + 3, STONE["dark"])
    img.set(x + 1, y - r + 1, STONE["edge"])
    facet(img, x - r + 1, y - r + 1, r * 2 - 2, r * 2 - 2, STONE["dark"], seed,
          0.18)


def chips(img: Img, x: int, y: int, count: int, seed: str) -> None:
    rnd = jitter(seed)
    for _ in range(count):
        cx = x + rnd.randint(-10, 12)
        cy = y + rnd.randint(-9, 6)
        img.set(cx, cy, rnd.choice((STONE["mid"], STONE["dark"], STONE["lit"])))
        if rnd.random() < 0.4:
            img.set(cx + 1, cy, STONE["edge"])


def beam(img: Img, y: int, length: int, h: int) -> None:
    """Chest beam: dark edge, cool outer band, hot core, capped tip."""
    if length <= 0:
        return
    x0 = CORE[0] + 5
    for i in range(length):
        x = x0 + i
        t = i / max(1, length - 1)
        hh = max(1, round(h * (1.0 - 0.35 * t)))
        img.line(x, y - hh, x, y + hh, BEAM[2])
        img.line(x, y - hh + 1, x, y + hh - 1, BEAM[1])
        img.line(x, y - max(0, hh - 2), x, y + max(0, hh - 2), BEAM[0])
    img.line(x0 + length - 1, y - h, x0 + length - 1, y + h, BEAM[3])


def scene_idle(f: int, n: int) -> Img:
    return stamp(pose(dy=(0, -1, 0, 1)[f], hy=(0, -1, 0, 1)[f],
                      arm=(52, 46, 52, 58)[f], fore=(24, 30, 24, 18)[f],
                      arm2=(66, 60, 66, 72)[f],
                      core=(2, 3, 3, 2)[f], eye="shut" if f == 2 else "open"))


def scene_walk(f: int, n: int) -> Img:
    gait = ((0, 4), (4, 0), (1, 4), (4, 1))[f]
    img = stamp(pose(dy=(1, 0, 1, 0)[f], legs=gait, stride=(0, 2, 2, 0)[f],
                     arm=(34, 68, 44, 74)[f], fore=(30, 10, 24, 6)[f],
                     arm2=(48, 88, 60, 94)[f], hy=(1, -1, 0, -1)[f]))
    if 0 in gait:
        dz.dust(img, FOOT + 1, 4, f"walk{f}")
    return img


def scene_roar(f: int, n: int) -> Img:
    img = stamp(pose(dy=(0, -2, -3, -1)[f], hx=(0, -1, -2, -1)[f],
                     hy=(0, -3, -5, -3)[f], jaw=(0, 2, 3, 1)[f],
                     eye="glow", core=(2, 3, 3, 2)[f],
                     arm=(30, -34, -58, -26)[f], fore=(46, 34, 26, 40)[f],
                     arm2=(214, 228, 240, 230)[f], fore2=(-40, -30, -22, -34)[f],
                     legs=((0, 0), (1, 0), (1, 1), (0, 1))[f]))
    if f >= 2:
        dz.shock(img, TORSO[0] + 2, FOOT - 1, 14 + 6 * (f - 2),
                 safe_light(STONE["lit"], 10))
    if f == 2:
        chips(img, HEAD[0] + 4, HEAD[1] - 6, 5, "roar")
    return img


def scene_slam(f: int, n: int) -> Img:
    p = pose(dy=(0, -3, -4, 3, 1)[f], hx=(0, 1, 2, 2, 0)[f],
             hy=(0, -2, -2, 3, 1)[f], jaw=(0, 1, 3, 2, 0)[f],
             eye="glow" if f in (3, 4) else "open", core=(2, 2, 3, 3, 2)[f],
             arm=(50, -108, -114, 74, 34)[f], fore=(14, 44, 40, 26, 20)[f],
             arm2=(150, -72, -66, 74, 56)[f], fore2=(-14, -44, -40, 24, -18)[f],
             legs=((0, 0), (0, 0), (2, 2), (2, 1), (0, 0))[f])
    img = stamp(p)
    if f == 3:
        dz.shock(img, TORSO[0] + 4, FOOT - 1, 18, safe_light(STONE["lit"], 12))
        dz.shock(img, TORSO[0] + 4, FOOT - 1, 10, STONE["core"])
    if f >= 3:
        dz.dust(img, FOOT, 8 if f == 3 else 12, f"slam{f}")
        chips(img, TORSO[0] + 12, FOOT - 4, 6, f"slamc{f}")
    return img


def scene_boulder(f: int, n: int) -> Img:
    arms = ((62, 26), (36, 34), (-58, 34), (-14, 22), (16, 24), (52, 24))[f]
    p = pose(dy=(2, 1, -2, -1, 0, 0)[f], hx=(0, -1, -2, 1, 2, 0)[f],
             hy=(2, 2, -2, -1, 0, 0)[f], core=(2, 2, 3, 3, 2, 2)[f],
             eye="glow" if f in (2, 3) else "open",
             arm=arms[0], fore=arms[1], arm2=(74, 46, 206, 182, 150, 66)[f],
             fore2=(-20, -14, -26, -18, -12, -18)[f],
             legs=((0, 2), (2, 2), (0, 0), (0, 1), (1, 0), (0, 0))[f])
    img = stamp(p)
    if f <= 2:                       # still held: sit the rock on the fist
        hx, hy = hand(p["arm"], p["fore"], p["dy"])
        boulder(img, hx + 1, hy + 1, 5, seed=f"rock{f}")
    elif f in (3, 4):                # released, travelling out of the frame
        boulder(img, (40, 47)[f - 3], (20, 16)[f - 3], 4, seed=f"rock{f}")
    if f == 4:
        chips(img, 44, 20, 4, "rockchip")
    return img


def scene_beam(f: int, n: int) -> Img:
    p = pose(dy=(0, -1, -1, 0, 0, 0)[f], hx=(0, -1, -1, 0, 0, 0)[f],
             hy=(0, 1, 2, 2, 1, 0)[f], jaw=(0, 1, 2, 2, 1, 0)[f],
             eye="glow", core=(1, 2, 3, 3, 2, 1)[f],
             arm=(16, 8, 2, 2, 12, 34)[f], fore=(38, 44, 46, 46, 40, 22)[f],
             arm2=(46, 38, 32, 32, 38, 56)[f],
             legs=((0, 0), (0, 1), (0, 1), (0, 0), (0, 0), (0, 0))[f])
    img = stamp(p)
    length = (0, 6, 20, 22, 14, 5)[f]
    if length:
        beam(img, CORE[1] + p["dy"], length, (0, 2, 4, 4, 3, 1)[f])
    if f in (3, 4):
        ea.star4(img, CORE[0] + 5 + length - 2, CORE[1] + p["dy"], 3,
                 STONE["core_hi"])
    if f >= 1:
        dz.dust(img, FOOT, 5, f"beam{f}")
    return img


def scene_hurt(f: int, n: int) -> Img:
    p = pose(dx=(0, -3, -1)[f], dy=(0, 1, 0)[f], hx=(0, -3, -1)[f],
             hy=(0, -1, 1)[f], jaw=(0, 2, 1)[f],
             eye=("open", "shut", "glow")[f], core=(2, 3, 1)[f],
             tint=(0.0, 0.12, 0.04)[f], crack=(0, 1, 1)[f],
             arm=(40, 12, 30)[f], fore=(22, 40, 18)[f],
             arm2=(62, 84, 50)[f], legs=((0, 0), (1, 2), (0, 0))[f])
    img = stamp(p)
    if f:
        chips(img, HEAD[0] - 2 + p["dx"], HEAD[1] - 4, 7 if f == 1 else 4,
              f"hurt{f}")
        img.set(CORE[0] + 6, CORE[1] - 4, STONE["core_hi"])
    return img


def scene_die(f: int, n: int) -> Img:
    if f >= 4:                       # the slabs have come down: rubble only
        img = blank()
        rubble(img, f)
        dz.dust(img, FOOT + 1, 14 if f == 4 else 8, f"die{f}")
        return img
    p = pose(dy=(0, 1, 2, 4)[f], hx=(0, -1, -3, -4)[f], hy=(0, 2, 5, 7)[f],
             jaw=(0, 2, 3, 3)[f], eye=("open", "glow", "shut", "shut")[f],
             core=(2, 3, 2, 1)[f], crack=(1, 2, 3, 4)[f],
             tint=(0, 0.1, 0.2, 0.34)[f], tint_to=SLATE,
             arm=(50, 74, 100, 124)[f], fore=(10, 2, -8, -14)[f],
             arm2=(64, 88, 110, 132)[f], fore2=(16, 8, -4, -10)[f],
             legs=((0, 0), (1, 0), (2, 1), (3, 3))[f], stride=(0, 0, 1, 2)[f])
    img = stamp(p)
    if f >= 3:
        dz.dust(img, FOOT - 1, 12, f"die{f}")
        chips(img, TORSO[0] + 4, FOOT - 6, 8, f"diec{f}")
    return img


def rubble(img: Img, f: int) -> None:
    """What is left when the slabs come down."""
    c = dict(STONE)
    for key in FILLS:
        c[key] = dz.blend(c[key], SLATE, 0.34 + 0.08 * (f - 4))
    # A mound, not confetti: one filled silhouette that narrows to a peak, so
    # the pile keeps the boss's three-tile footprint and reads as weight.
    profile = ((20, 26), (18, 28), (17, 25), (15, 30), (13, 31), (12, 29),
               (10, 34), (8, 36), (9, 38), (6, 40), (5, 41), (7, 42), (3, 43),
               (2, 44), (1, 45), (1, 45), (1, 45))
    top = SIZE - len(profile) - 3
    for i, (x0, x1) in enumerate(profile):
        y = top + i
        img.rect(x0, y, x1 - x0 + 1, 1, c["rock"] if i % 2 else c["mid"])
        img.set(x0, y, c["lit"])                      # catchlight down the slope
        if i == 0:
            img.line(x0, y, x1, y, c["lit"])          # the peak catches the light
        else:
            img.set(x0 + 5 + (i % 2) * 3, y, c["edge"])   # block joints
            img.set(x0 + 11 + (i % 2) * 3, y, c["edge"])
    for y in (top + 4, top + 9, top + 13):            # course lines
        x0, x1 = profile[y - top]
        img.line(x0 + 1, y, x1 - 1, y, c["dark"])
    # the skull, half-buried on the near flank, and the dead core in the middle
    img.rect(5, top + 10, 11, 6, c["rock"])
    img.line(5, top + 10, 15, top + 10, c["lit"])
    img.rect(5, top + 15, 11, 1, c["edge"])
    img.rect(7, top + 12, 3, 2, c["socket"])
    img.rect(11, top + 12, 3, 2, c["socket"])
    img.rect(20, top + 7, 7, 6, c["socket"])
    img.rect(21, top + 8, 5, 4, darken(STONE["core_lo"], 0.75))
    img.set(23, top + 10, darken(STONE["core_lo"], 0.45))
    for x, y in ((17, top + 2), (28, top + 6), (33, top + 12)):
        img.rect(x, y, 4, 2, c["moss"])
        img.set(x + 4, y + 1, c["moss2"])
    for x, y, w, h in ((42, top + 13, 5, 3), (44, top + 8, 2, 2)):
        img.rect(x, y, w, h, c["rock"])               # a slab thrown clear
        img.line(x, y, x + w - 1, y, c["lit"])
    rim(img, c)


BUILDERS = {
    "golem_idle": scene_idle, "golem_walk": scene_walk,
    "golem_roar": scene_roar, "golem_slam": scene_slam,
    "golem_boulder": scene_boulder, "golem_beam": scene_beam,
    "golem_hurt": scene_hurt, "golem_die": scene_die,
}


def build(name: str) -> List[Img]:
    n, _delay, _loop = TIMING[name]
    return [BUILDERS[name](f, n) for f in range(n)]


# ------------------------------------------------------------------- output
def write(name: str, out_dir: Path) -> Tuple[Path, List[Img]]:
    n, delay, loop = TIMING[name]
    frames = build(name)
    assert len(frames) == n, name
    path = dz.boss_dir() / f"{name}.vpea"
    save_vpea(path, SIZE, SIZE, [f.px for f in frames], delay, loop)
    w, h, buf = dz.concat(frames)
    encode_png_rgba(out_dir / f"{name}_strip.png", w, h, buf)
    return path, frames


def main(argv: Sequence[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--only", default="", help="comma list without the golem_ prefix")
    ap.add_argument("--scale", type=int, default=3, help="sheet zoom factor")
    ap.add_argument("--no-sheet", action="store_true")
    ap.add_argument("--out", default="", help="export folder (default: exports/boss)")
    args = ap.parse_args(argv)

    wanted = list(TIMING)
    if args.only:
        keys = {k.strip() for k in args.only.split(",") if k.strip()}
        wanted = [nm for nm in wanted if nm[6:] in keys]
    out_dir = Path(args.out) if args.out else export_dir(create=True) / "boss"
    out_dir.mkdir(parents=True, exist_ok=True)

    rows: List[Tuple[str, List[Img]]] = []
    total = 0
    for name in wanted:
        path, frames = write(name, out_dir)
        total += len(frames)
        rows.append((name, frames))
        n, delay, loop = TIMING[name]
        print(f"  {path.name}  {n}f {SIZE}x{SIZE} @{delay} ms loop={loop}")
    if not args.no_sheet:
        W, H, grid = dz.draw_sheet(rows, args.scale)
        sheet = export_dir(create=True) / "golem_sheet_all.png"
        encode_png_rgba(sheet, W, H, grid)
        print(f"  sheet {sheet.name}  {W}x{H}")
    print(f"  {len(wanted)} scenes, {total} frames -> {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
