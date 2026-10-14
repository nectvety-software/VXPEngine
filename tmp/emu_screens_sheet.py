"""Contact sheet for the VXPEmu device captures of the splash/menu front end.
The grabs are already 240x320 device pixels, so this only tiles and labels
them; pass a directory to re-sheet a different run."""
import os
import sys

from PIL import Image, ImageDraw

SCALE = 2
W, H = 240, 320
BG = (20, 22, 30)
LABEL_H = 14
GUTTER = 8
COLS = 5

ORDER = ["splash_1", "splash_2", "menu_auto", "menu_idle", "menu_side_row",
         "menu_side_kuro", "help", "menu_back", "fight_1s", "fight_punch",
         "fight_late", "menu_from_fight", "splash_skip_before", "menu_skipped"]


def main():
    global SCALE
    d = sys.argv[1] if len(sys.argv) > 1 else "tmp/storm_screens"
    out = sys.argv[2] if len(sys.argv) > 2 else "tmp/emu_screens_sheet.png"
    if len(sys.argv) > 3:
        SCALE = int(sys.argv[3])
    names = [n for n in ORDER if os.path.exists(os.path.join(d, n + ".png"))]
    extra = sorted(set(f[:-4] for f in os.listdir(d) if f.endswith(".png")
                       and not f.endswith("_full.png")
                       and not f.startswith("_")) - set(ORDER))
    names += extra
    rows = (len(names) + COLS - 1) // COLS
    sheet = Image.new("RGB", (COLS * (W * SCALE + GUTTER) + GUTTER,
                              rows * (H * SCALE + LABEL_H + GUTTER) + GUTTER), BG)
    draw = ImageDraw.Draw(sheet)
    for i, name in enumerate(names):
        img = Image.open(os.path.join(d, name + ".png")).convert("RGB")
        if img.size != (W, H):
            img = img.resize((W, H), Image.NEAREST)
        img = img.resize((W * SCALE, H * SCALE), Image.NEAREST)
        x = GUTTER + (i % COLS) * (W * SCALE + GUTTER)
        y = GUTTER + (i // COLS) * (H * SCALE + LABEL_H + GUTTER)
        sheet.paste(img, (x, y))
        draw.text((x + 2, y + H * SCALE + 2), name, fill=(200, 205, 220))
    sheet.save(out)
    print("wrote", out, sheet.size, len(names), "panels")


if __name__ == "__main__":
    main()
