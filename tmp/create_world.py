import json
from pathlib import Path
root=Path('examples/FoxRiftDemo')
items=[]
def add(kind,x,y,w,h,box=None):
    names=['wall_horizontal','wall_vertical','watch_hut','grass','tree','ruins']
    items.append(dict(id=names[kind]+'_'+str(len(items)),kind=kind,asset='assets/sprites/environment_'+names[kind]+'.png',position=[x,y],size=[w,h],solid=box is not None,collision=box or [0,0,0,0]))
for x,y in [(14,275),(168,460),(15,685),(167,120)]:add(0,x,y,58,30,[3,17,52,11])
for x,y in [(8,140),(204,550),(8,410),(204,790)]:add(1,x,y,28,72,[6,5,16,63])
for x,y in [(6,510),(172,260),(172,700)]:add(2,x,y,62,64,[12,43,38,18])
for x,y in [(20,340),(171,390),(20,775),(168,630),(22,570),(168,175)]:add(3,x,y,50,32)
for x,y in [(0,660),(182,430),(0,200),(184,820)]:add(4,x,y,56,72,[23,56,12,12])
for x,y in [(17,850),(168,520)]:add(5,x,y,55,32,[12,18,30,10])
(root/'assets/gameplay/world.json').write_text(json.dumps(dict(world=[240,960],viewport=[240,320],movement_bounds=[26,80,214,880],hero_radius=7,objects=items),indent=2))
