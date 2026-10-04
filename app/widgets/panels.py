"""Responsive editor panels for VXPEngine."""
from __future__ import annotations

import json
import shutil
import zipfile
from pathlib import Path

from file_utils import unique_destination

from PySide6.QtCore import QEvent, QMimeData, QObject, QPoint, QRect, QSize, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QAction, QColor, QCursor, QDrag, QFont, QIcon, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFontComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListView,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    QTabWidget,
    QToolButton,
    QTreeWidget,
    QTreeWidgetItem,
    QHeaderView,
    QVBoxLayout,
    QWidget,
)

from .icons import icon
from .custom_dialog import ColorPickerDialog
from .log_format import append_colored_log
from .panel_frame import PanelFrame
from .vxpemu_panel import VxpEmuPanel
from scene_screen_store import ScreenStore
from color_utils import format_hex, parse_color


class _PixelMagnifierOverlay(QWidget):
    """Transparent desktop eyedropper with a nearest-neighbour pixel lens."""

    color_picked = Signal(QColor)
    canceled = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent, Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._screens: list[tuple[QRect, object]] = []
        virtual = QRect()
        for screen in QApplication.screens():
            geometry = screen.geometry()
            virtual = geometry if virtual.isNull() else virtual.united(geometry)
            self._screens.append((geometry, screen.grabWindow(0).toImage()))
        if virtual.isNull():
            virtual = QRect(0, 0, 1, 1)
        self._virtual_geometry = virtual
        self.setGeometry(virtual)

    def _color_at(self, global_position: QPoint) -> QColor:
        for geometry, image in self._screens:
            if not geometry.contains(global_position) or image.isNull():
                continue
            local = global_position - geometry.topLeft()
            x = max(0, min(image.width() - 1, int(local.x() * image.width() / max(1, geometry.width()))))
            y = max(0, min(image.height() - 1, int(local.y() * image.height() / max(1, geometry.height()))))
            return image.pixelColor(x, y)
        return QColor()

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self.raise_(); self.activateWindow(); self.setFocus(Qt.FocusReason.ActiveWindowFocusReason)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        self.update()
        event.accept()

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            color = self._color_at(event.globalPosition().toPoint())
            if color.isValid():
                self.color_picked.emit(color)
            self.close(); event.accept(); return
        if event.button() == Qt.MouseButton.RightButton:
            self.canceled.emit(); self.close(); event.accept(); return
        super().mousePressEvent(event)

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if event.key() == Qt.Key.Key_Escape:
            self.canceled.emit(); self.close(); event.accept(); return
        super().keyPressEvent(event)

    def paintEvent(self, event) -> None:  # noqa: N802
        del event
        cursor_global = QCursor.pos()
        cursor = cursor_global - self._virtual_geometry.topLeft()
        diameter, cells = 132, 11
        cell = diameter // cells
        lens_x, lens_y = cursor.x() + 24, cursor.y() + 24
        if lens_x + diameter > self.width(): lens_x = cursor.x() - diameter - 24
        if lens_y + diameter > self.height(): lens_y = cursor.y() - diameter - 24
        lens_x = max(2, min(lens_x, self.width() - diameter - 2))
        lens_y = max(2, min(lens_y, self.height() - diameter - 2))
        lens = QRect(lens_x, lens_y, diameter, diameter)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        clip = QPainterPath(); clip.addEllipse(lens)
        painter.save(); painter.setClipPath(clip, Qt.ClipOperation.ReplaceClip)
        for row in range(cells):
            for column in range(cells):
                sample = cursor_global + QPoint(column - cells // 2, row - cells // 2)
                color = self._color_at(sample)
                painter.fillRect(lens_x + column * cell, lens_y + row * cell, cell + 1, cell + 1, color if color.isValid() else QColor("#000000"))
        painter.setPen(QPen(QColor(255, 255, 255, 75), 1))
        for index in range(1, cells):
            painter.drawLine(lens_x + index * cell, lens_y, lens_x + index * cell, lens_y + diameter)
            painter.drawLine(lens_x, lens_y + index * cell, lens_x + diameter, lens_y + index * cell)
        painter.restore()
        painter.setBrush(Qt.BrushStyle.NoBrush); painter.setPen(QPen(QColor("#F5F7FF"), 3)); painter.drawEllipse(lens)
        center_rect = QRect(lens_x + (cells // 2) * cell, lens_y + (cells // 2) * cell, cell, cell)
        painter.setPen(QPen(QColor("#FF3B6B"), 2)); painter.drawRect(center_rect)
        painter.end()


class _ColorInput(QWidget):
    """RGB editor with palette and one-shot desktop eyedropper."""

    value_changed = Signal(str)

    def __init__(self, value: str = "rgb(255, 255, 255)", parent=None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self); layout.setContentsMargins(0, 0, 0, 0); layout.setSpacing(3)
        self.edit = QLineEdit(format_hex(parse_color(value)))
        self.edit.setPlaceholderText("#ff8a3d")
        self.edit.editingFinished.connect(self._commit_text)
        layout.addWidget(self.edit, 1)
        self.palette_button = QToolButton(); self.palette_button.setIcon(icon("fa5s.palette")); self.palette_button.setToolTip("Mở bảng chọn màu")
        self.palette_button.clicked.connect(self._choose); layout.addWidget(self.palette_button)
        self.eyedrop_button = QToolButton(); self.eyedrop_button.setIcon(icon("fa5s.eye-dropper")); self.eyedrop_button.setText("Pick"); self.eyedrop_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon); self.eyedrop_button.setToolTip("Pick Color (ống nhỏ giọt): bấm rồi chọn một điểm màu trên màn hình")
        self.eyedrop_button.clicked.connect(self._start_eyedropper); layout.addWidget(self.eyedrop_button)
        self._sampling = False
        self._eyedrop_overlay: _PixelMagnifierOverlay | None = None
        self._update_swatch()

    def value(self) -> str: return self.edit.text()

    def set_value(self, value: str) -> None:
        self.edit.setText(format_hex(parse_color(value))); self._update_swatch()

    def _set_color(self, color: QColor, emit: bool = True) -> None:
        if not color.isValid(): return
        self.edit.setText(format_hex(color)); self._update_swatch()
        if emit: self.value_changed.emit(self.edit.text())

    def _update_swatch(self) -> None:
        self.edit.setStyleSheet(f"QLineEdit{{border-left:12px solid {parse_color(self.edit.text()).name()};}}")

    def _commit_text(self) -> None: self._set_color(parse_color(self.edit.text()))

    def _choose(self) -> None:
        self._set_color(ColorPickerDialog.get_color(parse_color(self.edit.text()), self, show_alpha=False))

    def _start_eyedropper(self) -> None:
        app = QApplication.instance()
        if app is None or self._sampling: return
        self._sampling = True
        self._eyedrop_overlay = _PixelMagnifierOverlay()
        self._eyedrop_overlay.color_picked.connect(self._picked_desktop_color)
        self._eyedrop_overlay.canceled.connect(self._stop_eyedropper)
        self._eyedrop_overlay.show()
        self.eyedrop_button.setToolTip("Nhấp vào điểm cần lấy màu · Esc để hủy")

    def _picked_desktop_color(self, color: QColor) -> None:
        self._set_color(color)
        self._stop_eyedropper(close_overlay=False)

    def _stop_eyedropper(self, close_overlay: bool = True) -> None:
        if not self._sampling: return
        self._sampling = False
        overlay, self._eyedrop_overlay = self._eyedrop_overlay, None
        if close_overlay and overlay is not None:
            overlay.close()
        self.eyedrop_button.setToolTip("Pick Color (ống nhỏ giọt): bấm rồi chọn một điểm màu trên màn hình")

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        return super().eventFilter(watched, event)


def _search_line(placeholder: str) -> QLineEdit:
    search = QLineEdit()
    search.setObjectName("SearchBox")
    search.setPlaceholderText(placeholder)
    search.addAction(icon("fa5s.search", "#718096"), QLineEdit.ActionPosition.LeadingPosition)
    return search


def _tree_item(text: str, icon_name: str, color: str = "#8FA0B8") -> QTreeWidgetItem:
    item = QTreeWidgetItem([text])
    item.setIcon(0, icon(icon_name, color))
    return item


def _scene_file(project_path: str) -> Path:
    root = Path(project_path)
    candidates = (
        root / "assets" / "scenes" / "main.dtfe",
        root / "scenes" / "main.dtfe",
        root / "scenes" / "main.nova",
    )
    return next((path for path in candidates if path.exists()), candidates[0])


def _load_scene(project_path: str) -> dict:
    scene_path = _scene_file(project_path)
    try:
        data = json.loads(scene_path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return {}


def _node_appearance(node_type: str) -> tuple[str, str]:
    normalized = node_type.lower()
    if "camera" in normalized:
        return "fa5s.video", "#72A8FF"
    if "sprite" in normalized or "effect" in normalized:
        return "fa5s.image", "#78D6A3"
    if "rectangle" in normalized:
        return "fa5s.vector-square", "#7DB1FF"
    if "circle" in normalized:
        return "fa5s.circle", "#82D2CE"
    if "line" in normalized or "brush" in normalized:
        return "fa5s.slash", "#F0B568"
    if "text" in normalized:
        return "fa5s.font", "#D7A5FF"
    if "tile" in normalized:
        return "fa5s.th", "#65D48A"
    return "fa5s.cube", "#9CB1C8"


class _SceneTreeWidget(QTreeWidget):
    order_changed = Signal(list)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setColumnCount(4)
        self.setHeaderLabels(["Layout / Layer", "Hiện", "Khóa", "⋯"])
        self.setAnimated(True)
        self.setIndentation(16)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setAlternatingRowColors(False)
        self.setExpandsOnDoubleClick(False)
        self.setColumnWidth(0, 220)
        self.setColumnWidth(1, 42)
        self.setColumnWidth(2, 42)
        self.setColumnWidth(3, 28)

    def dropEvent(self, event):  # noqa: N802
        super().dropEvent(event)
        self.order_changed.emit(self._serialize())

    def _serialize(self) -> list:
        def walk(parent):
            result = []
            for index in range(parent.childCount()):
                item = parent.child(index)
                payload = item.data(0, Qt.ItemDataRole.UserRole)
                if not isinstance(payload, dict):
                    continue
                entry = {
                    "id": str(payload.get("id", "")),
                    "kind": str(payload.get("kind", "node")),
                    "children": walk(item),
                }
                result.append(entry)
            return result
        top = self.topLevelItem(0)
        return walk(top) if top is not None else []


class SceneTreeWidget(QTreeWidget):
    """Photoshop-like layer tree with drag reordering."""

    order_changed = Signal(list)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setColumnCount(4)
        self.setHeaderHidden(True)
        self.setAnimated(True)
        self.setIndentation(12)
        self.setIconSize(QSize(24, 24))
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropOverwriteMode(False)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        header = self.header()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column in (1, 2, 3):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.Fixed)
            header.resizeSection(column, 18)

    def dropEvent(self, event) -> None:  # noqa: N802 - Qt API
        dragged = self.currentItem()
        payload = dragged.data(0, Qt.ItemDataRole.UserRole) if dragged is not None else None
        if not isinstance(payload, dict) or str(payload.get("kind", "")) in {"scene", "camera"}:
            event.ignore()
            return
        super().dropEvent(event)
        QTimer.singleShot(0, self._emit_order)

    def _emit_order(self) -> None:
        def serialize(item: QTreeWidgetItem) -> dict | None:
            payload = item.data(0, Qt.ItemDataRole.UserRole)
            if not isinstance(payload, dict):
                return None
            kind = str(payload.get("kind", ""))
            if kind not in {"node", "group"}:
                return None
            entry = {"kind": kind, "id": str(payload.get("id", "")), "children": []}
            for index in range(item.childCount()):
                child = serialize(item.child(index))
                if child is not None:
                    entry["children"].append(child)
            return entry

        structure: list[dict] = []
        for index in range(self.topLevelItemCount()):
            root = self.topLevelItem(index)
            for child_index in range(root.childCount()):
                entry = serialize(root.child(child_index))
                if entry is not None:
                    structure.append(entry)
        if structure:
            self.order_changed.emit(structure)


class ScenePanel(PanelFrame):
    node_open_requested = Signal(dict)
    node_action_requested = Signal(str, dict)
    screen_action_requested = Signal(str, dict)
    structure_changed = Signal(list)

    def __init__(self, project_path: str = "", parent=None) -> None:
        super().__init__("Scene", parent=parent)
        self.project_path = project_path
        self.screen_store = ScreenStore(project_path) if project_path else None
        self.current_screen_id = "main"
        self._updating_screens = False
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        scene_tab = QWidget()
        layout = QVBoxLayout(scene_tab)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(5)

        screen_bar = QWidget()
        screen_layout = QHBoxLayout(screen_bar)
        screen_layout.setContentsMargins(0, 0, 0, 0)
        screen_layout.setSpacing(4)
        self.screen_combo = QComboBox()
        self.screen_combo.setObjectName("SceneScreenCombo")
        self.screen_combo.setToolTip("Chọn màn chơi đang thiết kế")
        self.screen_combo.currentIndexChanged.connect(self._screen_changed)
        screen_layout.addWidget(self.screen_combo, 1)
        self.add_screen_button = QToolButton()
        self.add_screen_button.setObjectName("SceneScreenAction")
        self.add_screen_button.setIcon(icon("fa5s.plus"))
        self.add_screen_button.setIconSize(QSize(11, 11))
        self.add_screen_button.setFixedSize(24, 24)
        self.add_screen_button.setAutoRaise(True)
        self.add_screen_button.setToolTip("Thêm màn chơi")
        self.add_screen_button.clicked.connect(lambda: self.screen_action_requested.emit("create", {}))
        screen_layout.addWidget(self.add_screen_button)
        self.screen_menu_button = QToolButton()
        self.screen_menu_button.setObjectName("SceneScreenAction")
        self.screen_menu_button.setIcon(icon("fa5s.ellipsis-h"))
        self.screen_menu_button.setIconSize(QSize(11, 11))
        self.screen_menu_button.setFixedSize(24, 24)
        self.screen_menu_button.setAutoRaise(True)
        self.screen_menu_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        screen_menu = QMenu(self.screen_menu_button)
        for action_name, label, icon_name in (
            ("rename", "Đổi tên màn chơi…", "fa5s.i-cursor"),
            ("duplicate", "Nhân đôi màn chơi", "fa5s.copy"),
            ("map_event", "Ánh xạ sự kiện nối màn…", "fa5s.project-diagram"),
            ("delete", "Xóa màn chơi", "fa5s.trash-alt"),
        ):
            action = QAction(icon(icon_name), label, screen_menu)
            action.triggered.connect(lambda _checked=False, value=action_name: self._emit_screen_action(value))
            screen_menu.addAction(action)
        self.screen_menu_button.setMenu(screen_menu)
        screen_layout.addWidget(self.screen_menu_button)
        layout.addWidget(screen_bar)

        self.search = _search_line("Tìm node, nhóm hoặc mã gọi...")
        layout.addWidget(self.search)
        self.tree = SceneTreeWidget()
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._show_context_menu)
        self.tree.itemDoubleClicked.connect(self._open_tree_item)
        self.tree.order_changed.connect(self._layer_order_changed)
        layout.addWidget(self.tree)
        self.search.textChanged.connect(self._filter)
        self.tabs.addTab(scene_tab, icon("fa5s.sitemap"), "Scene")
        self.history_list = QListWidget()
        self.history_list.addItem("Lịch sử thao tác sẽ cập nhật theo Undo/Redo")
        self.tabs.addTab(self.history_list, icon("fa5s.history"), "History")
        self.content_layout.setContentsMargins(6, 6, 6, 6)
        self.add_widget(self.tabs)
        self.refresh()

    def _screen_changed(self, index: int) -> None:
        if self._updating_screens or index < 0:
            return
        payload = self.screen_combo.itemData(index, Qt.ItemDataRole.UserRole)
        if isinstance(payload, dict):
            self.current_screen_id = str(payload.get("id", "main"))
            self.node_open_requested.emit({
                "kind": "scene", "name": str(payload.get("name", "Main")),
                "type": "VXPScene", "screen_id": self.current_screen_id,
                "scene_file": str(payload.get("file", "assets/scenes/main.dtfe")),
            })

    def _current_screen_payload(self) -> dict:
        index = self.screen_combo.currentIndex()
        payload = self.screen_combo.itemData(index, Qt.ItemDataRole.UserRole) if index >= 0 else None
        return dict(payload) if isinstance(payload, dict) else {"id": "main", "name": "Main", "file": "assets/scenes/main.dtfe"}

    def _emit_screen_action(self, action: str) -> None:
        self.screen_action_requested.emit(action, self._current_screen_payload())

    def set_active_screen(self, screen_id: str) -> None:
        self.current_screen_id = str(screen_id or "main")
        for index in range(self.screen_combo.count()):
            payload = self.screen_combo.itemData(index, Qt.ItemDataRole.UserRole)
            if isinstance(payload, dict) and str(payload.get("id", "")) == self.current_screen_id:
                self._updating_screens = True
                self.screen_combo.setCurrentIndex(index)
                self._updating_screens = False
                break
        self.refresh()

    def _thumbnail_icon(self, payload: dict, node_type: str) -> QIcon:
        asset = str(payload.get("asset", ""))
        if asset and self.project_path:
            candidate = Path(self.project_path) / asset.replace("res://", "")
            if candidate.exists():
                pixmap = QPixmap(str(candidate))
                if not pixmap.isNull():
                    return QIcon(pixmap.scaled(26, 26, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        icon_name, color = _node_appearance(node_type)
        return icon(icon_name, color)

    def _layer_order_changed(self, structure: list) -> None:
        self.structure_changed.emit(list(structure))

    def _make_toggle(self, checked: bool, on_icon: str, off_icon: str, tooltip: str, callback) -> QToolButton:
        button = QToolButton(self.tree)
        button.setCheckable(True)
        button.setChecked(bool(checked))
        button.setObjectName("SceneLayerMiniButton")
        button.setFixedSize(16, 16)
        button.setIconSize(QSize(8, 8))
        button.setContentsMargins(0, 0, 0, 0)
        button.setAutoRaise(True)
        button.setToolTip(tooltip)
        button.setIcon(icon(on_icon if checked else off_icon, "#AFC3DF" if checked else "#58667A"))
        button.toggled.connect(lambda value: (button.setIcon(icon(on_icon if value else off_icon, "#AFC3DF" if value else "#58667A")), callback(value)))
        return button

    def _install_row_controls(self, item: QTreeWidgetItem, payload: dict) -> None:
        kind = str(payload.get("kind", "node"))
        if kind in {"scene", "camera"}:
            return
        visible = bool(payload.get("visible", True))
        locked = bool(payload.get("locked", False))
        eye = self._make_toggle(visible, "fa5s.eye", "fa5s.eye-slash", "Hiện/ẩn trong Frame Preview", lambda value: self.node_action_requested.emit("set_visible", {**payload, "value": value}))
        lock = self._make_toggle(locked, "fa5s.lock", "fa5s.unlock", "Khóa/mở khóa layout", lambda value: self.node_action_requested.emit("set_locked", {**payload, "value": value}))
        more = QToolButton(self.tree)
        more.setObjectName("SceneLayerMiniButton")
        more.setFixedSize(16, 16)
        more.setIconSize(QSize(8, 8))
        more.setContentsMargins(0, 0, 0, 0)
        more.setAutoRaise(True)
        more.setIcon(icon("fa5s.ellipsis-v"))
        more.setToolTip("Tùy chọn lớp")
        more.clicked.connect(lambda _checked=False, ref=item, button=more: self._show_item_menu(ref, button.mapToGlobal(QPoint(0, button.height()))))
        self.tree.setItemWidget(item, 1, eye)
        self.tree.setItemWidget(item, 2, lock)
        self.tree.setItemWidget(item, 3, more)

    def refresh(self, scene_file: str = "") -> None:
        self.tree.clear()
        if self.screen_store is None:
            return
        registry = self.screen_store.ensure()
        screens = [dict(item) for item in registry.get("screens", []) if isinstance(item, dict)]
        selected_id = self.current_screen_id or str(registry.get("active_screen") or "main")
        if scene_file:
            normalized = str(Path(scene_file).as_posix()).lower()
            for item in screens:
                file_value = str(item.get("file", "")).replace("\\", "/").lower()
                if normalized.endswith(file_value) or normalized == file_value:
                    selected_id = str(item.get("id", selected_id))
                    break
        if not any(str(item.get("id", "")) == selected_id for item in screens):
            selected_id = str(registry.get("active_screen") or "main")
        self.current_screen_id = selected_id

        self._updating_screens = True
        current_index = 0
        self.screen_combo.clear()
        for index, item in enumerate(screens):
            self.screen_combo.addItem(icon("fa5s.desktop", "#72A8FF"), str(item.get("name", "Screen")), item)
            if str(item.get("id", "")) == selected_id:
                current_index = index
        self.screen_combo.setCurrentIndex(current_index)
        self._updating_screens = False

        selected_screen = screens[current_index] if screens else {"id": "main", "name": "Main", "file": "assets/scenes/main.dtfe"}
        scene_path = Path(self.project_path) / str(selected_screen.get("file", "assets/scenes/main.dtfe"))
        try:
            scene_data = json.loads(scene_path.read_text(encoding="utf-8"))
            if not isinstance(scene_data, dict):
                scene_data = {}
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            scene_data = {}
        root_name = str(scene_data.get("name") or selected_screen.get("name") or "Main")
        root = QTreeWidgetItem([root_name, "", "", ""])
        root.setIcon(0, icon("fa5s.desktop", "#AF8AFF"))
        root_payload = {
            "kind": "scene", "name": root_name, "type": str(scene_data.get("type") or "VXPScene"),
            "screen_id": str(selected_screen.get("id", "main")),
            "scene_file": str(selected_screen.get("file", "assets/scenes/main.dtfe")),
        }
        root.setData(0, Qt.ItemDataRole.UserRole, root_payload)
        root.setToolTip(0, f"Nhấp đúp để mở {Path(root_payload['scene_file']).name} trong Preview 2D")
        root.setFlags((root.flags() | Qt.ItemFlag.ItemIsDropEnabled) & ~Qt.ItemFlag.ItemIsDragEnabled)

        raw_groups = [group for group in scene_data.get("groups", []) if isinstance(group, dict)]
        groups = {str(group.get("id", "")): group for group in raw_groups}
        children = scene_data.get("children")
        if not isinstance(children, list):
            children = [{"id": "camera2d", "name": "Camera2D", "type": "OrthographicCamera"}]
        all_nodes = [child for child in children if isinstance(child, dict)]
        camera_nodes = [
            child for child in all_nodes
            if "camera" in str(child.get("type", "")).lower()
        ]
        nodes = [child for child in all_nodes if child not in camera_nodes]
        group_nodes: dict[str, list[dict]] = {group_id: [] for group_id in groups}
        ungrouped: list[dict] = []
        for node in nodes:
            group_id = str(node.get("group_id", ""))
            if group_id in group_nodes:
                group_nodes[group_id].append(node)
            else:
                ungrouped.append(node)

        entries: list[tuple[float, str, dict]] = []
        for group_id, group in groups.items():
            z = float(group.get("z_index", max((float(node.get("z_index", 0)) for node in group_nodes.get(group_id, [])), default=0)))
            entries.append((z, "group", group))
        for node in ungrouped:
            entries.append((float(node.get("z_index", 0)), "node", node))
        entries.sort(key=lambda entry: entry[0], reverse=True)

        self.tree.addTopLevelItem(root)
        selected_item = root
        # Camera is a pinned scene setting, not a Photoshop content layer. Keep
        # it outside the z-order list so it never appears between artwork rows.
        for camera_node in camera_nodes:
            selected_item = self._append_node_item(root, camera_node, root_payload)
        for _z, entry_kind, data in entries:
            if entry_kind == "group":
                group_id = str(data.get("id", ""))
                item = QTreeWidgetItem([str(data.get("name") or "Group"), "", "", ""])
                item.setIcon(0, icon("fa5s.object-group", "#F0B568"))
                payload = dict(data)
                payload.update({"kind": "group", "type": "Group2D", "id": group_id, "screen_id": root_payload["screen_id"], "scene_file": root_payload["scene_file"]})
                item.setData(0, Qt.ItemDataRole.UserRole, payload)
                item.setToolTip(0, "Nhóm lớp — kéo để sắp xếp như Photoshop")
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsDragEnabled | Qt.ItemFlag.ItemIsDropEnabled)
                root.addChild(item)
                self._install_row_controls(item, payload)
                for node in sorted(group_nodes.get(group_id, []), key=lambda value: float(value.get("z_index", 0)), reverse=True):
                    self._append_node_item(item, node, root_payload)
            else:
                self._append_node_item(root, data, root_payload)

        self.tree.expandAll()
        self.tree.setCurrentItem(selected_item)
        self._filter(self.search.text())

    def _append_node_item(self, parent: QTreeWidgetItem, child: dict, root_payload: dict) -> QTreeWidgetItem:
        node_name = str(child.get("name") or child.get("type") or "Node")
        node_type = str(child.get("type") or "Node")
        item = QTreeWidgetItem([node_name, "", "", ""])
        item.setIcon(0, self._thumbnail_icon(child, node_type))
        code_name = str(child.get("code_name") or "")
        item.setToolTip(0, f"{node_type} • Code: {code_name or node_name} • kéo để đổi thứ tự lớp")
        payload = dict(child)
        payload.update({
            "kind": "camera" if "camera" in node_type.lower() else "node",
            "screen_id": root_payload["screen_id"], "scene_file": root_payload["scene_file"],
        })
        item.setData(0, Qt.ItemDataRole.UserRole, payload)
        if payload["kind"] == "camera":
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsDragEnabled)
        else:
            item.setFlags((item.flags() | Qt.ItemFlag.ItemIsDragEnabled) & ~Qt.ItemFlag.ItemIsDropEnabled)
        parent.addChild(item)
        self._install_row_controls(item, payload)
        return item

    def add_history_entry(self, text: str) -> None:
        if self.history_list.count() == 1 and "sẽ cập nhật" in self.history_list.item(0).text():
            self.history_list.clear()
        self.history_list.insertItem(0, text)
        while self.history_list.count() > 80:
            self.history_list.takeItem(self.history_list.count() - 1)

    def _open_tree_item(self, item: QTreeWidgetItem, _column: int) -> None:
        payload = item.data(0, Qt.ItemDataRole.UserRole)
        if isinstance(payload, dict):
            self.node_open_requested.emit(dict(payload))

    def _show_context_menu(self, position) -> None:
        item = self.tree.itemAt(position)
        if item is None:
            return
        self._show_item_menu(item, self.tree.viewport().mapToGlobal(position))

    def _show_item_menu(self, item: QTreeWidgetItem, global_position: QPoint) -> None:
        payload = item.data(0, Qt.ItemDataRole.UserRole)
        if not isinstance(payload, dict):
            return
        self.tree.setCurrentItem(item)
        kind = str(payload.get("kind", "node")).lower()
        node_type = str(payload.get("type", "")).lower()
        editable = kind not in {"scene", "camera"} and "camera" not in node_type
        is_group = kind == "group"

        menu = QMenu(self.tree)
        open_preview = QAction(icon("fa5s.crosshairs"), "Chọn trong Frame Preview", menu)
        open_preview.triggered.connect(lambda: self.node_open_requested.emit(dict(payload)))
        menu.addAction(open_preview)
        if kind == "scene":
            menu.addSeparator()
            for action_name, label, icon_name in (
                ("rename", "Đổi tên màn chơi…", "fa5s.i-cursor"),
                ("duplicate", "Nhân đôi màn chơi", "fa5s.copy"),
                ("map_event", "Ánh xạ sự kiện nối màn…", "fa5s.project-diagram"),
                ("delete", "Xóa màn chơi", "fa5s.trash-alt"),
            ):
                action = QAction(icon(icon_name), label, menu)
                action.triggered.connect(lambda _checked=False, value=action_name: self.screen_action_requested.emit(value, self._current_screen_payload()))
                menu.addAction(action)
            menu.exec(global_position)
            return

        if is_group:
            rename_group = QAction(icon("fa5s.i-cursor"), "Đổi tên nhóm…", menu)
            rename_group.triggered.connect(lambda: self.node_action_requested.emit("rename", dict(payload)))
            ungroup = QAction(icon("fa5s.object-ungroup"), "Tách nhóm", menu)
            ungroup.triggered.connect(lambda: self.node_action_requested.emit("ungroup", dict(payload)))
            menu.addAction(rename_group)
            menu.addAction(ungroup)
        else:
            edit_asset = QAction(icon("fa5s.magic"), "Mở Editor Assets", menu)
            edit_asset.setEnabled(editable)
            edit_asset.triggered.connect(lambda: self.node_action_requested.emit("asset_editor", dict(payload)))
            menu.addAction(edit_asset)
            rename = QAction(icon("fa5s.i-cursor"), "Đặt tên thành phần…", menu)
            rename.setEnabled(editable)
            rename.triggered.connect(lambda: self.node_action_requested.emit("rename", dict(payload)))
            menu.addAction(rename)

        if editable:
            visible_action = QAction(icon("fa5s.eye" if not bool(payload.get("visible", True)) else "fa5s.eye-slash"), "Bật/Ẩn lớp", menu)
            visible_action.triggered.connect(lambda: self.node_action_requested.emit("set_visible", {**payload, "value": not bool(payload.get("visible", True))}))
            lock_action = QAction(icon("fa5s.unlock" if bool(payload.get("locked", False)) else "fa5s.lock"), "Khóa/Mở khóa layout", menu)
            lock_action.triggered.connect(lambda: self.node_action_requested.emit("set_locked", {**payload, "value": not bool(payload.get("locked", False))}))
            menu.addAction(visible_action)
            menu.addAction(lock_action)
            automation_action = QAction(icon("fa5s.robot"), "Ánh xạ vai trò / tự động hóa…", menu)
            automation_action.triggered.connect(lambda: self.node_action_requested.emit("automation_mapping", dict(payload)))
            menu.addAction(automation_action)
            event_action = QAction(icon("fa5s.bolt"), "Ánh xạ sự kiện cơ bản…", menu)
            event_action.triggered.connect(lambda: self.node_action_requested.emit("event_mapping", dict(payload)))
            menu.addAction(event_action)

            layer_menu = menu.addMenu(icon("fa5s.layer-group"), "Sắp xếp lớp")
            for action_name, label, icon_name in (
                ("front", "Đưa lên trên cùng", "fa5s.angle-double-up"),
                ("forward", "Đưa lên một lớp", "fa5s.angle-up"),
                ("backward", "Đưa xuống một lớp", "fa5s.angle-down"),
                ("back", "Đưa xuống dưới cùng", "fa5s.angle-double-down"),
            ):
                action = QAction(icon(icon_name), label, layer_menu)
                action.triggered.connect(lambda _checked=False, value=action_name: self.node_action_requested.emit(value, dict(payload)))
                layer_menu.addAction(action)
            duplicate = QAction(icon("fa5s.copy"), "Nhân đôi", menu)
            duplicate.triggered.connect(lambda: self.node_action_requested.emit("duplicate", dict(payload)))
            clipping = QAction(icon("fa5s.mask"), "Nhân đôi thành Clipping Mask", menu)
            clipping.triggered.connect(lambda: self.node_action_requested.emit("duplicate_clipping", dict(payload)))
            menu.addAction(duplicate)
            menu.addAction(clipping)
        menu.addSeparator()
        delete = QAction(icon("fa5s.trash-alt", "#EF747A"), "Xóa", menu)
        delete.setEnabled(editable)
        delete.triggered.connect(lambda: self.node_action_requested.emit("delete", dict(payload)))
        menu.addAction(delete)
        menu.exec(global_position)

    def _filter(self, text: str) -> None:
        query = text.strip().lower()
        root = self.tree.invisibleRootItem()
        for i in range(root.childCount()):
            self._filter_item(root.child(i), query)

    def _filter_item(self, item: QTreeWidgetItem, query: str) -> bool:
        child_match = any(self._filter_item(item.child(index), query) for index in range(item.childCount()))
        own_match = not query or query in item.text(0).lower() or query in item.toolTip(0).lower()
        visible = own_match or child_match
        item.setHidden(not visible)
        if query and child_match:
            item.setExpanded(True)
        return visible

def build_scene_panel(project_path: str = "") -> ScenePanel:
    return ScenePanel(project_path)


def build_assets_panel(project_path: str = "", package_name: str = "com.vxp.ten_project") -> PanelFrame:
    from .asset_manager import build_assets_panel as build_project_assets_panel
    return build_project_assets_panel(project_path, package_name)


def _prop_row(name: str, widget: QWidget) -> QFrame:
    row = QFrame()
    row.setProperty("class", "PropRow")
    layout = QHBoxLayout(row)
    layout.setContentsMargins(2, 2, 2, 2)
    label = QLabel(name)
    label.setProperty("class", "PropName")
    label.setMinimumWidth(64)
    label.setMaximumWidth(82)
    layout.addWidget(label)
    layout.addWidget(widget, 1)
    return row


def _group_label(text: str) -> QLabel:
    label = QLabel(text)
    label.setProperty("class", "PropGroupLabel")
    return label


class InspectorPanel(PanelFrame):
    """Scrollable property editor for camera, sprites, vector nodes and text."""

    property_changed = Signal(str, object)
    action_requested = Signal(str)
    delete_requested = Signal()

    def __init__(self, project_path: str = "", parent=None) -> None:
        super().__init__("Inspector", parent=parent)
        self.project_path = project_path
        self._updating = False
        self._mode = "camera"
        self.set_content_margins(0, 0, 0, 0)

        self.scroll = QScrollArea()
        self.scroll.setObjectName("InspectorScroll")
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scroll.setStyleSheet("QScrollBar:vertical{width:0px;background:transparent;} QScrollBar::handle:vertical{background:transparent;}")
        self.form = QWidget()
        self.form.setObjectName("InspectorForm")
        self.form_layout = QVBoxLayout(self.form)
        self.form_layout.setContentsMargins(8, 8, 8, 12)
        self.form_layout.setSpacing(6)
        self.scroll.setWidget(self.form)
        self.add_widget(self.scroll)

        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(2, 2, 2, 8)
        self.header_icon = QLabel()
        header_layout.addWidget(self.header_icon)
        self.header_text = QLabel()
        self.header_text.setWordWrap(True)
        header_layout.addWidget(self.header_text, 1)
        self.form_layout.addWidget(header)

        self.node_group = _group_label("NODE")
        self.form_layout.addWidget(self.node_group)
        self.name_edit = QLineEdit()
        self.name_row = _prop_row("Name", self.name_edit)
        self.form_layout.addWidget(self.name_row)
        self.code_name_edit = QLineEdit()
        self.code_name_edit.setPlaceholderText("Tên dùng trong mã C")
        self.code_name_row = _prop_row("Code ID", self.code_name_edit)
        self.form_layout.addWidget(self.code_name_row)
        self.group_label = QLabel("—")
        self.group_row = _prop_row("Group", self.group_label)
        self.form_layout.addWidget(self.group_row)
        self.member_count = QLabel("—")
        self.member_row = _prop_row("Members", self.member_count)
        self.form_layout.addWidget(self.member_row)
        self.asset_edit = QLineEdit(); self.asset_edit.setReadOnly(True)
        self.asset_row = _prop_row("Asset", self.asset_edit)
        self.form_layout.addWidget(self.asset_row)
        self.size_width = QDoubleSpinBox(); self.size_width.setRange(1, 100000); self.size_width.setDecimals(1); self.size_width.setSuffix(" px")
        self.size_height = QDoubleSpinBox(); self.size_height.setRange(1, 100000); self.size_height.setDecimals(1); self.size_height.setSuffix(" px")
        size_widget = QWidget(); size_layout = QHBoxLayout(size_widget); size_layout.setContentsMargins(0,0,0,0)
        size_layout.addWidget(QLabel("W")); size_layout.addWidget(self.size_width); size_layout.addWidget(QLabel("H")); size_layout.addWidget(self.size_height)
        self.size_row = _prop_row("Size", size_widget)
        self.form_layout.addWidget(self.size_row)

        self.transform_group = _group_label("TRANSFORM")
        self.form_layout.addWidget(self.transform_group)
        self.position_x = QDoubleSpinBox(); self.position_x.setRange(-1000000, 1000000); self.position_x.setDecimals(2)
        self.position_y = QDoubleSpinBox(); self.position_y.setRange(-1000000, 1000000); self.position_y.setDecimals(2)
        pos_widget = QWidget(); pos_layout = QHBoxLayout(pos_widget); pos_layout.setContentsMargins(0,0,0,0)
        pos_layout.addWidget(QLabel("X")); pos_layout.addWidget(self.position_x); pos_layout.addWidget(QLabel("Y")); pos_layout.addWidget(self.position_y)
        self.position_row = _prop_row("Position", pos_widget); self.form_layout.addWidget(self.position_row)
        self.rotation = QDoubleSpinBox(); self.rotation.setRange(-360000, 360000); self.rotation.setSuffix("°"); self.rotation.setDecimals(2)
        self.rotation_row = _prop_row("Rotation", self.rotation); self.form_layout.addWidget(self.rotation_row)
        self.scale_x = QDoubleSpinBox(); self.scale_x.setRange(-1000,1000); self.scale_x.setValue(1); self.scale_x.setDecimals(3); self.scale_x.setSingleStep(.05)
        self.scale_y = QDoubleSpinBox(); self.scale_y.setRange(-1000,1000); self.scale_y.setValue(1); self.scale_y.setDecimals(3); self.scale_y.setSingleStep(.05)
        scale_widget = QWidget(); scale_layout = QHBoxLayout(scale_widget); scale_layout.setContentsMargins(0,0,0,0)
        scale_layout.addWidget(QLabel("X")); scale_layout.addWidget(self.scale_x); scale_layout.addWidget(QLabel("Y")); scale_layout.addWidget(self.scale_y)
        self.scale_prop_row = _prop_row("Scale", scale_widget); self.form_layout.addWidget(self.scale_prop_row)
        self.lock_aspect = QCheckBox("Giữ tỉ lệ W/H")
        self.lock_aspect_row = _prop_row("Aspect", self.lock_aspect); self.form_layout.addWidget(self.lock_aspect_row)
        self.pixel_snap = QCheckBox("Tọa độ pixel nguyên")
        self.pixel_snap_row = _prop_row("Pixel snap", self.pixel_snap); self.form_layout.addWidget(self.pixel_snap_row)
        self.anchor_mode = QComboBox(); self.anchor_mode.addItems([
            "Center", "Top Left", "Top", "Top Right", "Left", "Right",
            "Bottom Left", "Bottom", "Bottom Right",
        ])
        self.anchor_row = _prop_row("Anchor", self.anchor_mode); self.form_layout.addWidget(self.anchor_row)

        self.appearance_group = _group_label("APPEARANCE")
        self.form_layout.addWidget(self.appearance_group)
        self.opacity_slider = QSlider(Qt.Orientation.Horizontal); self.opacity_slider.setRange(0, 100); self.opacity_slider.setValue(100)
        self.opacity_value = QLabel("100%")
        opacity_widget = QWidget(); opacity_layout = QHBoxLayout(opacity_widget); opacity_layout.setContentsMargins(0,0,0,0); opacity_layout.setSpacing(6)
        opacity_layout.addWidget(self.opacity_slider, 1); opacity_layout.addWidget(self.opacity_value)
        self.opacity_row = _prop_row("Opacity", opacity_widget); self.form_layout.addWidget(self.opacity_row)
        self.z_index = QSpinBox(); self.z_index.setRange(-100000,100000)
        self.z_row = _prop_row("Z Index", self.z_index); self.form_layout.addWidget(self.z_row)
        self.visible = QCheckBox("Hiển thị trong scene"); self.visible.setChecked(True)
        self.visible_row = _prop_row("Visible", self.visible); self.form_layout.addWidget(self.visible_row)
        self.locked = QCheckBox("Khóa chỉnh sửa")
        self.locked_row = _prop_row("Locked", self.locked); self.form_layout.addWidget(self.locked_row)
        self.blend_mode = QComboBox(); self.blend_mode.addItems(["Normal", "Additive", "Multiply", "Screen"])
        self.blend_row = _prop_row("Blend", self.blend_mode); self.form_layout.addWidget(self.blend_row)
        self.tint_color = _ColorInput("rgb(255, 255, 255)")
        self.tint_row = _prop_row("Tint", self.tint_color); self.form_layout.addWidget(self.tint_row)
        self.background_bitmap = QLineEdit(); self.background_bitmap.setReadOnly(True)
        self.background_bitmap.setPlaceholderText("Không có ảnh nền")
        bitmap_widget = QWidget(); bitmap_layout = QHBoxLayout(bitmap_widget); bitmap_layout.setContentsMargins(0,0,0,0); bitmap_layout.setSpacing(3)
        bitmap_layout.addWidget(self.background_bitmap, 1)
        self.background_bitmap_browse = QToolButton(); self.background_bitmap_browse.setIcon(icon("fa5s.folder-open")); self.background_bitmap_browse.setToolTip("Chọn BackgroundBitmap")
        self.background_bitmap_clear = QToolButton(); self.background_bitmap_clear.setIcon(icon("fa5s.times")); self.background_bitmap_clear.setToolTip("Bỏ BackgroundBitmap")
        bitmap_layout.addWidget(self.background_bitmap_browse); bitmap_layout.addWidget(self.background_bitmap_clear)
        self.background_bitmap_row = _prop_row("Bg Bitmap", bitmap_widget); self.form_layout.addWidget(self.background_bitmap_row)
        self.background_bitmap_mode = QComboBox(); self.background_bitmap_mode.addItems(["Fill", "Fit", "Stretch", "Tile"])
        self.background_bitmap_mode.setToolTip("Fill: phủ kín; Fit: vừa khung; Stretch: kéo đầy; Tile: lát ảnh")
        self.background_bitmap_mode_row = _prop_row("Bitmap mode", self.background_bitmap_mode); self.form_layout.addWidget(self.background_bitmap_mode_row)

        self.automation_group = _group_label("AUTOMATION / GAMEPLAY")
        self.form_layout.addWidget(self.automation_group)
        self.automation_role_label = QLabel("—")
        self.automation_role_row = _prop_row("Role", self.automation_role_label); self.form_layout.addWidget(self.automation_role_row)
        self.automation_input_label = QLabel("—")
        self.automation_input_row = _prop_row("Input", self.automation_input_label); self.form_layout.addWidget(self.automation_input_row)
        self.automation_physics_label = QLabel("—")
        self.automation_physics_row = _prop_row("Physics", self.automation_physics_label); self.form_layout.addWidget(self.automation_physics_row)
        self.automation_tags_label = QLabel("—"); self.automation_tags_label.setWordWrap(True)
        self.automation_tags_row = _prop_row("Tags", self.automation_tags_label); self.form_layout.addWidget(self.automation_tags_row)
        self.collision_enabled = QCheckBox("Bật va chạm")
        self.collision_enabled_row = _prop_row("Collision", self.collision_enabled); self.form_layout.addWidget(self.collision_enabled_row)
        self.collision_shape = QComboBox(); self.collision_shape.addItems(["bounds", "circle", "none"])
        self.collision_shape_row = _prop_row("Hit shape", self.collision_shape); self.form_layout.addWidget(self.collision_shape_row)
        self.physics_mode = QComboBox(); self.physics_mode.addItems(["none", "static", "kinematic", "dynamic", "trigger"])
        self.physics_mode_row = _prop_row("Physics", self.physics_mode); self.form_layout.addWidget(self.physics_mode_row)
        self.automation_button = QPushButton("Cấu hình ánh xạ…")
        self.automation_button.setIcon(icon("fa5s.robot"))
        self.automation_button.clicked.connect(lambda: self.action_requested.emit("automation_mapping"))
        self.automation_button_row = _prop_row("Mapping", self.automation_button); self.form_layout.addWidget(self.automation_button_row)

        self.layer_group = _group_label("LAYERS & ARRANGE")
        self.form_layout.addWidget(self.layer_group)
        layer_widget = QWidget(); layer_layout = QGridLayout(layer_widget); layer_layout.setContentsMargins(0,0,0,0); layer_layout.setSpacing(4)
        layer_actions = [
            ("back", "fa5s.angle-double-down", "Xuống dưới cùng"),
            ("backward", "fa5s.angle-down", "Xuống một lớp"),
            ("forward", "fa5s.angle-up", "Lên một lớp"),
            ("front", "fa5s.angle-double-up", "Lên trên cùng"),
            ("flip_h", "fa5s.arrows-alt-h", "Lật ngang"),
            ("flip_v", "fa5s.arrows-alt-v", "Lật dọc"),
            ("group", "fa5s.object-group", "Gộp nhóm"),
            ("ungroup", "fa5s.object-ungroup", "Tách nhóm"),
            ("left", "fa5s.align-left", "Căn trái các thành phần đã chọn"),
            ("hcenter", "fa5s.grip-lines-vertical", "Căn giữa ngang vùng chọn"),
            ("right", "fa5s.align-right", "Căn phải các thành phần đã chọn"),
            ("center", "fa5s.crosshairs", "Căn chính giữa vùng chọn"),
            ("top", "fa5s.arrow-up", "Căn trên các thành phần đã chọn"),
            ("vcenter", "fa5s.grip-lines", "Căn giữa dọc vùng chọn"),
            ("bottom", "fa5s.arrow-down", "Căn dưới các thành phần đã chọn"),
            ("distribute_h", "fa5s.arrows-alt-h", "Phân bố khoảng cách ngang"),
            ("distribute_v", "fa5s.arrows-alt-v", "Phân bố khoảng cách dọc"),
            ("camera_left", "fa5s.step-backward", "Căn khối theo mép trái Camera2D"),
            ("camera_hcenter", "fa5s.grip-lines-vertical", "Căn giữa ngang theo Camera2D"),
            ("camera_center", "fa5s.expand", "Căn khối chính giữa Camera2D"),
            ("camera_right", "fa5s.step-forward", "Căn khối theo mép phải Camera2D"),
            ("camera_top", "fa5s.step-backward", "Căn khối theo mép trên Camera2D"),
            ("camera_vcenter", "fa5s.grip-lines", "Căn giữa dọc theo Camera2D"),
            ("camera_bottom", "fa5s.step-forward", "Căn khối theo mép dưới Camera2D"),
        ]
        self.layer_buttons = []
        self.layer_buttons_by_command = {}
        for index, (command, icon_name, tip) in enumerate(layer_actions):
            button = QToolButton(); button.setIcon(icon(icon_name)); button.setToolTip(tip); button.setFixedHeight(27)
            button.clicked.connect(lambda _checked=False, value=command: self.action_requested.emit(value))
            layer_layout.addWidget(button, index // 4, index % 4); self.layer_buttons.append(button)
            self.layer_buttons_by_command[command] = button
        self.layer_controls_row = _prop_row("Actions", layer_widget); self.form_layout.addWidget(self.layer_controls_row)

        self.vector_group = _group_label("VECTOR")
        self.form_layout.addWidget(self.vector_group)
        self.fill_color = _ColorInput("rgb(78, 141, 230)"); self.fill_row = _prop_row("Fill", self.fill_color); self.form_layout.addWidget(self.fill_row)
        self.stroke_color = _ColorInput("rgb(191, 213, 255)"); self.stroke_row = _prop_row("Stroke", self.stroke_color); self.form_layout.addWidget(self.stroke_row)
        self.stroke_width = QDoubleSpinBox(); self.stroke_width.setRange(0,100); self.stroke_width.setValue(2)
        self.stroke_width_row = _prop_row("Width", self.stroke_width); self.form_layout.addWidget(self.stroke_width_row)
        self.corner_radius = QDoubleSpinBox(); self.corner_radius.setRange(0,10000); self.corner_radius.setSuffix(" px")
        self.corner_radius_row = _prop_row("Corner radius", self.corner_radius); self.form_layout.addWidget(self.corner_radius_row)

        self.layout_group = _group_label("LAYOUT BOX")
        self.form_layout.addWidget(self.layout_group)
        self.padding = QSpinBox(); self.padding.setRange(0,10000); self.padding.setSuffix(" px")
        self.padding_row = _prop_row("Padding", self.padding); self.form_layout.addWidget(self.padding_row)
        self.margin = QSpinBox(); self.margin.setRange(0,10000); self.margin.setSuffix(" px")
        self.margin_row = _prop_row("Margin", self.margin); self.form_layout.addWidget(self.margin_row)

        self.text_group = _group_label("TEXT")
        self.form_layout.addWidget(self.text_group)
        self.text_content = QLineEdit(); self.text_content_row = _prop_row("Content", self.text_content); self.form_layout.addWidget(self.text_content_row)
        self.font_size = QSpinBox(); self.font_size.setRange(6,512); self.font_size.setValue(24)
        self.font_size_row = _prop_row("Font size", self.font_size); self.form_layout.addWidget(self.font_size_row)
        self.font_family = QFontComboBox(); self.font_family_row = _prop_row("Font", self.font_family); self.form_layout.addWidget(self.font_family_row)
        self.text_color = _ColorInput("rgb(244, 247, 255)"); self.text_color_row = _prop_row("Text color", self.text_color); self.form_layout.addWidget(self.text_color_row)
        text_style_widget = QWidget(); text_style_layout = QHBoxLayout(text_style_widget); text_style_layout.setContentsMargins(0,0,0,0)
        self.font_bold = QCheckBox("B"); self.font_bold.setToolTip("In đậm")
        self.font_italic = QCheckBox("I"); self.font_italic.setToolTip("In nghiêng")
        self.font_underline = QCheckBox("U"); self.font_underline.setToolTip("Gạch chân")
        self.font_strikeout = QCheckBox("S"); self.font_strikeout.setToolTip("Gạch ngang")
        for control in (self.font_bold, self.font_italic, self.font_underline, self.font_strikeout): text_style_layout.addWidget(control)
        self.text_style_row = _prop_row("Style", text_style_widget); self.form_layout.addWidget(self.text_style_row)

        self.camera_group = _group_label("CAMERA")
        self.form_layout.addWidget(self.camera_group)
        scene_data = _load_scene(project_path) if project_path else {}
        viewport = scene_data.get("viewport") if isinstance(scene_data.get("viewport"), dict) else {}
        self.viewport_width = QSpinBox(); self.viewport_width.setRange(240,320); self.viewport_width.setSingleStep(80); self.viewport_width.setValue(int(viewport.get("width",240)))
        self.viewport_height = QSpinBox(); self.viewport_height.setRange(240,320); self.viewport_height.setSingleStep(80); self.viewport_height.setValue(int(viewport.get("height",320)))
        self.viewport_width.setToolTip("Khung S30+ cố định: 240×320 hoặc 320×240")
        self.viewport_height.setToolTip("Khung S30+ cố định: 240×320 hoặc 320×240")
        viewport_widget = QWidget(); viewport_layout = QHBoxLayout(viewport_widget); viewport_layout.setContentsMargins(0,0,0,0)
        viewport_layout.addWidget(QLabel("W")); viewport_layout.addWidget(self.viewport_width); viewport_layout.addWidget(QLabel("H")); viewport_layout.addWidget(self.viewport_height)
        self.viewport_row = _prop_row("Viewport", viewport_widget); self.form_layout.addWidget(self.viewport_row)
        self.projection = QComboBox(); self.projection.addItems(["Orthographic", "Pixel Perfect"])
        self.projection_row = _prop_row("Projection", self.projection); self.form_layout.addWidget(self.projection_row)
        self.background = QComboBox(); self.background.addItems(["Editor Grid", "Transparent", "Game Clear Color"])
        self.background_row = _prop_row("Preview", self.background); self.form_layout.addWidget(self.background_row)

        self.delete_button = QPushButton("Xóa thành phần khỏi Scene")
        self.delete_button.setObjectName("InspectorDeleteButton")
        self.delete_button.setIcon(icon("fa5s.trash-alt", "#EF747A"))
        self.delete_button.clicked.connect(self.delete_requested.emit)
        self.form_layout.addWidget(self.delete_button)
        self.form_layout.addStretch()

        self.name_edit.editingFinished.connect(lambda: self._emit("name", self.name_edit.text()))
        self.code_name_edit.editingFinished.connect(lambda: self._emit("code_name", self.code_name_edit.text()))
        self.position_x.valueChanged.connect(lambda value: self._emit("position_x", value))
        self.position_y.valueChanged.connect(lambda value: self._emit("position_y", value))
        self.rotation.valueChanged.connect(lambda value: self._emit("rotation", value))
        self.scale_x.valueChanged.connect(lambda value: self._emit("zoom_x" if self._mode == "camera" else "scale_x", value))
        self.scale_y.valueChanged.connect(lambda value: self._emit("zoom_y" if self._mode == "camera" else "scale_y", value))
        self.size_width.valueChanged.connect(lambda value: self._emit("size_width", value))
        self.size_height.valueChanged.connect(lambda value: self._emit("size_height", value))
        self.lock_aspect.toggled.connect(lambda value: self._emit("lock_aspect", value))
        self.pixel_snap.toggled.connect(lambda value: self._emit("pixel_snap", value))
        self.anchor_mode.currentTextChanged.connect(lambda value: self._emit("anchor_mode", value))
        self.opacity_slider.valueChanged.connect(self._opacity_slider_changed)
        self.z_index.valueChanged.connect(lambda value: self._emit("z_index", value))
        self.visible.toggled.connect(lambda value: self._emit("visible", value))
        self.locked.toggled.connect(lambda value: self._emit("locked", value))
        self.blend_mode.currentTextChanged.connect(lambda value: self._emit("blend_mode", value))
        self.tint_color.value_changed.connect(lambda value: self._emit("tint", value))
        self.background_bitmap_browse.clicked.connect(self._choose_background_bitmap)
        self.background_bitmap_clear.clicked.connect(lambda: self._emit("background_bitmap", ""))
        self.background_bitmap_mode.currentTextChanged.connect(lambda value: self._emit("background_bitmap_mode", value))
        self.viewport_width.valueChanged.connect(lambda value: self._emit("viewport_width", value))
        self.viewport_height.valueChanged.connect(lambda value: self._emit("viewport_height", value))
        self.projection.currentTextChanged.connect(lambda value: self._emit("projection", value))
        self.background.currentTextChanged.connect(lambda value: self._emit("preview_background", value))
        self.fill_color.value_changed.connect(lambda value: self._emit("fill_color", value))
        self.stroke_color.value_changed.connect(lambda value: self._emit("stroke_color", value))
        self.stroke_width.valueChanged.connect(lambda value: self._emit("stroke_width", value))
        self.corner_radius.valueChanged.connect(lambda value: self._emit("corner_radius", value))
        self.padding.valueChanged.connect(lambda value: self._emit("padding", value))
        self.margin.valueChanged.connect(lambda value: self._emit("margin", value))
        self.text_content.editingFinished.connect(lambda: self._emit("text_content", self.text_content.text()))
        self.font_size.valueChanged.connect(lambda value: self._emit("font_size", value))
        self.font_family.currentFontChanged.connect(lambda value: self._emit("font_family", value.family()))
        self.text_color.value_changed.connect(lambda value: self._emit("text_color", value))
        self.font_bold.toggled.connect(lambda value: self._emit("font_bold", value))
        self.font_italic.toggled.connect(lambda value: self._emit("font_italic", value))
        self.font_underline.toggled.connect(lambda value: self._emit("font_underline", value))
        self.font_strikeout.toggled.connect(lambda value: self._emit("font_strikeout", value))
        self.collision_enabled.toggled.connect(lambda value: self._emit("collision_enabled", value))
        self.collision_shape.currentTextChanged.connect(lambda value: self._emit("collision_shape", value))
        self.physics_mode.currentTextChanged.connect(lambda value: self._emit("physics_mode", value))
        self.set_selection(self._camera_payload(scene_data))

    @staticmethod
    def _camera_payload(scene_data: dict) -> dict:
        viewport = scene_data.get("viewport") if isinstance(scene_data.get("viewport"), dict) else {}
        camera = next((node for node in scene_data.get("children", []) if isinstance(node, dict) and "camera" in str(node.get("type","")).lower()), {})
        return {
            "kind":"camera", "name":str(camera.get("name","Camera2D")), "type":str(camera.get("type","OrthographicCamera")),
            "position":camera.get("position",[0,0]), "rotation":camera.get("rotation",0), "zoom":camera.get("zoom",[1,1]),
            "viewport":[int(viewport.get("width",240)), int(viewport.get("height",320))],
            "projection":str(camera.get("projection", "Orthographic")),
            "preview_background":str(camera.get("preview_background", "Editor Grid")),
        }

    def _emit(self, key: str, value) -> None:
        if not self._updating:
            self.property_changed.emit(key, value)

    def _opacity_slider_changed(self, value: int) -> None:
        self.opacity_value.setText(f"{int(value)}%")
        self._emit("opacity", max(0.0, min(1.0, float(value) / 100.0)))

    def _choose_background_bitmap(self) -> None:
        start = Path(self.project_path) / "assets" if self.project_path else Path.home()
        path, _selected_filter = QFileDialog.getOpenFileName(
            self,
            "Chọn BackgroundBitmap",
            str(start),
            "Ảnh (*.png *.jpg *.jpeg *.webp *.bmp *.gif);;Tất cả tệp (*)",
        )
        if path:
            self._emit("background_bitmap", path)

    def set_selection(self, payload: dict) -> None:
        self._updating = True
        try:
            kind = str(payload.get("kind", "camera")).lower()
            self._mode = kind if kind in {"camera", "sprite", "shape", "text", "group", "multi"} else "shape"
            is_camera = self._mode == "camera"
            is_sprite = self._mode == "sprite"
            is_shape = self._mode == "shape"
            is_text = self._mode == "text"
            is_group = self._mode == "group"
            is_multi = self._mode == "multi"
            icon_name = {
                "camera":"fa5s.video", "sprite":"fa5s.image", "shape":"fa5s.vector-square",
                "text":"fa5s.font", "group":"fa5s.object-group", "multi":"fa5s.objects-group",
            }.get(self._mode, "fa5s.cube")
            color = {
                "camera":"#72A8FF", "sprite":"#78D6A3", "shape":"#82D2CE",
                "text":"#D7A5FF", "group":"#F0B568", "multi":"#AAB7CC",
            }.get(self._mode, "#9CB1C8")
            node_type = str(payload.get("type", "Node"))
            self.header_icon.setPixmap(icon(icon_name, color).pixmap(13,13))
            self.header_text.setText(f"{payload.get('name','Node')}  —  {node_type}")
            self.name_edit.setText(str(payload.get("name","Node")))
            self.name_edit.setReadOnly(is_camera or is_multi)
            self.code_name_edit.setText(str(payload.get("code_name", "")))
            self.group_label.setText(str(payload.get("group_name") or "—"))
            count = int(payload.get("member_count", 0) or 0)
            self.member_count.setText(str(count) if count else "—")
            self.asset_edit.setText(str(payload.get("asset","")))
            size = payload.get("display_size", payload.get("size", [1,1]))
            size_w = float(size[0]) if isinstance(size,(list,tuple)) and len(size)>=2 else 1.0
            size_h = float(size[1]) if isinstance(size,(list,tuple)) and len(size)>=2 else 1.0
            self.size_width.setValue(max(1.0, size_w)); self.size_height.setValue(max(1.0, size_h))
            position = payload.get("position",[0,0])
            self.position_x.setValue(float(position[0]) if isinstance(position,(list,tuple)) and position else 0)
            self.position_y.setValue(float(position[1]) if isinstance(position,(list,tuple)) and len(position)>1 else 0)
            self.rotation.setValue(float(payload.get("rotation",0)))
            scale = payload.get("scale", payload.get("zoom",[1,1]))
            self.scale_x.setValue(float(scale[0]) if isinstance(scale,(list,tuple)) and scale else 1)
            self.scale_y.setValue(float(scale[1]) if isinstance(scale,(list,tuple)) and len(scale)>1 else 1)
            self.lock_aspect.setChecked(bool(payload.get("lock_aspect", False)))
            self.pixel_snap.setChecked(bool(payload.get("pixel_snap", True)))
            anchor = payload.get("anchor") if isinstance(payload.get("anchor"), dict) else {}
            anchor_label = str(anchor.get("mode", "Center"))
            anchor_index = self.anchor_mode.findText(anchor_label)
            self.anchor_mode.setCurrentIndex(max(0, anchor_index))
            self.opacity_slider.setValue(int(round(float(payload.get("opacity",1)) * 100.0)))
            self.opacity_value.setText(f"{self.opacity_slider.value()}%")
            self.z_index.setValue(int(payload.get("z_index",0)))
            self.visible.setChecked(bool(payload.get("visible",True)))
            self.locked.setChecked(bool(payload.get("locked",False)))
            blend = str(payload.get("blend_mode", "Normal"))
            blend_index = self.blend_mode.findText(blend)
            self.blend_mode.setCurrentIndex(max(0, blend_index))
            self.tint_color.set_value(str(payload.get("tint", "#FFFFFFFF")))
            self.background_bitmap.setText(str(payload.get("background_bitmap", "")))
            bitmap_mode = str(payload.get("background_bitmap_mode", "Fill"))
            bitmap_mode_index = self.background_bitmap_mode.findText(bitmap_mode)
            self.background_bitmap_mode.setCurrentIndex(max(0, bitmap_mode_index))
            shape = payload.get("shape") if isinstance(payload.get("shape"),dict) else {}
            self.fill_color.set_value(str(shape.get("fill","#4E8DE6")))
            self.stroke_color.set_value(str(shape.get("stroke","#BFD5FF")))
            self.stroke_width.setValue(float(shape.get("stroke_width",2)))
            self.corner_radius.setValue(float(shape.get("corner_radius", payload.get("corner_radius", 0))))
            layout_data = payload.get("layout") if isinstance(payload.get("layout"), dict) else {}
            self.padding.setValue(int(layout_data.get("padding", payload.get("padding", 0)) or 0))
            self.margin.setValue(int(layout_data.get("margin", payload.get("margin", 0)) or 0))
            text_data = payload.get("text") if isinstance(payload.get("text"),dict) else {}
            self.text_content.setText(str(text_data.get("content", payload.get("content",""))))
            self.font_size.setValue(int(text_data.get("font_size",24)))
            self.font_family.setCurrentFont(QFont(str(text_data.get("font", "Segoe UI"))))
            self.text_color.set_value(str(text_data.get("color", "#F4F7FF")))
            self.font_bold.setChecked(bool(text_data.get("bold", False)))
            self.font_italic.setChecked(bool(text_data.get("italic", False)))
            self.font_underline.setChecked(bool(text_data.get("underline", False)))
            self.font_strikeout.setChecked(bool(text_data.get("strikeout", False)))
            viewport = payload.get("viewport",[240,320])
            self.viewport_width.setValue(int(viewport[0]) if isinstance(viewport,(list,tuple)) and viewport else 240)
            self.viewport_height.setValue(int(viewport[1]) if isinstance(viewport,(list,tuple)) and len(viewport)>1 else 320)
            projection = str(payload.get("projection", "Orthographic"))
            projection_index = self.projection.findText(projection)
            self.projection.setCurrentIndex(max(0, projection_index))
            preview_background = str(payload.get("preview_background", "Editor Grid"))
            background_index = self.background.findText(preview_background)
            self.background.setCurrentIndex(max(0, background_index))
            automation = payload.get("automation") if isinstance(payload.get("automation"), dict) else {}
            self.automation_role_label.setText(str(automation.get("role") or payload.get("ui_role") or "—"))
            self.automation_input_label.setText(str(automation.get("input_action") or payload.get("input_binding") or "—"))
            self.automation_physics_label.setText(str(automation.get("physics") or "none"))
            tags = automation.get("tags") if isinstance(automation.get("tags"), list) else []
            self.automation_tags_label.setText(", ".join(str(item) for item in tags) if tags else "—")
            collision_shape = str(automation.get("collision_shape", "none"))
            self.collision_enabled.setChecked(bool(automation.get("collision_enabled", collision_shape != "none")))
            collision_index = self.collision_shape.findText(collision_shape)
            self.collision_shape.setCurrentIndex(max(0, collision_index))
            physics = str(automation.get("physics", "none"))
            physics_index = self.physics_mode.findText(physics)
            self.physics_mode.setCurrentIndex(max(0, physics_index))

            is_node = not is_camera and not is_group and not is_multi
            self.code_name_row.setVisible(is_node)
            self.group_row.setVisible(is_node and bool(payload.get("group_name")))
            self.member_row.setVisible(is_group or is_multi)
            self.asset_row.setVisible(is_sprite)
            self.size_row.setVisible(not is_camera)
            self.transform_group.setVisible(not is_group and not is_multi)
            for widget in (self.position_row, self.rotation_row, self.scale_prop_row, self.lock_aspect_row, self.pixel_snap_row, self.anchor_row):
                widget.setVisible(not is_group and not is_multi)
            common_node_widgets = (
                self.appearance_group, self.opacity_row, self.z_row, self.visible_row,
                self.locked_row, self.layer_group, self.layer_controls_row, self.delete_button,
            )
            for widget in common_node_widgets:
                widget.setVisible(not is_camera)
            for widget in (self.automation_group, self.automation_role_row, self.automation_input_row, self.automation_physics_row, self.automation_tags_row, self.collision_enabled_row, self.collision_shape_row, self.physics_mode_row, self.automation_button_row):
                widget.setVisible(not is_camera and not is_multi)
            self.blend_row.setVisible(is_node)
            self.tint_row.setVisible(is_node)
            self.background_bitmap_row.setVisible(is_shape or is_group)
            self.background_bitmap_mode_row.setVisible(is_shape or is_group)
            for widget in (self.vector_group,self.fill_row,self.stroke_row,self.stroke_width_row,self.corner_radius_row):
                widget.setVisible(is_shape)
            for widget in (self.layout_group,self.padding_row,self.margin_row):
                widget.setVisible(is_node)
            for widget in (self.text_group,self.text_content_row,self.font_size_row,self.font_family_row,self.text_color_row,self.text_style_row):
                widget.setVisible(is_text)
            for widget in (self.camera_group,self.viewport_row,self.projection_row,self.background_row):
                widget.setVisible(is_camera)
            self.scale_prop_row.layout().itemAt(0).widget().setText("Zoom" if is_camera else "Scale")
            if len(self.layer_buttons) >= 8:
                self.layer_buttons[6].setEnabled(is_multi)
                self.layer_buttons[7].setEnabled(is_group or bool(payload.get("group_name")))
            selection_count = int(payload.get("member_count", 0) or (1 if is_node else 0))
            for command in ("left", "hcenter", "right", "center", "top", "vcenter", "bottom"):
                self.layer_buttons_by_command[command].setEnabled(selection_count >= 2)
            for command in ("distribute_h", "distribute_v"):
                self.layer_buttons_by_command[command].setEnabled(selection_count >= 3)
            for command in (
                "camera_left", "camera_hcenter", "camera_center", "camera_right",
                "camera_top", "camera_vcenter", "camera_bottom",
            ):
                self.layer_buttons_by_command[command].setEnabled(selection_count >= 1)
        finally:
            self._updating = False


def build_inspector_panel(project_path: str = "") -> InspectorPanel:
    return InspectorPanel(project_path)


class DebuggerPanel(QWidget):
    command_requested = Signal(str)
    stop_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8,6,8,6)
        toolbar = QHBoxLayout()
        self.state_label = QLabel("Debugger chưa chạy")
        self.state_label.setObjectName("DebuggerState")
        toolbar.addWidget(self.state_label)
        toolbar.addStretch()
        commands = [
            ("continue","fa5s.play","Tiếp tục"), ("pause","fa5s.pause","Tạm dừng"),
            ("step_over","fa5s.step-forward","Step Over"), ("step_into","fa5s.level-down-alt","Step Into"),
            ("step_out","fa5s.level-up-alt","Step Out"), ("stack","fa5s.layer-group","Call Stack"),
            ("locals","fa5s.list","Locals"), ("threads","fa5s.project-diagram","Threads"),
        ]
        self.buttons: list[QToolButton] = []
        for command, icon_name, tip in commands:
            button = QToolButton(); button.setIcon(icon(icon_name)); button.setToolTip(tip); button.setFixedSize(27,27)
            button.clicked.connect(lambda _checked=False, value=command: self.command_requested.emit(value))
            toolbar.addWidget(button); self.buttons.append(button)
        stop = QToolButton(); stop.setIcon(icon("fa5s.stop","#EF747A")); stop.setToolTip("Dừng Debug"); stop.setFixedSize(27,27); stop.clicked.connect(self.stop_requested.emit)
        toolbar.addWidget(stop); self.buttons.append(stop)
        layout.addLayout(toolbar)
        self.output = QPlainTextEdit(); self.output.setReadOnly(True); self.output.setPlaceholderText("Pipeline VXP không có debugger tích hợp; theo dõi log build/run trong tab Console...")
        layout.addWidget(self.output,1)
        self.set_state("Debugger chưa chạy")

    def append(self, text: str) -> None:
        self.output.moveCursor(self.output.textCursor().MoveOperation.End)
        self.output.insertPlainText(text)
        self.output.verticalScrollBar().setValue(self.output.verticalScrollBar().maximum())

    def set_state(self, state: str) -> None:
        # Nút luôn bật: runner trả lời mọi lệnh bằng giải thích trung thực
        # trong ô output bên dưới thay vì để nút chết không phản hồi.
        self.state_label.setText(state)
        for button in self.buttons:
            button.setEnabled(True)


class ProblemsPanel(QWidget):
    diagnostic_open_requested = Signal(dict)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self); layout.setContentsMargins(8,6,8,6)
        self.summary = QLabel("Không có lỗi biên dịch")
        layout.addWidget(self.summary)
        self.tree = QTreeWidget(); self.tree.setHeaderLabels(["Mức", "Tệp", "Dòng", "Thông báo"]); self.tree.setRootIsDecorated(False)
        self.tree.itemDoubleClicked.connect(self._open_item)
        layout.addWidget(self.tree,1)
        self._diagnostics: list[dict] = []

    def set_diagnostics(self, diagnostics: list[dict]) -> None:
        self._diagnostics = [dict(item) for item in diagnostics]
        self.tree.clear()
        errors = sum(1 for item in diagnostics if str(item.get("severity","")).lower()=="error")
        warnings = sum(1 for item in diagnostics if str(item.get("severity","")).lower()=="warning")
        self.summary.setText(f"{errors} lỗi • {warnings} cảnh báo" if diagnostics else "Không có lỗi biên dịch")
        for diagnostic in diagnostics:
            severity = str(diagnostic.get("severity","error")).title()
            path = Path(str(diagnostic.get("file","")))
            item = QTreeWidgetItem([severity, path.name, str(diagnostic.get("line",1)), str(diagnostic.get("message",""))])
            item.setIcon(0, icon("fa5s.times-circle" if severity.lower()=="error" else "fa5s.exclamation-triangle", "#F0646A" if severity.lower()=="error" else "#E5B84E"))
            item.setToolTip(1, str(path)); item.setData(0, Qt.ItemDataRole.UserRole, dict(diagnostic)); self.tree.addTopLevelItem(item)
        for column in range(4): self.tree.resizeColumnToContents(column)

    def _open_item(self, item: QTreeWidgetItem, _column: int) -> None:
        diagnostic = item.data(0, Qt.ItemDataRole.UserRole)
        if isinstance(diagnostic, dict): self.diagnostic_open_requested.emit(dict(diagnostic))


