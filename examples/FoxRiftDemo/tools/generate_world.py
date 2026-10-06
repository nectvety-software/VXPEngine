"""Validate editable world placements and emit fixed-capacity runtime geometry."""
from pathlib import Path
import json
ROOT=Path(__file__).resolve().parents[1]
def main():
    world=json.loads((ROOT/'assets/gameplay/world.json').read_text())
    if world['world']!=[240,960] or world['viewport']!=[240,320]:raise ValueError('Native world/viewport must match renderer')
    items=world['objects']
    if not 1<=len(items)<=64:raise ValueError('Use 1..64 objects')
    out=['#pragma once','struct DuelMapObject { int kind,x,y,w,h,solid,cx,cy,cw,ch; };','static const DuelMapObject duel_map_objects[]={']
    for item in items:
        kind=item['kind'];x,y=item['position'];w,h=item['size'];cx,cy,cw,ch=item['collision']
        if any(type(v) is not int for v in [kind,x,y,w,h,cx,cy,cw,ch]):raise ValueError('Integer geometry required')
        if not 0<=kind<6 or not 0<=x<x+w<=240 or not 0<=y<y+h<=960:raise ValueError('Invalid object bounds')
        if item['solid'] and not (0<=cx<cx+cw<=w and 0<=cy<cy+ch<=h):raise ValueError('Invalid collider')
        out.append('{'+','.join(map(str,[kind,x,y,w,h,int(item['solid']),cx,cy,cw,ch]))+'},')
    out.extend(['};','static const int duel_map_count=sizeof(duel_map_objects)/sizeof(duel_map_objects[0]);'])
    (ROOT/'src/world_generated.h').write_text('\n'.join(out)+'\n')
    print('Validated world objects:',len(items))
if __name__=='__main__':main()
