"""Create original pixel rock variants and portable 240x320 scatter map."""
from pathlib import Path
import sys, shutil, json
from PIL import Image, ImageDraw
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'app'))
from vendor.terra.engine.project import Project
from vendor.terra.engine.scatter import scatter_cells
folder=ROOT/'assets/map/tileset/rock_scatter'
folder.mkdir(parents=True,exist_ok=True)
atlas=Image.new('RGBA',(64,16))
for i in range(4):
    d=ImageDraw.Draw(atlas); x=i*16; top=4+(i%2)*2
    d.ellipse((x+1,11,x+15,15),fill=(22,31,29,150))
    d.polygon([(x+2,12),(x+3,top+2),(x+7,top),(x+12,top+1),(x+14,10),(x+11,14),(x+5,14)],fill=(87+i*8,98+i*6,96+i*5),outline=(40,53,53))
    d.polygon([(x+4,top+2),(x+7,top+1),(x+11,top+2),(x+8,9),(x+4,10)],fill=(157,166,151))
    d.line((x+8,9,x+11,12),fill=(55,67,63))
    if i==3: d.line((x+3,11,x+6,10),fill=(107,143,64),width=2)
atlas.save(folder/'rocks_atlas.png')
p=Project.new(folder/'rocks_atlas.png',15,20,16)
scatter_cells(p.map,[(x,y) for y in range(1,19) for x in range(1,14)],list(range(4)),60,2,42)
p.save(folder/'rocks.terra.json');p.export_png(folder/'rocks.png',transparent=True)
(folder/'rocks.tileset.dtfe').write_text(json.dumps({'name':'Original rock scatter','sprite_file':'rocks_atlas.png','frame_width':16,'frame_height':16,'frames':[{'name':'rock_'+str(i),'rect':[i*16,0,16,16]} for i in range(4)]},indent=2),encoding='utf-8')
shutil.copytree(folder,ROOT/'tmp/assets/map/tileset/rock_scatter',dirs_exist_ok=True)
print('Rock sample ready')
