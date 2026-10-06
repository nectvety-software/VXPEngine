"""Animate the player character: a 16x16 top-down hero in 4 directions.

The shipped library already has the hero as flat stills (`td_hero_<dir>_<action>
_<frame>.vpe`, 1-2 frames each). This turns the same body into real `.vpea`
scenes, so an engine can play them without stitching stills together:

  hero_<dir>_idle    4 f  200 ms  loop     breathing, blink on the last frame
  hero_<dir>_walk    4 f  140 ms  loop     0/1/0/-1 leg cycle from the stills
  hero_<dir>_run     4 f   90 ms  loop     lean + vertical bounce
  hero_<dir>_attack  4 f   80 ms  once     windup, thrust, blade arc, recover
  hero_<dir>_cast    5 f   90 ms  once     raise, charge, release, motes, settle
  hero_<dir>_hurt    3 f  110 ms  once     recoil away from the hit
  hero_<dir>_die     5 f  130 ms  once     stagger, lurch, collapse, dust

<dir> is down / left / up / right, so 28 scenes and 116 frames in total.

Everything reuses ``make_samples._td_person`` for the body, which is what keeps
the animated hero the same character as the stills; only props, offsets and
sparks are drawn here. VPE reserves 0xFFFF as the transparent key, so the pale
blade arc and spell highlights stay below it. All randomness is seeded, so
re-running rewrites byte-identical frames.

Writes (new files only; the existing td_hero_*.vpe stills are untouched):
  Documents\\VPE Pixel\\sprite\\characters\\player\\hero_<dir>_<action>.vpea
  Documents\\VPE Pixel\\exports\\player\\<scene>_strip.png
  Documents\\VPE Pixel\\exports\\player_sheet_<dir>.png   (review sheets)

Run from the repo root:
  python tools/make_player_anim.py [--only down,right] [--scale 5] [--no-sheet]
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

import make_knight_anim as ka  # noqa: E402  (label_w / scaled)
from make_vqeaf_icons import encode_png_rgba  # noqa: E402
from vpx_editor.gallery import category_dir  # noqa: E402
from vpx_editor.paths import export_dir  # noqa: E402
from vpx_editor.vpea import save_vpea  # noqa: E402
import make_samples as ms  # noqa: E402

Img, rgb, WHITE = ms.Img, ms.rgb, ms.WHITE
safe_light, darken = ms.safe_light, ms.darken
SIZE = 16
PAL = ms._pal()

DIRS = ("down", "left", "up", "right")           # index == _td_person's `d`
ACTIONS: Dict[str, Tuple[int, int, bool]] = {    # frames, delay ms, loop
    "idle": (4, 200, True),
    "walk": (4, 140, True),
    "run": (4, 90, True),
    "attack": (4, 80, False),
    "cast": (5, 90, False),
    "hurt": (3, 110, False),
    "die": (5, 130, False),
}

# ------------------------------------------------------------------ props
STEEL = rgb(196, 206, 220)
STEEL_HI = safe_light(STEEL, 22)
WOOD = rgb(126, 86, 48)
GOLD = rgb(232, 190, 70)
ARC = rgb(236, 244, 255)
MAGIC = rgb(120, 200, 252)
MAGIC_HI = rgb(220, 244, 255)
MAGIC_LO = rgb(96, 168, 236)
SPARK = rgb(252, 246, 190)
DUST = rgb(154, 142, 126)

# weapon hand per direction, and the unit vector the hero faces
HAND = {0: (12, 10), 1: (4, 10), 2: (12, 7), 3: (11, 10)}
FACE = {0: (0, 1), 1: (-1, 0), 2: (0, -1), 3: (1, 0)}
# head columns per direction, so sparks stay near the head instead of floating
HEAD_X = {0: (5, 10), 2: (5, 10), 1: (6, 9), 3: (6, 9)}
# windup -> slash -> follow-through, as offsets from the facing angle. Facing
# -x mirrors the sweep's handedness, and the profile views swing in the narrow
# column in front of the hand: a wider windup would cut across the body.
SWING = {0: (-2.3, -1.0, 0.4, 1.1), 2: (-2.3, -1.0, 0.4, 1.1),
         1: (-1.2, -0.5, 0.4, 1.1), 3: (-1.2, -0.5, 0.4, 1.1)}
REACH = {0: (4, 5, 5, 3), 2: (4, 5, 5, 3), 1: (4, 4, 4, 3), 3: (4, 4, 4, 3)}


# ----------------------------------------------------------------- helpers
def blank() -> Img:
    return Img(SIZE, SIZE, WHITE)


def shift(img: Img, dx: int = 0, dy: int = 0) -> Img:
    """Whole-sprite offset - the cheap way to add bounce and recoil."""
    if not (dx or dy):
        return img
    out = blank()
    for y in range(SIZE):
        for x in range(SIZE):
            c = img.px[y * SIZE + x]
            if c != WHITE:
                out.set(x + dx, y + dy, c)
    return out


def body(d: int, pose: str, f: int, dx: int = 0, dy: int = 0) -> Img:
    return shift(ms._td_person(d, pose, f, PAL), dx, dy)


def line(img: Img, x0: float, y0: float, x1: float, y1: float, c: int) -> None:
    steps = max(abs(x1 - x0), abs(y1 - y0), 1)
    for k in range(int(steps) + 1):
        t = k / steps
        img.set(round(x0 + (x1 - x0) * t), round(y0 + (y1 - y0) * t), c)


def sword(img: Img, d: int, angle: float, length: int) -> None:
    """Blade held in the weapon hand, pointing along `angle` (radians)."""
    hx, hy = HAND[d]
    dx, dy = math.cos(angle), math.sin(angle)
    px, py = -dy, dx                        # perpendicular: lit spine edge
    tipx, tipy = hx + dx * length, hy + dy * length
    line(img, hx, hy, tipx, tipy, STEEL)
    line(img, hx + px, hy + py, tipx + px, tipy + py, STEEL_HI)
    img.set(round(tipx), round(tipy), STEEL_HI)
    img.set(round(hx - dx), round(hy - dy), WOOD)     # pommel
    img.set(round(hx + px), round(hy + py), WOOD)     # crossguard


def tip_trail(img: Img, d: int, angles: Sequence[float], length: int,
              c: int) -> None:
    """Where the blade tip has been, brightest at the newest angle.

    Only empty texels are painted: at 16x16 the sweep circle passes through
    the hero's own silhouette, and a slash drawn over the body reads as a
    white hook rather than a cut.
    """
    hx, hy = HAND[d]
    n = len(angles)
    for i, a in enumerate(angles):
        x = round(hx + math.cos(a) * length)
        y = round(hy + math.sin(a) * length)
        if img.get(x, y) != WHITE:
            continue
        img.set(x, y, c if i == n - 1 else darken(c, 0.45 + 0.5 * i / n))


def swing(img: Img, d: int, a: float, length: int, c: int, turn: int = 1) -> None:
    """Tip trail for a blade that moved from `a - turn*span` to `a`."""
    tip_trail(img, d, [a - turn * s for s in (0.55, 0.35, 0.18, 0.0)], length, c)


def orb(img: Img, cx: int, cy: int, r: int) -> None:
    """A charged spell ball. Below r=2 a circle is a blob, so use a diamond."""
    if r <= 1:
        img.set(cx, cy, MAGIC_HI)
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            img.set(cx + dx, cy + dy, MAGIC)
        return
    img.circle(cx, cy, r, MAGIC, filled=True)
    img.circle(cx, cy, r - 1, MAGIC_HI, filled=True)
    img.circle(cx, cy, r, MAGIC_LO)
    img.set(cx - 1, cy - 1, safe_light(MAGIC_HI, 6))


def star(img: Img, cx: int, cy: int, c: int) -> None:
    """One-texel twinkle with dimmed arms - dazed stars, distant sparks."""
    img.set(cx, cy, c)
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        img.set(cx + dx, cy + dy, darken(c, 0.55))


def jitter(seed: str) -> random.Random:
    return random.Random(seed)


# ------------------------------------------------------------------ scenes
def eyes(d: int, bob: int) -> List[Tuple[int, int]]:
    """Eye texels of the 16x16 body, mirroring _td_person's own head layout."""
    tx, w0 = (6, 4) if d in (1, 3) else (5, 6)
    y = 1 - bob + 3
    if d == 0:
        return [(tx + 1, y), (tx + w0 - 2, y)]
    if d == 2:
        return []
    return [(tx + w0 - 2, y)] if d == 3 else [(tx + 1, y)]


