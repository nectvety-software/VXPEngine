"""Draw an ice wizard boss as a playable .vpea set for the VPE library.

The third boss of `sprite/enemies/boss/`, after the dragon and the stone golem.
Where those two are bulk - membranes, slabs - this one is a silhouette of
cloth: a bell robe with a fur hem, a cone hood over a shadowed face, and a
frozen staff whose crystal holds the only warm light on the sprite.

  wizard_idle     4 f  160 ms  loop    bobs, robe sways, orbiting icicles turn
  wizard_walk     4 f  150 ms  loop    glides on the hem, frost kicks at the feet
  wizard_cast     5 f   90 ms  once   staff rises, crystal charges, shards converge
  wizard_bolt     6 f   80 ms  once   fires an icicle spear off the right column
  wizard_blizzard 6 f   70 ms  once   snow ring spins out and covers the frame
  wizard_freeze   6 f   90 ms  once   frost cone from the tip, ground ices over
  wizard_hurt     3 f  120 ms  once   recoil, pale flash, shards scatter
  wizard_die      6 f  150 ms  once   cracks, bursts into shards, broken staff

40 frames, all through one parametric `wizard()` pose function. Like the golem,
fills are laid down first and a single `rim()` pass borders their union, so a
body built from a dozen tapered runs keeps one outline colour - which also means
every part must own its own tone or it merges into the robe.

VPE reserves 0xFFFF as the transparent key, so highlights go through
``ms.safe_light`` and no palette constant is allowed to pack to it. Light from
the crystal is painted with `bleed()`, which refuses to touch the transparent
background. Randomness is seeded per scene name, so re-running is byte-identical.

Writes (new files only; the dragon and golem scenes are left alone):
  Documents\\VPE Pixel\\sprite\\enemies\\boss\\wizard_<action>.vpea
  Documents\\VPE Pixel\\exports\\boss\\<scene>_strip.png
  Documents\\VPE Pixel\\exports\\wizard_sheet_all.png   (review sheet)

Run from the repo root:
  python tools/make_wizard_anim.py [--only idle,freeze] [--scale 3] [--no-sheet]
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
PREFIX = "wizard_"

TIMING: Dict[str, Tuple[int, int, bool]] = {   # frames, delay ms, loop
    "wizard_idle": (4, 160, True),
    "wizard_walk": (4, 150, True),
    "wizard_cast": (5, 90, False),
    "wizard_bolt": (6, 80, False),
    "wizard_blizzard": (6, 70, False),
    "wizard_freeze": (6, 90, False),
    "wizard_hurt": (3, 120, False),
    "wizard_die": (6, 150, False),
}

# ----------------------------------------------------------------- palettes
ICE = {
    "robe": rgb(40, 62, 112),         # lit-facing cloth
    "robe2": rgb(26, 40, 76),         # shaded side, far sleeve
    "robe3": rgb(66, 98, 158),        # shoulder band catchlight
    "hood": rgb(52, 78, 132),
    "fur": rgb(212, 230, 242),        # hem and cuff trim
    "fur2": rgb(146, 174, 202),       # shaded fur
    "trim": rgb(96, 168, 210),        # sash and hood binding
    "skin": rgb(198, 172, 150),
    "pole": rgb(98, 98, 126),          # frozen wood - bright enough to read
    "pole2": rgb(156, 160, 188),
    "crystal": rgb(120, 212, 240),
    "crystal2": safe_light(rgb(188, 240, 252), 8),
    "crystal3": rgb(52, 122, 172),
    "eye": rgb(150, 238, 252),
    "face": rgb(14, 18, 30),          # the hood's shadow: never a rim fill
    "out": rgb(18, 24, 38),           # same rim as the other two bosses
}
# rim() borders the union of these, so two parts that share a tone read as one
FILLS = ("robe", "robe2", "robe3", "hood", "fur", "fur2", "trim", "skin",
         "pole", "pole2", "crystal", "crystal2", "crystal3")
FROST = (rgb(226, 244, 252), rgb(150, 214, 240), rgb(74, 140, 190),
         rgb(38, 76, 122))
PALE = rgb(214, 234, 246)             # hurt flash: the cloth goes white, not red

# --------------------------------------------------------------- geometry
# 48x48 = three tiles. The wizard owns the left two thirds and leaves the right
# column free so the spear, the cone and the blizzard can travel out of frame.
CXR = 17              # robe centre-line
ROBE_TOP = 20         # shoulder row
HEM = 43              # fur hem row
HEAD = (18, 12)       # hood centre
SHLDR = (19, 22)      # near shoulder; the far one is 7 px back
GRIP = (26, 28)       # where the near hand holds the staff
STAFF_L = 20          # grip to crystal tip, in px - long enough to clear the hood
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
    """A run that narrows from `w0` to `w1` - sleeves, cones, icicles."""
    steps = max(1, int(max(abs(x1 - x0), abs(y1 - y0))))
    for k in range(steps + 1):
        t = k / steps
        x, y = round(lerp(x0, x1, t)), round(lerp(y0, y1, t))
        w = max(1, round(lerp(w0, w1, t)))
        img.rect(x - w // 2, y - w // 2, w, w, c)


def pole(img: Img, x0: int, y0: int, x1: int, y1: int, c: int, lit: int) -> None:
    """A near-vertical staff: three texels wide per row, lit down its left edge."""
    steps = max(1, abs(y1 - y0))
    dark = darken(c, 0.62)
    for k in range(steps + 1):
        t = k / steps
        x, y = round(lerp(x0, x1, t)), round(lerp(y0, y1, t))
        img.rect(x, y, 3, 1, c)
        img.set(x, y, lit)
        img.set(x + 2, y, dark)


def shard(img: Img, x: int, y: int, length: int, ang: float, p: Dict) -> None:
    """An icicle: a fat enough triangle that `rim()` leaves ice inside the
    outline, with a lit spine down the middle."""
    a = math.radians(ang)
    tx, ty = round(x + math.cos(a) * length), round(y + math.sin(a) * length)
    bx, by = round(x - math.cos(a) * 2), round(y - math.sin(a) * 2)
    nx, ny = -math.sin(a), math.cos(a)
    w = max(2, length // 3)
    img.tri(tx, ty, round(bx + nx * w), round(by + ny * w),
            round(bx - nx * w), round(by - ny * w), p["crystal"])
    img.line(bx, by, tx, ty, p["crystal2"])
    img.line(round(bx + nx), round(by + ny), tx, ty, p["crystal2"])
    img.set(round(bx + nx * w), round(by + ny * w), p["crystal3"])
    img.set(round(bx - nx * w), round(by - ny * w), p["crystal3"])


def robe(img: Img, p: Dict, lean: int, hem: int, wave: float) -> None:
    """The bell: per-row widths that flare toward a fur hem that swings."""
    top = ROBE_TOP + p["dy"]
    for y in range(top, HEM + 1 + p["dy"]):
        t = (y - top) / max(1, HEM - top)
        w = round(4 + 5 * t * t + 2 * t)
        cx = CXR + round(lean * t * t) + round(wave * t * t * 3)
        img.rect(cx - w, y, w * 2 + 1, 1, p["robe"])
        img.rect(cx - w, y, 3, 1, p["robe3"])            # lit fold, light from L
        img.rect(cx + w - 2, y, 3, 1, p["robe2"])        # shaded fold, right
    hy = HEM + p["dy"]
    w = 11 + round(wave)
    img.rect(CXR + lean - w, hy, w * 2 + 1, 2, p["fur"])         # fur hem
    img.rect(CXR + lean - w, hy + 2, w * 2 + 1, 1, p["fur2"])
    for i in range(-w + 2, w - 1, 4):                            # hem tassels
        img.set(CXR + lean + i, hy + 1, p["fur2"])
    img.rect(CXR + round(lean * 0.4) - 6, top + 8, 13, 2, p["trim"])   # sash
    img.rect(CXR + round(lean * 0.4) - 6, top + 10, 4, 2, p["trim"])
    for y in range(top + 3, hy - 1, 4):                          # cloth folds
        img.line(CXR - 4, y, CXR - 6, y + 3, p["robe2"])
        img.line(CXR + 4, y + 1, CXR + 6, y + 4, p["robe2"])


def sleeve(img: Img, p: Dict, sx: int, sy: int, hx: int, hy: int,
           far: bool) -> None:
    """A wide cloth sleeve from shoulder to cuff; the hand pokes out of it."""
    col = p["robe2"] if far else p["robe"]
    taper(img, sx, sy, hx, hy, 9 if far else 10, 5, col)
    img.circle(hx, hy, 3, col, filled=True)
    if not far:
        img.line(sx - 4, sy + 1, hx - 2, hy - 3, p["robe3"])    # lit shoulder
    img.rect(hx - 3, hy - 1, 7, 3, p["fur2"] if far else p["fur"])   # fur cuff
    if not far:
        img.rect(hx - 1, hy + 2, 3, 2, p["skin"])               # knuckles
        img.set(hx, hy + 1, p["skin"])


def hood(img: Img, p: Dict, hx: int, hy: int, tilt: float) -> None:
    """Cone hood, fur lining, and a shadowed face opening. The order matters:
    the opening is painted before the lining that frames it, or the lining eats
    the eyes."""
    for i in range(12):                       # the cone, narrow at the crown
        y = hy - 10 + i
        w = max(1, round(lerp(1, 8, (i / 11) ** 1.35)))
        cx = hx + round(tilt * (i - 5) * 0.4)
        img.rect(cx - w, y, w * 2 + 1, 1, p["hood"])
        img.rect(cx - w, y, 2, 1, p["robe3"])
    img.circle(hx + 1, hy + 3, 6, p["hood"], filled=True)       # cowl over the back
    img.rect(hx - 4, hy - 3, 9, 6, p["face"])                   # the opening
    for dx in (-6, 4):
        img.rect(hx + dx, hy - 2, 2, 5, p["fur"])               # fur lining
    img.rect(hx - 6, hy - 5, 13, 1, p["trim"])                  # brow binding
    img.rect(hx - 7, hy + 3, 15, 3, p["fur"])                   # fur brim
    img.rect(hx - 7, hy + 6, 15, 1, p["fur2"])
    for dx in (-7, 6):
        img.set(hx + dx, hy + 2, p["fur2"])                     # lining tufts
    img.rect(hx - 8, hy + 7, 17, 2, p["trim"])                  # collar band


def crystal(img: Img, p: Dict, x: int, y: int, r: int, level: int) -> None:
    """The staff head: a diamond of ice, brightened outward by `level`."""
    for i in range(-r, r + 1):
        w = max(1, r - abs(i))
        img.rect(x - w, y + i, w * 2 + 1, 1,
                 p["crystal"] if i < 0 else p["crystal3"])
    img.rect(x - max(1, r // 2), y - 1, r, 2, p["crystal2"])
    img.set(x, y - r, p["crystal2"])
    img.line(x - r, y, x - 1, y, p["crystal2"])
    if level >= 2:
        for k in range(4):
            a = math.radians(45 + k * 90)
            img.set(round(x + math.cos(a) * (r + 2)),
                    round(y + math.sin(a) * (r + 2)), p["crystal"])


def staff(img: Img, p: Dict, ang: float, level: int) -> Tuple[int, int]:
    """Draw the whole staff from the grip and return the crystal tip."""
    a = math.radians(ang)
    gx, gy = GRIP[0], GRIP[1] + p["dy"]
    tx, ty = round(gx + math.cos(a) * STAFF_L), round(gy + math.sin(a) * STAFF_L)
    bx, by = round(gx - math.cos(a) * 6), round(gy - math.sin(a) * 6)
    pole(img, bx, by, tx, ty + 3, p["pole"], p["pole2"])
    for k in (0.35, 0.62):                                 # ice bindings
        x, y = round(lerp(bx, tx, k)), round(lerp(by, ty, k))
        img.rect(x - 1, y, 5, 2, p["crystal3"])
        img.set(x, y, p["crystal"])
    img.rect(tx - 2, ty + 3, 7, 2, p["pole2"])             # collar under the head
    crystal(img, p, tx, ty, 4 + (level >= 3), level)
    return tx, ty


def eyes(img: Img, p: Dict, hx: int, hy: int, look: str) -> None:
    """Painted after rim(), so nothing outlines the glow."""
    if look == "shut":
        img.line(hx - 3, hy, hx - 1, hy, p["crystal3"])
        img.line(hx + 1, hy, hx + 3, hy, p["crystal3"])
        return
    bright = p["eye"] if look != "glow" else safe_light(p["eye"], 10)
    if look == "glow":
        bleed(img, hx, hy, 2, (safe_light(p["eye"], 4), p["crystal3"]))
    for dx in (-3, 1):
        img.rect(hx + dx, hy - 1, 3, 2, bright)
        img.set(hx + dx + 1, hy - 1, safe_light(p["eye"], 18))


def orbit(img: Img, p: Dict, phase: float, radius: float, n: int = 3) -> None:
    """Icicles turning over the hood. They sweep the upper arc only: the full
    circle put them level with the hat brim, where they read as shoulder pads."""
    for k in range(n):
        a = math.radians(205 + (phase + k * 40) % 90)
        x = round(HEAD[0] + math.cos(a) * radius)
        y = round(HEAD[1] + p["dy"] + math.sin(a) * radius * 0.75)
        if 2 < x < SIZE - 3 and 2 < y < SIZE - 3:
            shard(img, x, y, 6, math.degrees(a), p)


def rim(img: Img, p: Dict) -> None:
    """One outline pass around the union of the cloth and ice fills."""
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
    "dx": 0, "dy": 0, "hx": 0, "hy": 0, "eye": "open",
    "lean": 0, "wave": 0.0, "staff": -72, "level": 2, "phase": 90.0,
    "orbit": 13.0, "tilt": 0.0, "hand": (0, 0), "tint": 0.0, "tint_to": PALE,
    "crack": 0,
}


def pose(**kw) -> Dict:
    q = dict(BASE)
    q.update(kw)
    return q


def wizard(img: Img, p: Dict) -> Tuple[int, int]:
    """One boss frame from pose params - the only place the body is drawn."""
    c = dict(ICE)
    if p["tint"]:
        for key in FILLS:
            c[key] = dz.blend(c[key], p["tint_to"], p["tint"])
    c["dy"] = p["dy"]
    hx = HEAD[0] + p["hx"]
    hy = HEAD[1] + p["hy"] + p["dy"]
    far_sx, far_sy = SHLDR[0] - 7, SHLDR[1] + p["dy"] + 1
    sleeve(img, c, far_sx, far_sy, far_sx - 3 + p["hand"][0] // 2,
           far_sy + 7, True)
    robe(img, c, p["lean"], HEM, p["wave"])
    tx, ty = staff(img, c, p["staff"], p["level"])
    sleeve(img, c, SHLDR[0], SHLDR[1] + p["dy"],
           GRIP[0] + p["hand"][0], GRIP[1] + p["dy"] + p["hand"][1], False)
    hood(img, c, hx, hy, p["tilt"])
    if p["orbit"] > 0:
        orbit(img, c, p["phase"], p["orbit"])
    rim(img, c)
    eyes(img, c, hx, hy, p["eye"])
    if p["crack"]:
        cracks(img, c, p["crack"])
    return tx, ty


def cracks(img: Img, p: Dict, n: int) -> None:
    """Frost cracks climbing the robe: pale seams, brighter than the cloth."""
    rnd = jitter(f"crack{n}")
    for i in range(n):
        x = CXR - 6 + i * 4 + rnd.randint(-1, 1)
        y = HEM - 2
        for k in range(4 + i):
            y -= 1
            x += rnd.choice((-1, 0, 1))
            img.set(x, y, p["fur"] if k % 3 == 0 else p["crystal"])


def shift(src: Img, dx: int) -> Img:
    """Whole-frame offset for recoils and lunges."""
    if not dx:
        return src
    out = blank()
    for y in range(SIZE):
        for x in range(SIZE):
            col = src.px[y * SIZE + x]
            if col != WHITE:
                out.set(x + dx, y, col)
    return out


def stamp(p: Dict) -> Tuple[Img, Tuple[int, int]]:
    out = blank()
    tip = wizard(out, p)
    return shift(out, p["dx"]), (tip[0], tip[1])


# ------------------------------------------------------------------ effects
def frost(img: Img, row: int, count: int, seed: str) -> None:
    """Snow dust at the feet - the ice twin of the dragon's brown dust."""
    rnd = jitter(seed)
    for _ in range(count):
        x = rnd.randint(2, SIZE - 3)
        y = row + rnd.randint(-2, 0)
        img.set(x, y, FROST[0] if rnd.random() < 0.5 else FROST[1])


