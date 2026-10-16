#!/usr/bin/env python3
"""Gate tests for tools/vxp_import_sprite_forge.py.

Run under CTest (vxpe_sprite_forge_importer). It re-bakes the committed fixture
headers and compares them byte for byte, so a change to the importer that would
silently alter a shipped game's art fails here; then it drives every gate the
importer claims to enforce.

argv: <importer.py> <repo-root>
"""

import os
import re
import shutil
import subprocess
import sys
import tempfile

try:
    from PIL import Image
except ImportError:
    print("ERROR: Pillow is required to run the sprite-forge gate test")
    raise SystemExit(2)

FAILED = []


def check(label, cond, detail=""):
    if cond:
        print("  ok   %s" % label)
    else:
        FAILED.append(label)
        print("  FAIL %s%s" % (label, (" - " + detail) if detail else ""))


def run(tool, args, expect_rc):
    proc = subprocess.run([sys.executable, tool] + args,
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace")
    out = (proc.stdout or "") + (proc.stderr or "")
    if proc.returncode != expect_rc:
        FAILED.append("rc for %s: got %d want %d" % (" ".join(args), proc.returncode, expect_rc))
        print("  FAIL rc %d for %s\n%s" % (proc.returncode, " ".join(args), out))
    return out


def read(path):
    with open(path, "rb") as fh:
        return fh.read()


def draw(path, w, h, painter):
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    px = im.load()
    for (x, y, colour) in painter(w, h):
        px[x, y] = colour
    im.save(path)


O = (255, 0, 0, 255)
G = (56, 183, 100, 255)


def main():
    tool = os.path.abspath(sys.argv[1])
    tests_dir = os.path.abspath(sys.argv[2])
    data = os.path.join(tests_dir, "data", "sprite_forge")
    if not os.path.isdir(data):
        print("ERROR: fixture tree not found at %s" % data)
        return 2
    out_dir = tempfile.mkdtemp(prefix="vxpe_sprite_forge_")
    loose = os.path.join(data, "loose")
    bundle = os.path.join(data, "bundle")
    try:
        # 1. The committed fixtures must still be exactly what the tool emits.
        for rel, extra in (("fixture_loose.h", ["--input", os.path.join(data, "loose"),
                                                "--prefix", "ff_loose"]),
                           ("fixture_atlas.h", ["--input", os.path.join(data, "bundle"),
                                                "--prefix", "ff_bundle", "--mode", "atlas",
                                                "--atlas-cols", "2"])):
            regen = os.path.join(out_dir, rel)
            run(tool, extra + ["--out", regen], 0)
            committed = os.path.join(data, rel)
            check("%s reproduces the committed fixture" % rel,
                  read(regen) == read(committed),
                  "re-run: python %s %s --out %s" % (tool, " ".join(extra), committed))

        # 2. Same input twice must give the same bytes: no dict order, no clock.
        a = os.path.join(out_dir, "det_a.h")
        b = os.path.join(out_dir, "det_b.h")
        run(tool, ["--input", loose, "--prefix", "det", "--out", a], 0)
        run(tool, ["--input", loose, "--prefix", "det", "--out", b], 0)
        check("two runs are byte-identical", read(a) == read(b))

        # 3. Masks are packed the way mask_visible() reads them: bit y*width+x,
        #    MSB first, no row padding. Recompute independently and compare.
        with open(os.path.join(data, "fixture_loose.h"), encoding="utf-8") as fh:
            text = fh.read()
        with Image.open(os.path.join(loose, "frames", "hero_masked.png")) as im:
            im = im.convert("RGBA")
            w, h = im.size
            src = list(im.getdata())
        mask = bytearray((w * h + 7) // 8)
        for i, pixel in enumerate(src):
            if pixel[3] >= 128:
                mask[i >> 3] |= 0x80 >> (i & 7)
        array = text.split("ff_loose_mk_HERO_MASKED[")[1].split("};")[0]
        got = [int(v, 16) for v in re.findall(r"0x([0-9A-Fa-f]{2})", array)]
        check("mask array matches an independent packer", got == list(mask),
              "want %s got %s" % ([hex(v) for v in mask], [hex(v) for v in got]))
        check("fully opaque frame emits no mask",
              "ff_loose_mk_TILE_OPAQUE" not in text and
              "{ ff_loose_px_TILE_OPAQUE, 0, 8, 8, 8, 1 }" in text)

        # 4. Gates that must fail closed.
        blank = os.path.join(out_dir, "blank")
        os.makedirs(os.path.join(blank, "frames"))
        draw(os.path.join(blank, "frames/e.png"), 8, 8, lambda w, h: [])
        run(tool, ["--input", blank, "--out", os.path.join(out_dir, "blank.h")], 1)

        collapse = os.path.join(out_dir, "collapse")
        os.makedirs(os.path.join(collapse, "frames"))
        draw(os.path.join(collapse, "frames/c.png"), 8, 8,
             lambda w, h: [(x, y, (10, 10, 10, 255) if (x + y) % 2 else (8, 8, 8, 255))
                           for x in range(w) for y in range(h)])
        out = run(tool, ["--input", collapse, "--out", os.path.join(out_dir, "c.h")], 1)
        check("collapse gate names the shared 565 value", "collapse to RGB565" in out)
        run(tool, ["--input", collapse, "--out", os.path.join(out_dir, "c_ok.h"),
                   "--allow-collapse"], 0)

        stale = os.path.join(out_dir, "stale")
        shutil.copytree(os.path.join(data, "bundle"), stale)
        draw(os.path.join(stale, "frames/stand.png"), 8, 8,
             lambda w, h: [(x, y, O) for x in range(1, 7) for y in range(1, 7)])
        out = run(tool, ["--input", stale, "--mode", "atlas",
                         "--out", os.path.join(out_dir, "stale.h")], 1)
        check("manifest sha256 mismatch is refused", "sha256 mismatch" in out, out.strip()[:160])

        mixed = os.path.join(out_dir, "mixed.h")
        out = run(tool, ["--input", loose, "--mode", "atlas", "--out", mixed], 1)
        check("atlas mode refuses mixed frame sizes", "uniform frame size" in out, out.strip()[:160])

        run(tool, ["--input", loose, "--out", os.path.join(out_dir, "cols.h"),
                   "--max-colors", "2"], 1)
        run(tool, ["--input", bundle, "--mode", "atlas",
                   "--out", os.path.join(out_dir, "dim.h"), "--max-dimension", "4"], 1)
        run(tool, ["--input", bundle, "--mode", "atlas",
                   "--out", os.path.join(out_dir, "bud.h"), "--max-atlas-pixels", "16"], 1)
        run(tool, ["--input", bundle, "--mode", "atlas", "--clip", "nosuch",
                   "--out", os.path.join(out_dir, "clip.h")], 1)
        run(tool, ["--input", "no/such/dir", "--out", os.path.join(out_dir, "x.h")], 2)
        out = run(tool, ["--input", bundle, "--variant", "forest",
                         "--out", os.path.join(out_dir, "v.h")], 2)
        check("--variant cannot silently ignore a manifest",
              "has a clip manifest" in out, out.strip()[:160])

        # 5. Alpha handling is a documented threshold, never a silent blend.
        semi = os.path.join(out_dir, "semi")
        os.makedirs(os.path.join(semi, "frames"))
        draw(os.path.join(semi, "frames/s.png"), 8, 8,
             lambda w, h: [(x, y, G if y < 4 else (56, 183, 100, 200))
                           for x in range(1, 7) for y in range(1, 7)] +
             [(x, 6, (56, 183, 100, 100)) for x in range(1, 7)])
        out = run(tool, ["--input", semi, "--prefix", "semi",
                         "--out", os.path.join(out_dir, "semi.h")], 0)
        check("alpha below the threshold is reported as dropped",
              "made transparent" in out, out.strip()[:160])
        check("partial alpha warns instead of blending", "partial alpha" in out,
              out.strip()[:160])
        out = run(tool, ["--input", semi, "--prefix", "semi2", "--alpha-threshold", "64",
                         "--out", os.path.join(out_dir, "semi2.h")], 0)
        check("a lower threshold keeps the fainter pixels", "made transparent" not in out,
              out.strip()[:160])

        # 6. Clip selection reaches the header.
        one = os.path.join(out_dir, "one.h")
        run(tool, ["--input", bundle, "--mode", "atlas", "--clip", "hurt",
                   "--prefix", "ff_one", "--out", one], 0)
        with open(one, encoding="utf-8") as fh:
            only = fh.read()
        check("--clip emits only the chosen clip",
              "ff_one_hurt" in only and "ff_one_idle" not in only and "ff_one_walk" not in only)

        # 7. JSON summary reports the numbers a doc would cite.
        js = os.path.join(out_dir, "json.h")
        out = run(tool, ["--input", bundle, "--mode", "atlas", "--json", "--out", js], 0)
        line = [l for l in out.splitlines() if l.startswith("{")]
        check("--json prints one parseable line", bool(line), out.strip()[:160])
        if line:
            import json
            doc = json.loads(line[0])
            check("json summary counts frames and clips",
                  doc["frames"] == 4 and doc["clips"] == 3 and doc["mode"] == "atlas",
                  str(doc))
    finally:
        shutil.rmtree(out_dir, ignore_errors=True)

    if FAILED:
        print("sprite-forge importer FAILED %d check(s)" % len(FAILED))
        for f in FAILED:
            print(" - %s" % f)
        return 1
    print("sprite-forge importer ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
