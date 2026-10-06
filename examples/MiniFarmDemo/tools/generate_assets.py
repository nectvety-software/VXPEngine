#!/usr/bin/env python3
import json, os, struct, zlib
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/"assets_source"
OUT=ROOT/"resources"/"gen"
OUT.mkdir(parents=True,exist_ok=True)

def read_png(path):
    data=Path(path).read_bytes()
    if data[:8]!=b"\x89PNG\r\n\x1a\n": raise ValueError(f"not png: {path}")
    p=8; w=h=ctype=depth=None; raw=b""; palette=None; trns=None
    while p<len(data):
        n=struct.unpack(">I",data[p:p+4])[0]; typ=data[p+4:p+8]; chunk=data[p+8:p+8+n]; p+=12+n
        if typ==b"IHDR":
            w,h,depth,ctype,comp,filt,inter=struct.unpack(">IIBBBBB",chunk)
            if depth!=8 or inter!=0: raise ValueError(f"unsupported PNG depth/interlace: {path}")
        elif typ==b"IDAT": raw+=chunk
        elif typ==b"PLTE": palette=[tuple(chunk[i:i+3]) for i in range(0,len(chunk),3)]
        elif typ==b"tRNS": trns=chunk
        elif typ==b"IEND": break
    bpp={6:4,2:3,3:1,0:1}.get(ctype)
    if not bpp: raise ValueError(f"unsupported PNG color type {ctype}: {path}")
    dec=zlib.decompress(raw); stride=w*bpp; rows=[]; pos=0; prev=bytearray(stride)
    for _ in range(h):
        ft=dec[pos]; pos+=1; cur=bytearray(dec[pos:pos+stride]); pos+=stride
        for x in range(stride):
            a=cur[x-bpp] if x>=bpp else 0
            b=prev[x]
            c=prev[x-bpp] if x>=bpp else 0
            if ft==1: cur[x]=(cur[x]+a)&255
            elif ft==2: cur[x]=(cur[x]+b)&255
            elif ft==3: cur[x]=(cur[x]+((a+b)//2))&255
            elif ft==4:
                pr=a+b-c; pa=abs(pr-a); pb=abs(pr-b); pc=abs(pr-c)
                pred=a if pa<=pb and pa<=pc else (b if pb<=pc else c)
                cur[x]=(cur[x]+pred)&255
            elif ft!=0: raise ValueError("bad PNG filter")
        rows.append(cur); prev=cur
    rgba=bytearray(w*h*4)
    for y,row in enumerate(rows):
        for x in range(w):
            di=(y*w+x)*4
            if ctype==6:
                si=x*4; rgba[di:di+4]=row[si:si+4]
            elif ctype==2:
                si=x*3; rgba[di:di+3]=row[si:si+3]; rgba[di+3]=255
            elif ctype==3:
                idx=row[x]; r,g,b=palette[idx]; rgba[di:di+3]=bytes((r,g,b)); rgba[di+3]=trns[idx] if trns and idx<len(trns) else 255
            else:
                v=row[x]; rgba[di:di+4]=bytes((v,v,v,255))
    return w,h,rgba

def paste(dst,dw,dh,src,sw,sh,ox,oy):
    for y in range(sh):
        if oy+y<0 or oy+y>=dh: continue
        a=((oy+y)*dw+ox)*4; b=(y*sw)*4
        dst[a:a+sw*4]=src[b:b+sw*4]

def write_vxa8(path,w,h,rgba):
    pixels=[]; alpha=[]; opaque=True
    for i in range(w*h):
        r,g,b,a=rgba[i*4:i*4+4]
        pixels.append(((r&0xF8)<<8)|((g&0xFC)<<3)|(b>>3)); alpha.append(a)
        if a!=255: opaque=False
    out=bytearray(b"VXA8")+struct.pack("<HHBBH",w,h,1 if opaque else 0,1,12)
    for p in pixels: out+=struct.pack("<H",p)
    if not opaque: out+=bytes(alpha)
    Path(path).write_bytes(out)

W,H=256,144
canvas=bytearray(W*H*4)
regions=[]

def add_region(name,x,y,w,h):
    regions.append({"name":name,"x":x,"y":y,"w":w,"h":h})

tw,th,trgba=read_png(SRC/"terrain.png")
assert (tw,th)==(160,48)
paste(canvas,W,H,trgba,tw,th,0,0)
for r in range(3):
    for c in range(10):
        idx=r*10+c+1
        add_region(f"tile_{idx:02d}",c*16,r*16,16,16)

for i in range(1,21):
    p=SRC/"player"/f"farmer_{i:02d}.png"
    w,h,rgba=read_png(p); assert (w,h)==(24,24)
    x=(i-1)%5*24; y=48+(i-1)//5*24
    paste(canvas,W,H,rgba,w,h,x,y); add_region(f"farmer_{i:02d}",x,y,24,24)

for i in range(1,9):
    p=SRC/"animals"/f"animal_{i:02d}.png"
    w,h,rgba=read_png(p); assert (w,h)==(16,16)
    x=128+(i-1)*16; y=48
    paste(canvas,W,H,rgba,w,h,x,y); add_region(f"animal_{i:02d}",x,y,16,16)

for i in range(1,9):
    p=SRC/"ui"/f"ui_{i:02d}.png"
    w,h,rgba=read_png(p); assert (w,h)==(16,16)
    x=128+(i-1)*16; y=64
    paste(canvas,W,H,rgba,w,h,x,y); add_region(f"ui_{i:02d}",x,y,16,16)

write_vxa8(OUT/"farm_atlas.vxa8",W,H,canvas)
(OUT/"farm_atlas.json").write_text(json.dumps({"regions":regions},indent=2),encoding="utf-8")

solid={3,5,8,9,10,11}
tiles=[]
for tid in range(30):
    props=[]
    if tid+1 in solid: props=[{"name":"solid","type":"bool","value":True}]
    if props: tiles.append({"id":tid,"properties":props})
tsj={"name":"terrain","tilewidth":16,"tileheight":16,"tilecount":30,"columns":10,
     "image":"terrain.png","imagewidth":160,"imageheight":48,"tiles":tiles}
(OUT/"farm_tiles.tsj").write_text(json.dumps(tsj,indent=2),encoding="utf-8")

GRASS,SOIL,WATER,PATH,STONE,WOOD,FLOWER,FENCE,HOUSE,TREE,WELL,PLANTED=range(1,13)
cells=[]
for y in range(1,61):
    for x in range(1,61):
        if y<=2: t=TREE
        elif y>=57: t=PATH
        elif x<=2 or x>=57: t=FENCE
        elif 20<=y<=35 and 15<=x<=30:
            if y in (20,35) or x in (15,30): t=FENCE
            elif 22<=y<=33 and 17<=x<=28: t=SOIL
            else: t=GRASS
        elif 40<=y<=55 and 35<=x<=52:
            if y in (40,55) or x in (35,52): t=FENCE
            elif 42<=y<=53 and 37<=x<=50: t=SOIL
            else: t=GRASS
        else: t=GRASS
        cells.append(t)
def setcell(x,y,t): cells[(y-1)*60+(x-1)]=t
for x,y in [(18,20),(18,35),(44,40),(44,55)]: setcell(x,y,PATH)
setcell(12,25,WELL)
for x,y in [(15,15),(16,15),(15,16),(16,16)]: setcell(x,y,HOUSE)
for x,y in [(5,48),(6,48),(5,49)]: setcell(x,y,STONE)
# water pond + flowers so the demo shows more tile variety
for y in range(8,13):
    for x in range(38,45):
        if (x-41)*(x-41)+(y-10)*(y-10)<=12: setcell(x,y,WATER)
for x,y in [(9,10),(10,10),(11,10),(31,18),(32,18),(33,18)]: setcell(x,y,FLOWER)

objects=[
 {"id":1,"name":"spawn","class":"PlayerSpawn","x":8*16,"y":18*16,"width":16,"height":16,"rotation":0,"visible":True},
 {"id":2,"name":"chicken","class":"Animal","x":22*16,"y":17*16,"width":16,"height":16,"rotation":0,"visible":True},
 {"id":3,"name":"cow","class":"Animal","x":25*16,"y":17*16,"width":16,"height":16,"rotation":0,"visible":True},
 {"id":4,"name":"sheep","class":"Animal","x":23*16,"y":19*16,"width":16,"height":16,"rotation":0,"visible":True}
]
tmj={"orientation":"orthogonal","width":60,"height":60,"tilewidth":16,"tileheight":16,"infinite":False,
     "tilesets":[{"firstgid":1,"source":"farm_tiles.tsj"}],
     "layers":[
       {"type":"tilelayer","name":"Ground","width":60,"height":60,"visible":True,"opacity":1.0,"data":cells},
       {"type":"objectgroup","name":"Objects","visible":True,"opacity":1.0,"objects":objects}
     ]}
(OUT/"farm.tmj").write_text(json.dumps(tmj,separators=(",",":")),encoding="utf-8")
(OUT/"atlas_bases.json").write_text(json.dumps({"terrain":0}),encoding="utf-8")
print("farm_atlas.vxa8", (OUT/"farm_atlas.vxa8").stat().st_size)
print("regions",len(regions),"map cells",len(cells))
