#!/usr/bin/env python3
"""vxp_bake_light.py — offline vertex-light baker for MRE VXP (host only).

Clean-room companion to VxpSoft3D: mirrors the integer bake math
(vxpe_soft3d_bake_vertex_light) in Python so artists can bake lighting on the
host and ship only baked illumination arrays to the device — the same
"bake on desktop, play on device" division described in YMGRE's public docs
(scene/texture baking tools), reimplemented here from scratch.

Usage:
    python3 vxp_bake_light.py mesh.json --light 0,0,16384 --ambient 70 --diffuse 185 -o out.json

mesh.json: {"positions": [[x,y,z], ...], "normals": [[x,y,z], ...],
            "shadow": [0..255, ...] (optional)}
out.json:  {"illumination": [0..255, ...]}
"""
import argparse
import json
import math
import sys


def bake(positions, normals, light, ambient, diffuse, shadow=None):
    lx, ly, lz = light
    llen = math.sqrt(lx * lx + ly * ly + lz * lz) or 1.0
    out = []
    for i, (p, n) in enumerate(zip(positions, normals)):
        nx, ny, nz = n
        nlen = math.sqrt(nx * nx + ny * ny + nz * nz)
        if nlen == 0:
            ndl = 0.0
        else:
            ndl = abs(nx * lx + ny * ly + nz * lz) / (nlen * llen)
            ndl = min(1.0, max(0.0, ndl))
        ill = ambient + diffuse * ndl
        if shadow is not None:
            ill = ill * (255 - shadow[i]) / 255.0
        out.append(int(min(255, max(0, round(ill)))))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description="Bake per-vertex illumination for VxpSoft3D")
    ap.add_argument("mesh", help="input mesh.json")
    ap.add_argument("--light", default="0,0,16384", help="direction towards light")
    ap.add_argument("--ambient", type=int, default=70)
    ap.add_argument("--diffuse", type=int, default=185)
    ap.add_argument("-o", "--output", default="baked.json")
    args = ap.parse_args(argv)
    with open(args.mesh, encoding="utf-8") as f:
        mesh = json.load(f)
    light = tuple(int(v) for v in args.light.split(","))
    ill = bake(mesh["positions"], mesh["normals"], light,
               args.ambient, args.diffuse, mesh.get("shadow"))
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump({"illumination": ill}, f)
    print(f"baked {len(ill)} vertices -> {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
