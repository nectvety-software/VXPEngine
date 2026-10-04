"""Harness: kéo nhóm trong Frame Preview — nhóm phải đi theo con trỏ, mọi thành phần (kể cả ảnh) di chuyển cùng nhau.

Kiểm tra:
1. Nhấn vào thành viên trong khung camera → group_drag phải kích hoạt (hit-test xuyên overlay).
2. Kéo (snap tắt) → mọi thành viên dời đúng delta con trỏ.
3. Kéo (snap bật) → mọi thành viên dời CÙNG một delta (nhóm cứng).
4. Lưu đĩa → groups và group_id của children phải tồn tại song song.
5. Nạp lại từ đĩa → nhóm còn nguyên và kéo vẫn hoạt động.
"""
import json, os, shutil, sys, tempfile
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

import pathlib
from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import QMouseEvent, QPixmap
from PySide6.QtWidgets import QApplication

app = QApplication([])

import main as ide_main
from project_store import ProjectStore

store = ProjectStore()
tmp = tempfile.mkdtemp(prefix="vxp_group_harness_")
project = store.create_project("HarnessGroup", tmp)
print("Mở project:", project.name)

window = ide_main.MainWindow()
window.show()
window._open_project(project)
app.processEvents()

viewport = window.viewport_2d
assert viewport is not None, "Chưa mở viewport 2D"
scene = viewport.scene()

def make_rect(name, x, y, w=40, h=30):
    node = viewport._base_node(None, "Rectangle2D", name)
    node["position"] = [x, y]
    node["shape"] = {"width": w, "height": h, "fill": "#3355AA", "stroke": "#8DB7FF", "stroke_width": 2}
    return viewport._create_vector_item(node, persist=True)

r1 = make_rect("RectA", -60, -40)
r2 = make_rect("RectB", 50, 20)

proj_root = pathlib.Path(project.folder)
assets_dir = proj_root / "assets"
assets_dir.mkdir(parents=True, exist_ok=True)
png_path = assets_dir / "hero_test.png"
pix = QPixmap(24, 24)
pix.fill(0xFFCC6633)
assert pix.save(str(png_path)), "không lưu được png thử nghiệm"
spr = viewport._create_sprite_item(png_path, position=QPointF(0, 60), persist=True)
assert spr is not None, "không tạo được sprite ảnh"

items = [r1, r2, spr]
app.processEvents()

# ---- Gộp nhóm (2 hình + 1 ảnh) ----
scene.clearSelection()
for it in items:
    it.setSelected(True)
app.processEvents()
assert viewport.group_selected(), "group_selected thất bại"
group_id = str(r1.metadata.get("group_id", ""))
assert group_id, "group_id chưa được gán"
assert all(str(it.metadata.get("group_id", "")) == group_id for it in items), "thành viên thiếu group_id"
assert len(viewport._group_members(group_id)) == 3, "không đủ 3 thành viên trong nhóm"
print("OK  Gộp nhóm: 2 hình + 1 ảnh, group_id =", group_id[:12])

# ---- Helpers gửi sự kiện chuột thật ----
def view_point(scene_pt: QPointF) -> QPoint:
    return viewport.mapFromScene(scene_pt)

def send_mouse(etype, view_pt: QPoint, button=Qt.MouseButton.NoButton, buttons=Qt.MouseButton.NoButton):
    ev = QMouseEvent(etype, QPointF(view_pt), QPointF(view_pt), button, buttons, Qt.KeyboardModifier.NoModifier)
    QApplication.sendEvent(viewport.viewport(), ev)
    app.processEvents()

def drag(grab_item, delta: QPointF, snap: bool, members=None):
    group = members if members is not None else items
    viewport.set_snap_enabled(snap)
    grab = QPointF(grab_item.pos())
    before = {it: QPointF(it.pos()) for it in group}
    send_mouse(QEvent.Type.MouseButtonPress, view_point(grab), Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton)
    engaged = viewport._group_drag is not None
    send_mouse(QEvent.Type.MouseMove, view_point(grab + delta), Qt.MouseButton.NoButton, Qt.MouseButton.LeftButton)
    send_mouse(QEvent.Type.MouseButtonRelease, view_point(grab + delta), Qt.MouseButton.LeftButton, Qt.MouseButton.NoButton)
    app.processEvents()
    return engaged, before, {it: it.pos() - before[it] for it in group}

