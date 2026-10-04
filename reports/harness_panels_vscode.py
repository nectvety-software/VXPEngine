r"""Offscreen harness: tab TitleSet gộp một + cây Assets kiểu VSCode.

Chạy: .venv\Scripts\python.exe reports\harness_panels_vscode.py [duong_dan_du_an]
"""
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
APP = Path(__file__).resolve().parent.parent / "app"
sys.path.insert(0, str(APP))

from PySide6.QtWidgets import QApplication  # noqa: E402

project = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(
    r"C:\Users\doxuanhop\Documents\VXP Projects\game2d"
)
assert project.is_dir(), project

from widgets import panels  # noqa: E402
from widgets.asset_manager import AssetsPanel  # noqa: E402

app = QApplication(sys.argv)

# --- 1) TitleSet: không còn QTabWidget, một danh sách duy nhất
lib = panels.build_tilemap_panel(str(project))
assert not hasattr(lib, "tabs"), "thanh tab vẫn còn"
assert lib.sample_list.count() > 0, "TitleSet trống"
print("TITLESET_MERGED:", lib.sample_list.count(), "mẫu")

# --- 2) Assets: src hiện trong cây, nhấp đơn mở thư mục/tệp kiểu VSCode
assets = AssetsPanel(str(project), "game2d")
root = assets.tree.topLevelItem(0)
names = [root.child(i).text(0) for i in range(root.childCount())]
assert "src" in names, names
src_item = next(root.child(i) for i in range(root.childCount()) if root.child(i).text(0) == "src")
assert src_item.childCount() > 0, "src không có con"

initial = src_item.isExpanded()
assets._on_item_clicked(src_item)
assert src_item.isExpanded() != initial, "nhấp đơn không đảo trạng thái thư mục src"
assets._on_item_clicked(src_item)
assert src_item.isExpanded() == initial, "nhấp đơn lần hai không trả lại trạng thái cũ"
if not src_item.isExpanded():
    assets._on_item_clicked(src_item)

c_item = None
for i in range(src_item.childCount()):
    child = src_item.child(i)
    if child.text(0).endswith(".c") or child.text(0).endswith(".h"):
        c_item = child
        break
assert c_item is not None, "src không có tệp C"
opened: list[str] = []
assets.file_open_requested.connect(opened.append)
assets._on_item_clicked(c_item)
assert opened and opened[0].endswith(c_item.text(0)), opened
print("ASSETS_VSCODE_OK:", c_item.text(0))
print("PANELS_PASS")
