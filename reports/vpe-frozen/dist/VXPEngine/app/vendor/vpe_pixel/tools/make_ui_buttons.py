"""Draw a sample pressable-widget set for the VPE565 asset library.

3 styles x 9 shapes x 4 states, plus toggle / checkbox / radio indicators:

  styles   retro   VQEAF OS "Retro Utility" handset (charcoal plate, amber focus)
           cream   VQEAF OS "Claude S40 Day" (warm white on cream, terracotta)
           arcade  top-down game green plate, matching tools/make_samples hud_button
  states   normal  press  focus  off
  shapes   wide 96x24, std 72x20, small 48x16, soft 80x22, key 28x28,
           round 32x32, icon24 24x24, icon36 36x36, tab 64x18 (top corners only)
  marks    toggle 40x18, check 14x14, radio 14x14   (on / off)

Every canvas carries a 2 px transparent margin so the focus halo fits and the
pressed state can shift its content down 1 px without resizing the sprite -
states are meant to be swapped at the same coordinates.

VPE reserves 0xFFFF as the transparent key, so no token here may pack to pure
white; near-white ink is (255, 255, 240). pack() enforces that.

Writes:
  Documents/VPE Pixel/sprite/ui/buttons/btn_<style>_<shape>_<state>.vpe
  Documents/VPE Pixel/exports/buttons/<same>.png          RGBA, key transparent
  Documents/VPE Pixel/exports/buttons_sheet_<style>.png   contact sheet per style
  Documents/VPE Pixel/exports/buttons_sheet_all.png       3 sheets stacked

Run from Pixel_Editor root:
  python tools/make_ui_buttons.py [--styles retro,cream] [--no-label] [--scale 2]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

ROOT = Path(__file__).resolve().parent.parent
for p in (str(ROOT), str(ROOT / "tools")):
    if p not in sys.path:
        sys.path.insert(0, p)

from vpx_editor.vpe import c565_to_rgb, rgb_to_565, save_vpe  # noqa: E402
from vpx_editor.gallery import category_dir  # noqa: E402
import make_samples as ms  # noqa: E402
from make_vqeaf_icons import encode_png_rgba  # noqa: E402

Img = ms.Img
CLEAR = 0xFFFF
PAD = 3                      # transparent margin: 1 px rim, gap, 1 px focus halo
Radii = Tuple[int, int, int, int]
Style = Dict[str, Optional[int]]


# ------------------------------------------------------------- colour tokens
def pack(r: int, g: int, b: int) -> int:
    """RGB -> RGB565, never allowed to land on the transparent key."""
    c = rgb_to_565(r, g, b)
    return c if c != CLEAR else rgb_to_565(r, g, b - 8)


def hx(word: int) -> int:
    """Re-pack a device RGB565 constant so it cannot collide with 0xFFFF."""
    r, g, b = c565_to_rgb(word)
    return pack(r, g, b)


def mix(a: int, b: int, t: float) -> int:
    ar, ag, ab = c565_to_rgb(a)
    br, bg, bb = c565_to_rgb(b)
    return pack(int(ar + (br - ar) * t), int(ag + (bg - ag) * t),
                int(ab + (bb - ab) * t))


def well(S: Style) -> int:
    """Recessed surface: icon plates, toggle grooves, check/radio boxes."""
    return mix(S["body"], S["lo"], 0.5)


# cream/retro tokens are the real VQEAF_OS Theme.h constants for those themes.
# "press" is the body colour of the pressed state, "shadow" a 1 px hard drop
# shadow (None on dark backgrounds, where it cannot be seen anyway).
STYLES: Dict[str, Dict[str, Optional[int]]] = {
    "retro": {
        "bg": pack(0, 0, 0), "rim": pack(189, 189, 189),
        "body": pack(24, 24, 24), "hi": pack(74, 74, 74),
        "lo": pack(6, 6, 6), "ink": pack(255, 255, 240),
        "accent": pack(255, 207, 0), "dim": pack(96, 96, 96),
        "shadow": None,
        "sel": pack(44, 44, 48), "press": pack(10, 10, 12),
    },
    "cream": {
        "bg": hx(0xF7BD), "rim": mix(hx(0xE6D9), hx(0x2925), 0.22),
        "body": pack(255, 252, 240),
        "hi": pack(255, 255, 246), "lo": pack(212, 202, 188),
        "ink": hx(0x2925), "accent": hx(0xC328), "dim": hx(0x7BAD),
        "sel": hx(0xF71A), "press": hx(0xF71A),
        "shadow": mix(hx(0xF7BD), hx(0x2925), 0.16),
    },
    "arcade": {
        "bg": pack(24, 28, 42), "rim": pack(24, 52, 36),
        "body": pack(64, 140, 92), "hi": pack(126, 202, 140),
        "lo": pack(28, 72, 48), "ink": pack(244, 248, 255),
        "accent": pack(255, 207, 0), "dim": pack(48, 52, 70),
        "sel": pack(40, 90, 64), "press": pack(34, 86, 58),
        "shadow": None,
    },
}

STATES = ("normal", "press", "focus", "off")

# name, width, height, radii(tl,tr,br,bl), sample label, font scale
SHAPES: List[Tuple[str, int, int, Radii, str, int]] = [
    ("wide", 96, 24, (5, 5, 5, 5), "SELECT", 2),
    ("std", 72, 20, (4, 4, 4, 4), "OK", 2),
    ("small", 48, 16, (3, 3, 3, 3), "YES", 1),
    ("soft", 80, 22, (4, 4, 4, 4), "OPTIONS", 1),
    ("key", 28, 28, (4, 4, 4, 4), "5", 2),
    ("round", 32, 32, (99, 99, 99, 99), "OK", 2),
    ("icon24", 24, 24, (3, 3, 3, 3), "", 1),
    ("icon36", 36, 36, (4, 4, 4, 4), "", 1),
    ("tab", 64, 18, (6, 6, 0, 0), "HOME", 1),
]
SHAPE_BY_NAME = {s[0]: s for s in SHAPES}
MARKS = ("toggle", "check", "radio")
MARK_STATES = ("on", "off")
RECESSED = {"icon24", "icon36"}


# ------------------------------------------------------------------- geometry
def _corner(lx: int, ly: int, r: int) -> bool:
    return (r - lx) ** 2 + (r - ly) ** 2 <= r * r


def inside(px: int, py: int, x: int, y: int, w: int, h: int,
           radii: Radii) -> bool:
    """Is (px, py) inside the rounded rect (x, y, w, h) with per-corner radii?

    Radii are clamped to half the short side, so (99, 99, 99, 99) is a circle.
    """
    if px < x or px >= x + w or py < y or py >= y + h:
        return False
    cap = min(w, h) // 2
    tl, tr, br, bl = (min(r, cap) for r in radii)
    lx, ly = px - x, py - y
    rx, by = w - 1 - lx, h - 1 - ly
    if lx < tl and ly < tl and not _corner(lx, ly, tl):
        return False
    if rx < tr and ly < tr and not _corner(rx, ly, tr):
        return False
    if rx < br and by < br and not _corner(rx, by, br):
        return False
    if lx < bl and by < bl and not _corner(lx, by, bl):
        return False
    return True


def mask(w: int, h: int, radii: Radii, x: int = 0, y: int = 0) -> Set[Tuple[int, int]]:
    return {(px, py)
            for py in range(y, y + h)
            for px in range(x, x + w)
            if inside(px, py, x, y, w, h, radii)}


def shrink(radii: Radii, d: int = 1) -> Radii:
    return tuple(max(0, r - d) for r in radii)  # type: ignore[return-value]


def grow(radii: Radii, d: int = 1) -> Radii:
    return tuple(r + d for r in radii)  # type: ignore[return-value]


def paint(img: Img, pts: Iterable[Tuple[int, int]], c: int) -> None:
    for x, y in pts:
        img.set(x, y, c)


def bevels(pts: Set[Tuple[int, int]]) -> Tuple[set, set, set, set]:
    """Top / left / bottom / right edge pixels of an arbitrary mask."""
    top: Set[Tuple[int, int]] = set()
    left: Set[Tuple[int, int]] = set()
    bottom: Set[Tuple[int, int]] = set()
    right: Set[Tuple[int, int]] = set()
    cols: Dict[int, List[int]] = {}
    rows: Dict[int, List[int]] = {}
    for x, y in pts:
        cols.setdefault(x, []).append(y)
        rows.setdefault(y, []).append(x)
    for x, ys in cols.items():
        top.add((x, min(ys)))
        bottom.add((x, max(ys)))
    for y, xs in rows.items():
        left.add((min(xs), y))
        right.add((max(xs), y))
    return top, left, bottom, right


# ------------------------------------------------------------------- buttons
def draw_plate(img: Img, x: int, y: int, w: int, h: int, radii: Radii,
               S: Style, state: str) -> None:
    """Body + rim + bevels for one button state, on a cleared canvas.

    The rim is a 1 px ring outside the body; the focus state adds a dimmed
    accent halo one pixel further out, which is what PAD reserves room for.
    """
    body = mask(w, h, radii, x, y)
    rimmed = mask(w + 2, h + 2, grow(radii), x - 1, y - 1)
    rim = rimmed - body
    shadow_c = S.get("shadow")
    if state == "off":
        shadow_c = None

    if state == "press":
        body_c = S["press"]
        hi_c, lo_c = S["lo"], S["hi"]
        rim_c = mix(S["rim"], S["bg"], 0.25)
    elif state == "off":
        body_c = mix(S["body"], S["bg"], 0.3)
        hi_c = mix(S["hi"], S["bg"], 0.72)
        lo_c = mix(S["lo"], S["bg"], 0.72)
        rim_c = mix(S["rim"], S["bg"], 0.55)
    else:
        body_c, hi_c, lo_c = S["body"], S["hi"], S["lo"]
        rim_c = S["rim"]

    if state == "focus":
        halo = mask(w + 6, h + 6, grow(radii, 2), x - 3, y - 3) - rimmed
        paint(img, halo, mix(S["accent"], S["bg"], 0.45))
        rim_c = S["accent"]

    if shadow_c is not None:
        paint(img, {(px + 1, py + 1) for px, py in rimmed} - rimmed, shadow_c)
    paint(img, rim, rim_c)
    paint(img, body, body_c)
    top, left, bottom, right = bevels(body)
    paint(img, top | left, hi_c)
    paint(img, bottom | right, lo_c)
    if state == "focus":
        paint(img, top | left, mix(S["accent"], S["body"], 0.45))


def draw_label(img: Img, x: int, y: int, w: int, h: int, S: Style,
               state: str, text: str, scale: int) -> None:
    if not text:
        return
    ink = S["dim"] if state == "off" else S["ink"]
    if state == "press":
        ink = mix(ink, S["bg"], 0.25)
    tw = len(text) * 4 * scale - scale
    th = 5 * scale
    tx = x + (w - tw) // 2
    ty = y + (h - th) // 2 + (1 if state == "press" else 0)
    shadow = mix(ink, S["bg"], 0.55) if state != "off" else None
    img.text(tx, ty, text, ink, scale, shadow=shadow)


def draw_button(S: Style, shape: Tuple, state: str,
                labelled: bool = True) -> Img:
    name, w, h, radii, text, scale = shape
    img = Img(w + 2 * PAD, h + 2 * PAD, CLEAR)
    x, y = PAD, PAD
    draw_plate(img, x, y, w, h, radii, S, state)
    if name in RECESSED:
        plate = mask(w - 6, h - 6, shrink(radii, 3), x + 3, y + 3)
        body_c = well(S)
        paint(img, plate, body_c)
        top, left, bottom, right = bevels(plate)
        paint(img, top | left, mix(body_c, S["lo"], 0.55))
        paint(img, bottom | right, mix(body_c, S["hi"], 0.5))
    draw_label(img, x, y, w, h, S, state, text if labelled else "", scale)
    return img


# ------------------------------------------------------------------ indicators
def draw_toggle(S: Style, state: str) -> Img:
    """A switch: the knob slides and the plate warms toward the accent when on."""
    w, h = 40, 18
    img = Img(w + 2 * PAD, h + 2 * PAD, CLEAR)
    x, y = PAD, PAD
    on = state == "on"
    radii: Radii = (h // 2,) * 4
    plate = dict(S)
    if on:
        plate["body"] = mix(S["body"], S["accent"], 0.22)
        plate["rim"] = mix(S["rim"], S["accent"], 0.6)
        plate["hi"] = mix(S["hi"], S["accent"], 0.35)
    draw_plate(img, x, y, w, h, radii, plate, "normal")

    groove = mask(w - 6, h - 8, (5, 5, 5, 5), x + 3, y + 4)
    paint(img, groove, well(S))
    gtop, gleft, gbottom, gright = bevels(groove)
    paint(img, gtop | gleft, mix(S["bg"], S["lo"], 0.4))
    paint(img, gbottom | gright, mix(S["body"], S["hi"], 0.45))

    d = h - 4
    cx = x + w - 2 - d // 2 if on else x + 2 + d // 2
    knob = mask(d, d, (99, 99, 99, 99), cx - d // 2, y + 2)
    base = S["accent"] if on else mix(S["rim"], S["bg"], 0.15)
    paint(img, knob, base)
    ktop, kleft, kbottom, kright = bevels(knob)
    paint(img, ktop | kleft, mix(base, S["hi"], 0.5))
    paint(img, kbottom | kright, mix(base, S["lo"], 0.55))
    line = mix(base, S["bg"], 0.55)
    for i in (-2, 0, 2):
        paint(img, {(cx + i, yy) for yy in range(y + 5, y + h - 4)}, line)
    return img


def draw_box(S: Style, state: str, kind: str) -> Img:
    w = h = 14
    img = Img(w + 2 * PAD, h + 2 * PAD, CLEAR)
    x, y = PAD, PAD
    on = state == "on"
    radii: Radii = ((7, 7, 7, 7) if kind == "radio" else (3, 3, 3, 3))
    draw_plate(img, x, y, w, h, radii, S, "normal")
    hole = mask(w - 6, h - 6, shrink(radii, 2), x + 3, y + 3)
    paint(img, hole, well(S))
    if not on:
        return img
    if kind == "radio":
        dot = mask(8, 8, (99, 99, 99, 99), x + (w - 8) // 2, y + (h - 8) // 2)
        paint(img, dot, S["accent"])
        return img
    tick = [(x + 3, y + 7), (x + 4, y + 8), (x + 5, y + 9), (x + 6, y + 8),
            (x + 7, y + 7), (x + 8, y + 6), (x + 9, y + 5), (x + 10, y + 4)]
    paint(img, set(tick), S["accent"])
    paint(img, {(px, py + 1) for px, py in tick}, mix(S["accent"], S["bg"], 0.5))
    return img


def draw_mark(S: Style, kind: str, state: str) -> Img:
    if kind == "toggle":
        return draw_toggle(S, state)
    return draw_box(S, state, kind)


# --------------------------------------------------------------- contact sheet
def upscale(px: bytes, w: int, h: int, scale: int) -> Tuple[bytes, int, int]:
    if scale == 1:
        return px, w, h
    out = bytearray(w * scale * h * scale * 3)
    ow = w * scale
    for y in range(h):
        for x in range(w):
            r, g, b = px[(y * w + x) * 3:(y * w + x) * 3 + 3]
            for j in range(scale):
                base = ((y * scale + j) * ow + x * scale) * 3
                for i in range(scale):
                    o = base + i * 3
                    out[o:o + 3] = bytes((r, g, b))
    return bytes(out), ow, h * scale


def to_rgb(img: Img, over: int) -> Tuple[bytes, int, int]:
    """Flatten an RGB565 canvas onto `over`, treating CLEAR as `over`."""
    r0, g0, b0 = c565_to_rgb(over)
    out = bytearray()
    for c in img.px:
        if c == CLEAR:
            out += bytes((r0, g0, b0))
        else:
            out += bytes(c565_to_rgb(c))
    return bytes(out), img.w, img.h


def build_sheet(style: str, S: Style, labelled: bool) -> Img:
    rows: List[Tuple[str, List[Tuple[str, Img]]]] = []
    for shape in SHAPES:
        rows.append((shape[0], [(st, draw_button(S, shape, st, labelled))
                                for st in STATES]))
    for kind in MARKS:
        rows.append((kind, [(st, draw_mark(S, kind, st)) for st in MARK_STATES]))

    cell_w = max(max(im.w for _, im in cells) for _, cells in rows) + 6
    cell_h = max(max(im.h for _, im in cells) for _, cells in rows) + 6
    gutter = 46
    sheet = Img(gutter + cell_w * len(STATES) + 4,
                12 + cell_h * len(rows) + 12, S["bg"])
    ink, dim = S["ink"], mix(S["rim"], S["ink"], 0.45)
    for i, st in enumerate(STATES):               # column headings
        sheet.text(gutter + 6 + i * cell_w, 2, st.upper(), ink, 1)
    for r, (name, cells) in enumerate(rows):      # row headings + sprites
        ry = 12 + r * cell_h
        sheet.text(2, ry + 4, name, dim, 1)
        for i, (st, im) in enumerate(cells):
            rgb, w, h = to_rgb(im, S["bg"])
            ox = gutter + i * cell_w + (cell_w - w) // 2
            oy = ry + (cell_h - h) // 2
            for y in range(h):
                for x in range(w):
                    o = (y * w + x) * 3
                    sheet.set(ox + x, oy + y,
                              rgb_to_565(rgb[o], rgb[o + 1], rgb[o + 2]))
    return sheet


# ----------------------------------------------------------------------- main
def write_png(path: Path, img: Img) -> None:
    encode_png_rgba(path, img.w, img.h, img.px)


def main(argv: Sequence[str] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--styles", default=",".join(STYLES),
                    help="comma list of style keys (retro,cream,arcade)")
    ap.add_argument("--no-label", action="store_true",
                    help="emit blank buttons with no baked sample text")
    ap.add_argument("--scale", type=int, default=2, choices=(1, 2, 3),
                    help="upscale factor for the contact sheets")
    ap.add_argument("--no-png", action="store_true",
                    help="write .vpe only, skip exports/ PNGs")
    args = ap.parse_args(argv)

    picked = [s.strip() for s in args.styles.split(",") if s.strip()]
    unknown = [s for s in picked if s not in STYLES]
    if unknown:
        raise SystemExit(f"unknown style(s): {', '.join(unknown)}; "
                         f"choose from {', '.join(STYLES)}")

    out_dir = category_dir("sprite").joinpath("ui", "buttons")
    out_dir.mkdir(parents=True, exist_ok=True)
    export_dir = category_dir("sprite").parent / "exports" / "buttons"
    export_dir.mkdir(parents=True, exist_ok=True)

    labelled = not args.no_label
    count = 0
    sheets: List[Tuple[bytes, int, int]] = []
    for style in picked:
        S = STYLES[style]
        for shape in SHAPES:
            for state in STATES:
                name = f"btn_{style}_{shape[0]}_{state}"
                img = draw_button(S, shape, state, labelled)
                save_vpe(out_dir / f"{name}.vpe", img.w, img.h, img.px)
                if not args.no_png:
                    write_png(export_dir / f"{name}.png", img)
                count += 1
        for kind in MARKS:
            for state in MARK_STATES:
                name = f"btn_{style}_{kind}_{state}"
                img = draw_mark(S, kind, state)
                save_vpe(out_dir / f"{name}.vpe", img.w, img.h, img.px)
                if not args.no_png:
                    write_png(export_dir / f"{name}.png", img)
                count += 1
        rgb, sw, sh = to_rgb(build_sheet(style, S, labelled), S["bg"])
        big, w, h = upscale(rgb, sw, sh, args.scale)
        sheets.append((big, w, h))
        sheet_path = export_dir.parent / f"buttons_sheet_{style}.png"
        sheet_path.write_bytes(_png_rgb(w, h, big))
        print(f"{style:7s} "
              f"{len(SHAPES) * len(STATES) + len(MARKS) * len(MARK_STATES):>3} "
              f"sprites  sheet {w}x{h} -> {sheet_path.name}")

    if len(sheets) > 1:
        gap = 8
        w = max(s[1] for s in sheets)
        h = sum(s[2] for s in sheets) + gap * (len(sheets) - 1)
        canvas = bytearray(b"\x10\x10\x10" * (w * h))
        oy = 0
        for rgb, sw, sh in sheets:
            for y in range(sh):
                src = rgb[y * sw * 3:(y + 1) * sw * 3]
                o = ((oy + y) * w) * 3
                canvas[o:o + len(src)] = src
            oy += sh + gap
        (export_dir.parent / "buttons_sheet_all.png").write_bytes(
            _png_rgb(w, h, bytes(canvas)))
        print(f"master  sheet {w}x{h} -> buttons_sheet_all.png")

    print(f"vpe    {out_dir}")
    if not args.no_png:
        print(f"png    {export_dir}")
    print(f"sprites {count}  label={'on' if labelled else 'off'}")
    return 0


def _png_rgb(w: int, h: int, rgb: bytes) -> bytes:
    import struct
    import zlib
    raw = bytearray()
    for y in range(h):
        raw.append(0)
        raw += rgb[y * w * 3:(y + 1) * w * 3]

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (struct.pack(">I", len(data)) + tag + data
                + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))

    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
            + chunk(b"IEND", b""))


if __name__ == "__main__":
    raise SystemExit(main())
