#!/usr/bin/env python3
"""make_fnynn_anim.py - tu dong ve animation cho game Fnynn (MRE 240x320).

Ve procedural theo dung style/palette cua tools/build_rhynn_assets.py
(Nhhan vat Stardew 16x24, mob, effect 16x16), xuat 3 dang:

  Documents\\VPE Pixel\\fnynn\\anim\\*.vpea   (mo trong Pixel_Editor: timeline,
                                               Space preview, sua tay tung frame)
  <Fnynn>/resources/gen/*.vpa                 (game load truc tiep, xem VPA_FMT)
  <Fnynn>/run/preview/fnynn_anim_sheet.png    (contact sheet kiem tra)

VPA_FMT (game-side, little-endian):
  0   5  magic "VPA01" | 5  1  ver=1 | 6  2  w | 8  2  h
  10  2  nframes (1..64) | 12  2  ticks_per_frame | 14  1  loop | 15  1  0
  16  frames: RGB565 LE (w*h*2) + mask 1-bit ((w*h+7)//8), giong .raw

Quy uoc trong suot: RGBA alpha<128 -> mask 0. Rieng .vpea khong co mask
nen pixel trong suot ma hoa 0xFFFF; tranh dung trang tinh (255,255,255)
cho chi tiet can hien (slash dung 240,246,252).

  player : pa_c<class>_<d|u|s>_{atk,cast,hurt}   3x3x3 = 27 anim
  mob    : ma_{slime,bat,skel,fslime,golem}      5 anim x 4f
  effect : fx_{slash,hit,fire,boom,heal,pois}    6 anim

Chay:  python tools/make_fnynn_anim.py [--only pa_c0_d_atk,ma_slime]
"""
from __future__ import annotations

import argparse
import struct
import sys
from pathlib import Path

