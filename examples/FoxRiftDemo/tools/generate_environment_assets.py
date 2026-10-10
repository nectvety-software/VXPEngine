"""Bake original terrain/props; retain source alpha and nearest-neighbor pixels."""
from pathlib import Path
import json
from PIL import Image
from generate_assets import encode
ROOT=Path(__file__).resolve().parents[1]
def main():
    assets=ROOT/'assets';ground=Image.open(assets/'source/lane_ground.png').convert('RGB').resize((240,320),Image.Resampling.NEAREST)
    ground.save(assets/'backgrounds/lane_ground.png')
    world=Image.new('RGB',(240,960))
    for y in range(0,960,320):world.paste(ground,(0,y))
    world.save(assets/'backgrounds/lane_world.png')
    source=Image.open(assets/'source/environment.png').convert('RGBA');atlas=Image.new('RGBA',(192,160));frames=[]
    for i,name in enumerate(('wall_horizontal','wall_vertical','watch_hut','grass','tree','ruins')):
        col,row=i%3,i//3
        piece=source.crop((col*source.width//3,row*source.height//2,(col+1)*source.width//3,(row+1)*source.height//2));box=piece.getbbox()
        if not box:raise ValueError('Missing environment '+name)
        piece=piece.crop(box);ratio=min(60/piece.width,74/piece.height)
        piece=piece.resize((max(1,round(piece.width*ratio)),max(1,round(piece.height*ratio))),Image.Resampling.NEAREST)
        cell=Image.new('RGBA',(64,80));cell.alpha_composite(piece,((64-piece.width)//2,78-piece.height));cell.save(assets/'sprites'/f'environment_{name}.png');atlas.alpha_composite(cell,(col*64,row*80))
        frames.append(dict(name=name,rect=[col*64,row*80,64,80],foot_anchor=[32,78]))
    atlas.save(assets/'sprites/environment_atlas.png');(assets/'sprites/environment_frames.json').write_text(json.dumps(dict(frame_size=[64,80],frames=frames),indent=2))
    header=['#pragma once','#include <stdint.h>']
    for name,im in (('lane_ground',ground),('environment',atlas)):
        data=encode(im);(assets/'runtime'/f'{name}.vxa8').write_bytes(data);header.append(f'alignas(4) static const uint8_t duel_{name}[]={{')
        header.extend(','.join(str(v) for v in data[i:i+32])+',' for i in range(0,len(data),32));header.append('};')
    (ROOT/'src/environment_assets_generated.h').write_text('\n'.join(header)+'\n');print('Baked original lane ground and six environment sprites')
if __name__=='__main__':main()
