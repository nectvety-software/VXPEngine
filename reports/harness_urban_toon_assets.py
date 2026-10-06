"""Verify real demo assets and runtime profile transfer through Asset Editor."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QColor,QImage
from widgets.asset_editor import AssetEditorDialog
from game_art_styles import ART_STYLE_PROFILES,apply_game_palette

root=Path(__file__).resolve().parents[1]
app=QApplication([])
assert ART_STYLE_PROFILES['Game · Urban Toon']['runtime_preset']=='VXPE_ARTSTYLE_URBAN_TOON'
for name,descriptor,count,width,height in [('UrbanToonDemo','skater_roll.ani..dtfe',6,96,144),('NightfallSurvival','scenes/zombie_walk.ani..dtfe',2,48,64)]:
    project=root/'examples'/name
    editor=AssetEditorDialog(project)
    editor.load_image(project/'assets'/descriptor)
    assert len(editor.canvas.frames)==count
    assert editor.animation_player_settings['selected_indices']==list(range(count))
    assert editor.tile_w.value()==width and editor.tile_h.value()==height
    if name=='UrbanToonDemo':
        assert editor.style_combo.currentText()=='Game · Urban Toon'
        assert editor._art_style_metadata()['runtime_preset']=='VXPE_ARTSTYLE_URBAN_TOON'
    editor.close()
probe=QImage(3,1,QImage.Format.Format_ARGB32)
for x,alpha in enumerate((0,127,255)):probe.setPixelColor(x,0,QColor(177,199,89,alpha))
result=apply_game_palette(probe,'Game · Urban Toon')
assert [result.pixelColor(x,0).alpha() for x in range(3)]==[0,127,255]
print('PASS: skater/zombie atlas slicing, animation selection, Urban Toon runtime preset and alpha')
