"""Create small VXPEngine app/game projects using the real editor asset pipeline."""
from __future__ import annotations

import json
import sys
from pathlib import Path

from PySide6.QtCore import QPoint, QPointF, QRect, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPen, QPolygon
from PySide6.QtWidgets import QApplication

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

from project_store import ProjectStore  # noqa: E402
from scene_screen_store import ScreenStore  # noqa: E402
from widgets.asset_editor import AssetEditorDialog, CollisionRecord  # noqa: E402


def _editor_export(root: Path, image: QImage, name: str, destination: str, collision: QRect | None = None) -> Path:
    """Save through AssetEditorDialog, including its .asset.dtfe metadata path."""
    editor = AssetEditorDialog(root, initial_destination=destination)
    editor.canvas.set_image(image)
    editor.asset_name.setText(name)
    editor.allow_overwrite.setChecked(True)
    editor.write_metadata.setChecked(True)
    editor.write_animation.setChecked(False)
    editor.render_mode.setCurrentText("Nearest / Pixel")
    if collision is not None:
        editor.canvas.collisions = [CollisionRecord("bounds", QRect(collision), "solid")]
    editor.save_and_apply()
    if editor.saved_path is None:
        raise RuntimeError(f"Asset Editor could not export {name}")
    return editor.saved_path


