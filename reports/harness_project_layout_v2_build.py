"""Create a layout-v2 project and compile a real ARM .vxp."""
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])

from project_store import ProjectStore
from vxp_runner import VxpRunner


with tempfile.TemporaryDirectory() as temp:
    project = ProjectStore().create_project("LayoutV2Arm", temp)
    runner = VxpRunner()
    loop = QEventLoop()
    state = {"done": False, "ok": False}
    logs: list[str] = []
    runner.output.connect(logs.append)

    def finished(_code: int, ok: bool) -> None:
        state.update(done=True, ok=bool(ok))
        loop.quit()

    runner.finished.connect(finished)
    timer = QTimer()
    timer.setSingleShot(True)
    timer.timeout.connect(loop.quit)
    timer.start(180000)
    assert runner.build_arm(str(project.folder)), "VxpRunner refused layout-v2 build"
    loop.exec()
    if not state["done"] or not state["ok"]:
        raise AssertionError("ARM build failed/timeout:\n" + "\n".join(logs[-80:]))
    artifact = project.folder / "build-arm/main/layoutv2arm.vxp"
    assert artifact.is_file() and artifact.stat().st_size > 0, artifact
    print(f"OK  real ARM layout-v2 build: {artifact.name} ({artifact.stat().st_size} bytes)")

print("PASS_ALL")
