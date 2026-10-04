"""Regression: Open Project uses the native Windows folder picker."""
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

from PySide6.QtWidgets import QApplication, QFileDialog
from main import MainWindow


class MemorySettings:
    def __init__(self, values=None):
        self.values = dict(values or {})

    def value(self, key, default=None):
        return self.values.get(key, default)

    def setValue(self, key, value):
        self.values[key] = value


class ProjectStoreStub:
    def __init__(self, default_directory):
        self.default_directory = Path(default_directory)
        self.registered = []

    def default_projects_directory(self):
        return self.default_directory

    def register_existing(self, path):
        self.registered.append(path)
        return {"path": path}


app = QApplication.instance() or QApplication([])
with tempfile.TemporaryDirectory(prefix="vxpe_native_picker_") as tmp:
    root = Path(tmp)
    default_dir = root / "default"
    remembered_dir = root / "remembered"
    selected_dir = root / "projects-anywhere" / "MyGame"
    default_dir.mkdir()
    remembered_dir.mkdir()
    selected_dir.mkdir(parents=True)

    window = MainWindow()
    window._settings = MemorySettings({"projects/last_browse_directory": str(remembered_dir)})
    store = ProjectStoreStub(default_dir)
    window.project_store = store
    opened = []
    window._open_project = opened.append

    with patch.object(QFileDialog, "getExistingDirectory", return_value=str(selected_dir)) as picker:
        window._open_project_folder()

    args = picker.call_args.args
    assert args[0] is window
    assert args[1] == "Mở thư mục dự án VXPEngine"
    assert Path(args[2]) == remembered_dir
    assert args[3] & QFileDialog.Option.ShowDirsOnly
    assert not (args[3] & QFileDialog.Option.DontUseNativeDialog)
    assert store.registered == [str(selected_dir)]
    assert opened == [{"path": str(selected_dir)}]
    assert Path(window._settings.value("projects/last_browse_directory")) == selected_dir

    # Hủy hộp chọn không đăng ký hoặc mở thêm dự án nào.
    with patch.object(QFileDialog, "getExistingDirectory", return_value=""):
        window._open_project_folder()
    assert store.registered == [str(selected_dir)]
    assert len(opened) == 1

    window.deleteLater()
    app.processEvents()

print("PASS: Open Project uses native Windows folder picker and remembers location")
