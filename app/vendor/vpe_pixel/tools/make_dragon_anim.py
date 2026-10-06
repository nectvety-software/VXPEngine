"""Draw the boss dragon as a playable .vpea set for the VPE library.

The shipped library only has two flat stills (`td_dragon_0/1.vpe`, 32x24, a
2-frame wing flap). This redraws the same creature - green scales, pale belly,
gold horns, purple wing membrane - at 48x48, three tiles wide, so it reads as
a boss next to the 16x16 hero:

  dragon_idle    4 f  160 ms  loop    breathing, tail flick, wing sway
  dragon_walk    4 f  130 ms  loop    diagonal gait, head nod
  dragon_fly     4 f  110 ms  loop    wing up / forward / down / back
  dragon_bite    4 f   80 ms  once    coil, lunge, snap, recover
  dragon_breath  6 f   70 ms  once    throat glow, flame cone, fade
  dragon_slam    5 f   90 ms  once    rear up, wings overhead, shockwave
  dragon_hurt    3 f  120 ms  once    recoil, flash, wince
  dragon_die     6 f  150 ms  once    stagger, tilt, crash, settle, dust

36 frames in total, all drawn through one parametric `dragon()` pose function,
so every scene is the same animal. Fills are laid down first and a single
`rim()` pass borders the union of the fills - that is what keeps one outline
colour across a shape built from a dozen overlapping ellipses.

VPE reserves 0xFFFF as the transparent key, so every highlight goes through
``ms.safe_light``. The flame reuses the ``sprite/effect/`` palette from
``make_effect_anim`` so a breath matches the fireball already in the library.
All randomness is seeded per scene name, so re-running is byte-identical.

Writes (new folders only; the td_dragon stills are left alone):
  Documents\\VPE Pixel\\sprite\\enemies\\boss\\dragon_<action>.vpea
  Documents\\VPE Pixel\\exports\\boss\\<scene>_strip.png
  Documents\\VPE Pixel\\exports\\boss_sheet_all.png   (review sheet)

Run from the repo root:
  python tools/make_dragon_anim.py [--only idle,breath] [--scale 3] [--no-sheet]
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

import make_effect_anim as ea  # noqa: E402  (FIRE / EMBER palettes)
import make_knight_anim as ka  # noqa: E402  (label_w / LABEL_H / scaled)
from make_vqeaf_icons import encode_png_rgba  # noqa: E402
from vpx_editor.gallery import category_dir  # noqa: E402
from vpx_editor.paths import export_dir  # noqa: E402
from vpx_editor.vpea import save_vpea  # noqa: E402
import make_samples as ms  # noqa: E402

Img, rgb, WHITE = ms.Img, ms.rgb, ms.WHITE
safe_light, darken = ms.safe_light, ms.darken
from vpx_editor.vpe import c565_to_rgb  # noqa: E402
SIZE = 48

TIMING: Dict[str, Tuple[int, int, bool]] = {   # frames, delay ms, loop
    "dragon_idle": (4, 160, True),
    "dragon_walk": (4, 130, True),
    "dragon_fly": (4, 110, True),
    "dragon_bite": (4, 80, False),
    "dragon_breath": (6, 70, False),
    "dragon_slam": (5, 90, False),
    "dragon_hurt": (3, 120, False),
    "dragon_die": (6, 150, False),
}

# ----------------------------------------------------------------- palettes
GREEN = {
    "body": rgb(96, 158, 74),
    "hi": rgb(126, 186, 96),
    "dark": rgb(58, 104, 48),
    "belly": rgb(196, 214, 120),
    "belly2": rgb(158, 178, 92),
    "spike": rgb(226, 196, 90),
    "wing": rgb(172, 116, 200),
    "wing_far": rgb(96, 60, 118),
    "eye": rgb(244, 226, 120),
    "pupil": rgb(24, 20, 28),
    "tooth": rgb(240, 240, 228),
    "out": rgb(18, 24, 38),
}
# The skeleton variant is not shipped here, but RED keeps the hurt flash and
# the dying tint inside the boss's own hue range.
RED = rgb(196, 66, 48)
FIRE = ea.FIRE
EMBER = ea.EMBER
DUST = rgb(154, 142, 126)

# colours rim() treats as "the dragon": everything except eyes, teeth and rim
FILLS = ("body", "hi", "dark", "belly", "belly2", "spike", "wing", "wing_far")

# --------------------------------------------------------------- geometry
# A 48x48 box is three 16px tiles: the dragon owns the lower-left two thirds
# and leaves the right column free for the breath to start travelling.
BODY = (17, 30)          # torso ellipse centre
BRX, BRY = 10, 8
HEAD = (34, 13)          # skull centre
HRX, HRY = 6, 5
WING = (20, 23)          # membrane anchor on the shoulder blade
LEG_X = (8, 12, 21, 25)  # (0, 2) are the off-side pair
LEG_W = 4
FOOT = 44                # planted foot row
TAIL_BASE = (8, 30)


def blank() -> Img:
    return Img(SIZE, SIZE, WHITE)


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def blend(c: int, to: int, t: float) -> int:
    """Mix two packed RGB565 colours (ms.mix works on 8-bit triplets)."""
    a, b = c565_to_rgb(c), c565_to_rgb(to)
    return rgb(*[int(lerp(a[i], b[i], t)) for i in range(3)])


# ------------------------------------------------------------------ parts
def tail(img: Img, p: Dict, sway: int) -> None:
    """Tapering tail of discs, curling up so the tip stays inside the box."""
    bx, by = TAIL_BASE[0], TAIL_BASE[1] + p["dy"]
    pts = [(bx + 3, by), (bx, by - 1 + sway), (bx - 3, by - 5 + sway),
           (bx - 4, by - 11 + sway * 2)]
    for i, (x, y) in enumerate(pts):
        img.circle(x, y, max(1, 4 - i), p["body"], filled=True)
    img.circle(pts[1][0], pts[1][1] + 2, 2, p["dark"], filled=True)
    tx, ty = pts[-1]
    img.tri(tx - 3, ty + 2, tx, ty - 5, tx + 3, ty + 2, p["spike"])


def legs(img: Img, p: Dict, lifts: Sequence[int], crouch: int = 0) -> None:
    """Four column legs with a wide foot; `lifts` raise one foot off the floor."""
    for i, lx in enumerate(LEG_X):
        far = i in (0, 2)
        lift = lifts[i % len(lifts)]
        top = BODY[1] + p["dy"] + BRY - 7 + crouch
        foot = min(FOOT + p["dy"] - lift, SIZE - 3)
        col = p["dark"] if far else p["body"]
        img.rect(lx, top, LEG_W, max(2, foot - top), col)
        img.rect(lx - 1, foot - 1, LEG_W + 2, 3, col)
        img.rect(lx - 1, foot + 1, LEG_W + 2, 1, darken(col, 0.75))
        img.set(lx - 1, foot + 1, p["spike"])            # claws
        img.set(lx + LEG_W, foot + 1, p["spike"])
        if not far:
            img.line(lx, top + 2, lx, foot - 2, p["hi"])  # lit shin


def torso(img: Img, p: Dict) -> None:
    bx, by = BODY[0], BODY[1] + p["dy"]
    img.ellipse(bx, by, BRX, BRY, p["body"], filled=True)
    img.ellipse(bx - 1, by + 4, BRX - 3, BRY - 5, p["belly"], filled=True)
    img.ellipse(bx - 1, by - 5, BRX - 4, 3, p["hi"], filled=True)
    for i in range(5):                                   # belly scutes
        img.line(bx - 7 + i * 4, by + 2, bx - 8 + i * 4, by + 7, p["belly2"])
    for x in range(bx - 7, bx + 6, 4):                   # spine spikes
        img.tri(x, by - BRY + 2, x + 2, by - BRY - 3, x + 4, by - BRY + 2,
                p["spike"])
    img.line(bx + 2, by - 6, bx + 9, by - 2, p["dark"])  # shoulder blade
    img.line(bx - 6, by - 5, bx - 9, by - 1, p["dark"])  # haunch


def neck(img: Img, p: Dict, hx: int, hy: int) -> None:
    """Tapering column of discs from the shoulder to the skull."""
    x0, y0 = BODY[0] + BRX - 5, BODY[1] + p["dy"] - 4
    x1, y1 = hx - 4, hy + 3
    for k in range(7):
        t = k / 6
        img.circle(round(lerp(x0, x1, t)), round(lerp(y0, y1, t)),
                   max(2, 5 - k // 2), p["body"], filled=True)
    for k in range(6):                                   # throat
        t = k / 5
        img.circle(round(lerp(x0, x1, t)) + 1, round(lerp(y0, y1, t)) + 3,
                   max(1, 3 - k // 2), p["belly"], filled=True)


def head(img: Img, p: Dict, hx: int, hy: int, mouth: int, eye: str) -> None:
    """Skull, snout, hinged jaw, swept-back horns and the eye ridge."""
    img.tri(hx - 5, hy - 3, hx - 12, hy - 8, hx - 5, hy + 1, p["spike"])
    img.tri(hx - 1, hy - 4, hx - 5, hy - 12, hx + 3, hy - 4, p["spike"])
    img.ellipse(hx, hy, HRX, HRY, p["body"], filled=True)
    img.ellipse(hx + 1, hy - 3, HRX - 3, 2, p["hi"], filled=True)
    img.tri(hx + 2, hy - 3, hx + 9, hy, hx + 2, hy + 1, p["body"])      # snout
    # The lower jaw always has real thickness: a hinged quad, never a flat line,
    # or a closed mouth leaves a pale dash that reads as a floating beak.
    drop = 1 + mouth
    img.tri(hx + 1, hy + 1, hx + 8, hy + drop, hx + 1, hy + 3 + drop, p["body"])
    img.rect(hx + 1, hy + 1, 6, 2 + mouth, p["body"])
    # the gape line must stop on the jaw, or it pokes out as a floating slant
    img.line(hx + 2, hy + 1, hx + 7, hy + 1 + int(mouth * 5 / 7), p["dark"])
    for x in (hx + 4, hx + 6, hx + 8):                                  # fangs
        y = hy + 2 + int((x - hx) * mouth / 9)
        if x <= hx + 8 and mouth >= 2:
            img.set(x, y, p["tooth"])
    img.set(hx + 8, hy - 1, p["pupil"])                                  # nostril
    if eye == "shut":
        img.line(hx + 1, hy - 1, hx + 4, hy, p["pupil"])
    elif eye == "glow":
        img.rect(hx + 1, hy - 3, 4, 3, safe_light(p["eye"], 18))
        img.set(hx + 3, hy - 2, p["pupil"])
    else:
        img.rect(hx + 1, hy - 3, 4, 3, p["eye"])
        img.set(hx + 3, hy - 2, p["pupil"])
        img.set(hx + 2, hy - 3, p["tooth"])                               # glint


def wing(img: Img, p: Dict, ang: float, span: int, far: bool = False) -> None:
    """Bat wing: arm from shoulder to claw, two membrane webs that sag between
    the joints, so the trailing edge scallops on its own."""
    a = math.radians(ang)
    ax, ay = WING[0] - (2 if far else 0), WING[1] + (1 if far else 0)
    ex, ey = ax + math.cos(a) * span * 0.55, ay + math.sin(a) * span * 0.55
    tx, ty = ax + math.cos(a) * span, ay + math.sin(a) * span
    ex, ey, tx, ty = round(ex), round(ey), round(tx), round(ty)
    mem = p["wing_far"] if far else p["wing"]
    sag = max(6, span // 3)
    w1 = (ax - 2, ay + sag - 1)               # armpit: membrane meets the body
    w2 = (ex - 4, ey + sag)                   # sag under the elbow
    w3 = (tx - 3, ty + sag - 2)               # sag under the wrist
    img.tri(ax, ay, ex, ey, *w2, mem)
    img.tri(ax, ay, *w1, *w2, mem)
    img.tri(ex, ey, tx, ty, *w3, mem)
    img.tri(ex, ey, *w2, *w3, mem)
    img.line(ax, ay, ex, ey, p["dark"])
    img.line(ex, ey, tx, ty, p["dark"])
    img.set(tx, ty, p["spike"])
    img.set(tx - 1, ty + 1, p["spike"])


def rim(img: Img, p: Dict) -> None:
    """One outline pass around the union of the fills, after all parts are set."""
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


def dragon(img: Img, pose: Dict) -> None:
    """One boss frame from pose params - the only place the body is drawn."""
    p = dict(GREEN)
    if pose.get("tint"):
        k = pose["tint"]
        for key in FILLS:
            p[key] = blend(p[key], RED, k)
    p["dy"] = pose["dy"]
    hx = HEAD[0] + pose["hx"]
    hy = HEAD[1] + pose["hy"]
    wing(img, p, pose["wing2"], pose["span2"], far=True)
    tail(img, p, pose["tail"])
    legs(img, p, pose["legs"], pose.get("crouch", 0))
    torso(img, p)
    wing(img, p, pose["wing"], pose["span"], far=False)
    neck(img, p, hx, hy)
    head(img, p, hx, hy, pose["mouth"], pose["eye"])
    rim(img, p)


BASE: Dict = {
    "dy": 0, "dx": 0, "hx": 0, "hy": 0, "mouth": 0, "eye": "open",
    "wing": -142, "span": 22, "wing2": -134, "span2": 19,
    "tail": 0, "legs": (0, 1, 1, 0), "tint": 0.0, "crouch": 0,
}


def pose(**kw) -> Dict:
    p = dict(BASE)
    p.update(kw)
    return p


def stamp(img: Img, p: Dict) -> Img:
    """Render `p` and apply the pose's whole-frame offset (lunges, recoils)."""
    out = blank()
    if not p["dx"]:
        dragon(out, p)
        return out
    tmp = blank()
    dragon(tmp, p)
    for y in range(SIZE):
        for x in range(SIZE):
            c = tmp.px[y * SIZE + x]
            if c != WHITE:
                out.set(x + p["dx"], y, c)
    return out


