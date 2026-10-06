"""Authored bitmap font styles, exports and pixel-exact core preview."""
import copy,json
from pathlib import Path
from PIL import Image
from pixel_font_data import FONTS
ROLES=("title","body","numbers","hero","accent")
FIELDS=("font_id","scale","spacing","effects","color565","shadow565","outline565","highlight565")
def style(face,color,effects=1):
    return dict(font_id=face,scale=1,spacing=1,effects=effects,color565=color,shadow565=0,outline565=0x0862,highlight565=0xFFFF)
DEFAULT=dict(title=style(1,0xEDEB,5),body=style(0,0xFFB8),numbers=style(2,0xFFFF),hero=style(0,0xCF5F,3),accent=style(0,0xEDEB,5))
PRESETS={"Royal Gold":(0xEDEB,0xFFB8,0xFFFF,0xCF5F),"Frost Cyan":(0x7FFF,0xDFDF,0xBFFF,0x57F7),"Rune Violet":(0xD5FF,0xF7DF,0xC7FF,0xD5FF),"Clean Ivory":(0xFFFF,0xFFB8,0xFFFF,0xFFB8)}
def normalize(data):
    if not isinstance(data,dict):raise ValueError("Font styles must be an object")
    result=copy.deepcopy(DEFAULT)
    for role in ROLES:
        provided=data.get(role,{})
        if not isinstance(provided,dict):raise ValueError("Invalid font role")
        result[role].update({k:v for k,v in provided.items() if k in FIELDS})
        for key,(lo,hi) in dict(font_id=(0,2),scale=(1,4),spacing=(0,4),effects=(0,7),color565=(0,65535),shadow565=(0,65535),outline565=(0,65535),highlight565=(0,65535)).items():
            if type(result[role][key]) is not int or not lo<=result[role][key]<=hi:raise ValueError("Invalid "+role+" / "+key)
    return result

def preset(name):
    data=copy.deepcopy(DEFAULT);title,body,numbers,hero=PRESETS[name]
    for role,color in (("title",title),("body",body),("numbers",numbers),("hero",hero),("accent",title)):
        data[role]["color565"]=color
    if name=="Clean Ivory":
        for item in data.values():item["effects"]=1
    return data

def load(root):
    path=Path(root)/"assets/ui/font_styles.json"
    return normalize(json.loads(path.read_text(encoding="utf-8")) if path.exists() else {})

def save(root,data):
    root=Path(root);data=normalize(data)
    asset=root/"assets/ui/font_styles.json";header=root/"src/font_styles_generated.h"
    asset.parent.mkdir(parents=True,exist_ok=True);header.parent.mkdir(parents=True,exist_ok=True)
    code='#pragma once\n#include "graphics/VxpPixelFont.h"\n'
    for role in ROLES:
        code+='static const VxpeFontStyle vaelora_font_'+role+'={'+','.join(str(data[role][k]) for k in FIELDS)+'};\n'
    header.write_text(code,encoding="utf-8");asset.write_text(json.dumps(data,indent=2)+'\n',encoding="utf-8")
    return asset

def measure(value,s):
    f=FONTS[s["font_id"]]
    return max((sum(f["widths"][ord(c)-32 if 32<=ord(c)<=126 else 31] for c in line)+(len(line)-1)*s["spacing"])*s["scale"] if line else 0 for line in value[:512].split('\n'))

def rgb565(v):return ((v>>11&31)*255//31,(v>>5&63)*255//63,(v&31)*255//31)
def draw(im,x,y,value,s,clip=None):
    f=FONTS[s["font_id"]];scale=s["scale"];clip=clip or (0,0,im.width,im.height)
    def dot(px,py,v):
        for yy in range(scale):
            for xx in range(scale):
                ax,ay=px+xx,py+yy
                if 0<=ax<im.width and 0<=ay<im.height and clip[0]<=ax<clip[0]+clip[2] and clip[1]<=ay<clip[1]+clip[3]:im.putpixel((ax,ay),rgb565(v))
    for phase in range(3):
        if phase==0 and not s["effects"]&1 or phase==1 and not s["effects"]&2:continue
        px,py=x,y
        for ch in value[:512]:
            if ch=='\n':px=x;py+=(f["height"]+3)*scale;continue
            index=ord(ch)-32 if 32<=ord(ch)<=126 else 31
            rows=f["rows"][index*f["height"]:(index+1)*f["height"]]
            for yy,row in enumerate(rows):
                for xx in range(f["widths"][index]):
                    mask=1<<(f["width"]-1-xx)
                    if not row&mask:continue
                    gx,gy=px+xx*scale,py+yy*scale
                    if phase==0:dot(gx+scale,gy+scale,s["shadow565"])
                    elif phase==1:
                        for dx,dy in ((-scale,0),(scale,0),(0,-scale),(0,scale)):dot(gx+dx,gy+dy,s["outline565"])
                    else:
                        top=yy==0 or not rows[yy-1]&mask
                        dot(gx,gy,s["highlight565"] if s["effects"]&4 and top else s["color565"])
            px+=(f["widths"][index]+s["spacing"])*scale

def preview(data,size=(240,320)):
    data=normalize(data);im=Image.new("RGB",size,(12,20,29));w,h=size
    for role,y,value in (("title",22,"VAELORA DUEL"),("hero",60,"VELIN / TORVAN / NIMARA"),("body",96,"Choose your hero"),("body",115,"Prism Bolt  |  Iron Guard"),("numbers",147,"HP 1100/1100"),("numbers",166,"MP 600/600  01:29"),("accent",210,"5 START DUEL"),("body",235,"2468 MOVE / * PAUSE")):
        s=data[role];draw(im,(w-measure(value,s))//2,y,value,s)
    for face,y in enumerate((269,281,297)):
        s=style(face,0xAD55);draw(im,9,y,"Aa Bb 0123456789",s)
    return im
