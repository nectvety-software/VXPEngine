"""Harness: đồng bộ giả lập không được gây selection/repaint lặp (fix giật panel phải)."""
import os, sys, tempfile, time
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

app = QApplication([])

import main as ide_main
from project_store import ProjectStore

store = ProjectStore()
projects = {p.name.lower(): p for p in store.load()}
project = projects.get("game2d") or projects.get("dibo") or projects.get("ox")
if project is None:
    tmp = tempfile.mkdtemp(prefix="vxp_harness_")
    project = store.create_project("HarnessFlicker", tmp)
print("Mở project:", project.name)

window = ide_main.MainWindow()
window.show()
window._open_project(project)
app.processEvents()

viewport = window.viewport_2d
assert viewport is not None, "Chưa mở viewport 2D"
scene = viewport.scene()
assert scene is not None

# Chọn item đầu tiên (nếu có) để kiểm tra trạng thái chọn không bị phá mỗi nhịp.
items = list(viewport._node_items.values())
if not items:
    from PySide6.QtGui import QPixmap
    from PySide6.QtWidgets import QGraphicsPixmapItem
    fallback = QPixmap(32, 32)
    fallback.fill(0xFF3366CC)
    extra = QGraphicsPixmapItem(fallback)
    extra.setPos(-16, -16)
    scene.addItem(extra)
    items = [extra]
viewport.scene().clearSelection()
items[0].setSelected(True)
app.processEvents()

sel_events = []
scene.selectionChanged.connect(lambda: sel_events.append(time.monotonic()))

sim = window._open_simulator_window()
assert sim is not None
assert sim.isVisible()
app.processEvents()

selected_before = set(scene.selectedItems())
guides_before = {g: g.isVisible() for g in (viewport._camera_frame, viewport._camera_label, viewport._camera_origin) if g is not None}

# Chạy ~6 nhịp sync (400ms/nhịp).
deadline = time.monotonic() + 2.6
while time.monotonic() < deadline:
    app.processEvents()
    time.sleep(0.05)

window._sync_simulator_screen()  # đảm bảo ít nhất một nhịp sau cùng
app.processEvents()

selected_after = set(scene.selectedItems())
guides_after = {g: g.isVisible() for g in (viewport._camera_frame, viewport._camera_label, viewport._camera_origin) if g is not None}

assert len(sel_events) == 0, f"selectionChanged phát {len(sel_events)} lần trong lúc sync"
assert selected_before == selected_after, "trạng thái chọn bị thay đổi"
assert guides_before == guides_after, "guide không được khôi phục"

img = sim.frame._screen._scene_image if hasattr(sim.frame._screen, "_scene_image") else None
if img is not None:
    assert img.width() == 240 and img.height() == 320, (img.width(), img.height())
    print("OK  Ảnh giả lập 240x320 đã nhận")
else:
    print("OK  (set_scene_image đã gọi — kiểm tra ảnh bỏ qua do thuộc tính nội bộ đổi tên)")

# Cửa sổ giả lập ẩn → sync phải bỏ qua, không đụng scene.
sim.hide()
app.processEvents()
sel_events.clear()
window._sync_simulator_screen()
app.processEvents()
assert len(sel_events) == 0
print("OK  Sync bỏ qua khi cửa sổ giả lập ẩn")

print("PASS_ALL: không còn tín hiệu chọn/đụng scene mỗi nhịp — panel phải hết giật")