# ------------------------------------------------------------------ scenes
def jitter(seed: str) -> random.Random:
    return random.Random(seed)


def flame(img: Img, x0: int, y0: int, length: int, spread: int,
          seed: str) -> None:
    """Cone of fire out of the mouth: hot core, cool widening edge, flicker."""
    if length <= 0:
        return
    rnd = jitter(seed)
    for i in range(length):
        t = i / max(1, length - 1)
        x = x0 + i
        h = max(1 + int(2 * t), round(spread * (0.30 + 0.70 * t)))
        wob = rnd.randint(-1, 1) if t > 0.35 else 0
        for k in range(-h, h + 1):
            d = abs(k) / max(1, h)
            y = y0 + round(k * (0.75 + 0.5 * t)) + round(t * 1.5) + wob
            if d < 0.30:
                c = FIRE[3]                       # white-hot core
            elif d < 0.62:
                c = FIRE[2]
            elif d < 0.88:
                c = FIRE[1] if rnd.random() < 0.75 else FIRE[2]
            else:
                c = FIRE[0] if rnd.random() < 0.6 else EMBER
            img.set(x, y, c)
    # the leading edge breaks into embers
    for _ in range(7):
        img.set(x0 + length - rnd.randint(0, 5),
                y0 + rnd.randint(-spread - 1, spread + 3),
                EMBER if rnd.random() < 0.5 else FIRE[0])


