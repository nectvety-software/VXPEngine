"""Regression: component BackgroundBitmap previews, persists and exports."""
import json
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

from PySide6.QtCore import QRectF
from PySide6.QtGui import QImage, QPainter
from PySide6.QtWidgets import QApplication
from design_export import export_design_sprites
from project_store import ProjectStore
from scene_screen_store import ScreenStore
from widgets.panels import InspectorPanel
from widgets.viewport import Viewport2D

app = QApplication.instance() or QApplication([])

with tempfile.TemporaryDirectory(prefix="vxpe_bgbitmap_") as tmp:
    store = ProjectStore(); store.data_dir = Path(tmp) / ".registry"; store.data_dir.mkdir()
    store.registry_path = store.data_dir / "projects.json"
    project = store.create_project("BackgroundBitmap", tmp)
    scene_path = project.folder / "assets/scenes/main.dtfe"

    source = Path(tmp) / "button_skin.png"
    image = QImage(12, 6, QImage.Format.Format_ARGB32)
    image.fill(0xFFFF8A3D)
    assert image.save(str(source))

    viewport = Viewport2D(str(project.folder), scene_path=scene_path)
    button = viewport._create_vector_item({
        "id":"play_button", "name":"PlayButton", "type":"Rectangle2D", "position":[0,0],
        "component_category":"ui", "ui_role":"Button",
        "shape":{"width":96,"height":32,"corner_radius":7,"fill":"#182336","stroke":"#ffffff"},
    }, persist=True)
    assert button is not None
    viewport.update_selected_property("background_bitmap", str(source))
    button.metadata["group_id"] = "button_group"
    viewport._add_group({
        "id":"button_group", "name":"Nút bấm", "type":"Group2D", "ui_role":"Button",
        "component_category":"ui", "opacity":1.0, "visible":True, "locked":False, "z_index":0,
    })
    viewport._selected_group_id = "button_group"
    viewport.update_selected_property("background_bitmap_mode", "Fit")
    viewport._save_scene()

    assert not button._background_pixmap.isNull()
    preview = QImage(240, 320, QImage.Format.Format_ARGB32)
    preview.fill(0xFF000000)
    painter = QPainter(preview)
    viewport.scene().render(painter, QRectF(0, 0, 240, 320), viewport._camera_frame.rect())
    painter.end()
    center_color = preview.pixelColor(120, 160)
    assert center_color.red() > 220 and center_color.green() > 90, center_color.name()
    saved = json.loads(scene_path.read_text(encoding="utf-8"))
    node = next(item for item in saved["children"] if item.get("id") == "play_button")
    assert node["background_bitmap"].startswith("assets/imported/")
    assert node["background_bitmap_mode"] == "Fit"

    inspector = InspectorPanel(str(project.folder))
    inspector.set_selection(viewport._group_payload("button_group"))
    assert inspector.background_bitmap.text() == node["background_bitmap"]
    assert inspector.background_bitmap_mode.currentText() == "Fit"
    assert inspector.background_bitmap_row.isVisibleTo(inspector.form)

    header = ScreenStore(project.folder).generate_c_bindings().read_text(encoding="utf-8")
    assert 'MAIN_PLAYBUTTON_BACKGROUND_BITMAP "assets/imported/button_skin.png"' in header
    assert 'MAIN_PLAYBUTTON_BACKGROUND_BITMAP_MODE "Fit"' in header
    assert export_design_sprites(project.folder) == 1
    raw = project.folder / "resources/gen/main_playbutton.raw"
    assert raw.is_file() and raw.stat().st_size > 8
    blob = raw.read_bytes()
    assert (blob[0] | blob[1] << 8, blob[2] | blob[3] << 8) == (96, 32)

print("PASS: BackgroundBitmap chooser/model -> Camera2D preview -> DTFE/C/raw")
