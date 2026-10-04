"""Harness: build ARM (.vxp) trên project e2e design đã tạo (Win32 PASS trước đó)."""
import os, sys
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

from pathlib import Path
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

app = QApplication([])
from vxp_runner import VxpRunner

root = Path(sys.argv[1])
runner = VxpRunner()
state = {"done": False, "success": False, "code": None}
log_lines: list[str] = []

runner.output.connect(lambda text: log_lines.extend(line for line in text.splitlines() if line.strip()))
runner.finished.connect(lambda code, success: state.update(done=True, success=success, code=code))
if not runner.build_arm(str(root)):
    print("RUNNER_REFUSED\n" + "\n".join(log_lines[-20:]))
    sys.exit(1)

timer = QTimer()
timer.setInterval(200)
deadline = 480.0

def pump() -> None:
    global deadline
    deadline -= 0.2
    if state["done"] or deadline <= 0:
        timer.stop()
        app.quit()

timer.timeout.connect(pump)
timer.start()
app.exec()

tail = "\n".join(log_lines[-30:])
if not state["done"]:
    print("TIMEOUT\n" + tail); sys.exit(2)
if not state["success"]:
    print("BUILD_FAIL\n" + tail); sys.exit(1)

artifacts = sorted((root / "build-arm").rglob("*.vxp"))
assert artifacts, "không thấy .vxp trong build-arm"
print("OK  Build ARM (.vxp) thành công:", artifacts[-1])
print("PASS_ALL")
