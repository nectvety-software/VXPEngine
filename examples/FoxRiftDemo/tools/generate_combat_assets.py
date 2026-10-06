"""Bake generated structure and skill sheets into deterministic editor/runtime assets."""
from pathlib import Path
import json
from PIL import Image
from generate_assets import encode
ROOT=Path(__file__).resolve().parents[1]

def main():
    assets=ROOT/'assets'
    source=Image.open(assets/'source/structures.png').convert('RGBA')
    atlas=Image.new('RGBA',(192,160))
    structures=['tower_blue','tower_red','tower_ruins','core_blue','core_red','core_ruins']
    frames=[]
    for i,name in enumerate(structures):
        col,row=i%3,i//3
        piece=source.crop((col*source.width//3,row*source.height//2,(col+1)*source.width//3,(row+1)*source.height//2))
        box=piece.getbbox()
        if not box: raise ValueError('Missing structure '+name)
        piece=piece.crop(box)
        ratio=min(60/piece.width,(74 if row==0 else 59)/piece.height)
        piece=piece.resize((max(1,round(piece.width*ratio)),max(1,round(piece.height*ratio))),Image.Resampling.NEAREST)
        cell=Image.new('RGBA',(64,80));cell.alpha_composite(piece,((64-piece.width)//2,78-piece.height))
        cell.save(assets/'sprites'/f'{name}.png');atlas.alpha_composite(cell,(col*64,row*80))
        frames.append(dict(name=name,rect=[col*64,row*80,64,80],foot_anchor=[32,78]))
    atlas.save(assets/'sprites/structures_atlas.png')
    (assets/'sprites/structures_frames.json').write_text(json.dumps(dict(frame_size=[64,80],frames=frames),indent=2))
    source=Image.open(assets/'source/skill_icons.png').convert('RGBA')
    icons=Image.new('RGBA',(128,96));frames=[]
    names=[['prism_bolt','light_burst','anchor_ray','prism_nova'],['hammer_arc','iron_guard','charge','earthbreak'],['wind_bolt','gust_step','pinning_shot','arrowstorm']]
    for row,hero in enumerate(('velin','torvan','nimara')):
        for col,name in enumerate(names[row]):
            cell=source.crop((col*source.width//4,row*source.height//3,(col+1)*source.width//4,(row+1)*source.height//3)).resize((32,32),Image.Resampling.NEAREST)
            icons.alpha_composite(cell,(col*32,row*32));cell.save(assets/'ui'/f'{hero}_{name}.png')
            frames.append(dict(name=hero+'_'+name,hero=row,skill=col,rect=[col*32,row*32,32,32]))
    icons.save(assets/'ui/skill_icons_atlas.png')
    (assets/'ui/skill_icons_frames.json').write_text(json.dumps(dict(frame_size=[32,32],frames=frames),indent=2))
    header=['#pragma once','#include <stdint.h>']
    for name,im in (('structures',atlas),('skill_icons',icons)):
        data=encode(im);(assets/'runtime'/f'{name}.vxa8').write_bytes(data)
        header.append(f'alignas(4) static const uint8_t duel_{name}[]={{')
        header.extend(','.join(str(v) for v in data[i:i+32])+',' for i in range(0,len(data),32));header.append('};')
    (ROOT/'src/combat_assets_generated.h').write_text('\n'.join(header)+'\n')
    print('Baked six transparent structures and 12 skill icons with editor descriptors')
if __name__=='__main__':main()
