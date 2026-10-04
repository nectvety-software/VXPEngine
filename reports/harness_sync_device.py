"""Harness: đồng bộ 100% giả lập/build, sync hai chiều code↔Preview, debugger, update 404."""
import json
import os
import shutil
import sys
import tempfile
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

from PySide6.QtGui import QImage, QPainter
from PySide6.QtWidgets import QApplication

app = QApplication([])


def read_u16(image: QImage, x: int, y: int) -> int:
    """Đọc pixel RGB565 từ QImage Format_RGB16 (little-endian)."""
    data = bytes(image.constBits())
    offset = y * image.bytesPerLine() + x * 2
    return data[offset] | (data[offset + 1] << 8)


# ---------------------------------------------------------------- Update 404
from PySide6.QtNetwork import QNetworkReply

import update_checker as uc_module


class FakeReply:
    def __init__(self, status, error):
        self._status = status
        self._error = error

    def attribute(self, _attr):
        return self._status

    def error(self):
        return self._error

    def errorString(self):
        return "Error transferring ... server replied with status code 404"

    def readAll(self):
        return b""

    def deleteLater(self):
        pass


checker = uc_module.UpdateChecker("1.0.0")
channel_missing = []
failed_messages = []
checker.channel_unavailable.connect(lambda: channel_missing.append(True))
checker.failed.connect(lambda message: failed_messages.append(message))

network_calls = []


def fake_get(request):
    network_calls.append(request)

    class _Sig:
        def connect(self, *_args):
            pass

    class _Reply:
        finished = _Sig()

    return _Reply()


checker.network.get = fake_get

checker._finished(FakeReply(404, QNetworkReply.NetworkError.ContentNotFoundError))
assert channel_missing == [True], "404 phải phát channel_unavailable"
assert not failed_messages, "404 không được báo như lỗi transfer"
checker.check(manual=False)  # tự động sau khi biết kênh mất → bỏ qua mạng
checker.check(manual=True)  # thủ công vẫn thử lại
assert len(network_calls) == 1, network_calls
print("OK  Update 404 → thông tin thân thiện, auto-check không gọi mạng nữa")

# ------------------------------------------------------- design_render pixel
import design_render
from design_export import export_design_sprites
from project_store import ProjectStore

tmp_root = tempfile.mkdtemp(prefix="vxp_sync_harness_")
store = ProjectStore()
project = store.create_project("HarnessSync", tmp_root)
project_root = project.path if hasattr(project, "path") else None
from pathlib import Path

project_root = Path(project.path)

# Ảnh nguồn 16x16 đỏ đặc.
red = QImage(16, 16, QImage.Format.Format_ARGB32)
red.fill(0xFFFF0000)
texture_dir = project_root / "assets" / "map" / "texture"
texture_dir.mkdir(parents=True, exist_ok=True)
red_path = texture_dir / "red.png"
red.save(str(red_path))

from scene_screen_store import ScreenStore

scene_store = ScreenStore(project_root)
registry = scene_store.ensure()
main_file = project_root / registry["screens"][0]["file"]
scene = json.loads(main_file.read_text(encoding="utf-8"))
scene.setdefault("children", []).extend([
    {
        "id": "rect1", "name": "Block", "code_name": "Block", "type": "Rectangle2D",
        "position": [-50, 40], "rotation": 0.0, "scale": [1, 1], "opacity": 1.0,
        "z_index": 0, "visible": True,
        "shape": {"width": 30, "height": 20, "fill": "#31445E", "stroke": "#A9B3C6", "stroke_width": 2},
        "display_size": [30, 20],
    },
    {
        "id": "spr1", "name": "Red", "code_name": "Red", "type": "Sprite2D",
        "position": [10, -20], "rotation": 0.0, "scale": [1, 1], "opacity": 1.0,
        "z_index": 1, "visible": True, "asset": "assets/map/texture/red.png",
        "display_size": [16, 16],
    },
])
main_file.write_text(json.dumps(scene, ensure_ascii=False, indent=2), encoding="utf-8")

exported = export_design_sprites(project_root)
assert exported >= 1, "phải xuất ít nhất một sprite .raw"

rows = design_render.active_design_rows(project_root)
ids = [row["id"] for row in rows]
assert "rect1" in ids and "spr1" in ids, ids
assert ids.index("rect1") < ids.index("spr1"), "phải sắp theo z_index như bảng C"

frame = design_render.render_design_frame(project_root, rows)
assert frame.width() == 240 and frame.height() == 320
assert frame.format() == QImage.Format.Format_RGB16

# Sprite đỏ tâm (120+10, 160-20) = (130, 140): đỏ gần tuyệt đối trong RGB565.
sprite_pixel = read_u16(frame, 130, 140)
r = (sprite_pixel >> 11) & 0x1F
g = (sprite_pixel >> 5) & 0x3F
b = sprite_pixel & 0x1F
assert r >= 28 and g <= 4 and b <= 4, (r, g, b)

