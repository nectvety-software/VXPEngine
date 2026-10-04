"""Regression: fixed background, phone bezel, Camera2D bounds and alignment."""
import json
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

from PySide6.QtCore import QPointF
from PySide6.QtWidgets import QApplication
from project_store import ProjectStore
from widgets.viewport import Viewport2D

app = QApplication.instance() or QApplication([])
with tempfile.TemporaryDirectory(prefix="vxpe_bounds_") as tmp:
    store = ProjectStore(); store.data_dir = Path(tmp) / ".registry"; store.data_dir.mkdir()
    store.registry_path = store.data_dir / "projects.json"
    project = store.create_project("BoundsDemo", tmp, viewport_width=240, viewport_height=320)
    scene_path = project.folder / "assets/scenes/main.dtfe"
    scene = json.loads(scene_path.read_text(encoding="utf-8"))
    background = next(node for node in scene["children"] if node.get("id") == "bg")
    assert background["shape"]["width"] == 240 and background["shape"]["height"] == 320
    assert background["locked"] and not background["resizable"] and background["lock_aspect"]

    viewport = Viewport2D(str(project.folder), scene_path=scene_path)
    assert viewport._camera_bezel is not None
    assert viewport._camera_bezel.boundingRect().contains(viewport._camera_frame.rect())
    bg_item = viewport._node_items["bg"]
    assert viewport._item_payload(bg_item)["display_size"] == [240.0, 320.0]
    viewport.select_node({"id":"bg", "type":"Rectangle2D", "name":"Background"})
    viewport.update_selected_property("size_width", 999)
    assert viewport._item_payload(bg_item)["display_size"] == [240.0, 320.0]

    node = {"id":"card", "name":"Card", "type":"Rectangle2D", "position":[0,0],
            "shape":{"width":40,"height":20,"fill":"#FFFFFF","stroke":"#00000000","stroke_width":0},
            "scale":[1,1], "resizable":True, "pixel_snap":False}
    card = viewport._create_vector_item(node, persist=True)
    viewport.update_selected_property("position_x", 999)
    assert card.sceneBoundingRect().right() <= viewport._camera_frame.rect().right() + 0.01
    viewport.update_selected_property("size_width", 999)
    assert viewport._item_payload(card)["display_size"][0] <= 240.01
    assert viewport.align_selected("camera_hcenter")
    assert abs(card.sceneBoundingRect().center().x() - viewport._camera_frame.rect().center().x()) < 0.01

print("PASS: fixed background + bezel + bounds + Camera2D alignment")