def shock(img: Img, cx: int, cy: int, r: int, c: int) -> None:
    """Ground shockwave: a dashed, dithered ellipse ring."""
    for k in range(0, 64):
        a = k * math.tau / 64
        x, y = round(cx + math.cos(a) * r), round(cy + math.sin(a) * r * 0.34)
        if k % 3 == 0:
            img.set(x, y, c)
            img.set(x, y + 1, darken(c, 0.6))


def dust(img: Img, row: int, count: int, seed: str) -> None:
    rnd = jitter(seed)
    for _ in range(count):
        x = rnd.randint(2, SIZE - 3)
        y = row + rnd.randint(-1, 1)
        img.set(x, y, DUST if rnd.random() < 0.55 else darken(DUST, 0.72))


def scene_idle(f: int, n: int) -> Img:
    breathe = (0, -1, 0, 1)[f]
    return stamp(blank(), pose(dy=breathe, tail=(0, 0, 1, -1)[f],
                      wing=(-150, -142, -134, -142)[f],
                      wing2=(-142, -134, -126, -134)[f],
                      legs=(0, 0, 0, 0), eye="shut" if f == 3 else "open"))


def scene_walk(f: int, n: int) -> Img:
    gait = ((0, 1, 1, 0), (1, 0, 0, 1), (1, 1, 0, 0), (0, 0, 1, 1))[f]
    return stamp(blank(), pose(dy=(0, -1, 0, 1)[f], legs=gait,
                               tail=(0, 1, 2, 1)[f], hx=(0, 1, 0, -1)[f],
                               hy=(0, 0, 1, 0)[f], wing=(-120, -112, -104, -112)[f],
                               wing2=(-114, -106, -98, -106)[f]))


