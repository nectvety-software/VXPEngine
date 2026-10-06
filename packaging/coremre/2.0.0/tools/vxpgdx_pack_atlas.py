#!/usr/bin/env python3
import argparse,json,struct,sys
from pathlib import Path

def pack(src,dst,name_bytes=24):
    root=json.loads(Path(src).read_text(encoding="utf-8"))
    regions=root.get("regions",root if isinstance(root,list) else None)
    if not isinstance(regions,list):raise ValueError("JSON must be a list or contain a 'regions' list")
    if not 1<=name_bytes<=24:raise ValueError("name_bytes must be 1..24")
    if len(regions)>65535:raise ValueError("too many regions")
    out=bytearray(b"VXAT"+bytes([1,name_bytes])+struct.pack("<H",len(regions)))
    for i,r in enumerate(regions):
        name=str(r.get("name",f"region_{i}")).encode("utf-8")[:name_bytes]
        vals=[int(r.get(k,0)) for k in ("x","y","w","h")]
        ow=int(r.get("original_w",vals[2]));oh=int(r.get("original_h",vals[3]))
        ox=int(r.get("offset_x",0));oy=int(r.get("offset_y",0))
        for v in vals+[ow,oh]:
            if not 0<=v<=65535:raise ValueError(f"region {i}: unsigned value out of range")
        for v in (ox,oy):
            if not -32768<=v<=32767:raise ValueError(f"region {i}: offset out of range")
        out+=name.ljust(name_bytes,b"\0")
        out+=struct.pack("<HHHHHHhh",*vals,ow,oh,ox,oy)
    Path(dst).write_bytes(out)
    print(f"Packed {len(regions)} atlas regions -> {dst} ({len(out)} bytes)")

def main():
    ap=argparse.ArgumentParser(description="Pack VXPGDX TextureAtlas VXAT v1 metadata")
    ap.add_argument("input",help="atlas region JSON")
    ap.add_argument("output",help="output .vxat")
    ap.add_argument("--name-bytes",type=int,default=24)
    a=ap.parse_args()
    try:pack(a.input,a.output,a.name_bytes)
    except Exception as e:
        print(f"ERROR: {e}",file=sys.stderr);return 1
    return 0
if __name__=="__main__":raise SystemExit(main())
