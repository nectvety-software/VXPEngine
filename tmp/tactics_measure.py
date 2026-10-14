"""Measure the reference tactics GIF so the asset generator targets real values:
grid period, palette, and the mean colour of each terrain/unit region.
Run with the project venv (PIL)."""
from collections import Counter

from PIL import Image


def hist(path, top=28):
    im = Image.open(path).convert("RGB")
    # drop the decorative tan border frame: it dominates the histogram
    im = im.crop((8, 8, im.size[0] - 8, im.size[1] - 8))
    c = Counter(im.getdata())
    return im, c.most_common(top)


def grid_period(im, x0, x1, y):
    """Return the lag (2..24) with the strongest luminance autocorrelation."""
    px = im.load()
    lum = [sum(px[x, y]) / 3.0 for x in range(x0, x1)]
    m = sum(lum) / len(lum)
    best = []
    for lag in range(2, 25):
        s = sum((lum[i] - m) * (lum[i + lag] - m) for i in range(len(lum) - lag))
        best.append((s, lag))
    best.sort(reverse=True)
    return best[:4]


def region(im, box, name):
    crop = im.crop(box)
    px = crop.load()
    n = crop.size[0] * crop.size[1]
    r = sum(px[i % crop.size[0], i // crop.size[0]][0] for i in range(n)) // n
    g = sum(px[i % crop.size[0], i // crop.size[0]][1] for i in range(n)) // n
    b = sum(px[i % crop.size[0], i // crop.size[0]][2] for i in range(n)) // n
    print("%-14s #%02x%02x%02x" % (name, r, g, b))
    return (r, g, b)


def main():
    im, top = hist("tmp/tactics_ref/g00.png")
    print("== top colours (rgb565 target in brackets)")
    for (c, n) in top:
        r, g, b = c
        q = ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3)
        print("  #%02x%02x%02x  %6d  %04x" % (r, g, b, n, q))
    print("== grid period (lag, score) on a grass row")
    print("  y=470:", grid_period(im, 20, 220, 470))
    print("  y=300:", grid_period(im, 20, 220, 300))
    print("== region means")
    region(im, (30, 460, 90, 500), "grass")
    region(im, (150, 470, 190, 500), "road")
    region(im, (300, 60, 420, 160), "lake")
    region(im, (60, 300, 110, 380), "mountain")
    region(im, (100, 330, 150, 390), "forest")
    region(im, (430, 300, 470, 340), "castle gold")


if __name__ == "__main__":
    main()
