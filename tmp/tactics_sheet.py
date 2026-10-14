"""Turn the TacticsVanguard2D host harness's raw RGB565 dumps into labelled
contact sheets, grouped by screen so each sheet stays readable at 2x:
splash/menu, the battle front end, the enemy phase, the player attack, and the
auto-played tail. Judged by eye like the sprite sheets."""
import array
import glob
import os
import re
from collections import defaultdict

from PIL import Image, ImageDraw, ImageFont

SCALE = 2
W, H = 240, 320
BG = (18, 20, 28)
LABEL_H = 15
GUTTER = 6
PER_SHEET = 12
GROUPS = [
    ("splash", "splash"),
    ("menu", "menu"),
    ("help", "help"),
    ("battle", "battle"),
    ("range", "range"),
    ("path", "path"),
    ("walk", "walk"),
    ("card", "card"),
    ("attack", "attack_no_target"),
    ("round", "round2_start"),
    ("ai", "ai_"),
    ("atk", "atk"),
    ("play", "play_"),
    ("result", "result_menu"),
    ("fight", "fight_again"),
    ("lose", "lose_"),
]
OUT = "tmp"


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


files = sorted(glob.glob("tmp/tshots/*.565"))
by_tag = {}
for p in files:
    m = re.match(r"\d+_(.+)\.565$", os.path.basename(p))
    by_tag[m.group(1)] = p

# Groups are prefix families; a family larger than PER_SHEET splits in order.
taken = set()
plan = []
for name, prefix in GROUPS:
    tags = [t for t in by_tag if t.startswith(prefix) and t not in taken]
    tags.sort(key=lambda t: int(re.match(r"(\d+)_", os.path.basename(by_tag[t])).group(1)))
    taken.update(tags)
    for i in range(0, len(tags), PER_SHEET):
        plan.append((name if len(tags) <= PER_SHEET else "%s_%d" % (name, i // PER_SHEET),
                     tags[i:i + PER_SHEET]))

missing = sorted(set(by_tag) - taken)
if missing:
    print("UNGROUPED:", ",".join(missing))

font = ImageFont.load_default()
for name, tags in plan:
    cols = 4
    rows = (len(tags) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * (W * SCALE + GUTTER) + GUTTER,
                              rows * (H * SCALE + LABEL_H + GUTTER) + GUTTER), BG)
    draw = ImageDraw.Draw(sheet)
    for i, tag in enumerate(tags):
        img = load565(by_tag[tag]).resize((W * SCALE, H * SCALE), Image.NEAREST)
        x = GUTTER + (i % cols) * (W * SCALE + GUTTER)
        y = GUTTER + (i // cols) * (H * SCALE + LABEL_H + GUTTER)
        sheet.paste(img, (x, y))
        draw.text((x + 3, y + H * SCALE + 3), tag, fill=(205, 210, 228), font=font)
    path = "tmp/tactics_sheet_%s.png" % name
    sheet.save(path)
    print("sheet %-28s %s  %d panels" % (os.path.basename(path), sheet.size, len(tags)))
print("total %d frames" % len(files))
