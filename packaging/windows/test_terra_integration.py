"""Offscreen verification of Terra's integration into Asset Editor."""
import os
import sys
import tempfile
from pathlib import Path
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'app'))
from PySide6.QtWidgets import QApplication
from widgets.asset_editor import AssetEditorDialog
from vendor.terra.engine.project import Project
from vendor.terra.ui import dialogs

app = QApplication([])
app.setStyleSheet('QWidget { color: #abcdef; }')
before = app.styleSheet()
with tempfile.TemporaryDirectory() as td:
    host = AssetEditorDialog(td)
    host.workspace_tabs.setCurrentIndex(2)
    editor = host.terra.ensure_editor()
    editor.apply_theme('light')
    assert app.styleSheet() == before
    project = editor.project
    tile = project.sheet.solid[0].index
    editor._commit_paint('paint', project.map.paint(0, 0, tile))
    assert editor.dirty
    editor.undo()
    assert project.map.layers[0].cells[0] != tile
    editor.redo()
    assert project.map.layers[0].cells[0] == tile
    original_ask = dialogs.MessageDialog.ask
    dialogs.MessageDialog.ask = lambda *a, **kw: 'Huỷ'
    assert not host.terra.can_close()
    dialogs.MessageDialog.ask = original_ask
    expected = project.render(transparent=True).tobytes()
    path = project.save(Path(td) / 'test.terra.json')
    loaded = Project.load(path)
    assert loaded.render(transparent=True).tobytes() == expected
    host.terra.receive_map()
    assert host.workspace_tabs.currentIndex() == 0
    assert host.canvas.image.width() == 320
    assert host.canvas.image.height() == 224
    assert 'Terra' in host.status_label.text()
    assert host.terra.can_close()
    host.resize(1380, 860)
    host.show()
    app.processEvents()
    host.workspace_tabs.setCurrentIndex(2)
    app.processEvents()
    host.grab().save(str(ROOT / 'reports/terra/integration.png'))
    host.hide()
print('PASS: embedded tab, isolated theme, paint/undo/redo, discard cancellation, JSON roundtrip, Assets transfer')

