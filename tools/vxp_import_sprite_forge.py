#!/usr/bin/env python3
"""Bake agent-sprite-forge frames into a VXPEngine RGB565 C header.

Route: the vendored codeart2d / generate2dsprite skills emit transparent PNG
frames plus a manifest; this tool turns them into const data the core can draw
with no run-time conversion.

  sprites mode  one VxpeSprite565 per frame
  atlas  mode   one VxpeSprite565 atlas of uniform cells + VxpeRectI per cell
                + one VxpeAnimClip per clip in animation-clips.json

Gates fail closed: a fully transparent frame, a PNG whose sha256 disagrees with
the manifest, two source colours that collapse onto one RGB565 value, a
dimension or colour-budget breach. Overrides are explicit flags, never silent.
"""

import argparse
import hashlib
import json
import math
import os
import re
import sys

try:
    from PIL import Image
except ImportError:
    sys.stderr.write("ERROR: Pillow is required (python -m pip install Pillow)\n")
    raise SystemExit(2)

TOOL = "tools/vxp_import_sprite_forge.py"
WARNINGS = []


def warn(msg):
    WARNINGS.append(msg)
    print("WARNING: %s" % msg)


def fail(msg):
    print("ERROR: %s" % msg)


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def c_ident(name):
    ident = re.sub(r"[^0-9A-Za-z_]", "_", name)
    if not ident:
        return "_"
    if ident[0].isdigit():
        ident = "_" + ident
    return ident


def to565(r, g, b):
    return ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3)


def read_frame(path, expected_size=None):
    with Image.open(path) as im:
        size = im.size
        px = list(im.convert("RGBA").getdata())
    if expected_size is not None and size != tuple(expected_size):
        fail("%s: size %dx%d does not match manifest frame_size %dx%d" %
             (path, size[0], size[1], expected_size[0], expected_size[1]))
        return None
    return size, px


def bake(px, w, h, threshold):
    """RGBA -> (rgb565 flat, visible flags, source colours per value, partial-alpha count)."""
    out = []
    vis = []
    src = {}
    semi = 0
    dropped = 0
    for r, g, b, a in px:
        if a >= threshold:
            v = to565(r, g, b)
            out.append(v)
            vis.append(True)
            src.setdefault(v, set()).add((r, g, b))
        else:
            out.append(0)
            vis.append(False)
            if a > 0:
                dropped += 1
        if 0 < a < 255:
            semi += 1
    return out, vis, src, semi, dropped


