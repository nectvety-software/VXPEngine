"""Mở project 2 lần liên tiếp + mở khi screens.dtfe bị khóa → không crash."""
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "app"))

from PySide6.QtWidgets import QApplication

import main as ide_main
from project_store import ProjectStore

app = QApplication.instance() or QApplication([])

with tempfile.TemporaryDirectory(prefix="vxp_reopen_") as tmp:
    store = ProjectStore()
    project = store.create_project("ReopenTest", tmp)

    window = ide_main.MainWindow()
    window.show()
    window._open_project(project)
    app.processEvents()
    assert window.editor_page is not None, "mở lần 1 phải dựng được editor_page"
    first_page = window.editor_page
    print("OK  Mở project lần 1")

    # Lần 2: teardown editor_page cũ rồi dựng lại — trước đây crash RuntimeError.
    window._open_project(project)
    app.processEvents()
    assert window.editor_page is not None and window.editor_page is not first_page
    print("OK  Mở lại cùng project lần 2 — teardown an toàn, không RuntimeError")

    # Mở khi screens.dtfe bị khóa cứng (replace hỏng vĩnh viễn) → fallback vẫn dựng được.
    original_replace = Path.replace

    def broken(self, target):
        if str(self).startswith(tmp):
            raise PermissionError(13, "Access is denied", str(target))
        return original_replace(self, target)

    Path.replace = broken

    class _NoDialog:
        def __init__(self, *a, **k):
            pass

        def exec(self, *a, **k):
            return 0

    real_dialog = ide_main.NoticeDialog
    ide_main.NoticeDialog = _NoDialog
    try:
        window._open_project(project)
        app.processEvents()
    finally:
        Path.replace = original_replace
        ide_main.NoticeDialog = real_dialog
    assert window.editor_page is not None, "fallback ghi trực tiếp phải dựng được editor_page"
    print("OK  screens.dtfe bị khóa cứng → fallback ghi trực tiếp, project vẫn mở được")

    if window.viewport_2d is not None:
        window.viewport_2d.scene().blockSignals(True)
    window.close()
    app.processEvents()
    try:
        store.remove(str(project.folder))
    except Exception as error:
        print("bỏ qua đăng ký project:", error)

print("PASS_ALL: mở project an toàn trước khóa file + teardown widget đã hủy")