def snow(img: Img, x0: int, y0: int, w: int, h: int, count: int,
         seed: str) -> None:
    rnd = jitter(seed)
    for _ in range(count):
        img.set(x0 + rnd.randint(0, w - 1), y0 + rnd.randint(0, h - 1),
                FROST[rnd.randint(0, 1)])


def spear(img: Img, x: int, y: int, n: int) -> None:
    """The fired icicle: a ten-pixel shard with a bright head and a trail."""
    c = dict(ICE)
    img.tri(x + 9, y, x - 3, y - 3, x - 3, y + 2, c["crystal"])
    img.line(x - 3, y, x + 8, y, c["crystal2"])
    img.rect(x - 5, y - 1, 4, 3, c["fur"])                  # frozen muzzle
    for i in range(n):
        img.set(x - 8 - i * 3, y, FROST[min(2, i)])
        img.set(x - 8 - i * 3, y + 1, FROST[3])


def cone(img: Img, x0: int, y0: int, length: int, spread: int,
         seed: str) -> None:
    """Frost breath from the crystal: pale core, widening blue edge, spicules."""
    if length <= 0:
        return
    rnd = jitter(seed)
    for i in range(length):
        t = i / max(1, length - 1)
        x = x0 + i
        h = max(1, round(spread * (0.30 + 0.70 * t)))
        wob = rnd.randint(-1, 1) if t > 0.4 else 0
        for k in range(-h, h + 1):
            d = abs(k) / max(1, h)
            y = y0 + k + wob + round(t * 3)
            c = FROST[0] if d < 0.28 else FROST[1] if d < 0.6 else FROST[2]
            if d >= 0.92 and rnd.random() < 0.35:
                continue                       # ragged outer edge
            img.set(x, y, c)
        if i % 4 == 0:
            shard(img, x, y0 - h, 3 + rnd.randint(0, 2), -90, ICE)
            shard(img, x, y0 + h, 3 + rnd.randint(0, 2), 90, ICE)


