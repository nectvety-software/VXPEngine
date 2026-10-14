"""Compose selected StormArena25D poses next to the reference fighter so art
changes are judged by eye at device scale, not by pixel-diff counts."""
import importlib.util
import sys

from PIL import Image

spec = importlib.util.spec_from_file_location(
    "g", "tools/generate_stormarena_sprites.py")
g = importlib.util.module_from_spec(spec)
sys.modules["g"] = g
spec.loader.exec_module(g)

POSES = ["idle0", "walk0", "punch", "kick", "hit", "jump"]
SCALE = 2
BG = (26, 28, 36)
# Reference columns, so every pose is judged against the frame it copies
# rather than from memory of it.
REF = {"ren": ("tmp/refvid/f05.png", (200, 120, 275, 262), 127),
       "kuro": ("tmp/refvid/f05.png", (245, 145, 340, 268), 123)}


def ref_tile(key):
    path, box, subj_h = REF[key]
    c = Image.open(path).convert("RGB").crop(box)
    k = (g.FH - 10) * SCALE / float(subj_h)
    c = c.resize((int(c.width * k), int(c.height * k)), Image.NEAREST)
    out = Image.new("RGB", (g.FW * SCALE, g.FH * SCALE), BG)
    out.paste(c, (max(0, (out.width - c.width) // 2),
                  max(0, out.height - c.height)))
    return out


def tile(pose, key):
    buf = g.compose(pose, g.PALETTES[key])
    im = Image.new("RGB", (g.FW, g.FH), BG)
    px = im.load()
    for y in range(g.FH):
        for x in range(g.FW):
            v = buf[y * g.FW + x]
            if v is None:
                continue
            px[x, y] = (((v >> 11) & 31) * 255 // 31, ((v >> 5) & 63) * 255 // 63,
                        (v & 31) * 255 // 31)
    return im.resize((g.FW * SCALE, g.FH * SCALE), Image.NEAREST)


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else "tmp/art_sheet.png"
    tw, th = g.FW * SCALE, g.FH * SCALE
    cols = ["REF"] + POSES
    img = Image.new("RGB", (tw * len(cols), th * 2 + 10), BG)
    for row, key in enumerate(("ren", "kuro")):
        for col, pose in enumerate(cols):
            im = ref_tile(key) if pose == "REF" else tile(pose, key)
            img.paste(im, (col * tw, row * (th + 10)))
    img.save(out)
    print("sheet ->", out, img.size)


if __name__ == "__main__":
    main()
