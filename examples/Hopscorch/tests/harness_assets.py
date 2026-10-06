from pathlib import Path
import json
import struct
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT.parents[1]/'app'))
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication
from widgets.asset_editor import AssetEditorDialog
app=QApplication.instance() or QApplication([])
atlas=QImage(str(ROOT/'assets/sprites/hero_atlas.png'))
assert (atlas.width(),atlas.height())==(160,120)
data=(ROOT/'assets/sprites/hero_atlas.vxa8').read_bytes()
assert data[:4]==b'VXA8' and len(data)==12+160*120*3
assert struct.unpack_from('<HHBBH',data,4)==(160,120,0,1,12)
assert data[12+160*120*2:]==bytes(atlas.pixelColor(x,y).alpha() for y in range(120) for x in range(160))
editor=AssetEditorDialog(ROOT)
editor.load_image(ROOT/'assets/sprites/hero_atlas.png')
assert len(editor.canvas.frames)==32
assert editor.tile_w.value()==20 and editor.tile_h.value()==30
files=sorted((ROOT/'assets/scenes').glob('hero_*.ani..dtfe'))
assert len(files)==16
for descriptor in files:
    payload=json.loads(descriptor.read_text())
    editor.load_image(descriptor)
    selected=editor.animation_player_settings['selected_indices']
    assert selected==payload['animation']['selected_indices']
    assert len(selected)==payload['animation']['frame_count']
    for i,frame in zip(selected,payload['frames']):
        actual=editor.canvas.frames[i]
        assert (actual.rect.width(),actual.rect.height())==(20,30)
        assert actual.duration_ms==frame['duration_ms']
editor.close()
print('PASS: PNG/VXA8 alpha, 32 atlas frames, editor grid and 16 animation descriptors')
