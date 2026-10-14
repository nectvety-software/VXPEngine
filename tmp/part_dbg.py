import importlib.util, sys
from PIL import Image

spec = importlib.util.spec_from_file_location(
    "gen", "tools/generate_stormarena_sprites.py")
gen = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gen)

names = sys.argv[2:] or ["leg_kick", "arm_punch", "arm_up", "leg_tuck"]
fns = {f.__name__: f for f in gen.PARTS}
pal = gen.PALETTES["ren"]
tiles = []
for nm in names:
    x, y, w, h, px, mk = gen.bake(fns[nm](), pal)
    im = Image.new("RGB", (w, h), (60, 60, 60))
    tp = im.load()
    for j in range(h):
        for i in range(w):
            v = px[j * w + i]
            m = (mk[(j * w + i) >> 3] >> (7 - ((j * w + i) & 7))) & 1
            if v is None:
                continue
            tp[i, j] = (((v >> 11) & 31) * 255 // 31,
                        ((v >> 5) & 63) * 255 // 63, (v & 31) * 255 // 31) \
                if m else (0, 255, 0)
    print(nm, "bbox", (x, y, w, h))
    tiles.append((nm, im))
Z = 5
out = Image.new("RGB", (sum(t.width for _, t in tiles) * Z + 8 * len(tiles),
                        max(t.height for _, t in tiles) * Z), (26, 28, 36))
ox = 0
for nm, t in tiles:
    out.paste(t.resize((t.width * Z, t.height * Z), Image.NEAREST), (ox, 0))
    ox += t.width * Z + 8
out.save("tmp/parts_dbg.png")
print("wrote tmp/parts_dbg.png (green = mask off but pixel written)")
