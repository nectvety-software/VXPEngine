#!/usr/bin/env python3
import argparse, json, struct, sys
from pathlib import Path

HFLIP=0x80000000
VFLIP=0x40000000
DFLIP=0x20000000
EXTRA_ROT=0x10000000
GID_MASK=0x0FFFFFFF

FLAG_MAP={
    "solid":1, "collision":1, "blocked":1,
    "trigger":2,
    "damage":4, "hazard":4,
    "water":8,
    "ladder":16,
}

def u16(v):
    if not 0 <= int(v) <= 0xFFFF:
        raise ValueError(f"value out of u16 range: {v}")
    return int(v)

def s16(v):
    v=int(round(float(v)))
    if not -32768 <= v <= 32767:
        raise ValueError(f"value out of s16 range: {v}")
    return v

def rgb565(value):
    if not value:
        return 0xFFFF
    s=str(value).lstrip("#")
    if len(s)==8: s=s[2:]
    if len(s)!=6: return 0xFFFF
    r,g,b=int(s[0:2],16),int(s[2:4],16),int(s[4:6],16)
    return ((r&0xF8)<<8)|((g&0xFC)<<3)|(b>>3)

def props_dict(obj):
    out={}
    for p in obj.get("properties",[]) or []:
        out[p.get("name","")]=p.get("value")
    return out

def load_tileset(map_path, entry):
    if "source" in entry:
        p=(map_path.parent/entry["source"]).resolve()
        data=json.loads(p.read_text(encoding="utf-8"))
        key=data.get("name") or p.stem
    else:
        data=entry
        key=data.get("name") or f"tileset_{entry.get('firstgid',0)}"
    return key,data

