"""Bake original hero poses and wave unit sprites for runtime and Editor Assets."""
from pathlib import Path
import json
from PIL import Image
from generate_assets import encode
ROOT=Path(__file__).resolve().parents[1]
def main():
    assets=ROOT/'assets';header=['#pragma once','#include <stdint.h>']
    for name,cols,rows,size,labels in [('action_poses',6,3,48,['run_a','run_b','attack','cast_up','cast_forward','dash']),('minion_units',2,3,32,['blue','red']),('directional_poses',4,3,40,['north_a','north_b','south_a','south_b'])]:
        source=Image.open(assets/'source'/f'{name}.png').convert('RGBA');atlas=Image.new('RGBA',(cols*size,rows*size));frames=[]
        for row in range(rows):
            for col in range(cols):
                piece=source.crop((col*source.width//cols,row*source.height//rows,(col+1)*source.width//cols,(row+1)*source.height//rows));box=piece.getchannel("A").point(lambda a:255 if a>=128 else 0).getbbox()
                if not box:raise ValueError('Missing sprite')
                l,t,r,b=box;box=(max(0,l-6),max(0,t-6),min(piece.width,r+6),min(piece.height,b+6));piece=piece.crop(box);ratio=min((size-2)/piece.width,(size-2)/piece.height);piece=piece.resize((max(1,round(piece.width*ratio)),max(1,round(piece.height*ratio))),Image.Resampling.NEAREST)
                cell=Image.new('RGBA',(size,size));cell.alpha_composite(piece,((size-piece.width)//2,size-1-piece.height));atlas.alpha_composite(cell,(col*size,row*size))
                label=(['velin','torvan','nimara'] if name!='minion_units' else ['melee','ranged','siege'])[row]+'_'+labels[col]
                cell.save(assets/'sprites'/f'{label}.png');frames.append(dict(name=label,rect=[col*size,row*size,size,size],foot_anchor=[size//2,size-1]))
        atlas.save(assets/'sprites'/f'{name}_atlas.png');(assets/'sprites'/f'{name}_frames.json').write_text(json.dumps(dict(frame_size=[size,size],frames=frames),indent=2))
        if name=='directional_poses':
            for row,hero in enumerate(['velin','torvan','nimara']):
                for col,direction in [(0,'north'),(2,'south')]:
                    doc=json.loads((assets/'sprites'/f'{hero}_walk.ani..dtfe').read_text())
                    doc['asset']=doc['texture']='assets/sprites/directional_poses_atlas.png'
                    doc['animation']['name']=f'{hero}_walk_{direction}'
                    doc['animation']['selected_indices']=[row*4+col,row*4+col+1]
                    doc['frames']=[dict(name=f'{hero}_{direction}_{i}',x=(col+i)*size,y=row*size,width=size,height=size,source_index=row*4+col+i,duration_ms=120) for i in range(2)]
                    (assets/'sprites'/f'{hero}_walk_{direction}.ani..dtfe').write_text(json.dumps(doc,indent=2)+'\n')
        data=encode(atlas);(assets/'runtime'/f'{name}.vxa8').write_bytes(data);header.append(f'alignas(4) static const uint8_t duel_{name}[]={{')
        header.extend(','.join(str(v) for v in data[i:i+32])+',' for i in range(0,len(data),32));header.append('};')
    (ROOT/'src/army_assets_generated.h').write_text('\n'.join(header)+'\n');print('Baked 18 actions, 12 directional poses and six compact wave units')
if __name__=='__main__':main()
