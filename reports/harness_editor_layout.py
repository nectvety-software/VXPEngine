"""Regression: bottom console is opt-in and alignment menu is available."""
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

from PySide6.QtWidgets import QApplication
from main import MainWindow
from project_store import ProjectStore

app = QApplication.instance() or QApplication([])
with tempfile.TemporaryDirectory(prefix="vxpe_layout_") as tmp:
    store = ProjectStore(); store.data_dir = Path(tmp) / ".registry"; store.data_dir.mkdir()
    store.registry_path = store.data_dir / "projects.json"
    project = store.create_project("EditorLayoutDemo", tmp)
    window = MainWindow()
    window.current_project = project
    workspace = window._build_editor_page(project)
    assert window._console_visible is False
    assert window.console_panel.isHidden()
    assert not window.console_toggle_action.isChecked()
    assert window.align_menu_button.menu() is not None
    assert len(window.align_menu_button.menu().actions()) >= 15
    window._set_console_visible(True)
    assert window._console_visible and not window.console_panel.isHidden()
    window._set_console_visible(False)
    assert window.console_panel.isHidden()
    workspace.deleteLater(); window.deleteLater(); app.processEvents()

print("PASS: console hidden by default + explicit toggle + Photoshop alignment menu")
