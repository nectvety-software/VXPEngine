#!/usr/bin/env python3
"""Sinh cac bien the scene dung cho do chi phi fill tren ARM.

Ba bien the, tat ca deu chi ve bau troi (dither) + nam thap, nen phan khac nhau
duy nhat la thanh phan can do:

  scene_tower_now.cpp   - hinh hoc thap hien tai + shading per-vertex (sun)
  scene_tower_flat.cpp  - y nguyen hinh hoc tren, nhung quay lai shading phang
                          theo tung quad voi cong thuc cu 188+((s*13+level*17)%62)
  scene_tower_prev.cpp  - ban TRUOC khi nang cap (docs/scene_toweronly.cpp):
                          hinh hoc thap cu + shading phang cu

Moi phep thay the deu duoc assert; neu nguon doi mau van ban thi script bao loi
thay vi lang le sinh ra mot bien the do dang.
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DEMO = os.path.abspath(os.path.join(HERE, "..", ".."))
CUR = os.path.join(DEMO, "src", "scene.cpp")
PREV = os.path.join(DEMO, "docs", "scene_toweronly.cpp")

SKY_PLAIN = "vxpe2d_gradient_vertical(worldPixels,WORLD_W,WORLD_H,0,0,WORLD_W,WORLD_H,"
SKY_DITHER = "vxpe2d_gradient_vertical_dithered(worldPixels,WORLD_W,WORLD_H,0,0,WORLD_W,WORLD_H,"

# Tat moi thu ngoai nam thap bang dung kieu probe da dung trong docs/ (if(0) / i<0).
TOWER_ONLY = [
    ("    quad(target,cam,sea,point(-1800,0,0)",
     "    if(0)quad(target,cam,sea,point(-1800,0,0)"),
    ("for(int i=0;i<20;++i){int swell=",
     "for(int i=0;i<0;++i){int swell="),
    ("for(int i=0;i<8;++i){int z=120+i*155;",
     "for(int i=0;i<0;++i){int z=120+i*155;"),
    ("shore(target,cam,-170,430,115,foam);island(target,cam,-170,430,115,34,green,leaf,stone);",
     "if(0)shore(target,cam,-170,430,115,foam);island(target,cam,-170,430,115,34,green,leaf,stone);"),
    ("for(int i=0;i<8;++i){int x=(i%2?1:-1)*(225+",
     "for(int i=0;i<0;++i){int x=(i%2?1:-1)*(225+"),
    ("for(int i=0;i<4;++i){int z=SCAN_Z[i];",
     "for(int i=0;i<0;++i){int z=SCAN_Z[i];"),
]

# Quay lai dung cong thuc shading phang cu trong tower(), giu nguyen hinh hoc.
FLAT_SHADING = [
    ("const uint8_t sl[4]={sun_light(s),sun_light(s+1),sun_light(s+1),sun_light(s)};quadG(t,c,m,a,b,d,e,sl);",
     "quad(t,c,m,a,b,d,e,(uint8_t)(188+((s*13+level*17)%62)));"),
    ("const uint8_t bl[4]={sun_light(s),sun_light(s+1),sun_light(s+1),sun_light(s)};quadG(t,c,band,ga,gb,gd,ge,bl);",
     "quad(t,c,band,ga,gb,gd,ge,(uint8_t)(205+(s%3)*16));"),
    ("const uint8_t cl[4]={sun_light(s),sun_light(s+1),sun_light(s+1),sun_light(s)};quadG(t,c,white,a,b,d,e,cl);",
     "quad(t,c,white,a,b,d,e,245);"),
]


def apply(src, rules, name):
    out = src
    for old, new in rules:
        if out.count(old) != 1:
            sys.exit("FAIL: %s: mong doi dung 1 lan xuat hien, thay %d: %r"
                     % (name, out.count(old), old[:60]))
        out = out.replace(old, new)
    return out


def use_dithered_sky(src, name):
    """Bien the thap phai co cung nen (sky dither) o ca hai phia so sanh."""
    if src.count(SKY_PLAIN) == 1:
        return src.replace(SKY_PLAIN, SKY_DITHER)
    if src.count(SKY_DITHER) == 1:
        return src
    sys.exit("FAIL: %s: khong tim thay dung 1 lan goi sky gradient" % name)


def read(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(HERE, "gen"))
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)

    cur = read(CUR)
    prev = read(PREV)

    now = use_dithered_sky(apply(cur, TOWER_ONLY, "scene.cpp/tower-only"), "scene.cpp")
    flat = use_dithered_sky(apply(cur, TOWER_ONLY + FLAT_SHADING, "scene.cpp/flat-shading"),
                            "scene.cpp")
    prevonly = use_dithered_sky(prev, "scene_toweronly.cpp")

    for name, text in (("scene_tower_now.cpp", now),
                       ("scene_tower_flat.cpp", flat),
                       ("scene_tower_prev.cpp", prevonly)):
        with open(os.path.join(args.out, name), "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        print("wrote", name)

    # Nguon dang bi sua song song trong working tree, nen ghi lai dau van ban de
    # biet chinh xac bien the duoc sinh tu ban nao.
    import hashlib
    hashes = {}
    for path in (CUR, PREV):
        with open(path, "rb") as f:
            hashes[os.path.relpath(path, DEMO)] = hashlib.sha256(f.read()).hexdigest()
    with open(os.path.join(args.out, "provenance.json"), "w", encoding="utf-8") as f:
        json.dump(hashes, f, indent=2, sort_keys=True)
        f.write("\n")
    print("provenance:", hashes)


if __name__ == "__main__":
    main()