def build_console_panel(project_name: str = "untitled") -> PanelFrame:
    panel = PanelFrame("Console", show_header=False)
    panel.set_content_margins(0,0,0,0)
    tabs = QTabWidget(); tabs.setDocumentMode(True)

    console_tab = QWidget(); layout = QVBoxLayout(console_tab); layout.setContentsMargins(8,6,8,6)
    filter_line = _search_line("Lọc nhật ký..."); layout.addWidget(filter_line)
    log = QPlainTextEdit(); log.setReadOnly(True)
    append_colored_log(log, f"[Info] Project '{project_name}' loaded successfully.")
    append_colored_log(log, "[Success] Editor, w64devkit, ARM build, VXPEmu và Problems đã sẵn sàng.")
    layout.addWidget(log)
    panel.console_output = log

    problems = ProblemsPanel(); debugger = DebuggerPanel(); output_log = QPlainTextEdit(); output_log.setReadOnly(True)
    vxpemu = VxpEmuPanel()
    tabs.addTab(console_tab, icon("fa5s.terminal"), "Console")
    tabs.addTab(problems, icon("fa5s.exclamation-circle"), "Problems")
    tabs.addTab(debugger, icon("fa5s.bug"), "Debugger")
    tabs.addTab(output_log, icon("fa5s.stream"), "Output")
    tabs.addTab(vxpemu, icon("fa5s.mobile-alt", "#72a8ff"), "VXPEmu")
    panel.console_tabs = tabs; panel.problems_panel = problems; panel.debugger_panel = debugger; panel.output_log = output_log; panel.vxpemu_panel = vxpemu
    panel.add_widget(tabs)
    return panel



IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"}
ASSET_ROLE = int(Qt.ItemDataRole.UserRole)
COMPONENT_ROLE = ASSET_ROLE + 1
BACKGROUND_ROLE = ASSET_ROLE + 2
PERSPECTIVE_ROLE = ASSET_ROLE + 3

PIXEL_BACKGROUND_SPECS = (
    ("Nền thung lũng hoàng hôn · 240×320", "pixel_dusk_valley_240x320.png"),
    ("Nền chiến trường rừng · 320×240", "pixel_forest_battlefield_320x240.png"),
)


def pixel_background_templates() -> list[tuple[str, Path]]:
    """Resolve built-in pixel backgrounds in source and packaged installations."""
    roots = [Path(__file__).resolve().parents[2] / "assets" / "ui" / "backgrounds"]
    try:
        import sample_library
        sample_root = sample_library.ensure_extracted()
        if sample_root is not None:
            roots.append(sample_root / "ui" / "backgrounds")
    except (OSError, zipfile.BadZipFile):
        pass
    resolved: list[tuple[str, Path]] = []
    for label, filename in PIXEL_BACKGROUND_SPECS:
        path = next((root / filename for root in roots if (root / filename).is_file()), None)
        if path is not None:
            resolved.append((label, path))
    return resolved

UI_COMPONENTS = (
    {"kind": "canvas", "label": "Khung trong suốt", "icon": "fa5s.square", "type": "Rectangle2D", "size": [240, 320], "fill": "#00000000", "stroke": "#556B8A80", "ui_role": "Canvas"},
    {"kind": "frame", "label": "Frame UI tùy chỉnh", "icon": "fa5s.object-group", "type": "Rectangle2D", "size": [160, 96], "fill": "#111827B8", "stroke": "#60A5FA", "corner_radius": 8, "ui_role": "Frame"},
    {"kind": "button", "label": "Nút bấm", "icon": "fa5s.stop", "type": "Rectangle2D", "size": [88, 30], "fill": "#2563EB", "stroke": "#93C5FD", "text": "BUTTON", "ui_role": "Button", "input_binding": "OK"},
    {"kind": "label", "label": "Nhãn văn bản", "icon": "fa5s.font", "type": "Text2D", "size": [88, 20], "text": "LABEL", "ui_role": "Label"},
    {"kind": "checkbox", "label": "Hộp kiểm", "icon": "fa5s.check-square", "type": "Rectangle2D", "size": [18, 18], "fill": "#0F172A", "stroke": "#60A5FA", "text": "✓", "ui_role": "CheckBox", "input_binding": "OK"},
    {"kind": "input", "label": "Hộp nhập liệu", "icon": "fa5s.keyboard", "type": "Rectangle2D", "size": [112, 28], "fill": "#111827", "stroke": "#64748B", "text": "INPUT", "ui_role": "TextBox"},
    {"kind": "image", "label": "Hình ảnh", "icon": "fa5s.image", "type": "Rectangle2D", "size": [64, 64], "fill": "#162033", "stroke": "#60A5FA", "text": "IMAGE", "ui_role": "Image"},
    {"kind": "progress", "label": "Thanh tiến trình", "icon": "fa5s.minus", "type": "Rectangle2D", "size": [112, 14], "fill": "#2563EB", "stroke": "#93C5FD", "ui_role": "ProgressBar"},
    {"kind": "slider", "label": "Thanh trượt", "icon": "fa5s.sliders-h", "type": "Rectangle2D", "size": [112, 10], "fill": "#475569", "stroke": "#CBD5E1", "ui_role": "Slider", "input_binding": "LEFT_RIGHT"},
    {"kind": "switch", "label": "Công tắc", "icon": "fa5s.toggle-on", "type": "Rectangle2D", "size": [44, 22], "fill": "#22C55E", "stroke": "#BBF7D0", "ui_role": "Switch", "input_binding": "OK"},
)