def iceover(img: Img, row: int, n: int) -> None:
    """The frozen floor: a pale band with icicles standing up out of it."""
    c = dict(ICE)
    img.rect(2, row, SIZE - 4, 2, FROST[2])
    img.line(2, row, SIZE - 5, row, FROST[1])
    for k in range(n):
        x = 4 + k * 4
        h = 2 + (k % 3)
        img.tri(x, row - h, x - 1, row + 1, x + 2, row + 1, c["crystal"])
        img.set(x, row - h, c["crystal2"])


# ------------------------------------------------------------------- scenes
def scene_idle(f: int, n: int) -> Img:
    img, (tx, ty) = stamp(pose(dy=(0, -1, 0, 1)[f], hy=(0, -1, 0, 1)[f],
                               wave=(0.0, 0.6, 0.0, -0.6)[f],
                               lean=(0, 0, 1, 0)[f],
                               staff=(-72, -68, -72, -76)[f],
                               level=(2, 3, 3, 2)[f],
                               phase=(90, 116, 142, 168)[f],
                               eye="shut" if f == 2 else "open"))
    if f in (1, 2):
        bleed(img, tx, ty, 5, (ICE["crystal2"], ICE["crystal"], ICE["crystal3"]))
    return img


def scene_walk(f: int, n: int) -> Img:
    img, _ = stamp(pose(dy=(0, 1, 0, 1)[f], hy=(0, 1, 0, 1)[f],
                        lean=(-1, 0, 1, 0)[f],
                        wave=(0.8, 0.2, -0.8, -0.2)[f],
                        staff=(-68, -64, -60, -64)[f],
                        phase=(90, 120, 150, 180)[f],
                        hand=((0, 0), (0, -1), (0, 0), (0, 1))[f],
                        level=(2, 2, 3, 2)[f]))
    frost(img, FOOT + 1, 6, f"walk{f}")
    return img


