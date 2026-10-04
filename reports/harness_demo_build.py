"""Build both permanent demo projects through VXPEngine's real ARM pipeline."""
import json
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtWidgets import QApplication
from design_export import export_design_sprites
from scene_screen_store import ScreenStore
from vxp_runner import VxpRunner

app = QApplication.instance() or QApplication([])


def build(root: Path) -> Path:
    descriptor = json.loads((root / "project.vxp.json").read_text(encoding="utf-8"))
    app_name = str(descriptor["app_name"])
    ScreenStore(root).generate_c_bindings()
    assert export_design_sprites(root) > 0
    runner = VxpRunner()
    loop = QEventLoop()
    state = {"done": False, "ok": False}

    def finished(_code: int, ok: bool) -> None:
        state.update(done=True, ok=bool(ok))
        loop.quit()

    runner.finished.connect(finished)
    timer = QTimer(); timer.setSingleShot(True); timer.timeout.connect(loop.quit); timer.start(180000)
    assert runner.build_arm(str(root)), f"build refused: {root.name}"
    loop.exec()
    assert state["done"] and state["ok"], f"ARM build failed/timeout: {root.name}"
    artifact = root / "build-arm" / "main" / f"{app_name}.vxp"
    assert artifact.is_file() and artifact.stat().st_size > 0, artifact
    print(f"OK  {root.name}: {artifact.name} ({artifact.stat().st_size} bytes)")
    return artifact


build(ROOT / "examples" / "PocketToolkitDemo")
build(ROOT / "examples" / "IsometricOutpostDemo")
print("PASS_ALL")
