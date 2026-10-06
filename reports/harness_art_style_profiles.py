import os,sys,tempfile
from pathlib import Path
os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"app"))
from PySide6.QtGui import QColor,QImage
from PySide6.QtWidgets import QApplication
from game_art_styles import ART_STYLE_PROFILES,GAME_ART_STYLES
from widgets.asset_editor import AssetEditorDialog
app=QApplication.instance() or QApplication([])
for name in ["Game · Cozy Farm","Game · Dark Fantasy","Game · Neon Action","Game · Cel-Shaded Cartoon","Game · Saturated Adventure","Game · Strategy Kingdom","Game · Painterly Fantasy","Game · Low-Poly 2.5D"]:
    assert name in ART_STYLE_PROFILES and name in GAME_ART_STYLES
assert ART_STYLE_PROFILES["Game · Saturated Adventure"]["runtime_preset"]=="VXPE_ARTSTYLE_SATURATED_ADVENTURE"
with tempfile.TemporaryDirectory(prefix="vxpe-style-",dir=ROOT) as td:
    dlg=AssetEditorDialog(Path(td))
    i=dlg.style_combo.findText("Game · Saturated Adventure");assert i>=0;dlg.style_combo.setCurrentIndex(i)
    r=dlg.style_role_combo.findData("environment");dlg.style_role_combo.setCurrentIndex(r)
    img=QImage(8,8,QImage.Format.Format_ARGB32);img.fill(QColor("#3a8f75"));dlg.canvas.image=img;dlg.apply_style()
    cfg=dlg._art_style_metadata();assert cfg["role"]=="environment";assert cfg["runtime_preset"]=="VXPE_ARTSTYLE_SATURATED_ADVENTURE";assert cfg["trail"]=="#CAF8FF"
    dlg.style_combo.setCurrentIndex(0);dlg._load_art_style_metadata({"art_style":cfg})
    assert dlg.style_combo.currentText()=="Game · Saturated Adventure";assert dlg.style_role_combo.currentData()=="environment";dlg.close()
print("VXPE_ART_STYLE_EDITOR_PASS")
