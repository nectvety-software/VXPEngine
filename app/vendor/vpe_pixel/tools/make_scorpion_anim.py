"""Draw a sand scorpion boss as a playable .vpea set for the VPE library.

The fifth boss of `sprite/enemies/boss/`, after the dragon, the stone golem, the
ice wizard and the slime king. All four of those are vertical silhouettes - the
golem and the wizard stand on two legs, the dragon on four, the slime on none -
so this one is the opposite shape: low, wide and eight-legged, a domed carapace
over a segmented abdomen, two hinged claws out front and a thin five-plate tail
arched up from the rear and hanging over the head with a venom barb on the end.
It reads as a horizontal silhouette in a set of vertical ones - and it faces
right, so its own attacks leave through the right column while the tail works
the upper left.

  scorpion_idle   4 f  160 ms  loop   body settles, tail sways, claws open and shut
  scorpion_walk   4 f  140 ms  loop   alternate tripod steps, sand kicks at the feet
  scorpion_sting  5 f   80 ms  once   tail cocks back, whips over, barb drives down
  scorpion_pinch  4 f   90 ms  once   both claws lunge forward and snap shut
  scorpion_venom  6 f   70 ms  once   spurts green venom from the chelicerae
  scorpion_burrow 6 f   90 ms  once   sinks down, the sand level rises over it
  scorpion_hurt   3 f  120 ms  once   flinches back, all legs lift, tail whips up
  scorpion_die    6 f  160 ms  once   legs splay, the arch falls in, shell dries

38 frames, all through one parametric `scorpion()` pose function. The tail is
the interesting part: `curl` is not a scale but an *amount of turn* - each of
the five joints adds a share of a total sweep angle, so raising or lowering the
tail walks the barb along one arc instead of moving it around, which is what
keeps the sting readable without any per-frame coordinates.

Like the other bosses, fills go down first and a single `rim()` pass borders
their union, so a body built from a dozen tapered plates keeps one outline
colour. A union outline only separates parts that differ in *colour*, and a
scorpion is nothing but segments, so the tail plates alternate lit and mid
chitin with a dark ring at each joint, and the claws, legs and telson bulb each
own a tone. Sand, venom and eyes stay out of the fill set: dust must not be
outlined, and the glow is painted after the rim.

VPE reserves 0xFFFF as the transparent key, so highlights go through
``ms.safe_light`` and no palette constant is allowed to pack to it. Randomness
is seeded per scene name, so re-running is byte-identical.

Writes (new files only; the dragon, golem, slime and wizard scenes are untouched):
  Documents\\VPE Pixel\\sprite\\enemies\\boss\\scorpion_<action>.vpea
  Documents\\VPE Pixel\\exports\\boss\\<scene>_strip.png
  Documents\\VPE Pixel\\exports\\scorpion_sheet_all.png   (review sheet)

Run from the repo root:
  python tools/make_scorpion_anim.py [--only idle,sting] [--scale 3] [--no-sheet]
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

import make_dragon_anim as dz  # noqa: E402  (SIZE, lerp, blank, shock, sheet)
import make_effect_anim as ea  # noqa: E402  (star4)
from make_vqeaf_icons import encode_png_rgba  # noqa: E402
from vpx_editor.paths import export_dir  # noqa: E402
from vpx_editor.vpea import save_vpea  # noqa: E402
import make_samples as ms  # noqa: E402

Img, rgb, WHITE = ms.Img, ms.rgb, ms.WHITE
safe_light, darken = ms.safe_light, ms.darken
SIZE = dz.SIZE
lerp, blank = dz.lerp, dz.blank
PREFIX = "scorpion_"

TIMING: Dict[str, Tuple[int, int, bool]] = {   # frames, delay ms, loop
    "scorpion_idle": (4, 160, True),
    "scorpion_walk": (4, 140, True),
    "scorpion_sting": (5, 80, False),
    "scorpion_pinch": (4, 90, False),
    "scorpion_venom": (6, 70, False),
    "scorpion_burrow": (6, 90, False),
    "scorpion_hurt": (3, 120, False),
    "scorpion_die": (6, 160, False),
}

# ----------------------------------------------------------------- palettes
# Nine chitin tones, chosen so that no two neighbouring parts of the animal
# share one: `rim()` merges whatever it cannot tell apart.
CHITIN = {
    "plate": rgb(208, 152, 80),        # dorsal chitin, the lightest shell tone
    "shell": rgb(168, 112, 52),        # flanks, tail odd plates
    "mesa": rgb(142, 100, 58),         # abdomen plates, tail even plates
    "claw": rgb(190, 146, 82),         # pedipalp manus - pale, smooth, olive
    "claw2": rgb(108, 74, 42),         # far pedipalp, jaw hinges, barb root
    "legc": rgb(128, 76, 38),          # near walking legs, red-brown
    "dark": rgb(84, 52, 28),           # far legs, bellies
    "joint": rgb(54, 34, 22),          # the seam at each plate's front joint
    "spine": safe_light(rgb(232, 186, 116), 6),   # dorsal highlight, not 0xFFFF
    "eye": rgb(240, 96, 60),           # painted after rim(), so never a fill
    "out": rgb(18, 24, 38),            # same rim as the other three bosses
}
# rim() borders the union of these, so two parts that share a tone read as one
FILLS = ("plate", "shell", "mesa", "claw", "claw2", "legc", "dark", "joint",
         "spine")
# hurt/die tint only the bright tones: bleaching the seams away is what turned
# an early draft into a shapeless blob.
TINTS = ("plate", "shell", "mesa", "claw", "legc", "spine")
SANDT = (rgb(226, 206, 166), rgb(196, 168, 120), rgb(152, 126, 86),
         rgb(112, 92, 62))            # the dune: never rimmed
VENOMT = (safe_light(rgb(200, 250, 158), 6), rgb(120, 222, 96),
          rgb(56, 150, 62), rgb(26, 84, 42))
FLASH = rgb(238, 214, 176)            # hurt: chitin bleaches, it does not redden
DEAD = rgb(78, 56, 42)                # die: the husk goes dry and dark

# --------------------------------------------------------------- geometry
# 48x48 = three tiles. The animal lies along the bottom two tiles: abdomen at
# the left, head and claws at the right, and the tail arch works the upper-left
# quadrant, which is the only room an eight-legged boss leaves itself.
BODY = (21, 33)          # carapace/abdomen junction, the body's centre
TAIL_ROOT = (10, 33)     # where the metasoma leaves the rear of the abdomen
HEAD = (32, 36)          # chelicerae block, hung below the carapace's front
CLAW_NEAR = (27, 29)     # near pedipalp coxa, on the front shoulder
CLAW_FAR = (25, 32)      # far coxa, under the carapace lip
NEAR_HIPS = (26, 22, 18, 14)     # near leg hips, front to back
NEAR_SPREAD = (10, 5, -4, -9)    # how far each foot splays from its hip
FAR_HIPS = (23, 16)
FAR_SPREAD = (6, -6)
FOOT = 44


def jitter(seed: str) -> random.Random:
    return random.Random(seed)


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


def taper(img: Img, x0: int, y0: int, x1: int, y1: int, w0: float,
          w1: float, c: int) -> None:
    """A run that narrows from `w0` to `w1` - jaws, shins, the barb."""
    steps = max(1, int(max(abs(x1 - x0), abs(y1 - y0))))
    for k in range(steps + 1):
        t = k / steps
        x, y = round(lerp(x0, x1, t)), round(lerp(y0, y1, t))
        w = max(1, round(lerp(w0, w1, t)))
        img.rect(x - w // 2, y - w // 2, w, w, c)


def limb(img: Img, pts: Sequence[Tuple[int, int]], r: int, c: int,
         seam: int = None) -> None:
    """A chain of discs through the joints, shrinking once along the run."""
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        steps = max(1, int(max(abs(x1 - x0), abs(y1 - y0))))
        for k in range(steps + 1):
            t = k / steps
            x, y = round(lerp(x0, x1, t)), round(lerp(y0, y1, t))
            rr = max(1, round(lerp(r, r - 1, t)))
            img.circle(x, y, rr, c, filled=True)
            if seam is not None:
                img.set(x, y - rr, seam)


def plate(img: Img, a: Tuple[float, float], b: Tuple[float, float],
          d0: float, d1: float, col: int) -> None:
    """One tapered chitin plate, drawn as a run of discs."""
    steps = max(1, int(round(max(abs(b[0] - a[0]), abs(b[1] - a[1])))))
    for k in range(steps + 1):
        t = k / steps
        x, y = round(lerp(a[0], b[0], t)), round(lerp(a[1], b[1], t))
        img.circle(x, y, max(1, round(lerp(d0, d1, t) / 2)), col, filled=True)


def tail(img: Img, p: Dict, c: Dict[str, int]) -> Tuple[Tuple[int, int],
                                                        Tuple[int, int]]:
    """The metasoma: five plates that leave the rear of the abdomen pointing up
    and back, then turn through a total sweep of `curl` and hang over the head.
    Returns the telson bulb and the barb tip."""
    sweep = lerp(60.0, 150.0, p["curl"])
    share = (0.12, 0.20, 0.24, 0.22, 0.22)
    runs = tuple(r * p["tlen"] for r in (4.0, 4.0, 5.0, 5.0, 5.0))
    shrink = lerp(0.82, 1.0, min(1.0, p["curl"]))
    a = math.radians(lerp(212.0, 232.0, p["curl"]) + p["swing"])
    x, y = float(TAIL_ROOT[0]), float(TAIL_ROOT[1] + p["dy"])
    pts: List[Tuple[float, float]] = [(x, y)]
    angs: List[float] = [a]
    for i in range(5):
        a += math.radians(sweep * share[i])
        x += math.cos(a) * runs[i] * shrink
        y += math.sin(a) * runs[i] * shrink
        pts.append((x, y))
        angs.append(a)
    widths = (4.8, 4.4, 3.9, 3.4, 2.9, 2.5)
    for i in range(5):
        plate(img, pts[i], pts[i + 1], widths[i], widths[i + 1],
              c["plate"] if i % 2 else c["mesa"])
    # seams, then one continuous lit edge and shaded belly edge: per-plate
    # highlights scattered into speckle at this size.
    for i in range(1, 5):
        img.circle(round(pts[i][0]), round(pts[i][1]),
                   max(1, round(widths[i] / 2) - 1), c["joint"], filled=True)
    for sign, col in ((1, c["spine"]), (-1, c["dark"])):
        edge = []
        for i in range(6):
            ta = angs[min(i, 4)]
            nx, ny = math.sin(ta) * sign, -math.cos(ta) * sign
            r = max(1, round(widths[i] / 2))
            edge.append((round(pts[i][0] + nx * r), round(pts[i][1] + ny * r)))
        for a0, b0 in zip(edge, edge[1:]):
            img.line(a0[0], a0[1], b0[0], b0[1], col)
    bx, by = round(pts[-1][0]), round(pts[-1][1])
    img.ellipse(bx, by, 3, 2, c["claw"], filled=True)             # the bulb
    img.line(bx - 2, by - 1, bx + 2, by - 1, c["plate"])
    img.set(bx - 2, by + 1, c["dark"])
    # The barb is two runs so it can hook: `barbl` lets a strike throw it a few
    # pixels further than an idle sway without redrawing the tail.
    a2 = angs[-1] + math.radians(p["tip"])
    hook = lerp(0.75, 0.30, min(1.0, (p["barbl"] - 6) / 8))
    kx, ky = round(bx + math.cos(a2) * (p["barbl"] * 0.45)), \
        round(by + math.sin(a2) * (p["barbl"] * 0.45))
    a3 = a2 + hook
    ex, ey = round(kx + math.cos(a3) * (p["barbl"] * 0.6)), \
        round(ky + math.sin(a3) * (p["barbl"] * 0.6))
    taper(img, bx, by, kx, ky, 4, 2, c["claw2"])
    taper(img, kx, ky, ex, ey, 2, 1, c["spine"])
    img.set(ex, ey, c["joint"])
    return (bx, by), (ex, ey)


def legs(img: Img, p: Dict, c: Dict[str, int], lifts: Sequence[int],
         stride: int, far: bool) -> None:
    """Arthropod legs: the coxa goes out and *up* to the knee, the tibia drops
    back to the floor, so the whole animal hangs under a set of arches."""
    hips = FAR_HIPS if far else NEAR_HIPS
    spread = FAR_SPREAD if far else NEAR_SPREAD
    hy = BODY[1] + 3 + p["dy"]
    col = c["dark"] if far else c["legc"]
    for i, hx in enumerate(hips):
        lift = lifts[i % len(lifts)]
        dx = spread[i % len(spread)] + stride * (1 if i < 2 else -1)
        kx = round(hx + dx * 0.5)
        ky = hy - 5 + (2 if far else 0)
        fx = round(hx + dx)
        fy = FOOT - lift + p["dy"]
        limb(img, [(hx, hy), (kx, ky)], 2, col, None if far else c["joint"])
        img.circle(kx, ky, 2, col, filled=True)
        taper(img, kx, ky, fx, fy, 3, 2, col)
        img.line(kx, ky - 2, fx, fy - 1, c["plate"] if not far else c["dark"])
        img.rect(fx - 1, fy, 3, 1, col)                           # the tarsus
        img.set(fx + 2, fy, c["joint"])                           # its claw tip


def claw(img: Img, p: Dict, c: Dict[str, int], far: bool) -> Tuple[int, int]:
    """One pedipalp: a short arm, a fat manus, then two long fingers hinged
    apart. The claws are the boss's face - at 48 px a pincer only reads as one
    if the fingers are nearly as big as the hand and clearly open.
    Returns the jaw point so effects can spark between the fingers."""
    ang = p["fang"] if not far else p["fang2"]
    bnd = p["fangb"] if not far else p["fangb2"]
    sx, sy = CLAW_FAR if far else CLAW_NEAR
    sy += p["dy"]
    col = c["claw2"] if far else c["claw"]
    a = math.radians(ang)
    ex, ey = round(sx + math.cos(a) * 3), round(sy + math.sin(a) * 3)
    b = math.radians(ang + bnd)
    mx, my = round(ex + math.cos(b) * 4), round(ey + math.sin(b) * 4)
    limb(img, [(sx, sy), (ex, ey)], 2, col, None if far else c["joint"])
    img.circle(ex, ey, 2, c["dark"], filled=True)
    plate(img, (ex, ey), (mx, my), 9, 7, col)                     # the manus
    img.line(ex, ey - 3, mx, my - 2, c["plate"] if not far else c["claw"])
    gap = lerp(0.0, 34.0, p["spread"])
    up = math.radians(ang + bnd - gap * 0.5)
    lo = math.radians(ang + bnd + gap * 0.5 + 3)
    ux, uy = round(mx + math.cos(up) * 7), round(my + math.sin(up) * 7)
    lx, ly = round(mx + math.cos(lo) * 6), round(my + math.sin(lo) * 6)
    taper(img, mx, my, ux, uy, 6, 2, c["plate"] if not far else col)
    taper(img, mx, my, lx, ly, 6, 2, col)
    img.line(mx, my, ux, uy, c["spine"] if not far else c["claw"])
    img.set(round((mx + lx) / 2) + 1, round((my + ly) / 2) + 1, c["joint"])
    img.set(ux, uy, c["joint"])
    img.set(lx, ly, c["joint"])
    img.circle(mx, my, 2, c["dark"], filled=True)                 # the hinge
    return round((ux + lx) / 2), round((uy + ly) / 2)


def body(img: Img, p: Dict, c: Dict[str, int]) -> None:
    """A wide segmented abdomen behind a smooth domed carapace: the mass the
    tail and the claws both have to read against."""
    dy = p["dy"]
    ax, ay = BODY[0] - 6, BODY[1] + 1 + dy
    img.ellipse(ax, ay, 9, 5, c["mesa"], filled=True)
    for i in range(4):                        # tergite seams
        x = ax - 6 + i * 4
        img.line(x, ay - 4, x - 1, ay + 4, c["joint"])
    img.line(ax - 8, ay + 4, ax + 8, ay + 4, c["dark"])
    img.line(ax - 7, ay - 4, ax + 6, ay - 4, c["plate"])
    cx, cy = BODY[0] + 4, BODY[1] - 1 + dy
    img.ellipse(cx, cy, 7, 5, c["plate"], filled=True)
    img.ellipse(cx + 1, cy + 2, 6, 3, c["shell"], filled=True)
    img.line(cx - 6, cy - 3, cx + 5, cy - 3, c["spine"])
    img.line(cx - 5, cy + 4, cx + 6, cy + 4, c["dark"])
    img.line(cx - 2, cy - 4, cx - 3, cy + 3, c["shell"])          # one suture
    img.set(cx + 4, cy - 2, c["mesa"])


def head(img: Img, p: Dict, c: Dict[str, int]) -> Tuple[int, int]:
    """A small block hung below the carapace's front edge, with chelicerae that
    nibble. The neck seam is what keeps it off the dome in one silhouette.
    Returns the mouth the venom comes out of."""
    hx, hy = HEAD[0], HEAD[1] + p["dy"]
    img.line(hx - 4, hy - 4, hx - 4, hy + 1, c["joint"])
    img.rect(hx - 3, hy - 3, 6, 6, c["shell"])
    img.rect(hx - 3, hy - 3, 6, 2, c["plate"])
    img.line(hx - 3, hy + 2, hx + 2, hy + 2, c["dark"])
    img.rect(hx + 2, hy - 2, 2, 4, c["mesa"])
    for i, dyy in enumerate((0, 3)):
        o = p["chew"] * (1 if i else -1)
        img.rect(hx + 4, hy + dyy - o, 3, 2, c["claw"])
        img.set(hx + 6, hy + dyy - o, c["joint"])
    return hx + 7, hy + 2


def eyes(img: Img, p: Dict, c: Dict[str, int]) -> None:
    """One median pair on the crown of the carapace plus a lateral down each
    slope - all single texels. Painted after rim(), so nothing outlines them,
    and a two-pixel glow is enough: a three-pixel disc read as a red sore.
    `hidden` is the burrow's last frames, when the head is already under sand."""
    if p["eye"] == "hidden":
        return
    hx, hy = HEAD[0], HEAD[1] + p["dy"]
    shut = p["eye"] == "shut"
    on = c["joint"] if shut else c["eye"]
    if p["eye"] == "glow":
        bleed(img, hx - 3, hy - 6, 1, (safe_light(c["eye"], 8),
                                       darken(c["eye"], 0.45)))
    img.set(hx - 4, hy - 6, c["joint"] if shut else safe_light(c["eye"], 10))
    img.set(hx - 2, hy - 6, on)
    img.set(hx - 6, hy - 3, on)
    img.set(hx + 1, hy - 2, on)


