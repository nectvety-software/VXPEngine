"""Decode sprites_gen.h and composite idle0 exactly like main.c's blit_part."""
import re
import io
from PIL import Image

src = io.open("examples/StormArena25D/src/sprites_gen.h", encoding="utf-8").read()

arrays = {}
for m in re.finditer(r"static const (?:uint16_t|uint8_t) (sa_[a-z0-9_]+)\[\d+\] = \{(.*?)\n\};",
                     src, re.S):
    arrays[m.group(1)] = [int(v, 16) for v in re.findall(r"0x[0-9A-Fa-f]{2,4}", m.group(2))]

parts = {}
for m in re.finditer(r"\{ (\d+), (\d+), (\d+), (\d+), (sa_px_\w+), (sa_mk_\w+) \}", src):
    parts.setdefault(m.group(5).split("_")[2], []).append(
        (int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4)),
         m.group(5), m.group(6)))

poses = re.search(r"SA_POSES\[SA_NPOSE\]\[SA_POSE_LEN\] = \{(.*?)\n\};", src, re.S).group(1)
POSE = [list(map(list, re.findall(r"\{(-?\d+),(-?\d+),(-?\d+)\}", row)))
        for row in re.findall(r"\{ \{.*?\} \}", poses, re.S)]

FW, FH = 96, 176
for fighter in ("ren", "kuro"):
    px = [0] * (FW * FH)
    al = [0] * (FW * FH)
    for slot in POSE[0]:
        part, dx, dy = int(slot[0]), int(slot[1]), int(slot[2])
        if part < 0:
            continue
        ox, oy, w, h, pxa, mka = parts[fighter][part]
        A, M = arrays[pxa], arrays[mka]
        for y in range(h):
            for x in range(w):
                k = y * w + x
                if not (M[k >> 3] & (0x80 >> (k & 7))):
                    continue
                gx, gy = ox + x + dx, oy + y + dy
                if 0 <= gx < FW and 0 <= gy < FH:
                    px[gy * FW + gx] = A[k]
                    al[gy * FW + gx] = 255
    im = Image.new("RGB", (FW, FH), (26, 28, 36))
    tp = im.load()
    for y in range(FH):
        for x in range(FW):
            if not al[y * FW + x]:
                continue
            v = px[y * FW + x]
            tp[x, y] = (((v >> 11) & 31) * 255 // 31, ((v >> 5) & 63) * 255 // 63,
                        (v & 31) * 255 // 31)
    im.resize((FW * 4, FH * 4), Image.NEAREST).save("tmp/hdr_%s.png" % fighter)
print("wrote tmp/hdr_ren.png tmp/hdr_kuro.png")