FRAME_PERSPECTIVES = (
    {
        "kind": "side_scroller", "label": "Góc nhìn ngang", "icon": "fa5s.arrows-alt-h",
        "camera_angle": 0, "projection": "side", "movement_axes": "horizontal+jump",
        "description": "Side-Scroller / Platformer · di chuyển trái/phải, nhảy và rơi.",
    },
    {
        "kind": "top_down", "label": "Từ trên xuống", "icon": "fa5s.compass",
        "camera_angle": 90, "projection": "top_down", "movement_axes": "four_way",
        "description": "Top-Down 90° · di chuyển tự do theo bốn hướng.",
    },
    {
        "kind": "three_quarter", "label": "Góc nhìn 3/4", "icon": "fa5s.street-view",
        "camera_angle": 55, "projection": "top_down_3_4", "movement_axes": "four_way",
        "description": "Top-Down Perspective 45–60° · phù hợp RPG 2D kiểu handheld.",
    },
    {
        "kind": "isometric", "label": "Giả 3D Isometric", "icon": "fa5s.cubes",
        "camera_angle": 45, "projection": "isometric_2_1", "movement_axes": "isometric_four_way",
        "description": "Isometric / 2.5D · lưới chéo 2:1 tạo cảm giác chiều sâu.",
    },
)