def mound(img: Img, p: Dict) -> int:
    """The sand level rising to swallow the boss. Two earlier attempts failed:
    a dome whose `ry` grew with `cover` filled the whole frame like a wall, and
    a smaller dome still left the buried tail floating above its own crest. A
    flat band with a rippled edge and one bump where the animal went in reads
    correctly at any height, because the surface is a line the boss can break.
    Not a fill, so buried parts drop out of `rim()` and the sand stays
    outline-free. Returns the crest row so a scene can skip effects that would
    land under it."""
    cover = p["cover"]
    if cover <= 0:
        return SIZE
    rnd = jitter(f"mound{cover}")
    surf = FOOT + 3 - round(cover * 0.62)
    bx, bump = BODY[0] + 2, max(0, 5 - cover // 7)
    top = []
    for x in range(SIZE):
        dip = round(bump * max(0.0, 1.0 - ((x - bx) / 7.0) ** 2))
        top.append(min(SIZE - 2, surf - dip + (1 if rnd.random() < 0.35 else 0)))
    for x, y in enumerate(top):
        img.line(x, y, x, SIZE - 1, SANDT[1])
        img.set(x, y, SANDT[0] if x % 4 != 2 else SANDT[1])
        if y + 1 < SIZE:
            img.set(x, y + 1, SANDT[0] if rnd.random() < 0.4 else SANDT[1])
    lo, hi = surf + 2, SIZE - 2
    if hi > lo:                                # only once the band is deep enough
        for y in range(surf + 6, SIZE):        # the shade under the surface
            img.line(0, y, SIZE - 1, y, SANDT[2])
        for x in range(0, SIZE, 2):            # break the band's hard edge
            img.set(x, surf + 5, SANDT[2])
            if x % 4 == 0:
                img.set(x + 1, surf + 6, SANDT[2])
        for _ in range(10):                    # ripple dashes on the flat sand
            x = rnd.randint(1, SIZE - 6)
            y = rnd.randint(lo, hi)
            img.line(x, y, x + rnd.randint(1, 3), y, SANDT[0])
    for _ in range(24):                         # grains scattered on the slope
        x = rnd.randrange(SIZE)
        if top[x] + 2 <= hi:
            img.set(x, rnd.randint(top[x] + 2, hi), SANDT[rnd.randint(1, 3)])
    return min(top)


def sand_dust(img: Img, row: int, count: int, seed: str) -> None:
    rnd = jitter(seed)
    for _ in range(count):
        x = rnd.randint(2, SIZE - 3)
        y = row + rnd.randint(-2, 0)
        img.set(x, y, SANDT[rnd.randint(0, 1)])


def burst(img: Img, cx: int, cy: int, n: int, spread: int, seed: str,
          cols: Sequence[int]) -> None:
    """A radial spray of droplets - venom off the barb, sand off a flinch."""
    rnd = jitter(seed)
    for _ in range(n):
        a = math.radians(rnd.randint(0, 359))
        d = rnd.randint(2, spread)
        img.set(round(cx + math.cos(a) * d), round(cy + math.sin(a) * d),
                cols[rnd.randint(0, len(cols) - 1)])


def spray(img: Img, x0: int, y0: int, length: int, spread: int,
          seed: str) -> None:
    """Venom from the chelicerae: a jet that sags as it travels. Filling every
    column made a solid green plank at the edge of the frame; a jet this size is
    droplets, dense at the mouth and breaking up the further it goes."""
    if length <= 0:
        return
    rnd = jitter(seed)
    for i in range(length):
        t = i / max(1, length - 1)
        x = x0 + i
        h = min(4, max(1, round(spread * (0.4 + 0.6 * t))))
        base = y0 + round(t * t * 7) + (rnd.randint(-1, 1) if t > 0.3 else 0)
        for k in range(-h, h + 1):
            if rnd.random() < 0.25 + 0.55 * t:      # the cone disintegrates
                continue
            d = abs(k) / max(1, h)
            img.set(x, base + k, VENOMT[0] if d < 0.3 else
                    VENOMT[1] if d < 0.62 else VENOMT[2])
    for _ in range(12):                          # the mist past the jet
        t = rnd.random()
        img.set(x0 + round(t * (length + 6)),
                y0 + round(t * t * 7) + rnd.randint(-spread, spread),
                VENOMT[rnd.randint(1, 2)])


def stain(img: Img, row: int) -> None:
    """Venom eaten into the sand. Two failed versions here - a clean rectangle
    and then a single straight line of mid-green, both of which read as a UI
    strip laid on the floor. A burn is patchy: a dark wet core with a broken,
    dithered edge and a few bright flecks where it is still fizzing."""
    rnd = jitter(f"stain{row}")
    img.ellipse(BODY[0] + 15, row, 7, 2, VENOMT[3], filled=True)
    for k in range(18):
        x = BODY[0] + 5 + k + rnd.randint(0, 1)
        img.set(x, row + rnd.randint(-1, 1), VENOMT[rnd.randint(2, 3)])
    for k in range(5):
        img.set(BODY[0] + 8 + k * 3 + rnd.randint(0, 1), row - 1, VENOMT[1])


BASE: Dict = {
    "dx": 0, "dy": 0, "cover": 0,
    "curl": 0.85, "swing": 0.0, "tip": 0.0, "barbl": 6.0, "tlen": 1.0,
    "fang": -16.0, "fangb": 26.0, "fang2": -34.0, "fangb2": 30.0,
    "spread": 0.45,
    "lifts": (0, 0, 0, 0), "stride": 0,
    "eye": "open", "chew": 0, "tint": 0.0, "tint_to": FLASH,
}


def pose(**kw) -> Dict:
    q = dict(BASE)
    q.update(kw)
    return q


def scorpion(img: Img, p: Dict) -> Dict[str, Tuple[int, int]]:
    """One boss frame from pose params - the only place the animal is drawn.
    Far limbs, body and head, then the tail over the top, then the near limbs,
    then rim()."""
    c = dict(CHITIN)
    if p["tint"]:
        for key in TINTS:
            c[key] = dz.blend(c[key], p["tint_to"], p["tint"])
    claw(img, p, c, True)
    legs(img, p, c, (0, 0, 0, 0), 0, True)
    body(img, p, c)
    mouth = head(img, p, c)
    # The tail goes over the top of the body, not under it: hung from the rear
    # and curving down in front of the carapace, it has to stay visible while it
    # strikes, and drawing it first buried the barb inside the shell.
    bulb, barb = tail(img, p, c)
    legs(img, p, c, p["lifts"], p["stride"], False)
    jaw = claw(img, p, c, False)
    crest = mound(img, p)
    rim(img, c)
    eyes(img, p, c)
    return {"bulb": bulb, "barb": barb, "jaw": jaw, "mouth": mouth,
            "crest": (BODY[0] + 2, crest)}


def rim(img: Img, p: Dict) -> None:
    """One outline pass around the union of the chitin fills."""
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


def shift(src: Img, dx: int) -> Img:
    """Whole-frame offset for lunges and recoils."""
    if not dx:
        return src
    out = blank()
    for y in range(SIZE):
        for x in range(SIZE):
            col = src.px[y * SIZE + x]
            if col != WHITE:
                out.set(x + dx, y, col)
    return out


def stamp(p: Dict) -> Tuple[Img, Dict[str, Tuple[int, int]]]:
    out = blank()
    a = scorpion(out, p)
    if p["dx"]:
        a = {k: (v[0] + p["dx"], v[1]) for k, v in a.items()}
    return shift(out, p["dx"]), a


# ------------------------------------------------------------------- scenes
def scene_idle(f: int, n: int) -> Img:
    img, a = stamp(pose(
        dy=(0, -1, 0, 1)[f],
        curl=(0.8, 0.9, 0.85, 0.75)[f],
        swing=(0.0, -6.0, 4.0, 0.0)[f],
        tip=(18.0, 6.0, 14.0, 26.0)[f],
        fang=(-14.0, -22.0, -18.0, -10.0)[f],
        fangb=(26.0, 20.0, 24.0, 30.0)[f],
        fang2=(-32.0, -40.0, -36.0, -28.0)[f],
        spread=(0.45, 0.7, 0.55, 0.3)[f],
        chew=(0, 0, 1, 0)[f],
        eye="shut" if f == 2 else "open",
    ))
    if f in (1, 2):
        bleed(img, a["barb"][0], a["barb"][1], 1, VENOMT[:2])
    if f == 3:
        sand_dust(img, FOOT + 1, 4, "idledust")
    return img


def scene_walk(f: int, n: int) -> Img:
    img, a = stamp(pose(
        dy=(0, 1, 0, 1)[f],
        stride=(-1, 0, 1, 0)[f],
        lifts=((1, 0, 1, 0), (0, 1, 0, 1), (1, 0, 0, 1), (0, 1, 1, 0))[f],
        curl=(0.72, 0.82, 0.88, 0.78)[f],
        swing=(-8.0, 0.0, 8.0, 0.0)[f],
        tip=(24.0, 12.0, 4.0, 16.0)[f],
        fang=(-6.0, -14.0, -10.0, 0.0)[f],
        fangb=(28.0, 22.0, 26.0, 18.0)[f],
        fang2=(-26.0, -34.0, -30.0, -22.0)[f],
        spread=(0.3, 0.2, 0.35, 0.2)[f],
        chew=(0, 1, 0, 1)[f],
    ))
    sand_dust(img, FOOT + 1, 8, f"walk{f}")
    if f == 2:
        dz.shock(img, BODY[0] + 2, FOOT + 1, 13, SANDT[2])
    return img


def arc(img: Img, cx: int, cy: int, r: int, a0: float, a1: float,
        col: int, n: int = 10) -> None:
    """A motion trail: dots along a circle segment, thinning out at the tail of
    the path. The sting needs one because the whip is over between two frames -
    without the smear the barb simply teleports from the top of the arch to the
    ground."""
    rnd = jitter(f"arc{cx}{cy}{r}{int(a0)}")
    for k in range(n):
        t = k / max(1, n - 1)
        if rnd.random() < 0.3 * t:
            continue
        a = math.radians(lerp(a0, a1, t))
        img.set(round(cx + math.cos(a) * r), round(cy + math.sin(a) * r), col)


def scene_sting(f: int, n: int) -> Img:
    dxs, dys = (0, 0, 1, 3, 2), (0, -2, 0, 2, 0)
    img, a = stamp(pose(
        dx=dxs[f],
        dy=dys[f],
        # `curl` stays under 1.0: past that the total sweep passes 170 deg and
        # the tail closes into a ring with a hole in the middle of the boss.
        curl=(0.62, 0.45, 0.98, 0.9, 0.8)[f],
        swing=(4.0, -10.0, -2.0, 22.0, 10.0)[f],
        tip=(16.0, -6.0, 18.0, 14.0, 22.0)[f],
        barbl=(6.0, 8.0, 9.0, 10.0, 6.0)[f],
        fang=(-22.0, -32.0, -18.0, -10.0, -14.0)[f],
        fangb=(30.0, 36.0, 24.0, 16.0, 22.0)[f],
        fang2=(-40.0, -48.0, -34.0, -24.0, -30.0)[f],
        spread=(0.8, 1.0, 0.5, 0.25, 0.45)[f],
        eye="glow" if f >= 1 else "open",
        lifts=((0, 0, 0, 0), (1, 1, 0, 0), (0, 0, 2, 2), (0, 1, 0, 1),
               (0, 0, 0, 0))[f],
    ))
    if f == 1:                                 # the gland fills: a wet bead
        bleed(img, a["bulb"][0], a["bulb"][1], 1, VENOMT[:2])
    if f in (2, 3):
        burst(img, a["barb"][0] + 1, a["barb"][1] + 1, 6, 4, f"sting{f}",
              VENOMT[1:3])
    if f == 3:
        bx, by = a["barb"]
        rx, ry = TAIL_ROOT[0] + dxs[f], TAIL_ROOT[1] + dys[f]
        r = max(6, round(math.hypot(bx - rx, by - ry)))
        end = math.degrees(math.atan2(by - ry, bx - rx))
        arc(img, rx, ry, r, end - 78.0, end - 10.0, VENOMT[2], 12)
        ea.star4(img, bx + 2, by + 2, 3, VENOMT[1])
        dz.shock(img, bx + 2, by + 4, 6, SANDT[0])
        sand_dust(img, FOOT, 12, f"sting{f}")
    if f == 4:
        sand_dust(img, FOOT, 6, "sting4")
    return img


def scene_pinch(f: int, n: int) -> Img:
    img, a = stamp(pose(
        dx=(0, 2, 3, 1)[f],
        dy=(0, -1, 1, 0)[f],
        fang=(-34.0, -12.0, 2.0, -16.0)[f],
        fangb=(38.0, 16.0, 6.0, 24.0)[f],
        fang2=(-46.0, -24.0, -10.0, -28.0)[f],
        fangb2=(40.0, 18.0, 8.0, 26.0)[f],
        spread=(0.95, 0.5, 0.0, 0.3)[f],
        curl=(0.78, 0.92, 0.85, 0.8)[f],
        swing=(0.0, -6.0, 5.0, 0.0)[f],
        eye="glow" if f == 2 else "open",
        lifts=((0, 0, 0, 0), (0, 1, 0, 1), (1, 0, 1, 0), (0, 0, 0, 0))[f],
    ))
    if f == 2:
        jx, jy = a["jaw"]
        ea.star4(img, jx + 1, jy, 4, SANDT[0])
        burst(img, jx + 1, jy, 6, 5, f"pinch{f}", SANDT[:2])
    if f >= 1:
        sand_dust(img, FOOT, 6, f"pinch{f}")
    return img


def scene_venom(f: int, n: int) -> Img:
    length = (0, 6, 12, 17, 14, 8)[f]
    img, a = stamp(pose(
        dx=(0, 0, -1, -1, 0, 1)[f],
        dy=(0, 1, 1, 0, -1, 0)[f],
        curl=(0.85, 0.62, 0.5, 0.6, 0.88, 0.95)[f],
        swing=(0.0, 8.0, 12.0, 8.0, 0.0, -4.0)[f],
        tip=(14.0, 24.0, 30.0, 22.0, 12.0, 8.0)[f],
        chew=(0, 1, 2, 2, 1, 0)[f],
        fang=(-8.0, 2.0, 6.0, 3.0, -6.0, -12.0)[f],
        fangb=(22.0, 28.0, 32.0, 26.0, 18.0, 16.0)[f],
        fang2=(-28.0, -18.0, -14.0, -18.0, -26.0, -32.0)[f],
        spread=(0.4, 0.8, 0.95, 0.7, 0.4, 0.3)[f],
        eye="glow" if f >= 1 else "open",
    ))
    if length:
        mx, my = a["mouth"]
        spray(img, mx + 1, my, length, (0, 3, 5, 7, 6, 4)[f], f"venom{f}")
    if f >= 4:
        stain(img, FOOT + 1)
    if f == 3:
        burst(img, a["mouth"][0] + 15, a["mouth"][1] + 5, 8, 6, "venom3",
              VENOMT[:3])
    return img


def scene_burrow(f: int, n: int) -> Img:
    """The sand level rises and the boss sinks behind it. `cover` drives a flat
    band rather than a dome, and the tail keeps its arch through the last frame
    so exactly one piece is left above the surface - that is the read of a
    burrowing scorpion, and it is also what the smoke test's floor of rim pixels
    per frame checks."""
    img, a = stamp(pose(
        dy=(0, 1, 2, 3, 4, 5)[f],
        cover=(0, 5, 10, 15, 21, 26)[f],
        curl=(0.8, 0.78, 0.76, 0.74, 0.72, 0.7)[f],
        swing=(0.0, 5.0, 9.0, 13.0, 16.0, 18.0)[f],
        tip=(12.0, 18.0, 24.0, 28.0, 30.0, 32.0)[f],
        fang=(-16.0, 4.0, 18.0, 28.0, 34.0, 38.0)[f],
        fangb=(26.0, 22.0, 18.0, 14.0, 12.0, 10.0)[f],
        fang2=(-34.0, -16.0, 0.0, 10.0, 16.0, 20.0)[f],
        spread=(0.5, 0.85, 0.4, 0.2, 0.0, 0.0)[f],
        lifts=((2, 0, 2, 0), (0, 2, 0, 2), (3, 1, 3, 1), (1, 3, 1, 3),
               (4, 2, 4, 2), (2, 4, 2, 4))[f],
        eye="hidden" if f >= 4 else ("shut" if f == 3 else "open"),
    ))
    rnd = jitter(f"burrow{f}")
    for _ in range(5 + 4 * f):           # sand thrown up by the digging legs
        x = rnd.randint(2, SIZE - 3)
        y = a["crest"][1] - 1 - rnd.randint(0, 3 + 2 * f)
        img.set(x, y, SANDT[rnd.randint(0, 2)])
    if f >= 4:                           # the tail is the last thing left up
        bx, by = a["barb"]
        img.set(bx + 1, by + 2, VENOMT[1])
        img.set(bx, by + 4, VENOMT[2])
    return img


def scene_hurt(f: int, n: int) -> Img:
    img, a = stamp(pose(
        dx=(0, -3, -1)[f],
        dy=(0, 2, 0)[f],
        curl=(0.9, 0.52, 0.72)[f],
        swing=(0.0, -18.0, 6.0)[f],
        tip=(14.0, -10.0, 20.0)[f],
        barbl=(6.0, 9.0, 7.0)[f],
        fang=(-18.0, -40.0, -28.0)[f],
        fangb=(28.0, 44.0, 36.0)[f],
        fang2=(-36.0, -52.0, -44.0)[f],
        fangb2=(34.0, 46.0, 40.0)[f],
        spread=(0.5, 1.0, 0.7)[f],
        lifts=((0, 0, 0, 0), (2, 2, 2, 2), (1, 2, 1, 2))[f],
        eye="shut" if f == 1 else "open",
        # Only a light bleach: past ~0.18 the lit tones reach FLASH together and
        # the animal loses every seam at once.
        tint=(0.0, 0.15, 0.06)[f],
    ))
    if f:
        burst(img, BODY[0], BODY[1] + (0, 2, 0)[f], 9 if f == 1 else 5, 12,
              f"hurts{f}", SANDT[:2])
    if f == 1:
        dz.shock(img, BODY[0], FOOT + 1, 15, SANDT[1])
    return img


def scene_die(f: int, n: int) -> Img:
    """A collapse, not a redrawn corpse. Every frame goes through `scorpion()`,
    so the last pose is the same animal with its arch let go. Two dead ends on
    the way here: a separately drawn belly-up husk read as a pile of rocks, and
    simply lowering `curl`, whose arc still swings the tail forward over the
    head so the corpse loses its face. So the tail also *shortens* (`tlen`) -
    joints drying stiff - and settles behind the shoulder while the claws drop
    flat and the legs splay."""
    img, _ = stamp(pose(
        dx=(0, -2, -3, -4, -4, -4)[f],
        # `dy` moves the whole animal, feet included, so a big value walks the
        # legs out of the frame and leaves a legless blob. The sink is mostly
        # the arch coming down; the body only drops a few pixels.
        dy=(0, 1, 2, 3, 4, 4)[f],
        curl=(0.72, 0.6, 0.54, 0.48, 0.44, 0.42)[f],
        swing=(0.0, 4.0, 6.0, 8.0, 10.0, 10.0)[f],
        tlen=(1.0, 0.92, 0.82, 0.72, 0.6, 0.55)[f],
        tip=(16.0, 26.0, 34.0, 42.0, 50.0, 52.0)[f],
        barbl=(6.0, 6.0, 5.0, 4.0, 3.0, 3.0)[f],
        fang=(-12.0, 6.0, 20.0, 30.0, 42.0, 46.0)[f],
        fangb=(24.0, 28.0, 30.0, 26.0, 22.0, 20.0)[f],
        fang2=(-30.0, -14.0, 0.0, 10.0, 20.0, 24.0)[f],
        spread=(0.4, 0.15, 0.05, 0.0, 0.0, 0.0)[f],
        # The legs twitch up, then go slack and splay: the last frame has them
        # planted wide, so the corpse lies on the ground instead of tiptoeing.
        lifts=((0, 0, 0, 0), (2, 1, 2, 1), (4, 3, 4, 3), (5, 4, 5, 4),
               (3, 5, 3, 5), (0, 0, 0, 0))[f],
        eye=("open", "shut", "shut", "shut", "shut", "shut")[f],
        tint=(0.08, 0.16, 0.26, 0.32, 0.36, 0.38)[f],
        tint_to=DEAD,
    ))
    if f >= 1:
        sand_dust(img, FOOT, 6 * f, f"die{f}")
    if f == 3:
        dz.shock(img, BODY[0] - 2, FOOT + 1, 17, SANDT[1])
    return img


BUILDERS = {
    "scorpion_idle": scene_idle, "scorpion_walk": scene_walk,
    "scorpion_sting": scene_sting, "scorpion_pinch": scene_pinch,
    "scorpion_venom": scene_venom, "scorpion_burrow": scene_burrow,
    "scorpion_hurt": scene_hurt, "scorpion_die": scene_die,
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
    ap.add_argument("--only", default="", help=f"comma list without the {PREFIX} prefix")
    ap.add_argument("--scale", type=int, default=3, help="sheet zoom factor")
    ap.add_argument("--no-sheet", action="store_true")
    ap.add_argument("--out", default="", help="export folder (default: exports/boss)")
    args = ap.parse_args(argv)

    wanted = list(TIMING)
    if args.only:
        keys = {k.strip() for k in args.only.split(",") if k.strip()}
        wanted = [nm for nm in wanted if nm[len(PREFIX):] in keys]
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
        sheet = export_dir(create=True) / "scorpion_sheet_all.png"
        encode_png_rgba(sheet, W, H, grid)
        print(f"  sheet {sheet.name}  {W}x{H}")
    print(f"  {len(wanted)} scenes, {total} frames -> {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