def scene_cast(f: int, n: int) -> Img:
    img, (tx, ty) = stamp(pose(dy=(0, -1, -2, -1, 0)[f], hy=(0, -1, -2, -2, -1)[f],
                               lean=(0, -1, -2, -1, 0)[f],
                               wave=(0.0, -0.5, -0.9, -0.5, 0.2)[f],
                               staff=(-72, -80, -88, -84, -52)[f],
                               hand=((0, 0), (0, -2), (0, -4), (0, -3), (0, 0))[f],
                               level=(1, 2, 3, 3, 2)[f], eye="glow",
                               orbit=(13, 11, 9, 7, 10)[f],
                               phase=(90, 122, 154, 186, 218)[f]))
    if f >= 1:
        bleed(img, tx, ty, 2 + 2 * f,
              (ICE["crystal2"], ICE["crystal"], ICE["crystal3"]))
    if f >= 2:
        snow(img, tx - 6, ty - 6, 13, 13, 6 * (f - 1), f"cast{f}")
    if f == 4:
        frost(img, FOOT, 6, "castdust")
    return img


def scene_bolt(f: int, n: int) -> Img:
    pos = (None, None, (32, 12), (38, 11), (44, 11), None)[f]
    img, (tx, ty) = stamp(pose(dy=(0, -1, 1, 1, 0, 0)[f],
                               lean=(0, -1, 2, 2, 1, 0)[f],
                               wave=(0.0, -0.4, 0.7, 0.5, 0.0, 0.0)[f],
                               staff=(-72, -78, -82, -80, -76, -70)[f],
                               hand=((0, 0), (0, -2), (2, -1), (1, 0), (0, 0),
                                     (0, 0))[f],
                               level=(2, 3, 3, 2, 2, 1)[f],
                               eye="glow" if f in (2, 3) else "open",
                               phase=90 + 20 * f))
    if pos:
        spear(img, pos[0], pos[1], 3 if f < 4 else 5)
    if f == 2:
        bleed(img, tx, ty, 7, (ICE["crystal2"], ICE["crystal"], ICE["crystal3"]))
    return img


