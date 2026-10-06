"""Rebuild editable pixel art into a four-direction VXA8 actor atlas."""
from pathlib import Path
import json
import re
import struct
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QImage, QPainter

ROOT=Path(__file__).resolve().parents[1]
source=(ROOT/'src/hero.h').read_text()
rows=re.findall(r'"([^"\n]+)"',source)
colors=[int(v,16) for v in re.findall(r'0x([0-9a-f]{6})',source)]
indices={'o':0,'B':1,'L':2,'W':3,'P':4,'H':5,'S':6,'E':8,'R':9,'C':10,'T':11,'K':8,'D':12,'G':13,'F':14}
assert len(rows)==30 and all(len(row)==20 for row in rows)
front=list(rows)
front[5:14]=[
    '...oBBWWWWWWWBo.....','...oBLWWHWHWWLo.....',
    '...oBLWHWWWHWLo.....','...oBLWSSSSSWLo.....',
    '....oWSSESESWo......','.....oSSSSSSo.......',
    '......oSSSSo........','......oRSSRo........',
    '.....oRRRRRRo.......']
front[16:20]=['...oSCRTTTRCSo......','...oSCRTTTRCSo......',
              '...oSSRCTCRSSo......','....ooRCTCRoo.......']
back=list(front)
back[5:14]=['...oBBLLLLLBBBo.....','...oBLLLLLLLLBo.....',
    '...oBLLLLLLLLBo.....','...oBBLLLLLLBBo.....',
    '....oBBWWWWBBo......','.....oWWWWWWo.......',
    '......oWWWWo........','......oRRRRo........',
    '.....oRRRRRRo.......']
back[16:20]=['...oCRRTTTRRCo......','...oCRRKTKRRCo......',
             '...oCRRKKKRRCo......','....oCRRRRRCo.......']
for grid in (front,back):assert all(len(row)==20 for row in grid)

def image(grid):
    im=QImage(20,30,QImage.Format.Format_ARGB32);im.fill(Qt.GlobalColor.transparent)
    for y,row in enumerate(grid):
        for x,key in enumerate(row):
            if key!='.':im.setPixelColor(x,y,QColor.fromRgb(colors[indices[key]]))
    return im

east=image(rows);bases=[image(back),east,image(front),east.flipped(Qt.Orientation.Horizontal)]
atlas=QImage(160,120,QImage.Format.Format_ARGB32);atlas.fill(Qt.GlobalColor.transparent)
frames=[]
for direction,base in enumerate(bases):
    for frame in range(8):
        im=base.copy()
        if 1<=frame<=4:
            im.fill(Qt.GlobalColor.transparent)
            # Move leg silhouettes independently, with a one-pixel body bob.
            for y in range(30):
                for x in range(20):
                    c=base.pixelColor(x,y)
                    if not c.alpha():continue
                    offset=([0,1,0,-1][frame-1] * (1 if x<10 else -1)) if y>=23 else (-1 if frame in (2,4) else 0)
                    yy=y+offset
                    if 0<=yy<30:im.setPixelColor(x,yy,c)
        if frame>=5:
            p=QPainter(im)
            reach=1 if frame==5 else (3 if frame==6 else 0)
            armx=14 if direction!=3 else 2
            p.fillRect(armx,16-reach,4,3,QColor('#bb967e'))
            p.fillRect(armx-1,19-reach,4,2,QColor('#7f4947'))
            p.end()
        p=QPainter(atlas);p.drawImage(frame*20,direction*30,im);p.end()
        frames.append({'direction':['north','east','south','west'][direction],
            'column':frame,'rect':[frame*20,direction*30,20,30]})

out=ROOT/'assets/sprites'
atlas.save(str(out/'hero_atlas.png'))
atlas.scaled(640,480,Qt.AspectRatioMode.IgnoreAspectRatio,Qt.TransformationMode.FastTransformation).save(str(ROOT/'docs/hero_atlas_preview.png'))
pixels=[];alpha=[]
for y in range(120):
    for x in range(160):
        c=atlas.pixelColor(x,y);pixels.append(((c.red()>>3)<<11)|((c.green()>>2)<<5)|(c.blue()>>3));alpha.append(c.alpha())
raw=b'VXA8'+struct.pack('<HHBBH',160,120,0,1,12)+struct.pack('<'+str(len(pixels))+'H',*pixels)+bytes(alpha)
(out/'hero_atlas.vxa8').write_bytes(raw)
clips={'idle':{'first':0,'count':1,'frame_ms':180,'loop':True},
       'walk':{'first':1,'count':4,'frame_ms':100,'loop':True},
       'cast':{'first':5,'count':2,'frame_ms':140,'loop':False},
       'reel':{'first':7,'count':1,'frame_ms':180,'loop':False}}
(out/'hero_atlas.json').write_text(json.dumps({'format':'Hopscorch Actor Atlas','size':[160,120],
    'frame_size':[20,30],'anchor':[10,28],'clips':clips,'frames':frames},indent=2))
