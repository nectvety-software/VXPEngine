"""Regression harness for manifest-driven VXPEngine project layout v2."""
import json
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])

from project_store import ProjectStore
from vxp_runner import VxpRunner


with tempfile.TemporaryDirectory() as temp:
    store = ProjectStore()
    project = store.create_project("LayoutV2Harness", temp, viewport_width=320, viewport_height=240)
    root = project.folder
    descriptor = json.loads((root / "project.vxp.json").read_text(encoding="utf-8"))
    assert descriptor["layout_version"] == 2
    assert descriptor["template_version"] == "2.0.0"
    assert (root / ".vxpe/template-state.json").is_file()
    assert (root / ".vxpe/platform/main/CMakeLists.txt").is_file()
    assert (root / "scripts/build_arm.bat").is_file()
    assert not (root / "engine").exists()
    assert not (root / "build-arm").exists()
    assert VxpRunner._project_toolchain(root) == root / ".vxpe/cmake/toolchain-arm-none-eabi.cmake"

    source = root / "src/main.c"
    user_source = source.read_text(encoding="utf-8") + "\n/* user-owned */\n"
    source.write_text(user_source, encoding="utf-8")
    readme = root / "README.md"
    user_readme = "# README do nguoi dung sua\n"
    readme.write_text(user_readme, encoding="utf-8")
    state_path = root / ".vxpe/template-state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["files"]["README.md"]["template_sha256"] = "0" * 64
    state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")
    managed = root / ".vxpe/cmake/AddExecVxp.cmake"
    managed.unlink()

    notices = store.sync_template(project)
    assert managed.is_file(), "missing managed file was not restored"
    assert source.read_text(encoding="utf-8") == user_source, "seed source was overwritten"
    assert readme.read_text(encoding="utf-8") == user_readme, "modified managed file was overwritten"
    assert any("Giữ nguyên" in notice for notice in notices), notices
    print("OK  layout v2 + safe dynamic template sync")

print("PASS_ALL")
