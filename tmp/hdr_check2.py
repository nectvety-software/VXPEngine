"""Re-composite poses straight from sprites_gen.h (same logic as blit_part) and
render them on a magenta checker so any stray opaque pixels are obvious."""
import re
import sys
from PIL import Image

HDR = "examples/StormArena25D/src/sprites_gen.h"
FW, FH = 96, 176
SCALE = 3
t = open(HDR, encoding="utf-8").read()


def arr(n):
    m = re.search(r"static const \w+ " + n + r"\[[0-9]*\] = \{(.*?)\n\};", t, re.S)
    if not m:
        raise SystemExit("missing " + n)
    return [int(x, 16) for x in re.findall(r"0[xX][0-9a-fA-F]+", m.group(1))]


def c565(v):
    return ((v >> 11) * 255 // 31, ((v >> 5) & 63) * 255 // 63, (v & 31) * 255 // 31)


def parts_of(fig):
    rows = re.findall(r"\{ (\d+), (\d+), (\d+), (\d+), (sa_px_" + fig + r"_\w+), "
                      r"(sa_mk_" + fig + r"_\w+) \}", t)
    return [(int(a), int(b), int(c), int(d), arr(p), arr(m))
            for a, b, c, d, p, m in rows]


POSE_BLOCK = re.search(r"SA_POSES\s*(?:\[[^\]]*\])+\s*=\s*\{(.*?)\n\};", t, re.S)
POSES = []
for row in re.findall(r"\{((?:\s*\{[^{}]*\},?)+\s*)\}", POSE_BLOCK.group(1)):
    slots = [tuple(int(v) for v in s.split(","))
             for s in re.findall(r"\{([^{}]*)\}", row)]
    POSES.append(slots)

names = ["idle0", "idle1", "walk0", "walk1", "punch", "kick", "hit", "jump"]
fig = sys.argv[1] if len(sys.argv) > 1 else "ren"
P = parts_of(fig)
tiles = []
for nm, slots in zip(names, POSES):
    px = [0] * (FW * FH)
    al = [0] * (FW * FH)
    for part, dx, dy in slots:
        if part < 0:
            continue
        ox, oy, w, h, pd, md = P[part]
        for y in range(h):
            gy = oy + y + dy
            if gy < 0 or gy >= FH:
                continue
            for x in range(w):
                k = y * w + x
                if not (md[k >> 3] & (0x80 >> (k & 7))):
                    continue
                gx = ox + x + dx
                if gx < 0 or gx >= FW:
                    continue
                px[gy * FW + gx] = pd[k]
                al[gy * FW + gx] = 255
    im = Image.new("RGB", (FW, FH))
    p = im.load()
    for y in range(FH):
        for x in range(FW):
            i = y * FW + x
            if al[i]:
                p[x, y] = c565(px[i])
            else:
                p[x, y] = (255, 0, 255) if (x // 8 + y // 8) % 2 else (0, 200, 0)
    tiles.append((nm, im))

sheet = Image.new("RGB", (FW * SCALE * 4, FH * SCALE * 2), (20, 20, 20))
for i, (nm, im) in enumerate(tiles):
    im = im.resize((FW * SCALE, FH * SCALE), Image.NEAREST)
    sheet.paste(im, ((i % 4) * FW * SCALE, (i // 4) * FH * SCALE))
out = "tmp/pose_sheet_%s.png" % fig
sheet.save(out)
print("wrote", out, "parts:", len(P))
for i, (ox, oy, w, h, pd, md) in enumerate(P):
    bits = sum(bin(b).count("1") for b in md)
    print("  %2d %2dx%-3d ink=%d/%d" % (i, w, h, bits, w * h))