def scene_idle(d: int, n: int) -> List[Img]:
    out = []
    for f in range(n):
        img = body(d, "idle", f)
        if f == n - 1:                     # blink on the last frame
            for ex, ey in eyes(d, f % 2):
                assert img.get(ex, ey) == PAL["out"], "_td_person moved the eye"
                img.set(ex, ey, PAL["skin"])
        out.append(img)
    return out


def scene_walk(d: int, n: int) -> List[Img]:
    return [body(d, "walk", f) for f in range(n)]


def scene_run(d: int, n: int) -> List[Img]:
    # legs alternate every frame; the body hops on the two airborne frames
    return [body(d, "run", f, dy=-1 if f % 2 else 0) for f in range(n)]


def scene_attack(d: int, n: int) -> List[Img]:
    base = math.atan2(FACE[d][1], FACE[d][0])
    turn = -1 if d == 1 else 1             # see SWING
    poses = ("idle", "run", "run", "idle")
    out = []
    for f in range(n):
        a = base + turn * SWING[d][f]
        img = body(d, poses[f], f % 2)     # weight onto the front foot mid-swing
        sword(img, d, a, REACH[d][f])
        if f:
            swing(img, d, a, REACH[d][f], ARC if f < 3 else darken(ARC, 0.5),
                  turn)
        out.append(img)
    return out


