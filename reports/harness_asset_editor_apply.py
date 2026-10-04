"""Regression: Apply & Save closes Asset Editor without re-entrant Qt refresh crash."""
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

from PySide6.QtCore import QPoint
from PySide6.QtGui import QColor, QImage
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog
from main import MainWindow
from project_store import ProjectStore
from widgets.asset_editor import AssetEditorDialog, SceneFrameRecord

app = QApplication.instance() or QApplication([])
with tempfile.TemporaryDirectory(prefix="vxpe_asset_apply_") as tmp:
    store = ProjectStore(); store.data_dir = Path(tmp) / ".registry"; store.data_dir.mkdir()
    store.registry_path = store.data_dir / "projects.json"
    project = store.create_project("AssetApply", tmp)
    window = MainWindow()
    window.current_project = project
    window.editor_page = window._build_editor_page(project)
    window.stack.addWidget(window.editor_page)
    window._open_asset_editor("", "assets/map/texture")
    editor = window.asset_editor_windows[-1]
    QTest.qWait(80); app.processEvents()
    assert editor.isMaximized(), "Asset Editor must open maximized like VXPEngine"
    assert editor.maximize_button.toolTip() == "Khôi phục"
    editor.toggle_maximize_restore(); app.processEvents()
    assert not editor.isMaximized() and editor.width() >= 720 and editor.height() >= 500
    editor.toggle_maximize_restore(); app.processEvents()
    assert editor.isMaximized()
    editor.canvas.new_image(64, 64, transparent=True)
    editor.canvas.brush_color = QColor("#ff8a3d")
    editor.canvas.brush_size = 2
    for tool in (
        "shape_rect", "shape_round_rect", "shape_ellipse", "shape_triangle",
        "shape_right_triangle", "shape_arrow", "shape_star", "shape_speech",
    ):
        path = editor.canvas._frame_shape_path(tool, QPoint(6, 6), QPoint(54, 42))
        assert not path.isEmpty(), tool
    editor.canvas._commit_frame_shape("shape_round_rect", QPoint(6, 6), QPoint(54, 30))
    editor.canvas._commit_frame_shape("ruler", QPoint(4, 50), QPoint(58, 50))
    editor.canvas._commit_free_frame([QPoint(10, 45), QPoint(25, 35), QPoint(42, 48)])
    assert any(editor.canvas.image.pixelColor(x, y).alpha() for y in range(64) for x in range(64))
    assert {"ruler", "free_frame", "shape_rect"}.issubset(editor.tool_buttons)
    assert len(editor.tool_buttons["shape_rect"].menu().actions()) == 8
    assert editor.canvas._snap_ruler_endpoint(QPoint(0, 0), QPoint(11, 3)).y() == 0

    frame_a = QImage(8, 8, QImage.Format.Format_RGBA8888); frame_a.fill(0)
    frame_b = QImage(6, 4, QImage.Format.Format_RGBA8888); frame_b.fill(QColor("#22c55e"))
    frame_a.setPixelColor(3, 3, QColor("#ef4444")); frame_a.setPixelColor(4, 4, QColor("#ef4444"))
    editor.scene_frames = [
        SceneFrameRecord("idle", frame_a, 90), SceneFrameRecord("step", frame_b, 120),
    ]
    editor.selected_scene = 1; editor._refresh_scenes(); editor.scene_list.setCurrentRow(1)
    editor.animation_player_settings["source_mode"] = "scene_timeline"
    editor.onion_skin.setChecked(True)
    assert not editor.canvas.onion_image.isNull()
    editor.trim_scene_frames(); editor.normalize_scene_frames()
    assert len({(item.image.width(), item.image.height()) for item in editor.scene_frames}) == 1
    editor.make_scene_ping_pong(); assert len(editor.scene_frames) == 3
    editor.reverse_scene_timeline(); editor.flip_selected_scene()
    editor.scene_target.setCurrentIndex(editor.scene_target.findData("character"))
    editor.asset_name.setText("apply_safe.png")
    editor.save_and_apply()
    assert editor.result() == QDialog.DialogCode.Accepted
    QTest.qWait(180); app.processEvents()
    output = project.folder / "assets/map/texture/apply_safe.png"
    assert output.is_file()
    descriptors = list((project.folder / "assets/scenes").glob("apply_safe*.ani..dtfe"))
    assert len(descriptors) == 1
    import json
    animation = json.loads(descriptors[0].read_text(encoding="utf-8"))
    assert animation["source_mode"] == "scene_timeline"
    assert animation["asset_kind"] == "character"
    assert animation["package"] == "spritesheet+frames+descriptor"
    assert len(animation["frames"]) == 3
    assert all((project.folder / frame["file"]).is_file() for frame in animation["frames"])
    assert (project.folder / animation["texture"]).is_file()
    reopened = AssetEditorDialog(project.folder, descriptors[0])
    assert len(reopened.scene_frames) == 3
    assert reopened.animation_player_settings["source_mode"] == "scene_timeline"
    assert reopened.scene_target.currentData() == "character"
    reopened.close(); reopened.deleteLater(); app.processEvents()
    assert window.assets_panel is not None and window.tileset_panel is not None
    window.close(); app.processEvents()

print("PASS: Asset Editor Apply queued refresh + safe close")
