import re
import sys
from PIL import Image

BG = (128, 128, 128, 255)


def arr(text, sym):
    m = re.search(r"static const uint(?:16|8)_t %s\[\d+\] = \{(.*?)\};" % re.escape(sym),
                  text, re.S)
    if not m:
        raise SystemExit("missing array %s" % sym)
    return [int(v, 16) for v in re.findall(r"0x([0-9A-Fa-f]{2,4})", m.group(1))]


def unpack565(v):
    return (((v >> 11) & 31) * 255 // 31, ((v >> 5) & 63) * 255 // 63, (v & 31) * 255 // 31)


def sprite_from(px, mk, w, h, opaque, scale=6):
    im = Image.new("RGBA", (w * scale, h * scale), BG)
    out = im.load()
    for y in range(h):
        for x in range(w):
            if not opaque:
                bit = y * w + x
                if not (mk[bit >> 3] & (0x80 >> (bit & 7))):
                    continue
            r, g, b = unpack565(px[y * w + x])
            for dy in range(scale):
                for dx in range(scale):
                    out[x * scale + dx, y * scale + dy] = (r, g, b, 255)
    return im


def main():
    path, mode = sys.argv[1], sys.argv[2]
    text = open(path, encoding="utf-8").read()
    prefix = path.split("/")[-1].replace("_gen.h", "").replace(".h", "")
    tiles = []
    if mode == "atlas":
        up = prefix.upper()
        w = int(re.search(r"#define %s_ATLAS_W (\d+)" % up, text).group(1))
        h = int(re.search(r"#define %s_ATLAS_H (\d+)" % up, text).group(1))
        px = arr(text, "%s_atlas_px" % prefix)
        mk_sym = "%s_atlas_mk" % prefix
        mk = arr(text, mk_sym) if mk_sym in text else []
        tiles.append(sprite_from(px, mk, w, h, mk_sym not in text, 4))
    else:
        table = re.search(r"VxpeSprite565 %s_sprites\[.*?\] = \{(.*?)\n\};" % prefix,
                          text, re.S).group(1)
        for line in re.findall(r"\{ (\w+), (\w+|0), (\d+), (\d+), (\d+), (\d) \}", table):
            px_sym, mk_sym, w, h, _s, opaque = line
            w, h, opaque = int(w), int(h), int(opaque)
            tiles.append(sprite_from(arr(text, px_sym),
                                     arr(text, mk_sym) if mk_sym != "0" else [],
                                     w, h, opaque))
    pad = 8
    tw = sum(t.size[0] for t in tiles) + pad * (len(tiles) + 1)
    th = max(t.size[1] for t in tiles) + pad * 2
    sheet = Image.new("RGBA", (tw, th), (20, 20, 26, 255))
    x = pad
    for t in tiles:
        sheet.paste(t, (x, pad), t)
        x += t.size[0] + pad
    sheet.save(sys.argv[3])
    print("wrote %s: %d tiles, %dx%d" % (sys.argv[3], len(tiles), tw, th))


main()
