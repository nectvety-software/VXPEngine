"""Regression: Photoshop-style multi-selection and Camera2D block alignment."""
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

from PySide6.QtWidgets import QApplication
from project_store import ProjectStore
from widgets.panels import InspectorPanel
from widgets.viewport import Viewport2D

app = QApplication.instance() or QApplication([])
with tempfile.TemporaryDirectory(prefix="vxpe_align_") as tmp:
    store = ProjectStore(); store.data_dir = Path(tmp) / ".registry"; store.data_dir.mkdir()
    store.registry_path = store.data_dir / "projects.json"
    project = store.create_project("MultiAlign", tmp, viewport_width=320, viewport_height=240)
    scene_path = project.folder / "assets/scenes/main.dtfe"
    viewport = Viewport2D(str(project.folder), scene_path=scene_path)

    nodes = [
        {"id":"a", "name":"A", "type":"Rectangle2D", "position":[-100,-60], "shape":{"width":20,"height":16}},
        {"id":"b", "name":"B", "type":"Rectangle2D", "position":[0,10], "shape":{"width":30,"height":18}},
        {"id":"c", "name":"C", "type":"Rectangle2D", "position":[90,65], "shape":{"width":40,"height":20}},
    ]
    items = [viewport._create_vector_item(node, persist=True) for node in nodes]
    viewport.scene().clearSelection()
    for item in items:
        item.setSelected(True)

    assert viewport.align_selected("left")
    lefts = [round(item.sceneBoundingRect().left(), 3) for item in items]
    assert len(set(lefts)) == 1, lefts

    items[0].setPos(-100, -60); items[1].setPos(0, 10); items[2].setPos(90, 65)
    locked_background = viewport._node_items["bg"]
    locked_background.setSelected(True)
    assert viewport.align_selected("camera_center")
    camera_center = viewport._camera_frame.sceneBoundingRect().center()
    for item in items:
        center = item.sceneBoundingRect().center()
        assert abs(center.x() - camera_center.x()) < .01
        assert abs(center.y() - camera_center.y()) < .01
    assert locked_background.pos().x() == 0 and locked_background.pos().y() == 0

    # The frame-layout command intentionally preserves relative spacing.
    items[0].setPos(-100, -60); items[1].setPos(0, 10); items[2].setPos(90, 65)
    before_offsets = [item.sceneBoundingRect().center() - items[0].sceneBoundingRect().center() for item in items]
    assert viewport._align_selected_block_to_camera("center")
    after_offsets = [item.sceneBoundingRect().center() - items[0].sceneBoundingRect().center() for item in items]
    assert all(abs(a.x()-b.x()) < .01 and abs(a.y()-b.y()) < .01 for a,b in zip(before_offsets, after_offsets))

    assert viewport.align_selected("distribute_h")
    ordered = sorted(items, key=lambda item: item.sceneBoundingRect().left())
    gaps = [ordered[i+1].sceneBoundingRect().left() - ordered[i].sceneBoundingRect().right() for i in range(2)]
    assert abs(gaps[0] - gaps[1]) < .01, gaps

    inspector = InspectorPanel(str(project.folder))
    required = {"left", "center", "distribute_h", "camera_center", "camera_top", "camera_bottom"}
    assert required.issubset(inspector.layer_buttons_by_command)
    inspector.set_selection(viewport._group_payload("") if False else {"kind":"multi", "type":"MultiSelection", "member_count":3})
    assert all(inspector.layer_buttons_by_command[name].isEnabled() for name in required)

print("PASS: multi-align bounds + equal gaps + Camera2D block center + Inspector actions")