def _isometric_background() -> QImage:
    image = QImage(320, 240, QImage.Format.Format_RGBA8888)
    image.fill(QColor("#243C2A"))
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
    grass = (QColor("#668C3A"), QColor("#769D43"), QColor("#587B34"))
    tile_w, tile_h = 32, 16
    for row in range(-2, 19):
        for col in range(-7, 13):
            cx = col * tile_w + (row & 1) * 16 + 160
            cy = row * 8 + 36
            poly = QPolygon([QPointF(cx, cy - 8).toPoint(), QPointF(cx + 16, cy).toPoint(),
                             QPointF(cx, cy + 8).toPoint(), QPointF(cx - 16, cy).toPoint()])
            painter.setPen(QPen(QColor("#3D5D2B"), 1))
            painter.setBrush(grass[(row + col) % len(grass)])
            painter.drawPolygon(poly)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor("#346C83")); painter.drawPolygon(QPolygon([QPoint(0, 184), QPoint(320, 142), QPoint(320, 240), QPoint(0, 240)]))
    painter.setBrush(QColor("#4D8DA0"))
    for x in range(0, 320, 24):
        painter.drawRect(x, 198 + (x // 24 % 2) * 6, 14, 2)
    painter.end()
    return image


def _unit_sprite() -> QImage:
    image = QImage(24, 32, QImage.Format.Format_RGBA8888); image.fill(Qt.GlobalColor.transparent)
    p = QPainter(image); p.setRenderHint(QPainter.RenderHint.Antialiasing, False)
    p.fillRect(7, 3, 10, 8, QColor("#C88C57")); p.fillRect(6, 3, 12, 3, QColor("#583822"))
    p.fillRect(6, 11, 12, 11, QColor("#275C89")); p.fillRect(3, 13, 4, 10, QColor("#C88C57"))
    p.fillRect(17, 13, 4, 10, QColor("#C88C57")); p.fillRect(6, 22, 5, 8, QColor("#3B2B22"))
    p.fillRect(13, 22, 5, 8, QColor("#3B2B22")); p.fillRect(9, 6, 2, 2, QColor("#1A1E20"))
    p.fillRect(14, 6, 2, 2, QColor("#1A1E20")); p.end()
    return image


def _town_hall() -> QImage:
    image = QImage(72, 64, QImage.Format.Format_RGBA8888); image.fill(Qt.GlobalColor.transparent)
    p = QPainter(image); p.setRenderHint(QPainter.RenderHint.Antialiasing, False)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor("#4E3527")); p.drawPolygon(QPolygon([QPoint(4, 25), QPoint(36, 4), QPoint(68, 25), QPoint(36, 43)]))
    p.setBrush(QColor("#A25B32")); p.drawPolygon(QPolygon([QPoint(9, 24), QPoint(36, 8), QPoint(63, 24), QPoint(36, 38)]))
    p.setBrush(QColor("#C7A269")); p.drawPolygon(QPolygon([QPoint(10, 27), QPoint(36, 42), QPoint(36, 61), QPoint(10, 45)]))
    p.setBrush(QColor("#967044")); p.drawPolygon(QPolygon([QPoint(36, 42), QPoint(63, 27), QPoint(63, 45), QPoint(36, 61)]))
    p.fillRect(31, 44, 10, 17, QColor("#38271F")); p.end()
    return image


def _app_background() -> QImage:
    image = QImage(240, 320, QImage.Format.Format_RGBA8888); image.fill(QColor("#101B2D"))
    p = QPainter(image); p.setRenderHint(QPainter.RenderHint.Antialiasing, False)
    for y in range(0, 320, 16):
        p.fillRect(0, y, 240, 8, QColor(24 + y // 32, 40 + y // 24, 64 + y // 20))
    p.fillRect(12, 18, 216, 56, QColor("#25466C")); p.fillRect(16, 22, 208, 48, QColor("#193653"))
    p.end(); return image


def _write_scene(root: Path, width: int, height: int, children: list[dict], perspective: str = "") -> Path:
    path = root / "assets" / "scenes" / "main.dtfe"
    scene = json.loads(path.read_text(encoding="utf-8"))
    scene["viewport"] = {"type": "FitViewport", "width": width, "height": height,
                         "orientation": "landscape" if width > height else "portrait"}
    camera = {"id": "camera2d", "name": "Camera2D", "type": "OrthographicCamera",
              "position": [0, 0], "rotation": 0, "zoom": [1, 1], "projection": "Pixel Perfect",
              "preview_background": "Editor Grid"}
    if perspective:
        camera["frame_perspective"] = {"kind": perspective, "fit_mode": "camera_frame", "editor_guide": True}
    scene["children"] = [camera, *children]
    path.write_text(json.dumps(scene, ensure_ascii=False, indent=2), encoding="utf-8")
    ScreenStore(root).generate_c_bindings()
    return path


def create_demo_suite(base: Path) -> tuple[Path, Path]:
    base.mkdir(parents=True, exist_ok=True)
    store = ProjectStore()
    store.data_dir = base / ".registry"
    store.data_dir.mkdir(parents=True, exist_ok=True)
    store.registry_path = store.data_dir / "projects.json"

    app_project = store.create_project("PocketToolkitDemo", str(base), app_name="pocket_tools", viewport_width=240, viewport_height=320)
    app_bg = _editor_export(app_project.folder, _app_background(), "toolkit_background_240x320.png", "assets/map/background")
    app_children = [
        {"id":"app_bg","name":"Background","code_name":"Background","type":"Sprite2D","asset":app_bg.relative_to(app_project.folder).as_posix(),"position":[0,0],"scale":[1,1],"display_size":[240,320],"z_index":-10,"locked":True,"lock_aspect":True,"pixel_snap":True,"component_category":"background","ui_role":"Background"},
        {"id":"title","name":"Title","code_name":"Title","type":"Text2D","position":[-84,-122],"text":{"content":"POCKET TOOLS","font_size":18,"color":"#F4D77B"},"scale":[1,1],"z_index":2,"anchor":{"mode":"Top Left","x":0,"y":0},"pixel_snap":True},
        {"id":"panel","name":"InfoPanel","code_name":"InfoPanel","type":"Rectangle2D","position":[0,-20],"shape":{"width":200,"height":112,"fill":"#162943E8","stroke":"#7396B8","stroke_width":2},"scale":[1,1],"display_size":[200,112],"z_index":1,"anchor":{"mode":"Center","x":.5,"y":.5},"pixel_snap":True},
        {"id":"action","name":"StartButton","code_name":"StartButton","type":"Rectangle2D","position":[0,94],"shape":{"width":136,"height":34,"fill":"#3B7C65","stroke":"#9AD4B3","stroke_width":2},"scale":[1,1],"display_size":[136,34],"z_index":3,"automation":{"enabled":True,"role":"action_button","input_action":"ACTION","physics":"none","collision_enabled":True,"collision_shape":"bounds","tags":["ui"]}},
    ]
    _write_scene(app_project.folder, 240, 320, app_children)

    game_project = store.create_project("IsometricOutpostDemo", str(base), app_name="iso_outpost", viewport_width=320, viewport_height=240)
    bg = _editor_export(game_project.folder, _isometric_background(), "isometric_grassland_320x240.png", "assets/map/background")
    hall = _editor_export(game_project.folder, _town_hall(), "town_hall.png", "assets/scenes", QRect(9, 24, 55, 37))
    unit = _editor_export(game_project.folder, _unit_sprite(), "villager.png", "assets/scenes", QRect(5, 3, 15, 27))
    game_children = [
        {"id":"world","name":"WorldBackground","code_name":"WorldBackground","type":"Sprite2D","asset":bg.relative_to(game_project.folder).as_posix(),"position":[0,0],"scale":[1,1],"display_size":[320,240],"z_index":-10,"locked":True,"lock_aspect":True,"pixel_snap":True,"component_category":"background","ui_role":"Background"},
        {"id":"hall","name":"TownHall","code_name":"TownHall","type":"Sprite2D","asset":hall.relative_to(game_project.folder).as_posix(),"position":[30,-12],"scale":[1,1],"display_size":[72,64],"z_index":2,"lock_aspect":True,"pixel_snap":True,"anchor":{"mode":"Bottom","x":.5,"y":1},"automation":{"enabled":True,"role":"static_obstacle","physics":"static","collision_enabled":True,"collision_shape":"bounds","tags":["building"]}},
        {"id":"worker1","name":"Villager","code_name":"Villager","type":"Sprite2D","asset":unit.relative_to(game_project.folder).as_posix(),"position":[-46,34],"scale":[1,1],"display_size":[24,32],"z_index":4,"lock_aspect":True,"pixel_snap":True,"anchor":{"mode":"Bottom","x":.5,"y":1},"automation":{"enabled":True,"role":"player","physics":"kinematic","collision_enabled":True,"collision_shape":"bounds","tags":["unit","worker"]}},
        {"id":"hud","name":"ResourceBar","code_name":"ResourceBar","type":"Rectangle2D","position":[0,-106],"shape":{"width":304,"height":22,"fill":"#172235E8","stroke":"#C7A269","stroke_width":1},"scale":[1,1],"display_size":[304,22],"z_index":20,"pixel_snap":True,"anchor":{"mode":"Top","x":.5,"y":0}},
    ]
    _write_scene(game_project.folder, 320, 240, game_children, "isometric")
    return app_project.folder, game_project.folder


if __name__ == "__main__":
    qt_app = QApplication.instance() or QApplication([])
    destination = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else ROOT / "examples"
    app_root, game_root = create_demo_suite(destination)
    print(f"APP={app_root}")
    print(f"GAME={game_root}")
