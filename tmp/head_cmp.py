import importlib.util
from PIL import Image

spec = importlib.util.spec_from_file_location(
    "gen", "tools/generate_stormarena_sprites.py")
gen = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gen)

buf = gen.compose("idle0", gen.PALETTES["ren"])
mine = Image.new("RGB", (gen.FW, gen.FH), (26, 28, 36))
tp = mine.load()
for y in range(gen.FH):
    for x in range(gen.FW):
        v = buf[y * gen.FW + x]
        if v is None:
            continue
        tp[x, y] = (((v >> 11) & 31) * 255 // 31, ((v >> 5) & 63) * 255 // 63,
                    (v & 31) * 255 // 31)
mine = mine.crop((14, 0, 66, 44))

ref = Image.open("tmp/refvid/f01.png").convert("RGB").crop((138, 72, 176, 112))
Z = 8
out = Image.new("RGB", (ref.width * Z + mine.width * Z + 8,
                        max(ref.height, mine.height) * Z), (24, 24, 24))
out.paste(ref.resize((ref.width * Z, ref.height * Z), Image.NEAREST), (0, 0))
out.paste(mine.resize((mine.width * Z, mine.height * Z), Image.NEAREST),
          (ref.width * Z + 8, 0))
out.save("tmp/head_cmp.png")
print("wrote tmp/head_cmp.png")
