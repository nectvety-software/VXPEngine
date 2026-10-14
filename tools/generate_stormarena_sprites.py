#!/usr/bin/env python3
"""Generate StormArena25D's fighter art as baked RGB565 + 1-bit-mask parts.

Why parts and not frames: the engine blits RGB565 (optionally with a 1-bit
visibility mask), so eight full 96x176 poses per fighter would cost ~430 KB of
sprite data - far past what these handsets allow. Body parts are rasterised
once, offline, at full detail (curved silhouettes, cel shading, 1-px outline)
and the sample composites them per pose at runtime.

    python tools/generate_stormarena_sprites.py            # write header + preview
    python tools/generate_stormarena_sprites.py --preview  # preview PNG only

Preview: tmp/sprites_preview.png (both fighters, every pose, 3x).

Proportions and colours are measured off tmp/refvid/f05.png, not eyeballed: the
reference fighter is 127 px tall with a 14% head, a shoulder line 25% of his
height, the knee at 70%, and a value structure of bright hair + off-white limb
wraps over an olive vest (REN, #42493f) or a near-black suit (KURO, #0f0e10)
with navy trousers (#222433).
"""
import os
import sys

FW, FH = 96, 176          # figure canvas; soles on y=166, body centre x=40
BODY_X = 40
OUT_HEADER = "examples/StormArena25D/src/sprites_gen.h"
PREVIEW = "tmp/sprites_preview.png"

# material ids (0 = transparent). LEG_UP/LEG_LO let both fighters share one leg
# raster: REN wears baggy navy trousers to the ankle, KURO shorts to mid-thigh
# over a bare calf, and the same ids resolve to cloth and to skin.
SKIN, HAIR, CLOTH, METAL, VEST, VEST_D, LEG_UP, LEG_LO, WRAP, SANDAL, BELT, \
    GLOVE, ACCENT, EYE = range(1, 15)
# Key 0 is free (material ids start at 1) and carries the wrap stripe period.
STRIPE = 0


def c565(r, g, b):
    return ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3)


def darker(c, k):
    return tuple(max(0, int(v * k)) for v in c)


def lighter(c, k):
    return tuple(min(255, int(v * k)) for v in c)


# (base, shade, light) per material, per fighter.
def pal(skin, hair, cloth, metal, vest, leg_up, leg_lo, wrap, sandal, belt,
        glove, accent, stripe=0):
    return {
        SKIN:   (skin, darker(skin, 0.74), lighter(skin, 1.16)),
        HAIR:   (hair, darker(hair, 0.66), lighter(hair, 1.22)),
        CLOTH:  (cloth, darker(cloth, 0.68), lighter(cloth, 1.34)),
        METAL:  (metal, darker(metal, 0.66), lighter(metal, 1.24)),
        VEST:   (vest, darker(vest, 0.72), lighter(vest, 1.22)),
        VEST_D: (darker(vest, 0.58), darker(vest, 0.44), darker(vest, 0.74)),
        LEG_UP: (leg_up, darker(leg_up, 0.70), lighter(leg_up, 1.30)),
        LEG_LO: (leg_lo, darker(leg_lo, 0.70), lighter(leg_lo, 1.26)),
        WRAP:   (wrap, darker(wrap, 0.80), lighter(wrap, 1.04)),
        SANDAL: (sandal, darker(sandal, 0.68), lighter(sandal, 1.42)),
        BELT:   (belt, darker(belt, 0.68), lighter(belt, 1.24)),
        GLOVE:  (glove, darker(glove, 0.70), lighter(glove, 1.24)),
        ACCENT: (accent, darker(accent, 0.70), lighter(accent, 1.22)),
        EYE:    ((10, 10, 18), (10, 10, 18), (10, 10, 18)),
        STRIPE: stripe,
    }


