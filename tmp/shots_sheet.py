"""Turn the host harness's raw RGB565 dumps into one labelled contact sheet, so
the splash/menu/help layouts are judged by eye at 2x like the sprite work."""
import array
import glob
import os

from PIL import Image, ImageDraw

SCALE = 2
W, H = 240, 320
BG = (20, 22, 30)
LABEL_H = 14
GUTTER = 8


def load565(path):
    src = array.array("H", open(path, "rb").read())
    out = bytearray(len(src) * 3)
    for i, v in enumerate(src):
        r, g, b = (v >> 11) & 31, (v >> 5) & 63, v & 31
        o = i * 3
        out[o] = (r << 3) | (r >> 2)
        out[o + 1] = (g << 2) | (g >> 3)
        out[o + 2] = (b << 3) | (b >> 2)
    return Image.frombytes("RGB", (W, H), bytes(out))


files = sorted(glob.glob("tmp/shots/*.565"), key=lambda p: int(p.split(".")[-2]))
cols = 5
rows = (len(files) + cols - 1) // cols
sheet = Image.new("RGB", (cols * (W * SCALE + GUTTER) + GUTTER,
                          rows * (H * SCALE + LABEL_H + GUTTER) + GUTTER), BG)
draw = ImageDraw.Draw(sheet)

for i, path in enumerate(files):
    img = load565(path).resize((W * SCALE, H * SCALE), Image.NEAREST)
    x = GUTTER + (i % cols) * (W * SCALE + GUTTER)
    y = GUTTER + (i // cols) * (H * SCALE + LABEL_H + GUTTER)
    sheet.paste(img, (x, y))
    draw.text((x + 2, y + H * SCALE + 2),
              os.path.basename(path).split(".")[0], fill=(200, 205, 220))

sheet.save("tmp/shots_sheet.png")
print("wrote", sheet.size, len(files), "panels")