def pack_mask(vis, w, h):
    """Bit y*w+x, MSB first, no row padding - exactly what mask_visible() reads."""
    mask = bytearray((w * h + 7) // 8)
    for i, bit in enumerate(vis):
        if bit:
            mask[i >> 3] |= 0x80 >> (i & 7)
    return list(mask)


def check_collapse(label, src):
    hit = False
    for v, colors in sorted(src.items()):
        if len(colors) > 1:
            fail("%s: %d source colours collapse to RGB565 0x%04X (%s); "
                 "fix the palette or pass --allow-collapse" %
                 (label, len(colors), v,
                  ", ".join("#%02x%02x%02x" % c for c in sorted(colors))))
            hit = True
    return hit


def discover_loose_frames(input_dir, variants):
    """codeart2d output tree -> [(name, path)] in deterministic order."""
    found = []
    direct = os.path.join(input_dir, "frames")
    if os.path.isdir(direct):
        for fn in sorted(os.listdir(direct)):
            if fn.lower().endswith(".png"):
                found.append((os.path.splitext(fn)[0], os.path.join(direct, fn)))
        return found
    for entry in sorted(os.listdir(input_dir)):
        if variants and entry not in variants:
            continue
        frames_dir = os.path.join(input_dir, entry, "frames")
        if not os.path.isdir(frames_dir):
            continue
        for fn in sorted(os.listdir(frames_dir)):
            if fn.lower().endswith(".png"):
                stem = os.path.splitext(fn)[0]
                found.append(("%s_%s" % (entry, stem), os.path.join(frames_dir, fn)))
    if variants:
        seen = set(v for v in variants
                   if os.path.isdir(os.path.join(input_dir, v, "frames")))
        for v in sorted(set(variants) - seen):
            fail("variant '%s' has no frames/ directory under %s" % (v, input_dir))
    return found


def discover_manifest(input_dir):
    for rel in ("animation-clips.json", os.path.join("bundle", "animation-clips.json")):
        path = os.path.join(input_dir, rel)
        if os.path.isfile(path):
            return path
    return None


def load_manifest_frames(manifest_path, wanted_clips):
    with open(manifest_path, encoding="utf-8") as fh:
        doc = json.load(fh)
    base = os.path.dirname(manifest_path)
    frame_size = doc.get("frame_size")
    if not isinstance(frame_size, list) or len(frame_size) != 2:
        fail("%s: frame_size missing" % manifest_path)
        return None
    frames = []
    for entry in doc.get("frames", []):
        rel = entry.get("file")
        if not rel:
            fail("%s: frame '%s' has no file" % (manifest_path, entry.get("name")))
            return None
        path = os.path.normpath(os.path.join(base, rel))
        if not os.path.isfile(path):
            fail("%s: frame file not found: %s" % (manifest_path, path))
            return None
        want = entry.get("source", {}).get("file_sha256")
        if want:
            got = sha256_file(path)
            if got != want:
                fail("%s: sha256 mismatch for %s (manifest %s..., file %s...)" %
                     (manifest_path, rel, want[:12], got[:12]))
                return None
        frames.append({"index": int(entry.get("index", len(frames))),
                       "name": entry.get("name") or os.path.splitext(rel)[0],
                       "path": path})
    frames.sort(key=lambda f: f["index"])
    for i, f in enumerate(frames):
        if f["index"] != i:
            fail("%s: frame indexes are not contiguous from 0" % manifest_path)
            return None
    clips = {}
    for name in sorted(doc.get("clips", {})):
        if wanted_clips and name not in wanted_clips:
            continue
        clip = doc["clips"][name]
        idx = [int(v) for v in clip.get("frames", [])]
        if not idx:
            fail("%s: clip '%s' has no frames" % (manifest_path, name))
            return None
        for v in idx:
            if v < 0 or v >= len(frames):
                fail("%s: clip '%s' references frame %d outside 0..%d" %
                     (manifest_path, name, v, len(frames) - 1))
                return None
        durs = clip.get("duration_ms")
        if durs is None:
            durs = [int(clip.get("frame_ms", 150))] * len(idx)
        if len(durs) != len(idx):
            fail("%s: clip '%s' has %d durations for %d frames" %
                 (manifest_path, name, len(durs), len(idx)))
            return None
        clips[name] = {"frames": idx,
                       "duration_ms": [int(d) for d in durs],
                       "loop": 1 if clip.get("loop", True) else 0}
    for name in wanted_clips:
        if name not in clips:
            fail("%s: clip '%s' not found (available: %s)" %
                 (manifest_path, name, ", ".join(sorted(doc.get("clips", {})))))
            return None
    return {"frame_size": [int(frame_size[0]), int(frame_size[1])],
            "frames": frames, "clips": clips, "anchor_px": doc.get("anchor_px"),
            "manifest_sha256": sha256_file(manifest_path)}


def rows(values, per_line, fmt):
    out = []
    for i in range(0, len(values), per_line):
        out.append("    %s," % ", ".join(fmt % v for v in values[i:i + per_line]))
    return out


def write(path, lines):
    d = os.path.dirname(os.path.abspath(path))
    if d and not os.path.isdir(d):
        os.makedirs(d)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(lines) + "\n")


def header_prelude(prefix, provenance, extra):
    guard = "VXPE_%s_SPRITE_FORGE_H" % prefix.upper()
    lines = ["/* Generated by %s - do not edit." % TOOL, " *"]
    for p in provenance:
        lines.append(" * %s" % p)
    lines.append(" *")
    lines.extend(" * %s" % e.strip() for e in extra)
    lines += [" */", "", "#ifndef %s" % guard, "#define %s" % guard, "",
              "#include <graphics/VxpRender2D.h>", ""]
    return guard, lines


