"""Regression: RGB picker fields and editable text/layout styles persist to DTFE/C."""
import json
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

from PySide6.QtCore import QPoint, QRect
from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QApplication, QWidget
from color_utils import format_hex, parse_color
from project_store import ProjectStore
from scene_screen_store import ScreenStore
from widgets.custom_dialog import ColorPickerDialog
from widgets.panels import InspectorPanel, _ColorInput, _PixelMagnifierOverlay
from widgets.viewport import Viewport2D

app = QApplication.instance() or QApplication([])
assert format_hex(parse_color("rgb(89, 99, 110)")) == "#59636e"

# A palette opened from a nested Inspector control must center on the main
# window, not use the child's local frame coordinates.
screen_area = QApplication.primaryScreen().availableGeometry()
host = QWidget(); host.resize(700, 500)
host.move(screen_area.center().x() - 350, screen_area.center().y() - 250); host.show()
nested_color = _ColorInput(parent=host)
dialog = ColorPickerDialog(QColor("#ff8a3d"), nested_color)
dialog.show(); QApplication.processEvents()
assert abs(dialog.frameGeometry().center().x() - host.frameGeometry().center().x()) <= 3
assert abs(dialog.frameGeometry().center().y() - host.frameGeometry().center().y()) <= 3
dialog.close(); host.close()

# Pixel lens samples exact screen coordinates from its cached desktop image.
lens = _PixelMagnifierOverlay()
sample = QImage(3, 3, QImage.Format.Format_ARGB32); sample.fill(QColor("#123456"))
lens._screens = [(QRect(10, 20, 3, 3), sample)]
assert lens._color_at(QPoint(11, 21)).name() == "#123456"
lens.close()

with tempfile.TemporaryDirectory(prefix="vxpe_styles_") as tmp:
    store = ProjectStore(); store.data_dir = Path(tmp) / ".registry"; store.data_dir.mkdir()
    store.registry_path = store.data_dir / "projects.json"
    project = store.create_project("StyleInspector", tmp)
    scene_path = project.folder / "assets/scenes/main.dtfe"
    viewport = Viewport2D(str(project.folder), scene_path=scene_path)
    shape = viewport._create_vector_item({
        "id":"panel", "name":"Panel", "type":"Rectangle2D", "position":[0,0],
        "shape":{"width":100,"height":40,"fill":"#000000","stroke":"#FFFFFF"},
    }, persist=True)
    viewport.update_selected_property("fill_color", "#ff8a3d")
    viewport.update_selected_property("corner_radius", 12)
    viewport.update_selected_property("padding", 8)
    viewport.update_selected_property("margin", 6)
    assert shape.brush().color().name() == "#ff8a3d"
    assert shape.path().elementCount() > 5

    text = viewport._create_text_item({
        "id":"title", "name":"Title", "type":"Text2D", "position":[0,0],
        "text":{"content":"Hello", "font":"Segoe UI", "font_size":14, "color":"#FFFFFF"},
    }, persist=True)
    viewport.update_selected_property("text_color", "#59636e")
    viewport.update_selected_property("font_bold", True)
    viewport.update_selected_property("font_italic", True)
    viewport.update_selected_property("font_underline", True)
    viewport.update_selected_property("font_strikeout", True)
    viewport.update_selected_property("padding", 9)
    viewport.update_selected_property("margin", 7)
    viewport._save_scene()

    saved = json.loads(scene_path.read_text(encoding="utf-8"))
    panel = next(node for node in saved["children"] if node.get("id") == "panel")
    title = next(node for node in saved["children"] if node.get("id") == "title")
    assert panel["shape"]["fill"] == "#ff8a3d" and panel["shape"]["corner_radius"] == 12
    assert panel["layout"] == {"padding":8, "margin":6}
    assert title["text"]["color"] == "#59636e"
    assert all(title["text"][key] for key in ("bold","italic","underline","strikeout"))
    assert title["layout"] == {"padding":9, "margin":7}

    inspector = InspectorPanel(str(project.folder))
    inspector.set_selection(viewport._item_payload(text))
    assert inspector.fill_color.palette_button is not None and inspector.fill_color.eyedrop_button is not None
    assert inspector.text_color.value() == "#59636e"
    assert inspector.font_bold.isChecked() and inspector.font_italic.isChecked()

    header = ScreenStore(project.folder).generate_c_bindings().read_text(encoding="utf-8")
    assert "MAIN_TITLE_PADDING 9" in header
    assert 'MAIN_TITLE_TEXT_COLOR "#59636e"' in header
    assert "MAIN_TITLE_FONT_BOLD 1" in header and "MAIN_PANEL_CORNER_RADIUS 12.0000f" in header

print("PASS: hex palette/Pick Color + typography + padding/margin/radius -> DTFE/C")