def tilecount_of(ts):
    n=ts.get("tilecount")
    if n is not None:return int(n)
    cols=int(ts.get("columns") or 0)
    iw=int(ts.get("imagewidth") or 0);ih=int(ts.get("imageheight") or 0)
    tw=int(ts.get("tilewidth") or 0);th=int(ts.get("tileheight") or 0)
    spacing=int(ts.get("spacing") or 0);margin=int(ts.get("margin") or 0)
    if cols and iw and ih and tw and th:
        rows=max(0,(ih-2*margin+spacing)//(th+spacing))
        return cols*rows
    raise ValueError(f"tileset {ts.get('name','?')} has no tilecount")

def flatten_layers(layers, ox=0.0, oy=0.0, px=1.0, py=1.0, opacity=1.0, prefix=""):
    out=[]
    for layer in layers:
        name=layer.get("name","")
        full=f"{prefix}/{name}" if prefix and name else (name or prefix)
        lox=ox+float(layer.get("offsetx",0) or 0)
        loy=oy+float(layer.get("offsety",0) or 0)
        lpx=px*float(layer.get("parallaxx",1) or 1)
        lpy=py*float(layer.get("parallaxy",1) or 1)
        lop=opacity*float(layer.get("opacity",1) or 1)
        if layer.get("type")=="group":
            out.extend(flatten_layers(layer.get("layers",[]),lox,loy,lpx,lpy,lop,full))
        else:
            item=dict(layer)
            item["_vx_name"]=full[:12]
            item["_vx_ox"]=lox;item["_vx_oy"]=loy
            item["_vx_px"]=lpx;item["_vx_py"]=lpy
            item["_vx_opacity"]=lop
            out.append(item)
    return out

def encode_cell(raw):
    raw=int(raw)
    if raw==0:return 0xFFFF
    gid=raw&GID_MASK
    if gid>0x1FFE:
        raise ValueError(f"gid {gid} exceeds VXTM v3 usable cell id range (1..8190)")
    v=gid
    if raw&HFLIP:v|=0x8000
    if raw&VFLIP:v|=0x4000
    if raw&DFLIP:v|=0x2000
    return v

def atlas_bases(map_path, entries, atlas_map_path):
    mapping={}
    if atlas_map_path:
        mapping=json.loads(Path(atlas_map_path).read_text(encoding="utf-8"))
    result=[];cursor=0
    for e in entries:
        key,ts=load_tileset(map_path,e)
        count=tilecount_of(ts)
        base=int(mapping.get(key,cursor))
        result.append((e,key,ts,count,base))
        cursor=max(cursor,base+count)
    return result

def tile_flags_and_anims(firstgid,ts,count):
    flags=[0]*count;anims=[]
    for tile in ts.get("tiles",[]) or []:
        tid=int(tile.get("id",0))
        if not 0<=tid<count:continue
        p=props_dict(tile);f=0
        for k,v in p.items():
            lk=k.lower()
            if lk=="vxpe_flags":
                f|=int(v)&0xFF
            elif lk in FLAG_MAP and bool(v):
                f|=FLAG_MAP[lk]
        flags[tid]=f
        frames=[]
        for fr in tile.get("animation",[]) or []:
            frames.append((firstgid+int(fr["tileid"]),max(1,int(fr.get("duration",100)))))
        if frames:anims.append((firstgid+tid,frames))
    return flags,anims

def pack_map(src,out_path,atlas_map=None):
    src=Path(src).resolve()
    root=json.loads(src.read_text(encoding="utf-8"))
    if root.get("infinite"):
        raise ValueError("infinite/chunked Tiled maps are not supported; export a finite TMJ for MRE")
    orient=root.get("orientation","orthogonal")
    if orient not in ("orthogonal","isometric"):
        raise ValueError(f"unsupported orientation: {orient}")
    mw,mh=int(root.get("width",0)),int(root.get("height",0))
    tw,th=int(root.get("tilewidth",0)),int(root.get("tileheight",0))
    if min(mw,mh,tw,th)<=0:raise ValueError("map width/height/tile size must be > 0")

    ts_entries=root.get("tilesets",[]) or []
    ts_info=atlas_bases(src,ts_entries,atlas_map)
    tilesets=[];animations=[]
    for entry,key,ts,count,base in ts_info:
        first=int(entry.get("firstgid",ts.get("firstgid",0)))
        if first<=0:raise ValueError(f"tileset {key} missing firstgid")
        flags,anims=tile_flags_and_anims(first,ts,count)
        tilesets.append((first,count,base,flags))
        animations.extend(anims)

    flat=flatten_layers(root.get("layers",[]))
    tile_layers=[];object_layers=[];total_objects=0
    z=0
    for layer in flat:
        typ=layer.get("type")
        if typ=="tilelayer":
            data=layer.get("data")
            if not isinstance(data,list) or len(data)!=mw*mh:
                raise ValueError(f"tile layer {layer.get('name')} must contain an uncompressed JSON data array of {mw*mh} gids")
            cells=[encode_cell(v) for v in data]
            tint=rgb565(layer.get("tintcolor"))
            tile_layers.append((layer,z,cells,tint));z+=1
        elif typ=="objectgroup":
            objs=layer.get("objects",[]) or []
            encoded=[]
            for o in objs:
                flags=1 if o.get("visible",True) else 0
                if o.get("point"):flags|=2
                if o.get("ellipse"):flags|=4
                name=str(o.get("name","")).encode("utf-8")[:13]
                typn=str(o.get("class") or o.get("type") or "").encode("utf-8")[:11]
                encoded.append((u16(o.get("id",0)),u16(flags),s16(o.get("x",0)),s16(o.get("y",0)),
                                s16(o.get("width",0)),s16(o.get("height",0)),s16(o.get("rotation",0)),name,typn))
            total_objects+=len(encoded)
            object_layers.append((layer,z,encoded));z+=1

    if len(tile_layers)>255 or len(tilesets)>255 or len(object_layers)>255 or len(animations)>255 or total_objects>65535:
        raise ValueError("map exceeds VXTM v3 count limits")

    out=bytearray()
    out+=b"VXTM"
    out+=bytes([3,0 if orient=="orthogonal" else 1,len(tile_layers),len(tilesets)])
    out+=struct.pack("<HHHH",mw,mh,tw,th)
    out+=bytes([len(object_layers),len(animations)])
    out+=struct.pack("<H",total_objects)
    out+=b"\0\0\0\0"

    for first,count,base,flags in tilesets:
        has=1 if any(flags) else 0
        out+=struct.pack("<HHHBB",u16(first),u16(count),u16(base),has,0)
        if has:
            out+=bytes(flags)
            if len(out)&1:out+=b"\0"

    for layer,z,cells,tint in tile_layers:
        name=layer["_vx_name"].encode("utf-8")[:12].ljust(12,b"\0")
        vis=1 if layer.get("visible",True) else 0
        op=max(0,min(255,round(layer["_vx_opacity"]*255)))
        px=max(0,min(65535,round(layer["_vx_px"]*256)))
        py=max(0,min(65535,round(layer["_vx_py"]*256)))
        out+=name+bytes([vis,op])
        out+=struct.pack("<hhhHHH",s16(z),s16(layer["_vx_ox"]),s16(layer["_vx_oy"]),u16(px),u16(py),u16(tint))
        out+=b"\0\0"
        for c in cells:out+=struct.pack("<H",c)

    for layer,z,objs in object_layers:
        name=layer["_vx_name"].encode("utf-8")[:12].ljust(12,b"\0")
        vis=1 if layer.get("visible",True) else 0
        op=max(0,min(255,round(layer["_vx_opacity"]*255)))
        out+=name+bytes([vis,op])+struct.pack("<hH",s16(z),len(objs))+b"\0\0"
        for oid,flags,x,y,w,h,rot,nameb,typeb in objs:
            out+=struct.pack("<HHhhhhh",oid,flags,x,y,w,h,rot)
            out+=nameb.ljust(14,b"\0")+typeb.ljust(12,b"\0")

    for base,frames in animations:
        out+=struct.pack("<HH",u16(base),u16(len(frames)))
        for gid,dur in frames:out+=struct.pack("<HH",u16(gid),u16(dur))

    Path(out_path).write_bytes(out)
    print(f"Packed {src.name}: {len(tile_layers)} tile layers, {len(object_layers)} object layers, "
          f"{len(tilesets)} tilesets, {len(animations)} animations, {total_objects} objects -> {out_path} ({len(out)} bytes)")

def main():
    ap=argparse.ArgumentParser(description="Pack finite Tiled JSON/TMJ maps into VXPGDX VXTM v3")
    ap.add_argument("input",help=".tmj/.json map exported by Tiled")
    ap.add_argument("output",help="output .vxtm")
    ap.add_argument("--atlas-map",help="optional JSON object mapping tileset name to atlas first-region index")
    args=ap.parse_args()
    try:pack_map(args.input,args.output,args.atlas_map)
    except Exception as e:
        print(f"ERROR: {e}",file=sys.stderr);return 1
    return 0

if __name__=="__main__":
    raise SystemExit(main())