# ---- 1+2. Kéo bằng chuột thật, snap tắt: phải theo đúng con trỏ ----
engaged, before, moved = drag(r1, QPointF(37.0, 21.0), snap=False)
assert engaged, "nhấn vào thành viên trong khung camera nhưng group_drag KHÔNG kích hoạt"
print("OK  Nhấn trong khung camera → group_drag kích hoạt")
deltas_off = {(round(d.x(), 3), round(d.y(), 3)) for d in moved.values()}
assert len(deltas_off) == 1, f"nhóm không cứng khi snap tắt: {moved}"
dx, dy = deltas_off.pop()
# mapToScene qua tọa độ view nguyên px (zoom < 1) sai số ≤ ~1px view
assert abs(dx - 37.0) <= 1.5 and abs(dy - 21.0) <= 1.5, f"cả nhóm dời ({dx},{dy}) thay vì ~(37,21)"
print(f"OK  Kéo (snap tắt): cả 3 thành phần cùng delta ({dx}, {dy}) ≈ con trỏ (37, 21)")

# ---- 3. Kéo với snap bật: nhóm phải cứng (cùng một delta) ----
engaged2, before2, moved2 = drag(spr, QPointF(45.0, 12.0), snap=True)
assert engaged2, "kéo từ sprite ảnh không kích hoạt group_drag"
deltas = {(round(d.x(), 2), round(d.y(), 2)) for d in moved2.values()}
assert len(deltas) == 1, f"nhóm không cứng — mỗi thành viên một delta: {moved2}"
assert all(abs(d.x()) + abs(d.y()) > 0 for d in moved2.values()), "kéo có snap nhưng nhóm không nhúc nhích"
only_delta = deltas.pop()
print(f"OK  Kéo từ ảnh (snap bật): nhóm cứng, cả 3 cùng delta {only_delta}")

# ---- 4. Lưu đĩa: groups và group_id phải song song tồn tại ----
viewport._save_scene()
payload = json.loads(viewport.scene_file.read_text(encoding="utf-8"))
disk_groups = [g for g in payload.get("groups", []) if str(g.get("id", "")) == group_id]
disk_members = [c for c in payload.get("children", []) if str(c.get("group_id", "")) == group_id]
assert len(disk_groups) == 1, f"groups trên đĩa thiếu nhóm (có {len(disk_groups)})"
assert len(disk_members) == 3, f"children trên đĩa thiếu thành viên nhóm (có {len(disk_members)})"
print("OK  Trên đĩa: groups =", len(payload.get("groups", [])), "| children trong nhóm =", len(disk_members))

# ---- 5. Nạp lại từ đĩa (mô phỏng mở lại scene): nhóm phải còn nguyên ----
assert viewport.reload_from_disk() is False, "vừa lưu xong mà đĩa đã lệch nội dung viewport"
fake = json.loads(viewport.scene_file.read_text(encoding="utf-8"))
fake["children"][0]["position"] = [fake["children"][0]["position"][0] + 1, fake["children"][0]["position"][1]]
viewport.scene_file.write_text(json.dumps(fake, ensure_ascii=False), encoding="utf-8")
assert viewport.reload_from_disk() is True, "reload_from_disk không nạp thay đổi từ đĩa"
app.processEvents()
rebuilt = viewport._group_members(group_id)
assert len(rebuilt) == 3, f"sau reload nhóm còn {len(rebuilt)} thành viên"
print("OK  Reload từ đĩa: nhóm còn nguyên 3 thành viên (kể cả ảnh)")

engaged3, before3, moved3 = drag(rebuilt[0], QPointF(-20.0, 15.0), snap=False, members=rebuilt)
assert engaged3, "sau reload, kéo nhóm không kích hoạt"
deltas3 = {(round(d.x(), 3), round(d.y(), 3)) for d in moved3.values()}
assert len(deltas3) == 1, f"sau reload nhóm không cứng: {moved3}"
dx3, dy3 = deltas3.pop()
assert abs(dx3 + 20.0) <= 1.5 and abs(dy3 - 15.0) <= 1.5, f"sau reload nhóm dời ({dx3},{dy3}) thay vì ~(-20,15)"
print(f"OK  Sau reload: kéo nhóm bám con trỏ, cả 3 cùng delta ({dx3}, {dy3})")

print("PASS_ALL: gộp nhóm — kéo nhóm bám con trỏ, ảnh/hình di chuyển cùng nhóm, nhóm sống qua lưu/nạp")

scene.blockSignals(True)
window.close()
app.processEvents()
try:
    store.remove(str(project.folder))
except Exception as error:
    print("bỏ qua đăng ký project:", error)
shutil.rmtree(tmp, ignore_errors=True)
