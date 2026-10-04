r"""Offscreen harness: logic mới của toolbar/nav giả lập + debug_command.

Chạy: .venv\Scripts\python.exe reports\harness_sim_tools.py
"""
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "simulator"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "app"))

from PySide6.QtWidgets import QApplication

app = QApplication(sys.argv)

from frame_simulator_qt import FrameSimulator  # noqa: E402

tmp = Path(tempfile.mkdtemp(prefix="vxp_sim_tools_"))

win = FrameSimulator()
frame = win.frame
frame._captures_dir = lambda: tmp  # không chạm Pictures thật
frame._open_in_explorer = lambda path: None  # không bật Explorer offscreen

keys: list[str] = []
artifacts: list[str] = []
captures: list[str] = []
resyncs = []
frame.key_pressed.connect(keys.append)
frame.artifact_loaded.connect(artifacts.append)
frame.capture_saved.connect(captures.append)
frame.resync_requested.connect(lambda: resyncs.append(1))

# --- zoom toggle + window resize
assert frame.zoom == 1.0
frame._on_tool("zoom")
assert frame.zoom == 2.0, frame.zoom
assert win.width() == 520 + 240 and win.height() == 782 + 320, (win.width(), win.height())
frame._on_tool("zoom")
assert frame.zoom == 1.0
assert win.width() == 520 and win.height() == 782

# --- capture
frame._on_tool("capture")
assert len(captures) == 1 and Path(captures[0]).is_file(), captures
assert Path(captures[0]).stat().st_size > 0

# --- new folder
frame._on_tool("new_folder")
folders = [p for p in tmp.iterdir() if p.is_dir() and p.name.startswith("capture_")]
assert folders, list(tmp.iterdir())

# --- gallery (chỉ mở thư mục — đã no-op)
frame._on_tool("gallery")

# --- resync
frame._on_tool("resync")
assert resyncs == [1]

# --- record: 3 khung hình rồi dừng, ffmpeg ghép mp4
frame._on_tool("record")
assert frame._recording and frame._tool_action_buttons["record"].isChecked()
frame._record_frame()
frame._record_frame()
frame._record_frame()
frame._on_tool("record")
assert not frame._recording and not frame._tool_action_buttons["record"].isChecked()
rec_dirs = [p for p in tmp.iterdir() if p.is_dir() and p.name.startswith("record_")]
assert rec_dirs and len(list(rec_dirs[0].glob("frame_*.png"))) == 3
videos = list(tmp.glob("record_*.mp4"))
print("VIDEO:", videos[0].name if videos else "KHONG (ffmpeg thiếu)")

# --- nav keys
before = frame._screen.subject
frame._on_nav("Xoá")
assert keys and keys[-1] == "DELETE"
assert frame._screen.subject == before[:-1], (before, frame._screen.subject)
frame._on_nav("OK")
assert keys[-1] == "OK"
frame._on_nav("Lên")
assert keys[-1] == "UP"
frame._on_nav("Quay lại")
assert keys[-1] == "BACK"
frame._on_nav("Nhập")
assert keys[-1] == "ENTER"

# --- artifact_loaded (mô phỏng chọn tệp từ dialog)
frame.artifact_loaded.emit(str(tmp / "x.vxp"))
assert artifacts and artifacts[0].endswith("x.vxp")

# --- VxpRunner.debug_command trả lời trung thực vào debugger_output
from vxp_runner import VxpRunner  # noqa: E402

runner = VxpRunner()
notes: list[str] = []
runner.debugger_output.connect(notes.append)
runner.debug_command("stack")
runner.debug_command("continue")
runner.debug_command("weird")
assert len(notes) == 3, notes
assert "call stack" in notes[0]
assert "breakpoint" in notes[1]
assert "chưa được hỗ trợ" in notes[2]

print("SIM_TOOLS_PASS")