def scene_blizzard(f: int, n: int) -> Img:
    img, (tx, ty) = stamp(pose(dy=(0, -1, -1, 0, 0, 0)[f],
                               hy=(0, -1, -1, 0, 0, 0)[f],
                               staff=(-72, -84, -90, -90, -84, -74)[f],
                               hand=((0, 0), (0, -2), (0, -4), (0, -4),
                                     (0, -2), (0, 0))[f],
                               level=(2, 3, 3, 3, 2, 2)[f], eye="glow",
                               orbit=(13, 15, 17, 18, 16, 13)[f],
                               phase=90 + f * 55, wave=(0, 0.4, -0.4, 0.8, 0, 0)[f]))
    r = (0, 8, 14, 19, 22, 24)[f]
    if r:
        for k in range(28):
            a = math.radians(k * 360 / 28 + f * 14)
            x = round(CXR + 2 + math.cos(a) * r)
            y = round(26 + math.sin(a) * r * 0.66)
            if 1 <= x < SIZE - 1 and 1 <= y < SIZE - 1:
                img.set(x, y, FROST[k % 3])
                img.set(x + 1, y, FROST[1] if k % 2 else FROST[0])
    if f >= 2:
        snow(img, 1, 1, SIZE - 2, SIZE - 2, 10 * (f - 1), f"bliz{f}")
    if f >= 4:
        iceover(img, FOOT + 1, 6)
    return img