TOOLROOT = Path(__file__).resolve().parent
SYSROOT = TOOLROOT.parent
for _p in (str(SYSROOT), str(TOOLROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)
sys.path.insert(0, r"C:\Users\doxuanhop\Documents\VXP Projects\Fnynn\tools")

from PIL import Image, ImageDraw  # noqa: E402

import build_rhynn_assets as R  # noqa: E402 (palette + base frames)
from vpx_editor import vpe as VPE  # noqa: E402
from vpx_editor import vpea as VPEA  # noqa: E402

FNYN = Path(r"C:\Users\doxuanhop\Documents\VXP Projects\Fnynn")
GEN = FNYN / "resources" / "gen"
ANIM_DIR = Path.home() / "Documents" / "VPE Pixel" / "fnynn" / "anim"
SHEET = FNYN / "run" / "preview" / "fnynn_anim_sheet.png"

VPA_MAGIC = b"VPA01"
VPA_VER = 1

CLASS_SD = (
    ((196, 60, 60), (150, 40, 40), (150, 150, 160)),
    ((90, 90, 220), (60, 60, 170), (40, 40, 90)),
    ((70, 170, 100), (46, 128, 70), (50, 60, 50)),
)
HAIR_SD = ((90, 60, 34), (40, 36, 44), (140, 110, 60))
DIRS = ((0, "d"), (1, "u"), (2, "s"))
HILT = (116, 78, 42)
ARC = (240, 246, 252)          # trang mo (khong phai 0xFFFF)
GLOW = (255, 220, 120)
FIRE = (250, 140, 40)
FIRE_HI = (255, 214, 120)
LEAF_P = (120, 230, 150)


def rgba_to_565_list(im: Image.Image):
    """RGBA -> (pixels565 list, mask bytes). Transparent (a<128) -> 0xFFFF pixel."""
    im = im.convert("RGBA")
    w, h = im.size
    px = im.load()
    out, mask = [], bytearray((w * h + 7) // 8)
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            o = y * w + x
            if a >= 128:
                mask[o >> 3] |= 0x80 >> (o & 7)
                out.append(VPE.rgb_to_565(r, g, b))
            else:
                out.append(0xFFFF)
    return out, bytes(mask)


def encode_vpa(w: int, h: int, frames_rgba, tpf: int, loop: bool) -> bytes:
    n = len(frames_rgba)
    assert 1 <= n <= 64
    head = (VPA_MAGIC + bytes((VPA_VER,)) +
            struct.pack("<HHH", w, h, n) +
            struct.pack("<H", int(tpf)) +
            bytes((1 if loop else 0, 0)))
    body = bytearray()
    for im in frames_rgba:
        assert im.size == (w, h), im.size
        im = im.convert("RGBA")
        px = im.load()
        pix = bytearray(w * h * 2)
        mask = bytearray((w * h + 7) // 8)
        for y in range(h):
            for x in range(w):
                r, g, b, a = px[x, y]
                o = y * w + x
                if a >= 128:
                    mask[o >> 3] |= 0x80 >> (o & 7)
                else:
                    r = g = b = 0
                v = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
                pix[o * 2] = v & 0xFF
                pix[o * 2 + 1] = (v >> 8) & 0xFF
        body += pix + mask
    return head + bytes(body)


def save_anim(name: str, frames, tpf: int, loop: bool, sheet_cells: list):
    """frames: list PIL RGBA (cung size). Ghi .vpea + .vpa, gop sheet preview."""
    w, h = frames[0].size
    px565 = []
    for im in frames:
        p, _ = rgba_to_565_list(im)
        px565.append(p)
    ANIM_DIR.mkdir(parents=True, exist_ok=True)
    VPEA.save_vpea(ANIM_DIR / f"{name}.vpea", w, h, px565,
                   delay_ms=max(10, int(tpf) * 100), loop=loop)
    GEN.mkdir(parents=True, exist_ok=True)
    (GEN / f"{name}.vpa").write_bytes(encode_vpa(w, h, frames, tpf, loop))
    sheet_cells.append((name, frames))
    print(f"  {name:18s} {w}x{h} x{len(frames)} tpf={tpf} {'loop' if loop else 'once'}")


# ------------------------------------------------------- player attack/cast
def sword_line(d: ImageDraw.ImageDraw, x0, y0, x1, y1):
    d.line([x0, y0, x1, y1], fill=R.BLADE + (255,), width=2)
    d.line([x0, y0, x1, y1], fill=(250, 252, 255, 255), width=1)


def player_attack(cls: int, dirn: int):
    cloth, cloth_dk, hat = CLASS_SD[cls]
    hair = HAIR_SD[cls]
    out = []
    poses = [
        dict(dx=0, sw=(-4, -6, 2, 2), arc=[]),
        dict(dx=1, sw=(10, 2, 15, 10), arc=[(4, 12), (5, 10), (7, 8)]),
        dict(dx=1, sw=(2, 12, 14, 16), arc=[(3, 13), (5, 10), (8, 8), (11, 8), (13, 10)]),
        dict(dx=0, sw=(8, 8, 12, 14), arc=[(12, 12), (13, 14)]),
    ]
    for i, p in enumerate(poses):
        im = R.sd_player(cloth, cloth_dk, hat, hair, dirn, 1 if i in (1, 2) else 0).copy()
        d = ImageDraw.Draw(im)
        if dirn == 0:      # nhin xuong: tay phai vung ngang truoc mat
            ax = 13 + p["dx"]
            d.rectangle([ax, 13, ax + 1, 15], fill=R.SKIN + (255,))
            x0, y0, x1, y1 = p["sw"]
            sword_line(d, x0, y0 + 12, x1, y1 + 10)
            for ax_, ay_ in p["arc"]:
                d.point([ax_, ay_ + 8], fill=ARC + (255,))
                d.point([ax_ + 1, ay_ + 8], fill=ARC + (255,))
        elif dirn == 1:    # nhin len: chem vong qua dau
            ax = 3 - p["dx"]
            d.rectangle([ax - 1, 12, ax, 14], fill=R.SKIN + (255,))
            x0, y0, x1, y1 = p["sw"]
            sword_line(d, 15 - x1, 2 + i, 15 - x0, 6 + i)
            for ax_, ay_ in p["arc"]:
                d.point([15 - ax_, ay_], fill=ARC + (255,))
        else:              # ngang: dam + chem ngang
            ax = 11 + p["dx"]
            d.rectangle([ax, 14, ax + 1, 16], fill=R.SKIN + (255,))
            x0, y0, x1, y1 = p["sw"]
            sword_line(d, x0 + 2, y0 + 8, x1 + 2, y1 + 6)
            for ax_, ay_ in p["arc"]:
                d.point([ax_ + 2, ay_ + 6], fill=ARC + (255,))
                d.point([ax_ + 3, ay_ + 6], fill=ARC + (255,))
        # chuoi kiem
        d.point([13 if dirn != 1 else 3, 16], fill=HILT + (255,))
        out.append(im)
    return out


def player_cast(cls: int, dirn: int):
    cloth, cloth_dk, hat = CLASS_SD[cls]
    hair = HAIR_SD[cls]
    out = []
    for i in range(4):
        im = R.sd_player(cloth, cloth_dk, hat, hair, dirn, 0).copy()
        d = ImageDraw.Draw(im)
        # gay giơ len + quag sang lan rong
        sx = 13 if dirn != 1 else 2
        d.line([sx, 16, sx, 6 - i], fill=(150, 110, 60, 255), width=2)
        for r in range(i + 1):
            for ox, oy in ((0, -r - 1), (-r - 1, 0), (r + 1, 0)):
                d.point([sx + ox, 5 - i + oy], fill=GLOW + (255,))
        d.point([sx, 5 - i], fill=(255, 246, 200, 255))
        out.append(im)
    return out


def player_hurt(cls: int, dirn: int):
    cloth, cloth_dk, hat = CLASS_SD[cls]
    hair = HAIR_SD[cls]
    out = []
    for i, dx in ((0, -1), (1, 1)):
        im = R.sd_player(cloth, cloth_dk, hat, hair, dirn, i).copy()
        bg = Image.new("RGBA", im.size, (0, 0, 0, 0))
        bg.alpha_composite(im, (dx, 0))
        out.append(bg)
    return out


# ------------------------------------------------------------- mob 4-frame
def _slime4(fire: bool):
    body, hi, dark, eye = ((96, 206, 128), (120, 226, 150), (60, 150, 88), (18, 40, 24)) \
        if not fire else ((232, 116, 52), (250, 176, 92), (176, 66, 26), (90, 26, 10))
    gloss = (255, 255, 255, 255) if not fire else (255, 220, 120, 255)
    out = []
    for f in range(4):
        im = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
        px = im.load()
        squash = (0, 1, 0, -1)[f]          # nen/xẹp theo nhip
        top = 5 + max(0, squash)
        wid = 1 if squash < 0 else 0
        for y in range(top, 16):
            for x in range(16):
                ex = (x - 8) * (3 + wid) / 3
                if ex ** 2 * 3 + (y - 13) ** 2 * 12 < 120:
                    px[x, y] = (*body, 255)
        for y in range(top - 2, top + 1):
            for x in range(5, 11):
                if (x - 8) ** 2 < 8:
                    px[x, y] = (*hi, 255)
        ey = 9 + max(0, squash)
        if f == 2:                          # nhay mat frame 2
            for ex in (6, 9):
                px[ex, ey] = (*dark, 255)
        else:
            for ex in (6, 9):
                px[ex, ey] = (*eye, 255)
                px[ex, ey + 1] = gloss
        for x in range(4, 12):
            px[x, 14] = (*dark, 255)
        out.append(im)
    return out


def _bat4():
    out = []
    for f in range(4):
        im = Image.new("RGBA", (16, 12), (0, 0, 0, 0))
        px = im.load()
        for y in range(3, 10):
            for x in range(5, 11):
                if (x - 8) ** 2 + (y - 6) ** 2 < 9:
                    px[x, y] = (150, 84, 196, 255)
        # canh: len/xuong/giữa/xuong (4 pha)
        prof = ([1, 3, 5, 3][f], [2, 4, 6, 4][f])
        for x in range(0, 5):
            k = x / 4
            wy = int(prof[0] + (prof[1] - prof[0]) * k)
            for dy in (0, 1):
                px[x, wy + dy] = (110, 58, 150, 255)
                px[15 - x, wy + dy] = (110, 58, 150, 255)
        px[6, 6] = (255, 240, 130, 255)
        px[9, 6] = (255, 240, 130, 255)
        if f != 2:
            px[7, 2] = (255, 255, 255, 255)
            px[8, 2] = (255, 255, 255, 255)
        out.append(im)
    return out


def _skel4():
    bone, bone_dk = (232, 230, 218), (180, 178, 168)
    rib, rib_dk = (222, 220, 208), (160, 158, 150)
    out = []
    for f in range(4):
        im = Image.new("RGBA", (16, 22), (0, 0, 0, 0))
        px = im.load()
        lean = 1 if f in (1, 3) else 0
        step = f % 2
        for y in range(1, 8):
            for x in range(4, 12):
                if (x - 8) ** 2 + (y - 5) ** 2 * 1.4 < 14:
                    px[x, y] = (*bone, 255)
        px[6, 5] = (200, 40, 40, 255)
        px[9, 5] = (200, 40, 40, 255)
        for x in range(6, 10):
            px[x, 7] = (*bone_dk, 255)
        for y in range(8, 15):
            for x in range(6, 10):
                px[x, y] = (*(rib if y % 2 else rib_dk), 255)
            px[5, y] = (*bone_dk, 255)
            px[10 + lean, y] = (*bone_dk, 255)
        # kiem vung theo nhip buoc
        sw = f - 1
        for y in range(4, 9):
            px[3 + max(0, sw), y] = R.BLADE
        for x in range(3, 6):
            px[x + max(0, sw), 9] = (*rib, 255)
        if step == 0:
            for y in range(15, 22):
                px[5, y] = (*rib, 255)
                px[10, y] = (*rib, 255)
        else:
            for y in range(15, 19):
                px[5, y] = (*rib, 255)
            for y in range(15, 22):
                px[10 + lean, y] = (*rib, 255)
        out.append(im)
    return out


def _golem4():
    rock, rock_dk = (78, 68, 78), (48, 40, 50)
    lava, lava_hi = (255, 122, 30), (255, 196, 70)
    out = []
    for f in range(4):
        im = Image.new("RGBA", (16, 22), (0, 0, 0, 0))
        px = im.load()
        lean = 1 if f in (1, 3) else 0
        bob = 1 if f == 2 else 0
        for y in range(0, 6):
            for x in range(3, 13):
                if (x - 8) ** 2 + (y - 4) ** 2 * 2 < 20:
                    px[x, y + bob] = (*rock, 255)
        px[5, 2 + bob] = (*lava, 255)
        px[10, 2 + bob] = (*lava, 255)
        if f % 2 == 0:
            px[5, 3 + bob] = (*lava_hi, 255)
            px[10, 3 + bob] = (*lava_hi, 255)
        for y in range(6, 13):
            for x in range(4, 12):
                px[x, y + bob] = (*rock, 255)
            px[2, y + bob] = (*rock_dk, 255)
            px[13 - lean, y + bob] = (*rock_dk, 255)
        for y in range(7 + f % 3, 12, 3):   # nut lua chay doc nguc
            px[6, y + bob] = (*lava, 255)
            px[9, min(12, y + 1) + bob] = (*lava_hi, 255)
        for y in range(13, 17):
            for x in range(4, 7):
                px[x, y + bob] = (*rock_dk, 255)
            for x in range(9, 12):
                px[x + lean, y + bob] = (*rock_dk, 255)
        out.append(im)
    return out


# ------------------------------------------------------------------ effect
def _fx_slash():
    out = []
    for f in range(4):
        im = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        # cung quet mo rong dan: goc 200->340 do
        import math
        for k in range(6):
            a = (200 + f * 35 + k * 8) * math.pi / 180
            x = int(8 + 6.5 * math.cos(a))
            y = int(8 + 6.5 * math.sin(a))
            d.point([x, y], fill=ARC + (255,))
            if k % 2 == 0:
                d.point([x, y + 1], fill=(200, 214, 232, 255))
        d.point([8, 8], fill=(255, 252, 240, 255))
        out.append(im)
    return out


def _fx_hit():
    out = []
    for f in range(3):
        im = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        r = 2 + f * 2
        d.ellipse([8 - r, 8 - r, 8 + r, 8 + r], outline=(255, 230, 160, 255))
        d.point([8, 8], fill=(255, 252, 240, 255))
        for dx, dy in ((0, -r - 1), (0, r + 1), (-r - 1, 0), (r + 1, 0)):
            d.point([8 + dx, 8 + dy], fill=ARC + (255,))
        out.append(im)
    return out


def _fx_fire():
    out = []
    for f in range(4):
        im = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        lean = (0, 1, 0, -1)[f]
        d.ellipse([5, 8, 11, 15], fill=FIRE + (255,))
        d.ellipse([6, 4 - (f % 2), 10, 10], fill=(250, 170, 60, 255))
        d.ellipse([7 + lean, 2 + (f % 2), 9 + lean, 7], fill=FIRE_HI + (255,))
        out.append(im)
    return out


def _fx_boom():
    out = []
    for f in range(5):
        im = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        if f == 0:
            d.ellipse([4, 4, 12, 12], fill=(255, 246, 220, 255))
        elif f in (1, 2):
            r = 5 + f
            d.ellipse([8 - r, 8 - r, 8 + r, 8 + r], outline=FIRE_HI + (255,))
            d.ellipse([6, 6, 10, 10], fill=FIRE + (255,))
        else:
            import math
            for k in range(8):
                a = k * math.pi / 4 + f
                x = int(8 + (4 + f) * math.cos(a))
                y = int(8 + (4 + f) * math.sin(a))
                d.point([x, y], fill=FIRE + (255,))
            d.ellipse([6, 6, 10, 10], fill=(120, 90, 80, 255))
        out.append(im)
    return out


def _fx_heal():
    out = []
    for f in range(4):
        im = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        y0 = 12 - f * 2
        d.line([8, y0 - 3, 8, y0 + 3], fill=LEAF_P + (255,), width=1)
        d.line([8 - 3, y0, 8 + 3, y0], fill=LEAF_P + (255,), width=1)
        for ox, oy in ((-4, 2 + f), (4, 0 - f), (-2, -3 + f)):
            d.point([8 + ox, 8 + oy], fill=(220, 255, 220, 255))
        out.append(im)
    return out


def _fx_pois():
    out = []
    for f in range(4):
        im = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        d.ellipse([4, 9, 12, 15], fill=(110, 160, 90, 255))
        for k in range(3):
            x = 5 + ((k * 4 + f * 2) % 7)
            y = 8 - ((f + k) % 3) * 2
            d.ellipse([x, y, x + 2, y + 2], outline=(150, 200, 130, 255))
        out.append(im)
    return out


# ------------------------------------------------------------------- main
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    args = ap.parse_args()
    only = {s.strip() for s in args.only.split(",") if s.strip()}

    jobs = []  # (name, frames, tpf, loop)
    for cls in range(3):
        for dirn, tag in DIRS:
            jobs.append((f"pa_c{cls}_{tag}_atk", player_attack(cls, dirn), 2, False))
            jobs.append((f"pa_c{cls}_{tag}_cast", player_cast(cls, dirn), 2, False))
            jobs.append((f"pa_c{cls}_{tag}_hurt", player_hurt(cls, dirn), 4, False))
    for nm, fn in (("slime", lambda: _slime4(False)), ("bat", _bat4), ("skel", _skel4),
                   ("fslime", lambda: _slime4(True)), ("golem", _golem4)):
        jobs.append((f"ma_{nm}", fn(), 7, True))
    for nm, fn, tpf, loop in (
            ("slash", _fx_slash, 2, False), ("hit", _fx_hit, 2, False),
            ("fire", _fx_fire, 2, False), ("boom", _fx_boom, 3, False),
            ("heal", _fx_heal, 3, False), ("pois", _fx_pois, 4, True)):
        jobs.append((f"fx_{nm}", fn(), tpf, loop))

    cells = []
    n = 0
    for name, frames, tpf, loop in jobs:
        if only and name not in only:
            continue
        save_anim(name, frames, tpf, loop, cells)
        n += 1

    # contact sheet preview
    SHEET.parent.mkdir(parents=True, exist_ok=True)
    cols = 8
    cw, chh = 16 * 4 + 8, 24 * 4 + 22
    rows = (len(cells) + cols - 1) // cols
    sheet = Image.new("RGBA", (cols * cw, rows * chh), (30, 32, 44, 255))
    dd = ImageDraw.Draw(sheet)
    for i, (name, frames) in enumerate(cells):
        cx, cy = (i % cols) * cw, (i // cols) * chh
        x = cx + 4
        for fr in frames[:8]:
            f2 = fr.resize((fr.width * 4, fr.height * 4), Image.NEAREST)
            sheet.alpha_composite(f2, (x, cy + 18))
            x += fr.width * 4 + 2
        dd.text((cx + 4, cy + 4), f"{name} x{len(frames)}", fill=(255, 255, 160, 255))
    sheet.convert("RGB").save(SHEET)
    print(f"OK {n} anim -> {ANIM_DIR} + {GEN}")
    print(f"  sheet -> {SHEET}")


if __name__ == "__main__":
    main()
