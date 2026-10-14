"""Contact sheet for the TacticsVanguard2D live emulator grabs: every 240x320
device frame in tmp/tactics_emu, labelled, 4 columns, 2x. Judged by eye against
the host harness sheets in tmp/tactics_sheet_*.png."""
import glob
import os
import re

from PIL import Image, ImageDraw, ImageFont

SCALE = 2
OUT = "tmp/tactics_emu_sheet"
files = sorted(glob.glob("tmp/tactics_emu/*.png"))
files = [p for p in files if "hud" not in os.path.basename(p)]
font = ImageFont.load_default()
PER = 12
for part in range(0, (len(files) + PER - 1) // PER):
    chunk = files[part * PER:(part + 1) * PER]
    cols = 4
    rows = (len(chunk) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * (480 + 6) + 6, rows * (640 + 16 + 6) + 6),
                      (18, 20, 28))
    draw = ImageDraw.Draw(sheet)
    for i, p in enumerate(chunk):
        img = Image.open(p).resize((480, 640), Image.NEAREST)
        x = 6 + (i % cols) * (480 + 6)
        y = 6 + (i // cols) * (640 + 16 + 6)
        sheet.paste(img, (x, y))
        draw.text((x + 3, y + 642), os.path.basename(p), fill=(205, 210, 228),
                  font=font)
    name = OUT + ("_%d.png" % part if (len(files) + PER - 1) // PER > 1 else ".png")
    sheet.save(name)
    print("sheet %-34s %d panels" % (os.path.basename(name), len(chunk)))
print("frames:", len(files))