def emit_sprites(prefix, items, out_path, provenance):
    guard, lines = header_prelude(prefix, provenance, [
        "   %d masked sprites. Masks follow mask_visible() in VxpRender2D.cpp:"
        % len(items),
        "   bit y*width+x, MSB first, no row padding. A sprite with no",
        "   transparent pixel gets opaque=1 and no mask, so vxpe2d_blit takes",
        "   its memcpy fast path.",
    ])
    up = prefix.upper()
    lines.append("#define %s_NSPRITE %d" % (up, len(items)))
    lines.append("")
    table = []
    enum = []
    rodata = 0
    for slot, it in enumerate(items):
        name = c_ident(it["name"]).upper()
        w, h = it["w"], it["h"]
        px_sym = "%s_px_%s" % (prefix, name)
        lines.append("static const uint16_t %s[%d] = {" % (px_sym, w * h))
        lines.extend(rows(it["px"], 12, "0x%04X"))
        lines.append("};")
        rodata += w * h * 2
        if all(it["vis"]):
            lines.append("/* %s: fully opaque, drawn through the memcpy path. */" % it["name"])
            table.append("    { %s, 0, %d, %d, %d, 1 }," % (px_sym, w, h, w))
        else:
            mask = pack_mask(it["vis"], w, h)
            mk_sym = "%s_mk_%s" % (prefix, name)
            lines.append("static const uint8_t %s[%d] = {" % (mk_sym, len(mask)))
            lines.extend(rows(mask, 16, "0x%02X"))
            lines.append("};")
            rodata += len(mask)
            table.append("    { %s, %s, %d, %d, %d, 0 }," % (px_sym, mk_sym, w, h, w))
        enum.append("    %s_SPR_%s = %d" % (up, name, slot))
        lines.append("")
    lines.append("static const VxpeSprite565 %s_sprites[%s_NSPRITE] = {" % (prefix, up))
    lines.extend(table)
    lines.append("};")
    lines.append("")
    lines.append("enum {")
    lines.append(",\n".join(enum))
    lines.append("};")
    lines += ["", "#endif"]
    write(out_path, lines)
    return rodata