def scene_freeze(f: int, n: int) -> Img:
    length = (0, 6, 12, 16, 14, 7)[f]
    img, (tx, ty) = stamp(pose(dy=(0, -1, -1, -1, -1, 0)[f],
                               lean=(0, -1, -1, -1, 0, 0)[f],
                               wave=(0, -0.4, -0.6, -0.6, -0.3, 0.2)[f],
                               staff=(-72, -80, -86, -84, -80, -74)[f],
                               hand=((0, 0), (0, -1), (0, -2), (0, -2), (0, -1),
                                     (0, 0))[f],
                               level=(1, 2, 3, 3, 2, 1)[f], eye="glow",
                               phase=90 + 25 * f))
    if length:
        cone(img, tx + 3, ty + 1, length, (0, 3, 6, 8, 7, 4)[f], f"freeze{f}")
    if f >= 3:
        iceover(img, FOOT + 1, (0, 0, 0, 5, 9, 11)[f])
    if f == 3:
        ea.star4(img, tx + length + 4, ty + 4, 4, ICE["crystal2"])
    return img


def scene_hurt(f: int, n: int) -> Img:
    img, (tx, ty) = stamp(pose(dx=(0, -3, -1)[f], dy=(0, 1, 0)[f],
                               hx=(0, -2, -1)[f], hy=(0, -1, 1)[f],
                               lean=(0, 2, 1)[f], wave=(0, -0.8, -0.3)[f],
                               eye=("open", "shut", "glow")[f],
                               tint=(0.0, 0.24, 0.08)[f],
                               level=(2, 1, 2)[f], crack=(0, 2, 1)[f],
                               staff=(-72, -54, -66)[f],
                               orbit=(13, 16, 13)[f], phase=90 + 30 * f))
    if f:
        rnd = jitter(f"hurts{f}")
        for _ in range(7 if f == 1 else 4):
            x = CXR + rnd.randint(-9, 11)
            y = 18 + rnd.randint(-8, 14)
            img.set(x, y, FROST[rnd.randint(0, 1)])
            if rnd.random() < 0.5:
                shard(img, x, y, 3, rnd.randint(0, 359), ICE)
    return img


