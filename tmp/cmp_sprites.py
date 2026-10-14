"""Scratch: render StormArena poses next to the reference fighter."""
import importlib.util
from PIL import Image

spec = importlib.util.spec_from_file_location(
    "gen", "tools/generate_stormarena_sprites.py")
gen = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gen)


def tile(pose, key='ren'):
    buf = gen.compose(pose, gen.PALETTES[key])
    t = Image.new('RGB', (gen.FW, gen.FH), (26, 28, 36))
    tp = t.load()
    for y in range(gen.FH):
        for x in range(gen.FW):
            v = buf[y * gen.FW + x]
            if v is None:
                continue
            tp[x, y] = (((v >> 11) & 31) * 255 // 31,
                        ((v >> 5) & 63) * 255 // 63, (v & 31) * 255 // 31)
    return t


S = 4
ref = Image.open('tmp/refvid/f01.png').convert('RGB').crop(
    (124, 72, 186, 246)).resize((62 * S, 174 * S), Image.NEAREST)
poses = gen.POSE_NAMES
for nm, sel in [('tmp/cmp_row1.png', poses[:4]), ('tmp/cmp_row2.png', poses[4:])]:
    out = Image.new('RGB', (ref.width + (gen.FW * S) * len(sel),
                            max(ref.height, gen.FH * S)), (26, 28, 36))
    out.paste(ref, (0, 0))
    for i, pp in enumerate(sel):
        out.paste(tile(pp).resize((gen.FW * S, gen.FH * S), Image.NEAREST),
                  (ref.width + (gen.FW * S) * i, 0))
    out.save(nm)
print('wrote tmp/cmp_row1.png tmp/cmp_row2.png')
