"""Create editable DTFE compositions matching each demo location."""
import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
ENGINE=ROOT.parents[1]
sys.path.insert(0,str(ENGINE/'app'))
from scene_screen_store import ScreenStore

def sprite(name,asset,x,y,w=75,h=90,z=1):
    return {'id':name,'name':name,'code_name':name,'type':'Sprite2D',
        'asset':asset,'position':[x,y],'scale':[1,1],'display_size':[w,h],
        'z_index':z,'pixel_snap':True,'lock_aspect':True}

def main():
    directory=ROOT/'assets/scenes'
    for area in ['library','terrace','village']:
        camera={'id':'camera2d','name':'Camera2D','type':'OrthographicCamera',
            'position':[0,0],'rotation':0,'zoom':[1,1],'projection':'Pixel Perfect',
            'frame_perspective':{'kind':'three_quarter','fit_mode':'camera_frame','editor_guide':True}}
        bg=sprite('Background',f'assets/backgrounds/{area}.png',0,0,240,320,-10)
        bg.update({'locked':True,'component_category':'background','ui_role':'Background'})
        nodes=[camera,bg,sprite('Lyra','assets/sprites/hero_idle.png',-5,77,z=5),
            sprite('Syl','assets/sprites/fairy.png',23,14,z=4)]
        if area=='library':
            nodes.extend([sprite('Witch','assets/sprites/witch_idle.png',-74,77,z=3),
                sprite('Maelin','assets/sprites/sage_idle.png',72,79,z=6),
                sprite('Duck','assets/sprites/duck.png',33,81,z=8),
                sprite('Frog','assets/sprites/frog.png',57,80,z=7)])
        if area=='terrace':
            nodes[2]['position']=[-60,77]
            nodes[3]['position']=[-32,14]
            nodes.append(sprite('Rowan','assets/sprites/knight.png',65,77,z=3))
        scene={'name':area.title(),'screen_id':area,'type':'VXPScreen',
            'viewport':{'width':240,'height':320,'type':'FitViewport','orientation':'portrait'},
            'engine':{'core':'coremre','version':'2.0.0'},'children':nodes,
            'runtime':{'controller':'EmberScene','area':area,'notes':'DTFE is an editable composition; gameplay uses scene.cpp.'}}
        (directory/f'{area}.dtfe').write_text(json.dumps(scene,indent=2),encoding='utf-8')
        if area=='library':
            scene['screen_id']='main'
            (directory/'main.dtfe').write_text(json.dumps(scene,indent=2),encoding='utf-8')
    store=ScreenStore(ROOT)
    registry=store.ensure()
    registry['screens']=[{'id':name,'name':name.title(),'file':f'assets/scenes/{name}.dtfe',
        'code_name':name.title()} for name in ['main','library','terrace','village']]
    registry['active_screen']='main'
    store.registry_path.write_text(json.dumps(registry,indent=2),encoding='utf-8')
    store.generate_c_bindings()
    print('Wrote editable main/library/terrace/village DTFE scenes and C bindings')

if __name__=='__main__': main()
