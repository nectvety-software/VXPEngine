"""Editable splash, hero selection, duel and result compositions."""
from pathlib import Path
import json,sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT.parents[1]/"app"))
from scene_screen_store import ScreenStore

def main():
    def node(name,asset,x,y,w,h,z=1):
        return dict(id=name,name=name,code_name=name,type="Sprite2D",asset=asset,position=[x,y],scale=[1,1],display_size=[w,h],z_index=z,pixel_snap=True,lock_aspect=True)
    camera=dict(id="camera2d",name="Camera2D",type="OrthographicCamera",position=[0,0],rotation=0,zoom=[1,1],projection="Pixel Perfect")
    bg=node("Arena","assets/backgrounds/arena.png",0,0,240,320,-10)
    actors=[node("Player","assets/sprites/velin_idle.png",-55,21,60,60),node("Bot","assets/sprites/torvan_idle.png",59,-51,60,60)]
    combat=[node("BlueTower","assets/sprites/tower_blue.png",0,20,56,70),node("RedTower","assets/sprites/tower_red.png",0,-95,56,70)]+[node("Skill"+str(i),"assets/ui/velin_"+name+".png",-55+i*44,109,24,24,20) for i,name in enumerate(("prism_bolt","light_burst","anchor_ray","prism_nova"))]
    for screen in ("main","splash","heroes","result"):
        extra=actors+combat if screen in ("main","result") else ([node("Logo","assets/ui/logo.png",0,-27,200,114)] if screen=="splash" else [node(name,"assets/sprites/"+name+"_portrait.png",-78+i*78,-80,62,62) for i,name in enumerate(("velin","torvan","nimara"))])
        scene=dict(name="Vaelora "+screen.title(),screen_id=screen,type="VXPScreen",viewport=dict(width=240,height=320,type="FitViewport",orientation="portrait"),engine=dict(core="coremre",version="2.0.0"),children=[camera,bg]+extra,runtime=dict(controller="FoxScene",screen=screen,notes="Editable composition; UI and gameplay use src/scene.cpp."))
        (ROOT/f"assets/scenes/{screen}.dtfe").write_text(json.dumps(scene,indent=2))
    store=ScreenStore(ROOT);registry=store.ensure()
    registry["screens"]=[dict(id=name,name=name.title(),file=f"assets/scenes/{name}.dtfe",code_name=name.title()) for name in ("splash","heroes","main","result")]
    registry["active_screen"]="splash"
    store.registry_path.write_text(json.dumps(registry,indent=2));store.generate_c_bindings()
    for col,name in enumerate(("velin","torvan","nimara")):
        animation=dict(format="VXPEngine Animation",format_version=2,extension=".ani..dtfe",asset="assets/sprites/heroes_atlas.png",texture="assets/sprites/heroes_atlas.png",source_mode="atlas_frames",asset_kind="character",package="atlas+descriptor",animation=dict(name=name+"_walk",fps=7,loop=True,frame_count=2,source_mode="atlas_frames",asset_kind="character",selected_indices=[col,col+3]),frames=[dict(name=name+"_"+str(i),x=col*64,y=i*64,width=64,height=64,source_index=col+i*3,duration_ms=140) for i in range(2)])
        (ROOT/f"assets/sprites/{name}_walk.ani..dtfe").write_text(json.dumps(animation,indent=2))
    print("Prepared original splash, hero selection, duel/result and hero animations")
if __name__=="__main__":main()