class Part:
    """Material-indexed raster on the shared 96x176 figure canvas.

    flip=True mirrors the part about the body centre line, which is how the
    near-side limbs get their own bake: cel shading is resolved at authoring x,
    so a left-authored arm copied to the right stays in shadow.
    """

    def __init__(self, name, flip=False):
        self.name = name
        self.flip = flip
        self.m = [0] * (FW * FH)

    def X(self, x):
        return (BODY_X * 2 - x) if self.flip else x

    def put(self, x, y, mat):
        x, y = int(round(self.X(x))), int(round(y))
        if 0 <= x < FW and 0 <= y < FH:
            self.m[y * FW + x] = mat

    def hline(self, x0, x1, y, mat):
        if x1 < x0:
            x0, x1 = x1, x0
        for x in range(int(round(x0)), int(round(x1)) + 1):
            self.put(x, y, mat)

    def strip(self, stations, mat):
        """Fill a vertical band: stations = [(y, cx, half_width), ...]."""
        st = sorted(stations)
        for y in range(int(round(st[0][0])), int(round(st[-1][0])) + 1):
            for i in range(len(st) - 1):
                (y0, c0, w0), (y1, c1, w1) = st[i], st[i + 1]
                if y0 <= y <= y1:
                    t = 0.0 if y1 == y0 else (y - y0) / float(y1 - y0)
                    self.hline(c0 + (c1 - c0) * t - (w0 + (w1 - w0) * t),
                               c0 + (c1 - c0) * t + (w0 + (w1 - w0) * t),
                               y, mat)
                    break

    def ellipse(self, cx, cy, rx, ry, mat):
        for y in range(int(round(cy - ry)), int(round(cy + ry)) + 1):
            dy = (y - cy) / ry
            k = 1.0 - dy * dy
            if k <= 0:
                continue
            half = rx * (k ** 0.5)
            self.hline(cx - half, cx + half, y, mat)

    def circle(self, cx, cy, r, mat):
        self.ellipse(cx, cy, r, r, mat)

    def poly(self, pts, mat):
        ys = [p[1] for p in pts]
        for y in range(int(round(min(ys))), int(round(max(ys))) + 1):
            xs = []
            n = len(pts)
            for i in range(n):
                (x0, y0), (x1, y1) = pts[i], pts[(i + 1) % n]
                if y0 == y1:
                    continue
                if min(y0, y1) <= y < max(y0, y1):
                    t = (y - y0) / float(y1 - y0)
                    xs.append(x0 + (x1 - x0) * t)
            xs.sort()
            for i in range(0, len(xs) - 1, 2):
                self.hline(xs[i], xs[i + 1], y, mat)

    def rect(self, x, y, w, h, mat):
        for yy in range(int(round(y)), int(round(y + h))):
            self.hline(x, x + w - 1, yy, mat)

    def tube(self, ax, ay, aw, bx, by, bw, mat):
        """Tapered limb segment: rounded caps at both ends, linear width ramp."""
        dx, dy = bx - ax, by - ay
        ln = (dx * dx + dy * dy) ** 0.5
        if ln < 0.01:
            self.circle(ax, ay, aw, mat)
            return
        nx, ny = -dy / ln, dx / ln
        self.poly([(ax + nx * aw, ay + ny * aw), (bx + nx * bw, by + ny * bw),
                   (bx - nx * bw, by - ny * bw), (ax - nx * aw, ay - ny * aw)],
                  mat)
        self.circle(ax, ay, aw, mat)
        self.circle(bx, by, bw, mat)

    def taper(self, ax, ay, aw, tx, ty, mat):
        """Limb that comes to a soft point - hair spikes, sash tails."""
        self.tube(ax, ay, aw, tx, ty, 0.5, mat)

    def limb_band(self, limb, y0, y1, mat, inset=0.5):
        """Clip a horizontal band to a tube's axis over the y0..y1 range."""
        (ax, ay, ar), (bx, by, br) = limb

        def at(y):
            t = (y - ay) / float(by - ay)
            return (y, ax + (bx - ax) * t, ar + (br - ar) * t - inset)

        self.strip([at(y0), at(y1)], mat)

    def vline(self, x, y0, y1, mat):
        if y1 < y0:
            y0, y1 = y1, y0
        for y in range(int(round(y0)), int(round(y1)) + 1):
            self.put(x, y, mat)

    def limb_band_x(self, limb, x0, x1, mat, inset=0.5):
        """limb_band for a horizontal limb: a vertical slice over x0..x1."""
        (ax, ay, ar), (bx, by, br) = limb
        span = float(bx - ax)
        for xx in range(int(round(x0)), int(round(x1)) + 1):
            t = (xx - ax) / span
            cy, r = ay + (by - ay) * t, ar + (br - ar) * t - inset
            self.vline(xx, cy - r, cy + r, mat)


_BAKE_CACHE = {}