editor_frames=[]
for item in frames:
    x,y,w,h=item['rect'];editor_frames.append({'name':f"{item['direction']}_{item['column']}",
        'x':x,'y':y,'width':w,'height':h,'duration_ms':180 if item['column'] in (0,7) else 140 if item['column'] in (5,6) else 100})
for direction,name in enumerate(['north','east','south','west']):
    for action,clip in clips.items():
        selected=[direction*8+col for col in range(clip['first'],clip['first']+clip['count'])]
        clip_frames=[dict(editor_frames[i],source_index=i,duration_ms=clip['frame_ms']) for i in selected]
        payload={'format':'VXPEngine Animation','format_version':2,'extension':'.ani..dtfe',
            'asset':'assets/sprites/hero_atlas.png','texture':'assets/sprites/hero_atlas.png',
            'source_mode':'atlas_frames','asset_kind':'character','package':'atlas+descriptor',
            'preview_background':'checker','preview_zoom':4,
            'animation':{'name':f'hero_{name}_{action}','fps':round(1000/clip['frame_ms']),
                'loop':clip['loop'],'frame_count':len(selected),'source_mode':'atlas_frames',
                'asset_kind':'character','selected_indices':selected},'frames':clip_frames}
        (ROOT/'assets/scenes'/f'hero_{name}_{action}.ani..dtfe').write_text(json.dumps(payload,indent=2))
(out/'hero_atlas.asset.dtfe').write_text(json.dumps({'format':'VXPEngine Asset','format_version':2,
    'asset':'assets/sprites/hero_atlas.png','asset_type':'Sprite / Character','size':{'width':160,'height':120},
    'texture':{'pixels_per_unit':1,'render_mode':'nearest','transparent':True,'pixel_mode_bits':32},
    'grid':{'width':20,'height':30,'margin':0,'spacing':0},
    'animation':{'name':'hero_east_walk','fps':10,'loop':True,
        'descriptor':'assets/scenes/hero_east_walk.ani..dtfe','source_mode':'atlas_frames'},
    'frames':editor_frames,'collisions':[{'name':'feet','x':5,'y':23,'width':10,'height':6,'kind':'bounds'}]},indent=2))
header=['#pragma once','#include "graphics/VxpActorSprite2D.h"',
    'static const uint16_t hero_pixels[]={'+','.join(map(str,pixels))+'};',
    'static const uint8_t hero_alpha[]={'+','.join(map(str,alpha))+'};',
    'static const VxpeActorAtlas2D hero_atlas={{hero_pixels,hero_alpha,160,120,160,160,0},20,30,10,28,',
    '{{0,1,180,1},{1,4,100,1},{5,2,140,0},{7,1,180,0}}};']
(ROOT/'src/actor_assets.h').write_text('\n'.join(header))
print('PASS: 32 actor frames, 4 directions, VXA8 and embedded RGB565+A8')

# Separate pixel props: silver fish and a shaded red/ivory fishing bobber.
props=QImage(32,16,QImage.Format.Format_ARGB32);props.fill(Qt.GlobalColor.transparent)
p=QPainter(props)
for x,y,w,h,color in [(3,5,9,6,'#253c45'),(4,6,7,4,'#a5c7bb'),(5,6,6,1,'#edf3d0'),
    (6,9,5,1,'#688f95'),(1,4,3,3,'#7599a4'),(1,9,3,3,'#7599a4'),(10,6,1,1,'#20262d'),
    (23,2,1,3,'#493e3e'),(21,5,5,7,'#283742'),(22,5,3,3,'#f5e7c0'),
    (22,8,3,3,'#d26b50'),(22,8,1,2,'#f4a063'),(22,12,3,1,'#658e86')]:
    p.fillRect(x,y,w,h,QColor(color))
p.end();props.save(str(out/'fishing_props.png'))
pp=[];aa=[]
for y in range(16):
    for x in range(32):
        c=props.pixelColor(x,y);pp.append(((c.red()>>3)<<11)|((c.green()>>2)<<5)|(c.blue()>>3));aa.append(c.alpha())
(out/'fishing_props.vxa8').write_bytes(b'VXA8'+struct.pack('<HHBBH',32,16,0,1,12)+struct.pack('<512H',*pp)+bytes(aa))
(ROOT/'src/prop_assets.h').write_text('#pragma once\n#include "graphics/VxpSpriteFx.h"\n'+
    'static const uint16_t prop_pixels[]={'+','.join(map(str,pp))+'};\n'+
    'static const uint8_t prop_alpha[]={'+','.join(map(str,aa))+'};\n'+
    'static const VxpeSpriteA8 fishing_props={prop_pixels,prop_alpha,32,16,32,32,0};\n')
print('PASS: fish and bobber props, PNG/VXA8/embedded alpha')
