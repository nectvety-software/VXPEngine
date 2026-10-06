"""Bake Editor Assets atlas from the same 3D actor renderer as the live game.
Requires a native g++ on PATH and Pillow. No runtime Python dependency.
"""
from pathlib import Path
import subprocess, tempfile, json
from PIL import Image
ROOT=Path(__file__).resolve().parents[1]
ENGINE=ROOT.parents[1]/'engine/coremre'
with tempfile.TemporaryDirectory(prefix='vxpe_actor_') as tmp:
    tmp=Path(tmp);exe=tmp/'bake_actor.exe';raw=tmp/'frames.rgba'
    subprocess.run(['g++','-std=c++11','-O2','-I'+str(ENGINE/'include'),'-I'+str(ROOT/'src'),str(ROOT/'tests/bake_actor.cpp'),str(ROOT/'src/actor.cpp'),str(ENGINE/'src/graphics/VxpToon3D.cpp'),str(ENGINE/'src/graphics/VxpRender2D.cpp'),'-o',str(exe)],check=True)
    subprocess.run([str(exe),str(raw)],check=True)
    data=raw.read_bytes();assert len(data)==6*96*144*4
    atlas=Image.new('RGBA',(576,144))
    for i in range(6):atlas.paste(Image.frombytes('RGBA',(96,144),data[i*96*144*4:(i+1)*96*144*4]),(i*96,0))
    atlas.save(ROOT/'assets/skater_atlas.png')
frames=[{'name':f'roll_{i}','x':i*96,'y':0,'width':96,'height':144,'duration_ms':133,'source_index':i} for i in range(6)]
anim={'name':'skater_roll','fps':7.5,'loop':True,'frame_count':6,'source_mode':'atlas_frames','asset_kind':'character','selected_indices':list(range(6))}
style={'name':'Game · Urban Toon','role':'sprite','runtime_preset':'VXPE_ARTSTYLE_URBAN_TOON'}
descriptor={'format':'VXPEngine Animation','format_version':2,'extension':'.ani..dtfe','asset':'assets/skater_atlas.png','texture':'assets/skater_atlas.png','source_mode':'atlas_frames','asset_kind':'character','package':'atlas+descriptor','preview_background':'checker','animation':anim,'frames':frames,'art_style':style}
metadata={'format':'VXPEngine Asset','format_version':2,'asset':'assets/skater_atlas.png','asset_type':'Sprite / Character','size':{'width':576,'height':144},'texture':{'pixels_per_unit':1,'render_mode':'nearest','transparent':True,'pixel_mode_bits':32},'grid':{'width':96,'height':144,'margin':0,'spacing':0},'frames':frames,'animation':{**anim,'descriptor':'assets/skater_roll.ani..dtfe'},'art_style':style,'source_mesh':'src/actor.cpp'}
for name,value in [('skater_roll.ani..dtfe',descriptor),('skater_atlas.asset.dtfe',metadata)]:
    (ROOT/'assets'/name).write_text(json.dumps(value,indent=2),encoding='utf-8')
print('Baked original 6-frame mesh atlas and Editor Assets descriptors')
