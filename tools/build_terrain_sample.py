"""Original 16px terrain family and editable demo; no video frames used as art."""
import json
import shutil
import sys
from pathlib import Path
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'app'))
from vendor.terra.engine.project import Project


def build():
    destination = ROOT / 'assets/map/tileset/terrain_video_demo'
    destination.mkdir(parents=True, exist_ok=True)
    atlas = Image.new('RGBA', (64, 64))
    frames = []
    for mask in range(16):
        tile = Image.new('RGBA', (16,16), (111,123,66,255))
        d = ImageDraw.Draw(tile)
        for y in range(2,16,4):
            for x in range(1,16,5):
                d.point((x,y), fill=(143,151,86))
                d.point(((x+2)%16,y+1), fill=(91,105,54))
        # A connected side is seamless; exposed edges have a bevel.
        if not mask & 1: d.line((0,0,15,0), fill=(204,210,129)); d.line((0,1,15,1), fill=(167,178,101))
        if not mask & 2: d.line((15,0,15,15), fill=(47,62,39))
        if not mask & 4: d.line((0,15,15,15), fill=(38,51,34)); d.line((0,14,15,14), fill=(73,88,45))
        if not mask & 8: d.line((0,0,0,15), fill=(174,187,108))
        name = f'moss_stone__rule_{mask}.png'
        tile.save(destination / name)
        atlas.paste(tile, ((mask%4)*16,(mask//4)*16))
        frames.append({'name':f'Rule {mask}', 'file':f'assets/map/tileset/terrain_video_demo/{name}',
                       'category':'terrain','rect':[(mask%4)*16,(mask//4)*16,16,16]})
    shutil.copy2(destination/'moss_stone__rule_15.png',destination/'moss_stone.png')
    atlas.save(destination/'terrain_atlas.png')
    catalog={'format':'VXPEngine TitleSet Catalog','version':1,'name':'Terrain · Moss Stone',
             'source':'assets/map/tileset/terrain_video_demo/terrain_atlas.png',
             'auto_category':'terrain','tile_width':16,'tile_height':16,'frames':frames}
    (destination/'terrain.tileset.dtfe').write_text(json.dumps(catalog,indent=2),encoding='utf-8')
    for name,w,h in [('terrain_portrait',15,20),('terrain_long',45,80)]:
        p=Project.new(destination/'terrain_atlas.png',w,h,16)
        p.terrain={'enabled':True,'variants':list(range(16)), 'mask_order':'N=1,E=2,S=4,W=8'}
        m=p.map
        # Two chambers, a winding connecting path and a hollow pocket.
        m.paint_rect(1,2,w//2, h//3,15)
        m.paint_rect(w//3,h//2,w-2,h-3,15)
        m.paint_rect(3,4,max(3,w//3),max(4,h//4),-1)
        for offset in (-1,0,1):
            m.paint_line(w//2+offset,h//3,w//2+2+offset,h//2,15)
        m.retile_terrain([(x,y) for x,y,_ in m.active_layer.tile_positions()],list(range(16)))
        p.save(destination/f'{name}.terra.json')
        p.export_png(destination/f'{name}.png',transparent=True)
    (destination/'README.md').write_text(
        'Terrain mẫu 16px, đồ họa tự tạo. Video chỉ dùng tham khảo thao tác.\n'
        'Editor Assets → Terra · Tilemap → Mẫu địa hình. Chuột trái vẽ, phải xóa; '
        'bật Tự nối viền, chọn cỡ cọ 1–9 ô. Ctrl+Z/Redo phục hồi cả viền. '
        'Lưu .terra.json để giữ layer/ô; Đưa tilemap vào Assets xuất ảnh PNG.\n'
        'terrain_portrait: 240×320; terrain_long: 720×1280. '
        'Rule mask: Bắc=1, Đông=2, Nam=4, Tây=8.\n',encoding='utf-8')
    temp = ROOT/'tmp/assets/map/tileset/terrain_video_demo'
    shutil.copytree(destination,temp,dirs_exist_ok=True)
    print(destination)
    print(temp)


if __name__ == '__main__':
    build()
