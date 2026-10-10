"""Generate original shop signs and pavement textures; no external artwork."""
from pathlib import Path
from PIL import Image, ImageDraw
import random
ROOT=Path(__file__).resolve().parents[1]
random.seed(39)
header=['#pragma once','#include <stdint.h>']
for name in ['BRICK','ROAD','SHOP','OFFICE','SIGN_RADIO','SIGN_CAFE','SIGN_SKATE']:
    size=128 if name in ('SHOP','OFFICE') else 64
    im=Image.new('RGB',(size,size),{'BRICK':'#66645a','ROAD':'#424d53','SHOP':'#899181','OFFICE':'#667c78','SIGN_RADIO':'#a07149','SIGN_CAFE':'#436e68','SIGN_SKATE':'#675d57'}[name]);d=ImageDraw.Draw(im)
    if name=='BRICK':
        for y in range(0,size,8):
            d.line((0,y,size-1,y),fill='#444d4c')
            for x in range(-8 if y%16 else 0,size,16):d.line((x,y,x,y+8),fill='#444d4c')
    elif name=='ROAD':
        for i in range(320):
            x,y=random.randrange(size),random.randrange(size);v=random.randrange(58,76);d.point((x,y),fill=(v-8,v,v+5))
    elif name.startswith('SIGN'):
        d.rectangle((2,2,61,61),outline='#f5d577',width=2)
        word=name.split('_')[1]
        for i,ch in enumerate(word):d.text((27,6+i*9),ch,fill='#fff6d4')
        d.line((8,8,8,55),fill='#e7e39f',width=2)
    else:
        for y in range(3,88,28):
            d.rectangle((0,y+25,127,y+27),fill='#444f50')
            for x in range(6,128,30):
                d.rectangle((x,y,x+20,y+19),fill='#1c2b30');d.rectangle((x+2,y+2,x+18,y+17),fill='#45625f')
                if (x//30+y//28)%3==0:d.rectangle((x+2,y+2,x+18,y+17),fill='#c1ac78')
                d.polygon([(x+2,y+2),(x+18,y+2),(x+2,y+14)],fill='#829a84')
                d.line((x+10,y+2,x+10,y+17),fill='#a6ad92')
                if name=='SHOP':
                    d.rectangle((x-2,y+17,x+22,y+21),fill='#acb0a0')
                    for k in range(x,x+22,4):d.line((k,y+17,k,y+21),fill='#485655')
        d.rectangle((2,96,125,127),fill='#273b43')
        for x in range(6,125,23):
            d.rectangle((x,99,x+19,126),fill='#a78d61');d.line((x+4,100,x+4,125),fill='#bfc8b4')
        d.rectangle((0,87,127,98),fill='#775a40' if name=='SHOP' else '#365b58')
        d.text((15,87),'RADIO / RECORDS' if name=='SHOP' else 'CAFE  /  STUDIO',fill='#fff0b6')
    im.save(ROOT/'assets'/('city_'+name.lower()+'.png'))
    colors=[((r>>3)<<11)|((g>>2)<<5)|(b>>3) for r,g,b in im.getdata()]
    header.append('static const uint16_t CITY_'+name+'[]={'+','.join(hex(c) for c in colors)+'};')
(ROOT/'src/city.h').write_text('\n'.join(header))
print('Generated 7 original city textures')
