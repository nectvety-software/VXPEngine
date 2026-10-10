"""Bake original procedural mesh into Editor preview; not used as live geometry."""

from pathlib import Path

import subprocess,tempfile,json

from PIL import Image

ROOT=Path(__file__).resolve().parents[1];ENGINE=ROOT.parents[1]/'engine/coremre'

with tempfile.TemporaryDirectory(prefix='vxpe_ps1_') as tmp:

 tmp=Path(tmp);exe=tmp/'bake.exe';raw=tmp/'frames.rgba'

 subprocess.run(['g++','-std=c++11','-O2','-I'+str(ENGINE/'include'),'-I'+str(ROOT/'src'),str(ROOT/'tests/bake_ps1.cpp'),str(ROOT/'src/ps1.cpp'),str(ENGINE/'src/graphics/VxpToon3D.cpp'),str(ENGINE/'src/graphics/VxpRender2D.cpp'),'-o',str(exe)],check=True)

 subprocess.run([str(exe),str(raw)],check=True);data=raw.read_bytes();assert len(data)==8*120*160*4

 atlas=Image.new('RGBA',(960,160))

 for i in range(8):atlas.paste(Image.frombytes('RGBA',(120,160),data[i*120*160*4:(i+1)*120*160*4]),(i*120,0))

 atlas.save(ROOT/'assets/ps1_martini_v1.png')

frames=[{'name':f'view_{i}','x':i*120,'y':0,'width':120,'height':160,'duration_ms':1047,'source_index':i} for i in range(8)]

style={'name':'Game · Low Poly 2.5D','role':'sprite','runtime_preset':'VXPE_ARTSTYLE_LOW_POLY_25D'}

# Use a supported profile; live glass colours come from mesh materials.

style={'name':'Game · Low-Poly 2.5D','role':'sprite','runtime_preset':'VXPE_ARTSTYLE_LOW_POLY_25D'}

anim={'name':'martini_turntable','fps':0.955,'loop':True,'frame_count':8,'selected_indices':list(range(8)),'source_mode':'atlas_frames','asset_kind':'prop'}

desc={'format':'VXPEngine Animation','format_version':2,'extension':'.ani..dtfe','asset':'assets/ps1_martini_v1.png','texture':'assets/ps1_martini_v1.png','source_mode':'atlas_frames','asset_kind':'prop','package':'atlas+descriptor','preview_background':'checker','animation':anim,'frames':frames,'art_style':style}

meta={'format':'VXPEngine Asset','format_version':2,'asset':'assets/ps1_martini_v1.png','asset_type':'Sprite / Character','size':{'width':960,'height':160},'grid':{'width':120,'height':160,'margin':0,'spacing':0},'texture':{'render_mode':'nearest','transparent':True,'pixel_mode_bits':32},'frames':frames,'animation':{**anim,'descriptor':'assets/ps1_martini_v1.ani..dtfe'},'art_style':style,'pivot':{'x':60,'y':136},'source_mesh':'src/ps1.cpp'}

manifest={'version':1,'type':'original procedural mesh study','reference':'Erman Malak - a dry martini for a ps1 cocktail bar that does not exist yet','reference_use':'visual study only; no video pixels, audio or third-party assets included','source_mesh':'src/ps1.cpp','baker':'tools/bake_ps1.py','output':'assets/ps1_martini_v1.png','frame_size':[120,160],'frame_order':list(range(8)),'ticks':[i*31 for i in range(8)],'alpha':'binary depth coverage; dither holes remain transparent','physics':'visual prop only, no change to actor hitboxes','viewport':[240,320]}

for name,value in [('ps1_martini_v1.ani..dtfe',desc),('ps1_martini_v1.asset.dtfe',meta),('ps1_martini_v1.manifest.json',manifest)]:

 (ROOT/'assets'/name).write_text(json.dumps(value,indent=2),encoding='utf-8')

print('Baked original PS1 mesh atlas and Editor metadata')