# Rectangle fallback tâm (120-50, 160+40) = (70, 200): màu RGB565(150,168,200).
expected_rect = design_render._rgb565(150, 168, 200)
assert read_u16(frame, 70, 200) == expected_rect, hex(read_u16(frame, 70, 200))

default_frame = design_render.render_default_frame(0)
expected_bg = design_render._rgb565(10, 18, 32)
assert read_u16(default_frame, 0, 0) == expected_bg
print("OK  design_render giống từng pixel với draw_design/draw_default của máy")

# --------------------------------------------------- MainWindow tích hợp
import main as ide_main

window = ide_main.MainWindow()
window.show()
window._open_project(project)
app.processEvents()

viewport = window.viewport_2d
assert viewport is not None, "phải mở Frame Preview"
assert str(viewport.scene_file) == str(main_file), viewport.scene_file

sim = window._open_simulator_window()
assert sim is not None and sim.isVisible()
window._sync_simulator_screen()
app.processEvents()
screen_image = sim.frame._screen._scene_image
assert screen_image is not None and screen_image.width() == 240 and screen_image.height() == 320
assert screen_image.format() == QImage.Format.Format_RGB16, "giả lập phải nhận khung RGB565 của thiết bị"
assert read_u16(screen_image, 130, 140) == sprite_pixel, "giả lập phải giống framebuffer build"
print("OK  Giả lập hiển thị đúng khung RGB565 mà bản build vẽ")

# --- Design → code: đổi vị trí trong Frame Preview, tab .dtfe phải cập nhật.
window._open_asset_file(str(main_file))
editor = window.code_editors.get(main_file.resolve())
assert editor is not None, "phải mở .dtfe trong code editor"
viewport.select_node({"id": "spr1"})
item = viewport._node_items.get("spr1")
assert item is not None, "không tìm thấy node sprite trong viewport"
viewport.scene().clearSelection()
item.setSelected(True)
viewport.update_selected_property("position_x", 40.0)
viewport.update_selected_property("position_y", 25.0)
for _ in range(20):
    app.processEvents()
    time.sleep(0.05)
editor_text = editor.toPlainText()
assert "40.0" in editor_text and "25.0" in editor_text, "code .dtfe chưa cập nhật theo thiết kế"
assert not editor.document().isModified(), "tab .dtfe phải được đồng bộ, không ở trạng thái chưa lưu"
print("OK  Design → code: Frame Preview đổi là tab .dtfe cập nhật realtime")

# --- Code → design: sửa scene trên đĩa (như editor ngoài), Preview tự nạp lại.
scene_now = json.loads(main_file.read_text(encoding="utf-8"))
scene_now["children"].append({
    "id": "circle9", "name": "Circle9", "code_name": "Circle9", "type": "Circle2D",
    "position": [0, 0], "rotation": 0.0, "scale": [1, 1], "opacity": 1.0,
    "z_index": 2, "visible": True,
    "shape": {"radius": 12, "fill": "#5EEAD4", "stroke": "#FFFFFF", "stroke_width": 1},
    "display_size": [24, 24],
})
main_file.write_text(json.dumps(scene_now, ensure_ascii=False, indent=2), encoding="utf-8")
deadline = time.monotonic() + 3.0
while time.monotonic() < deadline:
    app.processEvents()
    if any(payload.get("id") == "circle9" for payload in viewport._scene_payload.get("children", [])):
        break
    time.sleep(0.05)
assert any(child.get("id") == "circle9" for child in viewport._scene_payload.get("children", [])), \
    "Frame Preview không nạp lại scene sau khi code đổi"
assert any(node_id == "circle9" for node_id in viewport._node_items), "node mới chưa dựng trong viewport"
print("OK  Code → design: tệp .dtfe đổi là Frame Preview cập nhật realtime")

# --- Debugger.
window._handle_debug_command("stack")
window._handle_debug_command("locals")
window._handle_debug_command("threads")
assert window.debugger_panel is not None
debug_text = window.debugger_panel.output.toPlainText()
assert "Chồng component" in debug_text, debug_text
assert "Trạng thái tiến trình" in debug_text
window._handle_debug_command("pause")
assert window._debug_paused and not window._sim_sync_timer.isActive()
tick_before = window._device_tick
window._handle_debug_command("step_over")
assert window._device_tick == tick_before + 8
window._handle_debug_command("continue")
assert not window._debug_paused and window._sim_sync_timer.isActive()
print("OK  Debugger: pause/step/continue + stack/locals/threads hoạt động thật")

window._sync_simulator_screen()
app.processEvents()

viewport.scene().blockSignals(True)
window.close()
app.processEvents()
store.remove(project.path)
shutil.rmtree(tmp_root, ignore_errors=True)
print("PASS_ALL: SYNC_DEVICE")
