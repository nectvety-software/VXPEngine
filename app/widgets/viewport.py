"""Interactive 2D scene viewport with real editor tools and DTFE persistence."""
from __future__ import annotations

import copy
import filecmp
import json
import math
import shutil
import time
import uuid
from pathlib import Path

from PySide6.QtCore import QLineF, QPoint, QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import (
    QAction,
    QBrush,
    QColor,
    QFont,
    QImage,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QPolygonF,
    QTransform,
)
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsItem,
    QGraphicsPathItem,
    QGraphicsPixmapItem,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsSimpleTextItem,
    QGraphicsTextItem,
    QGraphicsView,
    QMenu,
)
from shiboken6 import isValid


from .custom_dialog import TextInputDialog
from .icons import icon
from file_utils import unique_destination
from color_utils import format_hex, parse_color

GRID_BG = QColor("#0E131B")
GRID_LINE = QColor(255, 255, 255, 13)
GRID_LINE_MAJOR = QColor(255, 255, 255, 25)
X_AXIS_COLOR = QColor("#E15B64")
Y_AXIS_COLOR = QColor("#55B779")
CAMERA_COLOR = QColor("#5B93FF")
DEFAULT_FILL = "#4E8DE6"
DEFAULT_STROKE = "#BFD5FF"
RULER_SIZE = 24
RULER_BG = QColor("#151B25")
RULER_BORDER = QColor("#2A3342")
RULER_TEXT = QColor("#93A0B5")
SMART_GUIDE_X = QColor("#45A3FF")  # vertical alignment guide
SMART_GUIDE_Y = QColor("#F2C94C")  # horizontal alignment guide
GUIDE_ENTER_PX = 4.0
GUIDE_RELEASE_PX = 7.0
GRID_ENTER_PX = 2.5
RESIZE_HANDLE_PX = 9
MIN_COMPONENT_SCALE = 0.02
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif", ".svg"}
EDITABLE_NODE_TYPES = {
    "sprite", "sprite2d", "effect2d", "rectangle2d", "circle2d", "line2d",
    "brush2d", "tile2d", "text2d",
}
MRE_PORTRAIT = (240, 320)
MRE_LANDSCAPE = (320, 240)


def _mre_viewport(width: int, height: int) -> tuple[int, int]:
    """Normalize every scene to one of the two physical S30+ orientations."""
    return MRE_LANDSCAPE if int(width) > int(height) else MRE_PORTRAIT


def _item_change(owner: "Viewport2D", item: QGraphicsItem, change, value):
    if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange and not owner._loading:
        if owner._item_is_locked(item):
            return QPointF(item.pos())
        if owner.current_tool == "Select":
            node_pixel_snap = bool(getattr(item, "metadata", {}).get("pixel_snap", True))
            proposed = owner._soft_grid_snap_point(value) if owner.snap_enabled and node_pixel_snap else QPointF(value)
            return owner._smart_snap_position(item, proposed)
    if change in {
        QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged,
        QGraphicsItem.GraphicsItemChange.ItemRotationHasChanged,
        QGraphicsItem.GraphicsItemChange.ItemScaleHasChanged,
        QGraphicsItem.GraphicsItemChange.ItemTransformHasChanged,
        QGraphicsItem.GraphicsItemChange.ItemVisibleHasChanged,
        QGraphicsItem.GraphicsItemChange.ItemOpacityHasChanged,
        QGraphicsItem.GraphicsItemChange.ItemZValueHasChanged,
    }:
        QTimer.singleShot(0, lambda: owner._item_transform_changed(item))
    return value


class SceneAssetItem(QGraphicsPixmapItem):
    def __init__(self, pixmap: QPixmap, metadata: dict, owner: "Viewport2D") -> None:
        super().__init__(pixmap)
        self.metadata = metadata
        self.owner = owner
        self.setTransformationMode(Qt.TransformationMode.FastTransformation)
        self.setTransformOriginPoint(self.boundingRect().center())
        self.setToolTip(str(metadata.get("asset", metadata.get("name", "Sprite"))))
        self.owner._configure_node_item(self)

    def itemChange(self, change, value):  # noqa: N802
        value = _item_change(self.owner, self, change, value)
        return super().itemChange(change, value)


class SceneVectorItem(QGraphicsPathItem):
    def __init__(self, path: QPainterPath, metadata: dict, owner: "Viewport2D") -> None:
        super().__init__(path)
        self.metadata = metadata
        self.owner = owner
        self._background_pixmap = QPixmap()
        self.refresh_background_bitmap()
        self.setTransformOriginPoint(self.boundingRect().center())
        self.setToolTip(str(metadata.get("name", metadata.get("type", "Vector"))))
        self.owner._configure_node_item(self)

    def itemChange(self, change, value):  # noqa: N802
        value = _item_change(self.owner, self, change, value)
        return super().itemChange(change, value)

    def refresh_background_bitmap(self) -> None:
        source = self.owner._resolve_asset_path(str(self.metadata.get("background_bitmap", "")))
        self._background_pixmap = QPixmap(str(source)) if source is not None else QPixmap()
        self.update()

    def paint(self, painter, option, widget=None) -> None:
        super().paint(painter, option, widget)
        if self._background_pixmap.isNull():
            return
        bounds = self.path().boundingRect()
        if bounds.isEmpty():
            return
        mode = str(self.metadata.get("background_bitmap_mode", "Fill")).strip().lower()
        painter.save()
        painter.setClipPath(self.path())
        if mode == "tile":
            painter.drawTiledPixmap(bounds, self._background_pixmap)
        else:
            aspect = {
                "fit": Qt.AspectRatioMode.KeepAspectRatio,
                "stretch": Qt.AspectRatioMode.IgnoreAspectRatio,
            }.get(mode, Qt.AspectRatioMode.KeepAspectRatioByExpanding)
            scaled = self._background_pixmap.scaled(
                max(1, int(round(bounds.width()))),
                max(1, int(round(bounds.height()))),
                aspect,
                Qt.TransformationMode.FastTransformation,
            )
            painter.drawPixmap(
                QPointF(bounds.center().x() - scaled.width() / 2.0, bounds.center().y() - scaled.height() / 2.0),
                scaled,
            )
        painter.restore()
        if self.pen().style() != Qt.PenStyle.NoPen and self.pen().widthF() > 0:
            painter.save()
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(self.pen())
            painter.drawPath(self.path())
            painter.restore()


class SceneTextItem(QGraphicsTextItem):
    def __init__(self, text: str, metadata: dict, owner: "Viewport2D") -> None:
        super().__init__(text)
        self.metadata = metadata
        self.owner = owner
        self.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        self.setTransformOriginPoint(self.boundingRect().center())
        self.setToolTip(str(metadata.get("name", "Text")))
        self.owner._configure_node_item(self)

    def itemChange(self, change, value):  # noqa: N802
        value = _item_change(self.owner, self, change, value)
        return super().itemChange(change, value)


