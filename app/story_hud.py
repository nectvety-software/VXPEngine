"""Project-owned Story HUD configuration and deterministic pixel preview."""
import json
from pathlib import Path
from PIL import Image, ImageDraw
DEFAULT = dict(title="EMBER CHRONICLE", gold=0xEDEB, ivory=0xFFB8,
    muted=0xAD55, panel=0x1083, border=0x6288, keycap=0x2945, alpha=238,
    keys=["2468","5","7","0","9","1"], labels=["MOVE","TALK","CAST","SCENE","PAUSE","RESET"])
FONT = [[0, 0, 0, 0, 0, 0, 0], [4, 4, 4, 4, 4, 0, 4], [10, 10, 10, 0, 0, 0, 0], [10, 10, 31, 10, 31, 10, 10], [4, 15, 20, 14, 5, 30, 4], [24, 25, 2, 4, 8, 19, 3], [12, 18, 20, 8, 21, 18, 13], [4, 4, 8, 0, 0, 0, 0], [2, 4, 8, 8, 8, 4, 2], [8, 4, 2, 2, 2, 4, 8], [0, 4, 21, 14, 21, 4, 0], [0, 4, 4, 31, 4, 4, 0], [0, 0, 0, 0, 4, 4, 8], [0, 0, 0, 31, 0, 0, 0], [0, 0, 0, 0, 0, 12, 12], [0, 1, 2, 4, 8, 16, 0], [14, 17, 19, 21, 25, 17, 14], [4, 12, 4, 4, 4, 4, 14], [14, 17, 1, 2, 4, 8, 31], [14, 17, 1, 6, 1, 17, 14], [2, 6, 10, 18, 31, 2, 2], [31, 16, 16, 30, 1, 1, 30], [6, 8, 16, 30, 17, 17, 14], [31, 1, 2, 4, 8, 8, 8], [14, 17, 17, 14, 17, 17, 14], [14, 17, 17, 15, 1, 2, 12], [0, 12, 12, 0, 12, 12, 0], [0, 12, 12, 0, 12, 4, 8], [2, 4, 8, 16, 8, 4, 2], [0, 0, 31, 0, 31, 0, 0], [8, 4, 2, 1, 2, 4, 8], [14, 17, 1, 2, 4, 0, 4], [14, 17, 23, 21, 23, 16, 15], [4, 10, 17, 17, 31, 17, 17], [30, 17, 17, 30, 17, 17, 30], [14, 17, 16, 16, 16, 17, 14], [28, 18, 17, 17, 17, 18, 28], [31, 16, 16, 30, 16, 16, 31], [31, 16, 16, 30, 16, 16, 16], [14, 17, 16, 23, 17, 17, 15], [17, 17, 17, 31, 17, 17, 17], [14, 4, 4, 4, 4, 4, 14], [7, 2, 2, 2, 2, 18, 12], [17, 18, 20, 24, 20, 18, 17], [16, 16, 16, 16, 16, 16, 31], [17, 27, 21, 21, 17, 17, 17], [17, 17, 25, 21, 19, 17, 17], [14, 17, 17, 17, 17, 17, 14], [30, 17, 17, 30, 16, 16, 16], [14, 17, 17, 17, 21, 18, 13], [30, 17, 17, 30, 20, 18, 17], [15, 16, 16, 14, 1, 1, 30], [31, 4, 4, 4, 4, 4, 4], [17, 17, 17, 17, 17, 17, 14], [17, 17, 17, 17, 17, 10, 4], [17, 17, 17, 21, 21, 27, 17], [17, 17, 10, 4, 10, 17, 17], [17, 17, 10, 4, 4, 4, 4], [31, 1, 2, 4, 8, 16, 31], [14, 8, 8, 8, 8, 8, 14], [0, 16, 8, 4, 2, 1, 0], [14, 2, 2, 2, 2, 2, 14], [4, 10, 17, 0, 0, 0, 0], [0, 0, 0, 0, 0, 0, 31], [8, 4, 2, 0, 0, 0, 0], [0, 0, 14, 1, 15, 17, 15], [16, 16, 30, 17, 17, 17, 30], [0, 0, 15, 16, 16, 16, 15], [1, 1, 15, 17, 17, 17, 15], [0, 0, 14, 17, 31, 16, 14], [6, 8, 30, 8, 8, 8, 8], [0, 15, 17, 17, 15, 1, 14], [16, 16, 22, 25, 17, 17, 17], [4, 0, 12, 4, 4, 4, 14], [2, 0, 6, 2, 2, 18, 12], [16, 16, 18, 20, 24, 20, 18], [12, 4, 4, 4, 4, 4, 14], [0, 0, 26, 21, 21, 17, 17], [0, 0, 22, 25, 17, 17, 17], [0, 0, 14, 17, 17, 17, 14], [0, 0, 30, 17, 17, 30, 16], [0, 0, 15, 17, 17, 15, 1], [0, 0, 22, 25, 16, 16, 16], [0, 0, 15, 16, 14, 1, 30], [8, 8, 30, 8, 8, 8, 7], [0, 0, 17, 17, 17, 17, 15], [0, 0, 17, 17, 17, 10, 4], [0, 0, 17, 17, 21, 21, 10], [0, 0, 17, 10, 4, 10, 17], [0, 0, 17, 17, 15, 1, 14], [0, 0, 31, 2, 4, 8, 31], [2, 4, 4, 8, 4, 4, 2], [4, 4, 4, 4, 4, 4, 4], [8, 4, 4, 2, 4, 4, 8], [0, 0, 8, 21, 2, 0, 0]]