def scene_fly(f: int, n: int) -> Img:
    # wing up / forward / down / back, body hanging under the beat
    beat = ((-162, 23, -156, 20), (-122, 24, -116, 21),
            (-74, 23, -68, 20), (-134, 22, -128, 19))[f]
    return stamp(blank(), pose(dy=(0, -2, -3, -2)[f], legs=(2, 2, 1, 1),
                               tail=(0, -1, -2, -1)[f], hx=(-1, 0, 1, 0)[f],
                               hy=(0, 1, 0, -1)[f], wing=beat[0], span=beat[1],
                               wing2=beat[2], span2=beat[3]))


def scene_bite(f: int, n: int) -> Img:
    # coil back, lunge, snap shut, recover
    k = ((-4, -2, 3, 0), (4, -1, 4, 2), (5, 1, 1, 4), (-1, 0, 0, 1))[f]
    return stamp(blank(), pose(dx=k[0], hx=k[0], hy=k[1], mouth=k[2],
                               eye="glow" if f == 1 else "open",
                               dy=(0, -1, 1, 0)[f],
                               wing=(-135, -100, -70, -118)[f],
                               wing2=(-128, -94, -64, -112)[f],
                               legs=((0, 1, 1, 0), (0, 0, 1, 1), (1, 1, 0, 0),
                                     (0, 1, 1, 0))[f]))


