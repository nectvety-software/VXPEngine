from pathlib import Path

import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))

from PySide6.QtWidgets import QApplication

from PySide6.QtGui import QImage

from widgets.asset_editor import AssetEditorDialog

from game_art_styles import ART_STYLE_PROFILES,apply_game_palette

app=QApplication([]);root=Path('examples/GnarlyDungeonDemo').resolve()

assert ART_STYLE_PROFILES['Game · Dungeon Synth']['runtime_preset']=='VXPE_ARTSTYLE_DUNGEON_SYNTH'

for name in ['stone','floor','skeleton','sword']:

    editor=AssetEditorDialog(root);editor.load_image(root/'assets'/(name+'.png'))

    assert editor.style_combo.currentText()=='Game · Dungeon Synth'

    assert editor._art_style_metadata()['runtime_preset']=='VXPE_ARTSTYLE_DUNGEON_SYNTH'

    editor.close()

image=QImage(str(root/'assets/skeleton.png'));styled=apply_game_palette(image,'Game · Dungeon Synth')

assert styled.pixelColor(0,0).alpha()==0

assert any(styled.pixelColor(x,y).alpha()==255 for y in range(96) for x in range(64))

print('PASS: four dungeon assets, Editor style metadata and preserved alpha')

