"""Harness: main.c trống cũ phải được nâng cấp lên bản vẽ theo bảng thiết kế.

Kiểm chứng refresh_legacy_main_c():
- project có main.c trống cũ nguyên vẹn (dibo) → được thay bằng bản template
  mới (include scene_bindings.h), lần gọi thứ hai không thay nữa;
- project có main.c tự viết (Heros) → giữ nguyên từng byte.
"""
import os
import shutil
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

APP = Path(__file__).resolve().parent.parent / "app"
sys.path.insert(0, str(APP))

from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or QApplication(sys.argv)

from design_export import LEGACY_BLANK_MARKER, refresh_legacy_main_c  # noqa: E402

DIBO = Path(os.environ.get("VXP_LEGACY_DIBO", r"C:\Users\doxuanhop\Documents\VXP Projects\dibo"))
HEROS = Path(os.environ.get("VXP_LEGACY_HEROS", r"C:\Users\doxuanhop\Documents\VXP Projects\Heros"))

SKIP = {"build-win32", "build-arm", "build-arm-signed", "__pycache__"}

tmp = Path(tempfile.mkdtemp(prefix="vxpe_legacy_"))
try:
    legacy = tmp / "legacy"
    shutil.copytree(DIBO, legacy, ignore=shutil.ignore_patterns(*SKIP))
    custom = tmp / "custom"
    shutil.copytree(HEROS, custom, ignore=shutil.ignore_patterns(*SKIP))

    legacy_main = legacy / "src" / "main.c"
    assert LEGACY_BLANK_MARKER in legacy_main.read_text(encoding="utf-8"), "bản sao dibo phải mang main.c trống cũ"

    assert refresh_legacy_main_c(legacy) is True, "phải nâng cấp main.c trống cũ"
    upgraded = legacy_main.read_text(encoding="utf-8")
    assert "scene_bindings.h" in upgraded and "draw_design" in upgraded, "main.c mới phải vẽ theo bảng thiết kế"
    assert LEGACY_BLANK_MARKER not in upgraded
    print("PASS: main.c trống cũ được nâng cấp sang bản vẽ theo thiết kế")

    assert refresh_legacy_main_c(legacy) is False, "gọi lại không được ghi đè nữa"
    print("PASS: nâng cấp idempotent")

    from scene_screen_store import ScreenStore
    from design_export import export_design_sprites

    ScreenStore(legacy).generate_c_bindings()
    exported = export_design_sprites(legacy)
    bindings = (legacy / "src" / "scene_bindings.h").read_text(encoding="utf-8")
    assert "VXP_DESIGN_ACTIVE_HAS_DESIGN" in bindings and "_HAS_DESIGN 1" in bindings, (
        "bảng thiết kế dibo phải có component"
    )
    print(f"PASS: flush trước build (bindings + {exported} sprite .raw) trên bản sao")

    custom_main = custom / "src" / "main.c"
    before = custom_main.read_bytes()
    assert refresh_legacy_main_c(custom) is False, "main.c tự viết không được đụng tới"
    assert custom_main.read_bytes() == before
    print("PASS: main.c tự viết giữ nguyên")

    print("PASS_ALL: main.c cũ không phá đồng nhất build/giả lập")
    print("TMP_PROJECT_FOR_BUILD=" + str(legacy))
    print("TMP_ROOT=" + str(tmp))
except Exception:
    shutil.rmtree(tmp, ignore_errors=True)
    raise