def scene_die(f: int, n: int) -> Img:
    if f >= 4:                        # the cloth is gone: shards and a staff
        img = blank()
        remains(img, f)
        return img
    img, (tx, ty) = stamp(pose(dx=(0, -2, -3, -3)[f], dy=(0, 1, 2, 3)[f],
                               hx=(0, -2, -3, -3)[f], hy=(0, 1, 3, 4)[f],
                               lean=(0, 2, 4, 5)[f],
                               wave=(0, -0.6, -1.0, -1.0)[f],
                               eye=("open", "shut", "shut", "shut")[f],
                               tint=(0.08, 0.22, 0.38, 0.52)[f],
                               level=(2, 1, 1, 0)[f], crack=(1, 3, 5, 6)[f],
                               staff=(-72, -60, -44, -30)[f],
                               orbit=(13, 14, 16, 0)[f], phase=90 + 45 * f))
    if f >= 2:
        rnd = jitter(f"dies{f}")
        for _ in range(8 * (f - 1)):
            x = CXR + rnd.randint(-12, 14)
            y = 14 + rnd.randint(-10, 26)
            if 1 <= x < SIZE - 1 and 1 <= y < SIZE - 1:
                img.set(x, y, FROST[rnd.randint(0, 1)])
    if f == 3:
        dz.shock(img, CXR + 2, FOOT - 2, 16, FROST[1])
    return img


def remains(img: Img, f: int) -> None:
    """What is left: an ice pool, the shards the robe burst into, the staff."""
    c = dict(ICE)
    rnd = jitter(f"remains{f}")
    img.ellipse(CXR + 2, FOOT - 1, 15, 5, FROST[2], filled=True)
    img.ellipse(CXR + 2, FOOT - 2, 11, 3, FROST[1], filled=True)
    img.line(CXR - 10, FOOT - 5, CXR + 14, FOOT - 5, FROST[0])
    for x, y, w, h in ((5, FOOT - 4, 6, 3), (29, FOOT - 3, 7, 2)):
        img.rect(x, y, w, h, c["robe2"])            # torn cloth sunk in the ice
        img.line(x, y, x + w - 1, y, c["robe"])
    img.tri(CXR - 4, FOOT - 10, CXR - 10, FOOT - 3, CXR + 1, FOOT - 4,
            c["hood"])                              # the hood, collapsed
    img.line(CXR - 10, FOOT - 4, CXR + 1, FOOT - 4, c["fur"])
    for x, h in ((9, 11), (16, 16), (23, 9), (28, 14), (34, 7)):
        img.tri(x, FOOT - 5 - h, x - 2, FOOT - 4, x + 2, FOOT - 4, c["crystal"])
        img.line(x, FOOT - 5 - h, x - 1, FOOT - 9, c["crystal2"])
    pole(img, 31, FOOT - 1, 43, FOOT - 5, c["pole"], c["pole2"])   # snapped shaft
    crystal(img, c, 44, FOOT - 6, 3, 1)                            # dead tip
    for _ in range(34 - 9 * (f - 4)):      # the shatter field, settling
        x = CXR + rnd.randint(-16, 20)
        y = 14 + rnd.randint(-10, 28)
        if 1 <= x < SIZE - 1 and 1 <= y < SIZE - 1:
            img.set(x, y, FROST[rnd.randint(0, 1)])
            if rnd.random() < 0.4:
                shard(img, x, y, 4, rnd.randint(0, 359), c)
    rim(img, c)
    snow(img, 2, 2, SIZE - 4, 24, 14, f"remainsnow{f}")


BUILDERS = {
    "wizard_idle": scene_idle, "wizard_walk": scene_walk,
    "wizard_cast": scene_cast, "wizard_bolt": scene_bolt,
    "wizard_blizzard": scene_blizzard, "wizard_freeze": scene_freeze,
    "wizard_hurt": scene_hurt, "wizard_die": scene_die,
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
        sheet = export_dir(create=True) / "wizard_sheet_all.png"
        encode_png_rgba(sheet, W, H, grid)
        print(f"  sheet {sheet.name}  {W}x{H}")
    print(f"  {len(wanted)} scenes, {total} frames -> {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