def emit_atlas(prefix, items, clips, cols, out_path, provenance):
    tw, th = items[0]["w"], items[0]["h"]
    rows_n = (len(items) + cols - 1) // cols
    aw, ah = cols * tw, rows_n * th
    px = [0] * (aw * ah)
    vis = [False] * (aw * ah)
    for slot, it in enumerate(items):
        ox, oy = (slot % cols) * tw, (slot // cols) * th
        for y in range(th):
            dst = (oy + y) * aw + ox
            src = y * tw
            for x in range(tw):
                px[dst + x] = it["px"][src + x]
                vis[dst + x] = it["vis"][src + x]
    fully_opaque = all(vis)
    mask = None if fully_opaque else pack_mask(vis, aw, ah)
    up = prefix.upper()
    guard, lines = header_prelude(prefix, provenance, [
        "   Atlas of %d uniform %dx%d cells in %d column(s), size %dx%d." %
        (len(items), tw, th, cols, aw, ah),
        "   stride == width, so mask_visible() indexing stays exact for both",
        "   vxpe2d_blit src rects and VxpTilemap2D cell lookups.",
        "   %s" % ("Every pixel is visible: opaque=1, no mask." if fully_opaque else
                   "Mask bit y*%d+x, MSB first." % aw),
    ])
    lines += [
        "#define %s_TILE_W %d" % (up, tw),
        "#define %s_TILE_H %d" % (up, th),
        "#define %s_ATLAS_COLS %d" % (up, cols),
        "#define %s_ATLAS_ROWS %d" % (up, rows_n),
        "#define %s_ATLAS_W %d" % (up, aw),
        "#define %s_ATLAS_H %d" % (up, ah),
        "#define %s_NFRAME %d" % (up, len(items)),
        "",
        "static const uint16_t %s_atlas_px[%d] = {" % (prefix, aw * ah),
    ]
    lines.extend(rows(px, 12, "0x%04X"))
    lines.append("};")
    if mask is not None:
        lines += ["", "static const uint8_t %s_atlas_mk[%d] = {" % (prefix, len(mask))]
        lines.extend(rows(mask, 16, "0x%02X"))
        lines.append("};")
    lines += ["", "static const VxpeSprite565 %s_atlas = {" % prefix]
    if mask is None:
        lines.append("    %s_atlas_px, 0, %d, %d, %d, 1," % (prefix, aw, ah, aw))
    else:
        lines.append("    %s_atlas_px, %s_atlas_mk, %d, %d, %d, 0," %
                     (prefix, prefix, aw, ah, aw))
    lines.append("};")
    lines.append("")
    lines.append("enum {")
    lines.append(",\n".join("    %s_FRAME_%s = %d" % (up, c_ident(it["name"]).upper(), slot)
                            for slot, it in enumerate(items)))
    lines.append("};")
    lines.append("")
    for name in sorted(clips):
        clip = clips[name]
        sym = c_ident(name).lower()
        rect_sym = "%s_%s_rects" % (prefix, sym)
        dur_sym = "%s_%s_ms" % (prefix, sym)
        lines.append("static const VxpeRectI %s[%d] = {" % (rect_sym, len(clip["frames"])))
        for idx in clip["frames"]:
            lines.append("    { %d, %d, %d, %d }," %
                         ((idx % cols) * tw, (idx // cols) * th, tw, th))
        lines.append("};")
        lines.append("static const uint16_t %s[%d] = { %s };" %
                     (dur_sym, len(clip["duration_ms"]),
                      ", ".join(str(d) for d in clip["duration_ms"])))
        lines.append("static const VxpeAnimClip %s_%s = {" % (prefix, sym))
        lines.append("    %s, %s, %d, %d, %d, 0," %
                     (rect_sym, dur_sym, len(clip["frames"]),
                      clip["duration_ms"][0], clip["loop"]))
        lines.append("};")
        lines.append("")
    lines += ["#endif"]
    write(out_path, lines)
    return aw * ah * 2 + (len(mask) if mask else 0)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--input", required=True,
                    help="codeart2d output dir, or a generate2dsprite bundle dir")
    ap.add_argument("--out", required=True, help="C header to write")
    ap.add_argument("--prefix", help="C symbol prefix (default: input dir name)")
    ap.add_argument("--mode", choices=("sprites", "atlas"), default="sprites")
    ap.add_argument("--variant", action="append", default=[],
                    help="only these variant subdirectories (repeatable, loose frames only)")
    ap.add_argument("--clip", action="append", default=[],
                    help="only these clips from animation-clips.json (repeatable)")
    ap.add_argument("--manifest", help="animation-clips.json (auto-detected when absent)")
    ap.add_argument("--alpha-threshold", type=int, default=128,
                    help="source alpha at or above this becomes a visible pixel")
    ap.add_argument("--max-colors", type=int, default=32,
                    help="distinct RGB565 values allowed across the import (0 = no limit)")
    ap.add_argument("--max-dimension", type=int, default=255,
                    help="largest sprite width or height accepted")
    ap.add_argument("--max-atlas-pixels", type=int, default=16384,
                    help="atlas pixel budget (0 = no limit)")
    ap.add_argument("--atlas-cols", type=int, default=0,
                    help="cells per atlas row (default: near-square grid)")
    ap.add_argument("--allow-collapse", action="store_true",
                    help="accept two source colours that map to one RGB565 value")
    ap.add_argument("--allow-blank", action="store_true",
                    help="accept frames with no visible pixel at all")
    ap.add_argument("--json", action="store_true", help="print one JSON summary line")
    args = ap.parse_args()

    if not os.path.isdir(args.input):
        fail("--input is not a directory: %s" % args.input)
        return 2
    if not 0 <= args.alpha_threshold <= 255:
        fail("--alpha-threshold must be 0..255")
        return 2

    prefix = c_ident(args.prefix or os.path.basename(os.path.normpath(args.input))).lower()
    if re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", prefix) is None:
        fail("prefix '%s' is not a C identifier" % prefix)
        return 2

    manifest_path = args.manifest or discover_manifest(args.input)
    if manifest_path:
        manifest_path = os.path.normpath(manifest_path).replace("\\", "/")
    if args.manifest and not os.path.isfile(args.manifest):
        fail("manifest not found: %s" % args.manifest)
        return 2

    loaded = None
    if manifest_path is not None:
        if args.variant:
            fail("--variant selects loose frames/ subdirectories, but %s has a clip "
                 "manifest (%s); import the manifest or point --input at one variant dir"
                 % (args.input, manifest_path))
            return 2
        loaded = load_manifest_frames(manifest_path, args.clip)
        if loaded is None:
            return 1

    # No filesystem paths in the header: a generated asset must byte-match on
    # any machine, so provenance is the frame digests themselves.
    provenance = []
    items = []
    palette = {}
    semi_total = 0

    if loaded is not None:
        sources = loaded["frames"]
        provenance = ["Manifest sha256 %s" % loaded["manifest_sha256"],
                      "Every frame PNG was verified against that manifest."]
        if loaded["anchor_px"]:
            provenance.append("Forge anchor %s: shared canvas root, not a per-frame"
                              " bottom." % loaded["anchor_px"])
    else:
        sources = [{"name": n, "path": p}
                   for n, p in discover_loose_frames(args.input, args.variant)]
        provenance = ["Code-drawn frames (vendored codeart2d renderer, no image model)."]

    if not sources:
        fail("no frames imported from %s" % args.input)
        return 2
    provenance.append("Frame digests:")
    width = max(len(f["name"]) for f in sources)
    for f in sources:
        provenance.append("  %s  %s" % (f["name"].ljust(width), sha256_file(f["path"])))

    for f in sources:
        expect = loaded["frame_size"] if loaded is not None else None
        got = read_frame(f["path"], expect)
        if got is None:
            return 1
        (w, h), pxdata = got
        if w * h != len(pxdata):
            fail("%s: decoded %d pixels for a %dx%d frame" % (f["name"], len(pxdata), w, h))
            return 1
        if w > args.max_dimension or h > args.max_dimension:
            fail("%s: %dx%d exceeds --max-dimension %d" %
                 (f["name"], w, h, args.max_dimension))
            return 1
        px, vis, src, semi, dropped = bake(pxdata, w, h, args.alpha_threshold)
        semi_total += semi
        if dropped:
            warn("%s: %d pixel(s) with alpha below %d made transparent" %
                 (f["name"], dropped, args.alpha_threshold))
        if not any(vis):
            if not args.allow_blank:
                fail("%s: every pixel is transparent" % f["name"])
                return 1
            warn("%s: blank frame kept (--allow-blank)" % f["name"])
        if not args.allow_collapse and check_collapse(f["name"], src):
            return 1
        for v, colors in src.items():
            palette.setdefault(v, set()).update(colors)
        items.append({"name": f["name"], "w": w, "h": h, "px": px, "vis": vis})

    if semi_total:
        warn("%d source pixel(s) used partial alpha; the core mask is 1 bit per pixel"
             % semi_total)
    if args.max_colors and len(palette) > args.max_colors:
        fail("import uses %d distinct RGB565 colours, budget is %d (--max-colors)" %
             (len(palette), args.max_colors))
        return 1

    if args.mode == "sprites":
        rodata = emit_sprites(prefix, items, args.out, provenance)
        cols = 0
    else:
        sizes = set((it["w"], it["h"]) for it in items)
        if len(sizes) != 1:
            fail("atlas mode needs one uniform frame size, found %s" %
                 ", ".join("%dx%d" % s for s in sorted(sizes)))
            return 1
        cols = args.atlas_cols
        if cols <= 0:
            cols = max(1, int(math.ceil(math.sqrt(len(items)))))
        tw, th = items[0]["w"], items[0]["h"]
        total = cols * tw * ((len(items) + cols - 1) // cols) * th
        if args.max_atlas_pixels and total > args.max_atlas_pixels:
            fail("atlas would be %d pixels, budget is %d (--max-atlas-pixels)" %
                 (total, args.max_atlas_pixels))
            return 1
        rodata = emit_atlas(prefix, items, loaded["clips"] if loaded else {},
                            cols, args.out, provenance)

    summary = {
        "status": "pass",
        "tool": TOOL,
        "mode": args.mode,
        "prefix": prefix,
        "out": os.path.normpath(args.out).replace("\\", "/"),
        "header_bytes": os.path.getsize(args.out),
        "rodata_bytes": rodata,
        "frames": len(items),
        "clips": len(loaded["clips"]) if loaded else 0,
        "atlas_cols": cols,
        "distinct565": len(palette),
        "warnings": WARNINGS,
    }
    if args.json:
        print(json.dumps(summary, sort_keys=True))
    else:
        print("OK: %s -> %s (%d frames, %d clips, %d distinct RGB565, %d header bytes, "
              "%d bytes .rodata)" %
              (args.mode, args.out, len(items), summary["clips"], len(palette),
               summary["header_bytes"], rodata))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
