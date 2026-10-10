"""Headless integration checks: strokes, neighbours, erase, undo and editable IO."""
import os
import sys
import tempfile
from pathlib import Path
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'app'))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QPoint
from PySide6.QtGui import QFontDatabase
from vendor.terra.engine.project import Project
from vendor.terra.engine.history import PaintCommand
from vendor.terra.ui.canvas import MapCanvas
from widgets.terra_panel import TerraPanel
from widgets.asset_editor import AssetEditorDialog

app=QApplication.instance() or QApplication([])
for font in ('segoeui.ttf','seguisym.ttf','consola.ttf'):
 QFontDatabase.addApplicationFont(str(Path('C:/Windows/Fonts')/font))
sample=ROOT/'assets/map/tileset/terrain_video_demo/terrain_portrait.terra.json'
p=Project.load(sample)
assert p.map.pixel_size==(240,320) and p.terrain['enabled']
p.map.clear_layer(0)
c=MapCanvas(p)
c.set_tile(15)
commands=[]
c.paintCommitted.connect(lambda name,edits:commands.append(PaintCommand(name,p.map,edits)))
before=p.map.active_layer.cells.copy()
c._begin(QPoint(3,5),'brush')
c._stroke_to(QPoint(8,5))
c._commit()
assert p.map.active_layer.get(3,5)==2 and p.map.active_layer.get(8,5)==8
assert p.map.active_layer.get(5,5)==10
after=p.map.active_layer.cells.copy()
commands[-1].undo();assert p.map.active_layer.cells==before
commands[-1].redo();assert p.map.active_layer.cells==after
c._begin(QPoint(5,5),'eraser');c._commit()
assert p.map.active_layer.get(5,5)==-1
assert p.map.active_layer.get(4,5)==8 and p.map.active_layer.get(6,5)==2
commands[-1].undo();assert p.map.active_layer.cells==after
p.map.active_layer.locked=True
c._begin(QPoint(1,1),'fill');assert p.map.active_layer.cells==after
p.map.active_layer.locked=False
c.brush_size=3
c._begin(QPoint(2,12),'brush');c._stroke_to(QPoint(9,12));c._commit()
assert all(p.map.active_layer.get(x,y)!=-1 for x in range(1,11) for y in range(11,14))
c._begin(QPoint(2,12),'eraser');c._commit()
assert all(p.map.active_layer.get(x,y)==-1 for x in range(1,4) for y in range(11,14))
with tempfile.TemporaryDirectory() as tmp:
 q=Path(tmp)/'roundtrip.terra.json';p.save(q);r=Project.load(q)
 assert r.map.to_dict()==p.map.to_dict() and r.terrain==p.terrain
 assert r.render(transparent=True).size==(240,320)
 exported=Path(tmp)/'imported.png'
 doc=TerraPanel.save_editable(p,exported)
 loaded=Project.load(doc)
 assert loaded.sheet.path.is_relative_to(Path(tmp))
 assert loaded.map.to_dict()==p.map.to_dict() and loaded.terrain==p.terrain
panel=TerraPanel();editor=panel.ensure_editor();panel.load_terrain_sample()
assert panel.terrain_toggle.isChecked() and editor.canvas.tile==15
panel.brush_size.setValue(3);assert editor.canvas.brush_size==3
panel.terrain_toggle.setChecked(False);assert not editor.project.terrain['enabled']
panel.resize(1380,900);panel.show();app.processEvents()
editor.canvas.camera.fit(*editor.project.map.pixel_size);editor.canvas.update();app.processEvents()
out=ROOT/'tmp/terrain-editor-preview.png';panel.grab().save(str(out))
received=[];panel.received.connect(lambda frames,name:received.append((frames,name)))
panel.receive_map();assert received[0][0][0].size().width()==240
with tempfile.TemporaryDirectory() as tmp:
 dialog=AssetEditorDialog(tmp)
 dialog.terra.load_terrain_sample()
 dialog.terra.receive_map()
 dialog.asset_name.setText('terrain_import.png')
 dialog.write_animation.setChecked(False)
 dialog.save_and_apply()
 assert dialog.saved_path and dialog.saved_path.is_file()
 imported=Project.load(dialog.saved_path.with_suffix('.terra.json'))
 assert imported.map.pixel_size==(240,320) and imported.terrain['enabled']
 assert imported.sheet.path.resolve().is_relative_to(Path(tmp).resolve())
 dialog.deleteLater()
print('PASS: continuous strokes, auto edges, erase neighbours, multi-cell brush, locked layer, undo/redo, editable save/load, Terra panel, Assets receive')
print(out)