def normalize(data):
    result = dict(DEFAULT)
    result.update({k: v for k,v in data.items() if k in DEFAULT})
    for k in ("title",):
        result[k] = str(result[k])[:48]
        if any(ord(c)<32 or ord(c)>126 for c in result[k]):
            raise ValueError("Runtime font supports printable ASCII only")
    for k in ("keys","labels"):
        values=result[k]
        if not isinstance(values,list) or len(values)!=6: raise ValueError("Six controls required")
        result[k]=[str(v)[:4 if k=="keys" else 12] for v in values]
        if any(ord(c)<32 or ord(c)>126 for v in result[k] for c in v): raise ValueError("Controls require ASCII")
    for k in ("gold","ivory","muted","panel","border","keycap","alpha"):
        result[k]=int(result[k])
        if not 0<=result[k]<=(255 if k=="alpha" else 65535): raise ValueError("Invalid color/opacity")
    return result

def save(root,data):
    root=Path(root); data=normalize(data)
    asset=root/"assets/ui/story_hud.json"; header=root/"src/story_hud_generated.h"
    asset.parent.mkdir(parents=True,exist_ok=True); header.parent.mkdir(parents=True,exist_ok=True)
    quote=lambda text: json.dumps(text,ensure_ascii=True)
    code='#pragma once\n#include "graphics/VxpStory2D.h"\n'
    code+='static const VxpeStoryHudStyle story_hud_style={'+','.join(str(data[k]) for k in ("gold","ivory","muted","panel","border","keycap","alpha"))+'};\n'
    code+='static const char* const story_hud_title='+quote(data["title"])+ ';\n'
    for k in ("keys","labels"):
        code+='static const char* const story_hud_'+k+'[6]={'+','.join(map(quote,data[k]))+'};\n'
    header.write_text(code,encoding="utf-8")
    asset.write_text(json.dumps(data,indent=2)+'\n',encoding="utf-8")
    return asset

def load(root):
    p=Path(root)/"assets/ui/story_hud.json"
    return normalize(json.loads(p.read_text(encoding="utf-8")) if p.exists() else {})

def preview(data,size=(240,320),background=None):
    c=normalize(data); w,h=size
    im=background.convert("RGB").resize(size,Image.Resampling.NEAREST) if background else Image.new("RGB",size,(25,29,35))
    def color(v): return ((v>>11&31)*255//31,(v>>5&63)*255//63,(v&31)*255//31)
    draw=ImageDraw.Draw(im)
    def rect(x,y,width,height,v):
        if width>0 and height>0: draw.rectangle((x,y,x+width-1,y+height-1),fill=color(v))
    def text(x,y,value,v,columns=48):
        for i,ch in enumerate(value[:max(0,min(48,columns))]):
            bits=FONT[ord(ch)-32 if 32<=ord(ch)<=126 else 31]
            for yy,row in enumerate(bits):
                for xx in range(5):
                    if row&(1<<(4-xx)) and 0<=x+i*6+xx<w and 0<=y+yy<h: im.putpixel((x+i*6+xx,y+yy),color(v))
    overlay=Image.new("RGBA",size,(0,0,0,0)); od=ImageDraw.Draw(overlay)
    for box in ((0,0,w-1,43),(0,h-26,w-1,h-1)): od.rectangle(box,fill=(*color(c["panel"]),c["alpha"]))
    im=Image.alpha_composite(im.convert("RGBA"),overlay).convert("RGB"); draw=ImageDraw.Draw(im)
    title=c["title"][:(w-48)//6]; left=(w-len(title)*6)//2
    rect(12,6,left-24,1,c["gold"]);rect(w-left+12,6,left-24,1,c["gold"])
    text(left,3,title,c["gold"])
    location="EMBERFALL SQUARE"; text((w-len(location)*6)//2,16,location,c["ivory"])
    columns=(w-30)//12; text(12,31,"III / EMBERFALL",c["muted"],columns)
    status="SEALS 0/3"; text(w-12-len(status)*6,31,status,c["gold"],columns)
    rect(0,43,w,1,c["border"]);rect(0,h-26,w,1,c["border"])
    for i,(key,label) in enumerate(zip(c["keys"],c["labels"])):
        cell=(w-6)//3; x=6+i%3*cell; y=h-23+i//3*12; kw=len(key)*6+4
        rect(x,y,kw,9,c["keycap"]);text(x+2,y+1,key,c["gold"],4)
        text(x+kw+4,y+1,label,c["muted"],(cell-kw-10)//6)
    return im
