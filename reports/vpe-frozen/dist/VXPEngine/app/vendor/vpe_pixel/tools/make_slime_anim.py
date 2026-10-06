"""Draw a slime king boss as a playable .vpea set for the VPE library.

The fourth boss of `sprite/enemies/boss/`, after the dragon, the golem and the
ice wizard. The three before it are articulated - joints, limbs, props - so this
one is deliberately the opposite: a single jelly mass with a stolen crown on top,
squashing, stretching and wobbling as one body, with the gem it is digesting
still floating inside it.

  slime_idle     4 f  160 ms  loop    the mass jiggles, the crown bobs
  slime_hop      4 f  140 ms  loop    squash, launch, stretch, land flat
  slime_slide    4 f  150 ms  loop    travels low, the wake dragging behind
  slime_attack   4 f   90 ms  once   rears back, throws a pseudopod slam
  slime_split    5 f  100 ms  once   pinches into two smaller slimes
  slime_spit     6 f   80 ms  once   fires acid globs down the right column
  slime_hurt     3 f  120 ms  once   dents inward, droplets spray
  slime_die      6 f  150 ms  once   shrinks, crown slips off, dissolves to a pool

36 frames. The mass is drawn by one `body()` shape function that walks rows and
derives each row's half-width from a superellipse plus wobble harmonics, so every
scene deforms the same creature instead of redrawing it. The union `rim()` pass
the other bosses use still borders it, which is why the jelly carries three tones
(`body`, `body2`, `edge`) before any highlight is painted.

VPE reserves 0xFFFF as the transparent key, so the shine goes through
``ms.safe_light`` and no palette constant is allowed to pack to it. Randomness is
seeded per scene name, so re-running is byte-identical.

Writes (new files only; the other three boss sets are left alone):
  Documents\\VPE Pixel\\sprite\\enemies\\boss\\slime_<action>.vpea
  Documents\\VPE Pixel\\exports\\boss\\<scene>_strip.png
  Documents\\VPE Pixel\\exports\\slime_sheet_all.png    (review sheet)

Run from the repo root:
  python tools/make_slime_anim.py [--only hop,split] [--scale 3] [--no-sheet]
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
from make_vqeaf_icons import encode_png_rgba  # noqa: E402
from vpx_editor.paths import export_dir  # noqa: E402
from vpx_editor.vpea import save_vpea  # noqa: E402
import make_samples as ms  # noqa: E402

Img, rgb, WHITE = ms.Img, ms.rgb, ms.WHITE
safe_light, darken = ms.safe_light, ms.darken
SIZE = dz.SIZE
lerp, blank = dz.lerp, dz.blank
PREFIX = "slime_"

TIMING: Dict[str, Tuple[int, int, bool]] = {   # frames, delay ms, loop
    "slime_idle": (4, 160, True),
    "slime_hop": (4, 140, True),
    "slime_slide": (4, 150, True),
    "slime_attack": (4, 90, False),
    "slime_split": (5, 100, False),
    "slime_spit": (6, 80, False),
    "slime_hurt": (3, 120, False),
    "slime_die": (6, 150, False),
}

# ----------------------------------------------------------------- palettes
JELLY = {
    "body": rgb(96, 190, 108),         # the lit mass
    "body2": rgb(58, 132, 78),         # its lower half, thick with sediment
    "edge": rgb(34, 92, 56),           # the dense skin at the silhouette
    "hi": safe_light(rgb(176, 234, 170), 8),
    "hi2": safe_light(rgb(222, 248, 214), 6),
    "core": rgb(246, 226, 120),        # the gem it is slowly dissolving
    "gem": rgb(226, 196, 92),          # ... the same gold seen through jelly
    "gem2": rgb(168, 126, 40),
    "gold": rgb(228, 178, 56),         # the crown
    "gold2": rgb(150, 106, 26),
    "gold3": safe_light(rgb(248, 224, 140), 8),
    "acid": rgb(178, 234, 84),         # spit and droplets
    "acid2": rgb(118, 182, 50),
    "eye": rgb(24, 22, 30),
    "mouth": rgb(26, 58, 38),
    "out": rgb(18, 24, 38),            # same rim as the other three bosses
}
# rim() borders the union of these, so the jelly needs its own three tones or the
# silhouette collapses into one flat green disc
FILLS = ("body", "body2", "edge", "hi", "hi2", "core", "gem", "gem2",
         "gold", "gold2", "gold3", "acid", "acid2")
BLEACH = rgb(226, 246, 214)            # hurt: the mass goes pale, not red
MUD = rgb(52, 74, 58)                  # die: it loses its colour as it drains

# --------------------------------------------------------------- geometry
# 48x48 = three tiles. The king sits on the left two thirds and the right column
# stays free for the spit to travel out of.
CX, CY = 20, 31       # centre of the resting mass
RX, RY = 14, 11       # its half radii
GROUND = 42           # the row the mass flattens onto


def jitter(seed: str) -> random.Random:
    return random.Random(seed)


def body(img: Img, p: Dict, cx: int, cy: int, rx: int, ry: int,
         wob: float, phase: float, lean: int, c: Dict,
         flat: float = 1.0) -> None:
    """One jelly mass: a dome that flares into a flat foot where it rests.

    A plain superellipse ends in a single-pixel point, which reads as a leaf or a
    droplet. `flat` blends that point back out to a full-width base, so the mass
    looks like something sitting on a floor; airborne poses pass flat=0 instead.
    """
    for dy in range(-ry, ry + 1):
        t = dy / max(1, ry)
        dome = rx * math.sqrt(max(0.0, 1 - t * t))
        if t <= 0.0:
            w = dome
        else:                       # a resting blob stays wide, it does not taper
            w = lerp(dome, rx * (1.0 - 0.30 * t ** 3), flat)
        w += wob * math.sin(phase + t * 3.4) * 1.1
        w = max(1.0, w)
        x0 = round(cx - w + lean * t * t)
        x1 = round(cx + w + lean * t * t)
        for x in range(x0, x1 + 1):
            u = (x - cx) / max(1.0, w)
            if abs(u) > 0.76:
                col = c["edge"]
            elif t > 0.42:
                col = c["body2"]
            elif t < -0.55:
                col = c["hi"]
            else:
                col = c["body"]
            img.set(x, cy + dy, col)
    # the shine: two hard glints high on the mass, the classic wet read
    img.ellipse(round(cx - rx * 0.34), round(cy - ry * 0.5),
                max(2, rx // 4), max(1, ry // 5), c["hi2"], filled=True)
    img.set(round(cx - rx * 0.1), round(cy - ry * 0.66), c["hi2"])
    img.set(round(cx + rx * 0.3), round(cy - ry * 0.3), c["hi"])


def crown(img: Img, c: Dict, x: int, y: int, tilt: float, w: int = 7) -> None:
    """A three-spiked gold band that rides the dome instead of floating over it.

    The band dips at its ends by the same curve the jelly surface drops, so it
    sinks into the mass at the sides - a straight band left a 2 px gap there and
    read as a halo.
    """
    for i in range(-w, w + 1):
        dip = round(2.0 * (i / w) ** 2)
        img.rect(x + i, y + dip, 1, 4, c["gold"])
        img.set(x + i, y + dip, c["gold3"])
        img.set(x + i, y + dip + 3, c["gold2"])
    for k, sx in enumerate((-w + 1, 0, w - 1)):
        top = y + round(2.0 * (sx / w) ** 2)
        bx = x + sx + round(tilt * 2)
        img.tri(bx + 1, top - 5, bx - 2, top + 1, bx + 4, top + 1, c["gold"])
        img.line(bx + 1, top - 5, bx - 1, top, c["gold3"])
        img.set(bx + 1, top + 1, c["core"] if k == 1 else c["gold2"])


def gem(img: Img, c: Dict, x: int, y: int, r: int) -> None:
    """The half-dissolved prize floating inside the mass, seen through the jelly."""
    for i in range(-r, r + 1):
        w = max(1, r - abs(i))
        img.rect(x - w, y + i, w * 2 + 1, 1,
                 c["gem"] if i < 0 else c["gem2"])
    img.line(x - r, y, x + r, y, c["gem"])
    img.set(x - 1, y - r, c["gold3"])


def face(img: Img, p: Dict, cx: int, cy: int, rx: int, ry: int, c: Dict) -> None:
    """Eyes and a mouth, painted after rim() so nothing outlines them.

    The features scale with the mass: a split offspring is 6-9 px wide and would
    otherwise get the king's face hanging off its silhouette.
    """
    s = 1.0 if rx >= 12 else 0.55
    out = max(2, round(5 * s))       # outer eye edge
    inn = max(1, round(2 * s))       # inner eye edge
    ew = max(1, round(2.6 * s))      # eye width
    eh = max(2, round(3.4 * s))      # eye height
    ex, ey = cx, cy - round(ry * 0.18)
    if p["eyes"] == "shut":
        img.line(ex - out, ey, ex - inn, ey, c["eye"])
        img.line(ex + inn, ey, ex + out, ey, c["eye"])
    elif p["eyes"] == "angry":
        for dx in (-out, inn):
            img.rect(ex + dx, ey - 1, ew, eh - 1, c["eye"])
            img.set(ex + dx + (ew - 1 if dx < 0 else 0), ey - 2, c["eye"])
    else:
        for dx in (-out, inn):
            img.rect(ex + dx, ey - 1, ew, eh, c["eye"])
            img.set(ex + dx, ey - 1, c["mouth"])
    m = p["mouth"]
    mw = max(1, round(3.2 * s))
    if m:
        img.rect(ex - mw, ey + 5, mw * 2 + 1, 1 + m, c["mouth"])
        if m > 1:                       # only a wide-open mouth catches the light
            img.line(ex - mw, ey + 5 + m, ex + mw, ey + 5 + m, c["hi"])
    else:
        img.line(ex - mw, ey + 5, ex + mw, ey + 5, c["edge"])


def shadow(img: Img, cx: int, w: int, c: Dict) -> None:
    """A thin contact shadow so the mass reads as resting on something."""
    y = GROUND + 1
    for x in range(cx - w, cx + w + 1):
        if 0 <= x < SIZE and img.get(x, y) == WHITE:
            img.set(x, y, darken(c["body2"], 0.55))


BASE: Dict = {
    "dx": 0, "dy": 0, "rx": RX, "ry": RY, "wob": 1.2, "phase": 0.0,
    "lean": 0, "eyes": "open", "mouth": 0, "crown": 1, "gem": 1,
    "lid": 0, "tint": 0.0, "tint_to": BLEACH, "arm": 0, "flat": 1.0,
    "cx": CX, "cy": CY, "wake": 0,
    # split offspring as (offset x, offset y, rx, ry, wears the crown)
    "kids": (),
}


def pose(**kw) -> Dict:
    q = dict(BASE)
    q.update(kw)
    return q


def parts(p: Dict) -> Sequence[Tuple[int, int, int, int, int, int]]:
    """The jelly masses of this frame: the king alone, or the pair it tore into."""
    cx, cy = p["cx"] + p["dx"], p["cy"] + p["dy"]
    if p["kids"]:
        # the offspring that wear the crown are the ones that kept the gem
        return [(cx + ox, cy + oy, rx, ry, cr, cr)
                for ox, oy, rx, ry, cr in p["kids"]]
    return [(cx, cy, p["rx"], p["ry"], p["crown"], p["gem"])]


def slime(img: Img, p: Dict) -> None:
    """One boss frame from pose params - the only place the mass is drawn."""
    c = dict(JELLY)
    if p["tint"]:
        for key in FILLS:
            c[key] = dz.blend(c[key], p["tint_to"], p["tint"])
        # the crown is metal: it catches the flash, it does not bleach with the jelly
        for key in ("gold", "gold2", "gold3"):
            c[key] = dz.blend(JELLY[key], p["tint_to"], p["tint"] * 0.35)
    ps = list(parts(p))
    for x, y, rx, _ry, _cr, _gm in ps:
        shadow(img, x, max(4, rx - 2 - abs(y - CY) // 2), c)
    for k, (x, y, rx, ry, _cr, _gm) in enumerate(ps):
        body(img, p, x, y, rx, ry, p["wob"], p["phase"] + 1.6 * k, p["lean"],
             c, p["flat"])
    if p["arm"] > 0:                     # a pseudopod thrown out of the mass
        pseudopod(img, c, p["cx"] + p["dx"], p["cy"] + p["dy"], p["arm"])
    for k in range(p["wake"]):         # the trail a sliding mass drags behind it
        x = p["cx"] + p["dx"] - p["rx"] + 2 - k * 3
        img.ellipse(x, GROUND - 1 - k, max(1, 4 - k), max(1, 3 - k),
                    c["body2"], filled=True)
    for x, y, rx, ry, cr, _gm in ps:
        if cr:
            crown(img, c, x, y - ry - 1 + p["lid"], p["phase"] / 40.0,
                  max(4, rx // 2))
    rim(img, c)
    for x, y, rx, ry, _cr, gm in ps:
        face(img, p, x, y, rx, ry, c)
        if gm:                            # the treasure it is slowly digesting
            gem(img, c, x - rx // 2, y + ry - 4, 3 if rx >= 12 else 2)


def pseudopod(img: Img, c: Dict, cx: int, cy: int, reach: int) -> None:
    """A thick arm of jelly flung out of the mass.

    Body tones only, never `edge`: rim() borders the union, so a hand-drawn
    outline here would survive as a dark ring inside the arm.
    """
    x0, y0 = cx + 4, cy - 2
    x1, y1 = cx + 5 + reach, cy + 3
    for k in range(reach + 1):
        t = k / max(1, reach)
        x = round(lerp(x0, x1, t))
        y = round(lerp(y0, y1, t) + math.sin(t * 3.1) * 2)
        r = max(2, round(lerp(6, 4, t)))
        img.circle(x, y, r, c["body"], filled=True)
        img.circle(x, y + 2, max(1, r - 2), c["body2"], filled=True)
    img.ellipse(x1, y1 + 1, 5, 3, c["body2"], filled=True)
    img.ellipse(x1, y1 - 1, 4, 2, c["body"], filled=True)
    img.line(x1 - 3, y1 - 3, x1 + 3, y1 - 3, c["hi"])


def rim(img: Img, p: Dict) -> None:
    """One outline pass around the union of the jelly tones."""
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


def stamp(p: Dict) -> Img:
    out = blank()
    slime(out, p)
    return out


# ------------------------------------------------------------------ effects
def drip(img: Img, x: int, y: int, n: int, seed: str) -> None:
    """Acid droplets thrown off the mass."""
    rnd = jitter(seed)
    for _ in range(n):
        dx, dy = rnd.randint(-11, 13), rnd.randint(-8, 7)
        r = rnd.choice((1, 1, 2))
        img.circle(x + dx, y + dy, r, JELLY["acid"], filled=True)
        if r > 1:
            img.set(x + dx - 1, y + dy - 1, JELLY["hi2"])


def glob(img: Img, x: int, y: int, r: int) -> None:
    """A spit ball: bright core, acid skin, a tail of smaller drops."""
    img.circle(x, y, r, JELLY["acid2"], filled=True)
    img.circle(x - 1, y - 1, max(1, r - 1), JELLY["acid"], filled=True)
    img.set(x - 1, y - 1, JELLY["hi2"])
    for k in range(1, 3):
        img.circle(x - r - k * 3, y + k // 2, max(1, r - k), JELLY["acid2"],
                   filled=True)


def splash(img: Img, x: int, y: int, r: int) -> None:
    """Impact: short radial dashes. A full ring read as a bubble, not a slap."""
    for k in range(8):
        a = math.radians(k * 45 + 12)
        img.line(round(x + math.cos(a) * (r // 2)), round(y + math.sin(a) * (r // 2)),
                 round(x + math.cos(a) * r), round(y + math.sin(a) * r),
                 JELLY["acid"] if k % 2 else JELLY["acid2"])


def pool(img: Img, cx: int, w: int, c: Dict, seed: str = "") -> None:
    """The last frames: a shallow puddle wide enough to read as the whole boss."""
    for dy in range(-3, 4):
        k = abs(dy) / 3.0
        hw = max(1.0, w * math.sqrt(max(0.0, 1 - k * k)))
        img.line(round(cx - hw), GROUND + dy, round(cx + hw), GROUND + dy,
                 c["body2"] if dy < 0 else c["edge"])
    img.line(cx - w // 2, GROUND - 1, cx + w // 3, GROUND - 1, c["hi"])
    img.ellipse(cx - w // 2, GROUND - 2, 3, 1, c["hi2"], filled=True)
    if seed:                              # last lumps of jelly collapsing down
        rnd = jitter(seed)
        for _ in range(5):
            x = cx + rnd.randint(-w + 2, w - 2)
            h = rnd.randint(1, 4)
            img.rect(x, GROUND - 2 - h, 2, h + 1, c["body"])
            img.set(x, GROUND - 2 - h, c["hi"])


# ------------------------------------------------------------------- scenes
def scene_idle(f: int, n: int) -> Img:
    return stamp(pose(wob=(1.2, 0.9, 1.2, 1.5)[f], phase=f * 1.5,
                      ry=(11, 10, 11, 12)[f], rx=(14, 15, 14, 13)[f],
                      cy=(31, 32, 31, 30)[f],
                      lid=(0, -1, 0, 1)[f], mouth=(0, 0, 1, 0)[f],
                      eyes="shut" if f == 2 else "open"))


def scene_hop(f: int, n: int) -> Img:
    # squash, launch, airborne teardrop, land flat
    k = ((16, 7, 35), (12, 13, 29), (11, 15, 25), (18, 6, 36))[f]
    img = stamp(pose(rx=k[0], ry=k[1], cy=k[2], wob=0.7, phase=f * 1.2,
                     flat=(1.0, 0.5, 0.0, 1.0)[f],
                     lid=(0, -2, -1, 2)[f], eyes="angry",
                     mouth=(0, 1, 2, 0)[f], lean=(0, -1, 1, 2)[f]))
    if f == 3:
        dz.dust(img, GROUND + 2, 6, f"hop{f}")
    return img


def scene_slide(f: int, n: int) -> Img:
    return stamp(pose(dx=(-2, 0, 3, 6)[f], rx=(16, 15, 17, 15)[f],
                      ry=(9, 10, 8, 10)[f], cy=(33, 32, 34, 33)[f],
                      wob=1.6, phase=f * 1.9, lean=(3, 1, 4, 2)[f],
                      eyes="angry", lid=0, wake=3))


def scene_attack(f: int, n: int) -> Img:
    # rear up, wind the mass back, throw the arm, follow through
    k = ((13, 13, 29, 0), (11, 15, 26, 0), (16, 10, 34, 13), (15, 11, 32, 6))[f]
    img = stamp(pose(rx=k[0], ry=k[1], cy=k[2], arm=k[3], wob=1.4,
                     flat=(1.0, 0.4, 1.0, 1.0)[f],
                     phase=f * 1.1, lean=(2, -3, 6, 2)[f], eyes="angry",
                     mouth=(1, 2, 3, 1)[f], lid=(0, -2, 1, 0)[f]))
    if f == 2:
        splash(img, CX + 19, GROUND - 2, 8)
        drip(img, CX + 18, GROUND - 4, 5, "atk")
    if f >= 2:
        dz.dust(img, GROUND + 2, 6, f"atk{f}")
    return img


def scene_split(f: int, n: int) -> Img:
    # one king, a waist, a tear, two of them
    kids = {
        1: ((-4, 0, 9, 11, 1), (4, 1, 8, 10, 0)),
        2: ((-7, 0, 9, 11, 1), (7, 1, 8, 10, 0)),
        3: ((-12, 0, 10, 11, 1), (12, 1, 8, 9, 0)),
        4: ((-14, 0, 9, 10, 1), (14, 2, 7, 8, 0)),
    }
    return stamp(pose(rx=(14, 0, 0, 0, 0)[f], ry=(11, 0, 0, 0, 0)[f],
                      cy=31, kids=kids.get(f, ()),
                      wob=(1.2, 1.6, 2.4, 1.4, 0.9)[f], phase=f * 1.4,
                      lean=(0, 1, 2, 0, 0)[f], eyes="angry",
                      mouth=(0, 2, 1, 2, 1)[f],
                      crown=1 if f == 0 else 0,
                      gem=1 if f == 0 else 0, lid=(0, 0, 0, -1, 1)[f]))


def scene_spit(f: int, n: int) -> Img:
    pos = (None, None, (28, 33), (34, 32), (40, 31), (45, 30))[f]
    img = stamp(pose(rx=(14, 12, 15, 14, 14, 14)[f],
                     ry=(11, 13, 10, 11, 11, 11)[f],
                     cy=(31, 29, 31, 31, 31, 31)[f], wob=1.4, phase=f * 1.3,
                     lean=(0, -2, 3, 2, 1, 0)[f], eyes="angry",
                     mouth=(1, 3, 2, 1, 0, 0)[f]))
    if pos:
        glob(img, pos[0], pos[1], 3 if f < 4 else 2)
    if f == 1:
        drip(img, CX + 10, 26, 3, "spit0")
    return img


def scene_hurt(f: int, n: int) -> Img:
    img = stamp(pose(dx=(0, -3, -1)[f], rx=(14, 16, 13)[f], ry=(11, 9, 12)[f],
                     cy=(31, 33, 30)[f], wob=(1.2, 2.6, 1.8)[f], phase=f * 2.1,
                     lean=(0, 4, 1)[f], eyes=("open", "shut", "angry")[f],
                     mouth=(0, 2, 1)[f], tint=(0.0, 0.34, 0.12)[f],
                     lid=(0, 2, 0)[f]))
    if f:
        drip(img, CX + 8, 24, 6 if f == 1 else 3, f"hurt{f}")
    return img


def scene_die(f: int, n: int) -> Img:
    if f >= 4:                        # the mass has drained into a puddle
        img = blank()
        c = dict(JELLY)
        for key in FILLS:
            c[key] = dz.blend(c[key], MUD, 0.35 + 0.12 * (f - 4))
        pool(img, CX + 1, 16 - (f - 4) * 3, c, f"die{f}")
        crown(img, c, CX - 12, GROUND - 4, 1.2, 6)
        gem(img, c, CX + 8, GROUND - 2, 2)
        rim(img, c)
        return img
    return stamp(pose(rx=(14, 12, 10, 8)[f], ry=(11, 12, 11, 9)[f],
                      cy=(31, 31, 32, 34)[f], wob=(1.2, 2.2, 3.0, 3.6)[f],
                      phase=f * 2.4, lean=(0, -2, -4, -5)[f],
                      eyes=("open", "shut", "shut", "shut")[f],
                      mouth=(0, 1, 2, 2)[f], tint=(0.1, 0.26, 0.4, 0.52)[f],
                      tint_to=MUD, lid=(0, 1, 3, 5)[f],
                      crown=1 if f < 3 else 0, gem=1 if f < 3 else 0))


BUILDERS = {
    "slime_idle": scene_idle, "slime_hop": scene_hop,
    "slime_slide": scene_slide, "slime_attack": scene_attack,
    "slime_split": scene_split, "slime_spit": scene_spit,
    "slime_hurt": scene_hurt, "slime_die": scene_die,
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
        sheet = export_dir(create=True) / "slime_sheet_all.png"
        encode_png_rgba(sheet, W, H, grid)
        print(f"  sheet {sheet.name}  {W}x{H}")
    print(f"  {len(wanted)} scenes, {total} frames -> {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
