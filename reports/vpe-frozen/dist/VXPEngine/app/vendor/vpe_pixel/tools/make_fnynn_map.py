#!/usr/bin/env python3
"""make_fnynn_map.py - ve lai TOAN BO do hoa map/sprite Fnynn theo style
5 anh tham khao top-down trong docs/ai_ui_design (con co san kiem tra,
nong trai mua, hon dao noi):

  - co kiem tra 2 bung (chanh tuoi / xanh dua) + luoi co + rim toi day
  - cat chuyen co -> nuoc/cat/dat/da kieu overhang tuft (rim scallop)
  - duong mon tan + pebble, cobblestone tron, san hang da + tuong gach
  - cay tron nhieu lop sang/toi, hoa 4 mua, berry, cay trong 4 gian doan
  - nha/ho/rom/coi xay kieu Summer Farm + Simple Autumn
  - menu bg thung lung nong trai moi

Xuat 3 dang (ten + kich thuoc GIU NGUYEN nhu resources/gen/*.raw cu ->
game khong can doi code, ngoai tru t_grass2 kiem tra moi):

  Documents\\VPE Pixel\\fnynn_map\\tile\\<ten>.png|.vpe     (15 tile 16x16)
  Documents\\VPE Pixel\\fnynn_map\\sprite\\<ten>.png|.vpe    (con lai)
  <Fnynn>\\run\\preview\\fnynn_map_sheet.png   (contact sheet 4x co nhan)
  <Fnynn>\\run\\preview\\fnynn_map_mock.png    (ghép scene 240x320 kiem tra)

Nhân vật/mob giữ khung gốc cua build_rhynn_assets.py (R.sd_player,
R.*_frame) + polish vien/shading -> animation .vpa (make_fnynn_anim.py)
van khop. PNG co alpha that; .vpe hoa trang trong suot 0xFFFF theo quy
uoc Pixel_Editor.

Chay:  python tools/make_fnynn_map.py [--only t_grass,t_grass2,...]
           [--no-sheet] [--no-vpe]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

TOOLROOT = Path(__file__).resolve().parent
SYSROOT = TOOLROOT.parent
for _p in (str(SYSROOT), str(TOOLROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)
sys.path.insert(0, r"C:\Users\doxuanhop\Documents\VXP Projects\Fnynn\tools")

from PIL import Image, ImageDraw  # noqa: E402

from vpx_editor import vpe as VPE  # noqa: E402

FNYN = Path(r"C:\Users\doxuanhop\Documents\VXP Projects\Fnynn")
ROOT = Path.home() / "Documents" / "VPE Pixel" / "fnynn_map"
SHEET = FNYN / "run" / "preview" / "fnynn_map_sheet.png"
MOCK = FNYN / "run" / "preview" / "fnynn_map_mock.png"

# ---------------------------------------------------------------- palette
# Co 2 bung kiem tra (ref 1): chanh tuoi + xanh dua, rim scallop toi
# (ref 2).
G_A = (134, 196, 74)          # bung sang
G_A_HI = (160, 218, 96)
G_A_DK = (108, 166, 58)
G_B = (102, 168, 58)          # bung toi
G_B_HI = (128, 190, 76)
G_B_DK = (80, 136, 48)
G_RIM = (52, 100, 38)         # vien co tom (scallop)
TUFT_HI = (176, 224, 106)
TUFT_MID = (140, 200, 84)

DIRT = (176, 132, 84)
DIRT_HI = (202, 160, 106)
DIRT_DK = (138, 98, 60)
SAND = (230, 204, 146)
SAND_HI = (244, 226, 176)
SAND_DK = (202, 172, 112)
PATH = (196, 162, 108)
PATH_HI = (220, 192, 142)
PATH_DK = (160, 128, 82)
PEB = (150, 144, 136)
PEB_HI = (184, 180, 172)

WATER = (58, 142, 208)
WATER_HI = (120, 190, 240)
WATER_DK = (38, 108, 178)
FOAM = (190, 228, 250)

COBB = (158, 158, 166)
COBB_HI = (192, 192, 200)
COBB_DK = (116, 116, 128)
MORTAR = (94, 92, 106)
CAVE_F = (94, 88, 108)
CAVE_F_HI = (120, 114, 134)
CAVE_F_DK = (70, 64, 86)
BRICK = (86, 78, 98)
BRICK_HI = (122, 114, 134)
BRICK_DK = (58, 52, 68)

WOOD = (150, 106, 62)
WOOD_HI = (182, 136, 86)
WOOD_DK = (112, 76, 42)
LEAF = (78, 156, 66)
LEAF_HI = (118, 196, 92)
LEAF_DK = (48, 110, 46)
LEAF_DEEP = (34, 84, 38)
TRUNK = (122, 82, 46)
TRUNK_DK = (90, 60, 34)

BARN_RED = (190, 70, 56)
BARN_RED_DK = (142, 46, 40)
TRIM = (240, 232, 210)
ROOF_GRAY = (122, 120, 134)
ROOF_GRAY_DK = (90, 88, 102)
HOUSE_TEAL = (142, 202, 188)
HOUSE_TEAL_DK = (104, 164, 150)
HOUSE_WOOD = (168, 116, 70)
HOUSE_WOOD_DK = (128, 84, 50)
MILL_BRICK = (150, 104, 78)
MILL_BRICK_DK = (112, 74, 56)
SAIL = (238, 232, 212)
HAY = (224, 192, 112)
HAY_DK = (186, 152, 86)
OUT = (30, 34, 26)            # vien outline chung
GOLD = (250, 204, 72)
GOLD_HI = (255, 234, 150)

TILE = 16


# ---------------------------------------------------------------- helpers
class Rng:
    def __init__(self, seed):
        self.s = (seed * 2654435761) & 0x7FFFFFFF or 1

    def next(self, n):
        self.s = (self.s * 1103515245 + 12345) & 0x7FFFFFFF
        return (self.s >> 8) % n


def seed_of(name):
    return sum((i + 1) * ord(c) for i, c in enumerate(name)) & 0x7FFFFFFF


def safe(c):
    """Khong bao gio trang tinh 0xFFFF (quy uoc trong suot cua .vpe)."""
    r, g, b = (max(0, min(250, v)) for v in c[:3])
    if r >= 248 and g >= 252 and b >= 248:
        b = 240
    return (r, g, b)


def new(w, h, color=None):
    return Image.new("RGBA", (w, h), (*safe(color), 255) if color else (0, 0, 0, 0))


def put(im, x, y, c, a=255):
    if 0 <= x < im.width and 0 <= y < im.height:
        im.load()[x, y] = (*safe(c), a)


def get(im, x, y):
    return im.load()[x, y]


def speckle(im, name, n, cols, x0=0, y0=0, x1=None, y1=None):
    rng = Rng(seed_of(name))
    w, h = im.size
    x1 = w - 1 if x1 is None else x1
    y1 = h - 1 if y1 is None else y1
    for i in range(n):
        x = rng.next(x1 - x0 + 1) + x0
        y = rng.next(y1 - y0 + 1) + y0
        put(im, x, y, cols[i % len(cols)])


def shade_rows(im, top_hi, bot_dk):
    """Nhe sang 1 hang dinh, tom toi 2 hang day -> co sau do nhat quan."""
    w, h = im.size
    px = im.load()
    for x in range(w):
        r, g, b, a = px[x, 0]
        if a:
            px[x, 0] = (min(250, r + top_hi), min(250, g + top_hi), min(250, b + top_hi), a)
        for y in (h - 2, h - 1):
            r, g, b, a = px[x, y]
            if a:
                k = bot_dk if y == h - 1 else bot_dk // 2
                px[x, y] = (max(0, r - k), max(0, g - k), max(0, b - k), a)


def outline(im, color=OUT):
    """Vien 4-huong quanh silhouette ( RGBA trong, khong de len pixel cu)."""
    w, h = im.size
    px = im.load()
    add = []
    for y in range(h):
        for x in range(w):
            if px[x, y][3] >= 128:
                continue
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nx, ny = x + dx, y + dy
                if 0 <= nx < w and 0 <= ny < h and px[nx, ny][3] >= 128:
                    add.append((x, y))
                    break
    for x, y in add:
        px[x, y] = (*color, 255)
    return im


def disc(im, cx, cy, r, c, sq=1):
    for y in range(cy - r, cy + r + 1):
        for x in range(cx - r, cx + r + 1):
            if (x - cx) ** 2 + (y - cy) ** 2 * sq <= r * r:
                put(im, x, y, c)


# ---------------------------------------------------------------- tiles
def _blade_cluster(im, x, y, hi, dk):
    """Cum 3 luoi co (ref 1: van co trong tung o)."""
    for bx, hgt in ((0, 2), (1, 3), (2, 2)):
        for i in range(hgt):
            put(im, x + bx, y - i, hi if i == hgt - 1 else dk)


def grass_tile(bright):
    base, hi, dk = (G_A, G_A_HI, G_A_DK) if bright else (G_B, G_B_HI, G_B_DK)
    im = new(TILE, TILE, base)
    name = "grassA" if bright else "grassB"
    speckle(im, name, 12, [dk])
    speckle(im, name + "h", 8, [hi])
    rng = Rng(seed_of(name))
    for _ in range(3):                       # 3 cum blade + 2 diem toi
        x, y = 2 + rng.next(12), 4 + rng.next(10)
        _blade_cluster(im, x, y, hi, dk)
    for _ in range(3):
        put(im, 1 + rng.next(14), 1 + rng.next(14), dk)
    shade_rows(im, 10, 18)
    return im


def dirt_tile():
    im = new(TILE, TILE, DIRT)
    speckle(im, "dirt", 18, [DIRT_DK, DIRT_HI])
    rng = Rng(seed_of("dirt"))
    for _ in range(4):                       # con dat ron
        x, y = 1 + rng.next(12), 1 + rng.next(12)
        put(im, x, y, DIRT_DK), put(im, x + 1, y, DIRT_DK)
        put(im, x, y + 1, DIRT_HI)
    shade_rows(im, 8, 16)
    return im


def cobble_tile():
    """Cobblestone tron ken kieu dai da ref 1 (vien sang, mortar toi)."""
    im = new(TILE, TILE, MORTAR)
    stones = ((1, 1, 5, 4), (7, 1, 4, 4), (12, 2, 3, 5), (1, 7, 4, 4),
              (6, 6, 5, 4), (12, 9, 3, 4), (2, 12, 4, 3), (7, 12, 5, 3))
    rng = Rng(seed_of("cobble"))
    for sx, sy, sw, sh in stones:
        c = [COBB, COBB, (168, 166, 174)][rng.next(3)]
        for y in range(sy, sy + sh):
            for x in range(sx, sx + sw):
                if 1 <= x < TILE - 1 and 1 <= y < TILE - 1:
                    col = c
                    if y == sy or x == sx:
                        col = COBB_HI
                    if y == sy + sh - 1 or x == sx + sw - 1:
                        col = COBB_DK
                    put(im, x, y, col)
    speckle(im, "cobble2", 4, [COBB_DK])
    return im


def stone_tile():
    """Da nen trang tri (san rocky): xi mang cham + ven toi."""
    im = new(TILE, TILE, COBB)
    speckle(im, "stone", 16, [COBB_DK, COBB_HI])
    rng = Rng(seed_of("stone"))
    for _ in range(3):
        x, y = rng.next(13), rng.next(13)
        put(im, x, y, COBB_DK), put(im, x + 1, y + 1, COBB_DK)
    shade_rows(im, 8, 14)
    return im


def water_tile():
    im = new(TILE, TILE, WATER)
    px = im.load()
    for y in range(TILE):                    # dan toi phia day
        if y >= 12:
            for x in range(TILE):
                px[x, y] = (*WATER_DK, 255)
    for (wx, wy) in ((1, 4), (8, 9)):        # 2 net song mem
        for i in range(6):
            put(im, wx + i, wy + (1 if i in (2, 3) else 0), WATER_HI)
    put(im, 12, 2, FOAM), put(im, 13, 2, FOAM)
    speckle(im, "water", 5, [WATER_DK])
    return im


def sand_tile():
    im = new(TILE, TILE, SAND)
    speckle(im, "sand", 12, [SAND_DK, SAND_HI])
    for (wx, wy) in ((2, 4), (9, 10)):       # gợn sóng cát
        for i in range(5):
            put(im, wx + i, wy + (1 if i in (2, 3) else 0), SAND_DK)
    put(im, 12, 3, SAND_HI), put(im, 12, 4, SAND_HI), put(im, 13, 4, SAND_HI)
    put(im, 4, 13, SAND_HI)
    shade_rows(im, 6, 12)
    return im


def path_tile():
    im = new(TILE, TILE, PATH)
    speckle(im, "path", 14, [PATH_DK, PATH_HI])
    rng = Rng(seed_of("path"))
    for _ in range(2):                       # 2 pebble xam nho
        x, y = 2 + rng.next(10), 2 + rng.next(10)
        put(im, x, y, PEB), put(im, x + 1, y, PEB_HI)
        put(im, x, y + 1, PEB)
    for _ in range(2):                       # vet queo mau dat
        x, y = 1 + rng.next(11), 1 + rng.next(13)
        put(im, x, y, PATH_DK), put(im, x + 1, y, PATH_DK)
    shade_rows(im, 8, 16)
    return im


def bridge_tile():
    im = new(TILE, TILE, WOOD)
    px = im.load()
    for y in range(TILE):
        for x in range(TILE):
            if y % 5 == 4:
                px[x, y] = (*WOOD_DK, 255)
            elif y % 5 == 0:
                px[x, y] = (*WOOD_HI, 255)
    for x in (0, 15):                        # lan can 2 ben
        for y in range(TILE):
            px[x, y] = (*WOOD_DK, 255) if y % 2 else (*TRUNK_DK, 255)
    for (nx, ny) in ((3, 2), (12, 7), (4, 12)):
        put(im, nx, ny, (208, 208, 216))
    return im


def floor_tile():
    """San hang da: 4 tam slate + mortar + vet nut (ref grotto)."""
    im = new(TILE, TILE, CAVE_F)
    px = im.load()
    for y in range(TILE):
        for x in range(TILE):
            if x == 8 or y == 8:
                px[x, y] = (*CAVE_F_DK, 255)
            elif (x < 8 and y < 8) or (x >= 8 and y >= 8):
                px[x, y] = (*CAVE_F, 255)
            else:
                px[x, y] = (*(98, 92, 112), 255)
    for x in range(TILE):                    # sang dinh moi tam
        px[x, 0] = (*CAVE_F_HI, 255)
        px[x, 8] = (*CAVE_F_HI, 255)
    speckle(im, "floor", 8, [CAVE_F_DK])
    for (cx, cy) in ((3, 10), (4, 11), (5, 11), (11, 3), (12, 4), (12, 5)):
        put(im, cx, cy, CAVE_F_DK)
    return im


def wall_tile():
    """Tuong gach hang da: vien sang dinh, gach so le, mortar toi."""
    im = new(TILE, TILE, BRICK)
    px = im.load()
    for y in range(TILE):
        row = y // 4
        seam = (y % 4) == 3
        off = (row % 2) * 4
        for x in range(TILE):
            vcol = ((x + off) % 8) == 7
            if seam or vcol:
                px[x, y] = (*BRICK_DK, 255)
            elif (y % 4) == 0:
                px[x, y] = (*BRICK_HI, 255)
    speckle(im, "wall", 5, [BRICK_DK], y0=1, y1=14)
    return im


def door_tile():
    im = wall_tile()
    px = im.load()
    for y in range(1, TILE):
        for x in range(2, 14):
            frame = y == 1 or x in (2, 13)
            arch = y == 2 and (x < 4 or x > 11)
            if frame or arch:
                px[x, y] = (*TRUNK_DK, 255)
            else:
                c = WOOD if (x % 4) < 2 else WOOD_DK
                if y == 3:
                    c = WOOD_HI
                px[x, y] = (*c, 255)
    for y in (6, 11):                        # thanh go ngang
        for x in range(4, 12):
            px[x, y] = (*TRUNK_DK, 255)
    put(im, 10, 8, GOLD), put(im, 10, 9, (200, 160, 40))
    return im


def tilled_tile():
    """Ranh cat NGANG (long furrow): ridge sang / mat cat / rãnh toi."""
    im = new(TILE, TILE, DIRT)
    px = im.load()
    for y in range(TILE):
        band = y % 4
        for x in range(TILE):
            if band == 0:
                px[x, y] = (*DIRT_HI, 255)
            elif band == 2:
                px[x, y] = (*DIRT_DK, 255)
            else:
                px[x, y] = (*DIRT, 255)
    rng = Rng(seed_of("tilled"))
    for _ in range(5):                       # con dat ron ridge
        x, y = rng.next(14), (1 + rng.next(3)) * 4 % 16
        put(im, x, y, DIRT_DK)
    return im


def watered_tile():
    im = tilled_tile()
    px = im.load()
    for y in range(TILE):
        for x in range(TILE):
            r, g, b, a = px[x, y]
            px[x, y] = (int(r * 0.70), int(g * 0.70), int(b * 0.80 + 18), a)
    speckle(im, "watered", 6, [(70, 96, 128)])
    return im


def blades_tile():
    """Overlay luoi co lay theo gio (transparent)."""
    im = new(TILE, TILE)
    for bx, hgt, c1, c2 in ((3, 7, TUFT_MID, TUFT_HI), (8, 9, LEAF, TUFT_MID),
                            (13, 6, TUFT_MID, TUFT_HI)):
        for i in range(hgt):
            put(im, bx, 15 - i, c1 if i < hgt - 2 else c2)
        put(im, bx - 1, 15 - hgt + 1, c2)
    return im


# ---------------------------------------------------------------- deco
def tree_sprite():
    """Cay tron nhieu lop kieu ref 3/4: tán scallop, sáng tren trai, rim toi."""
    im = new(24, 32)
    for y in range(21, 32):                  # than
        c = TRUNK if 10 <= y - 21 or y < 29 else TRUNK_DK
        put(im, 11, y, TRUNK), put(im, 12, y, TRUNK)
        put(im, 10, y, TRUNK_DK), put(im, 13, y, TRUNK_DK)
    for x in range(8, 17):                   # re/cat duoi than
        put(im, x, 31, DIRT_DK)
    disc(im, 12, 11, 9, LEAF, sq=1)
    disc(im, 7, 14, 6, LEAF)
    disc(im, 17, 14, 6, LEAF)
    disc(im, 12, 15, 8, LEAF)
    px = im.load()
    for y in range(32):                      # rim toi + shadow duoi tan
        for x in range(24):
            r, g, b, a = px[x, y]
            if a and y >= 4:
                if y > 17 and px[x, min(31, y + 1)][3] and y >= 18:
                    pass
    for cx, cy, r in ((12, 11, 9), (7, 14, 6), (17, 14, 6), (12, 15, 8)):
        for y in range(cy - r, cy + r + 1):
            for x in range(cx - r, cx + r + 1):
                if (x - cx) ** 2 + (y - cy) ** 2 <= r * r and 0 <= x < 24 and 0 <= y < 32:
                    if px[x, y][3]:
                        if (x - cx) * 2 + (y - cy) * 3 > r:
                            put(im, x, y, LEAF_DK)
                        elif (x - cx) + (y - cy) < -r // 2:
                            put(im, x, y, LEAF_HI)
    speckle(im, "tree", 22, [LEAF_DK], x0=4, y0=4, x1=19, y1=20)
    speckle(im, "treehi", 12, [LEAF_HI], x0=5, y0=3, x1=13, y1=12)
    # scallop mep duoi tan: chom co rua xuong (ref 2 overhang)
    for bx in (3, 6, 9, 12, 15, 18, 21):
        h = 2 + (bx % 3)
        for i in range(h):
            put(im, bx, 20 + i, LEAF_DK if i == h - 1 else LEAF)
    outline(im, (26, 56, 28))
    return im


def tuft_sprite():
    im = new(14, 9)
    for bx, hgt in ((2, 5), (5, 7), (7, 4), (9, 8), (12, 5)):
        for i in range(hgt):
            put(im, bx, 8 - i, TUFT_MID if i < hgt - 2 else TUFT_HI)
        put(im, bx - 1, 8 - hgt + 1, TUFT_HI)
    return im


def rock_sprite():
    im = new(12, 9)
    disc(im, 5, 5, 4, COBB)
    disc(im, 8, 6, 3, COBB)
    px = im.load()
    for y in range(9):
        for x in range(12):
            if px[x, y][3]:
                if y >= 6:
                    put(im, x, y, COBB_DK)
                elif x + y < 6:
                    put(im, x, y, COBB_HI)
    put(im, 4, 3, COBB_HI), put(im, 5, 3, COBB_HI)
    outline(im, (60, 58, 68))
    return im


def mush_sprite():
    im = new(12, 11)
    for y in range(2, 6):
        for x in range(2, 10):
            if (x - 5) ** 2 + (y - 6) ** 2 * 2 <= 18:
                put(im, x, y, (214, 74, 70))
    for x in range(3, 9):
        put(im, x, 2, (238, 118, 106))
    for (dx, dy) in ((4, 3), (7, 4), (5, 5)):
        put(im, dx, dy, TRIM)
    for y in range(6, 11):
        put(im, 5, y, (236, 226, 200))
        put(im, 6, y, (210, 198, 172))
    outline(im, (70, 34, 34))
    return im


def flower_sprite(tag, petal, center):
    im = new(16, 16)
    for i in range(6):                       # than + la
        put(im, 8, 15 - i, LEAF_DK if i < 2 else LEAF)
    put(im, 6, 12, LEAF_HI), put(im, 7, 12, LEAF)
    put(im, 10, 10, LEAF_HI), put(im, 9, 10, LEAF)
    cx, cy = 8, 6
    for dx, dy in ((0, -2), (2, -1), (2, 1), (0, 2), (-2, 1), (-2, -1)):
        disc(im, cx + dx, cy + dy, 1, petal)
    disc(im, cx, cy, 1, center)
    put(im, cx - 1, cy - 1, TRIM)
    outline(im, (40, 60, 36))
    return im


def berry_sprite(tag, berry_c, berry_hi):
    im = new(12, 12)
    disc(im, 5, 6, 4, LEAF_DK)
    disc(im, 8, 7, 3, LEAF_DK)
    disc(im, 4, 4, 3, LEAF)
    speckle(im, "berry" + tag, 6, [LEAF_HI])
    for (bx, by) in ((3, 6), (7, 5), (6, 9), (9, 8)):
        disc(im, bx, by, 1, berry_c)
        put(im, bx, by - 1, berry_hi)
    outline(im, (26, 56, 28))
    return im


# ---------------------------------------------------------------- crops
def crop_frames(kind):
    stem, leaf = (74, 148, 62), (104, 184, 84)
    fruit, f_hi = {
        0: ((226, 224, 240), (248, 248, 252)),      # turnip
        1: ((196, 150, 96), (222, 180, 124)),       # potato
        2: ((224, 74, 60), (250, 150, 130)),        # tomato
        3: ((236, 142, 44), (252, 190, 96)),        # pumpkin
    }[kind]
    frames = []
    for st in range(4):
        im = new(16, 16)
        if st == 0:
            for i in range(4):
                put(im, 8, 15 - i, stem)
            put(im, 6, 11, leaf), put(im, 7, 11, leaf), put(im, 10, 11, leaf), put(im, 9, 11, leaf)
            put(im, 7, 10, leaf), put(im, 10, 10, leaf)
        elif st == 1:
            for i in range(7):
                put(im, 8, 15 - i, stem)
            for (lx, ly) in ((5, 9), (11, 9), (4, 11), (12, 11)):
                disc(im, lx, ly, 1, leaf)
            speckle(im, f"crop{kind}1", 4, [LEAF_HI])
        elif st == 2:
            for i in range(9):
                put(im, 8, 15 - i, stem)
            for (lx, ly, r) in ((5, 7, 2), (11, 7, 2), (7, 11, 2), (10, 11, 2)):
                disc(im, lx, ly, r, leaf)
            speckle(im, f"crop{kind}2", 6, [LEAF_HI])
            if kind != 3:
                disc(im, 8, 5, 1, f_hi)
        else:
            if kind == 3:                    # bi ngo: qua lon nam dat
                for y in range(8, 16):
                    for x in range(2, 14):
                        if (x - 8) ** 2 * 2 + (y - 12) ** 2 * 3 <= 42:
                            c = fruit
                            if x in (5, 8, 11):
                                c = (210, 120, 32)
                            if y == 8:
                                c = f_hi
                            put(im, x, y, c)
                put(im, 8, 7, stem), put(im, 9, 6, stem), put(im, 7, 6, leaf)
                disc(im, 4, 14, 2, leaf), disc(im, 13, 13, 1, leaf)
            elif kind == 1:                  # khoai: dau dat + cay
                disc(im, 8, 12, 3, leaf)
                speckle(im, f"crop{kind}3a", 5, [LEAF_HI])
                for (bx, by) in ((5, 14), (9, 14), (7, 13)):
                    disc(im, bx, by, 1, fruit)
                    put(im, bx, by - 1, f_hi)
                for i in range(6):
                    put(im, 8, 9 - i, stem)
                disc(im, 6, 5, 1, TRIM), disc(im, 10, 4, 1, TRIM)
            else:                            # turnip/tomato: dau cu + la
                for i in range(8):
                    put(im, 8, 15 - i - 6, stem)
                for (lx, ly, r) in ((5, 4, 2), (11, 4, 2), (8, 3, 2)):
                    disc(im, lx, ly, r, leaf)
                speckle(im, f"crop{kind}3b", 5, [LEAF_HI])
                disc(im, 8, 10, 3, fruit)
                put(im, 6, 9, f_hi), put(im, 7, 8, f_hi)
                if kind == 0:
                    disc(im, 8, 13, 2, fruit)
        outline(im, (30, 52, 28))
        frames.append(im)
    return frames


# ---------------------------------------------------------------- items
def potion_sprite():
    im = new(12, 12)
    for y in range(4, 12):
        for x in range(2, 10):
            if (x - 5) ** 2 + (y - 8) ** 2 * 2 <= 17:
                put(im, x, y, (226, 62, 84))
    for y in range(7, 11):
        for x in range(3, 9):
            if (x - 5) ** 2 + (y - 8) ** 2 * 2 <= 12:
                put(im, x, y, (244, 108, 120))
    for y in range(0, 4):
        put(im, 5, y, (196, 196, 206)), put(im, 6, y, (160, 160, 172))
    put(im, 4, 0, (176, 128, 74)), put(im, 7, 0, (176, 128, 74))
    put(im, 3, 7, TRIM), put(im, 3, 8, TRIM)
    outline(im, (64, 30, 40))
    return im


def sword_sprite():
    im = new(12, 12)
    for i in range(8):
        put(im, 10 - i, 1 + i, (214, 224, 242))
        put(im, 11 - i, 1 + i, (160, 172, 196))
    put(im, 3, 8, (255, 214, 96)), put(im, 4, 9, (255, 214, 96))
    put(im, 4, 7, (255, 214, 96)), put(im, 5, 8, (222, 178, 60))
    for i in range(3):
        put(im, 2 - i, 10 + i, WOOD_DK) if i else put(im, 2, 10, WOOD)
        put(im, 1, 11, WOOD_DK)
    outline(im, (44, 44, 56))
    return im


def coin_sprite():
    im = new(12, 12)
    disc(im, 5, 5, 5, (214, 160, 40))
    disc(im, 5, 5, 4, GOLD)
    disc(im, 4, 4, 2, GOLD_HI)
    put(im, 7, 8, (184, 130, 30)), put(im, 8, 7, (184, 130, 30))
    outline(im, (122, 84, 18))
    return im


# ---------------------------------------------------------------- polish
def polish(im: Image.Image) -> Image.Image:
    """Viên outline + shading tren-trai sang / duoi-phai toi cho sprite R."""
    im = im.convert("RGBA").copy()
    w, h = im.size
    px = im.load()
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if a < 128:
                continue
            d = ((x / max(1, w - 1)) + (y / max(1, h - 1))) / 2
            f = 1.14 - 0.26 * d
            px[x, y] = (*safe((int(r * f), int(g * f), int(b * f))), 255)
    return outline(im)


def char_stills():
    """Van dung khung R (khop voi animation .vpa) + polish."""
    import build_rhynn_assets as R
    out = {}
    CLASS_SD = (
        ((196, 60, 60), (150, 40, 40), (150, 150, 160)),
        ((90, 90, 220), (60, 60, 170), (40, 40, 90)),
        ((70, 170, 100), (46, 128, 70), (50, 60, 50)),
    )
    HAIR_SD = ((90, 60, 34), (40, 36, 44), (140, 110, 60))
    for idx, (cloth, cdk, hat) in enumerate(CLASS_SD):
        hair = HAIR_SD[idx]
        for dirn, tag in ((0, "d"), (1, "u"), (2, "s")):
            for step in (0, 1):
                out[f"sd_c{idx}_{tag}{step}"] = polish(R.sd_player(cloth, cdk, hat, hair, dirn, step))
        for step in (0, 1):
            nm = f"p_class{idx}" if step == 0 else f"p_class{idx}_1"
            out[nm] = polish(R.player_frame(cloth, cdk, hat, step))
    for nm, fn in (("slime", R.slime_frame), ("skel", R.skel_frame),
                   ("fslime", R.fslime_frame), ("golem", R.golem_frame)):
        for step in (0, 1):
            key = f"m_{nm}" if step == 0 else f"m_{nm}_1"
            out[key] = polish(fn(step))
    for step in (0, 1):
        out[f"m_bat{'_1' if step else ''}"] = polish(R.bat_frame(step))
    out["npc_shop"] = polish(npc_shop_sprite())
    out["npc_grandma"] = polish(npc_grandma_sprite())
    return out


def npc_shop_sprite():
    im = new(16, 24)
    for y in range(1, 7):
        for x in range(4, 12):
            put(im, x, y, (242, 202, 162))
    for x in range(3, 13):
        put(im, x, 0, (96, 64, 32)), put(im, x, 1, (124, 86, 46))
    for x in range(2, 14):
        put(im, x, 2, (124, 86, 46))
    put(im, 6, 4, (34, 30, 36)), put(im, 9, 4, (34, 30, 36))
    for y in range(7, 18):
        for x in range(3, 13):
            put(im, x, y, (74, 114, 184))
    for y in range(10, 15):
        for x in range(6, 10):
            put(im, x, y, (232, 232, 238))
    for y in range(18, 24):
        for x in (5, 6, 9, 10):
            put(im, x, y, (64, 54, 46))
    return im


def npc_grandma_sprite():
    im = new(16, 24)
    for y in range(2, 8):
        for x in range(4, 12):
            put(im, x, y, (152, 102, 56))
    for y in range(4, 20):
        put(im, 3, y, (152, 102, 56)), put(im, 12, y, (128, 84, 46))
    for y in range(4, 8):
        for x in range(5, 11):
            put(im, x, y, (242, 205, 168))
    put(im, 6, 6, (34, 30, 36)), put(im, 9, 6, (34, 30, 36))
    put(im, 5, 7, (255, 190, 195)), put(im, 10, 7, (255, 190, 195))
    for y in range(8, 19):
        for x in range(4 + (18 - y) // 8, 12 - (18 - y) // 8):
            put(im, x, y, (242, 202, 84))
    put(im, 7, 12, (255, 236, 170)), put(im, 8, 14, (255, 236, 170))
    for y in range(19, 24):
        put(im, 6, y, (242, 205, 168)), put(im, 9, y, (242, 205, 168))
    return im


# ---------------------------------------------------------------- farm
def house_sprite(warm: bool):
    im = new(32, 32)
    wall, wall_dk = (HOUSE_WOOD, HOUSE_WOOD_DK) if warm else (HOUSE_TEAL, HOUSE_TEAL_DK)
    for y in range(15, 30):                  # tuong van gach doc
        for x in range(4, 28):
            put(im, x, y, wall if (x % 4) != 3 else wall_dk)
    for y in range(27, 30):                  # chan da
        for x in range(4, 28):
            put(im, x, y, COBB if (x + y) % 3 else COBB_DK)
    for y in range(5, 15):                   # mai doc gan kin tuong
        x0 = 10 - (y - 5)                    # 10 -> 0
        x1 = 21 + (y - 5)
        for x in range(x0, x1 + 1):
            put(im, x, y, ROOF_GRAY if (y % 2) else (140, 138, 152))
        put(im, x0, y, ROOF_GRAY_DK), put(im, x1, y, ROOF_GRAY_DK)
    for x in range(0, 31):                   # mi cheo toi + dong gach mai
        put(im, x, 15, TRUNK_DK)
    for x in range(15, 17):
        for y in range(5, 15):
            put(im, x, y, ROOF_GRAY_DK)      # ridge
    for y in range(20, 30):                  # cua
        for x in range(13, 19):
            edge = y == 20 or x in (13, 18)
            put(im, x, y, TRIM if edge else (WOOD if x % 4 < 2 else WOOD_DK))
    put(im, 17, 25, GOLD)
    for (wx, wy) in ((6, 17), (22, 17)):     # cua so xanh troi
        for y in range(wy, wy + 5):
            for x in range(wx, wx + 4):
                put(im, x, y, (150, 200, 232) if (x + y) % 2 else (190, 226, 246))
        for x in range(wx - 1, wx + 5):      # khung go
            put(im, x, wy - 1, TRUNK_DK), put(im, x, wy + 5, TRUNK_DK)
        for y in range(wy - 1, wy + 6):
            put(im, wx - 1, y, TRUNK_DK), put(im, wx + 4, y, TRUNK_DK)
    outline(im)
    return im


def barn_sprite():
    im = new(48, 32)
    for y in range(13, 30):                  # tuong do
        for x in range(3, 45):
            c = BARN_RED if (y % 5) != 4 else BARN_RED_DK
            if x in (3, 44):
                c = TRIM                     # goi corner trang
            put(im, x, y, c)
    for y in range(2, 13):                   # mai gambrel 2 doc
        t = y - 2
        if t < 6:
            x0, x1 = 14 - t * 2, 33 + t * 2
        else:
            x0, x1 = 2 - (t - 5), 45 + (t - 5)
            x0, x1 = max(x0, 2), min(x1, 45)
        for x in range(x0, x1 + 1):
            put(im, x, y, ROOF_GRAY if (y % 2) else (140, 138, 152))
        put(im, x0, y, ROOF_GRAY_DK), put(im, x1, y, ROOF_GRAY_DK)
    for x in range(2, 46):                   # mi cheo
        put(im, x, 13, TRUNK_DK)
    for y in range(18, 30):                  # cua lon vien trang
        for x in range(17, 31):
            if y == 18 or x in (17, 30):
                put(im, x, y, TRIM)
            else:
                put(im, x, y, WOOD_DK if (x + y) % 6 < 3 else WOOD)
    for x in range(18, 30):                  # cheo X
        put(im, x, 19 + (x - 18) * 10 // 12, (150, 106, 62))
        put(im, x, 29 - (x - 18) * 10 // 12, (150, 106, 62))
    for y in range(6, 12):                   # loft cat rom
        for x in range(21, 27):
            put(im, x, y, TRIM if (y == 6 or x in (21, 26)) else (52, 40, 30))
    for x in range(3, 45):
        put(im, x, 30, TRIM)                 # ran chan trang
    outline(im)
    return im


def mill_sprite():
    im = new(20, 36)
    for y in range(10, 34):                  # than nhat dan deu
        inset = 3 - (33 - y) * 3 // 24       # 3 dinh -> 0 day
        x0, x1 = 6 + inset, 13 - inset
        for x in range(x0, x1 + 1):
            c = MILL_BRICK if ((x + y) % 4) else MILL_BRICK_DK
            if x == x0:
                c = MILL_BRICK_DK
            put(im, x, y, c)
    for y in range(1, 10):                   # mai non tron
        w = 1 + (y - 1) * 6 // 9
        for x in range(10 - w, 10 + w + 1):
            put(im, x, y, ROOF_GRAY_DK if y % 3 == 2 else (112, 102, 122))
    put(im, 10, 0, (80, 72, 90))
    for y in range(24, 32):                  # cua vung moc
        for x in range(8, 12):
            edge = y == 24 or x in (8, 11)
            put(im, x, y, TRUNK_DK if edge else WOOD)
    speckle(im, "mill", 8, [MILL_BRICK_DK], y0=11, y1=33)
    outline(im)
    return im


def blades_sprite(rot: bool):
    import math
    im = new(24, 24)
    d = ImageDraw.Draw(im)
    for k in range(4):
        a = (45 if rot else 0) + k * 90
        x2 = 12 + int(10 * math.cos(math.radians(a)))
        y2 = 12 + int(10 * math.sin(math.radians(a)))
        d.line([(12, 12), (x2, y2)], fill=(*SAIL, 255), width=3)
        p3 = (int(10 * math.cos(math.radians(a + 14))),
              int(10 * math.sin(math.radians(a + 14))))
        d.line([(12, 12), (12 + p3[0], 12 + p3[1])], fill=(206, 198, 176, 255), width=1)
    disc(im, 12, 12, 2, TRUNK_DK)
    put(im, 12, 12, TRUNK)
    outline(im, (60, 52, 44))
    return im


def hay_sprite():
    im = new(16, 16)
    disc(im, 7, 9, 6, HAY)
    disc(im, 7, 9, 4, (236, 206, 132))
    px = im.load()
    for y in range(16):                      # strand nam doc theo bun
        if y % 3 == 1:
            for x in range(16):
                if px[x, y][3]:
                    put(im, x, y, HAY_DK)
    for x in range(16):                      # 2 day cat giua bun
        if px[x, 6][3]:
            put(im, x, 6, (158, 122, 62))
        if px[x, 12][3]:
            put(im, x, 12, (158, 122, 62))
    outline(im, (140, 104, 48))
    return im


def fence_sprite():
    im = new(16, 16)
    for x in range(16):                      # 2 thanh ngang sang
        put(im, x, 6, WOOD_HI), put(im, x, 7, WOOD)
        put(im, x, 10, WOOD_HI), put(im, x, 11, WOOD)
    for px_ in (2, 12):                      # cot go toi hon
        for y in range(3, 15):
            put(im, px_, y, WOOD)
            put(im, px_ + 1, y, WOOD_DK)
        put(im, px_, 2, WOOD_HI)
    outline(im, (60, 44, 26))
    return im


# ---------------------------------------------------------------- menu bg
def menu_bg_scene():
    """Thung lung nong trai kieu ref 3/4: troi binh minh, doi co kiem tra,
    duong mon uon, ho lua sung, nha/ho/rom + coi xay quat quay."""
    W, H = 240, 320
    im = new(W, H)
    # --- troi + mat troi + may (ken nhau, khong de lo hong)
    for y in range(104):
        k = y / 104
        c = (int(122 + 108 * k), int(172 + 66 * k), int(230 - 44 * k))
        for x in range(W):
            put(im, x, y, c)
    rng = Rng(seed_of("menubg"))
    disc(im, 182, 34, 13, (252, 228, 150))
    disc(im, 182, 34, 10, (250, 240, 196))
    for (cx, cy) in ((52, 26), (120, 44), (206, 62)):
        for (ox, oy, r) in ((0, 0, 7), (8, -2, 6), (15, 1, 5), (-7, 2, 5)):
            disc(im, cx + ox, cy + oy, r, (246, 244, 238))
        for x in range(cx - 10, cx + 20):
            put(im, x, cy + 6, (224, 228, 226))
    # --- chim xa
    for (bx, by) in ((84, 58), (96, 64), (150, 30)):
        put(im, bx, by, (70, 80, 96)), put(im, bx + 1, by - 1, (70, 80, 96))
        put(im, bx + 2, by, (70, 80, 96))
    # --- day nui xa sau doi
    for x in range(W):
        h = 88 - int(16 * abs(((x + 30) % 90) - 45) / 45)
        for y in range(h, 104):
            put(im, x, y, (96, 130, 142) if y < h + 5 else (84, 118, 130))
    # --- doi co kiem tra tu y=96 (de mai nui) xuong het man
    for ty in range(6, 20):
        for tx in range(15):
            im.alpha_composite(grass_tile((tx + ty) & 1), (tx * 16, 96 + (ty - 6) * 16))
    # --- duong mon uon chu S (ghep o 16px theo tam)
    for ty in range(112, 320, 16):
        t = (ty - 112) / 208
        cx = int(120 - 74 * t + 120 * t * t)
        im.alpha_composite(path_tile(), (cx - 8, ty))
        im.alpha_composite(path_tile(), (cx + 8, ty))
    # --- ho nuoc goc phai + vien cat + lua sung
    for y in range(236, 300):
        for x in range(150, 240):
            dx, dy = (x - 208) / 44.0, (y - 268) / 30.0
            d = dx * dx + dy * dy
            if d <= 1.0:
                put(im, x, y, WATER)
            elif d <= 1.45:
                put(im, x, y, SAND)
    for (wx, wy) in ((170, 250), (196, 262), (222, 244), (184, 284), (214, 288)):
        for i in range(5):                   # net song rung roi
            put(im, wx + i, wy + (1 if i in (2, 3) else 0), WATER_HI)
    for (lx, ly) in ((188, 258), (214, 276), (228, 252)):
        disc(im, lx, ly, 3, LEAF_DK)
        disc(im, lx, ly, 2, LEAF)
        put(im, lx + 1, ly - 1, LEAF_HI)
    # --- cay + hoa + bon co + da rat rac (tranh duong + ho + farm)
    def free(x, y):
        if 104 <= y < 320 and abs(x - (120 - 74 * ((max(y, 112) - 112) / 208)
                                       + 120 * ((max(y, 112) - 112) / 208) ** 2)) < 30:
            return False
        return not (150 <= x < 240 and 232 <= y < 304) and not (0 <= x < 96 and 224 <= y < 296)
    for (tx2, ty2) in ((20, 132), (66, 176), (168, 148), (214, 190), (128, 300), (44, 306)):
        if free(tx2, ty2):
            im.alpha_composite(tree_sprite(), (tx2 - 12, ty2 - 26))
    for _ in range(30):
        x, y = rng.next(232), 108 + rng.next(200)
        if free(x, y):
            put(im, x, y, [(248, 158, 190), (250, 214, 96), (240, 140, 60)][rng.next(3)])
    for _ in range(12):
        x, y = rng.next(226), 112 + rng.next(196)
        if free(x, y):
            im.alpha_composite(tuft_sprite(), (x, y))
    # --- farmstead goc trai duoi (kich thuoc that)
    im.alpha_composite(barn_sprite(), (2, 244))
    im.alpha_composite(hay_sprite(), (52, 268))
    im.alpha_composite(hay_sprite(), (66, 272))
    im.alpha_composite(mill_sprite(), (76, 178))
    im.alpha_composite(blades_sprite(False), (74, 172))
    for x in range(0, 150, 16):
        if x > 96:
            continue
        im.alpha_composite(fence_sprite(), (x, 296))
    # --- vignette nhe giu focus giua
    pxl = im.load()
    for y in range(H):
        for x in range(W):
            d = max(abs(x - 120) / 160, abs(y - 160) / 210)
            if d > 0.9:
                r, g, bch, a = pxl[x, y]
                k = 0.84
                pxl[x, y] = (int(r * k), int(g * k), int(bch * k), a)
    return im


# ---------------------------------------------------------------- registry
def build_all():
    """name -> (folder, RGBA). folder: 'tile' hoac 'sprite'."""
    A = {}
    A["t_grass"] = ("tile", grass_tile(False))
    A["t_grass2"] = ("tile", grass_tile(True))
    A["t_dirt"] = ("tile", dirt_tile())
    A["t_stone"] = ("tile", stone_tile())
    A["t_water"] = ("tile", water_tile())
    A["t_sand"] = ("tile", sand_tile())
    A["t_path"] = ("tile", path_tile())
    A["t_bridge"] = ("tile", bridge_tile())
    A["t_floor"] = ("tile", floor_tile())
    A["t_wall"] = ("tile", wall_tile())
    A["t_door"] = ("tile", door_tile())
    A["t_tilled"] = ("tile", tilled_tile())
    A["t_watered"] = ("tile", watered_tile())
    A["t_grass_blades"] = ("tile", blades_tile())
    A["t_cobble"] = ("tile", cobble_tile())
    A["d_tree"] = ("sprite", tree_sprite())
    A["d_tuft"] = ("sprite", tuft_sprite())
    A["d_rock"] = ("sprite", rock_sprite())
    A["d_mush"] = ("sprite", mush_sprite())
    for tag, (petal, ctr) in {
        "sp": ((248, 158, 192), (255, 240, 170)),
        "su": ((250, 214, 96), (255, 250, 220)),
        "fa": ((240, 140, 60), (255, 226, 150)),
        "wi": ((222, 232, 246), (250, 250, 235)),
    }.items():
        A[f"deco_flower_{tag}"] = ("sprite", flower_sprite(tag, petal, ctr))
    for tag, (bc, bh) in {
        "sp": ((230, 90, 80), (255, 225, 170)),
        "su": ((240, 180, 70), (255, 240, 160)),
        "fa": ((190, 90, 50), (250, 190, 120)),
        "wi": ((200, 215, 240), (250, 250, 255)),
        "cave": ((235, 120, 170), (255, 220, 130)),
    }.items():
        A[f"f_berry_{tag}"] = ("sprite", berry_sprite(tag, bc, bh))
    for kind, nm in enumerate(("turnip", "potato", "tomato", "pumpkin")):
        for st, fr in enumerate(crop_frames(kind)):
            A[f"c_{nm}_{st}"] = ("sprite", fr)
    A["i_potion"] = ("sprite", potion_sprite())
    A["i_sword"] = ("sprite", sword_sprite())
    A["i_coin"] = ("sprite", coin_sprite())
    A["h_house_w"] = ("sprite", house_sprite(False))
    A["h_house_s"] = ("sprite", house_sprite(True))
    A["h_barn"] = ("sprite", barn_sprite())
    A["h_mill"] = ("sprite", mill_sprite())
    A["h_blades"] = ("sprite", blades_sprite(False))
    A["h_blades_1"] = ("sprite", blades_sprite(True))
    A["h_hay"] = ("sprite", hay_sprite())
    A["h_fence"] = ("sprite", fence_sprite())
    A["menu_bg"] = ("sprite", menu_bg_scene())
    for nm, im in char_stills().items():
        A[nm] = ("sprite", im)
    return A


def save_one(name, folder, im, want_vpe=True):
    d = ROOT / folder
    d.mkdir(parents=True, exist_ok=True)
    im.save(d / f"{name}.png")
    if want_vpe:
        w, h = im.size
        px = im.load()
        pix = []
        for y in range(h):
            for x in range(w):
                r, g, b, a = px[x, y]
                pix.append(0xFFFF if a < 128 else VPE.rgb_to_565(r, g, b))
        VPE.save_vpe(d / f"{name}.vpe", w, h, pix)


def contact_sheet(items):
    SHEET.parent.mkdir(parents=True, exist_ok=True)
    S = 4
    cw = 24 * S + 10
    cols = 14
    rows = (len(items) + cols - 1) // cols
    sheet = Image.new("RGBA", (cols * cw, rows * (32 * S + 26)), (36, 38, 52, 255))
    dd = ImageDraw.Draw(sheet)
    for i, (name, im) in enumerate(items):
        cx, cy = (i % cols) * cw, (i // cols) * (32 * S + 26)
        big = im.convert("RGBA").resize((im.width * S, im.height * S), Image.NEAREST)
        sheet.alpha_composite(big, (cx + 4, cy + 18))
        dd.text((cx + 4, cy + 4), f"{name} {im.width}x{im.height}", fill=(255, 255, 170, 255))
    sheet.convert("RGB").save(SHEET)


def mock_scene(A):
    """Ghep 15x20 o 240x320: co kiem tra + ho + cau + duong + farm + crop."""
    W, H = 240, 320
    im = new(W, H)
    g = lambda tx, ty: A["t_grass2" if (tx + ty) & 1 else "t_grass"][1]
    for ty in range(20):
        for tx in range(15):
            im.alpha_composite(g(tx, ty), (tx * 16, ty * 16))
    # ho + cat bo + nuoc
    for ty in range(2, 8):
        for tx in range(9, 15):
            dx, dy = tx - 13.5, ty - 4.5
            if dx * dx * 0.7 + dy * dy <= 8:
                im.alpha_composite(A["t_water"][1], (tx * 16, ty * 16))
            elif dx * dx * 0.7 + dy * dy <= 12:
                im.alpha_composite(A["t_sand"][1], (tx * 16, ty * 16))
    for tx in range(9, 14):
        im.alpha_composite(A["t_bridge"][1], (tx * 16, 4 * 16))
    # duong cheo + cobble
    for ty in range(8, 20):
        im.alpha_composite(A["t_path"][1], ((13 - (ty - 8) // 2) * 16, ty * 16))
    for tx in range(0, 15):
        im.alpha_composite(A["t_cobble"][1], (tx * 16, 0))
    # vuon crop 4x4 + tuoi nuoc
    for j, kind in enumerate(("turnip", "potato", "tomato", "pumpkin")):
        for i in range(4):
            tx, ty = 1 + i, 12 + (j > 1) * 0
            ty = 12 + j
            if ty > 19:
                continue
            im.alpha_composite(A["t_watered" if i % 3 else "t_tilled"][1], (tx * 16, ty * 16))
            im.alpha_composite(A[f"c_{kind}_{min(3, i)}"][1], (tx * 16, ty * 16))
    # cay/da/hoa/tuft
    for (tx, ty) in ((0, 3), (2, 6), (5, 2), (7, 9), (1, 9)):
        im.alpha_composite(A["d_tree"][1], (tx * 16 - 4, ty * 16 - 16))
    for (tx, ty) in ((4, 8), (12, 10), (6, 14)):
        im.alpha_composite(A["d_rock"][1], (tx * 16 + 2, ty * 16 + 5))
    for (tx, ty, f) in ((3, 4, "sp"), (8, 11, "su"), (11, 13, "fa"), (2, 17, "wi")):
        im.alpha_composite(A[f"deco_flower_{f}"][1], (tx * 16, ty * 16))
    for (tx, ty) in ((6, 6), (10, 9), (4, 18), (13, 15)):
        im.alpha_composite(A["d_tuft"][1], (tx * 16, ty * 16 + 6))
    # farm row + nha + player
    im.alpha_composite(A["h_barn"][1], (16, 232))
    im.alpha_composite(A["h_house_w"][1], (70, 240))
    im.alpha_composite(A["h_mill"][1], (112, 228))
    im.alpha_composite(A["h_blades"][1], (110, 216))
    im.alpha_composite(A["h_hay"][1], (148, 256))
    for x in range(16, 240, 16):
        im.alpha_composite(A["h_fence"][1], (x, 288))
    im.alpha_composite(A["sd_c0_d0"][1], (96, 176))
    im.alpha_composite(A["m_slime"][1], (150, 190))
    MOCK.parent.mkdir(parents=True, exist_ok=True)
    im.convert("RGB").save(MOCK)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    ap.add_argument("--no-sheet", action="store_true")
    ap.add_argument("--no-vpe", action="store_true")
    args = ap.parse_args()
    only = {s.strip() for s in args.only.split(",") if s.strip()}

    A = build_all()
    n = 0
    for name, (folder, im) in sorted(A.items()):
        if only and name not in only:
            continue
        save_one(name, folder, im, want_vpe=not args.no_vpe)
        n += 1
    print(f"OK {n} asset -> {ROOT}\\tile + {ROOT}\\sprite")
    if not args.no_sheet:
        sheet_items = [(k, v[1]) for k, v in sorted(A.items()) if k != "menu_bg"]
        contact_sheet(sheet_items)
        mock_scene(A)
        print(f"  sheet -> {SHEET}")
        print(f"  mock  -> {MOCK}")


if __name__ == "__main__":
    main()
