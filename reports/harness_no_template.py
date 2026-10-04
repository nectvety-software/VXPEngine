"""Harness: xác nhận UI mẫu dự án đã bị loại bỏ và tạo project trống vẫn hoạt động."""
import os, sys, tempfile
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

from PySide6.QtWidgets import QApplication
app = QApplication([])

from project_store import PROJECT_TEMPLATES, ProjectStore
assert list(PROJECT_TEMPLATES) == ["blank"], PROJECT_TEMPLATES
print("OK  PROJECT_TEMPLATES chỉ còn blank")

from widgets.home_page import HomePage
home = HomePage()
labels = [btn.text() for btn, _label in home.sidebar_buttons]
assert not hasattr(home, "templates_button"), "templates_button vẫn tồn tại"
assert not hasattr(home, "project_template_requested") or "project_template_requested" not in dir(home)
for widget in home.sidebar.findChildren(type(home.docs_button)):
    assert widget.text() != "Mẫu dự án", "nút Mẫu dự án vẫn còn"
print("OK  Sidebar Home không còn mục 'Mẫu dự án'; buttons =", labels)

from widgets.new_project_dialog import NewProjectDialog
from PySide6.QtWidgets import QLabel
dlg = NewProjectDialog(tempfile.gettempdir())
texts = [child.text() for child in dlg.findChildren(QLabel)]
assert not any(t.startswith("Mẫu:") for t in texts), texts
assert not hasattr(dlg, "template_key")
print("OK  NewProjectDialog không còn thẻ mẫu / template_key")

with tempfile.TemporaryDirectory() as tmp:
    store = ProjectStore()
    project = store.create_project("HarnessBlank", tmp)
    assert (project.folder / "src" / "main.c").exists()
    assert (project.folder / "CMakeLists.txt").exists()
    assert not (project.folder / "signing").exists()
    assert not (project.folder / "engine").exists()
    assert project.template_key == "blank"
    main_c = (project.folder / "src" / "main.c").read_text(encoding="utf-8", errors="replace")
    assert "HarnessBlank" in main_c or "BlankApp" not in main_c
    print("OK  create_project(blank) hoạt động:", project.folder.name, "AppID", project.app_id)

print("PASS_ALL")