def scene_cast(d: int, n: int) -> List[Img]:
    hx, hy = HAND[d]
    fx, fy = FACE[d]
    poses = ("idle", "idle", "run", "run", "idle")
    out = []
    for f in range(n):
        img = body(d, poses[f], f % 2)
        if f == 0:
            orb(img, hx, hy, 1)
        elif f == 1:
            orb(img, hx, hy, 1)
            for k in range(4):             # charge sparks pulled into the hand
                a = k * math.pi / 2 + 0.4
                x, y = round(hx + math.cos(a) * 3), round(hy + math.sin(a) * 3)
                if img.get(x, y) == WHITE:
                    img.set(x, y, MAGIC_LO)
        elif f == 2:
            orb(img, hx, hy, 2)
            star(img, hx + fx * 4, hy + fy * 4, SPARK)
        elif f == 3:                     # the spell leaves the hand
            orb(img, hx + fx * 3, hy + fy * 3, 2)
            for k in range(1, 3):
                img.set(hx + fx * (3 - k), hy + fy * (3 - k),
                        MAGIC if k % 2 else MAGIC_LO)
        else:                            # motes settling where it went off
            star(img, hx + fx * 4, hy + fy * 4, darken(MAGIC, 0.7))
            img.set(hx + fx * 3, hy + fy * 4, darken(MAGIC_LO, 0.6))
        out.append(img)
    return out


def scene_hurt(d: int, n: int) -> List[Img]:
    fx, fy = FACE[d]
    out = []
    for f in range(n):
        if f == n - 1:                     # recovered: no stars, just the body
            out.append(body(d, "idle", 1))
            continue
        img = body(d, "hurt", f, dx=-fx, dy=1 if f else 0)
        # stars beside the head, never on the hair (that reads as a crown)
        x0, x1 = HEAD_X[d]
        star(img, x0 - 3, 3 - f, SPARK)
        star(img, x1 + 3, 2 + f, GOLD)
        out.append(img)
    return out


def lying(d: int) -> Img:
    """Collapsed pose drawn here: _td_person's single die frame is too blobby."""
    img = blank()
    out = PAL["out"]
    flip = d == 1                          # head end follows the facing axis
    tx = 5 if flip else 4                  # torso, 7 wide, mirrored about x=8
    img.rect(tx, 11, 7, 4, darken(PAL["shirt"], 0.78))
    img.frame(tx, 11, 7, 4, out)
    img.rect(tx, 14, 7, 1, darken(PAL["pants"], 0.6))
    hx = 1 if flip else 11                 # head at the front end, no overlap
    img.rect(hx, 10, 4, 4, PAL["skin"])
    img.frame(hx, 10, 4, 4, out)
    img.rect(hx, 10, 4, 2, PAL["hair"])
    img.set(hx + 1, 12, out)               # eyes shut
    img.set(hx + 2, 12, out)
    lx = 13 if flip else 0                 # legs trail behind, opposite the head
    img.rect(lx, 12, 3, 3, PAL["pants"])
    img.frame(lx, 12, 3, 3, out)
    line(img, 4, 9, 8, 8, STEEL)           # dropped sword, clear of the body
    img.set(3, 10, WOOD)
    return img


