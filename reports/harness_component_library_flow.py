"""Regression harness for Component Library -> Camera2D -> DTFE/C bindings."""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

from PySide6.QtCore import QEventLoop, QMimeData, QPointF, QTimer, Qt, QUrl
from PySide6.QtGui import QDragEnterEvent, QDropEvent, QImage
from PySide6.QtWidgets import QApplication

from scene_screen_store import ScreenStore
from widgets.panels import FRAME_PERSPECTIVES, pixel_background_templates, TitleSetLibraryPanel, UI_COMPONENTS
from widgets.viewport import Viewport2D


app = QApplication.instance() or QApplication([])

with tempfile.TemporaryDirectory(prefix="vxp_component_library_") as temporary:
    workspace = Path(temporary)
    project = workspace / "project"
    project.mkdir()
    store = ScreenStore(project)
    store.ensure()
    scene_path = project / "assets" / "scenes" / "main.dtfe"

    # Simulate a PNG created by Asset Editor in an older/general asset folder.
    editor_output = project / "assets" / "sprites" / "pixel_ship.png"
    editor_output.parent.mkdir(parents=True)
    image = QImage(16, 16, QImage.Format.Format_ARGB32)
    image.fill(0xFF22C55E)
    assert image.save(str(editor_output))

    panel = TitleSetLibraryPanel(str(project))
    panel.refresh(editor_output)
    backgrounds_available = pixel_background_templates()
    assert panel.lists["components"].count() == len(UI_COMPONENTS) + len(backgrounds_available)
    assert len(UI_COMPONENTS) == 10 and len(backgrounds_available) == 2
    assert panel.lists["perspectives"].count() == len(FRAME_PERSPECTIVES) == 4
    # Selection is the public behavior needed here; paths are stored in a custom role.
    assert panel.lists["all"].currentItem() is not None
    assert panel.lists["all"].currentItem().text() == "pixel_ship"

    viewport = Viewport2D(str(project), scene_path=scene_path, screen_id="main")
    viewport.resize(900, 700)
    viewport.show()
    QApplication.processEvents()
    imported: list[str] = []
    viewport.asset_imported.connect(imported.append)

    button = next(item for item in UI_COMPONENTS if item["kind"] == "button")
    assert viewport.insert_component(button, QPointF(0, 0))

    frame_template = next(item for item in UI_COMPONENTS if item["kind"] == "frame")
    assert viewport.insert_component(frame_template, QPointF(0, 72))
    frame_item = next(
        item for item in viewport._node_items.values()
        if getattr(item, "metadata", {}).get("component", {}).get("kind") == "frame"
    )
    assert frame_item.metadata["shape"]["corner_radius"] == 8
    assert frame_item.metadata["ui_role"] == "Frame"

    # Text and rectangle must share the same visual center even though Qt text
    # items store their position by top-left corner.
    button_items = [
        item for item in viewport._node_items.values()
        if getattr(item, "metadata", {}).get("component", {}).get("kind") == "button"
    ]
    assert len(button_items) == 2
    centers = [item.sceneBoundingRect().center() for item in button_items]
    assert abs(centers[0].x() - centers[1].x()) < 0.75
    assert abs(centers[0].y() - centers[1].y()) < 0.75

    # External art is imported once, then reused by normal drag and Paint Tile.
    outside = workspace / "outside_tile.png"
    image.fill(0xFF3B82F6)
    assert image.save(str(outside))
    assert viewport.insert_asset_path(outside, QPointF(48, 48))

    # Exercise the real Qt drag/drop path used by TitleSet, not only its helper.
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(outside))])
    mime.setData("application/x-vxp-asset", str(outside).encode("utf-8"))
    drop_point = viewport.mapFromScene(QPointF(72, 72))
    enter = QDragEnterEvent(
        drop_point, Qt.DropAction.CopyAction, mime,
        Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier,
    )
    QApplication.sendEvent(viewport.viewport(), enter)
    assert enter.isAccepted()
    drop = QDropEvent(
        QPointF(drop_point), Qt.DropAction.CopyAction, mime,
        Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier,
    )
    QApplication.sendEvent(viewport.viewport(), drop)
    assert drop.isAccepted()

    assert viewport.set_terrain_brush(outside, tile_size=16, rule_mode=True)
    assert viewport._paint_terrain_cell(QPointF(-110, -150))

    background_mime = QMimeData()
    background_path = backgrounds_available[0][1]
    background_mime.setUrls([QUrl.fromLocalFile(str(background_path))])
    background_mime.setData("application/x-vxp-asset", str(background_path).encode("utf-8"))
    background_mime.setData("application/x-vxp-background", b"1")
    background_point = viewport.mapFromScene(QPointF(0, 0))
    background_enter = QDragEnterEvent(
        background_point, Qt.DropAction.CopyAction, background_mime,
        Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier,
    )
    QApplication.sendEvent(viewport.viewport(), background_enter)
    assert background_enter.isAccepted()
    background_drop = QDropEvent(
        QPointF(background_point), Qt.DropAction.CopyAction, background_mime,
        Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier,
    )
    QApplication.sendEvent(viewport.viewport(), background_drop)
    assert background_drop.isAccepted()

    # Old projects stored Canvas/Vùng_vẽ as an opaque #111827 rectangle. It must
    # be upgraded to a transparent Photoshop-like guide so a bottom background
    # remains visible.
    legacy_canvas = viewport._create_vector_item({
        "type": "Rectangle2D", "name": "Vùng_vẽ_cũ", "ui_role": "Canvas",
        "component_category": "ui", "component": {"kind": "canvas"},
        "position": [0, 0],
        "shape": {"width": 240, "height": 320, "fill": "#111827", "stroke": "#334155"},
    }, persist=False)
    assert legacy_canvas is not None
    assert legacy_canvas.brush().color().alpha() == 0
    background_item = next(
        item for item in viewport._node_items.values()
        if getattr(item, "metadata", {}).get("component_category") == "background"
    )
    viewport._select_item(background_item)
    assert viewport.move_selected_layer("back")
    assert background_item.zValue() == min(item.zValue() for item in viewport._node_items.values())
    assert background_item.isVisible()

    perspective = FRAME_PERSPECTIVES[2]
    perspective_mime = QMimeData()
    perspective_mime.setData(
        "application/x-vxp-frame-perspective",
        json.dumps(perspective, ensure_ascii=False).encode("utf-8"),
    )
    perspective_enter = QDragEnterEvent(
        background_point, Qt.DropAction.CopyAction, perspective_mime,
        Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier,
    )
    QApplication.sendEvent(viewport.viewport(), perspective_enter)
    assert perspective_enter.isAccepted()
    perspective_drop = QDropEvent(
        QPointF(background_point), Qt.DropAction.CopyAction, perspective_mime,
        Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier,
    )
    QApplication.sendEvent(viewport.viewport(), perspective_drop)
    assert perspective_drop.isAccepted()
    viewport._queue_save()

    loop = QEventLoop()
    QTimer.singleShot(900, loop.quit)
    loop.exec()

    copied = list((project / "assets" / "imported").glob("outside_tile*.png"))
    assert len(copied) == 1, copied
    assert len(imported) == 2, imported

    payload = json.loads(scene_path.read_text(encoding="utf-8"))
    camera = next(node for node in payload["children"] if node.get("type") == "OrthographicCamera")
    assert camera["frame_perspective"]["kind"] == "three_quarter"
    assert camera["frame_perspective"]["fit_mode"] == "camera_frame"
    nodes = [node for node in payload["children"] if node.get("type") != "OrthographicCamera"]
    runtime_nodes = [node for node in nodes if not node.get("editor_guide", False)]
    assert any(node.get("component", {}).get("kind") == "button" for node in nodes)
    assert sum(node.get("asset") == "assets/imported/outside_tile.png" for node in nodes) == 3
    assert any(node.get("terrain", {}).get("tile_size") == 16 for node in nodes)
    backgrounds = [node for node in nodes if node.get("component_category") == "background"]
    assert len(backgrounds) == 1
    assert backgrounds[0]["position"] == [0.0, 0.0]
    assert backgrounds[0]["display_size"] == [240.0, 320.0], backgrounds[0]

    bindings = store.generate_c_bindings().read_text(encoding="utf-8")
    assert f"MAIN_COMPONENT_COUNT {len(runtime_nodes)}" in bindings
    assert "Button" in bindings and "outside_tile" in bindings
    assert '#define MAIN_FRAME_PERSPECTIVE "three_quarter"' in bindings
    assert '#define MAIN_FRAME_PROJECTION "top_down_3_4"' in bindings

    # Drain queued item-change callbacks before Qt destroys the view.
    QApplication.processEvents()
    viewport.close()
    viewport.deleteLater()
    QApplication.processEvents()

print("PASS: Asset Editor -> Component Library -> Camera2D -> DTFE/C bindings")
