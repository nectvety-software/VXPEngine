"""Harness e2e: project trống + thiết kế Camera 2D → build ARM (.vxp).

Xác nhận: scene_bindings.h mới (bảng component) và sprite .raw xuất từ thiết kế
được nạp vào pipeline build thật; main.c theo thiết kế biên dịch thành công.
"""
import os, sys, tempfile
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

import json
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication

app = QApplication([])

from project_store import ProjectStore
from scene_screen_store import ScreenStore
from design_export import export_design_sprites
from vxp_runner import VxpRunner

tmp = tempfile.mkdtemp(prefix="vxp_e2e_design_")
store = ProjectStore()
project = store.create_project("HarnessBuildDesign", tmp)
root = project.folder

asset_dir = root / "assets" / "map" / "texture"
asset_dir.mkdir(parents=True, exist_ok=True)
img = QImage(24, 16, QImage.Format.Format_ARGB32)
img.fill(0xFF2F7EF7)
assert img.save(str(asset_dir / "hero.png"))

scene_path = root / "assets" / "scenes" / "main.dtfe"
scene = json.loads(scene_path.read_text(encoding="utf-8"))
scene["children"] = [
    {
        "id": "n1", "name": "Hero", "code_name": "Hero", "type": "Sprite2D",
        "asset": "assets/map/texture/hero.png",
        "position": [0, 0], "rotation": 0.0, "scale": [1, 1],
        "display_size": [48, 32], "z_index": 1, "visible": True,
        "opacity": 1, "blend_mode": "Normal", "tint": "#FFFFFFFF",
        "events": [], "automation": {}, "clipping_mask": {},
    },
]
scene_path.write_text(json.dumps(scene, indent=2), encoding="utf-8")

screens = ScreenStore(root)
screens.generate_c_bindings()
exported = export_design_sprites(root)
assert exported == 1, exported
header_text = (root / "src" / "scene_bindings.h").read_text(encoding="utf-8")
assert "MAIN_DESIGN_COMPONENTS[1]" in header_text
raw_files = list((root / "resources" / "gen").glob("main_hero*.raw"))
assert raw_files, "thiếu sprite .raw trong resources/gen"
print("OK  Thiết kế + sprite .raw sẵn sàng:", raw_files[0].name)

runner = VxpRunner()
state = {"done": False, "success": False, "code": None}
log_lines: list[str] = []

def on_output(text: str) -> None:
    for line in text.splitlines():
        if line.strip():
            log_lines.append(line)

def on_finished(code: int, success: bool) -> None:
    state["done"] = True
    state["success"] = success
    state["code"] = code

runner.output.connect(on_output)
runner.finished.connect(on_finished)
assert runner.build_arm(str(root)), "runner từ chối build ARM"

timer = QTimer()
timer.setInterval(200)
deadline = 480  # giây

def pump() -> None:
    global deadline
    deadline -= 0.2
    if state["done"] or deadline <= 0:
        timer.stop()
        app.quit()

timer.timeout.connect(pump)
timer.start()
app.exec()

tail = "\n".join(log_lines[-25:])
if not state["done"]:
    print("TIMEOUT\n" + tail)
    sys.exit(2)
if not state["success"]:
    print("BUILD_FAIL\n" + tail)
    sys.exit(1)

artifact = root / "build-arm" / "main" / f"{project.app_name}.vxp"
assert artifact.exists(), f"thiếu artifact {artifact}"
print("OK  Build ARM thành công với thiết kế:", artifact.name)
print("PASS_ALL")
