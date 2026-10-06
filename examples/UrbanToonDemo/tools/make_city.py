"""Generate original shop signs and pavement textures; no external artwork."""
from pathlib import Path
from PIL import Image, ImageDraw
import random
ROOT=Path(__file__).resolve().parents[1]
random.seed(39)
header=['#pragma once','#include <stdint.h>']
for name in ['BRICK','ROAD','SHOP','OFFICE','SIGN_RADIO','SIGN_CAFE','SIGN_SKATE']:
    size=128 if name in ('SHOP','OFFICE') else 64
    im=Image.new('RGB',(size,size),{'BRICK':'#b58174','ROAD':'#91918b','SHOP':'#e9dfbe','OFFICE':'#d5d8cd','SIGN_RADIO':'#ce4227','SIGN_CAFE':'#167e86','SIGN_SKATE':'#592469'}[name]);d=ImageDraw.Draw(im)
    if name=='BRICK':
        for y in range(0,size,8):
            d.line((0,y,size-1,y),fill='#805e57')
            for x in range(-8 if y%16 else 0,size,16):d.line((x,y,x,y+8),fill='#805e57')
    elif name=='ROAD':
        for i in range(600):
            x,y=random.randrange(size),random.randrange(size);v=random.randrange(126,154);d.point((x,y),fill=(v,v,v-5))
    elif name.startswith('SIGN'):
        d.rectangle((2,2,61,61),outline='#f5d577',width=2)
        word=name.split('_')[1]
        for i,ch in enumerate(word):d.text((27,6+i*9),ch,fill='#fff6d4')
        d.line((8,8,8,55),fill='#e7e39f',width=2)
    else:
        for y in range(3,88,28):
            d.rectangle((0,y+25,127,y+27),fill='#959c90')
            for x in range(6,128,30):
                d.rectangle((x,y,x+20,y+19),fill='#2a3b46');d.rectangle((x+2,y+2,x+18,y+17),fill='#6c98a2')
                d.polygon([(x+2,y+2),(x+18,y+2),(x+2,y+14)],fill='#9bb4b3')
                d.line((x+10,y+2,x+10,y+17),fill='#d5d7bd')
                if name=='SHOP':
                    d.rectangle((x-2,y+17,x+22,y+21),fill='#acb0a0')
                    for k in range(x,x+22,4):d.line((k,y+17,k,y+21),fill='#485655')
        d.rectangle((2,96,125,127),fill='#273b43')
        for x in range(6,125,23):
            d.rectangle((x,99,x+19,126),fill='#60888d');d.line((x+4,100,x+4,125),fill='#bfc8b4')
        d.rectangle((0,87,127,98),fill='#ce482c' if name=='SHOP' else '#147c80')
        d.text((15,87),'RADIO / RECORDS' if name=='SHOP' else 'CAFE  /  STUDIO',fill='#fff0b6')
    im.save(ROOT/'assets'/('city_'+name.lower()+'.png'))
    colors=[((r>>3)<<11)|((g>>2)<<5)|(b>>3) for r,g,b in im.getdata()]
    header.append('static const uint16_t CITY_'+name+'[]={'+','.join(hex(c) for c in colors)+'};')
(ROOT/'src/city.h').write_text('\n'.join(header))
print('Generated 7 original city textures')
