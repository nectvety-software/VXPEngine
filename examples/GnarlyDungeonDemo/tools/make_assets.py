from pathlib import Path
from PIL import Image,ImageDraw
import random,json
ROOT=Path(__file__).resolve().parents[1];random.seed(7821643);header=['#pragma once','#include <stdint.h>']
for name in ['STONE','FLOOR','SKELETON','SWORD']:
    w,h=(64,96) if name=='SKELETON' else (100,160) if name=='SWORD' else (64,64)
    im=Image.new('RGBA',(w,h),(0,0,0,0));d=ImageDraw.Draw(im)
    if name in ('STONE','FLOOR'):
        im.paste('#6f6a57',(0,0,w,h))
        rows,cols=(16,32) if name=='STONE' else (32,32)
        for y in range(0,h,rows):
            for x in range(-16 if y%32 else 0,w,cols):
                v=random.randrange(82,123);d.rectangle((x+1,y+1,x+cols-2,y+rows-2),fill=(v,v-4,v-18,255),outline='#403e34');d.line((x+2,y+2,x+cols-3,y+2),fill='#9d967c')
        for i in range(150):
            x,y=random.randrange(w),random.randrange(h);d.point((x,y),fill='#565b40')
    elif name=='SKELETON':
        bone='#d1c394';hi='#f7e4ae';dark='#756b52'
        d.ellipse((22,3,43,25),fill=bone,outline=dark,width=2);d.rectangle((25,22,39,28),fill=bone)
        d.ellipse((25,10,30,15),fill='#241f27');d.ellipse((35,10,40,15),fill='#241f27');d.polygon([(32,16),(29,20),(34,20)],fill=dark)
        for x in range(27,40,4):d.line((x,23,x,28),fill=dark)
        d.line((32,29,32,62),fill=bone,width=4)
        for y in range(32,54,6):d.arc((20,y-5,44,y+8),0,180,fill=bone,width=3)
        d.line((17,31,47,31),fill=bone,width=4)
        for a,b in [((18,32),(11,51)),((11,51),(18,65)),((47,32),(51,48)),((51,48),(47,58)),((27,60),(23,77)),((23,77),(19,91)),((37,60),(42,77)),((42,77),(45,91))]:
            d.line([a,b],fill=dark,width=5);d.line([a,b],fill=bone,width=3)
        d.arc((24,53,41,68),0,180,fill=bone,width=4);d.line((15,92,24,92),fill=hi,width=4);d.line((41,92,50,92),fill=hi,width=4)
        d.polygon([(4,40),(17,36),(20,57),(12,68),(5,56)],fill='#67473a',outline='#c79647',width=2)
        d.line((50,59,56,31),fill='#c9b48d',width=4);d.line((46,56,56,59),fill='#b48b44',width=3)
    else:
        d.polygon([(20,159),(28,133),(49,120),(66,136),(77,159)],fill='#5d4032',outline='#241d24',width=3)
        d.line((38,146,65,108),fill='#4b3329',width=11)
        d.polygon([(49,111),(64,116),(99,13),(88,4)],fill='#c5c4ae',outline='#403b41',width=3)
        d.polygon([(88,4),(83,86),(64,116),(99,13)],fill='#73767a')
        d.line((39,103,76,120),fill='#c79743',width=7);d.line((41,101,77,118),fill='#f2d381',width=2)
    im.save(ROOT/'assets'/(name.lower()+'.png'));colors=[];alpha=[]
    for r,g,b,a in im.getdata():colors.append(((r>>3)<<11)|((g>>2)<<5)|(b>>3));alpha.append(a)
    header.append('static const uint16_t D_'+name+'[]={'+','.join(hex(c) for c in colors)+'};')
    if name in ('SKELETON','SWORD'):header.append('static const uint8_t D_'+name+'_A[]={'+','.join(str(a) for a in alpha)+'};')
    meta={'format':'VXPEngine Asset','format_version':2,'asset':'assets/'+name.lower()+'.png','asset_type':'Sprite / Character' if name=='SKELETON' else 'Texture','size':{'width':w,'height':h},'texture':{'render_mode':'nearest','transparent':name in ('SKELETON','SWORD'),'pixel_mode_bits':32},'art_style':{'name':'Game · Dungeon Synth','role':'sprite' if name=='SKELETON' else 'environment','runtime_preset':'VXPE_ARTSTYLE_DUNGEON_SYNTH'}}
    (ROOT/'assets'/(name.lower()+'.asset.dtfe')).write_text(json.dumps(meta,indent=2))
(ROOT/'src/assets.h').write_text('\n'.join(header))
print('Generated original dungeon stone, floor, skeleton and sword assets')