def scene_breath(f: int, n: int) -> Img:
    p = pose(dx=(-4, -4, -3, -2, -1, 0)[f], hx=(-6, -6, -5, -4, -3, -1)[f],
             hy=(0, 1, 1, 0, 0, 0)[f], mouth=(1, 3, 4, 4, 3, 1)[f], eye="glow",
             dy=(0, -1, -1, 0, 0, 0)[f],
             wing=(-146, -152, -158, -158, -152, -144)[f],
             wing2=(-138, -146, -152, -152, -144, -136)[f],
             legs=(0, 0, 1, 1))
    img = stamp(blank(), p)
    hx, hy = HEAD[0] + p["hx"] + p["dx"], HEAD[1] + p["hy"]
    if f == 0:
        ea.glow(img, hx + 6, hy + 2, 2, (FIRE[3], FIRE[2], FIRE[1]))
    if f >= 1:
        length = (0, 9, 14, 16, 13, 6)[f]
        flame(img, hx + 9, hy + 1, length, (0, 2, 4, 5, 4, 2)[f],
              f"breath{f}")
    if f >= 3:
        dust(img, FOOT, 4, f"breathdust{f}")
    return img


def scene_slam(f: int, n: int) -> Img:
    p = pose(dy=(0, -2, 2, 1, 0)[f],
             wing=(-152, -168, -66, -96, -142)[f], span=(22, 24, 23, 19, 22)[f],
             wing2=(-144, -160, -58, -88, -134)[f], span2=(19, 21, 20, 16, 19)[f],
             hx=(0, -1, 2, 1, 0)[f], hy=(0, -2, 2, 1, 0)[f],
             mouth=(0, 1, 3, 2, 0)[f], eye="glow" if f in (2, 3) else "open",
             legs=((0, 1, 1, 0), (0, 0, 0, 0), (2, 2, 2, 2), (1, 1, 0, 0),
                   (0, 1, 1, 0))[f])
    img = stamp(blank(), p)
    if f == 2:
        shock(img, BODY[0] + 4, FOOT - 1, 18, safe_light(GREEN["spike"], 10))
    if f >= 3:
        shock(img, BODY[0] + 4, FOOT - 1, (0, 0, 0, 20, 22)[f], darken(DUST, 0.9))
        dust(img, FOOT, 6 if f == 3 else 10, f"slam{f}")
    return img


def scene_hurt(f: int, n: int) -> Img:
    p = pose(dx=(0, -3, -1)[f], dy=(0, 1, 0)[f], hx=(0, -3, -1)[f],
             hy=(0, -1, 0)[f], mouth=(0, 3, 1)[f],
             eye=("open", "shut", "shut")[f], tint=(0.0, 0.16, 0.05)[f],
             wing=(-118, -84, -136)[f], wing2=(-110, -76, -128)[f],
             tail=(0, 2, 1)[f], legs=((0, 1, 1, 0), (1, 1, 0, 0), (0, 1, 1, 0))[f])
    img = stamp(blank(), p)
    if f:
        hx, hy = HEAD[0] + p["hx"] + p["dx"], HEAD[1] + p["hy"]
        ea.star4(img, hx + 6, hy - 6, 3, safe_light(GREEN["eye"], 12))
        img.set(hx - 4, hy - 8, RED)
    return img


