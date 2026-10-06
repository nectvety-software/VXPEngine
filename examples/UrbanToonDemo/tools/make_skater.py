"""Original code-drawn skater artwork for the core Toon3D demo."""
from pathlib import Path
from PIL import Image,ImageDraw
import json
ROOT=Path(__file__).resolve().parents[1]
(ROOT/'assets').mkdir(exist_ok=True)
images=[]
ink='#0d1620'
for frame in range(3):
    im=Image.new('RGBA',(56,96));d=ImageDraw.Draw(im)
    lean=frame-1
    d.polygon([(22,46),(29,47),(27+lean*2,79),(17+lean*3,84),(15,79)],fill='#26353d',outline=ink,width=2)
    d.polygon([(29,47),(36,45),(43-lean*3,77),(38,84),(31,80)],fill='#26353d',outline=ink,width=2)
    d.polygon([(14,24),(5,34),(2,49),(8,52),(14,38),(22,31)],fill='#ebc294',outline=ink,width=2)
    d.polygon([(37,24),(47,32),(53,43),(49,49),(43,41),(33,31)],fill='#ebc294',outline=ink,width=2)
    d.polygon([(15,22),(23,18),(35,19),(42,27),(36,48),(27,54),(15,46)],fill='#ffd427',outline=ink,width=2)
    d.polygon([(34,24),(41,27),(35,47),(28,51),(26,38)],fill='#e6a91d')
    d.rectangle((22,26,33,37),fill=ink);d.polygon([(24,28),(30,28),(28,34),(24,35)],fill='#12c6bd')
    d.rectangle((23,13,33,22),fill='#ebc294');d.ellipse((20,3,35,19),fill='#ebc294',outline=ink,width=2)
    d.pieslice((18,0,37,18),180,360,fill='#1262bb',outline=ink,width=2)
    d.rectangle((18,7,38,11),fill='#3a94c7',outline=ink,width=1)
    d.rectangle((18,12,22,19),fill='#0d1620');d.rectangle((34,12,38,19),fill='#0d1620')
    d.polygon([(14+lean*3,78),(23+lean*2,78),(29+lean*2,88),(14+lean*3,90)],fill='#64e496',outline=ink,width=2)
    d.polygon([(32,78),(39,78),(45,85),(45,91),(30,90)],fill='#12c6bd',outline=ink,width=2)
    for xx in (17+lean*3,25+lean*2,33,41):d.ellipse((xx-2,88,xx+2,94),fill='#e52d8a',outline=ink)
    d.line((17+lean*3,82,24+lean*2,84),fill='#ebead5',width=2);d.line((33,82,40,84),fill='#ebead5',width=2)
    images.append(im);im.save(ROOT/'assets'/f'skater_{frame}.png')
header=['#pragma once','#include <stdint.h>']
for i,im in enumerate(images):
    colors=[];alpha=[]
    for y in range(im.height):
        for x in range(im.width):
            r,g,b,a=im.getpixel((x,y));colors.append(((r>>3)<<11)|((g>>2)<<5)|(b>>3));alpha.append(a)
    header.append('static const uint16_t SKATER_'+str(i)+'[]={'+','.join(hex(c) for c in colors)+'};')
    header.append('static const uint8_t SKATER_ALPHA_'+str(i)+'[]={'+','.join(str(c) for c in alpha)+'};')
facade=Image.new('RGB',(64,64),'#cdd5ca');d=ImageDraw.Draw(facade)
for y in range(0,64,16):
    d.rectangle((0,y,63,y+2),fill='#7c8581')
    for x in range(4,64,20):
        d.rectangle((x,y+5,x+13,y+13),fill='#26353d');d.rectangle((x+1,y+6,x+12,y+12),fill='#3a94c7')
        d.line((x+5,y+6,x+5,y+12),fill='#b1b4a4');d.line((x+2,y+6,x+6,y+6),fill='#ebead5')
graffiti=Image.new('RGB',(64,64),'#ebead5');d=ImageDraw.Draw(graffiti)
d.rectangle((0,2,63,12),fill='#26353d');d.rectangle((0,13,63,15),fill='#12c6bd')
d.polygon([(3,46),(12,23),(22,25),(13,39),(29,32),(34,20),(42,24),(35,43),(48,27),(59,31),(56,52),(25,56)],fill='#0d1620')
d.polygon([(8,46),(15,29),(18,29),(13,44),(31,37),(35,26),(38,27),(32,48),(50,33),(54,34),(52,47),(27,51)],fill='#12c6bd')
d.line((4,57,55,54),fill='#e52d8a',width=4);d.line((11,45,36,35),fill='#3a94c7',width=3)
for name,texture in [('FACADE',facade),('GRAFFITI',graffiti)]:
    texture.save(ROOT/'assets'/('city_'+name.lower()+'.png'))
    colors=[]
    for y in range(64):
        for x in range(64):
            r,g,b=texture.getpixel((x,y));colors.append(((r>>3)<<11)|((g>>2)<<5)|(b>>3))
    header.append('static const uint16_t CITY_'+name+'[]={'+','.join(hex(c) for c in colors)+'};')
(ROOT/'src/skater.h').write_text('\n'.join(header)+'\n',encoding='utf-8')
atlas=Image.new('RGBA',(168,96))
for i,im in enumerate(images):atlas.paste(im,(i*56,0))
atlas.save(ROOT/'assets/skater_legacy_atlas.png')
descriptor={'format':'VXPEngine Animation','format_version':2,'extension':'.ani..dtfe','asset':'assets/skater_legacy_atlas.png','texture':'assets/skater_legacy_atlas.png','source_mode':'atlas_frames','asset_kind':'character','package':'atlas+descriptor','preview_background':'checker',
 'animation':{'name':'skater_legacy_roll','fps':6,'loop':True,'frame_count':3,'source_mode':'atlas_frames','asset_kind':'character','selected_indices':[0,1,2]},
 'frames':[{'name':f'roll_{i}','x':i*56,'y':0,'width':56,'height':96,'duration_ms':167,'source_index':i} for i in range(3)]}
(ROOT/'assets/skater_legacy_roll.ani..dtfe').write_text(json.dumps(descriptor,indent=2),encoding='utf-8')
metadata={'format':'VXPEngine Asset','format_version':2,'asset':'assets/skater_legacy_atlas.png','asset_type':'Sprite / Character',
 'size':{'width':168,'height':96},'texture':{'pixels_per_unit':1,'render_mode':'nearest','transparent':True,'pixel_mode_bits':32},
 'grid':{'width':56,'height':96,'margin':0,'spacing':0},'frames':descriptor['frames'],
 'animation':{**descriptor['animation'],'descriptor':'assets/skater_legacy_roll.ani..dtfe'}}
metadata['art_style']={'name':'Game · Urban Toon','role':'sprite','runtime_preset':'VXPE_ARTSTYLE_URBAN_TOON'}
(ROOT/'assets/skater_legacy_atlas.asset.dtfe').write_text(json.dumps(metadata,indent=2),encoding='utf-8')
print('Generated original skater, 3-frame atlas, animation descriptor and embedded A8 assets')