def bake(part, palette):
    """Resolve materials to RGB565 with a diagonal cel terminator, then add a
    material-tinted 1-px outline. Returns (x, y, w, h, pixels, mask) trimmed to
    content."""
    ck = (part.name, id(palette))
    hit = _BAKE_CACHE.get(ck)
    if hit is not None:
        return hit
    ys0 = [y for y in range(FH) for x in range(FW) if part.m[y * FW + x]]
    if not ys0:
        raise SystemExit("empty part " + part.name)
    top, bot = min(ys0), max(ys0)
    span = float(max(1, bot - top))

    px = [None] * (FW * FH)
    stripe = palette.get(STRIPE, 0)
    stripe_ink = palette[CLOTH][1]
    for y in range(FH):
        for x in range(FW):
            mat = part.m[y * FW + x]
            if not mat:
                continue
            base, shade, light = palette[mat]
            # Key light from the upper right: the terminator runs diagonally
            # across each part's own height, so a copied limb never picks up the
            # highlight just because it sits high on the canvas.
            d = (x - BODY_X) / 20.0
            v = (y - top) / span
            key = 0.62 * d + 0.42 * (0.5 - v)
            edge = x + 1 >= FW or not part.m[y * FW + x + 1]
            below = y + 1 >= FH or not part.m[(y + 1) * FW + x]
            if key > 0.34 or (edge and d > 0.05) or (v < 0.10 and d > -0.15):
                col = light
            elif key < -0.30 or (below and v > 0.70):
                col = shade
            else:
                col = base
            # Bandage wraps: KURO's are the reference's black-and-white ladder
            # pattern, REN's are solid cream. Same raster, so the period lives on
            # the palette and is carved here rather than at authoring time.
            if mat == WRAP and stripe and (y % stripe) < (stripe + 1) // 2:
                col = stripe_ink
            px[y * FW + x] = c565(*col)

    # 1-px outline pass over the silhouette. The outline colour is a darkened
    # copy of the material it touches, never a fixed near-black: parts are
    # composited at runtime and every seam between two parts would otherwise
    # stack two outline rings into a 3-px black stripe.
    ink = [1 if px[i] is not None else 0 for i in range(FW * FH)]
    src = list(px)

    def lum(v):
        return (v >> 11) + ((v >> 5) & 63) + (v & 31)

    for y in range(FH):
        for x in range(FW):
            i = y * FW + x
            if ink[i]:
                continue
            near = []
            if x:
                near.append(src[i - 1])
            if x + 1 < FW:
                near.append(src[i + 1])
            if y:
                near.append(src[i - FW])
            if y + 1 < FH:
                near.append(src[i + FW])
            near = [v for v in near if v is not None]
            if not near:
                continue
            n = max(near, key=lum)
            rgb = ((n >> 11) * 255 // 31, ((n >> 5) & 63) * 255 // 63,
                   (n & 31) * 255 // 31)
            px[i] = c565(*darker(rgb, 0.34))
            ink[i] = 2

    xs = [x for y in range(FH) for x in range(FW) if ink[y * FW + x]]
    ys = [y for y in range(FH) for x in range(FW) if ink[y * FW + x]]
    x0, y0 = max(0, min(xs) - 1), max(0, min(ys) - 1)
    x1, y1 = min(FW - 1, max(xs) + 1), min(FH - 1, max(ys) + 1)
    w, h = x1 - x0 + 1, y1 - y0 + 1
    out = []
    bits = []
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            i = y * FW + x
            if ink[i]:
                out.append(px[i] if px[i] is not None else 0)
                bits.append(1)
            else:
                out.append(0)
                bits.append(0)
    mask = bytearray((len(bits) + 7) // 8)
    for i, b in enumerate(bits):
        if b:
            mask[i >> 3] |= 0x80 >> (i & 7)
    res = (x0, y0, w, h, out, bytes(mask))
    _BAKE_CACHE[ck] = res
    return res


# ---------------------------------------------------------------- art authoring
#
# Figure space: 96x176 canvas, body centre x=40, soles on y=166. Landmarks are
# measured off tmp/refvid/f05.png (tmp/ref_ren_5x.png, tmp/ref_kuro_5x.png),
# which is the one clean frame - f02 is washed out by a hit flash and sent me
# chasing a tan vest that is really olive. In f05 REN is 127 px tall with a 14%
# head, a 25%-of-height shoulder line, the knee at 70% and the sole at 100%.
# Scaled to this canvas: hair crown y=8, chin y=31, shoulders y=42, hips y=86,
# knees y=118, soles y=166.
#
# Parts are authored for the screen-left side; the flipped copies land on the
# right hip/shoulder automatically because X(x) mirrors about BODY_X.

SH_L, SH_R = 22, 58        # shoulder joints
HIP_L, HIP_R = 32, 48      # hip joints
SH_Y, HIP_Y = 42, 86       # shoulder line, hip line
KNEE_Y, ANKLE_Y, SOLE_Y = 118, 150, 166


def head():
    p = Part("head")
    # skull: temples wider than the jaw, closing on the chin at y=31
    p.strip([(14, 40, 8.4), (20, 40, 8.8), (26, 40, 7.8), (31, 40, 5.0)], SKIN)
    # one rounded, swept-back mass - the reference hair is a beanie of spikes,
    # not a crown of separate licks, so the licks are anchored inside it
    p.ellipse(39, 14, 9.4, 8.4, HAIR)
    p.strip([(8, 39, 7.2), (14, 39, 9.4), (20, 38, 8.8)], HAIR)
    # The licks stay inside a 26-px envelope: the reference hair is narrower
    # than the shoulder line, and a wider fan reads as a spiky wig.
    for (ax, ay, aw, tx, ty) in [(34, 12, 3.2, 27, 3), (38, 10, 3.2, 35, 1),
                                 (42, 10, 3.0, 45, 3), (32, 17, 3.0, 25, 13),
                                 (31, 21, 2.8, 25, 24), (45, 14, 2.8, 51, 8),
                                 (36, 11, 2.8, 31, 4)]:
        p.taper(ax, ay, aw, tx, ty, HAIR)
    # fringe over the brow, then the band drawn on top of it
    p.strip([(15, 43, 4.6), (21, 43, 3.4)], HAIR)
    # headband low over the brow: plate at the forehead, two tails flying back
    p.strip([(17, 40, 8.6), (22, 40, 8.2)], CLOTH)
    p.rect(36, 18, 7, 4, METAL)
    p.rect(38, 19, 3, 2, CLOTH)
    p.taper(32, 19, 2.4, 20, 21, CLOTH)
    p.taper(32, 21, 2.2, 21, 27, CLOTH)
    # eyes: a narrow skin slit between band and mask, only the near one drawn
    p.strip([(23, 44, 4.0), (27, 44, 3.6)], SKIN)
    p.rect(44, 23, 2, 4, EYE)
    p.rect(41, 25, 1, 2, EYE)
    # mask over nose, mouth and throat, tapering into the collar
    p.strip([(26, 41, 6.6), (30, 41, 5.8), (34, 40, 4.6)], CLOTH)
    return p


def torso():
    p = Part("torso")
    # neck and the high collar that closes under the face mask
    p.strip([(29, 40, 5.2), (34, 40, 6.4), (39, 40, 7.0)], CLOTH)
    # undersuit: shoulder caps, chest, tapered waist
    p.strip([(37, 40, 17.0), (46, 40, 16.2), (58, 40, 14.0), (72, 40, 12.8),
             (86, 40, 13.8)], CLOTH)
    for sx in (SH_L, SH_R):
        p.ellipse(sx, 42, 8.0, 6.4, CLOTH)
    # flak vest over it, left open at the collar
    p.strip([(41, 40, 16.4), (50, 40, 15.2), (64, 40, 13.4), (78, 40, 13.0),
             (84, 40, 12.4)], VEST)
    for sx in (SH_L, SH_R):
        p.ellipse(sx, 45, 7.2, 5.6, VEST)
    p.poly([(40, 38), (36, 41), (40, 52), (44, 41)], CLOTH)    # V-neck
    p.strip([(45, 40.5, 0.9), (76, 40.5, 0.9)], VEST_D)        # centre seam
    # shoulder strap slung across the chest, as on the reference vest
    p.tube(25, 43, 2.0, 52, 66, 1.7, VEST_D)
    p.rect(47, 61, 4, 3, METAL)
    for px0 in (26, 47):                                       # pocket flaps
        p.rect(px0, 54, 11, 4, VEST_D)
        p.rect(px0, 58, 11, 7, VEST)
        p.hline(px0, px0 + 10, 65, VEST_D)
    p.strip([(78, 40, 13.4), (82, 40, 12.8)], VEST_D)          # hem shadow
    # sash at the waist with a knot tail hanging over the left hip
    p.strip([(79, 40, 13.4), (86, 40, 13.0)], ACCENT)
    p.strip([(81, 40, 13.2), (84, 40, 12.8)], BELT)
    p.taper(29, 85, 3.2, 25, 102, ACCENT)
    # trouser top, drawn in front of both hips
    p.strip([(85, 40, 13.6), (93, 40, 12.0), (99, 40, 10.2)], LEG_UP)
    return p


def _arm_back(p):
    """Screen-left arm: elbow soft, fist held low in front of the hip."""
    up = ((SH_L - 1, 44, 6.2), (18, 63, 5.4))
    lo = ((18, 63, 5.4), (22, 80, 4.6))
    p.tube(*up[0], *up[1], CLOTH)
    p.tube(*lo[0], *lo[1], CLOTH)
    p.limb_band(up, 47, 53, ACCENT)                  # armband
    p.limb_band(lo, 67, 77, WRAP)                    # forearm bandage
    p.ellipse(23, 83, 4.4, 4.8, GLOVE)
    for k in range(3):
        p.hline(20, 26, 81 + k * 2, CLOTH)           # knuckle seams


def arm_back():
    p = Part("arm_back")
    _arm_back(p)
    return p


def arm_guard():
    """Front arm: elbow dropped, fist raised in front of the chest."""
    p = Part("arm_guard")
    up = ((SH_R + 1, 44, 6.4), (66, 59, 5.6))
    lo = ((66, 59, 5.6), (57, 48, 4.8))
    p.tube(*up[0], *up[1], CLOTH)
    p.tube(*lo[0], *lo[1], CLOTH)
    p.limb_band(up, 46, 52, ACCENT)
    p.limb_band(lo, 50, 57, WRAP)
    p.ellipse(54, 45, 5.0, 4.8, GLOVE)
    p.hline(50, 57, 41, GLOVE)
    return p


def arm_punch():
    """Front arm driven straight out to the screen-right, closed fist leading."""
    p = Part("arm_punch")
    arm = ((SH_R - 6, 45, 6.4), (70, 43, 5.0))
    p.tube(*arm[0], *arm[1], CLOTH)
    p.limb_band_x(arm, 48, 53, ACCENT)
    p.limb_band_x(arm, 59, 66, WRAP)
    p.tube(71, 43, 3.8, 76, 43, 3.4, CLOTH)          # cuff
    p.ellipse(81, 43, 4.6, 5.0, GLOVE)               # fist, half the head wide
    for k in range(3):
        p.hline(79, 85, 40 + k * 3, CLOTH)           # finger seams
    return p


def arm_up():
    """Front arm thrown up and back - the recoil pose."""
    p = Part("arm_up")
    up = ((SH_R, 44, 6.4), (67, 31, 5.6))
    lo = ((67, 31, 5.6), (71, 16, 4.6))
    p.tube(*up[0], *up[1], CLOTH)
    p.tube(*lo[0], *lo[1], CLOTH)
    p.limb_band(up, 46, 51, ACCENT)
    p.limb_band(lo, 19, 28, WRAP)
    p.ellipse(72, 11, 5.0, 5.4, GLOVE)
    p.hline(68, 77, 7, GLOVE)
    return p


def _foot(p, ax):
    """Ninja sandal: thin sole plank, instep strap, a knuckle of bare toes."""
    p.poly([(ax - 5, ANKLE_Y + 3), (ax + 5, ANKLE_Y + 4),
            (ax + 6, SOLE_Y - 4), (ax - 6, SOLE_Y - 3)], SANDAL)
    p.poly([(ax - 6, SOLE_Y - 3), (ax + 9, SOLE_Y - 4),
            (ax + 10, SOLE_Y), (ax - 7, SOLE_Y)], SANDAL)
    p.ellipse(ax + 7, SOLE_Y - 5, 2.4, 1.8, SKIN)
    p.tube(ax - 2, ANKLE_Y + 6, 1.3, ax + 4, SOLE_Y - 6, 1.1, CLOTH)


def _stance_leg(p):
    """Screen-left stance leg. The thigh is LEG_UP (REN's trouser top, KURO's
    shorts), everything below it LEG_LO (his trousers, KURO's bare skin), which
    is what lets one raster carry both silhouettes."""
    thigh = ((HIP_L, HIP_Y, 9.2), (30, 104, 7.4))
    knee = ((30, 104, 7.4), (26, KNEE_Y, 6.8))
    shin = ((26, KNEE_Y, 6.2), (21, ANKLE_Y, 4.2))
    p.tube(*thigh[0], *thigh[1], LEG_UP)
    p.tube(*knee[0], *knee[1], LEG_LO)
    p.tube(*shin[0], *shin[1], LEG_LO)
    p.limb_band(thigh, 92, 96, WRAP, 0.6)
    p.limb_band(thigh, 101, 105, WRAP, 0.6)
    p.limb_band(shin, 127, 145, WRAP, 0.4)
    p.strip([(114, 27, 6.8), (121, 26, 6.4)], LEG_LO)     # knee gather
    _foot(p, 21)


def leg_stance():
    p = Part("leg_stance")
    _stance_leg(p)
    return p


def leg_stance_r():
    p = Part("leg_stance_r", flip=True)
    _stance_leg(p)
    return p


def leg_kick():
    """Front leg thrown out sideways: thigh raised to the hip line, sole leads."""
    p = Part("leg_kick")
    th = ((HIP_R - 2, HIP_Y - 2, 9.4), (58, HIP_Y - 10, 7.2))
    sh = ((58, HIP_Y - 10, 6.6), (80, HIP_Y - 5, 4.6))
    p.tube(*th[0], *th[1], LEG_UP)
    p.tube(*sh[0], *sh[1], LEG_LO)
    p.limb_band_x(th, 42, 48, WRAP, 0.6)
    p.limb_band_x(sh, 64, 74, WRAP, 0.4)
    p.poly([(80, HIP_Y - 9), (92, HIP_Y - 7), (91, HIP_Y + 2),
            (79, HIP_Y)], SANDAL)
    p.ellipse(90, HIP_Y - 5, 2.2, 1.8, SKIN)
    p.tube(81, HIP_Y - 8, 1.2, 88, HIP_Y - 6, 1.0, CLOTH)
    return p


def leg_tuck():
    """Jump: the near knee drives up, the far leg trails back and down."""
    p = Part("leg_tuck")
    th = ((HIP_L, HIP_Y, 8.8), (24, 104, 6.6))
    sh = ((24, 104, 6.0), (30, 128, 4.0))
    p.tube(*th[0], *th[1], LEG_UP)
    p.tube(*sh[0], *sh[1], LEG_LO)
    p.limb_band(sh, 114, 126, WRAP, 0.4)
    p.poly([(26, 129), (40, 126), (42, 134), (28, 137)], SANDAL)
    p.ellipse(38, 129, 2.2, 1.8, SKIN)
    kt = ((HIP_R, HIP_Y, 9.4), (58, 90, 7.2))
    ks = ((58, 90, 6.6), (46, 102, 4.8))
    p.tube(*kt[0], *kt[1], LEG_UP)
    p.tube(*ks[0], *ks[1], LEG_LO)
    p.limb_band(ks, 94, 101, WRAP, 0.4)
    p.poly([(38, 102), (52, 99), (54, 108), (40, 111)], SANDAL)
    p.ellipse(41, 105, 1.8, 2.4, SKIN)
    return p


PARTS = [head, torso, arm_back, arm_guard, arm_punch, arm_up,
         leg_stance, leg_stance_r, leg_kick, leg_tuck]

# pose = list of (part index, dx, dy) in back-to-front order
# ids: 0 head, 1 torso, 2 arm_back, 3 arm_guard, 4 arm_punch, 5 arm_up,
#      6 leg_stance, 7 leg_stance_r, 8 leg_kick, 9 leg_tuck
# The figure faces screen-right, so the left-authored limb is the far one and
# goes down first; the flipped copy is the near limb and covers it. The flipped
# leg already lands on the right hip, so dx only opens the stride and leans the
# figure. Head and torso move together - a head offset more than ~2 px past the
# torso tears the neck.
POSE_TABLE = {
    "idle0": [(6, 0, 0), (7, 0, 0), (2, 0, 0), (1, 0, 0), (3, 0, 0),
              (0, 0, 0)],
    "idle1": [(6, 0, 1), (7, 0, 1), (2, 0, 2), (1, 0, 2), (3, 0, 2),
              (0, 0, 2)],
    "walk0": [(6, -6, -1), (7, 6, 0), (2, 0, 1), (1, 0, 1), (3, 2, 1),
              (0, 0, 1)],
    "walk1": [(6, 4, 0), (7, -4, -1), (2, 0, 0), (1, 0, 0), (3, -2, 0),
              (0, 0, 0)],
    "punch": [(6, -4, 0), (7, 0, 0), (2, -2, 0), (1, 2, 0), (4, 2, -2),
              (0, 3, 0)],
    # The support leg stays planted: the old trailing-leg part had its heel up
    # and no other foot in the pose, so the whole figure floated 17 px off its
    # own shadow.
    "kick":  [(6, -4, 0), (2, -2, 0), (1, -6, -1), (3, -6, -1), (8, -2, 0),
              (0, -7, -1)],
    "hit":   [(6, -8, 0), (7, -2, 1), (2, -4, 2), (1, -6, 1), (5, -5, 1),
              (0, -8, 3)],
    "jump":  [(9, 0, -6), (2, 0, -2), (1, 0, -2), (3, 0, -3), (0, 0, -2)],
}
POSE_NAMES = ["idle0", "idle1", "walk0", "walk1", "punch", "kick", "hit",
              "jump"]

# Sampled off f05 and lifted toward the value contrast the dim capture loses:
# REN's vest is olive grey (#42493f), his trousers navy (#222433), his hair the
# brightest thing in frame. KURO is near-black (#0f0e10) with the reference's
# black-and-white bandedage on forearms and shins over bare thighs.
PALETTES = {
    "ren": pal(skin=(198, 156, 118), hair=(206, 210, 214), cloth=(38, 41, 58),
               metal=(152, 160, 174), vest=(124, 137, 98),
               leg_up=(44, 48, 70), leg_lo=(40, 44, 64), wrap=(226, 224, 210),
               sandal=(26, 27, 40), belt=(48, 50, 66), glove=(52, 55, 74),
               accent=(140, 50, 56)),
    "kuro": pal(skin=(206, 164, 126), hair=(44, 48, 70), cloth=(24, 25, 36),
                metal=(140, 148, 164), vest=(48, 51, 70),
                leg_up=(20, 21, 30), leg_lo=(206, 164, 126),
                wrap=(222, 220, 206), sandal=(18, 18, 26), belt=(96, 34, 44),
                glove=(40, 42, 58), accent=(150, 46, 58), stripe=3),
}


def compose(pose, palette):
    """Composite one pose into a 96x176 RGB565 preview buffer."""
    buf = [None] * (FW * FH)
    masks = {}
    for fn in PARTS:
        masks[PARTS.index(fn)] = bake(fn(), palette)
    for idx, dx, dy in POSE_TABLE[pose]:
        x0, y0, w, h, px, mk = masks[idx]
        for y in range(h):
            for x in range(w):
                i = y * w + x
                if not (mk[i >> 3] & (0x80 >> (i & 7))):
                    continue
                gx, gy = x0 + x + dx, y0 + y + dy
                if 0 <= gx < FW and 0 <= gy < FH:
                    buf[gy * FW + gx] = px[i]
    return buf


def write_preview(path):
    from PIL import Image
    scale = 3
    cols = len(POSE_NAMES)
    img = Image.new("RGB", (FW * scale * cols, FH * scale * 2 + 8 * scale),
                    (26, 28, 36))
    for row, key in enumerate(PALETTES):
        for col, pose in enumerate(POSE_NAMES):
            buf = compose(pose, PALETTES[key])
            tile = Image.new("RGB", (FW, FH), (26, 28, 36))
            tp = tile.load()
            for y in range(FH):
                for x in range(FW):
                    v = buf[y * FW + x]
                    if v is None:
                        continue
                    tp[x, y] = (((v >> 11) & 31) * 255 // 31,
                                ((v >> 5) & 63) * 255 // 63,
                                (v & 31) * 255 // 31)
            img.paste(tile.resize((FW * scale, FH * scale), Image.NEAREST),
                      (col * FW * scale, row * (FH * scale + 8 * scale)))
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)
    img.save(path)
    print("preview ->", path)


def emit_header(path):
    baked = {}
    for key, palette in PALETTES.items():
        for fn in PARTS:
            baked[(key, fn.__name__)] = bake(fn(), palette)

    L = []
    L.append("/* Generated by tools/generate_stormarena_sprites.py - do not edit.\n"
             " *\n"
             " * StormArena25D fighter art: %d body parts per fighter, baked as\n"
             " * RGB565 with a 1-bit visibility mask and a 1-px dark outline. The\n"
             " * sample composites them per pose at runtime because eight full\n"
             " * 96x176 frames per fighter would not fit the memory budget. */\n"
             % len(PARTS))
    L.append("#ifndef VXPE_STORMARENA_SPRITES_GEN_H\n"
             "#define VXPE_STORMARENA_SPRITES_GEN_H\n\n"
             "#include <stdint.h>\n\n"
             "#define SA_FIG_W %d\n"
             "#define SA_FIG_H %d\n"
             "#define SA_NPART %d\n"
             "#define SA_NPOSE %d\n\n"
             "typedef struct SaPart {\n"
             "    uint8_t ox, oy;          /* origin on the 96x176 figure canvas */\n"
             "    uint8_t w, h;\n"
             "    const uint16_t* px;      /* row-major, w*h entries */\n"
             "    const uint8_t* mask;     /* 1 bit per pixel, MSB first */\n"
             "} SaPart;\n\n"
             "typedef struct SaPoseSlot {\n"
             "    int8_t part, dx, dy;\n"
             "} SaPoseSlot;\n\n"
             % (FW, FH, len(PARTS), len(POSE_NAMES)))

    def arr(name, vals, per, fmt):
        rows = [fmt[1] % v for v in vals]
        L.append("static const %s %s[%d] = {" % (fmt[0], name, len(vals)))
        for i in range(0, len(rows), per):
            L.append("  " + ", ".join(rows[i:i + per]) + ",")
        L.append("};\n")

    for key in PALETTES:
        for fn in PARTS:
            x0, y0, w, h, px, mk = baked[(key, fn.__name__)]
            arr("sa_px_%s_%s" % (key, fn.__name__), px, 12, ("uint16_t", "0x%04X"))
            arr("sa_mk_%s_%s" % (key, fn.__name__), list(mk), 16,
                ("uint8_t", "0x%02X"))

    for key in PALETTES:
        L.append("static const SaPart SA_PARTS_%s[SA_NPART] = {" % key.upper())
        for fn in PARTS:
            x0, y0, w, h, px, mk = baked[(key, fn.__name__)]
            L.append("    { %d, %d, %d, %d, sa_px_%s_%s, sa_mk_%s_%s },"
                     % (x0, y0, w, h, key, fn.__name__, key, fn.__name__))
        L.append("};\n")

    L.append("/* back-to-front; SA_POSE_LEN slots per pose, unused slots have"
             " part = -1 */")
    maxlen = max(len(v) for v in POSE_TABLE.values())
    L.append("#define SA_POSE_LEN %d" % maxlen)
    L.append("static const SaPoseSlot SA_POSES[SA_NPOSE][SA_POSE_LEN] = {")
    for pose in POSE_NAMES:
        slots = POSE_TABLE[pose]
        L.append("  { " + ", ".join("{%d,%d,%d}" % s for s in slots)
                 + ", " + ", ".join("{-1,0,0}" for _ in range(maxlen - len(slots)))
                 + " },")
    L.append("};\n")
    L.append("/* part and pose ids, in authoring order */")
    for i, fn in enumerate(PARTS):
        L.append("#define SA_P_%s %d" % (fn.__name__.upper(), i))
    L.append("")
    for i, pose in enumerate(POSE_NAMES):
        L.append("#define SA_POSE_%s %d" % (pose.upper(), i))
    L.append("\n#endif /* VXPE_STORMARENA_SPRITES_GEN_H */")

    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)
    with open(path, "w", newline="\n") as f:
        f.write("\n".join(L) + "\n")
    total = sum(len(b[4]) * 2 + len(b[5]) for b in baked.values())
    print("header ->", path, "(%d bytes of sprite data, %d parts)"
          % (total, len(PARTS) * len(PALETTES)))


def main():
    if "--preview" in sys.argv:
        write_preview(PREVIEW)
    else:
        emit_header(OUT_HEADER)
        write_preview(PREVIEW)


if __name__ == "__main__":
    main()