def scene_die(f: int, n: int) -> Img:
    fall = ((0, 0, 0), (0, 0, -2), (-2, 2, -5), (-4, 4, -7), (-4, 4, -7),
            (-4, 4, -7))[f]
    p = pose(dx=(0, -1, -2, -3, -3, -3)[f], dy=(0, 1, 2, 4, 4, 4)[f],
             hx=(0, 0, -2, -4, -5, -5)[f], hy=(0, 1, 4, 7, 8, 8)[f],
             mouth=(0, 2, 3, 1, 0, 0)[f], eye=("open", "shut", "shut", "shut",
                                               "shut", "shut")[f],
             tint=(0, 0.1, 0.2, 0.3, 0.35, 0.4)[f],
             wing=(-142, -126, -104, -168, -172, -172)[f],
             span=(22, 23, 24, 20, 19, 19)[f],
             wing2=(-134, -118, -96, -160, -164, -164)[f],
             span2=(19, 20, 21, 17, 16, 16)[f],
             legs=((0, 1, 1, 0), (1, 0, 0, 1), (2, 2, 2, 2), (3, 3, 2, 2),
                   (3, 3, 3, 3), (3, 3, 3, 3))[f],
             tail=fall[2])
    img = stamp(blank(), p)
    if f >= 3:
        dust(img, FOOT - fall[1], 8 if f == 3 else 14, f"die{f}")
    if f >= 4:                                  # last embers going out
        rnd = jitter(f"diee{f}")
        for _ in range(4):
            img.set(rnd.randint(8, 30), FOOT + rnd.randint(-6, -2), FIRE[0])
    return img


BUILDERS = {
    "dragon_idle": scene_idle, "dragon_walk": scene_walk,
    "dragon_fly": scene_fly, "dragon_bite": scene_bite,
    "dragon_breath": scene_breath, "dragon_slam": scene_slam,
    "dragon_hurt": scene_hurt, "dragon_die": scene_die,
}


def build(name: str) -> List[Img]:
    n, _delay, _loop = TIMING[name]
    return [BUILDERS[name](f, n) for f in range(n)]


# ------------------------------------------------------------------- output
def boss_dir() -> Path:
    root = category_dir("sprite", create=True) / "enemies" / "boss"
    root.mkdir(parents=True, exist_ok=True)
    return root


def concat(frames: Sequence[Img]) -> Tuple[int, int, List[int]]:
    w, h = SIZE * len(frames), SIZE
    buf = [WHITE] * (w * h)
    for i, f in enumerate(frames):
        for y in range(h):
            row = y * w + i * SIZE
            buf[row:row + SIZE] = f.px[y * SIZE:(y + 1) * SIZE]
    return w, h, buf


def write(name: str, out_dir: Path) -> Tuple[Path, List[Img]]:
    n, delay, loop = TIMING[name]
    frames = build(name)
    assert len(frames) == n, name
    path = boss_dir() / f"{name}.vpea"
    save_vpea(path, SIZE, SIZE, [f.px for f in frames], delay, loop)
    w, h, buf = concat(frames)
    encode_png_rgba(out_dir / f"{name}_strip.png", w, h, buf)
    return path, frames


def draw_sheet(rows: List[Tuple[str, List[Img]]], scale: int,
               pad: int = 2) -> Tuple[int, int, List[int]]:
    """Review sheet: one labelled row per scene, dark checker behind."""
    label_cols = max(ka.label_w(nm) for nm, _f in rows) * scale
    cell = (SIZE + pad) * scale
    row_h = (ka.LABEL_H + SIZE + pad) * scale
    widest = max(len(fr) for _nm, fr in rows)
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
        title = Img(ka.label_w(name), ka.LABEL_H, WHITE)
        title.text(0, 1, name, rgb(214, 224, 240))
        paste(ka.scaled(title, scale), title.w * scale, title.h * scale,
              pad * scale, y0)
        for i, img in enumerate(frames):
            paste(ka.scaled(img, scale), SIZE * scale, SIZE * scale,
                  pad * scale + label_cols + i * cell,
                  y0 + (ka.LABEL_H + pad) * scale)
    return W, H, grid


def main(argv: Sequence[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--only", default="", help="comma list without the dragon_ prefix")
    ap.add_argument("--scale", type=int, default=3, help="sheet zoom factor")
    ap.add_argument("--no-sheet", action="store_true")
    ap.add_argument("--out", default="", help="export folder (default: exports/boss)")
    args = ap.parse_args(argv)

    wanted = list(TIMING)
    if args.only:
        keys = {k.strip() for k in args.only.split(",") if k.strip()}
        wanted = [nm for nm in wanted if nm[7:] in keys]
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
        W, H, grid = draw_sheet(rows, args.scale)
        sheet = export_dir(create=True) / "boss_sheet_all.png"
        encode_png_rgba(sheet, W, H, grid)
        print(f"  sheet {sheet.name}  {W}x{H}")
    print(f"  {len(wanted)} scenes, {total} frames -> {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
