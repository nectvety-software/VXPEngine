"""Regression: Inspector exact size/gameplay fields + Asset Editor demo factory."""
import json
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))
sys.path.insert(0, str(ROOT / "tools"))

from PySide6.QtWidgets import QApplication
from demo_project_factory import create_demo_suite
from widgets.panels import InspectorPanel
from widgets.viewport import Viewport2D

app = QApplication.instance() or QApplication([])
with tempfile.TemporaryDirectory(prefix="vxpe_specialist_") as tmp:
    app_root, game_root = create_demo_suite(Path(tmp))
    assert (app_root / "assets/map/background/toolkit_background_240x320.png").is_file()
    assert (game_root / "assets/scenes/villager.asset.dtfe").is_file(), "Asset Editor metadata missing"

    scene_path = game_root / "assets/scenes/main.dtfe"
    viewport = Viewport2D(str(game_root), scene_path=scene_path)
    inspector = InspectorPanel(str(game_root))
    inspector.property_changed.connect(viewport.update_selected_property)
    viewport.selection_changed.connect(inspector.set_selection)
    viewport.select_node({"id": "worker1", "name": "Villager", "type": "Sprite2D"})

    inspector.lock_aspect.setChecked(True)
    inspector.size_width.setValue(36)
    app.processEvents()
    payload = viewport._item_payload(viewport._node_items["worker1"])
    assert payload["display_size"] == [36.0, 48.0], payload["display_size"]

    inspector.lock_aspect.setChecked(False)
    inspector.size_height.setValue(44)
    inspector.anchor_mode.setCurrentText("Bottom")
    inspector.pixel_snap.setChecked(False)
    inspector.collision_enabled.setChecked(True)
    inspector.collision_shape.setCurrentText("circle")
    inspector.physics_mode.setCurrentText("kinematic")
    viewport._save_scene()
    saved = json.loads(scene_path.read_text(encoding="utf-8"))
    worker = next(node for node in saved["children"] if node.get("id") == "worker1")
    assert worker["display_size"] == [36.0, 44.0], worker
    assert worker["anchor"] == {"mode":"Bottom", "x":0.5, "y":1.0}
    assert worker["pixel_snap"] is False
    assert worker["automation"]["collision_shape"] == "circle"
    assert worker["automation"]["physics"] == "kinematic"

    header = game_root / "src/scene_bindings.h"
    from scene_screen_store import ScreenStore
    ScreenStore(game_root).generate_c_bindings()
    text = header.read_text(encoding="utf-8")
    assert "MAIN_VILLAGER_DISPLAY_WIDTH 36.0000f" in text
    assert 'MAIN_VILLAGER_COLLISION_SHAPE "circle"' in text
    assert "MAIN_VILLAGER_COLLISION_ENABLED 1" in text
    assert 'MAIN_VILLAGER_ANCHOR_MODE "Bottom"' in text
    assert "MAIN_VILLAGER_PIXEL_SNAP 0" in text
    print("OK  Inspector W/H, aspect, anchor, pixel snap, collision, physics -> DTFE/C")
    print("OK  Asset Editor created portrait utility app + isometric strategy game")

print("PASS_ALL")
