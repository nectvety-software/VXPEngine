"""Harness: màn giả lập phải vẽ khung thiết bị ngay cả khi QSS toàn cục của IDE bật.

Lỗi gốc: luật `QWidget { background:#0F1115; }` của dark_theme.qss làm overlay
trong suốt đè trên ScreenPane hóa đục và che kín màn hình. Sửa bằng
objectName ScreenOverlay + luật transparent trong QSS của khung thiết bị.
"""
import os
import shutil
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "app"))

from PySide6.QtWidgets import QApplication

import main as ide_main

app = QApplication.instance() or QApplication([])
ide_main.load_stylesheet(app)  # QSS toàn cục giống IDE thật — điều kiện gây lỗi

import main as ide_main2  # noqa: E402  (cùng module, giữ tên quen thuộc)
from project_store import ProjectStore  # noqa: E402

BG = "#0f1115"

tmp = tempfile.mkdtemp(prefix="vxp_sim_paint_")
store = ProjectStore()
project = store.create_project("HarnessPaint", tmp)

window = ide_main2.MainWindow()
window.show()
window._open_project(project)
app.processEvents()

sim = window._open_simulator_window()
window._sync_simulator_screen()
app.processEvents()

pane = sim.frame._screen
expected = window._render_device_frame()
assert expected is not None, "phải render được khung thiết bị"

pix = pane.grab().toImage()
# tâm màn: paintEvent ánh xạ 1:1 tại tâm ở zoom 1
got = pix.pixelColor(pix.width() // 2, pix.height() // 2).name()
want = expected.pixelColor(expected.width() // 2, expected.height() // 2).name()
assert got == want, f"pixel tâm giả lập {got} != khung thiết bị {want}"
print("OK  Pixel tâm giả lập khớp khung thiết bị:", got)

# vùng giữa màn không được phủ kín bởi màu nền QSS (overlay đục che màn hình)
region = [
    pix.pixelColor(x, y).name()
    for x in range(40, pix.width() - 40, 10)
    for y in range(40, pix.height() - 40, 10)
]
bg_ratio = sum(1 for c in region if c == BG) / len(region)
assert bg_ratio < 0.05, f"overlay vẫn che màn hình (tỉ lệ nền {bg_ratio:.2f})"
print(f"OK  Overlay trong suốt — tỉ lệ pixel nền {bg_ratio:.2f}")

# zoom 2 (nút phóng to) cũng phải vẽ
sim.frame._on_tool("zoom")
window._sync_simulator_screen()
app.processEvents()
pix2 = pane.grab().toImage()
region2 = [
    pix2.pixelColor(x, y).name()
    for x in range(60, pix2.width() - 60, 20)
    for y in range(60, pix2.height() - 60, 20)
]
bg_ratio2 = sum(1 for c in region2 if c == BG) / len(region2)
assert bg_ratio2 < 0.05, f"zoom 2: overlay vẫn che màn hình ({bg_ratio2:.2f})"
print(f"OK  Zoom 200% vẫn vẽ khung — tỉ lệ pixel nền {bg_ratio2:.2f}")

if window.viewport_2d is not None:
    window.viewport_2d.scene().blockSignals(True)
window.close()
if sim is not None:
    sim.close()
app.processEvents()
try:
    store.remove(str(project.folder))
except Exception as error:
    print("bỏ qua đăng ký project:", error)
shutil.rmtree(tmp, ignore_errors=True)

print("PASS_ALL: giả lập vẽ khung thiết bị dưới QSS toàn cục của IDE")