def scene_die(d: int, n: int) -> List[Img]:
    out = []
    for f in range(n):
        if f == 0:
            img = body(d, "hurt", 0)
        elif f == 1:
            img = body(d, "hurt", 1, dy=1)
        elif f == 2:
            # the last lurch before the knees go: never upward, that reads as floating
            img = body(d, "hurt", 1, dx=1 if d != 1 else -1, dy=1)
        elif f == 3:
            img = lying(d)
        else:
            img = lying(d)
            rnd = jitter(f"die{d}")
            for _ in range(8):                    # dust settling
                img.set(rnd.randint(1, SIZE - 2), rnd.choice((10, 15, 15)),
                        DUST if rnd.random() < 0.6 else darken(DUST, 0.7))
        out.append(img)
    return out


SCENES_FOR = {
    "idle": scene_idle, "walk": scene_walk, "run": scene_run,
    "attack": scene_attack, "cast": scene_cast, "hurt": scene_hurt,
    "die": scene_die,
}


def scene_names(dirs: Sequence[str] = DIRS) -> List[str]:
    return [f"hero_{d}_{a}" for a in ACTIONS for d in dirs]


def split(name: str) -> Tuple[int, str]:
    _, d, action = name.split("_", 2)
    return DIRS.index(d), action


def build(name: str) -> List[Img]:
    d, action = split(name)
    return SCENES_FOR[action](d, ACTIONS[action][0])


# ------------------------------------------------------------------ output
def player_dir() -> Path:
    root = category_dir("sprite", create=True) / "characters" / "player"
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
    d, action = split(name)
    frames, delay, loop = build(name), ACTIONS[action][1], ACTIONS[action][2]
    path = player_dir() / f"{name}.vpea"
    save_vpea(path, SIZE, SIZE, [f.px for f in frames], delay, loop)
    w, h, buf = concat(frames)
    encode_png_rgba(out_dir / f"{name}_strip.png", w, h, buf)
    return path, frames


def draw_sheet(rows: List[Tuple[str, List[Img]]], scale: int,
               pad: int = 3) -> Tuple[int, int, List[int]]:
    """Review sheet: one labelled row per scene, dark checker behind."""
    label_cols = max(ka.label_w(n) for n, _f in rows) * scale
    cell = (SIZE + pad) * scale
    row_h = (ka.LABEL_H + SIZE + pad) * scale
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
    ap.add_argument("--only", default="", help="comma list of directions")
    ap.add_argument("--scale", type=int, default=5, help="sheet zoom factor")
    ap.add_argument("--no-sheet", action="store_true")
    ap.add_argument("--out", default="", help="export folder (default: exports/player)")
    args = ap.parse_args(argv)

    dirs = list(DIRS)
    if args.only:
        keys = {k.strip() for k in args.only.split(",") if k.strip()}
        dirs = [d for d in DIRS if d in keys]
    out_dir = Path(args.out) if args.out else export_dir(create=True) / "player"
    out_dir.mkdir(parents=True, exist_ok=True)

    made: Dict[int, List[Tuple[str, List[Img]]]] = {DIRS.index(d): [] for d in dirs}
    total = 0
    for name in scene_names(dirs):
        path, frames = write(name, out_dir)
        total += len(frames)
        d, action = split(name)
        made[d].append((name, frames))
        print(f"  {path.name}  {len(frames)}f {SIZE}x{SIZE}"
              f" @{ACTIONS[action][1]} ms loop={ACTIONS[action][2]}")

    if not args.no_sheet:
        for di, rows in made.items():
            W, H, grid = draw_sheet(rows, args.scale)
            sheet = export_dir(create=True) / f"player_sheet_{DIRS[di]}.png"
            encode_png_rgba(sheet, W, H, grid)
            print(f"  sheet {sheet.name}  {W}x{H}")
    print(f"  {len(dirs) * len(ACTIONS)} scenes, {total} frames -> {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
