import os,sys,tempfile
from pathlib import Path
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'app'))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QPoint
from PySide6.QtGui import QFontDatabase
from vendor.terra.engine.project import Project
from vendor.terra.engine.scatter import scatter_cells,cell_hash
from vendor.terra.engine.history import PaintCommand
from widgets.terra_panel import TerraPanel
app=QApplication([])
for font in ("segoeui.ttf","seguisym.ttf","consola.ttf"):
 QFontDatabase.addApplicationFont(str(Path("C:/Windows/Fonts")/font))
panel=TerraPanel();panel.load_scatter_sample();editor=panel.ensure_editor();p=editor.project
assert editor.canvas.tool=='scatter' and editor.canvas.scatter_variants==list(range(4))
p.map.clear_layer(0);c=editor.canvas;c.brush_size=3;c.scatter_density=100;c.scatter_spacing=2
before=p.map.active_layer.cells.copy();commands=[]
c.paintCommitted.connect(lambda label,edits:commands.append(PaintCommand(label,p.map,edits)))
c._begin(QPoint(2,5),'scatter');c._stroke_to(QPoint(12,5));c._commit()
after=p.map.active_layer.cells.copy();assert after!=before
positions=p.map.active_layer.tile_positions()
assert all(max(abs(x-a),abs(y-b))>=2 for x,y,_ in positions for a,b,_ in positions if (x,y)!=(a,b))
commands[-1].undo();assert p.map.active_layer.cells==before
commands[-1].redo();assert p.map.active_layer.cells==after
p.map.active_layer.locked=True;c._begin(QPoint(2,8),'scatter');c._commit();assert p.map.active_layer.cells==after
p.map.active_layer.locked=False
with tempfile.TemporaryDirectory() as temp:
 out=Path(temp)/'rocks.png';doc=panel.save_editable(p,out);q=Project.load(doc)
 assert q.map.to_dict()==p.map.to_dict();assert q.render(True).size==(240,320)
coords=[(x,y) for y in range(20) for x in range(15)]
p.map.clear_layer(0);scatter_cells(p.map,coords,list(range(4)),50,2,42);a=p.map.active_layer.cells.copy()
p.map.clear_layer(0);scatter_cells(p.map,coords,list(range(4)),50,2,42);assert p.map.active_layer.cells==a
p.map.clear_layer(0);assert not scatter_cells(p.map,coords,[0],0,1,42)
assert [cell_hash(x,y,42) for x,y in [(0,0),(3,7),(-1,5)]]==[4237770831,3819037551,2724760519]
p.map.active_layer.cells=a
c.update()
panel.resize(1500,900);panel.show();app.processEvents();panel.grab().save(str(ROOT/'tmp/scatter-editor-preview.png'))
print('PASS: scatter stroke, spacing, undo/redo, locked layer, portable save, seed, zero density')