class Viewport2D(QGraphicsView):
    """2D scene editor with transform/vector tools and undo/redo history."""

    selection_changed = Signal(dict)
    scene_changed = Signal()
    status_message = Signal(str)
    tool_changed = Signal(str)
    history_changed = Signal(bool, bool)
    asset_editor_requested = Signal(str, str)
    keyframe_editor_requested = Signal(dict)
    event_mapping_requested = Signal(dict)
    automation_mapping_requested = Signal(dict)
    screen_saved = Signal(str)
    asset_imported = Signal(str)

    def __init__(self, project_path: str = "", scene_path: str | Path | None = None, screen_id: str = "main", parent=None):
        super().__init__(parent)
        self.project_path = Path(project_path).resolve() if project_path else None
        self._scene_file_override = Path(scene_path).expanduser().resolve() if scene_path else None
        self.screen_id = str(screen_id or "main")
        self.current_tool = "Select"
        self.snap_enabled = True
        self.grid_size = 32
        self._zoom = 1.0
        self._loading = True
        self._sprite_items: dict[str, SceneAssetItem] = {}
        self._node_items: dict[str, QGraphicsItem] = {}
        self._camera_frame: QGraphicsRectItem | None = None
        self._camera_bezel: QGraphicsPathItem | None = None
        self._camera_label: QGraphicsSimpleTextItem | None = None
        self._camera_origin: QGraphicsSimpleTextItem | None = None
        self._create_start: QPointF | None = None
        self._create_preview: QGraphicsPathItem | None = None
        self._brush_points: list[QPointF] = []
        self._transform_drag: dict | None = None
        self._group_drag: dict | None = None
        self._item_resize_drag: dict | None = None
        self._camera_resize_drag: dict | None = None
        self._pan_start: QPoint | None = None
        self._pan_scroll: tuple[int, int] | None = None
        self._history: list[str] = []
        self._history_index = -1
        self._active_guide_x: float | None = None
        self._active_guide_y: float | None = None
        self._active_guide_x_source: int | None = None
        self._active_guide_y_source: int | None = None
        self._guide_suppress_x = False
        self._guide_suppress_y = False
        self._camera_handle_hover: str | None = None
        self._item_handle_hover: str | None = None
        self._last_mouse_scene = QPointF(0, 0)
        self._selected_group_id: str | None = None
        self._pending_asset_edit_context: dict | None = None
        self._clipboard_nodes: list[dict] = []
        self._terrain_brush_path: Path | None = None
        self._terrain_brush_size = 16
        self._terrain_rule_mode = True
        self._terrain_erase_mode = False
        self._terrain_last_cell: tuple[int, int] | None = None
        self._terrain_stroke_dirty = False
        self._guide_clear_timer = QTimer(self)
        self._guide_clear_timer.setSingleShot(True)
        self._guide_clear_timer.timeout.connect(self._clear_smart_guides)

        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.SmartViewportUpdate)
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setBackgroundBrush(QBrush(GRID_BG))
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setAcceptDrops(True)
        self.viewport().setAcceptDrops(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMouseTracking(True)
        self.viewport().setMouseTracking(True)

        graphics_scene = QGraphicsScene(-4000, -2800, 8000, 5600)
        graphics_scene.selectionChanged.connect(self._emit_selection)
        self.setScene(graphics_scene)

        self._scene_payload = self._read_scene_payload()
        self._camera_width, self._camera_height = self._read_camera_size()
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(120)
        self._save_timer.timeout.connect(self._save_scene)
        self._history_timer = QTimer(self)
        self._history_timer.setSingleShot(True)
        self._history_timer.setInterval(320)
        self._history_timer.timeout.connect(self._record_history)

        self._add_camera_frame()
        self._load_editable_nodes()
        self._loading = False
        self._record_history(force=True)
        self.centerOn(QPointF(0, 0))
        self.scale(0.74, 0.74)
        self._zoom = 0.74
        self.set_tool("Select")
        QTimer.singleShot(0, self._emit_selection)

    @property
    def scene_file(self) -> Path | None:
        if self.project_path is None:
            return None
        if self._scene_file_override is not None:
            return self._scene_file_override
        current = self.project_path / "assets" / "scenes" / "main.dtfe"
        if current.exists():
            return current
        for legacy in (self.project_path / "scenes" / "main.dtfe", self.project_path / "scenes" / "main.nova"):
            if legacy.exists():
                return legacy
        return current

    def _read_scene_payload(self) -> dict:
        path = self.scene_file
        if path is not None:
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(payload, dict):
                    return payload
            except (OSError, ValueError, TypeError, json.JSONDecodeError):
                pass
        return {
            "name": "Main",
            "type": "VXPScene",
            "screen_id": self.screen_id,
            "viewport": {"type": "FitViewport", "width": 240, "height": 320},
            "groups": [],
            "children": [{"id": "camera2d", "code_name": "Camera2D", "name": "Camera2D", "type": "OrthographicCamera", "position": [0, 0], "zoom": [1, 1]}],
        }

    def _read_camera_size(self) -> tuple[int, int]:
        viewport = self._scene_payload.get("viewport", {})
        try:
            width = int(viewport.get("width", 240))
            height = int(viewport.get("height", 320))
        except (AttributeError, TypeError, ValueError):
            width, height = MRE_PORTRAIT
        width, height = _mre_viewport(width, height)
        if isinstance(viewport, dict):
            viewport["width"], viewport["height"] = width, height
        return width, height

    @property
    def screen_name(self) -> str:
        return str(self._scene_payload.get("name") or self.screen_id or "Main")

    def _groups(self) -> list[dict]:
        groups = self._scene_payload.get("groups")
        if not isinstance(groups, list):
            groups = []
            self._scene_payload["groups"] = groups
        return [group for group in groups if isinstance(group, dict)]

    def _group_by_id(self, group_id: str | None) -> dict | None:
        value = str(group_id or "")
        if not value:
            return None
        return next((group for group in self._groups() if str(group.get("id", "")) == value), None)

    def _add_group(self, group: dict) -> None:
        """Ghi nhóm vào đúng danh sách groups của scene (không phải bản lọc của _groups())."""
        groups = self._scene_payload.get("groups")
        if not isinstance(groups, list):
            groups = []
            self._scene_payload["groups"] = groups
        groups.append(group)

    def _group_members(self, group_id: str | None) -> list[QGraphicsItem]:
        value = str(group_id or "")
        if not value:
            return []
        return [
            item for item in self._node_items.values()
            if str(getattr(item, "metadata", {}).get("group_id", "")) == value
        ]

    def _group_opacity(self, group_id: str | None) -> float:
        group = self._group_by_id(group_id)
        if group is None:
            return 1.0
        try:
            return max(0.0, min(1.0, float(group.get("opacity", 1.0))))
        except (TypeError, ValueError):
            return 1.0

    def _group_visible(self, group_id: str | None) -> bool:
        group = self._group_by_id(group_id)
        return bool(group.get("visible", True)) if group is not None else True

    def _group_locked(self, group_id: str | None) -> bool:
        group = self._group_by_id(group_id)
        return bool(group.get("locked", False)) if group is not None else False

    def _item_is_locked(self, item: QGraphicsItem) -> bool:
        data = getattr(item, "metadata", {})
        return bool(data.get("locked", False)) or self._group_locked(data.get("group_id"))

    def _apply_effective_item_state(self, item: QGraphicsItem) -> None:
        data = getattr(item, "metadata", {})
        try:
            local_opacity = max(0.0, min(1.0, float(data.get("opacity", 1.0))))
        except (TypeError, ValueError):
            local_opacity = 1.0
        item.setOpacity(local_opacity * self._group_opacity(data.get("group_id")))
        item.setVisible(bool(data.get("visible", True)) and self._group_visible(data.get("group_id")))
        self._refresh_item_flags(item)

    def _group_payload(self, group_id: str) -> dict:
        group = self._group_by_id(group_id) or {}
        members = self._group_members(group_id)
        background_owner = next((member for member in members if isinstance(member, SceneVectorItem)), None)
        background_data = getattr(background_owner, "metadata", {}) if background_owner is not None else {}
        rect = QRectF()
        for member in members:
            rect = member.sceneBoundingRect() if rect.isNull() else rect.united(member.sceneBoundingRect())
        return {
            "kind": "group",
            "id": str(group.get("id", group_id)),
            "name": str(group.get("name", "Group")),
            "type": "Group2D",
            "opacity": float(group.get("opacity", 1.0)),
            "visible": bool(group.get("visible", True)),
            "locked": bool(group.get("locked", False)),
            "z_index": int(group.get("z_index", min((int(item.zValue()) for item in members), default=0))),
            "member_count": len(members),
            "size": [round(rect.width()), round(rect.height())],
            "background_bitmap": str(background_data.get("background_bitmap", "")),
            "background_bitmap_mode": str(background_data.get("background_bitmap_mode", "Fill")),
            "screen_id": self.screen_id,
        }

    def scene_tree_payload(self) -> dict:
        payload = copy.deepcopy(self._compose_payload())
        payload["scene_file"] = str(self.scene_file or "")
        payload["screen_id"] = str(payload.get("screen_id") or self.screen_id)
        return payload

    def _add_camera_frame(self) -> None:
        bezel = QGraphicsPathItem()
        bezel.setPen(QPen(QColor("#34445B"), 2.0))
        bezel.setBrush(QBrush(QColor("#18212D")))
        bezel.setZValue(-100000)
        bezel.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        self.scene().addItem(bezel)
        self._camera_bezel = bezel

        frame = QGraphicsRectItem()
        pen = QPen(CAMERA_COLOR, 1.4)
        pen.setCosmetic(True)
        pen.setStyle(Qt.PenStyle.DashLine)
        frame.setPen(pen)
        frame.setBrush(QBrush(Qt.BrushStyle.NoBrush))
        frame.setZValue(100000)
        frame.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        self.scene().addItem(frame)
        self._camera_frame = frame

        label = QGraphicsSimpleTextItem()
        label.setBrush(QBrush(QColor("#9FC0FF")))
        label.setFont(QFont("Segoe UI", 10, QFont.Weight.DemiBold))
        label.setZValue(100001)
        label.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        self.scene().addItem(label)
        self._camera_label = label

        origin = QGraphicsSimpleTextItem("0, 0")
        origin.setBrush(QBrush(QColor("#AAB6C8")))
        origin.setFont(QFont("Cascadia Code", 9))
        origin.setPos(8, 8)
        origin.setZValue(100001)
        origin.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        self.scene().addItem(origin)
        self._camera_origin = origin
        self._update_camera_visuals()

    def _camera_node(self) -> dict:
        children = self._scene_payload.setdefault("children", [])
        camera = next(
            (child for child in children if isinstance(child, dict) and "camera" in str(child.get("type", "")).lower()),
            None,
        )
        if camera is None:
            camera = {"name": "Camera2D", "type": "OrthographicCamera", "position": [0, 0], "zoom": [1, 1]}
            children.insert(0, camera)
        return camera

    def _update_camera_visuals(self) -> None:
        if self._camera_frame is None:
            return
        camera = self._camera_node()
        position = self._point_from(camera.get("position"), QPointF(0, 0))
        # Camera zoom changes world projection, never the physical S30+
        # framebuffer outline shown in the editor.
        width = self._camera_width
        height = self._camera_height
        self._camera_frame.setRect(position.x() - width / 2, position.y() - height / 2, width, height)
        if self._camera_bezel is not None:
            outer = QRectF(position.x() - width / 2 - 16, position.y() - height / 2 - 30, width + 32, height + 70)
            bezel_path = QPainterPath()
            bezel_path.addRoundedRect(outer, 18, 18)
            bezel_path.addRoundedRect(QRectF(position.x() - 26, outer.top() + 9, 52, 6), 3, 3)
            bezel_path.addRoundedRect(QRectF(position.x() - 46, outer.bottom() - 29, 92, 20), 10, 10)
            self._camera_bezel.setPath(bezel_path)
        if self._camera_label:
            self._camera_label.setText(f"Camera2D  {self._camera_width} × {self._camera_height}")
            # Nhãn nằm NGOÀI frame (phía trên) để không lọt vào màn chơi 240x320
            # khi đồng bộ giả lập / build .vxp.
            self._camera_label.setPos(position.x() - width / 2 + 12, position.y() - height / 2 - 22)

    def _camera_handle_at(self, scene_pos: QPointF) -> str | None:
        # The device frame is fixed; components remain freely editable inside.
        return None

    def _start_camera_resize(self, handle: str, scene_pos: QPointF) -> None:
        camera = self._camera_node()
        center = self._point_from(camera.get("position"), QPointF(0, 0))
        self._camera_resize_drag = {"handle": handle, "center": center}

    def _apply_camera_resize(self, scene_pos: QPointF) -> None:
        return

    def _configure_node_item(self, item: QGraphicsItem) -> None:
        item.setFlags(
            QGraphicsItem.GraphicsItemFlag.ItemIsSelectable
            | QGraphicsItem.GraphicsItemFlag.ItemIsFocusable
            | QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges
        )
        self._refresh_item_flags(item)

    def _refresh_item_flags(self, item: QGraphicsItem | None = None) -> None:
        targets = [item] if item is not None else list(self._node_items.values())
        for target in targets:
            if target is None:
                continue
            # Direct manipulation behaves like a visual design tool: Select
            # chooses and drags nodes; Move pans the whole camera workspace.
            target.setFlag(
                QGraphicsItem.GraphicsItemFlag.ItemIsMovable,
                self.current_tool == "Select" and not self._item_is_locked(target),
            )
            target.setAcceptedMouseButtons(Qt.MouseButton.LeftButton | Qt.MouseButton.RightButton)

    def set_tool(self, name: str) -> None:
        normalized = str(name or "Select").title()
        valid = {"Select", "Move", "Rotate", "Scale", "Rectangle", "Circle", "Line", "Text", "Tile", "Brush", "Terrain"}
        self.current_tool = normalized if normalized in valid else "Select"
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag if self.current_tool == "Select" else QGraphicsView.DragMode.NoDrag)
        self._refresh_item_flags()
        cursors = {
            "Select": Qt.CursorShape.ArrowCursor,
            "Move": Qt.CursorShape.OpenHandCursor,
            "Rotate": Qt.CursorShape.CrossCursor,
            "Scale": Qt.CursorShape.SizeFDiagCursor,
            "Rectangle": Qt.CursorShape.CrossCursor,
            "Circle": Qt.CursorShape.CrossCursor,
            "Line": Qt.CursorShape.CrossCursor,
            "Text": Qt.CursorShape.IBeamCursor,
            "Tile": Qt.CursorShape.CrossCursor,
            "Brush": Qt.CursorShape.CrossCursor,
            "Terrain": Qt.CursorShape.CrossCursor,
        }
        self.viewport().setCursor(cursors[self.current_tool])
        self.tool_changed.emit(self.current_tool)
        description = {
            "Select": "chọn và kéo trực tiếp thành phần như Canva",
            "Move": "kéo toàn bộ frame/canvas",
            "Rotate": "xoay thành phần",
            "Scale": "thay đổi kích thước thành phần",
        }.get(self.current_tool, "tạo thành phần mới")
        self.status_message.emit(f"[Tool] {self.current_tool}: {description}.")

    def set_snap_enabled(self, enabled: bool) -> None:
        self.snap_enabled = bool(enabled)
        self.viewport().update()
        self.status_message.emit(f"[Scene] Snap to Grid: {'Bật' if enabled else 'Tắt'}.")

    def set_grid_size(self, size: int) -> None:
        self.grid_size = max(4, min(256, int(size)))
        self.viewport().update()

    def _snap_point(self, point: QPointF) -> QPointF:
        if not self.snap_enabled:
            return QPointF(point)
        size = float(self.grid_size)
        return QPointF(round(point.x() / size) * size, round(point.y() / size) * size)

    def _soft_grid_snap_point(self, point: QPointF) -> QPointF:
        """Snap only near a grid line instead of quantizing the whole drag."""
        if not self.snap_enabled:
            return QPointF(point)
        size = float(self.grid_size)
        threshold = GRID_ENTER_PX / max(self._zoom, 0.12)
        target_x = round(point.x() / size) * size
        target_y = round(point.y() / size) * size
        return QPointF(
            target_x if abs(target_x - point.x()) <= threshold else point.x(),
            target_y if abs(target_y - point.y()) <= threshold else point.y(),
        )

    def _guide_candidates(self, moving) -> tuple[list[float], list[float]]:
        excluded = moving if isinstance(moving, (set, frozenset, list, tuple)) else {moving}
        x_values = [0.0]
        y_values = [0.0]
        if self._camera_frame is not None:
            rect = self._camera_frame.sceneBoundingRect()
            x_values.extend([rect.left(), rect.center().x(), rect.right()])
            y_values.extend([rect.top(), rect.center().y(), rect.bottom()])
        for item in self._node_items.values():
            if item in excluded or not item.isVisible():
                continue
            rect = item.sceneBoundingRect()
            x_values.extend([rect.left(), rect.center().x(), rect.right()])
            y_values.extend([rect.top(), rect.center().y(), rect.bottom()])
        return sorted(set(x_values)), sorted(set(y_values))

    @staticmethod
    def _best_axis_guide(
        sources: list[float], targets: list[float], active: float | None,
        active_source: int | None, enter_threshold: float, release_threshold: float,
    ) -> tuple[float, float, int] | None:
        """Choose an alignment with hysteresis so guides neither flicker nor feel sticky."""
        if active is not None and active_source is not None and 0 <= active_source < len(sources):
            difference = active - sources[active_source]
            if abs(difference) <= release_threshold:
                return difference, active, active_source
            # Do not switch from center alignment to an edge alignment during
            # the same mouse move; that is perceived as a sudden sticky jump.
            return None
        best: tuple[float, float, int] | None = None
        for source_index, source in enumerate(sources):
            for target in targets:
                difference = target - source
                if abs(difference) <= enter_threshold and (best is None or abs(difference) < abs(best[0])):
                    best = (difference, target, source_index)
        return best

    def _smart_snap_position(self, item: QGraphicsItem, proposed: QPointF) -> QPointF:
        """Snap moving nodes to camera/object rulers and expose alignment guides."""
        current_rect = item.sceneBoundingRect()
        delta = proposed - item.pos()
        proposed_rect = current_rect.translated(delta)
        source_x = [proposed_rect.left(), proposed_rect.center().x(), proposed_rect.right()]
        source_y = [proposed_rect.top(), proposed_rect.center().y(), proposed_rect.bottom()]
        target_x, target_y = self._guide_candidates(item)
        enter = GUIDE_ENTER_PX / max(self._zoom, 0.12)
        release = GUIDE_RELEASE_PX / max(self._zoom, 0.12)
        had_x = self._active_guide_x is not None
        had_y = self._active_guide_y is not None
        best_x = None if self._guide_suppress_x and not had_x else self._best_axis_guide(source_x, target_x, self._active_guide_x, self._active_guide_x_source, enter, release)
        best_y = None if self._guide_suppress_y and not had_y else self._best_axis_guide(source_y, target_y, self._active_guide_y, self._active_guide_y_source, enter, release)
        if had_x and best_x is None:
            self._guide_suppress_x = True
        if had_y and best_y is None:
            self._guide_suppress_y = True
        near_x = any(abs(target - source) <= enter for source in source_x for target in target_x)
        near_y = any(abs(target - source) <= enter for source in source_y for target in target_y)
        if self._guide_suppress_x and not near_x:
            self._guide_suppress_x = False
        if self._guide_suppress_y and not near_y:
            self._guide_suppress_y = False

        adjusted = QPointF(proposed)
        self._active_guide_x = None
        self._active_guide_y = None
        self._active_guide_x_source = None
        self._active_guide_y_source = None
        if best_x is not None:
            adjusted.setX(adjusted.x() + best_x[0])
            self._active_guide_x = best_x[1]
            self._active_guide_x_source = best_x[2]
        if best_y is not None:
            adjusted.setY(adjusted.y() + best_y[0])
            self._active_guide_y = best_y[1]
            self._active_guide_y_source = best_y[2]
        if best_x is not None or best_y is not None:
            self._guide_clear_timer.start(240)
            self.viewport().update()
        data = getattr(item, "metadata", {})
        if str(data.get("component_category", "")).lower() == "background":
            return self._camera_frame.rect().center() if self._camera_frame is not None else adjusted
        return self._position_inside_camera(adjusted, proposed_rect.width(), proposed_rect.height())

    def _clear_smart_guides(self) -> None:
        if self._active_guide_x is None and self._active_guide_y is None and not self._guide_suppress_x and not self._guide_suppress_y:
            return
        self._active_guide_x = None
        self._active_guide_y = None
        self._active_guide_x_source = None
        self._active_guide_y_source = None
        self._guide_suppress_x = False
        self._guide_suppress_y = False
        self.viewport().update()

    @staticmethod
    def _ruler_step(scene_units_per_pixel: float) -> float:
        target = max(1.0, scene_units_per_pixel * 72.0)
        exponent = math.floor(math.log10(target))
        base = 10.0 ** exponent
        for multiplier in (1.0, 2.0, 5.0, 10.0):
            step = base * multiplier
            if step >= target:
                return step
        return base * 10.0

    def _load_editable_nodes(self) -> None:
        children = self._scene_payload.get("children", [])
        if not isinstance(children, list):
            return
        for node in children:
            if not isinstance(node, dict):
                continue
            node_type = str(node.get("type", "")).lower()
            if node_type not in EDITABLE_NODE_TYPES:
                continue
            self._create_item_from_node(node, persist=False)
        for item in list(self._sprite_items.values()):
            self._apply_clipping_mask(item)

    def _create_item_from_node(self, node: dict, persist: bool = False) -> QGraphicsItem | None:
        node_type = str(node.get("type", "")).lower()
        if node_type in {"sprite", "sprite2d", "effect2d"}:
            source = self._resolve_asset_path(str(node.get("asset", "")))
            return self._create_sprite_item(source, node=node, position=None, persist=persist) if source else None
        if node_type == "text2d":
            return self._create_text_item(node, persist=persist)
        return self._create_vector_item(node, persist=persist)

    def _resolve_asset_path(self, value: str) -> Path | None:
        if not value:
            return None
        path = Path(value)
        if not path.is_absolute() and self.project_path is not None:
            path = self.project_path / value.replace("project://", "", 1)
        try:
            path = path.resolve()
        except OSError:
            return None
        return path if path.exists() and path.is_file() else None

    def _relative_asset_path(self, path: Path) -> str:
        if self.project_path is None:
            return path.as_posix()
        try:
            return path.resolve().relative_to(self.project_path).as_posix()
        except (OSError, ValueError):
            return path.as_posix()

    def _ensure_project_asset(self, source: Path) -> Path | None:
        """Copy external/sample-library art into the project before DTFE stores it."""
        try:
            source = source.expanduser().resolve()
        except OSError:
            return None
        if not source.is_file() or source.suffix.lower() not in IMAGE_EXTENSIONS:
            return None
        if self.project_path is None:
            return source
        try:
            source.relative_to(self.project_path)
            return source
        except ValueError:
            destination_dir = self.project_path / "assets" / "imported"
            destination_dir.mkdir(parents=True, exist_ok=True)
            preferred = destination_dir / source.name
            try:
                if preferred.is_file() and filecmp.cmp(source, preferred, shallow=False):
                    return preferred
            except OSError:
                pass
            destination = unique_destination(preferred)
            try:
                shutil.copy2(source, destination)
            except OSError as error:
                self.status_message.emit(f"[Assets] Không thể nhập {source.name}: {error}")
                return None
            self.asset_imported.emit(str(destination))
            self.status_message.emit(f"[Assets] Đã nhập {source.name} vào project://assets/imported/.")
            return destination

    def _base_node(self, node: dict | None, node_type: str, name: str) -> dict:
        data = dict(node or {})
        data.setdefault("id", uuid.uuid4().hex[:12])
        data.setdefault("name", self._unique_node_name(name))
        data.setdefault("code_name", self._unique_code_name(str(data.get("name") or name)))
        data["type"] = node_type
        data.setdefault("position", [0.0, 0.0])
        data.setdefault("rotation", 0.0)
        data.setdefault("scale", [1.0, 1.0])
        data.setdefault("opacity", 1.0)
        data.setdefault("z_index", self._next_z_index())
        data.setdefault("visible", True)
        data.setdefault("locked", False)
        data.setdefault("blend_mode", "Normal")
        data.setdefault("tint", "#FFFFFFFF")
        data.setdefault("group_id", "")
        data.setdefault("resizable", True)
        data.setdefault("lock_aspect", False)
        data.setdefault("events", [])
        data.setdefault("automation", {})
        data.setdefault("clipping_mask", {})
        return data

    @staticmethod
    def _asset_semantics(source: Path) -> dict:
        name = source.stem.lower()
        semantics = {"component_category": "sprite", "ui_role": "", "input_binding": "", "resizable": True, "lock_aspect": False, "automation": {}}
        if (
            source.parent.name.lower() in {"background", "backgrounds"}
            or any(token in name for token in ("background", "backdrop", "battlefield", "scenery"))
            or name.endswith("_240x320")
            or name.endswith("_320x240")
        ):
            semantics.update(
                component_category="background", ui_role="Background",
                resizable=False, lock_aspect=True,
            )
        elif "joystick_left" in name or (name.endswith("left") and "joystick" in name):
            semantics.update(component_category="control", ui_role="DirectionButton", input_binding="MOVE_LEFT", automation={"enabled": True, "role": "direction_button", "input_action": "MOVE_LEFT", "axis": "x", "direction": -1, "physics": "none", "collision_shape": "circle", "tags": ["ui", "movement"]})
        elif "joystick_right" in name or (name.endswith("right") and "joystick" in name):
            semantics.update(component_category="control", ui_role="DirectionButton", input_binding="MOVE_RIGHT", automation={"enabled": True, "role": "direction_button", "input_action": "MOVE_RIGHT", "axis": "x", "direction": 1, "physics": "none", "collision_shape": "circle", "tags": ["ui", "movement"]})
        elif "joystick" in name or "dpad" in name:
            semantics.update(component_category="control", ui_role="VirtualJoystick", input_binding="MOVE_AXIS", automation={"enabled": True, "role": "virtual_joystick", "input_action": "MOVE_AXIS", "axis": "xy", "dead_zone": 0.18, "sensitivity": 1.0, "physics": "none", "collision_shape": "circle", "tags": ["ui", "movement"]})
        elif "jump" in name:
            semantics.update(component_category="control", ui_role="JumpButton", input_binding="JUMP", automation={"enabled": True, "role": "action_button", "input_action": "JUMP", "physics": "none", "collision_shape": "circle", "tags": ["ui", "player_button"]})
        elif "run" in name:
            semantics.update(component_category="control", ui_role="RunButton", input_binding="RUN", automation={"enabled": True, "role": "action_button", "input_action": "RUN", "physics": "none", "collision_shape": "circle", "tags": ["ui", "player_button"]})
        elif "attack" in name:
            semantics.update(component_category="control", ui_role="ActionButton", input_binding="ATTACK", automation={"enabled": True, "role": "action_button", "input_action": "ATTACK", "physics": "none", "collision_shape": "circle", "tags": ["ui", "player_button", "combat"]})
        elif "interact" in name or "use_button" in name:
            semantics.update(component_category="control", ui_role="ActionButton", input_binding="INTERACT", automation={"enabled": True, "role": "action_button", "input_action": "INTERACT", "physics": "none", "collision_shape": "bounds", "tags": ["ui", "player_button"]})
        elif "dash" in name:
            semantics.update(component_category="control", ui_role="ActionButton", input_binding="DASH", automation={"enabled": True, "role": "action_button", "input_action": "DASH", "physics": "none", "collision_shape": "circle", "tags": ["ui", "player_button", "movement"]})
        elif any(token in name for token in ("skill", "spell", "ult")):
            semantics.update(component_category="skill", ui_role="SkillButton", input_binding="SKILL_1", automation={"enabled": True, "role": "skill_button", "input_action": "SKILL_1", "physics": "none", "collision_shape": "circle", "tags": ["ui", "skill_button"]})
        elif "template_player" in name or name.startswith("player_") or "character" in name:
            semantics.update(component_category="character", ui_role="Player", input_binding="", automation={"enabled": True, "role": "player", "input_action": "", "physics": "kinematic", "collision_shape": "bounds", "tags": ["player", "character"], "event_channel": "PLAYER", "auto_execute": True, "movement_mode": "platformer", "move_speed": 260.0, "jump_speed": 560.0, "gravity": 1450.0})
        elif "button" in name:
            semantics.update(component_category="control", ui_role="ActionButton", input_binding="ACTION", automation={"enabled": True, "role": "action_button", "input_action": "ACTION", "physics": "none", "collision_shape": "bounds", "tags": ["ui"]})
        elif "tileset" in name or source.parent.name.lower() == "tileset" or name.startswith("frame_"):
            semantics.update(component_category="tileset", ui_role="TileSetItem", input_binding="", automation={})
        return semantics

    def _create_sprite_item(
        self,
        source: Path | None,
        *,
        node: dict | None = None,
        position: QPointF | None,
        persist: bool,
    ) -> SceneAssetItem | None:
        if source is None:
            return None
        if self.project_path is not None:
            try:
                source.resolve().relative_to(self.project_path)
            except (OSError, ValueError):
                self.status_message.emit("[Scene] Hãy nhập ảnh vào Assets trước khi kéo vào camera preview.")
                return None
        pixmap = QPixmap(str(source))
        if pixmap.isNull():
            self.status_message.emit(f"[Scene] Không thể đọc ảnh: {source.name}")
            return None
        data = self._base_node(node, str((node or {}).get("type", "Sprite2D")), source.stem)
        data["asset"] = self._relative_asset_path(source)
        semantics = self._asset_semantics(source)
        for key, value in semantics.items():
            if key == "automation":
                if not isinstance(data.get("automation"), dict) or not data.get("automation"):
                    data["automation"] = copy.deepcopy(value)
            else:
                data.setdefault(key, value)
        if semantics.get("component_category") == "background":
            camera = self._camera_frame.rect() if self._camera_frame is not None else QRectF(-120, -160, 240, 320)
            data.update({
                "component_category": "background",
                "ui_role": "Background",
                "position": [camera.center().x(), camera.center().y()],
                "scale": [camera.width() / pixmap.width(), camera.height() / pixmap.height()],
                "resizable": False,
                "lock_aspect": True,
                "locked": True,
            })
            position = camera.center()
            if node is None:
                data["z_index"] = min(
                    (int(existing.zValue()) for existing in self._node_items.values()),
                    default=0,
                ) - 1
        item = SceneAssetItem(pixmap, data, self)
        item.setOffset(-pixmap.width() / 2, -pixmap.height() / 2)
        self._apply_common_item_state(item, data, position)
        self.scene().addItem(item)
        self._sprite_items[str(data["id"])] = item
        self._node_items[str(data["id"])] = item
        if persist:
            self._select_item(item)
            self._queue_save()
            self.status_message.emit(f"[Scene] Đã thêm {source.name} vào camera preview.")
        return item

    def _apply_clipping_mask(self, item: SceneAssetItem) -> None:
        data = getattr(item, "metadata", {})
        mask = data.get("clipping_mask") if isinstance(data.get("clipping_mask"), dict) else {}
        if not mask.get("enabled"):
            return
        source_id = str(mask.get("source_id", ""))
        source_item = self._sprite_items.get(source_id)
        if source_item is None or source_item is item:
            return
        content = item.pixmap()
        source = source_item.pixmap()
        if content.isNull() or source.isNull():
            return
        target = QPixmap(content.size())
        target.fill(Qt.GlobalColor.transparent)
        painter = QPainter(target)
        painter.drawPixmap(0, 0, content)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationIn)
        painter.drawPixmap(target.rect(), source, source.rect())
        painter.end()
        item.setPixmap(target)
        item.setOffset(-target.width() / 2, -target.height() / 2)
        item.setToolTip(f"Clipping Mask • nguồn: {source_id}")

    def set_selected_events(self, mapping: dict) -> bool:
        selected = self._selected_items()
        if not selected and not self._selected_group_id:
            return False
        event = {
            "trigger": str(mapping.get("trigger", "on_click")),
            "action": str(mapping.get("action", "change_screen")),
            "target_screen": str(mapping.get("target_screen", "")),
            "parameter": str(mapping.get("parameter", "")),
            "enabled": bool(mapping.get("enabled", True)),
        }
        if self._selected_group_id:
            group = self._group_by_id(self._selected_group_id)
            if group is None:
                return False
            group.setdefault("events", []).append(event)
        else:
            for selected_item in selected:
                data = getattr(selected_item, "metadata", {})
                data.setdefault("events", []).append(copy.deepcopy(event))
                self._sync_item_metadata(selected_item)
        self._queue_save()
        self._emit_selection()
        self.status_message.emit(f"[Event] Đã ánh xạ {event['trigger']} → {event['action']}.")
        return True

    @staticmethod
    def _legacy_semantics_from_automation(mapping: dict) -> tuple[str, str, str]:
        role = str(mapping.get("role", "custom"))
        input_action = str(mapping.get("input_action", ""))
        ui_roles = {
            "virtual_joystick": "VirtualJoystick",
            "direction_button": "DirectionButton",
            "action_button": "ActionButton",
            "skill_button": "SkillButton",
            "ground": "Ground",
            "one_way_platform": "OneWayPlatform",
            "static_obstacle": "StaticObstacle",
            "hazard": "HazardZone",
            "trigger_zone": "TriggerZone",
            "portal": "Portal",
            "collectible": "Collectible",
            "player": "Player",
            "enemy": "Enemy",
            "spawn_point": "SpawnPoint",
            "camera_target": "CameraTarget",
            "decoration": "Decoration",
        }
        categories = {
            "virtual_joystick": "control", "direction_button": "control",
            "action_button": "control", "skill_button": "skill",
            "ground": "terrain", "one_way_platform": "terrain",
            "static_obstacle": "terrain", "hazard": "trigger",
            "trigger_zone": "trigger", "portal": "trigger",
            "collectible": "gameplay", "player": "character",
            "enemy": "character", "spawn_point": "gameplay",
            "camera_target": "gameplay", "decoration": "sprite",
        }
        return ui_roles.get(role, ""), input_action, categories.get(role, "sprite")

    def set_selected_automation(self, mapping: dict) -> bool:
        selected = self._selected_items()
        if not selected and not self._selected_group_id:
            return False
        clean = copy.deepcopy(mapping if isinstance(mapping, dict) else {})
        clean.setdefault("enabled", True)
        clean.setdefault("role", "custom")
        clean.setdefault("input_action", "")
        clean.setdefault("physics", "none")
        clean.setdefault("collision_shape", "bounds")
        clean.setdefault("tags", [])
        ui_role, input_binding, category = self._legacy_semantics_from_automation(clean)

        def apply_generated_event(data: dict) -> None:
            role = str(clean.get("role", ""))
            target = str(clean.get("target_screen", ""))
            channel = str(clean.get("event_channel", ""))
            generated: dict | None = None
            if role == "portal" and target:
                generated = {"trigger": "on_overlap", "action": "change_screen", "target_screen": target, "parameter": "", "enabled": True, "generated_by": "automation"}
            elif role in {"hazard", "collectible", "trigger_zone"} and channel:
                generated = {"trigger": "on_overlap", "action": "emit_signal", "target_screen": "", "parameter": channel, "enabled": True, "generated_by": "automation"}
            if generated is None:
                return
            events = data.setdefault("events", [])
            signature = (generated["trigger"], generated["action"], generated["target_screen"], generated["parameter"])
            exists = any(
                isinstance(event, dict) and
                (str(event.get("trigger", "")), str(event.get("action", "")), str(event.get("target_screen", "")), str(event.get("parameter", ""))) == signature
                for event in events
            )
            if not exists:
                events.append(generated)

        if self._selected_group_id:
            group = self._group_by_id(self._selected_group_id)
            if group is None:
                return False
            group["automation"] = clean
            group["ui_role"] = ui_role
            group["input_binding"] = input_binding
            group["component_category"] = category
            # Runtime automation is node-based. Applying a role to a group mirrors
            # the mapping to each member so the generated C bindings work.
            for member in self._group_members(self._selected_group_id):
                data = getattr(member, "metadata", {})
                data["automation"] = copy.deepcopy(clean)
                data["ui_role"] = ui_role
                data["input_binding"] = input_binding
                data["component_category"] = category
                apply_generated_event(data)
                self._sync_item_metadata(member)
        else:
            for selected_item in selected:
                data = getattr(selected_item, "metadata", {})
                data["automation"] = copy.deepcopy(clean)
                data["ui_role"] = ui_role
                data["input_binding"] = input_binding
                data["component_category"] = category
                apply_generated_event(data)
                self._sync_item_metadata(selected_item)
        self._queue_save()
        self._emit_selection()
        self.status_message.emit(
            f"[Automation] Đã gán role={clean.get('role')} • input={clean.get('input_action') or 'none'} • physics={clean.get('physics')}."
        )
        return True

    def _selected_automation_payload(self) -> dict:
        selected = self._selected_items()
        if self._selected_group_id:
            group = self._group_by_id(self._selected_group_id) or {}
            return {
                "kind": "group", "id": self._selected_group_id, "name": str(group.get("name", "Group")),
                "automation": copy.deepcopy(group.get("automation", {})),
                "ui_role": str(group.get("ui_role", "")), "input_binding": str(group.get("input_binding", "")),
                "screen_id": self.screen_id, "scene_file": str(self.scene_file or ""),
            }
        if selected:
            return self._item_payload(selected[0])
        return {}

    def _selected_event_payload(self, preset_trigger: str = "") -> dict:
        selected = self._selected_items()
        if self._selected_group_id:
            group = self._group_by_id(self._selected_group_id) or {}
            return {
                "kind": "group", "id": self._selected_group_id, "name": str(group.get("name", "Group")),
                "events": list(group.get("events", [])), "preset_trigger": preset_trigger,
                "screen_id": self.screen_id, "scene_file": str(self.scene_file or ""),
            }
        if selected:
            payload = self._item_payload(selected[0])
            payload["preset_trigger"] = preset_trigger
            return payload
        return {}

    def _create_vector_item(self, node: dict, persist: bool = False) -> SceneVectorItem | None:
        data = self._base_node(node, str(node.get("type", "Rectangle2D")), str(node.get("name", "Vector")))
        shape = data.setdefault("shape", {})
        component = data.get("component") if isinstance(data.get("component"), dict) else {}
        is_background = (
            str(data.get("component_category", "")).lower() == "background"
            or str(data.get("ui_role", "")).lower() == "background"
            or str(data.get("name", "")).strip().lower() == "background"
        )
        if is_background:
            # Old projects stored `size` and `fill` at node level. Normalize
            # them while loading and pin the background to the physical screen.
            shape.update({
                "width": float(self._camera_width),
                "height": float(self._camera_height),
                "fill": str(shape.get("fill") or data.get("fill") or "#0F1B2E"),
                "stroke": str(shape.get("stroke") or "#263B57"),
                "stroke_width": 0.0,
            })
            center = self._camera_frame.rect().center() if self._camera_frame is not None else QPointF()
            data.update({
                "component_category": "background", "ui_role": "Background",
                "position": [center.x(), center.y()], "scale": [1.0, 1.0],
                "display_size": [self._camera_width, self._camera_height],
                "resizable": False, "lock_aspect": True, "locked": True,
                "pixel_snap": True, "z_index": min(int(data.get("z_index", -10)), -10),
            })
        is_canvas_guide = (
            str(data.get("ui_role", "")).lower() == "canvas"
            or str(component.get("kind", "")).lower() == "canvas"
        )
        if is_canvas_guide:
            # Photoshop-like canvas/frame objects are guides, not opaque paint
            # layers. Also upgrades old "Vùng_vẽ" nodes that used #111827 and
            # hid a background after it was sent to the bottom.
            shape["fill"] = "#00000000"
            shape.setdefault("stroke", "#556B8A80")
            data["editor_guide"] = True
        kind = str(data.get("type", "Rectangle2D")).lower()
        path = QPainterPath()
        if kind in {"rectangle2d", "tile2d"}:
            width = max(1.0, float(shape.get("width", self.grid_size)))
            height = max(1.0, float(shape.get("height", self.grid_size)))
            radius = max(0.0, min(float(shape.get("corner_radius", 0)), min(width, height) / 2))
            rect = QRectF(-width / 2, -height / 2, width, height)
            path.addRoundedRect(rect, radius, radius) if radius > 0 else path.addRect(rect)
        elif kind == "circle2d":
            width = max(1.0, float(shape.get("width", 64)))
            height = max(1.0, float(shape.get("height", width)))
            path.addEllipse(-width / 2, -height / 2, width, height)
        else:
            points = shape.get("points", [[0, 0], [64, 0]])
            if isinstance(points, list) and points:
                first = self._point_from(points[0], QPointF(0, 0))
                path.moveTo(first)
                for value in points[1:]:
                    path.lineTo(self._point_from(value, first))
        item = SceneVectorItem(path, data, self)
        fill = parse_color(shape.get("fill", DEFAULT_FILL), DEFAULT_FILL)
        stroke = parse_color(shape.get("stroke", DEFAULT_STROKE), DEFAULT_STROKE)
        width = max(0.0, float(shape.get("stroke_width", 2.0)))
        pen = QPen(stroke, width)
        pen.setCosmetic(True)
        item.setPen(pen)
        item.setBrush(QBrush(fill if kind not in {"line2d", "brush2d"} else Qt.BrushStyle.NoBrush))
        self._apply_common_item_state(item, data, None)
        self.scene().addItem(item)
        self._node_items[str(data["id"])] = item
        if persist:
            self._select_item(item)
            self._queue_save()
        return item

    def _create_text_item(self, node: dict, persist: bool = False) -> SceneTextItem:
        data = self._base_node(node, "Text2D", str(node.get("name", "Text")))
        text_data = data.setdefault("text", {})
        content = str(text_data.get("content", data.get("content", "Text")))
        font_size = max(6, int(text_data.get("font_size", 24)))
        color = parse_color(text_data.get("color", "#F4F7FF"), "#F4F7FF")
        item = SceneTextItem(content, data, self)
        font = QFont(str(text_data.get("font", "Segoe UI")), font_size)
        font.setBold(bool(text_data.get("bold", False)))
        font.setItalic(bool(text_data.get("italic", False)))
        font.setUnderline(bool(text_data.get("underline", False)))
        font.setStrikeOut(bool(text_data.get("strikeout", False)))
        item.setFont(font)
        layout_data = data.get("layout") if isinstance(data.get("layout"), dict) else {}
        if "padding" in layout_data:
            item.document().setDocumentMargin(max(0.0, float(layout_data.get("padding", 0))))
        item.setDefaultTextColor(color)
        self._apply_common_item_state(item, data, None)
        self.scene().addItem(item)
        self._node_items[str(data["id"])] = item
        if persist:
            self._select_item(item)
            self._queue_save()
        return item

    def _apply_common_item_state(self, item: QGraphicsItem, data: dict, position: QPointF | None) -> None:
        item.setPos(position if position is not None else self._point_from(data.get("position"), QPointF(0, 0)))
        item.setRotation(float(data.get("rotation", 0)))
        scale = data.get("scale", [1, 1])
        try:
            sx = float(scale[0])
            sy = float(scale[1] if len(scale) > 1 else scale[0])
        except (TypeError, ValueError, IndexError):
            sx = sy = 1.0
        item.setTransform(QTransform.fromScale(sx, sy))
        item.setZValue(float(data.get("z_index", 0)))
        self._apply_effective_item_state(item)

    @staticmethod
    def _point_from(value, fallback: QPointF) -> QPointF:
        if isinstance(value, (list, tuple)) and len(value) >= 2:
            try:
                return QPointF(float(value[0]), float(value[1]))
            except (TypeError, ValueError):
                pass
        return QPointF(fallback)

    def _next_z_index(self) -> int:
        return max((int(round(item.zValue())) for item in self._node_items.values()), default=-1) + 1

    def _unique_code_name(self, base: str, exclude_item: QGraphicsItem | None = None) -> str:
        clean = "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in str(base)).strip("_") or "Node"
        if clean[0].isdigit():
            clean = f"Node_{clean}"
        parts = [part for part in clean.split("_") if part]
        clean = "".join(part[:1].upper() + part[1:] for part in parts) or "Node"
        existing = {
            str(getattr(item, "metadata", {}).get("code_name", "")).lower()
            for item in self._node_items.values() if item is not exclude_item
        }
        candidate = clean
        index = 2
        while candidate.lower() in existing:
            candidate = f"{clean}{index}"
            index += 1
        return candidate

    def _unique_group_name(self) -> str:
        existing = {str(group.get("name", "")).lower() for group in self._groups()}
        index = 1
        while f"group_{index}" in existing or f"group {index}" in existing:
            index += 1
        return f"Group_{index}"

    def _unique_node_name(self, base: str) -> str:
        clean = "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in base).strip("_") or "Node"
        existing = {str(getattr(item, "metadata", {}).get("name", "")) for item in self._node_items.values()}
        if clean not in existing:
            return clean
        index = 2
        while f"{clean}_{index}" in existing:
            index += 1
        return f"{clean}_{index}"

    def _sync_item_metadata(self, item: QGraphicsItem) -> None:
        data = getattr(item, "metadata", None)
        if not isinstance(data, dict):
            return
        group_id = str(data.get("group_id", ""))
        group_opacity = self._group_opacity(group_id)
        local_opacity = float(data.get("opacity", 1.0))
        if group_opacity > 0.0001 and not self._loading:
            local_opacity = max(0.0, min(1.0, item.opacity() / group_opacity))
        # Logical W/H must not change when Rotation changes.  sceneBoundingRect()
        # is an axis-aligned rotated box and therefore cannot represent editable
        # component size (a 45-degree sprite appeared wider in Inspector).
        local_bounds = item.boundingRect()
        display_width = local_bounds.width() * abs(item.transform().m11())
        display_height = local_bounds.height() * abs(item.transform().m22())
        if isinstance(item, SceneAssetItem):
            # QGraphicsPixmapItem adds an interaction margin to boundingRect.
            display_width = item.pixmap().width() * abs(item.transform().m11())
            display_height = item.pixmap().height() * abs(item.transform().m22())
        elif isinstance(item, SceneVectorItem):
            # QGraphicsPathItem.boundingRect() includes half the outline pen.
            # Inspector W/H and exported bitmap must describe the component's
            # actual geometry, not grow whenever Stroke Width changes.
            shape = data.get("shape") if isinstance(data.get("shape"), dict) else {}
            display_width = float(shape.get("width", local_bounds.width())) * abs(item.transform().m11())
            display_height = float(shape.get("height", local_bounds.height())) * abs(item.transform().m22())
        data.update({
            "position": [round(item.pos().x(), 3), round(item.pos().y(), 3)],
            "rotation": round(item.rotation(), 3),
            "scale": [round(item.transform().m11(), 4), round(item.transform().m22(), 4)],
            "display_size": [round(display_width, 3), round(display_height, 3)],
            "opacity": round(local_opacity, 4),
            "z_index": int(round(item.zValue())),
            "visible": bool(data.get("visible", True)) if not self._group_visible(group_id) else item.isVisible(),
            "locked": bool(data.get("locked", False)),
            "blend_mode": str(data.get("blend_mode", "Normal")),
            "tint": str(data.get("tint", "#FFFFFFFF")),
            "pixel_snap": bool(data.get("pixel_snap", True)),
            "lock_aspect": bool(data.get("lock_aspect", False)),
            "code_name": str(data.get("code_name") or self._unique_code_name(str(data.get("name", "Node")), item)),
        })
        if isinstance(item, SceneTextItem):
            data.setdefault("text", {})["content"] = item.toPlainText()
            data["text"]["font_size"] = item.font().pointSize()
            data["text"]["font"] = item.font().family()
            data["text"]["color"] = format_hex(item.defaultTextColor())
            data["text"]["bold"] = item.font().bold()
            data["text"]["italic"] = item.font().italic()
            data["text"]["underline"] = item.font().underline()
            data["text"]["strikeout"] = item.font().strikeOut()

    def _item_payload(self, item: QGraphicsItem) -> dict:
        self._sync_item_metadata(item)
        payload = dict(getattr(item, "metadata", {}))
        node_type = str(payload.get("type", "Node")).lower()
        if node_type in {"sprite", "sprite2d", "effect2d"}:
            payload["kind"] = "sprite"
            if isinstance(item, SceneAssetItem):
                payload["size"] = [item.pixmap().width(), item.pixmap().height()]
        elif node_type == "text2d":
            payload["kind"] = "text"
            payload["size"] = [round(item.boundingRect().width()), round(item.boundingRect().height())]
        else:
            payload["kind"] = "shape"
            payload["size"] = [round(item.boundingRect().width()), round(item.boundingRect().height())]
        group = self._group_by_id(str(payload.get("group_id", "")))
        payload["group_name"] = str(group.get("name", "")) if group else ""
        payload["effective_opacity"] = round(item.opacity(), 4)
        payload["screen_id"] = self.screen_id
        return payload

    def camera_payload(self) -> dict:
        camera = dict(self._camera_node())
        camera.update({
            "kind": "camera",
            "name": str(camera.get("name", "Camera2D")),
            "type": str(camera.get("type", "OrthographicCamera")),
            "position": camera.get("position", [0, 0]),
            "zoom": camera.get("zoom", [1, 1]),
            "viewport": [self._camera_width, self._camera_height],
            "screen_id": str(self._scene_payload.get("screen_id") or self.screen_id),
            "screen_name": self.screen_name,
            "scene_file": str(self.scene_file or ""),
        })
        return camera

    def _item_transform_changed(self, item: QGraphicsItem) -> None:
        if self._loading or item not in self._node_items.values():
            return
        self._sync_item_metadata(item)
        if item.isSelected():
            self.selection_changed.emit(self._item_payload(item))
        self._queue_save()

    def _select_item(self, item: QGraphicsItem, *, preserve_group: bool = False) -> None:
        if not preserve_group:
            self._selected_group_id = None
        self.scene().clearSelection()
        item.setSelected(True)
        self.selection_changed.emit(self._item_payload(item))

    def _selected_items(self) -> list[QGraphicsItem]:
        if not isValid(self):
            return []
        return [item for item in self.scene().selectedItems() if item in self._node_items.values()]

    def _begin_group_drag(self, item: QGraphicsItem, scene_pos: QPointF, modifiers: Qt.KeyboardModifiers) -> bool:
        """Select and drag every member of a group as one layout unit.

        Ctrl-click intentionally bypasses group selection so an individual member
        can still be edited without ungrouping.
        """
        if modifiers & Qt.KeyboardModifier.ControlModifier:
            return False
        data = getattr(item, "metadata", {})
        group_id = str(data.get("group_id", ""))
        if not group_id or self._group_locked(group_id):
            return False
        members = self._group_members(group_id)
        if not members:
            return False
        self.scene().clearSelection()
        for member in members:
            member.setSelected(True)
        self._selected_group_id = group_id
        self._group_drag = {
            "group_id": group_id,
            "start": QPointF(scene_pos),
            "origins": {member: QPointF(member.pos()) for member in members},
        }
        self.selection_changed.emit(self._group_payload(group_id))
        self.viewport().setCursor(Qt.CursorShape.ClosedHandCursor)
        return True

    def _move_group_drag(self, scene_pos: QPointF) -> None:
        if self._group_drag is None:
            return
        start = self._group_drag["start"]
        delta = scene_pos - start
        origins = self._group_drag["origins"]
        if self.snap_enabled and origins:
            delta = self._snap_group_delta(origins, delta)
        if origins and self._camera_frame is not None:
            bounds = self._group_bounds(origins).translated(delta)
            camera = self._camera_frame.rect()
            if bounds.width() <= camera.width():
                if bounds.left() < camera.left(): delta.setX(delta.x() + camera.left() - bounds.left())
                elif bounds.right() > camera.right(): delta.setX(delta.x() + camera.right() - bounds.right())
            if bounds.height() <= camera.height():
                if bounds.top() < camera.top(): delta.setY(delta.y() + camera.top() - bounds.top())
                elif bounds.bottom() > camera.bottom(): delta.setY(delta.y() + camera.bottom() - bounds.bottom())
        self._loading = True
        try:
            for member, origin in origins.items():
                member.setPos(origin + delta)
                self._sync_item_metadata(member)
        finally:
            self._loading = False
        group_id = str(self._group_drag.get("group_id", ""))
        if group_id:
            self.selection_changed.emit(self._group_payload(group_id))
        self.viewport().update()

    def _group_bounds(self, origins: dict) -> QRectF:
        """Khung bao quanh nhóm tại vị trí gốc lúc bắt đầu kéo."""
        bounds = QRectF()
        for member, origin in origins.items():
            rect = QRectF(member.sceneBoundingRect())
            rect.translate(QPointF(origin) - member.pos())
            bounds = rect if bounds.isNull() else bounds.united(rect)
        return bounds

    def _snap_group_delta(self, origins: dict, delta: QPointF) -> QPointF:
        """Snap cả khung nhóm theo lưới và guide — giữ nguyên bố cục nội bộ."""
        bounds = self._group_bounds(origins)
        if bounds.isNull():
            return delta
        proposed = bounds.translated(delta)
        corner = self._soft_grid_snap_point(proposed.topLeft())
        adjusted = QPointF(
            delta.x() + corner.x() - proposed.topLeft().x(),
            delta.y() + corner.y() - proposed.topLeft().y(),
        )
        proposed = bounds.translated(adjusted)
        source_x = [proposed.left(), proposed.center().x(), proposed.right()]
        source_y = [proposed.top(), proposed.center().y(), proposed.bottom()]
        target_x, target_y = self._guide_candidates(set(origins.keys()))
        enter = GUIDE_ENTER_PX / max(self._zoom, 0.12)
        release = GUIDE_RELEASE_PX / max(self._zoom, 0.12)
        had_x = self._active_guide_x is not None
        had_y = self._active_guide_y is not None
        best_x = None if self._guide_suppress_x and not had_x else self._best_axis_guide(source_x, target_x, self._active_guide_x, self._active_guide_x_source, enter, release)
        best_y = None if self._guide_suppress_y and not had_y else self._best_axis_guide(source_y, target_y, self._active_guide_y, self._active_guide_y_source, enter, release)
        if had_x and best_x is None:
            self._guide_suppress_x = True
        if had_y and best_y is None:
            self._guide_suppress_y = True
        near_x = any(abs(target - source) <= enter for source in source_x for target in target_x)
        near_y = any(abs(target - source) <= enter for source in source_y for target in target_y)
        if self._guide_suppress_x and not near_x:
            self._guide_suppress_x = False
        if self._guide_suppress_y and not near_y:
            self._guide_suppress_y = False
        self._active_guide_x = None
        self._active_guide_y = None
        self._active_guide_x_source = None
        self._active_guide_y_source = None
        if best_x is not None:
            adjusted.setX(adjusted.x() + best_x[0])
            self._active_guide_x = best_x[1]
            self._active_guide_x_source = best_x[2]
        if best_y is not None:
            adjusted.setY(adjusted.y() + best_y[0])
            self._active_guide_y = best_y[1]
            self._active_guide_y_source = best_y[2]
        if best_x is not None or best_y is not None:
            self._guide_clear_timer.start(240)
            self.viewport().update()
        return adjusted

    def _end_group_drag(self) -> None:
        if self._group_drag is None:
            return
        group_id = str(self._group_drag.get("group_id", ""))
        self._group_drag = None
        self.viewport().setCursor(Qt.CursorShape.ArrowCursor)
        self._save_scene()
        self._record_history()
        if group_id:
            self.selection_changed.emit(self._group_payload(group_id))
            self.status_message.emit("[Scene] Đã di chuyển toàn bộ layout trong nhóm.")

    def take_asset_edit_context(self) -> dict | None:
        context = copy.deepcopy(self._pending_asset_edit_context) if self._pending_asset_edit_context else None
        self._pending_asset_edit_context = None
        return context

    def refresh_asset(self, file_path: str | Path) -> int:
        """Reload every scene sprite that references the saved image."""
        try:
            target = Path(file_path).expanduser().resolve()
        except OSError:
            return 0
        pixmap = QPixmap(str(target))
        if pixmap.isNull():
            return 0
        refreshed = 0
        for item in list(self._sprite_items.values()):
            data = getattr(item, "metadata", {})
            source = self._resolve_asset_path(str(data.get("asset", "")))
            if source is None:
                continue
            try:
                matches = source.resolve() == target
            except OSError:
                matches = False
            if not matches:
                continue
            item.setPixmap(pixmap)
            item.setOffset(-pixmap.width() / 2, -pixmap.height() / 2)
            item.setTransformOriginPoint(item.boundingRect().center())
            refreshed += 1
        if refreshed:
            self.viewport().update()
            self._emit_selection()
            self.status_message.emit(f"[Scene] Đã đồng bộ {refreshed} thành phần từ {target.name}.")
        return refreshed

    def apply_asset_editor_result(self, file_path: str | Path, context: dict | None) -> bool:
        """Apply an Editor Assets result back to the exact selected node/group."""
        if not context:
            return bool(self.refresh_asset(file_path))
        try:
            output = Path(file_path).expanduser().resolve()
        except OSError:
            return False
        mode = str(context.get("mode", ""))
        node_ids = [str(value) for value in context.get("node_ids", []) if str(value)]
        if mode == "update_sprite" and node_ids:
            item = self._node_items.get(node_ids[0])
            if not isinstance(item, SceneAssetItem):
                return False
            data = getattr(item, "metadata", {})
            data["asset"] = self._relative_asset_path(output)
            pixmap = QPixmap(str(output))
            if pixmap.isNull():
                return False
            item.setPixmap(pixmap)
            item.setOffset(-pixmap.width() / 2, -pixmap.height() / 2)
            item.setTransformOriginPoint(item.boundingRect().center())
            self._select_item(item)
            self._save_scene()
            self._record_history()
            self.status_message.emit(f"[Scene] Đã áp dụng {output.name} vào {data.get('name', 'Sprite2D')}.")
            return True

        selected_items = [self._node_items.get(node_id) for node_id in node_ids]
        selected_items = [item for item in selected_items if item is not None]
        if not selected_items:
            return False
        center_data = context.get("center", [0, 0])
        center = self._point_from(center_data, QPointF(0, 0))
        name = str(context.get("name") or "EditedAsset")
        z_index = int(context.get("z_index", min((int(item.zValue()) for item in selected_items), default=0)))
        group_id = str(context.get("group_id", ""))
        created = None
        self._loading = True
        try:
            for item in selected_items:
                node_id = str(getattr(item, "metadata", {}).get("id", ""))
                self._node_items.pop(node_id, None)
                self._sprite_items.pop(node_id, None)
                self.scene().removeItem(item)
            if group_id:
                self._scene_payload["groups"] = [
                    group for group in self._groups() if str(group.get("id", "")) != group_id
                ]
            node = self._base_node(None, "Sprite2D", name)
            node["asset"] = self._relative_asset_path(output)
            node["position"] = [center.x(), center.y()]
            node["z_index"] = z_index
            created = self._create_sprite_item(output, node=node, position=center, persist=False)
        finally:
            self._loading = False
        self._selected_group_id = None
        if created is None:
            return False
        self._select_item(created)
        self._save_scene()
        self._record_history()
        self.status_message.emit(f"[Scene] Đã áp dụng bản chỉnh sửa {output.name} vào Frame Preview.")
        return True

    def _node_item_at(self, view_position: QPoint) -> QGraphicsItem | None:
        """Node item dưới con trỏ — bỏ qua overlay (camera frame/nhãn) không nhận chuột."""
        scene_position = self.mapToScene(view_position)
        node_items = set(self._node_items.values())
        for item in self.scene().items(scene_position):
            if item in node_items and item.acceptedMouseButtons() & Qt.MouseButton.LeftButton:
                return item
        return None

    def select_node(self, payload: dict | None) -> None:
        data = dict(payload or {})
        node_type = str(data.get("type", "")).lower()
        node_kind = str(data.get("kind", "")).lower()
        node_name = str(data.get("name", ""))
        node_id = str(data.get("id", ""))
        if node_kind == "group" or node_type == "group2d":
            members = self._group_members(node_id)
            self.scene().clearSelection()
            self._selected_group_id = node_id if members else None
            for member in members:
                member.setSelected(True)
            if members:
                self.selection_changed.emit(self._group_payload(node_id))
                rect = members[0].sceneBoundingRect()
                for member in members[1:]:
                    rect = rect.united(member.sceneBoundingRect())
                self.ensureVisible(rect, 80, 80)
            self.setFocus()
            return
        if node_kind in {"scene", "camera"} or "camera" in node_type or "camera" in node_name.lower():
            self.scene().clearSelection()
            self._selected_group_id = None
            camera = self.camera_payload()
            self.centerOn(self._point_from(camera.get("position"), QPointF(0, 0)))
            self.selection_changed.emit(camera)
            self.setFocus()
            return
        target = self._node_items.get(node_id)
        if target is None and node_name:
            target = next((item for item in self._node_items.values() if getattr(item, "metadata", {}).get("name") == node_name), None)
        if target is None:
            self.status_message.emit(f"[Scene] Không tìm thấy node: {node_name or node_id or 'Node'}")
            return
        self._select_item(target)
        self.ensureVisible(target, 80, 80)
        self.setFocus()

    def _emit_selection(self) -> None:
        # A queued selection notification can outlive a closing editor by one
        # event-loop turn. Avoid dereferencing its destroyed C++ view.
        if not isValid(self):
            return
        selected = self._selected_items()
        if self._selected_group_id and selected:
            members = self._group_members(self._selected_group_id)
            if members and all(member in selected for member in members):
                self.selection_changed.emit(self._group_payload(self._selected_group_id))
                return
            self._selected_group_id = None
        if len(selected) > 1:
            self.selection_changed.emit({
                "kind": "multi", "name": f"{len(selected)} thành phần", "type": "MultiSelection",
                "member_count": len(selected), "opacity": 1.0, "visible": True, "locked": False,
                "size": [0, 0], "screen_id": self.screen_id,
            })
            return
        self.selection_changed.emit(self._item_payload(selected[0]) if selected else self.camera_payload())

    def update_selected_property(self, key: str, value) -> None:
        if self._selected_group_id:
            self._update_group_property(self._selected_group_id, key, value)
            return
        selected = self._selected_items()
        if not selected:
            self._update_camera_property(key, value)
            return

        # Properties that naturally apply to all selected nodes make multi-selection
        # useful for level design without forcing the user to edit one object at a time.
        bulk_keys = {"opacity", "visible", "locked", "blend_mode", "tint", "z_index"}
        targets = selected if len(selected) > 1 and key in bulk_keys else [selected[0]]
        self._loading = True
        try:
            for item in targets:
                data = getattr(item, "metadata", {})
                if key == "name":
                    data["name"] = str(value).strip() or data.get("name", "Node")
                    item.setToolTip(str(data["name"]))
                elif key == "code_name":
                    data["code_name"] = self._unique_code_name(str(value), item)
                elif key == "position_x":
                    item.setX(float(value))
                elif key == "position_y":
                    item.setY(float(value))
                elif key == "rotation":
                    item.setRotation(float(value))
                elif key == "scale_x":
                    item.setTransform(QTransform.fromScale(float(value), item.transform().m22()))
                elif key == "scale_y":
                    item.setTransform(QTransform.fromScale(item.transform().m11(), float(value)))
                elif key in {"size_width", "size_height"}:
                    self._set_item_dimension(item, key, float(value))
                elif key == "lock_aspect":
                    data["lock_aspect"] = bool(value)
                elif key == "pixel_snap":
                    data["pixel_snap"] = bool(value)
                    if bool(value):
                        item.setPos(round(item.x()), round(item.y()))
                elif key == "anchor_mode":
                    data["anchor"] = self._anchor_payload(str(value))
                elif key == "opacity":
                    data["opacity"] = max(0.0, min(1.0, float(value)))
                    self._apply_effective_item_state(item)
                elif key == "z_index":
                    data["z_index"] = int(value)
                    item.setZValue(float(value))
                elif key == "visible":
                    data["visible"] = bool(value)
                    self._apply_effective_item_state(item)
                elif key == "locked":
                    data["locked"] = bool(value)
                    self._refresh_item_flags(item)
                elif key == "blend_mode":
                    data["blend_mode"] = str(value or "Normal")
                elif key == "tint":
                    data["tint"] = str(value or "#FFFFFFFF")
                elif key == "background_bitmap" and isinstance(item, SceneVectorItem):
                    raw_value = str(value)
                    resolved = self._resolve_asset_path(raw_value) if raw_value else None
                    source = self._ensure_project_asset(resolved or Path(raw_value)) if raw_value else None
                    data["background_bitmap"] = self._relative_asset_path(source) if source is not None else ""
                    item.refresh_background_bitmap()
                elif key == "background_bitmap_mode" and isinstance(item, SceneVectorItem):
                    mode = str(value or "Fill").title()
                    data["background_bitmap_mode"] = mode if mode in {"Fill", "Fit", "Stretch", "Tile"} else "Fill"
                    item.update()
                elif key == "fill_color" and isinstance(item, SceneVectorItem):
                    data.setdefault("shape", {})["fill"] = str(value)
                    item.setBrush(QBrush(parse_color(value, DEFAULT_FILL)))
                elif key == "stroke_color" and isinstance(item, SceneVectorItem):
                    data.setdefault("shape", {})["stroke"] = str(value)
                    pen = item.pen(); pen.setColor(parse_color(value, DEFAULT_STROKE)); item.setPen(pen)
                elif key == "stroke_width" and isinstance(item, SceneVectorItem):
                    data.setdefault("shape", {})["stroke_width"] = float(value)
                    pen = item.pen(); pen.setWidthF(float(value)); item.setPen(pen)
                elif key == "corner_radius" and isinstance(item, SceneVectorItem):
                    data.setdefault("shape", {})["corner_radius"] = max(0.0, float(value))
                    self._rebuild_vector_path(item)
                elif key in {"padding", "margin"}:
                    data.setdefault("layout", {})[key] = max(0, int(value))
                    if key == "padding" and isinstance(item, SceneTextItem):
                        item.document().setDocumentMargin(max(0.0, float(value)))
                elif key == "text_content" and isinstance(item, SceneTextItem):
                    item.setPlainText(str(value))
                elif key == "font_size" and isinstance(item, SceneTextItem):
                    font = item.font(); font.setPointSize(max(6, int(value))); item.setFont(font)
                elif key == "font_family" and isinstance(item, SceneTextItem):
                    font = item.font(); font.setFamily(str(value or "Segoe UI")); item.setFont(font)
                elif key == "text_color" and isinstance(item, SceneTextItem):
                    item.setDefaultTextColor(parse_color(value, "#F4F7FF"))
                elif key in {"font_bold", "font_italic", "font_underline", "font_strikeout"} and isinstance(item, SceneTextItem):
                    font = item.font()
                    if key == "font_bold": font.setBold(bool(value))
                    elif key == "font_italic": font.setItalic(bool(value))
                    elif key == "font_underline": font.setUnderline(bool(value))
                    else: font.setStrikeOut(bool(value))
                    item.setFont(font)
                elif key in {"collision_enabled", "collision_shape", "physics_mode"}:
                    automation = data.setdefault("automation", {})
                    if key == "collision_enabled":
                        automation["collision_enabled"] = bool(value)
                        if bool(value) and automation.get("collision_shape", "none") == "none":
                            automation["collision_shape"] = "bounds"
                    elif key == "collision_shape":
                        automation["collision_shape"] = str(value)
                        automation["collision_enabled"] = str(value) != "none"
                    else:
                        automation["physics"] = str(value)
                if key in {"position_x", "position_y", "rotation", "size_width", "size_height"}:
                    if str(data.get("component_category", "")).lower() == "background":
                        item.setPos(self._camera_frame.rect().center() if self._camera_frame is not None else QPointF())
                    else:
                        item_rect = item.sceneBoundingRect()
                        item.setPos(self._position_inside_camera(item.pos(), item_rect.width(), item_rect.height()))
                self._sync_item_metadata(item)
        finally:
            self._loading = False
        self._emit_selection()
        self._queue_save()

    def _update_group_property(self, group_id: str, key: str, value) -> None:
        group = self._group_by_id(group_id)
        if group is None:
            self._selected_group_id = None
            return
        if key == "name":
            group["name"] = str(value).strip() or str(group.get("name", "Group"))
        elif key == "opacity":
            group["opacity"] = max(0.0, min(1.0, float(value)))
        elif key == "visible":
            group["visible"] = bool(value)
        elif key == "locked":
            group["locked"] = bool(value)
        elif key == "z_index":
            delta = int(value) - int(group.get("z_index", 0))
            for item in self._group_members(group_id):
                item.setZValue(item.zValue() + delta)
                getattr(item, "metadata", {})["z_index"] = int(round(item.zValue()))
            group["z_index"] = int(value)
        elif key in {"background_bitmap", "background_bitmap_mode"}:
            background_owner = next(
                (item for item in self._group_members(group_id) if isinstance(item, SceneVectorItem)),
                None,
            )
            if background_owner is not None:
                data = getattr(background_owner, "metadata", {})
                if key == "background_bitmap":
                    raw_value = str(value)
                    resolved = self._resolve_asset_path(raw_value) if raw_value else None
                    source = self._ensure_project_asset(resolved or Path(raw_value)) if raw_value else None
                    data["background_bitmap"] = self._relative_asset_path(source) if source is not None else ""
                    background_owner.refresh_background_bitmap()
                else:
                    mode = str(value or "Fill").title()
                    data["background_bitmap_mode"] = mode if mode in {"Fill", "Fit", "Stretch", "Tile"} else "Fill"
                    background_owner.update()
                self._sync_item_metadata(background_owner)
        for item in self._group_members(group_id):
            self._apply_effective_item_state(item)
        self._refresh_item_flags()
        self.selection_changed.emit(self._group_payload(group_id))
        self._queue_save()

    def _update_camera_property(self, key: str, value) -> None:
        camera = self._camera_node()
        if key in {"position_x", "position_y"}:
            point = list(camera.get("position", [0, 0])); point += [0] * (2 - len(point))
            point[0 if key.endswith("x") else 1] = float(value); camera["position"] = point
        elif key in {"scale_x", "scale_y", "zoom_x", "zoom_y"}:
            zoom = list(camera.get("zoom", [1, 1])); zoom += [1] * (2 - len(zoom))
            zoom[0 if key.endswith("x") else 1] = float(value); camera["zoom"] = zoom
        elif key == "rotation":
            camera["rotation"] = float(value)
        elif key == "projection":
            camera["projection"] = str(value)
        elif key == "preview_background":
            camera["preview_background"] = str(value)
        elif key in {"viewport_width", "viewport_height"}:
            viewport = self._scene_payload.setdefault("viewport", {"type": "FitViewport"})
            number = int(value)
            if key == "viewport_width":
                width, height = MRE_LANDSCAPE if number >= 280 else MRE_PORTRAIT
            else:
                width, height = MRE_PORTRAIT if number >= 280 else MRE_LANDSCAPE
            viewport["width"], viewport["height"] = width, height
            self._camera_width, self._camera_height = width, height
        self._update_camera_visuals()
        self.selection_changed.emit(self.camera_payload())
        self._queue_save()

    def group_selected(self) -> bool:
        selected = self._selected_items()
        if len(selected) < 2:
            self.status_message.emit("[Scene] Chọn ít nhất hai thành phần để gộp nhóm.")
            return False
        group_id = f"group_{uuid.uuid4().hex[:10]}"
        name = self._unique_group_name()
        z_values = [int(round(item.zValue())) for item in selected]
        group = {
            "id": group_id, "name": name, "type": "Group2D",
            "opacity": 1.0, "visible": True, "locked": False,
            "z_index": min(z_values) if z_values else 0,
        }
        self._add_group(group)
        for item in selected:
            getattr(item, "metadata", {})["group_id"] = group_id
            self._apply_effective_item_state(item)
        self._selected_group_id = group_id
        self.selection_changed.emit(self._group_payload(group_id))
        self._queue_save()
        self.status_message.emit(f"[Scene] Đã gộp {len(selected)} thành phần thành {name}.")
        return True

    def ungroup_selected(self) -> bool:
        selected = self._selected_items()
        group_ids = {
            str(getattr(item, "metadata", {}).get("group_id", ""))
            for item in selected
            if str(getattr(item, "metadata", {}).get("group_id", ""))
        }
        if self._selected_group_id:
            group_ids.add(self._selected_group_id)
        if not group_ids:
            self.status_message.emit("[Scene] Thành phần đang chọn chưa thuộc nhóm.")
            return False
        for item in self._node_items.values():
            data = getattr(item, "metadata", {})
            if str(data.get("group_id", "")) in group_ids:
                data["group_id"] = ""
                self._apply_effective_item_state(item)
        self._scene_payload["groups"] = [
            group for group in self._groups() if str(group.get("id", "")) not in group_ids
        ]
        self._selected_group_id = None
        self._refresh_item_flags()
        self._emit_selection()
        self._queue_save()
        self.status_message.emit(f"[Scene] Đã tách {len(group_ids)} nhóm.")
        return True

    def rename_group(self, group_id: str | None = None) -> bool:
        target_id = str(group_id or self._selected_group_id or "")
        group = self._group_by_id(target_id)
        if group is None:
            return False
        current = str(group.get("name", "Group"))
        value, accepted = TextInputDialog.get_text(self, "Đổi tên nhóm", "Tên nhóm:", text=current)
        value = value.strip()
        if not accepted or not value:
            return False
        group["name"] = value
        self.selection_changed.emit(self._group_payload(target_id))
        self._queue_save()
        self.status_message.emit(f"[Scene] Đã đổi tên nhóm '{current}' thành '{value}'.")
        return True

    def toggle_lock_selected(self) -> bool:
        if self._selected_group_id:
            group = self._group_by_id(self._selected_group_id)
            if group is None:
                return False
            group["locked"] = not bool(group.get("locked", False))
            for item in self._group_members(self._selected_group_id):
                self._refresh_item_flags(item)
            self.selection_changed.emit(self._group_payload(self._selected_group_id))
            self._queue_save()
            return True
        selected = self._selected_items()
        if not selected:
            return False
        new_value = not all(bool(getattr(item, "metadata", {}).get("locked", False)) for item in selected)
        for item in selected:
            getattr(item, "metadata", {})["locked"] = new_value
            self._refresh_item_flags(item)
        self._emit_selection(); self._queue_save()
        return True

    def flip_selected(self, horizontal: bool) -> bool:
        selected = self._selected_items()
        if not selected:
            return False
        self._loading = True
        try:
            for item in selected:
                sx = item.transform().m11()
                sy = item.transform().m22()
                item.setTransform(QTransform.fromScale(-sx if horizontal else sx, sy if horizontal else -sy))
                self._sync_item_metadata(item)
        finally:
            self._loading = False
        self._emit_selection(); self._queue_save()
        return True

    def align_selected(self, mode: str) -> bool:
        selected = [item for item in self._selected_items() if not self._item_is_locked(item)]
        align_to_camera = mode.startswith("camera_")
        base_mode = mode.removeprefix("camera_")
        minimum = 1 if align_to_camera else (3 if base_mode.startswith("distribute") else 2)
        if len(selected) < minimum:
            self.status_message.emit(f"[Scene] Chọn ít nhất {minimum} thành phần để căn chỉnh.")
            return False
        rects = {item: item.sceneBoundingRect() for item in selected}
        selection_bounds = next(iter(rects.values()))
        for rect in list(rects.values())[1:]:
            selection_bounds = selection_bounds.united(rect)
        camera_rect = self._camera_frame.rect() if self._camera_frame is not None else selection_bounds
        self._loading = True
        try:
            if base_mode in {"distribute_h", "distribute_v"} and len(selected) >= 3:
                horizontal = base_mode == "distribute_h"
                ordered = sorted(selected, key=lambda item: rects[item].left() if horizontal else rects[item].top())
                extent = selection_bounds.width() if horizontal else selection_bounds.height()
                occupied = sum(rects[item].width() if horizontal else rects[item].height() for item in ordered)
                gap = (extent - occupied) / max(1, len(ordered) - 1)
                cursor = selection_bounds.left() if horizontal else selection_bounds.top()
                for item in ordered:
                    rect = rects[item]
                    delta = cursor - (rect.left() if horizontal else rect.top())
                    item.moveBy(delta if horizontal else 0.0, delta if not horizontal else 0.0)
                    cursor += (rect.width() if horizontal else rect.height()) + gap
            elif align_to_camera:
                # Align every selected layer directly to Camera2D, matching
                # Photoshop's "Align to Canvas" behaviour. A compound button
                # (shape + text) therefore has both layers truly centred at 0,0.
                for item in selected:
                    rect = rects[item]
                    dx = dy = 0.0
                    if base_mode == "left": dx = camera_rect.left() - rect.left()
                    elif base_mode == "hcenter": dx = camera_rect.center().x() - rect.center().x()
                    elif base_mode == "right": dx = camera_rect.right() - rect.right()
                    elif base_mode == "top": dy = camera_rect.top() - rect.top()
                    elif base_mode == "vcenter": dy = camera_rect.center().y() - rect.center().y()
                    elif base_mode == "bottom": dy = camera_rect.bottom() - rect.bottom()
                    elif base_mode == "center":
                        dx = camera_rect.center().x() - rect.center().x()
                        dy = camera_rect.center().y() - rect.center().y()
                    else:
                        return False
                    item.moveBy(dx, dy)
            else:
                # Photoshop-style "Align to selection": every selected node uses
                # the common selection bounds, independent of selection order.
                for item in selected:
                    rect = rects[item]
                    dx = dy = 0.0
                    if base_mode == "left": dx = selection_bounds.left() - rect.left()
                    elif base_mode == "hcenter": dx = selection_bounds.center().x() - rect.center().x()
                    elif base_mode == "right": dx = selection_bounds.right() - rect.right()
                    elif base_mode == "top": dy = selection_bounds.top() - rect.top()
                    elif base_mode == "vcenter": dy = selection_bounds.center().y() - rect.center().y()
                    elif base_mode == "bottom": dy = selection_bounds.bottom() - rect.bottom()
                    elif base_mode == "center":
                        dx = selection_bounds.center().x() - rect.center().x()
                        dy = selection_bounds.center().y() - rect.center().y()
                    else:
                        return False
                    item.moveBy(dx, dy)
            for item in selected:
                self._sync_item_metadata(item)
        finally:
            self._loading = False
        self._emit_selection(); self._queue_save()
        target_name = "Camera2D" if align_to_camera else "vùng chọn"
        self.status_message.emit(f"[Arrange] Đã căn {len(selected)} thành phần theo {target_name}.")
        return True

    def align_all_nodes_to_camera(self, mode: str = "center") -> bool:
        """Quick frame-layout action used by the empty Camera2D context menu."""
        candidates = [item for item in self._node_items.values() if not self._item_is_locked(item)]
        if not candidates:
            self.status_message.emit("[Arrange] Frame không có thành phần có thể căn chỉnh.")
            return False
        self.scene().clearSelection()
        self._selected_group_id = None
        for item in candidates:
            item.setSelected(True)
        return self._align_selected_block_to_camera(mode.removeprefix("camera_"))

    def _align_selected_block_to_camera(self, mode: str) -> bool:
        """Move a complete frame layout as one block without changing its spacing."""
        selected = [item for item in self._selected_items() if not self._item_is_locked(item)]
        if not selected or self._camera_frame is None:
            return False
        bounds = selected[0].sceneBoundingRect()
        for item in selected[1:]:
            bounds = bounds.united(item.sceneBoundingRect())
        camera = self._camera_frame.sceneBoundingRect()
        dx = dy = 0.0
        if mode == "left": dx = camera.left() - bounds.left()
        elif mode == "hcenter": dx = camera.center().x() - bounds.center().x()
        elif mode == "right": dx = camera.right() - bounds.right()
        elif mode == "top": dy = camera.top() - bounds.top()
        elif mode == "vcenter": dy = camera.center().y() - bounds.center().y()
        elif mode == "bottom": dy = camera.bottom() - bounds.bottom()
        elif mode == "center":
            dx = camera.center().x() - bounds.center().x()
            dy = camera.center().y() - bounds.center().y()
        else:
            return False
        self._loading = True
        try:
            for item in selected:
                item.moveBy(dx, dy)
                self._sync_item_metadata(item)
        finally:
            self._loading = False
        self._emit_selection(); self._queue_save()
        self.status_message.emit(f"[Arrange] Đã căn cả khối layout theo Camera2D ({mode}).")
        return True

    def move_selected_layer(self, mode: str) -> bool:
        selected = set(self._selected_items())
        if not selected:
            return False
        ordered = sorted(self._node_items.values(), key=lambda item: (item.zValue(), str(getattr(item, "metadata", {}).get("id", ""))))
        block = [item for item in ordered if item in selected]
        others = [item for item in ordered if item not in selected]
        if mode == "front":
            result = others + block
        elif mode == "back":
            result = block + others
        elif mode == "forward":
            result = list(ordered)
            for index in range(len(result) - 2, -1, -1):
                if result[index] in selected and result[index + 1] not in selected:
                    result[index], result[index + 1] = result[index + 1], result[index]
        elif mode == "backward":
            result = list(ordered)
            for index in range(1, len(result)):
                if result[index] in selected and result[index - 1] not in selected:
                    result[index], result[index - 1] = result[index - 1], result[index]
        else:
            return False
        self._loading = True
        try:
            for index, item in enumerate(result):
                item.setZValue(index)
                getattr(item, "metadata", {})["z_index"] = index
            for group in self._groups():
                members = self._group_members(str(group.get("id", "")))
                if members:
                    group["z_index"] = min(int(round(member.zValue())) for member in members)
        finally:
            self._loading = False
        self._emit_selection(); self._queue_save()
        action_name = {
            "front": "Đưa lên trên cùng", "forward": "Đưa lên một lớp",
            "backward": "Đưa xuống một lớp", "back": "Đưa xuống dưới cùng",
        }[mode]
        self.status_message.emit(
            f"[Layers] {action_name} · thứ tự hiển thị đã đồng bộ như Photoshop."
        )
        return True

    def apply_scene_structure(self, structure: list) -> bool:
        if not structure:
            return False
        groups = {str(group.get("id", "")): group for group in self._groups()}
        order: list[str] = []

        def walk(entries: list, group_id: str = "") -> None:
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                entry_id = str(entry.get("id", ""))
                kind = str(entry.get("kind", "node"))
                if kind == "group" and entry_id in groups:
                    for member in self._group_members(entry_id):
                        getattr(member, "metadata", {})["group_id"] = entry_id
                    walk(entry.get("children", []), entry_id)
                else:
                    item = self._node_items.get(entry_id)
                    if item is None:
                        continue
                    getattr(item, "metadata", {})["group_id"] = group_id
                    order.append(entry_id)
                    walk(entry.get("children", []), group_id)

        walk(structure, "")
        if not order:
            return False
        self._loading = True
        try:
            for index, node_id in enumerate(reversed(order)):
                item = self._node_items.get(node_id)
                if item is None:
                    continue
                item.setZValue(index)
                getattr(item, "metadata", {})["z_index"] = index
            for group in self._groups():
                members = self._group_members(str(group.get("id", "")))
                if members:
                    group["z_index"] = min(int(round(member.zValue())) for member in members)
        finally:
            self._loading = False
        self._refresh_item_flags()
        self._emit_selection()
        self._queue_save()
        return True

    def assign_basic_event(self, event_type: str, target_screen: str = "") -> bool:
        payload = self._selected_event_payload(event_type)
        if not payload:
            return False
        if target_screen:
            return self.set_selected_events({
                "trigger": event_type, "action": "change_screen", "target_screen": target_screen, "enabled": True
            })
        self.event_mapping_requested.emit(payload)
        return True

    def copy_selected(self) -> bool:
        selected = self._selected_items()
        if not selected:
            return False
        self._clipboard_nodes = []
        for item in selected:
            self._sync_item_metadata(item)
            self._clipboard_nodes.append(copy.deepcopy(getattr(item, "metadata", {})))
        self.status_message.emit(f"[Scene] Đã sao chép {len(self._clipboard_nodes)} thành phần.")
        return True

    def paste_nodes(self) -> bool:
        if not self._clipboard_nodes:
            return False
        created = []
        group_map: dict[str, str] = {}
        for source in self._clipboard_nodes:
            node = copy.deepcopy(source)
            node["id"] = uuid.uuid4().hex[:12]
            node["name"] = self._unique_node_name(str(node.get("name", "Node")))
            node["code_name"] = self._unique_code_name(str(node.get("code_name") or node["name"]))
            old_group = str(node.get("group_id", ""))
            if old_group:
                if old_group not in group_map:
                    new_group = f"group_{uuid.uuid4().hex[:10]}"
                    group_map[old_group] = new_group
                    old_data = self._group_by_id(old_group) or {}
                    self._add_group({
                        "id": new_group, "name": self._unique_group_name(), "type": "Group2D",
                        "opacity": float(old_data.get("opacity", 1.0)), "visible": True, "locked": False,
                        "z_index": self._next_z_index(),
                    })
                node["group_id"] = group_map[old_group]
            pos = list(node.get("position", [0, 0])); pos += [0] * (2 - len(pos))
            node["position"] = [float(pos[0]) + self.grid_size, float(pos[1]) + self.grid_size]
            node["z_index"] = self._next_z_index()
            item = self._create_item_from_node(node, persist=False)
            if item: created.append(item)
        self.scene().clearSelection()
        for item in created: item.setSelected(True)
        self._selected_group_id = next(iter(group_map.values()), None) if len(group_map) == 1 else None
        if created:
            self._emit_selection(); self._queue_save(); return True
        return False

    def delete_selected(self) -> bool:
        selected = self._selected_items()
        if not selected:
            return False
        deleted_group = self._selected_group_id
        for item in selected:
            node_id = str(getattr(item, "metadata", {}).get("id", ""))
            self._node_items.pop(node_id, None)
            self._sprite_items.pop(node_id, None)
            self.scene().removeItem(item)
        if deleted_group:
            self._scene_payload["groups"] = [
                group for group in self._groups() if str(group.get("id", "")) != deleted_group
            ]
        else:
            used_groups = {str(getattr(item, "metadata", {}).get("group_id", "")) for item in self._node_items.values()}
            self._scene_payload["groups"] = [
                group for group in self._groups() if str(group.get("id", "")) in used_groups
            ]
        self._selected_group_id = None
        self._queue_save()
        self._emit_selection()
        self.status_message.emit(f"[Scene] Đã xóa {len(selected)} thành phần.")
        return True

    def rename_selected(self) -> bool:
        """Rename the selected group or first selected scene node."""
        if self._selected_group_id:
            return self.rename_group(self._selected_group_id)
        selected = self._selected_items()
        if not selected:
            self.status_message.emit("[Scene] Hãy chọn một thành phần trước khi đặt tên.")
            return False
        item = selected[0]
        data = getattr(item, "metadata", {})
        current_name = str(data.get("name", "Node"))
        value, accepted = TextInputDialog.get_text(
            self,
            "Đặt tên thành phần",
            "Tên mới:",
            text=current_name,
        )
        value = value.strip()
        if not accepted or not value:
            return False
        data["name"] = value
        if not str(data.get("code_name", "")).strip():
            data["code_name"] = self._unique_code_name(value, item)
        item.setToolTip(value)
        self.selection_changed.emit(self._item_payload(item))
        self._queue_save()
        self.status_message.emit(f"[Scene] Đã đổi tên '{current_name}' thành '{value}'.")
        return True

    def _export_selection_snapshot(self, items: list[QGraphicsItem]) -> Path | None:
        if self.project_path is None or not items:
            return None
        bounds = QRectF()
        for item in items:
            bounds = item.sceneBoundingRect() if bounds.isNull() else bounds.united(item.sceneBoundingRect())
        if bounds.isNull() or bounds.width() < 1 or bounds.height() < 1:
            return None
        bounds = bounds.adjusted(-12, -12, 12, 12)
        image = QImage(max(1, int(math.ceil(bounds.width()))), max(1, int(math.ceil(bounds.height()))), QImage.Format.Format_ARGB32_Premultiplied)
        image.fill(Qt.GlobalColor.transparent)
        painter = QPainter(image)
        self.scene().render(painter, QRectF(0, 0, image.width(), image.height()), bounds)
        painter.end()
        temp_dir = self.project_path / '.vxpe' / 'temp_asset_editor'
        temp_dir.mkdir(parents=True, exist_ok=True)
        temp_file = temp_dir / f'selection_{uuid.uuid4().hex[:10]}.png'
        image.save(str(temp_file), 'PNG')
        return temp_file

    def open_selected_in_asset_editor(self) -> bool:
        """Open the selected component/group and remember where Apply must return."""
        selected = self._selected_items()
        if not selected:
            self.status_message.emit("[Scene] Hãy chọn một thành phần trước khi mở Editor Assets.")
            return False
        source_text = ""
        destination = "assets/map/texture"
        bounds = QRectF()
        for item in selected:
            bounds = item.sceneBoundingRect() if bounds.isNull() else bounds.united(item.sceneBoundingRect())
        group_id = str(self._selected_group_id or "")
        group = self._group_by_id(group_id) if group_id else None
        context = {
            "scene_file": str(self.scene_file or ""),
            "screen_id": self.screen_id,
            "node_ids": [str(getattr(item, "metadata", {}).get("id", "")) for item in selected],
            "group_id": group_id,
            "center": [bounds.center().x(), bounds.center().y()],
            "z_index": min((int(item.zValue()) for item in selected), default=0),
            "name": str(group.get("name", "EditedGroup") if group else getattr(selected[0], "metadata", {}).get("name", "EditedAsset")),
        }
        if group_id or len(selected) > 1:
            snapshot = self._export_selection_snapshot(selected)
            source_text = str(snapshot) if snapshot is not None else ""
            context["mode"] = "flatten_selection"
        else:
            item = selected[0]
            data = getattr(item, "metadata", {})
            source = self._resolve_asset_path(str(data.get("asset", "")))
            source_text = str(source) if source is not None else ""
            if isinstance(item, SceneAssetItem) and source is not None:
                context["mode"] = "update_sprite"
                try:
                    destination = source.parent.resolve().relative_to(self.project_path).as_posix() if self.project_path else destination
                except (OSError, ValueError):
                    pass
            else:
                snapshot = self._export_selection_snapshot([item])
                source_text = str(snapshot) if snapshot is not None else ""
                context["mode"] = "flatten_selection"
        self._pending_asset_edit_context = context
        self.asset_editor_requested.emit(source_text, destination)
        return True

    def duplicate_selected(self, clipping_mask: bool = False) -> bool:
        if self._selected_group_id:
            if not self.copy_selected():
                return False
            ok = self.paste_nodes()
            if ok and clipping_mask:
                pasted = self._selected_items()
                source_id = str(getattr(pasted[0], "metadata", {}).get("id", "")) if pasted else ""
                for item in pasted[1:]:
                    getattr(item, "metadata", {})["clipping_mask"] = {"enabled": True, "source_id": source_id, "mode": "alpha"}
                    if isinstance(item, SceneAssetItem):
                        self._apply_clipping_mask(item)
                self._queue_save()
            return ok
        selected = self._selected_items()
        if not selected:
            return False
        created: list[QGraphicsItem] = []
        for item in selected:
            self._sync_item_metadata(item)
            node = copy.deepcopy(getattr(item, "metadata", {}))
            node["id"] = uuid.uuid4().hex[:12]
            node["name"] = self._unique_node_name(str(node.get("name", "Node")))
            original_id = str(getattr(item, "metadata", {}).get("id", ""))
            if clipping_mask:
                node["clipping_mask"] = {"enabled": True, "source_id": original_id, "mode": "alpha"}
            pos = list(node.get("position", [0, 0])); pos += [0] * (2 - len(pos))
            node["position"] = [float(pos[0]), float(pos[1])] if clipping_mask else [float(pos[0]) + self.grid_size, float(pos[1]) + self.grid_size]
            node["z_index"] = int(getattr(item, "metadata", {}).get("z_index", int(item.zValue()))) + 1
            duplicate = self._create_item_from_node(node, persist=False)
            if isinstance(duplicate, SceneAssetItem) and clipping_mask:
                self._apply_clipping_mask(duplicate)
            if duplicate: created.append(duplicate)
        self.scene().clearSelection()
        for item in created: item.setSelected(True)
        if created:
            if clipping_mask:
                self.status_message.emit("[Scene] Đã nhân đôi thành phần với tùy chọn Clipping Mask.")
            self._queue_save(); self._emit_selection(); return True
        return False

    def frame_selection(self) -> None:
        selected = self._selected_items()
        if selected:
            rect = selected[0].sceneBoundingRect()
            for item in selected[1:]: rect = rect.united(item.sceneBoundingRect())
            self.fitInView(rect.adjusted(-80, -80, 80, 80), Qt.AspectRatioMode.KeepAspectRatio)
            self._zoom = max(0.12, min(abs(self.transform().m11()), 8))
        else:
            self.reset_view()

    def shutdown(self) -> None:
        """Stop deferred callbacks and release graphics items before Qt exits."""
        for timer_name in ("_save_timer", "_history_timer", "_guide_clear_timer"):
            timer = getattr(self, timer_name, None)
            if timer is not None:
                timer.stop()
        try:
            self._save_scene()
        except (OSError, ValueError, TypeError):
            pass
        self._loading = True
        try:
            scene = self.scene()
            if scene is not None:
                scene.clearSelection()
                scene.clear()
            self._node_items.clear()
            self._sprite_items.clear()
        finally:
            self._loading = False

    def reset_view(self) -> None:
        self.resetTransform()
        if self._camera_frame is not None:
            rect = self._camera_frame.rect().adjusted(-96, -96, 96, 96)
            self.fitInView(rect, Qt.AspectRatioMode.KeepAspectRatio)
            self._zoom = max(0.12, min(abs(self.transform().m11()), 8.0))
        else:
            self._zoom = 1.0
            self.centerOn(self._point_from(self._camera_node().get("position"), QPointF(0, 0)))
        self.status_message.emit("[Scene] Đã đặt lại frame theo Camera2D.")

    def zoom_by(self, factor: float) -> None:
        factor = float(factor)
        if factor <= 0:
            return
        target = self._zoom * factor
        if not 0.12 <= target <= 8.0:
            return
        self.scale(factor, factor)
        self._zoom = target
        self.status_message.emit(f"[Scene] Zoom: {self._zoom * 100:.0f}%")

    def undo(self) -> bool:
        if self._history_index <= 0:
            return False
        self._history_index -= 1
        self._restore_history(self._history[self._history_index])
        self.history_changed.emit(self._history_index > 0, self._history_index < len(self._history) - 1)
        return True

    def redo(self) -> bool:
        if self._history_index >= len(self._history) - 1:
            return False
        self._history_index += 1
        self._restore_history(self._history[self._history_index])
        self.history_changed.emit(self._history_index > 0, self._history_index < len(self._history) - 1)
        return True

    def _compose_payload(self) -> dict:
        children = self._scene_payload.get("children", [])
        static = [child for child in children if not isinstance(child, dict) or str(child.get("type", "")).lower() not in EDITABLE_NODE_TYPES]
        editable = []
        for item in sorted(self._node_items.values(), key=lambda value: (value.zValue(), str(getattr(value, "metadata", {}).get("id", "")))):
            self._sync_item_metadata(item)
            editable.append(copy.deepcopy(getattr(item, "metadata", {})))
        used_group_ids = {str(node.get("group_id", "")) for node in editable if str(node.get("group_id", ""))}
        payload = copy.deepcopy(self._scene_payload)
        payload["screen_id"] = str(payload.get("screen_id") or self.screen_id)
        payload["groups"] = [copy.deepcopy(group) for group in self._groups() if str(group.get("id", "")) in used_group_ids]
        payload["children"] = static + editable
        return payload

    def _record_history(self, force: bool = False) -> None:
        snapshot = json.dumps(self._compose_payload(), ensure_ascii=False, sort_keys=True)
        if not force and self._history_index >= 0 and self._history[self._history_index] == snapshot:
            return
        if self._history_index < len(self._history) - 1:
            self._history = self._history[: self._history_index + 1]
        self._history.append(snapshot)
        if len(self._history) > 80:
            self._history.pop(0)
        self._history_index = len(self._history) - 1
        self.history_changed.emit(self._history_index > 0, False)

    def _restore_history(self, snapshot: str) -> None:
        try:
            payload = json.loads(snapshot)
        except json.JSONDecodeError:
            return
        self._loading = True
        try:
            for item in list(self._node_items.values()): self.scene().removeItem(item)
            self._node_items.clear(); self._sprite_items.clear()
            self._scene_payload = payload
            self._camera_width, self._camera_height = self._read_camera_size()
            self._update_camera_visuals()
            self._load_editable_nodes()
        finally:
            self._loading = False
        self._save_scene()
        self._emit_selection()
        self.viewport().update()

    def reload_from_disk(self) -> bool:
        """Nạp lại scene từ đĩa khi tệp .dtfe được sửa ở nơi khác.

        Dùng cho đồng bộ hai chiều: code editor (hoặc công cụ ngoài) ghi
        scene → Frame Preview cập nhật ngay. Bỏ qua nếu nội dung đĩa trùng
        với những gì viewport đang giữ (tránh vòng lặp lưu ↔ nạp).
        """
        path = self.scene_file
        if path is None or not path.exists():
            return False
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            return False
        if not isinstance(payload, dict):
            return False
        unchanged = json.dumps(payload, ensure_ascii=False, sort_keys=True) == json.dumps(
            self._compose_payload(), ensure_ascii=False, sort_keys=True
        )
        if unchanged:
            return False
        self._loading = True
        try:
            for item in list(self._node_items.values()):
                self.scene().removeItem(item)
            self._node_items.clear()
            self._sprite_items.clear()
            self._scene_payload = payload
            self._camera_width, self._camera_height = self._read_camera_size()
            self._update_camera_visuals()
            self._load_editable_nodes()
        finally:
            self._loading = False
        self._record_history(force=True)
        self._emit_selection()
        self.viewport().update()
        return True

    def _queue_save(self) -> None:
        if self._loading:
            return
        self._save_timer.start()
        self._history_timer.start()

    def _save_scene(self) -> None:
        path = self.scene_file
        if path is None:
            return
        self._scene_payload = self._compose_payload()
        content = json.dumps(self._scene_payload, ensure_ascii=False, indent=2)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_suffix(path.suffix + ".tmp")
            temporary.write_text(content, encoding="utf-8")
            last_error: OSError | None = None
            for attempt in range(4):
                try:
                    temporary.replace(path)
                    last_error = None
                    break
                except OSError as error:
                    # Windows: antivirus/OneDrive/IDE cũ có thể khóa file tạm — thử lại rồi ghi trực tiếp.
                    last_error = error
                    time.sleep(0.05 * (attempt + 1))
            if last_error is not None:
                try:
                    path.write_text(content, encoding="utf-8")
                except OSError:
                    raise last_error from None
                try:
                    temporary.unlink()
                except OSError:
                    pass
        except OSError as error:
            self.status_message.emit(f"[Scene] Không thể lưu {path.name}: {error}")
            return
        self.scene_changed.emit()
        self.screen_saved.emit(str(path))

    def _create_node_from_tool(self, tool: str, start: QPointF, end: QPointF, points: list[QPointF] | None = None) -> QGraphicsItem | None:
        start = self._snap_point(start) if self.snap_enabled else start
        end = self._snap_point(end) if self.snap_enabled else end
        if tool in {"Rectangle", "Circle"}:
            rect = QRectF(start, end).normalized()
            if self._camera_frame is not None:
                rect = rect.intersected(self._camera_frame.rect())
            if rect.width() < 2 or rect.height() < 2:
                return None
            node_type = "Rectangle2D" if tool == "Rectangle" else "Circle2D"
            node = self._base_node(None, node_type, tool)
            node["position"] = [rect.center().x(), rect.center().y()]
            node["shape"] = {
                "width": rect.width(), "height": rect.height(),
                "fill": DEFAULT_FILL, "stroke": DEFAULT_STROKE, "stroke_width": 2,
            }
            return self._create_vector_item(node, persist=True)
        if tool == "Line":
            delta = end - start
            if QLineF(start, end).length() < 2: return None
            node = self._base_node(None, "Line2D", "Line")
            node["position"] = [start.x(), start.y()]
            node["shape"] = {"points": [[0, 0], [delta.x(), delta.y()]], "fill": "#00000000", "stroke": DEFAULT_STROKE, "stroke_width": 2}
            return self._create_vector_item(node, persist=True)
        if tool == "Brush" and points and len(points) > 1:
            origin = points[0]
            local = [[point.x() - origin.x(), point.y() - origin.y()] for point in points]
            node = self._base_node(None, "Brush2D", "Brush")
            node["position"] = [origin.x(), origin.y()]
            node["shape"] = {"points": local, "fill": "#00000000", "stroke": DEFAULT_STROKE, "stroke_width": 3}
            return self._create_vector_item(node, persist=True)
        return None

    def _preview_path(self, tool: str, start: QPointF, current: QPointF, points: list[QPointF]) -> QPainterPath:
        path = QPainterPath()
        if tool == "Rectangle": path.addRect(QRectF(start, current).normalized())
        elif tool == "Circle": path.addEllipse(QRectF(start, current).normalized())
        elif tool == "Line": path.moveTo(start); path.lineTo(current)
        elif tool == "Brush" and points:
            path.moveTo(points[0])
            for point in points[1:]: path.lineTo(point)
        return path

    def _resizable_items(self) -> list[QGraphicsItem]:
        selected = self._selected_items()
        return [
            item for item in selected
            if bool(getattr(item, "metadata", {}).get("resizable", True))
            and not self._item_is_locked(item)
        ]

    def _selection_scene_rect(self, items: list[QGraphicsItem] | None = None) -> QRectF:
        targets = items if items is not None else self._resizable_items()
        bounds = QRectF()
        for item in targets:
            rect = item.sceneBoundingRect()
            bounds = rect if bounds.isNull() else bounds.united(rect)
        return bounds

    def _selection_handle_points(self, items: list[QGraphicsItem] | None = None) -> dict[str, QPointF]:
        rect = self._selection_scene_rect(items)
        if rect.isNull():
            return {}
        center = rect.center()
        return {
            "top_left": rect.topLeft(),
            "top": QPointF(center.x(), rect.top()),
            "top_right": rect.topRight(),
            "right": QPointF(rect.right(), center.y()),
            "bottom_right": rect.bottomRight(),
            "bottom": QPointF(center.x(), rect.bottom()),
            "bottom_left": rect.bottomLeft(),
            "left": QPointF(rect.left(), center.y()),
        }

    def _rotation_handle_scene_point(self, items: list[QGraphicsItem] | None = None) -> QPointF | None:
        """Tay nắm xoay kiểu Canva: vòng tròn phía trên đỉnh khung chọn."""
        rect = self._selection_scene_rect(items)
        if rect.isNull():
            return None
        scale = abs(self.transform().m11()) or 1.0
        offset = 26.0 / max(0.05, scale)
        return QPointF(rect.center().x(), rect.top() - offset)

    def _item_resize_handle_at(self, view_pos: QPoint) -> str | None:
        if self.current_tool not in {"Select", "Scale"}:
            return None
        items = self._resizable_items()
        if not items:
            return None
        threshold = RESIZE_HANDLE_PX + 4
        rotate_point = self._rotation_handle_scene_point(items)
        if rotate_point is not None:
            point = self.mapFromScene(rotate_point)
            if abs(point.x() - view_pos.x()) <= threshold and abs(point.y() - view_pos.y()) <= threshold:
                return "rotate"
        for handle, scene_point in self._selection_handle_points(items).items():
            point = self.mapFromScene(scene_point)
            if abs(point.x() - view_pos.x()) <= threshold and abs(point.y() - view_pos.y()) <= threshold:
                return handle
        return None

    def _begin_item_resize(self, handle: str, scene_pos: QPointF) -> bool:
        items = self._resizable_items()
        if not items:
            return False
        bounds = self._selection_scene_rect(items)
        if bounds.isNull() or bounds.width() < 0.001 or bounds.height() < 0.001:
            return False
        center = bounds.center()
        if handle == "rotate":
            vector = scene_pos - center
            self._item_resize_drag = {
                "handle": "rotate",
                "center": QPointF(center),
                "start_angle": math.degrees(math.atan2(vector.y(), vector.x())),
                "items": [{"item": it, "rotation": float(it.rotation())} for it in items],
            }
            self.status_message.emit("[Scene] Kéo để xoay thành phần; giữ Shift để bắt góc 15°.")
            return True
        item_states = []
        for item in items:
            item_states.append({
                "item": item,
                "position": QPointF(item.pos()),
                "scale_x": float(item.transform().m11()),
                "scale_y": float(item.transform().m22()),
            })
        self._item_resize_drag = {
            "handle": handle,
            "bounds": QRectF(bounds),
            "center": QPointF(center),
            "start": QPointF(scene_pos),
            "items": item_states,
            "lock_aspect": any(bool(getattr(item, "metadata", {}).get("lock_aspect", False)) for item in items),
        }
        self.status_message.emit("[Scene] Kéo dãn thành phần; giữ Shift để khóa tỉ lệ.")
        return True

    def _apply_item_resize(self, scene_pos: QPointF, modifiers: Qt.KeyboardModifiers) -> None:
        drag = self._item_resize_drag
        if drag is None:
            return
        if str(drag["handle"]) == "rotate":
            vector = scene_pos - drag["center"]
            delta = math.degrees(math.atan2(vector.y(), vector.x())) - float(drag["start_angle"])
            if modifiers & Qt.KeyboardModifier.ShiftModifier:
                delta = round(delta / 15.0) * 15.0
            for state in drag["items"]:
                angle = state["rotation"] + delta
                state["item"].setRotation(angle)
                getattr(state["item"], "metadata", {})["rotation"] = round(angle, 3)
            self._emit_selection()
            return
        bounds: QRectF = drag["bounds"]
        center: QPointF = drag["center"]
        handle = str(drag["handle"])
        half_w = max(0.5, bounds.width() / 2.0)
        half_h = max(0.5, bounds.height() / 2.0)
        factor_x = 1.0
        factor_y = 1.0
        if handle in {"left", "right", "top_left", "top_right", "bottom_left", "bottom_right"}:
            factor_x = max(MIN_COMPONENT_SCALE, abs(scene_pos.x() - center.x()) / half_w)
        if handle in {"top", "bottom", "top_left", "top_right", "bottom_left", "bottom_right"}:
            factor_y = max(MIN_COMPONENT_SCALE, abs(scene_pos.y() - center.y()) / half_h)
        lock_aspect = bool(modifiers & Qt.KeyboardModifier.ShiftModifier) or bool(drag.get("lock_aspect", False))
        if lock_aspect:
            if handle in {"left", "right"}:
                factor_y = factor_x
            elif handle in {"top", "bottom"}:
                factor_x = factor_y
            else:
                uniform = max(factor_x, factor_y)
                factor_x = factor_y = uniform
        if self._camera_frame is not None:
            camera = self._camera_frame.rect()
            factor_x = min(factor_x, camera.width() / max(bounds.width(), 0.001))
            factor_y = min(factor_y, camera.height() / max(bounds.height(), 0.001))
            if lock_aspect:
                uniform = min(factor_x, factor_y)
                factor_x = factor_y = uniform
        self._loading = True
        try:
            for state in drag["items"]:
                item: QGraphicsItem = state["item"]
                start_pos: QPointF = state["position"]
                offset = start_pos - center
                item.setPos(QPointF(center.x() + offset.x() * factor_x, center.y() + offset.y() * factor_y))
                sx = state["scale_x"] * factor_x
                sy = state["scale_y"] * factor_y
                item.setTransform(QTransform.fromScale(sx, sy))
                item_rect = item.sceneBoundingRect()
                item.setPos(self._position_inside_camera(item.pos(), item_rect.width(), item_rect.height()))
                self._sync_item_metadata(item)
        finally:
            self._loading = False
        self._emit_selection()
        self.viewport().update()

    def reset_selected_size(self) -> bool:
        items = self._selected_items()
        if not items:
            return False
        self._loading = True
        try:
            for item in items:
                item.setTransform(QTransform.fromScale(1.0, 1.0))
                self._sync_item_metadata(item)
        finally:
            self._loading = False
        self._emit_selection()
        self._queue_save()
        self.status_message.emit(f"[Scene] Đã đặt lại kích thước {len(items)} thành phần về 100%.")
        return True

    def toggle_selected_aspect_lock(self) -> bool:
        items = self._selected_items()
        if not items:
            return False
        new_value = not all(bool(getattr(item, "metadata", {}).get("lock_aspect", False)) for item in items)
        for item in items:
            getattr(item, "metadata", {})["lock_aspect"] = new_value
        self._queue_save()
        self.status_message.emit(f"[Scene] Khóa tỉ lệ kéo dãn: {'Bật' if new_value else 'Tắt'}.")
        return True

    def _begin_transform(self, item: QGraphicsItem, scene_pos: QPointF) -> None:
        data = getattr(item, "metadata", {})
        if self._item_is_locked(item) or (self.current_tool == "Scale" and not bool(data.get("resizable", True))):
            self.status_message.emit("[Scene] Thành phần đang khóa hoặc có kích thước cố định.")
            return
        self._select_item(item)
        center = item.sceneBoundingRect().center()
        vector = scene_pos - center
        self._transform_drag = {
            "item": item,
            "center": center,
            "rotation": item.rotation(),
            "scale": (item.transform().m11(), item.transform().m22()),
            "angle": math.degrees(math.atan2(vector.y(), vector.x())),
            "distance": max(1.0, math.hypot(vector.x(), vector.y())),
        }

    def dragEnterEvent(self, event):  # noqa: N802
        if (
            self._mime_perspective(event.mimeData())
            or self._mime_component(event.mimeData())
            or self._mime_image_paths(event.mimeData())
        ):
            event.setDropAction(Qt.DropAction.CopyAction)
            event.accept()
            return
        super().dragEnterEvent(event)

    def dragMoveEvent(self, event):  # noqa: N802
        if (
            self._mime_perspective(event.mimeData())
            or self._mime_component(event.mimeData())
            or self._mime_image_paths(event.mimeData())
        ):
            event.setDropAction(Qt.DropAction.CopyAction)
            event.accept()
            return
        super().dragMoveEvent(event)

    def dropEvent(self, event):  # noqa: N802
        perspective = self._mime_perspective(event.mimeData())
        if perspective:
            position = self.mapToScene(event.position().toPoint())
            if self._camera_frame is not None and not self._camera_frame.rect().contains(position):
                self.status_message.emit("[Frame Perspective] Hãy thả preset bên trong Camera2D.")
                return
            if self.apply_frame_perspective(perspective):
                event.setDropAction(Qt.DropAction.CopyAction)
                event.accept()
            return
        component = self._mime_component(event.mimeData())
        if component:
            position = self.mapToScene(event.position().toPoint())
            if self._camera_frame is not None and not self._camera_frame.rect().contains(position):
                self.status_message.emit("[UI Design] Hãy thả component bên trong Camera2D.")
                return
            if self.insert_component(component, position):
                event.setDropAction(Qt.DropAction.CopyAction)
                event.accept()
            return
        paths = self._mime_image_paths(event.mimeData())
        if not paths:
            super().dropEvent(event); return
        position_view = event.position().toPoint()
        position = self.mapToScene(position_view)
        if self._camera_frame is not None and not self._camera_frame.rect().contains(position):
            self.status_message.emit("[TitleSet] Hãy thả asset bên trong Camera2D.")
            return
        if event.mimeData().hasFormat("application/x-vxp-background"):
            if self.insert_background_path(paths[0]):
                event.setDropAction(Qt.DropAction.CopyAction)
                event.accept()
            return
        offset = QPointF()
        created = 0
        for path in paths:
            source = self._ensure_project_asset(path)
            if source is not None:
                pixmap = QPixmap(str(source))
                drop_position = self._position_inside_camera(
                    position + offset,
                    pixmap.width() if not pixmap.isNull() else 1,
                    pixmap.height() if not pixmap.isNull() else 1,
                )
                if self._create_sprite_item(source, position=drop_position, persist=True):
                    created += 1
                    offset += QPointF(24, 24)
        if created:
            event.setDropAction(Qt.DropAction.CopyAction)
            event.accept()

    def insert_asset_path(self, path: str | Path, position: QPointF | None = None) -> bool:
        source = self._ensure_project_asset(Path(path))
        if source is None:
            return False
        if position is None:
            position = self._camera_frame.rect().center() if self._camera_frame is not None else QPointF()
        pixmap = QPixmap(str(source))
        position = self._position_inside_camera(
            QPointF(position),
            pixmap.width() if not pixmap.isNull() else 1,
            pixmap.height() if not pixmap.isNull() else 1,
        )
        created = self._create_sprite_item(source, position=position, persist=True)
        return created is not None

    def insert_background_path(self, path: str | Path) -> bool:
        """Import and place a pixel background exactly behind Camera2D content."""
        source = self._ensure_project_asset(Path(path))
        if source is None:
            return False
        pixmap = QPixmap(str(source))
        if pixmap.isNull():
            return False
        camera = self._camera_frame.rect() if self._camera_frame is not None else QRectF(-120, -160, 240, 320)
        z_index = min((int(item.zValue()) for item in self._node_items.values()), default=0) - 1
        node = {
            "type": "Sprite2D",
            "name": source.stem,
            "position": [camera.center().x(), camera.center().y()],
            "scale": [camera.width() / pixmap.width(), camera.height() / pixmap.height()],
            "z_index": z_index,
            "component_category": "background",
            "ui_role": "Background",
            "resizable": False,
            "lock_aspect": True,
            "locked": True,
        }
        created = self._create_sprite_item(source, node=node, position=camera.center(), persist=True)
        if created is None:
            return False
        self.status_message.emit(
            f"[UI Design] Đã đặt nền pixel {source.name} đúng {int(camera.width())}×{int(camera.height())}."
        )
        return True

    @staticmethod
    def _mime_perspective(mime) -> dict | None:
        if not mime.hasFormat("application/x-vxp-frame-perspective"):
            return None
        try:
            payload = json.loads(
                bytes(mime.data("application/x-vxp-frame-perspective")).decode("utf-8")
            )
        except (UnicodeDecodeError, ValueError, TypeError, json.JSONDecodeError):
            return None
        return payload if isinstance(payload, dict) else None

    @staticmethod
    def _mime_component(mime) -> dict | None:
        if not mime.hasFormat("application/x-vxp-component"):
            return None
        try:
            payload = json.loads(bytes(mime.data("application/x-vxp-component")).decode("utf-8"))
        except (UnicodeDecodeError, ValueError, TypeError, json.JSONDecodeError):
            return None
        return payload if isinstance(payload, dict) else None

    def apply_frame_perspective(self, template: dict) -> bool:
        """Apply an editor-only perspective guide that always follows Camera2D."""
        if not isinstance(template, dict):
            return False
        kind = str(template.get("kind") or "").strip().lower()
        if kind not in {"side_scroller", "top_down", "three_quarter", "isometric"}:
            return False
        perspective = {
            "kind": kind,
            "label": str(template.get("label") or kind),
            "camera_angle": int(template.get("camera_angle", 0)),
            "projection": str(template.get("projection") or kind),
            "movement_axes": str(template.get("movement_axes") or "four_way"),
            "fit_mode": "camera_frame",
            "editor_guide": True,
        }
        self._camera_node()["frame_perspective"] = perspective
        self.scene().clearSelection()
        self._selected_group_id = None
        self.selection_changed.emit(self.camera_payload())
        self._queue_save()
        self.viewport().update()
        self.status_message.emit(
            f"[Frame Perspective] {perspective['label']} đã khít Camera2D "
            f"{self._camera_width}×{self._camera_height}; guide chỉ hiển thị trong editor."
        )
        return True

    @staticmethod
    def _anchor_payload(label: str) -> dict:
        points = {
            "Top Left": (0.0, 0.0), "Top": (0.5, 0.0), "Top Right": (1.0, 0.0),
            "Left": (0.0, 0.5), "Center": (0.5, 0.5), "Right": (1.0, 0.5),
            "Bottom Left": (0.0, 1.0), "Bottom": (0.5, 1.0), "Bottom Right": (1.0, 1.0),
        }
        mode = label if label in points else "Center"
        x, y = points[mode]
        return {"mode": mode, "x": x, "y": y}

    def _set_item_dimension(self, item: QGraphicsItem, key: str, value: float) -> None:
        """Resize one selected component to an exact unrotated logical pixel size."""
        value = max(1.0, min(100000.0, float(value)))
        bounds = item.boundingRect()
        if isinstance(item, SceneAssetItem):
            base_w = max(1.0, float(item.pixmap().width()))
            base_h = max(1.0, float(item.pixmap().height()))
        else:
            base_w = max(0.001, bounds.width())
            base_h = max(0.001, bounds.height())
        data = getattr(item, "metadata", {})
        if str(data.get("component_category", "")).lower() == "background":
            center = self._camera_frame.rect().center() if self._camera_frame is not None else QPointF()
            item.setPos(center)
            item.setTransform(QTransform.fromScale(self._camera_width / base_w, self._camera_height / base_h))
            return
        value = min(value, float(self._camera_width if key == "size_width" else self._camera_height))
        sx = float(item.transform().m11())
        sy = float(item.transform().m22())
        sign_x = -1.0 if sx < 0 else 1.0
        sign_y = -1.0 if sy < 0 else 1.0
        current_w = base_w * abs(sx)
        current_h = base_h * abs(sy)
        lock = bool(getattr(item, "metadata", {}).get("lock_aspect", False))
        if key == "size_width":
            next_sx = sign_x * value / base_w
            next_sy = sign_y * (value / max(current_w, 0.001)) * current_h / base_h if lock else sy
        else:
            next_sy = sign_y * value / base_h
            next_sx = sign_x * (value / max(current_h, 0.001)) * current_w / base_w if lock else sx
        item.setTransform(QTransform.fromScale(next_sx, next_sy))

    def _rebuild_vector_path(self, item: SceneVectorItem) -> None:
        """Rebuild rectangle geometry after Corner Radius changes."""
        data = getattr(item, "metadata", {})
        shape = data.get("shape") if isinstance(data.get("shape"), dict) else {}
        kind = str(data.get("type", "Rectangle2D")).lower()
        if kind not in {"rectangle2d", "tile2d"}:
            return
        width = max(1.0, float(shape.get("width", item.boundingRect().width())))
        height = max(1.0, float(shape.get("height", item.boundingRect().height())))
        radius = max(0.0, min(float(shape.get("corner_radius", 0)), min(width, height) / 2))
        path = QPainterPath(); rect = QRectF(-width / 2, -height / 2, width, height)
        path.addRoundedRect(rect, radius, radius) if radius > 0 else path.addRect(rect)
        item.setPath(path)
        item.setTransformOriginPoint(item.boundingRect().center())

    def _position_inside_camera(self, position: QPointF, width: float, height: float) -> QPointF:
        if self._camera_frame is None:
            return QPointF(position)
        rect = self._camera_frame.rect()
        half_w = min(max(0.0, width / 2), rect.width() / 2)
        half_h = min(max(0.0, height / 2), rect.height() / 2)
        return QPointF(
            max(rect.left() + half_w, min(position.x(), rect.right() - half_w)),
            max(rect.top() + half_h, min(position.y(), rect.bottom() - half_h)),
        )

    def insert_component(self, template: dict, position: QPointF | None = None) -> bool:
        """Create a reusable UI component and persist it as ordinary DTFE nodes."""
        if not isinstance(template, dict):
            return False
        kind = str(template.get("kind") or "component")
        label = str(template.get("label") or kind.title())
        node_type = str(template.get("type") or "Rectangle2D")
        size = template.get("size", [80, 28])
        try:
            width, height = max(1, float(size[0])), max(1, float(size[1]))
        except (TypeError, ValueError, IndexError):
            width, height = 80.0, 28.0
        camera = self._camera_frame.rect() if self._camera_frame is not None else QRectF(-120, -160, 240, 320)
        if kind == "canvas":
            width, height = camera.width(), camera.height()
            position = camera.center()
        elif position is None:
            position = camera.center()
        position = self._position_inside_camera(QPointF(position), width, height)
        common = {
            "component_category": "ui",
            "ui_role": str(template.get("ui_role") or kind.title()),
            "input_binding": str(template.get("input_binding") or ""),
            "component": {"kind": kind, "template": label},
            "position": [position.x(), position.y()],
        }
        created: list[QGraphicsItem] = []
        text = str(template.get("text") or "")

        if node_type.lower() == "text2d":
            node = self._base_node(None, "Text2D", label)
            node.update(common)
            node["text"] = {
                "content": text or label,
                "font": "Segoe UI",
                "font_size": max(8, int(height * 0.65)),
                "color": "#F8FAFC",
            }
            created.append(self._create_text_item(node, persist=False))
        else:
            group_id = f"ui_{uuid.uuid4().hex[:10]}" if text else ""
            node = self._base_node(None, "Rectangle2D", label)
            node.update(common)
            node["group_id"] = group_id
            node["shape"] = {
                "width": width,
                "height": height,
                "fill": str(template.get("fill") or "#1E293B"),
                "stroke": str(template.get("stroke") or "#7DD3FC"),
                "stroke_width": 1,
                "corner_radius": max(0.0, float(template.get("corner_radius", 0) or 0)),
            }
            node["background_bitmap"] = str(template.get("background_bitmap") or "")
            node["background_bitmap_mode"] = str(template.get("background_bitmap_mode") or "Fill")
            if kind == "canvas":
                node["z_index"] = min((int(item.zValue()) for item in self._node_items.values()), default=0) - 1
                node["locked"] = True
                node["resizable"] = False
            shape = self._create_vector_item(node, persist=False)
            if shape is not None:
                created.append(shape)
            if text and shape is not None:
                text_node = self._base_node(None, "Text2D", f"{label}_Text")
                text_node.update(common)
                text_node["group_id"] = group_id
                text_node["resizable"] = False
                text_node["z_index"] = int(node.get("z_index", 0)) + 1
                text_node["text"] = {
                    "content": text,
                    "font": "Segoe UI",
                    "font_size": max(7, min(14, int(height * 0.48))),
                    "color": "#F8FAFC",
                }
                text_item = self._create_text_item(text_node, persist=False)
                if text_item is not None:
                    # Rectangle2D uses a centered origin while QGraphicsTextItem
                    # uses its top-left corner. Align both visual centers so a
                    # dragged Button/Input/Checkbox looks correct immediately.
                    text_bounds = text_item.boundingRect()
                    was_loading = self._loading
                    self._loading = True  # placement is exact, not grid-snapped
                    try:
                        text_item.setPos(
                            position.x() - text_bounds.center().x(),
                            position.y() - text_bounds.center().y(),
                        )
                    finally:
                        self._loading = was_loading
                    self._sync_item_metadata(text_item)
                    created.append(text_item)
                self._add_group({
                    "id": group_id,
                    "name": self._unique_group_name(),
                    "type": "Group2D",
                    "component_category": "ui",
                    "ui_role": common["ui_role"],
                    "opacity": 1.0,
                    "visible": True,
                    "locked": False,
                    "z_index": int(node.get("z_index", 0)),
                })

        created = [item for item in created if item is not None]
        if not created:
            return False
        self.scene().clearSelection()
        group_id = str(getattr(created[0], "metadata", {}).get("group_id", ""))
        self._selected_group_id = group_id or None
        for item in created:
            item.setSelected(True)
        self._queue_save()
        if group_id:
            self.selection_changed.emit(self._group_payload(group_id))
        else:
            self.selection_changed.emit(self._item_payload(created[0]))
        self.status_message.emit(f"[UI Design] Đã thêm {label}; scene .dtfe sẽ tự lưu.")
        return True

    def set_terrain_brush(self, path: str | Path, tile_size: int = 32, rule_mode: bool = True, erase: bool = False) -> bool:
        """Activate a grid material brush for direct painting in Frame Preview."""
        source = self._ensure_project_asset(Path(path)) if str(path) else None
        if not erase and (source is None or not source.is_file()):
            self.status_message.emit("[Terrain] Hãy chọn một texture/tile hợp lệ trong TitleSet.")
            return False
        self._terrain_brush_path = source
        self._terrain_brush_size = max(4, min(256, int(tile_size)))
        self._terrain_rule_mode = bool(rule_mode)
        self._terrain_erase_mode = bool(erase)
        self.grid_size = self._terrain_brush_size
        self._terrain_last_cell = None
        self.set_tool("Terrain")
        mode = "Eraser" if erase else f"Paint · {source.stem}"
        self.status_message.emit(f"[Terrain] {mode} · grid {self._terrain_brush_size}px · Rule Tile {'ON' if rule_mode else 'OFF'}.")
        self.viewport().update()
        return True

    def clear_terrain_brush(self) -> None:
        self._terrain_brush_path = None
        self._terrain_erase_mode = False
        self._terrain_last_cell = None
        if self.current_tool == "Terrain":
            self.set_tool("Select")

    def _terrain_cell(self, position: QPointF) -> tuple[int, int]:
        size = float(self._terrain_brush_size)
        camera = self._camera_frame.rect() if self._camera_frame is not None else QRectF()
        return math.floor((position.x() - camera.left()) / size), math.floor((position.y() - camera.top()) / size)

    def _terrain_item_at(self, cell: tuple[int, int]) -> SceneAssetItem | None:
        for item in self._sprite_items.values():
            terrain = item.metadata.get("terrain")
            if not isinstance(terrain, dict):
                continue
            raw_cell = terrain.get("cell")
            if isinstance(raw_cell, (list, tuple)) and len(raw_cell) >= 2:
                if (int(raw_cell[0]), int(raw_cell[1])) == cell and int(terrain.get("tile_size", 0)) == self._terrain_brush_size:
                    return item
        return None

    def _paint_terrain_cell(self, position: QPointF, erase: bool = False) -> bool:
        camera = self._camera_frame.rect() if self._camera_frame is not None else QRectF()
        if not camera.contains(position):
            return False
        cell = self._terrain_cell(position)
        if cell == self._terrain_last_cell:
            return False
        self._terrain_last_cell = cell
        existing = self._terrain_item_at(cell)
        if erase:
            if existing is None:
                return False
            terrain = existing.metadata.get("terrain", {})
            terrain_id = str(terrain.get("terrain_id", ""))
            node_id = str(existing.metadata.get("id", ""))
            self._node_items.pop(node_id, None)
            self._sprite_items.pop(node_id, None)
            self.scene().removeItem(existing)
            self._update_rule_tiles(cell, terrain_id)
            return True
        source = self._terrain_brush_path
        if source is None:
            return False
        terrain_id = source.stem.split("__rule_", 1)[0].split("_rule_", 1)[0]
        base_candidate = source.with_name(f"{terrain_id}{source.suffix}")
        base_source = base_candidate if base_candidate.is_file() else source
        if existing is not None:
            terrain = existing.metadata.get("terrain", {})
            if str(terrain.get("terrain_id", "")) == terrain_id:
                return False
            old_terrain_id = str(terrain.get("terrain_id", ""))
            node_id = str(existing.metadata.get("id", ""))
            self._node_items.pop(node_id, None)
            self._sprite_items.pop(node_id, None)
            self.scene().removeItem(existing)
            self._update_rule_tiles(cell, old_terrain_id)
        pixmap = QPixmap(str(source))
        if pixmap.isNull():
            return False
        size = self._terrain_brush_size
        center = QPointF(camera.left() + (cell[0] + 0.5) * size,
                         camera.top() + (cell[1] + 0.5) * size)
        tile_rect = QRectF(center.x() - size / 2, center.y() - size / 2, size, size)
        if not camera.contains(tile_rect):
            return False
        node = {
            "type": "Sprite2D",
            "position": [center.x(), center.y()],
            "scale": [size / max(1, pixmap.width()), size / max(1, pixmap.height())],
            "component_category": "terrain",
            "ui_role": "TilemapCell",
            "resizable": False,
            "lock_aspect": True,
            "terrain": {
                "cell": [cell[0], cell[1]],
                "tile_size": size,
                "terrain_id": terrain_id,
                "base_asset": self._relative_asset_path(base_source),
                "rule_enabled": self._terrain_rule_mode,
                "rule_mask": 0,
            },
        }
        if self._create_sprite_item(source, node=node, position=center, persist=False) is None:
            return False
        self._update_rule_tiles(cell, terrain_id)
        return True

    def _update_rule_tiles(self, changed_cell: tuple[int, int], terrain_id: str) -> None:
        if not terrain_id:
            return
        targets = {
            changed_cell,
            (changed_cell[0], changed_cell[1] - 1),
            (changed_cell[0] + 1, changed_cell[1]),
            (changed_cell[0], changed_cell[1] + 1),
            (changed_cell[0] - 1, changed_cell[1]),
        }
        for cell in targets:
            item = self._terrain_item_at(cell)
            if item is None:
                continue
            terrain = item.metadata.get("terrain", {})
            if str(terrain.get("terrain_id", "")) != terrain_id:
                continue
            mask = 0
            for dx, dy, bit in ((0, -1, 1), (1, 0, 2), (0, 1, 4), (-1, 0, 8)):
                neighbor = self._terrain_item_at((cell[0] + dx, cell[1] + dy))
                neighbor_terrain = neighbor.metadata.get("terrain", {}) if neighbor is not None else {}
                if str(neighbor_terrain.get("terrain_id", "")) == terrain_id:
                    mask |= bit
            terrain["rule_mask"] = mask
            if bool(terrain.get("rule_enabled", False)):
                self._apply_rule_variant(item, mask)

    def _apply_rule_variant(self, item: SceneAssetItem, mask: int) -> None:
        terrain = item.metadata.get("terrain", {})
        base = self._resolve_asset_path(str(terrain.get("base_asset", "")))
        if base is None:
            return
        candidates = (
            base.with_name(f"{base.stem}__rule_{mask}{base.suffix}"),
            base.with_name(f"{base.stem}_rule_{mask}{base.suffix}"),
        )
        source = next((candidate for candidate in candidates if candidate.is_file()), base)
        pixmap = QPixmap(str(source))
        if pixmap.isNull():
            return
        item.setPixmap(pixmap)
        item.setOffset(-pixmap.width() / 2, -pixmap.height() / 2)
        size = int(terrain.get("tile_size", self._terrain_brush_size))
        scale = [size / max(1, pixmap.width()), size / max(1, pixmap.height())]
        item.metadata["scale"] = scale
        item.metadata["asset"] = self._relative_asset_path(source)
        item.setTransform(QTransform.fromScale(scale[0], scale[1]))
        item.setToolTip(f"{terrain.get('terrain_id', 'Terrain')} · Rule mask {mask}")

    def replace_selected_asset(self, path: str | Path) -> bool:
        selected = self._selected_items()
        if len(selected) != 1 or not isinstance(selected[0], SceneAssetItem):
            return False
        source = Path(path)
        pixmap = QPixmap(str(source))
        if pixmap.isNull():
            return False
        item = selected[0]
        data = item.metadata
        old_ui_role = str(data.get("ui_role", ""))
        old_input_binding = str(data.get("input_binding", ""))
        preserved = {
            "id": data.get("id"), "code_name": data.get("code_name"),
            "name": data.get("name"), "group_id": data.get("group_id"),
            "position": data.get("position"), "rotation": data.get("rotation"),
            "scale": data.get("scale"), "opacity": data.get("opacity"),
            "z_index": data.get("z_index"), "visible": data.get("visible"),
            "locked": data.get("locked"), "motion": data.get("motion"),
        }
        data["asset"] = self._relative_asset_path(source)
        semantics = self._asset_semantics(source)
        data["component_category"] = semantics.get("component_category", data.get("component_category", "sprite"))
        # Mapping is preserved when replacing joystick/button art. Only fill missing mappings.
        data["ui_role"] = old_ui_role or semantics.get("ui_role", "")
        data["input_binding"] = old_input_binding or semantics.get("input_binding", "")
        for key, value in preserved.items():
            if value is not None:
                data[key] = value
        item.setPixmap(pixmap)
        item.setOffset(-pixmap.width() / 2, -pixmap.height() / 2)
        item.setTransformOriginPoint(item.boundingRect().center())
        item.setToolTip(str(data.get("name") or source.stem))
        self.selection_changed.emit(self._item_payload(item))
        self._queue_save()
        self.status_message.emit(f"[Scene] Đã thay hình {source.name}; giữ nguyên mapping {data.get('input_binding') or 'không gán'}.")
        return True

    def insert_control_kit(self) -> bool:
        if self.project_path is None:
            return False
        texture = self.project_path / "assets" / "map" / "texture"
        scenes = self.project_path / "assets" / "scenes"
        skills = self.project_path / "assets" / "map" / "skill"
        names = (
            (texture / "ui_joystick_left.png", QPointF(-self._camera_width * 0.36, self._camera_height * 0.34)),
            (texture / "ui_joystick_right.png", QPointF(-self._camera_width * 0.22, self._camera_height * 0.34)),
            (texture / "ui_run_button_round.png", QPointF(self._camera_width * 0.28, self._camera_height * 0.34)),
            (texture / "ui_jump_button_round.png", QPointF(self._camera_width * 0.40, self._camera_height * 0.28)),
            (texture / "ui_player_attack_button.png", QPointF(self._camera_width * 0.28, self._camera_height * 0.20)),
            (texture / "ui_player_interact_button.png", QPointF(self._camera_width * 0.40, self._camera_height * 0.12)),
            (scenes / "template_player_blue.png", QPointF(-self._camera_width * 0.10, self._camera_height * 0.18)),
            (skills / "template_effect_orb.png", QPointF(self._camera_width * 0.08, -self._camera_height * 0.05)),
        )
        camera_pos = self._point_from(self._camera_node().get("position"), QPointF(0, 0))
        created = 0
        for path, relative_pos in names:
            if path.exists() and self._create_sprite_item(path, position=camera_pos + relative_pos, persist=False):
                created += 1
        if created:
            group_items = self._selected_items()
            self._queue_save()
            self.status_message.emit(f"[Scene] Đã thêm bộ mẫu scene gồm {created} thành phần (nhân vật, hiệu ứng, joystick và nút).")
            return True
        return False

    @staticmethod
    def _mime_image_paths(mime) -> list[Path]:
        candidates: list[Path] = []
        if mime.hasUrls(): candidates.extend(Path(url.toLocalFile()) for url in mime.urls() if url.isLocalFile())
        if mime.hasFormat("application/x-vxp-asset"):
            try:
                candidates.extend(Path(line) for line in bytes(mime.data("application/x-vxp-asset")).decode("utf-8").splitlines() if line.strip())
            except (UnicodeDecodeError, ValueError): pass
        result: list[Path] = []; seen: set[str] = set()
        for path in candidates:
            try: resolved = path.resolve()
            except OSError: continue
            key = str(resolved).lower()
            if key not in seen and resolved.is_file() and resolved.suffix.lower() in IMAGE_EXTENSIONS:
                seen.add(key); result.append(resolved)
        return result

    def apply_motion_preset(self, preset: str) -> bool:
        selected = self._selected_items()
        if not selected:
            return False
        presets = {
            "move_left_right": {"type": "move", "axis": "x", "distance": 48, "duration": 1.2, "loop": True, "easing": "easeInOut"},
            "move_up_down": {"type": "move", "axis": "y", "distance": 36, "duration": 1.0, "loop": True, "easing": "easeInOut"},
            "float": {"type": "float", "distance": 18, "duration": 1.4, "loop": True, "easing": "sine"},
            "pulse": {"type": "scale", "from": 1.0, "to": 1.12, "duration": 0.9, "loop": True, "easing": "easeInOut"},
            "spin": {"type": "rotate", "degrees": 360, "duration": 1.8, "loop": True, "easing": "linear"},
            "fade": {"type": "opacity", "from": 1.0, "to": 0.35, "duration": 0.85, "loop": True, "easing": "easeInOut"},
        }
        motion = presets.get(preset)
        if motion is None:
            return False
        for item in selected:
            item.metadata["motion"] = dict(motion)
        self._queue_save()
        self.status_message.emit(f"[Scene] Đã áp dụng hiệu ứng '{preset}' cho {len(selected)} thành phần.")
        return True

    def clear_motion_preset(self) -> bool:
        selected = self._selected_items()
        if not selected:
            return False
        for item in selected:
            item.metadata.pop("motion", None)
        self._queue_save()
        self.status_message.emit(f"[Scene] Đã xóa hiệu ứng chuyển động khỏi {len(selected)} thành phần.")
        return True

    def open_selected_in_keyframe_editor(self) -> bool:
        selected = self._selected_items()
        if len(selected) != 1 or self._selected_group_id:
            self.status_message.emit("[Keyframe] Hãy chọn đúng một thành phần/nhân vật để mở Keyframe Editor.")
            return False
        payload = self._item_payload(selected[0])
        self.keyframe_editor_requested.emit(payload)
        return True

    def apply_keyframe_data(self, node_id: str, keyframes: list[dict], anchor: dict) -> bool:
        item = self._node_items.get(str(node_id))
        if item is None:
            return False
        data = getattr(item, "metadata", {})
        data["animation_keyframes"] = [dict(frame) for frame in keyframes if isinstance(frame, dict)]
        data["anchor"] = dict(anchor or {})
        data["animation_mode"] = "keyframe"
        self.selection_changed.emit(self._item_payload(item))
        self._queue_save()
        self.status_message.emit(
            f"[Keyframe] Đã lưu {len(data['animation_keyframes'])} keyframe và điểm neo "
            f"({data['anchor'].get('x', 0)}, {data['anchor'].get('y', 0)})."
        )
        return True

    def contextMenuEvent(self, event):  # noqa: N802 - Qt API
        """Photoshop-style component, grouping and layer actions."""
        item = self._node_item_at(event.pos())
        if item is not None and not item.isSelected():
            self._select_item(item)
        selected = self._selected_items()
        menu = QMenu(self)

        if not selected:
            paste_action = QAction(icon("fa5s.paste"), "Dán thành phần", menu)
            paste_action.setEnabled(bool(self._clipboard_nodes))
            paste_action.triggered.connect(self.paste_nodes)
            reset_action = QAction(icon("fa5s.crosshairs"), "Đặt lại góc nhìn", menu)
            reset_action.triggered.connect(self.reset_view)
            menu.addAction(paste_action)
            quick_frame_menu = menu.addMenu(icon("fa5s.align-center"), "Căn nhanh Frame Layout")
            for mode, label, icon_name in (
                ("left", "Căn khối sang trái", "fa5s.align-left"),
                ("center", "Căn khối chính giữa", "fa5s.crosshairs"),
                ("right", "Căn khối sang phải", "fa5s.align-right"),
                ("top", "Căn khối lên trên", "fa5s.arrow-up"),
                ("bottom", "Căn khối xuống dưới", "fa5s.arrow-down"),
            ):
                action = QAction(icon(icon_name), label, quick_frame_menu)
                action.triggered.connect(lambda _checked=False, value=mode: self.align_all_nodes_to_camera(value))
                quick_frame_menu.addAction(action)
            menu.addSeparator()
            menu.addAction(reset_action)
            menu.exec(event.globalPos())
            event.accept()
            return

        edit_action = QAction(icon("fa5s.magic"), "Mở Editor Assets", menu)
        keyframe_action = QAction(icon("fa5s.bezier-curve"), "Mở Keyframe / Điểm neo", menu)
        rename_action = QAction(icon("fa5s.i-cursor"), "Đặt tên thành phần/nhóm…", menu)
        duplicate_action = QAction(icon("fa5s.copy"), "Nhân đôi", menu)
        duplicate_mask_action = QAction(icon("fa5s.clone"), "Nhân đôi + Clipping Mask", menu)
        copy_action = QAction(icon("fa5s.copy"), "Sao chép", menu)
        paste_action = QAction(icon("fa5s.paste"), "Dán", menu)
        delete_action = QAction(icon("fa5s.trash-alt", "#EF747A"), "Xóa", menu)
        edit_action.setEnabled(bool(self._selected_group_id) or bool(selected))
        keyframe_action.setEnabled(len(selected) == 1 and self._selected_group_id is None)
        edit_action.triggered.connect(self.open_selected_in_asset_editor)
        keyframe_action.triggered.connect(self.open_selected_in_keyframe_editor)
        rename_action.triggered.connect(self.rename_selected)
        duplicate_action.triggered.connect(self.duplicate_selected)
        duplicate_mask_action.triggered.connect(lambda: self.duplicate_selected(clipping_mask=True))
        copy_action.triggered.connect(self.copy_selected)
        paste_action.setEnabled(bool(self._clipboard_nodes))
        paste_action.triggered.connect(self.paste_nodes)
        delete_action.triggered.connect(self.delete_selected)

        group_action = QAction(icon("fa5s.object-group"), "Gộp nhóm", menu)
        group_action.setEnabled(len(selected) >= 2 and self._selected_group_id is None)
        group_action.triggered.connect(self.group_selected)
        ungroup_action = QAction(icon("fa5s.object-ungroup"), "Tách nhóm", menu)
        ungroup_action.setEnabled(
            bool(self._selected_group_id) or any(str(getattr(node, "metadata", {}).get("group_id", "")) for node in selected)
        )
        ungroup_action.triggered.connect(self.ungroup_selected)
        lock_action = QAction(icon("fa5s.lock" if not all(self._item_is_locked(node) for node in selected) else "fa5s.unlock"), "Khóa/Mở khóa", menu)
        lock_action.triggered.connect(self.toggle_lock_selected)

        quick_center_action = QAction(icon("fa5s.crosshairs"), "Căn nhanh chính giữa Camera2D", menu)
        quick_center_action.triggered.connect(lambda: self.align_selected("camera_center"))
        menu.addAction(quick_center_action)

        layer_menu = menu.addMenu(icon("fa5s.layer-group"), "Sắp xếp lớp")
        layer_actions = (
            ("front", "Đưa lên trên cùng", "fa5s.angle-double-up"),
            ("forward", "Đưa lên một lớp", "fa5s.angle-up"),
            ("backward", "Đưa xuống một lớp", "fa5s.angle-down"),
            ("back", "Đưa xuống dưới cùng", "fa5s.angle-double-down"),
        )
        for mode, label, icon_name in layer_actions:
            action = QAction(icon(icon_name), label, layer_menu)
            action.triggered.connect(lambda _checked=False, value=mode: self.move_selected_layer(value))
            layer_menu.addAction(action)

        align_menu = menu.addMenu(icon("fa5s.align-center"), "Căn chỉnh")
        align_actions = (
            ("left", "Căn trái", "fa5s.align-left"),
            ("hcenter", "Căn giữa ngang", "fa5s.grip-lines-vertical"),
            ("right", "Căn phải", "fa5s.align-right"),
            ("top", "Căn trên", "fa5s.arrow-up"),
            ("vcenter", "Căn giữa dọc", "fa5s.grip-lines"),
            ("bottom", "Căn dưới", "fa5s.arrow-down"),
            ("center", "Căn chính giữa", "fa5s.crosshairs"),
            ("distribute_h", "Phân bố ngang", "fa5s.arrows-alt-h"),
            ("distribute_v", "Phân bố dọc", "fa5s.arrows-alt-v"),
        )
        for mode, label, icon_name in align_actions:
            action = QAction(icon(icon_name), label, align_menu)
            action.setEnabled(len(selected) >= (3 if mode.startswith("distribute") else 2))
            action.triggered.connect(lambda _checked=False, value=mode: self.align_selected(value))
            align_menu.addAction(action)
        camera_align_menu = align_menu.addMenu(icon("fa5s.expand"), "Căn theo Camera2D")
        for mode, label, icon_name in (
            ("camera_left", "Căn mép trái", "fa5s.align-left"),
            ("camera_hcenter", "Căn giữa ngang", "fa5s.grip-lines-vertical"),
            ("camera_right", "Căn mép phải", "fa5s.align-right"),
            ("camera_top", "Căn mép trên", "fa5s.arrow-up"),
            ("camera_vcenter", "Căn giữa dọc", "fa5s.grip-lines"),
            ("camera_bottom", "Căn mép dưới", "fa5s.arrow-down"),
            ("camera_center", "Căn chính giữa khung", "fa5s.crosshairs"),
        ):
            action = QAction(icon(icon_name), label, camera_align_menu)
            action.setEnabled(bool(selected))
            action.triggered.connect(lambda _checked=False, value=mode: self.align_selected(value))
            camera_align_menu.addAction(action)

        transform_menu = menu.addMenu(icon("fa5s.exchange-alt"), "Biến đổi")
        flip_h = QAction(icon("fa5s.arrows-alt-h"), "Lật ngang", transform_menu)
        flip_v = QAction(icon("fa5s.arrows-alt-v"), "Lật dọc", transform_menu)
        flip_h.triggered.connect(lambda: self.flip_selected(True))
        flip_v.triggered.connect(lambda: self.flip_selected(False))
        transform_menu.addAction(flip_h); transform_menu.addAction(flip_v)
        transform_menu.addSeparator()
        reset_size_action = QAction(icon("fa5s.compress-arrows-alt"), "Đặt lại kích thước 100%", transform_menu)
        aspect_lock_action = QAction(icon("fa5s.link"), "Khóa/Mở khóa tỉ lệ kéo dãn", transform_menu)
        reset_size_action.triggered.connect(self.reset_selected_size)
        aspect_lock_action.triggered.connect(self.toggle_selected_aspect_lock)
        transform_menu.addAction(reset_size_action)
        transform_menu.addAction(aspect_lock_action)

        automation_action = QAction(icon("fa5s.robot"), "Ánh xạ vai trò / tự động hóa…", menu)
        automation_action.triggered.connect(
            lambda: self.automation_mapping_requested.emit(self._selected_automation_payload())
        )
        menu.addAction(automation_action)

        event_menu = menu.addMenu(icon("fa5s.bolt"), "Ánh xạ sự kiện cơ bản")
        edit_event_action = QAction(icon("fa5s.sliders-h"), "Cấu hình sự kiện…", event_menu)
        edit_event_action.triggered.connect(lambda: self.event_mapping_requested.emit(self._selected_event_payload()))
        event_menu.addAction(edit_event_action)
        event_menu.addSeparator()
        for event_key, label, icon_name in (("on_touch", "Chạm / tương tác", "fa5s.hand-pointer"), ("on_overlap", "Va chạm / overlap", "fa5s.compress-arrows-alt"), ("screen_link", "Nối sang map khác", "fa5s.map-signs")):
            action = QAction(icon(icon_name), label, event_menu)
            action.triggered.connect(lambda _checked=False, value=event_key: self.assign_basic_event(value))
            event_menu.addAction(action)

        motion_menu = menu.addMenu(icon("fa5s.magic"), "Hiệu ứng tự động")
        for preset_key, label, icon_name in (
            ("move_left_right", "Di chuyển trái ↔ phải", "fa5s.arrows-alt-h"),
            ("move_up_down", "Di chuyển lên ↕ xuống", "fa5s.arrows-alt-v"),
            ("float", "Lơ lửng / bobbing", "fa5s.feather-alt"),
            ("pulse", "Phóng to / thu nhỏ", "fa5s.expand-arrows-alt"),
            ("spin", "Xoay vòng", "fa5s.sync"),
            ("fade", "Nhấp nháy opacity", "fa5s.adjust"),
        ):
            action = QAction(icon(icon_name), label, motion_menu)
            action.triggered.connect(lambda _checked=False, value=preset_key: self.apply_motion_preset(value))
            motion_menu.addAction(action)
        motion_menu.addSeparator()
        clear_motion = QAction(icon("fa5s.eraser"), "Xóa hiệu ứng", motion_menu)
        clear_motion.triggered.connect(self.clear_motion_preset)
        motion_menu.addAction(clear_motion)

        menu.insertAction(layer_menu.menuAction(), group_action)
        menu.insertAction(layer_menu.menuAction(), ungroup_action)
        menu.insertSeparator(layer_menu.menuAction())
        menu.addSeparator()
        menu.addAction(lock_action)
        menu.addSeparator()
        menu.addAction(edit_action)
        menu.addAction(keyframe_action)
        menu.addAction(rename_action)
        menu.addAction(duplicate_action)
        menu.addAction(duplicate_mask_action)
        menu.addAction(copy_action)
        menu.addAction(paste_action)
        menu.addSeparator()
        menu.addAction(delete_action)
        menu.exec(event.globalPos())
        event.accept()

    def keyPressEvent(self, event):  # noqa: N802
        control = bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier)
        if control and event.key() == Qt.Key.Key_Z:
            (self.redo() if event.modifiers() & Qt.KeyboardModifier.ShiftModifier else self.undo()); event.accept(); return
        if control and event.key() == Qt.Key.Key_Y: self.redo(); event.accept(); return
        if control and event.key() == Qt.Key.Key_D: self.duplicate_selected(); event.accept(); return
        if control and event.key() == Qt.Key.Key_G:
            (self.ungroup_selected() if event.modifiers() & Qt.KeyboardModifier.ShiftModifier else self.group_selected())
            event.accept(); return
        if control and event.key() == Qt.Key.Key_C: self.copy_selected(); event.accept(); return
        if control and event.key() == Qt.Key.Key_V: self.paste_nodes(); event.accept(); return
        if control and event.key() == Qt.Key.Key_BracketRight:
            self.move_selected_layer("front" if event.modifiers() & Qt.KeyboardModifier.ShiftModifier else "forward")
            event.accept(); return
        if control and event.key() == Qt.Key.Key_BracketLeft:
            self.move_selected_layer("back" if event.modifiers() & Qt.KeyboardModifier.ShiftModifier else "backward")
            event.accept(); return
        if event.key() in {Qt.Key.Key_Delete, Qt.Key.Key_Backspace} and self.delete_selected(): event.accept(); return
        if event.key() == Qt.Key.Key_F: self.frame_selection(); event.accept(); return
        if event.key() == Qt.Key.Key_F2 and self.rename_selected(): event.accept(); return
        if event.key() in {Qt.Key.Key_Left, Qt.Key.Key_Right, Qt.Key.Key_Up, Qt.Key.Key_Down}:
            selected = self._selected_items()
            if selected:
                step = 10.0 if event.modifiers() & Qt.KeyboardModifier.ShiftModifier else 1.0
                dx = -step if event.key() == Qt.Key.Key_Left else step if event.key() == Qt.Key.Key_Right else 0.0
                dy = -step if event.key() == Qt.Key.Key_Up else step if event.key() == Qt.Key.Key_Down else 0.0
                for item in selected:
                    item.moveBy(dx, dy)
                self._queue_save()
                event.accept()
                return
        tool_keys = {Qt.Key.Key_Q:"Select", Qt.Key.Key_W:"Move", Qt.Key.Key_E:"Rotate", Qt.Key.Key_R:"Scale"}
        if event.key() in tool_keys: self.set_tool(tool_keys[event.key()]); event.accept(); return
        super().keyPressEvent(event)

    def mousePressEvent(self, event):  # noqa: N802
        view_pos = event.position().toPoint()
        scene_pos = self.mapToScene(view_pos)
        self._last_mouse_scene = QPointF(scene_pos)
        if view_pos.x() < RULER_SIZE or view_pos.y() < RULER_SIZE:
            event.accept()
            return
        if self.current_tool == "Terrain" and event.button() in {Qt.MouseButton.LeftButton, Qt.MouseButton.RightButton}:
            erase = self._terrain_erase_mode or event.button() == Qt.MouseButton.RightButton
            self._terrain_stroke_dirty = self._paint_terrain_cell(scene_pos, erase=erase) or self._terrain_stroke_dirty
            event.accept()
            return
        if event.button() == Qt.MouseButton.LeftButton and self.current_tool in {"Select", "Scale"}:
            hit_item = self._node_item_at(view_pos)
            multi_target = bool(self._selected_group_id) or len(self._resizable_items()) > 1
            if hit_item is None or not multi_target:
                resize_handle = self._item_resize_handle_at(view_pos)
                if resize_handle is not None and self._begin_item_resize(resize_handle, scene_pos):
                    event.accept(); return
        if event.button() == Qt.MouseButton.LeftButton and self.current_tool == "Move":
            handle = self._camera_handle_at(scene_pos)
            if handle is not None:
                self._start_camera_resize(handle, scene_pos)
                event.accept(); return
        if event.button() == Qt.MouseButton.MiddleButton or (
            event.button() == Qt.MouseButton.LeftButton and self.current_tool == "Move"
        ):
            self._pan_start = view_pos
            self._pan_scroll = (self.horizontalScrollBar().value(), self.verticalScrollBar().value())
            self.viewport().setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept(); return
        if event.button() != Qt.MouseButton.LeftButton:
            super().mousePressEvent(event); return

        if self.current_tool == "Select":
            item = self._node_item_at(view_pos)
            if item is not None and self._begin_group_drag(item, scene_pos, event.modifiers()):
                event.accept(); return
        if self.current_tool in {"Rotate", "Scale"}:
            item = self._node_item_at(view_pos) or (self._selected_items()[0] if self._selected_items() else None)
            if item is not None:
                self._begin_transform(item, scene_pos); event.accept(); return
        if self.current_tool == "Text":
            text, accepted = TextInputDialog.get_text(self, "Tạo Text2D", "Nội dung:", text="Text")
            if accepted and text:
                point = self._snap_point(scene_pos)
                node = self._base_node(None, "Text2D", "Text")
                node["position"] = [point.x(), point.y()]
                node["text"] = {"content": text, "font": "Segoe UI", "font_size": 24, "color": "#F4F7FF"}
                self._create_text_item(node, persist=True)
            event.accept(); return
        if self.current_tool == "Tile":
            point = self._snap_point(scene_pos)
            node = self._base_node(None, "Tile2D", "Tile")
            node["position"] = [point.x(), point.y()]
            node["shape"] = {"width": self.grid_size, "height": self.grid_size, "fill": DEFAULT_FILL, "stroke": DEFAULT_STROKE, "stroke_width": 1}
            self._create_vector_item(node, persist=True); event.accept(); return
        if self.current_tool in {"Rectangle", "Circle", "Line", "Brush"}:
            self._create_start = scene_pos
            self._brush_points = [scene_pos]
            preview = QGraphicsPathItem()
            pen = QPen(QColor("#8DB7FF"), 1.5); pen.setCosmetic(True); pen.setStyle(Qt.PenStyle.DashLine)
            preview.setPen(pen); preview.setBrush(QBrush(QColor(78,141,230,45))); preview.setZValue(99999)
            self.scene().addItem(preview); self._create_preview = preview
            event.accept(); return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):  # noqa: N802
        view_pos = event.position().toPoint()
        scene_pos = self.mapToScene(view_pos)
        self._last_mouse_scene = QPointF(scene_pos)
        self.viewport().update()
        if self.current_tool == "Terrain" and event.buttons() & (Qt.MouseButton.LeftButton | Qt.MouseButton.RightButton):
            erase = self._terrain_erase_mode or bool(event.buttons() & Qt.MouseButton.RightButton)
            self._terrain_stroke_dirty = self._paint_terrain_cell(scene_pos, erase=erase) or self._terrain_stroke_dirty
            event.accept()
            return
        if self._pan_start is not None and self._pan_scroll is not None:
            delta = view_pos - self._pan_start
            self.horizontalScrollBar().setValue(self._pan_scroll[0] - delta.x())
            self.verticalScrollBar().setValue(self._pan_scroll[1] - delta.y())
            event.accept(); return
        if self._group_drag is not None:
            self._move_group_drag(scene_pos)
            event.accept(); return
        if self._camera_resize_drag is not None:
            self._apply_camera_resize(scene_pos)
            event.accept(); return
        if self._item_resize_drag is not None:
            self._apply_item_resize(scene_pos, event.modifiers())
            event.accept(); return
        if self.current_tool in {"Select", "Scale"}:
            handle = self._item_resize_handle_at(view_pos)
            self._item_handle_hover = handle
            cursor_map = {
                "left": Qt.CursorShape.SizeHorCursor, "right": Qt.CursorShape.SizeHorCursor,
                "top": Qt.CursorShape.SizeVerCursor, "bottom": Qt.CursorShape.SizeVerCursor,
                "top_left": Qt.CursorShape.SizeFDiagCursor, "bottom_right": Qt.CursorShape.SizeFDiagCursor,
                "top_right": Qt.CursorShape.SizeBDiagCursor, "bottom_left": Qt.CursorShape.SizeBDiagCursor,
                "rotate": Qt.CursorShape.PointingHandCursor,
            }
            if handle is not None:
                self.viewport().setCursor(cursor_map[handle])
            elif self.current_tool == "Select":
                self.viewport().setCursor(Qt.CursorShape.ArrowCursor)
        if self.current_tool == "Move":
            handle = self._camera_handle_at(scene_pos)
            self._camera_handle_hover = handle
            cursor_map = {
                "left": Qt.CursorShape.SizeHorCursor, "right": Qt.CursorShape.SizeHorCursor,
                "top": Qt.CursorShape.SizeVerCursor, "bottom": Qt.CursorShape.SizeVerCursor,
                "top_left": Qt.CursorShape.SizeFDiagCursor, "bottom_right": Qt.CursorShape.SizeFDiagCursor,
                "top_right": Qt.CursorShape.SizeBDiagCursor, "bottom_left": Qt.CursorShape.SizeBDiagCursor,
            }
            self.viewport().setCursor(cursor_map.get(handle, Qt.CursorShape.OpenHandCursor))
        if self._transform_drag is not None:
            item = self._transform_drag["item"]
            center = self._transform_drag["center"]
            vector = scene_pos - center
            if self.current_tool == "Rotate":
                angle = math.degrees(math.atan2(vector.y(), vector.x()))
                item.setRotation(self._transform_drag["rotation"] + angle - self._transform_drag["angle"])
            else:
                distance = max(1.0, math.hypot(vector.x(), vector.y()))
                factor = max(0.02, distance / self._transform_drag["distance"])
                sx, sy = self._transform_drag["scale"]
                if self._camera_frame is not None:
                    base = item.boundingRect()
                    max_x = self._camera_width / max(base.width() * abs(sx), 0.001)
                    max_y = self._camera_height / max(base.height() * abs(sy), 0.001)
                    factor = min(factor, max_x, max_y)
                item.setTransform(QTransform.fromScale(sx * factor, sy * factor))
                item_rect = item.sceneBoundingRect()
                item.setPos(self._position_inside_camera(item.pos(), item_rect.width(), item_rect.height()))
            event.accept(); return
        if self._create_start is not None and self._create_preview is not None:
            if self.current_tool == "Brush": self._brush_points.append(scene_pos)
            self._create_preview.setPath(self._preview_path(self.current_tool, self._create_start, scene_pos, self._brush_points))
            event.accept(); return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):  # noqa: N802
        view_pos = event.position().toPoint()
        scene_pos = self.mapToScene(view_pos)
        if self.current_tool == "Terrain" and event.button() in {Qt.MouseButton.LeftButton, Qt.MouseButton.RightButton}:
            self._terrain_last_cell = None
            if self._terrain_stroke_dirty:
                self._terrain_stroke_dirty = False
                self._queue_save()
                self.status_message.emit("[Terrain] Đã cập nhật Tilemap/Rule Tile vào scene.")
            event.accept()
            return
        if event.button() in {Qt.MouseButton.MiddleButton, Qt.MouseButton.LeftButton} and self._pan_start is not None:
            self._pan_start = None; self._pan_scroll = None
            self._guide_clear_timer.start(180)
            self.viewport().setCursor(Qt.CursorShape.ArrowCursor); self.set_tool(self.current_tool)
            event.accept(); return
        if event.button() == Qt.MouseButton.LeftButton and self._group_drag is not None:
            self._end_group_drag(); self._guide_clear_timer.start(180); event.accept(); return
        if event.button() == Qt.MouseButton.LeftButton and self._camera_resize_drag is not None:
            self._camera_resize_drag = None; self._queue_save(); self._guide_clear_timer.start(180); event.accept(); return
        if event.button() == Qt.MouseButton.LeftButton and self._item_resize_drag is not None:
            self._item_resize_drag = None
            self._queue_save()
            self._guide_clear_timer.start(180)
            self.status_message.emit("[Scene] Đã cập nhật Transform (kích thước/xoay) thành phần vào scene/code bindings.")
            event.accept(); return
        if event.button() == Qt.MouseButton.LeftButton and self._transform_drag is not None:
            self._transform_drag = None; self._queue_save(); self._guide_clear_timer.start(180); event.accept(); return
        if event.button() == Qt.MouseButton.LeftButton and self._create_start is not None:
            start = self._create_start; points = list(self._brush_points)
            if self._create_preview is not None: self.scene().removeItem(self._create_preview)
            self._create_preview = None; self._create_start = None; self._brush_points = []
            self._create_node_from_tool(self.current_tool, start, scene_pos, points)
            event.accept(); return
        super().mouseReleaseEvent(event)

    def drawBackground(self, painter: QPainter, rect: QRectF):  # noqa: N802
        painter.fillRect(rect, GRID_BG)
        grid_size = max(4, self.grid_size)
        left = int(rect.left()) - (int(rect.left()) % grid_size)
        top = int(rect.top()) - (int(rect.top()) % grid_size)
        minor_lines: list[QLineF] = []; major_lines: list[QLineF] = []
        x = left
        while x < rect.right():
            (major_lines if x % (grid_size * 5) == 0 else minor_lines).append(QLineF(x, rect.top(), x, rect.bottom())); x += grid_size
        y = top
        while y < rect.bottom():
            (major_lines if y % (grid_size * 5) == 0 else minor_lines).append(QLineF(rect.left(), y, rect.right(), y)); y += grid_size
        painter.setPen(QPen(GRID_LINE, 0)); painter.drawLines(minor_lines)
        painter.setPen(QPen(GRID_LINE_MAJOR, 0)); painter.drawLines(major_lines)
        x_pen = QPen(X_AXIS_COLOR, 1.2); x_pen.setCosmetic(True); painter.setPen(x_pen); painter.drawLine(QLineF(rect.left(), 0, rect.right(), 0))
        y_pen = QPen(Y_AXIS_COLOR, 1.2); y_pen.setCosmetic(True); painter.setPen(y_pen); painter.drawLine(QLineF(0, rect.top(), 0, rect.bottom()))

    def _draw_frame_perspective(self, painter: QPainter) -> None:
        if self._camera_frame is None:
            return
        config = self._camera_node().get("frame_perspective")
        if not isinstance(config, dict) or not bool(config.get("editor_guide", True)):
            return
        kind = str(config.get("kind", ""))
        camera = self._camera_frame.rect()
        if camera.isEmpty():
            return

        painter.save()
        painter.setClipRect(camera)
        guide = QColor("#A78BFA")
        guide.setAlpha(112)
        pen = QPen(guide, 1.15)
        pen.setCosmetic(True)
        pen.setStyle(Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)

        if kind == "side_scroller":
            ground_y = camera.top() + camera.height() * 0.72
            painter.drawLine(QLineF(camera.left(), ground_y, camera.right(), ground_y))
            for fraction in (0.25, 0.5, 0.75):
                x = camera.left() + camera.width() * fraction
                painter.drawLine(QLineF(x, camera.top(), x, camera.bottom()))
            jump_x = camera.left() + camera.width() * 0.18
            painter.drawLine(QLineF(jump_x, ground_y, jump_x, ground_y - camera.height() * 0.30))
        elif kind == "top_down":
            for column in range(1, 6):
                x = camera.left() + camera.width() * column / 6
                painter.drawLine(QLineF(x, camera.top(), x, camera.bottom()))
            for row in range(1, 8):
                y = camera.top() + camera.height() * row / 8
                painter.drawLine(QLineF(camera.left(), y, camera.right(), y))
        elif kind == "three_quarter":
            vanishing = QPointF(camera.center().x(), camera.top() + camera.height() * 0.27)
            painter.drawLine(QLineF(camera.left(), vanishing.y(), camera.right(), vanishing.y()))
            for fraction in (0.0, 0.2, 0.4, 0.6, 0.8, 1.0):
                painter.drawLine(QLineF(
                    vanishing,
                    QPointF(camera.left() + camera.width() * fraction, camera.bottom()),
                ))
            for fraction in (0.42, 0.58, 0.72, 0.84, 0.93):
                y = camera.top() + camera.height() * fraction
                painter.drawLine(QLineF(camera.left(), y, camera.right(), y))
        elif kind == "isometric":
            step = max(16.0, min(camera.width(), camera.height()) / 6.0)
            span = camera.width() + camera.height() * 2
            x = camera.left() - camera.height() * 2
            while x <= camera.left() + span:
                painter.drawLine(QLineF(x, camera.top(), x + camera.height() * 2, camera.bottom()))
                painter.drawLine(QLineF(x, camera.top(), x - camera.height() * 2, camera.bottom()))
                x += step

        label_color = QColor("#D8CCFF")
        label_color.setAlpha(210)
        painter.setPen(label_color)
        painter.setFont(QFont("Segoe UI", 8, QFont.Weight.DemiBold))
        painter.drawText(
            camera.adjusted(7, 6, -7, -6),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
            str(config.get("label") or kind),
        )
        painter.restore()

    def drawForeground(self, painter: QPainter, rect: QRectF):  # noqa: N802
        super().drawForeground(painter, rect)
        self._draw_frame_perspective(painter)
        if self.current_tool == "Terrain":
            camera = self._camera_frame.rect() if self._camera_frame is not None else QRectF()
            if camera.contains(self._last_mouse_scene):
                cell = self._terrain_cell(self._last_mouse_scene)
                size = self._terrain_brush_size
                brush_rect = QRectF(
                    camera.left() + cell[0] * size,
                    camera.top() + cell[1] * size,
                    size,
                    size,
                ).intersected(camera)
                color = QColor("#FF6B6B") if self._terrain_erase_mode else QColor("#62D394")
                fill = QColor(color)
                fill.setAlpha(42)
                pen = QPen(color, 1.6)
                pen.setCosmetic(True)
                painter.setPen(pen)
                painter.setBrush(fill)
                painter.drawRect(brush_rect)
        if self._active_guide_x is not None:
            pen = QPen(SMART_GUIDE_X, 1.35)
            pen.setCosmetic(True)
            pen.setStyle(Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.drawLine(QLineF(self._active_guide_x, rect.top(), self._active_guide_x, rect.bottom()))
        if self._active_guide_y is not None:
            pen = QPen(SMART_GUIDE_Y, 1.35)
            pen.setCosmetic(True)
            pen.setStyle(Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.drawLine(QLineF(rect.left(), self._active_guide_y, rect.right(), self._active_guide_y))
        if self._camera_frame is not None and self.current_tool == "Move":
            camera_rect = self._camera_frame.sceneBoundingRect()
            handle_size = max(8.0, 10.0 / max(self._zoom, 0.12))
            painter.setPen(QPen(QColor("#BFD5FF"), 1))
            painter.setBrush(QColor("#12233B"))
            for point in (camera_rect.topLeft(), camera_rect.topRight(), camera_rect.bottomLeft(), camera_rect.bottomRight()):
                painter.drawRect(QRectF(point.x() - handle_size / 2, point.y() - handle_size / 2, handle_size, handle_size))

    def paintEvent(self, event):  # noqa: N802
        super().paintEvent(event)
        viewport = self.viewport()
        width = viewport.width()
        height = viewport.height()
        if width <= RULER_SIZE or height <= RULER_SIZE:
            return
        painter = QPainter(viewport)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        painter.fillRect(0, 0, width, RULER_SIZE, RULER_BG)
        painter.fillRect(0, 0, RULER_SIZE, height, RULER_BG)
        painter.setPen(QPen(RULER_BORDER, 1))
        painter.drawLine(RULER_SIZE, RULER_SIZE - 1, width, RULER_SIZE - 1)
        painter.drawLine(RULER_SIZE - 1, RULER_SIZE, RULER_SIZE - 1, height)

        transform_scale = abs(self.transform().m11()) or 1.0
        major = self._ruler_step(1.0 / transform_scale)
        minor = major / 5.0
        top_left = self.mapToScene(QPoint(RULER_SIZE, RULER_SIZE))
        bottom_right = self.mapToScene(QPoint(width, height))
        font = QFont("Segoe UI", 8)
        painter.setFont(font)
        painter.setPen(RULER_TEXT)

        first_x = math.floor(top_left.x() / minor) * minor
        value = first_x
        while value <= bottom_right.x() + minor:
            px = self.mapFromScene(QPointF(value, 0)).x()
            if px >= RULER_SIZE:
                major_tick = abs((value / major) - round(value / major)) < 1e-5
                tick = 9 if major_tick else 4
                px_i = int(px)
                painter.drawLine(px_i, RULER_SIZE - tick, px_i, RULER_SIZE - 1)
                if major_tick:
                    painter.drawText(px_i + 3, 10, f"{value:g}")
            value += minor

        first_y = math.floor(top_left.y() / minor) * minor
        value = first_y
        while value <= bottom_right.y() + minor:
            py = self.mapFromScene(QPointF(0, value)).y()
            if py >= RULER_SIZE:
                major_tick = abs((value / major) - round(value / major)) < 1e-5
                tick = 9 if major_tick else 4
                py_i = int(py)
                painter.drawLine(RULER_SIZE - tick, py_i, RULER_SIZE - 1, py_i)
                if major_tick:
                    painter.save()
                    painter.translate(8, py_i + 3)
                    painter.rotate(-90)
                    painter.drawText(0, 0, f"{value:g}")
                    painter.restore()
            value += minor

        cursor_view = self.mapFromScene(self._last_mouse_scene)
        if cursor_view.x() >= RULER_SIZE:
            painter.setPen(QPen(SMART_GUIDE_X, 1))
            cursor_x = int(cursor_view.x())
            painter.drawLine(cursor_x, 0, cursor_x, RULER_SIZE)
        if cursor_view.y() >= RULER_SIZE:
            painter.setPen(QPen(SMART_GUIDE_Y, 1))
            cursor_y = int(cursor_view.y())
            painter.drawLine(0, cursor_y, RULER_SIZE, cursor_y)
        painter.fillRect(0, 0, RULER_SIZE, RULER_SIZE, QColor("#111722"))
        painter.setPen(RULER_TEXT)
        painter.drawText(4, 10, "X")
        painter.drawText(13, 20, "Y")

        # Canva/Figma-style direct resize handles for selected TitleSet/components.
        selected = self._resizable_items()
        handles = self._selection_handle_points(selected)
        if handles and self.current_tool in {"Select", "Scale"}:
            ordered = [handles[name] for name in ("top_left", "top_right", "bottom_right", "bottom_left")]
            polygon = QPolygonF([QPointF(self.mapFromScene(point)) for point in ordered])
            outline_pen = QPen(QColor("#68A4FF"), 1.4)
            outline_pen.setCosmetic(True)
            painter.setPen(outline_pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPolygon(polygon)
            for handle_name, scene_point in handles.items():
                point = self.mapFromScene(scene_point)
                size = RESIZE_HANDLE_PX + (2 if handle_name == self._item_handle_hover else 0)
                rect = QRectF(point.x() - size / 2, point.y() - size / 2, size, size)
                painter.setPen(QPen(QColor("#DCE9FF"), 1))
                painter.setBrush(QColor("#2F7EF7") if handle_name == self._item_handle_hover else QColor("#182A48"))
                painter.drawRect(rect)
            rotate_point = self._rotation_handle_scene_point(selected)
            if rotate_point is not None:
                stem_pen = QPen(QColor("#68A4FF"), 1.2)
                stem_pen.setCosmetic(True)
                painter.setPen(stem_pen)
                painter.drawLine(self.mapFromScene(handles["top"]), self.mapFromScene(rotate_point))
                hovered = self._item_handle_hover == "rotate"
                painter.setPen(QPen(QColor("#DCE9FF"), 1))
                painter.setBrush(QColor("#2F7EF7") if hovered else QColor("#182A48"))
                grip = self.mapFromScene(rotate_point)
                radius = 5.5 if hovered else 4.5
                painter.drawEllipse(QRectF(grip.x() - radius, grip.y() - radius, radius * 2, radius * 2))
        painter.end()

    def wheelEvent(self, event):  # noqa: N802
        factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        next_zoom = max(0.12, min(self._zoom * factor, 8.0))
        effective = next_zoom / self._zoom
        self._zoom = next_zoom
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.scale(effective, effective)