class _TitleSetList(QListWidget):
    """Thumbnail palette that drags scene-ready assets into Frame Preview."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setViewMode(QListView.ViewMode.IconMode)
        self.setFlow(QListView.Flow.LeftToRight)
        self.setResizeMode(QListView.ResizeMode.Adjust)
        self.setMovement(QListView.Movement.Static)
        self.setIconSize(QSize(58, 58))
        self.setGridSize(QSize(82, 88))
        self.setSpacing(4)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setDragEnabled(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.DragOnly)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)

    def startDrag(self, supported_actions) -> None:  # noqa: N802 - Qt API
        item = self.currentItem()
        if item is None:
            return
        mime = QMimeData()
        perspective = item.data(PERSPECTIVE_ROLE)
        component = item.data(COMPONENT_ROLE)
        if isinstance(perspective, dict):
            mime.setData(
                "application/x-vxp-frame-perspective",
                json.dumps(perspective, ensure_ascii=False).encode("utf-8"),
            )
        elif isinstance(component, dict):
            mime.setData(
                "application/x-vxp-component",
                json.dumps(component, ensure_ascii=False).encode("utf-8"),
            )
        else:
            path = str(item.data(ASSET_ROLE) or "")
            if not path:
                return
            mime.setUrls([QUrl.fromLocalFile(path)])
            mime.setData("application/x-vxp-asset", path.encode("utf-8"))
            if bool(item.data(BACKGROUND_ROLE)):
                mime.setData("application/x-vxp-background", b"1")
        drag = QDrag(self)
        drag.setMimeData(mime)
        drag.setPixmap(item.icon().pixmap(48, 48))
        drag.exec(Qt.DropAction.CopyAction, Qt.DropAction.CopyAction)


class TitleSetLibraryPanel(PanelFrame):
    """Bottom-right TitleSet/template library shown in the red-marked area."""

    insert_asset_requested = Signal(str)
    insert_component_requested = Signal(dict)
    insert_background_requested = Signal(str)
    insert_perspective_requested = Signal(dict)
    replace_asset_requested = Signal(str)
    edit_asset_requested = Signal(str, str)
    insert_control_kit_requested = Signal()
    assets_imported = Signal(list)
    terrain_brush_requested = Signal(str, int, bool, bool)
    terrain_paint_stopped = Signal()

    def __init__(self, project_path: str, parent=None) -> None:
        super().__init__("TitleSet", show_header=False, parent=parent)
        self.project_root = Path(project_path).resolve()
        self.set_content_margins(6, 6, 6, 6)

        top = QWidget()
        top_layout = QHBoxLayout(top)
        top_layout.setContentsMargins(0, 0, 0, 4)
        top_layout.setSpacing(5)
        title = QLabel("TitleSet / Component Library")
        title.setObjectName("PanelMiniTitle")
        top_layout.addWidget(title, 1)
        import_button = QToolButton()
        import_button.setIcon(icon("fa5s.file-import"))
        import_button.setToolTip("Import bằng cửa sổ mặc định của Windows")
        import_button.setFixedSize(28, 26)
        import_button.clicked.connect(self._import_native_assets)
        top_layout.addWidget(import_button)
        kit = QToolButton()
        kit.setIcon(icon("fa5s.gamepad"))
        kit.setToolTip("Thêm bộ mẫu gồm nhân vật, hiệu ứng, joystick, RUN và JUMP vào màn hiện tại")
        kit.setFixedSize(28, 26)
        kit.clicked.connect(self.insert_control_kit_requested.emit)
        top_layout.addWidget(kit)
        refresh = QToolButton()
        refresh.setIcon(icon("fa5s.sync-alt"))
        refresh.setToolTip("Làm mới TitleSet")
        refresh.setFixedSize(28, 26)
        refresh.clicked.connect(self.refresh)
        top_layout.addWidget(refresh)
        self.add_widget(top)

        painter = QWidget()
        painter_layout = QHBoxLayout(painter)
        painter_layout.setContentsMargins(0, 0, 0, 5)
        painter_layout.setSpacing(4)
        self.terrain_paint_button = QToolButton()
        self.terrain_paint_button.setIcon(icon("fa5s.paint-brush"))
        self.terrain_paint_button.setText("Paint Tile")
        self.terrain_paint_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.terrain_paint_button.setCheckable(True)
        self.terrain_paint_button.setToolTip("Vẽ tile đang chọn trực tiếp trong Camera2D")
        self.terrain_paint_button.toggled.connect(self._toggle_terrain_paint)
        painter_layout.addWidget(self.terrain_paint_button)
        self.terrain_erase_button = QToolButton()
        self.terrain_erase_button.setIcon(icon("fa5s.eraser"))
        self.terrain_erase_button.setCheckable(True)
        self.terrain_erase_button.setToolTip("Xóa tile bằng cọ trên Frame Preview")
        self.terrain_erase_button.toggled.connect(self._toggle_terrain_erase)
        painter_layout.addWidget(self.terrain_erase_button)
        self.terrain_grid = QSpinBox()
        self.terrain_grid.setRange(4, 256)
        self.terrain_grid.setValue(16)
        self.terrain_grid.setSuffix(" px")
        self.terrain_grid.setToolTip("Kích thước ô Terrain Painting")
        self.terrain_grid.valueChanged.connect(self._terrain_settings_changed)
        painter_layout.addWidget(self.terrain_grid)
        self.terrain_rule = QCheckBox("Rule")
        self.terrain_rule.setChecked(True)
        self.terrain_rule.setToolTip("Tự tính cạnh N/E/S/W và chọn biến thể __rule_0..15 nếu có")
        self.terrain_rule.toggled.connect(self._terrain_settings_changed)
        painter_layout.addWidget(self.terrain_rule)
        painter_layout.addStretch()
        self.add_widget(painter)

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.lists: dict[str, _TitleSetList] = {}
        for key, label, icon_name in (
            ("components", "UI", "fa5s.shapes"),
            ("perspectives", "Frame Perspective", "fa5s.drafting-compass"),
            ("all", "Assets", "fa5s.images"),
            ("characters", "Nhân vật", "fa5s.user"),
            ("tiles", "Tiles", "fa5s.border-all"),
        ):
            widget = _TitleSetList()
            widget.itemDoubleClicked.connect(lambda item, _column=0: self._insert_item(item))
            widget.customContextMenuRequested.connect(
                lambda pos, source=widget: self._context_menu(source, pos)
            )
            widget.itemSelectionChanged.connect(
                lambda source=widget: self._terrain_selection_changed(source)
            )
            self.lists[key] = widget
            self.tabs.addTab(widget, icon(icon_name), label)
        self.sample_list = self.lists["all"]
        self.tabs.currentChanged.connect(self._library_tab_changed)
        self.add_widget(self.tabs)

        footer = QWidget()
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(0, 4, 0, 0)
        self.info = QLabel("Kéo UI hoặc asset vào Camera2D; mọi thay đổi tự lưu vào .dtfe.")
        self.info.setWordWrap(True)
        self.info.setObjectName("DialogHint")
        footer_layout.addWidget(self.info, 1)
        self.add_widget(footer)
        self._tip_timer = QTimer(self)
        self._tip_timer.setSingleShot(True)
        self._tip_timer.timeout.connect(self.info.hide)
        self.refresh()

    def _show_tip(self, message: str, timeout_ms: int = 4800) -> None:
        """Show a contextual footer hint, then free the library's vertical space."""
        self._tip_timer.stop()
        self.info.setText(message)
        self.info.show()
        if timeout_ms > 0:
            self._tip_timer.start(timeout_ms)

    def show_current_tip(self, timeout_ms: int = 7000) -> None:
        tips = {
            "components": "UI: kéo nút, nhãn hoặc nền pixel vào Camera2D; .dtfe tự cập nhật.",
            "perspectives": "Frame Perspective: kéo góc nhìn vào Camera2D để tự khít 240×320 hoặc 320×240.",
            "all": "Assets: kéo ảnh vào Camera2D; dùng Inspector để nhập chính xác kích thước và vị trí.",
            "characters": "Nhân vật: kéo sprite vào khung; đường dóng xanh/vàng hỗ trợ căn chỉnh.",
            "tiles": "Tiles: chọn tile rồi bật Paint Tile để vẽ trực tiếp trong Camera2D.",
        }
        current = self.tabs.currentWidget()
        key = next((name for name, widget in self.lists.items() if widget is current), "components")
        self._show_tip(tips[key], timeout_ms)

    def _classify_import_destination(self, source: Path) -> Path:
        name = source.stem.lower()
        if any(token in name for token in ("skill", "spell", "attack", "ult", "effect", "fx")):
            return self.project_root / "assets" / "map" / "skill"
        if any(token in name for token in ("tile", "terrain", "grass", "forest", "ground", "water", "rock", "tree")):
            return self.project_root / "assets" / "map" / "tileset" / "imported"
        if any(token in name for token in ("hero", "player", "character", "npc", "enemy", "monster")):
            return self.project_root / "assets" / "scenes" / "characters"
        return self.project_root / "assets" / "map" / "texture" / "controls"

    def _import_native_assets(self) -> None:
        files, _selected_filter = QFileDialog.getOpenFileNames(
            self,
            "Import tài nguyên vào TitleSet",
            str(Path.home()),
            "Ảnh 2D (*.png *.jpg *.jpeg *.webp *.bmp *.gif);;Tất cả tệp (*.*)",
        )
        if not files:
            return
        imported: list[str] = []
        for file_name in files:
            source = Path(file_name)
            if not source.is_file() or source.suffix.lower() not in IMAGE_EXTENSIONS:
                continue
            destination_dir = self._classify_import_destination(source)
            destination_dir.mkdir(parents=True, exist_ok=True)
            destination = unique_destination(destination_dir / source.name)
            try:
                shutil.copy2(source, destination)
            except OSError:
                continue
            imported.append(str(destination))
        if imported:
            self.refresh()
            self.assets_imported.emit(imported)
            self._show_tip(f"Đã import {len(imported)} ảnh bằng cửa sổ Windows và tự phân loại vào TitleSet.", 6500)

    def _candidate_paths(self) -> list[Path]:
        # Asset Editor and older projects may use assets/sprites, assets/temp,
        # assets/ui, assets/map/...; the Component Library must see all of them.
        roots = [self.project_root / "assets"]
        # Mẫu nén của VXPEngine (packaging/vxp_sample_assets.zip) giải nén vào cache.
        try:
            import sample_library
            sample_root = sample_library.ensure_extracted()
            if sample_root is not None:
                roots.append(sample_root)
        except (OSError, zipfile.BadZipFile):
            pass
        result: list[Path] = []
        seen: set[str] = set()
        for root in roots:
            if not root.exists():
                continue
            for path in sorted(root.rglob("*"), key=lambda value: value.name.lower()):
                if not path.is_file() or path.suffix.lower() not in IMAGE_EXTENSIONS:
                    continue
                if path.parent.name.lower() == "backgrounds" and path.name in {
                    filename for _label, filename in PIXEL_BACKGROUND_SPECS
                }:
                    continue  # shown once in the UI tab as a background template
                key = str(path.resolve()).lower()
                if key not in seen:
                    seen.add(key)
                    result.append(path)
        return result

    @staticmethod
    def _asset_categories(path: Path) -> set[str]:
        combined = f"{path.parent.as_posix().lower()}/{path.stem.lower()}"
        categories = {"all"}
        if any(token in combined for token in ("hero", "player", "character", "enemy", "npc", "worm")):
            categories.add("characters")
        if any(token in combined for token in ("tile", "terrain", "grass", "ground", "water", "rock", "tree", "panel")):
            categories.add("tiles")
        return categories

    def refresh(self, select_path: str | Path | None = None) -> None:
        for widget in self.lists.values():
            widget.clear()
        for component in UI_COMPONENTS:
            item = QListWidgetItem(icon(str(component["icon"]), "#8DB7FF"), str(component["label"]))
            item.setData(COMPONENT_ROLE, dict(component))
            item.setToolTip(f"{component['label']} · kéo vào Camera2D để tạo node UI và cập nhật .dtfe")
            self.lists["components"].addItem(item)
        for perspective in FRAME_PERSPECTIVES:
            item = QListWidgetItem(
                icon(str(perspective["icon"]), "#C4A7FF"),
                str(perspective["label"]),
            )
            item.setData(PERSPECTIVE_ROLE, dict(perspective))
            item.setToolTip(
                f"{perspective['label']}\n{perspective['description']}\n"
                "Kéo vào Camera2D để guide tự khít frame và lưu vào .dtfe."
            )
            self.lists["perspectives"].addItem(item)
        backgrounds = pixel_background_templates()
        for label, path in backgrounds:
            pixmap = QPixmap(str(path))
            if pixmap.isNull():
                continue
            thumb = pixmap.scaled(
                58, 58, Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.FastTransformation,
            )
            item = QListWidgetItem(QIcon(thumb), label)
            item.setData(ASSET_ROLE, str(path))
            item.setData(BACKGROUND_ROLE, True)
            item.setToolTip(f"{label}\nKéo vào Camera2D để đặt làm nền pixel và tự cập nhật .dtfe.")
            self.lists["components"].addItem(item)
        selected_key = ""
        if select_path:
            try:
                selected_key = str(Path(select_path).resolve()).lower()
            except OSError:
                selected_key = ""
        for path in self._candidate_paths():
            pixmap = QPixmap(str(path))
            if pixmap.isNull():
                continue
            thumb = pixmap.scaled(58, 58, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.FastTransformation)
            for category in self._asset_categories(path):
                widget = self.lists[category]
                item = QListWidgetItem(QIcon(thumb), path.stem)
                item.setData(ASSET_ROLE, str(path))
                try:
                    origin = f"{path.relative_to(self.project_root)}"
                except ValueError:
                    origin = "Thư viện mẫu VXPEngine (gói nén)"
                item.setToolTip(f"{origin}\nKéo vào Camera2D để tạo Sprite2D và cập nhật .dtfe.")
                widget.addItem(item)
                if selected_key and str(path.resolve()).lower() == selected_key and category == "all":
                    widget.setCurrentItem(item)
                    widget.scrollToItem(item)
        count = self.sample_list.count()
        self._show_tip(
            f"{len(UI_COMPONENTS)} UI · {len(FRAME_PERSPECTIVES)} góc nhìn · "
            f"{len(backgrounds)} nền pixel · {count} asset "
            "• kéo vào Camera2D; .dtfe tự cập nhật.",
            4800,
        )
        if selected_key:
            self.tabs.setCurrentWidget(self.sample_list)
        self._update_paint_controls()

    def _insert_item(self, item: QListWidgetItem) -> None:
        perspective = item.data(PERSPECTIVE_ROLE)
        if isinstance(perspective, dict):
            self.insert_perspective_requested.emit(dict(perspective))
            return
        component = item.data(COMPONENT_ROLE)
        if isinstance(component, dict):
            self.insert_component_requested.emit(dict(component))
            return
        path = str(item.data(ASSET_ROLE) or "")
        if path:
            if bool(item.data(BACKGROUND_ROLE)):
                self.insert_background_requested.emit(path)
            else:
                self.insert_asset_requested.emit(path)

    def _selected_material_path(self) -> str:
        current = self.tabs.currentWidget()
        if isinstance(current, _TitleSetList) and current.currentItem() is not None:
            item = current.currentItem()
            if not bool(item.data(BACKGROUND_ROLE)):
                return str(item.data(ASSET_ROLE) or "")
        return ""

    def _library_tab_changed(self, _index: int) -> None:
        self._update_paint_controls()
        self.show_current_tip()

    def _update_paint_controls(self) -> None:
        has_material = bool(self._selected_material_path())
        self.terrain_paint_button.setEnabled(has_material)
        self.terrain_rule.setEnabled(has_material)
        if not has_material and self.terrain_paint_button.isChecked():
            self.terrain_paint_button.setChecked(False)

    def _emit_terrain_brush(self, *, erase: bool = False, path: str | None = None) -> bool:
        material = str(path or self._selected_material_path())
        if not material and not erase:
            self._show_tip("Hãy chọn một texture/tile trước khi bật Terrain Paint.", 6000)
            return False
        self.terrain_brush_requested.emit(
            material,
            self.terrain_grid.value(),
            self.terrain_rule.isChecked(),
            erase,
        )
        if erase:
            self._show_tip("Terrain Eraser đang bật · kéo chuột trên Frame Preview để xóa tile.", 6000)
        else:
            self._show_tip(f"Terrain Paint: {Path(material).stem} · kéo chuột để quét, chuột phải để xóa.", 6000)
        return True

    def _toggle_terrain_paint(self, checked: bool) -> None:
        if checked:
            self.terrain_erase_button.blockSignals(True)
            self.terrain_erase_button.setChecked(False)
            self.terrain_erase_button.blockSignals(False)
            if not self._emit_terrain_brush():
                self.terrain_paint_button.blockSignals(True)
                self.terrain_paint_button.setChecked(False)
                self.terrain_paint_button.blockSignals(False)
        elif not self.terrain_erase_button.isChecked():
            self.terrain_paint_stopped.emit()

    def _toggle_terrain_erase(self, checked: bool) -> None:
        if checked:
            self.terrain_paint_button.blockSignals(True)
            self.terrain_paint_button.setChecked(False)
            self.terrain_paint_button.blockSignals(False)
            self._emit_terrain_brush(erase=True)
        elif not self.terrain_paint_button.isChecked():
            self.terrain_paint_stopped.emit()

    def _terrain_settings_changed(self, _value=None) -> None:
        if self.terrain_paint_button.isChecked():
            self._emit_terrain_brush()
        elif self.terrain_erase_button.isChecked():
            self._emit_terrain_brush(erase=True)

    def _terrain_selection_changed(self, source: _TitleSetList) -> None:
        self._update_paint_controls()
        if source is self.tabs.currentWidget() and self.terrain_paint_button.isChecked():
            self._emit_terrain_brush()

    def _activate_terrain_material(self, path: str) -> None:
        self.terrain_paint_button.blockSignals(True)
        self.terrain_paint_button.setChecked(True)
        self.terrain_paint_button.blockSignals(False)
        self.terrain_erase_button.blockSignals(True)
        self.terrain_erase_button.setChecked(False)
        self.terrain_erase_button.blockSignals(False)
        self._emit_terrain_brush(path=path)

    def _context_menu(self, source: _TitleSetList, position: QPoint) -> None:
        item = source.itemAt(position)
        if item is None:
            return
        perspective = item.data(PERSPECTIVE_ROLE)
        component = item.data(COMPONENT_ROLE)
        path = str(item.data(ASSET_ROLE) or "")
        menu = QMenu(self)
        if isinstance(perspective, dict):
            apply_perspective = QAction(icon("fa5s.expand"), "Áp dụng và khít Camera2D", menu)
            apply_perspective.triggered.connect(
                lambda: self.insert_perspective_requested.emit(dict(perspective))
            )
            menu.addAction(apply_perspective)
            menu.exec(source.viewport().mapToGlobal(position))
            return
        if isinstance(component, dict):
            insert_component = QAction(icon("fa5s.plus-square"), "Thêm UI vào Camera2D", menu)
            insert_component.triggered.connect(lambda: self.insert_component_requested.emit(dict(component)))
            menu.addAction(insert_component)
            menu.exec(source.viewport().mapToGlobal(position))
            return
        if not path:
            return
        is_background = bool(item.data(BACKGROUND_ROLE))
        insert_label = "Đặt làm nền Camera2D" if is_background else "Thêm vào Frame Preview"
        insert_action = QAction(icon("fa5s.plus-square"), insert_label, menu)
        replace_action = QAction(icon("fa5s.exchange-alt"), "Thay hình thành phần đang chọn", menu)
        edit_action = QAction(icon("fa5s.magic"), "Mở trong Editor Assets", menu)
        paint_action = QAction(icon("fa5s.paint-brush"), "Dùng làm Terrain Brush", menu)
        if is_background:
            insert_action.triggered.connect(lambda: self.insert_background_requested.emit(path))
        else:
            insert_action.triggered.connect(lambda: self.insert_asset_requested.emit(path))
        replace_action.triggered.connect(lambda: self.replace_asset_requested.emit(path))
        edit_action.triggered.connect(lambda: self.edit_asset_requested.emit(path, self._relative_parent(Path(path))))
        paint_action.triggered.connect(lambda: self._activate_terrain_material(path))
        menu.addAction(insert_action)
        if not is_background:
            menu.addAction(replace_action)
            menu.addAction(paint_action)
        menu.addSeparator()
        menu.addAction(edit_action)
        menu.exec(source.viewport().mapToGlobal(position))

    def _relative_parent(self, path: Path) -> str:
        try:
            return path.parent.resolve().relative_to(self.project_root).as_posix()
        except (OSError, ValueError):
            return "assets/map/tileset"


def build_tilemap_panel(project_path: str = "") -> TitleSetLibraryPanel:
    return TitleSetLibraryPanel(project_path)
