"""Integrated VXPEngine Asset Editor.

The editor is intentionally project-aware: exported images are written only to
the fixed VXP project ``assets`` tree. PNG files remain normal images while
animation descriptors are stored under ``assets/scenes``.  It
supports transparent pixel drawing, grid/tileset slicing, collision rectangles,
texture cleanup, simple 2D style filters, compositing and undo/redo.
"""
from __future__ import annotations

import json
import copy
import math
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QEvent, QPoint, QPointF, QRect, QRectF, QSize, Qt, Signal, QTimer
from PySide6.QtGui import (
    QAction,
    QColor,
    QColorConstants,
    QCursor,
    QIcon,
    QImage,
    QKeySequence,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QShowEvent,
    QTransform,
    QWheelEvent,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListView,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QPushButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    QSplitter,
    QTabWidget,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .animation_player import AnimationPlayerWindow, AnimationPreviewFrame
from .vpe_pixel_panel import VpePixelPanel
from .custom_dialog import ColorPickerDialog, CustomDialog, NoticeDialog
from .icons import icon
from smart_slice import detect_content_regions
from game_art_styles import ART_STYLE_PROFILES, GAME_ART_STYLES, apply_game_palette
from legacy_asset_import import (
    LEGACY_CATEGORIES,
    import_legacy_res,
    load_legacy_catalog,
    resolve_legacy_preview,
    update_legacy_asset_metadata,
)


IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif", ".svg"}
ANIMATION_SUFFIX = ".ani..dtfe"
LEGACY_ANIMATION_SUFFIX = ".ani.dtfe"
LEGACY_CATEGORY_LABELS = {
    "background": "Background",
    "character": "Character",
    "enemy": "Enemy",
    "boss": "Boss",
    "effect": "Effect",
    "item": "Item",
    "ui": "UI",
    "animation": "Animation",
    "audio": "Audio",
    "map": "Map",
    "misc": "Misc",
}
LEGACY_CATEGORY_ICONS = {
    "background": "fa5s.image",
    "character": "fa5s.user",
    "enemy": "fa5s.skull",
    "boss": "fa5s.crown",
    "effect": "fa5s.magic",
    "item": "fa5s.gem",
    "ui": "fa5s.window-maximize",
    "animation": "fa5s.film",
    "audio": "fa5s.music",
    "map": "fa5s.map",
    "misc": "fa5s.file",
}

IMAGE_DESTINATIONS = (
    ("Scene / nhân vật chuyển động", "assets/scenes"),
    ("Map / ảnh nền", "assets/map/background"),
    ("Map / skill", "assets/map/skill"),
    ("Map / texture", "assets/map/texture"),
    ("Map / tileset", "assets/map/tileset"),
    ("Biểu tượng game / ứng dụng", "assets/app-icon"),
)


class _AssetEditorTitleBar(QWidget):
    def __init__(self, owner: "AssetEditorDialog") -> None:
        super().__init__(owner)
        self.owner = owner

    def mousePressEvent(self, event: QMouseEvent) -> None:
        self.owner._title_mouse_press(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        self.owner._title_mouse_move(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self.owner._title_mouse_release(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.owner.toggle_maximize_restore()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)


class _HiddenHorizontalScrollArea(QScrollArea):
    """Compact chip rail with touchpad/wheel scrolling and no visible bars."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setFixedHeight(42)

    def wheelEvent(self, event: QWheelEvent) -> None:
        delta = event.angleDelta().x() or event.angleDelta().y()
        bar = self.horizontalScrollBar()
        bar.setValue(bar.value() - delta)
        event.accept()


class _HorizontalChipRail(QWidget):
    """A hidden-scroll chip row with compact, discoverable arrow controls."""

    def __init__(self, content: QWidget, parent=None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(3)

        self.left_button = self._arrow_button(Qt.ArrowType.LeftArrow, "Cuộn sang trái")
        self.scroll = _HiddenHorizontalScrollArea()
        self.right_button = self._arrow_button(Qt.ArrowType.RightArrow, "Cuộn sang phải")
        self.scroll.setWidget(content)
        layout.addWidget(self.left_button)
        layout.addWidget(self.scroll, 1)
        layout.addWidget(self.right_button)
        self.setFixedHeight(42)

        bar = self.scroll.horizontalScrollBar()
        bar.rangeChanged.connect(lambda _minimum, _maximum: self._update_arrows())
        bar.valueChanged.connect(lambda _value: self._update_arrows())
        self.left_button.clicked.connect(lambda: self._scroll_page(-1))
        self.right_button.clicked.connect(lambda: self._scroll_page(1))
        QTimer.singleShot(0, self._update_arrows)

    @staticmethod
    def _arrow_button(arrow: Qt.ArrowType, tooltip: str) -> QToolButton:
        button = QToolButton()
        button.setObjectName("CompactScrollArrow")
        button.setArrowType(arrow)
        button.setAutoRepeat(True)
        button.setAutoRepeatDelay(260)
        button.setAutoRepeatInterval(70)
        button.setToolTip(tooltip)
        button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        return button

    def _scroll_page(self, direction: int) -> None:
        bar = self.scroll.horizontalScrollBar()
        step = max(64, int(bar.pageStep() * 0.72))
        bar.setValue(bar.value() + direction * step)

    def _update_arrows(self) -> None:
        bar = self.scroll.horizontalScrollBar()
        has_overflow = bar.maximum() > bar.minimum()
        self.left_button.setVisible(has_overflow and bar.value() > bar.minimum())
        self.right_button.setVisible(has_overflow and bar.value() < bar.maximum())


@dataclass(slots=True)
class FrameRecord:
    name: str
    rect: QRect
    duration_ms: int = 100


@dataclass(slots=True)
class CollisionRecord:
    name: str
    rect: QRect
    kind: str = "solid"


@dataclass(slots=True)
class SceneFrameRecord:
    """A full cel/scene captured from the drawing canvas for timeline animation."""

    name: str
    image: QImage
    duration_ms: int = 100


@dataclass(slots=True)
class EditorSnapshot:
    image: QImage
    frames: list[FrameRecord]
    collisions: list[CollisionRecord]
    selection: QRect
    scene_frames: list[SceneFrameRecord]
    selected_scene: int
    player_settings: dict
    fps: int
    loop: bool
    write_animation: bool


class NewCanvasDialog(CustomDialog):
    """Small preset dialog used by the large Asset Editor modal."""

    PRESETS = {
        "Nhân vật / Sprite 32 px": (128, 128, 32, 32),
        "RTS Isometric / Unit 32 px": (32, 40, 8, 8),
        "RTS Isometric / Building 64 px": (64, 64, 8, 8),
        "Background MRE ngang 320×240": (320, 240, 16, 16),
        "Background MRE dọc 240×320": (240, 320, 16, 16),
        "Tileset / Map 16 px": (256, 256, 16, 16),
        "Tileset / Map 32 px": (512, 512, 32, 32),
        "UI / HUD": (512, 256, 8, 8),
        "Nguyên liệu / Material": (256, 256, 16, 16),
        "Tùy chỉnh": (256, 256, 16, 16),
    }

    def __init__(self, parent=None) -> None:
        super().__init__("Tạo tài nguyên 2D trống", parent=parent, width=520)
        form_host = QWidget()
        form = QFormLayout(form_host)
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(10)

        self.preset = QComboBox()
        self.preset.addItems(self.PRESETS.keys())
        self.width_spin = QSpinBox(); self.width_spin.setRange(1, 8192)
        self.height_spin = QSpinBox(); self.height_spin.setRange(1, 8192)
        self.tile_w_spin = QSpinBox(); self.tile_w_spin.setRange(1, 1024)
        self.tile_h_spin = QSpinBox(); self.tile_h_spin.setRange(1, 1024)
        self.transparent = QCheckBox("Nền trong suốt")
        self.transparent.setChecked(True)

        form.addRow("Mẫu", self.preset)
        form.addRow("Chiều rộng", self.width_spin)
        form.addRow("Chiều cao", self.height_spin)
        form.addRow("Ô lưới rộng", self.tile_w_spin)
        form.addRow("Ô lưới cao", self.tile_h_spin)
        form.addRow("", self.transparent)
        self.add_body_widget(form_host)

        note = QLabel(
            "Canvas được tạo trong bộ nhớ. Chỉ khi nhấn “Lưu & áp dụng”, VXPEngine mới ghi PNG và metadata vào codebase."
        )
        note.setWordWrap(True)
        note.setObjectName("DialogDescription")
        self.add_body_widget(note)

        cancel = self.add_footer_button("Hủy", ghost=True, icon_name="fa5s.times")
        create = self.add_footer_button("Tạo canvas", accent=True, icon_name="fa5s.plus")
        cancel.clicked.connect(self.reject)
        create.clicked.connect(self.accept)
        self.preset.currentTextChanged.connect(self._apply_preset)
        self._apply_preset(self.preset.currentText())

    def _apply_preset(self, text: str) -> None:
        width, height, tile_w, tile_h = self.PRESETS.get(text, self.PRESETS["Tùy chỉnh"])
        self.width_spin.setValue(width)
        self.height_spin.setValue(height)
        self.tile_w_spin.setValue(tile_w)
        self.tile_h_spin.setValue(tile_h)


class AssetCanvas(QWidget):
    """QImage-backed 2D canvas with pixel tools, grids and collision overlays."""

    edit_started = Signal()
    image_changed = Signal()
    color_picked = Signal(QColor)
    cursor_changed = Signal(int, int)
    collision_added = Signal(QRect)
    selection_changed = Signal(QRect)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("AssetCanvas")
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMinimumSize(260, 220)

        self.image = QImage(256, 256, QImage.Format.Format_RGBA8888)
        self.image.fill(Qt.GlobalColor.transparent)
        self.zoom = 2.0
        self.pan = QPointF(0.0, 0.0)
        self.tool = "pencil"
        self.brush_color = QColor("#ff8a3d")
        self.brush_size = 1
        self.pixel_color_depth = 32
        self.grid_visible = True
        self.grid_width = 16
        self.grid_height = 16
        self.onion_image = QImage()
        self.onion_opacity = 0.28
        self.frames: list[FrameRecord] = []
        self.collisions: list[CollisionRecord] = []
        self.selected_frame = -1
        self.selected_collision = -1
        self.selection = QRect()
        self._temp_rect = QRect()
        self._drawing = False
        self._panning = False
        self._last_pixel = QPoint(-1, -1)
        self._shape_points: list[QPoint] = []
        self._drag_origin_widget = QPoint()
        self._pan_origin = QPointF()
        self._checker_a = QColor("#1d222c")
        self._checker_b = QColor("#262c38")

    def set_image(self, image: QImage) -> None:
        converted = image.convertToFormat(QImage.Format.Format_RGBA8888)
        self.image = converted.copy()
        self.frames.clear()
        self.collisions.clear()
        self.selection = QRect()
        self.fit_to_view()
        self.image_changed.emit()
        self.update()

    def new_image(self, width: int, height: int, transparent: bool = True) -> None:
        image = QImage(width, height, QImage.Format.Format_RGBA8888)
        image.fill(Qt.GlobalColor.transparent if transparent else QColor("#ffffff"))
        self.set_image(image)

    def set_tool(self, tool: str) -> None:
        self.tool = tool
        cursors = {
            "pencil": Qt.CursorShape.CrossCursor,
            "eraser": Qt.CursorShape.CrossCursor,
            "fill": Qt.CursorShape.PointingHandCursor,
            "picker": Qt.CursorShape.CrossCursor,
            "select": Qt.CursorShape.CrossCursor,
            "collision": Qt.CursorShape.CrossCursor,
            "pan": Qt.CursorShape.OpenHandCursor,
            "ruler": Qt.CursorShape.CrossCursor,
            "free_frame": Qt.CursorShape.CrossCursor,
        }
        cursor = Qt.CursorShape.CrossCursor if tool.startswith("shape_") else cursors.get(tool, Qt.CursorShape.ArrowCursor)
        self.setCursor(QCursor(cursor))

    def set_zoom(self, zoom: float) -> None:
        self.zoom = max(0.125, min(48.0, float(zoom)))
        self.update()

    def set_pixel_depth(self, bits: int) -> None:
        """Select color precision used by the pixel pencil and flood fill.

        8-bit uses RGB332 (256 colors), 16-bit uses RGB565 and 32-bit keeps
        the full ARGB8888 value.  This gives the submenu a real drawing effect
        instead of being only a visual preset.
        """
        self.pixel_color_depth = bits if bits in {8, 16, 32} else 32

    def quantize_color(self, color: QColor) -> QColor:
        if self.pixel_color_depth == 8:
            r = round(color.red() * 7 / 255) * 255 // 7
            g = round(color.green() * 7 / 255) * 255 // 7
            b = round(color.blue() * 3 / 255) * 255 // 3
            return QColor(r, g, b, color.alpha())
        if self.pixel_color_depth == 16:
            r = round(color.red() * 31 / 255) * 255 // 31
            g = round(color.green() * 63 / 255) * 255 // 63
            b = round(color.blue() * 31 / 255) * 255 // 31
            return QColor(r, g, b, color.alpha())
        return QColor(color)

    def fit_to_view(self) -> None:
        if self.image.isNull() or self.width() <= 0 or self.height() <= 0:
            return
        available_w = max(1, self.width() - 80)
        available_h = max(1, self.height() - 80)
        fit = min(available_w / self.image.width(), available_h / self.image.height())
        self.zoom = max(0.125, min(16.0, fit))
        self.pan = QPointF(0.0, 0.0)
        self.update()

    def image_display_rect(self) -> QRectF:
        width = self.image.width() * self.zoom
        height = self.image.height() * self.zoom
        center = QPointF(self.width() / 2.0, self.height() / 2.0) + self.pan
        return QRectF(center.x() - width / 2.0, center.y() - height / 2.0, width, height)

    def widget_to_image(self, point: QPointF, clamp: bool = False) -> QPoint:
        rect = self.image_display_rect()
        x = math.floor((point.x() - rect.left()) / self.zoom)
        y = math.floor((point.y() - rect.top()) / self.zoom)
        if clamp:
            x = max(0, min(self.image.width() - 1, x))
            y = max(0, min(self.image.height() - 1, y))
        return QPoint(x, y)

    def image_to_widget_rect(self, rect: QRect) -> QRectF:
        display = self.image_display_rect()
        return QRectF(
            display.left() + rect.x() * self.zoom,
            display.top() + rect.y() * self.zoom,
            rect.width() * self.zoom,
            rect.height() * self.zoom,
        )

    def _inside_image(self, point: QPoint) -> bool:
        return 0 <= point.x() < self.image.width() and 0 <= point.y() < self.image.height()

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#0e1118"))
        display = self.image_display_rect()

        painter.save()
        painter.setClipRect(display)
        checker = max(6, int(8 * min(self.zoom, 2.0)))
        left = int(display.left())
        top = int(display.top())
        right = int(display.right()) + checker
        bottom = int(display.bottom()) + checker
        for y in range(top, bottom, checker):
            for x in range(left, right, checker):
                color = self._checker_a if ((x - left) // checker + (y - top) // checker) % 2 == 0 else self._checker_b
                painter.fillRect(x, y, checker, checker, color)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
        if not self.onion_image.isNull():
            painter.save()
            painter.setOpacity(max(0.0, min(0.8, float(self.onion_opacity))))
            onion_rect = QRectF(
                display.center().x() - self.onion_image.width() * self.zoom / 2.0,
                display.center().y() - self.onion_image.height() * self.zoom / 2.0,
                self.onion_image.width() * self.zoom,
                self.onion_image.height() * self.zoom,
            )
            painter.drawImage(onion_rect, self.onion_image)
            painter.restore()
        painter.drawImage(display, self.image)
        painter.restore()

        painter.setPen(QPen(QColor("#59657a"), 1))
        painter.drawRect(display)

        if self.grid_visible:
            self._paint_grid(painter, display)
        self._paint_frames(painter)
        self._paint_collisions(painter)

        if not self.selection.isNull():
            selection_rect = self.image_to_widget_rect(self.selection)
            pen = QPen(QColor("#f3c969"), 1, Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.setBrush(QColor(243, 201, 105, 24))
            painter.drawRect(selection_rect)

        if not self._temp_rect.isNull():
            if self.tool == "ruler" or self.tool.startswith("shape_"):
                self._paint_frame_preview(painter)
            else:
                temp = self.image_to_widget_rect(self._temp_rect)
                color = QColor("#ff6f61") if self.tool == "collision" else QColor("#f3c969")
                painter.setPen(QPen(color, 2, Qt.PenStyle.DashLine))
                painter.setBrush(QColor(color.red(), color.green(), color.blue(), 28))
                painter.drawRect(temp)
        elif self.tool == "free_frame" and len(self._shape_points) > 1:
            self._paint_frame_preview(painter)

        painter.setPen(QColor("#8290a7"))
        painter.drawText(12, 22, f"{self.image.width()} × {self.image.height()} px   •   {self.zoom * 100:.0f}%")

    def _image_path_to_widget(self, path: QPainterPath) -> QPainterPath:
        display = self.image_display_rect()
        transform = QTransform()
        transform.translate(display.left(), display.top())
        transform.scale(self.zoom, self.zoom)
        return transform.map(path)

    def _paint_frame_preview(self, painter: QPainter) -> None:
        if self.tool == "free_frame":
            path = self._free_frame_path(self._shape_points, close=False)
            current = self._shape_points[-1]
        else:
            start = self._last_pixel
            current = self._shape_points[-1] if self.tool == "ruler" and self._shape_points else self._temp_rect.bottomRight()
            path = self._frame_shape_path(self.tool, start, current)
        display = self.image_display_rect()
        current_x = display.left() + current.x() * self.zoom
        current_y = display.top() + current.y() * self.zoom
        painter.save(); painter.setClipRect(display)
        painter.setPen(QPen(QColor(75, 167, 255, 150), 1, Qt.PenStyle.DashLine))
        painter.drawLine(QPointF(current_x, display.top()), QPointF(current_x, display.bottom()))
        painter.setPen(QPen(QColor(246, 200, 72, 150), 1, Qt.PenStyle.DashLine))
        painter.drawLine(QPointF(display.left(), current_y), QPointF(display.right(), current_y))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor("#F3C969"), 2, Qt.PenStyle.DashLine))
        painter.drawPath(self._image_path_to_widget(path))
        painter.restore()
        if self.tool != "free_frame":
            width = abs(current.x() - self._last_pixel.x()) + 1
            height = abs(current.y() - self._last_pixel.y()) + 1
            painter.setPen(QColor("#F7D978"))
            painter.drawText(int(current_x + 8), int(current_y - 8), f"{width} × {height} px")

    def _paint_grid(self, painter: QPainter, display: QRectF) -> None:
        if self.grid_width <= 0 or self.grid_height <= 0:
            return
        if self.grid_width * self.zoom < 5 or self.grid_height * self.zoom < 5:
            return
        painter.save()
        painter.setClipRect(display)
        painter.setPen(QPen(QColor(94, 128, 174, 100), 1))
        x = 0
        while x <= self.image.width():
            px = display.left() + x * self.zoom
            painter.drawLine(QPointF(px, display.top()), QPointF(px, display.bottom()))
            x += self.grid_width
        y = 0
        while y <= self.image.height():
            py = display.top() + y * self.zoom
            painter.drawLine(QPointF(display.left(), py), QPointF(display.right(), py))
            y += self.grid_height
        painter.restore()

    def _paint_frames(self, painter: QPainter) -> None:
        for index, frame in enumerate(self.frames):
            rect = self.image_to_widget_rect(frame.rect)
            selected = index == self.selected_frame
            color = QColor("#56a1ff") if selected else QColor(86, 161, 255, 150)
            painter.setPen(QPen(color, 2 if selected else 1))
            painter.setBrush(QColor(86, 161, 255, 22 if selected else 10))
            painter.drawRect(rect)
            if self.zoom >= 1.0:
                painter.drawText(rect.adjusted(3, 3, -3, -3), Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft, str(index + 1))

    def _paint_collisions(self, painter: QPainter) -> None:
        colors = {
            "solid": QColor("#55d98b"),
            "trigger": QColor("#f2c94c"),
            "hurtbox": QColor("#ff6b72"),
            "hitbox": QColor("#bb86fc"),
        }
        for index, collision in enumerate(self.collisions):
            rect = self.image_to_widget_rect(collision.rect)
            color = colors.get(collision.kind, QColor("#55d98b"))
            painter.setPen(QPen(color, 2 if index == self.selected_collision else 1, Qt.PenStyle.DashLine))
            painter.setBrush(QColor(color.red(), color.green(), color.blue(), 38))
            painter.drawRect(rect)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.MiddleButton or self.tool == "pan":
            self._panning = True
            self._drag_origin_widget = event.position().toPoint()
            self._pan_origin = QPointF(self.pan)
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return
        if event.button() != Qt.MouseButton.LeftButton:
            return super().mousePressEvent(event)

        pixel = self.widget_to_image(event.position())
        if not self._inside_image(pixel):
            return
        self.setFocus()
        self._drawing = True
        self._last_pixel = pixel

        if self.tool in {"pencil", "eraser"}:
            self.edit_started.emit()
            self._draw_segment(pixel, pixel)
        elif self.tool == "fill":
            self.edit_started.emit()
            self._flood_fill(pixel)
            self._drawing = False
        elif self.tool == "picker":
            self.color_picked.emit(self.image.pixelColor(pixel))
            self._drawing = False
        elif self.tool in {"select", "collision", "ruler"} or self.tool.startswith("shape_"):
            self._temp_rect = QRect(pixel, QSize(1, 1))
            if self.tool == "ruler":
                self._shape_points = [QPoint(pixel), QPoint(pixel)]
        elif self.tool == "free_frame":
            self._shape_points = [QPoint(pixel)]
        event.accept()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._panning:
            delta = event.position().toPoint() - self._drag_origin_widget
            self.pan = self._pan_origin + QPointF(delta)
            self.update()
            event.accept()
            return

        raw_pixel = self.widget_to_image(event.position())
        pixel = self.widget_to_image(event.position(), clamp=self._drawing)
        if self._inside_image(raw_pixel):
            self.cursor_changed.emit(raw_pixel.x(), raw_pixel.y())
        else:
            self.cursor_changed.emit(-1, -1)

        if not self._drawing or not self._inside_image(pixel):
            return super().mouseMoveEvent(event)
        if self.tool in {"pencil", "eraser"}:
            self._draw_segment(self._last_pixel, pixel)
            self._last_pixel = pixel
        elif self.tool in {"select", "collision"} or self.tool.startswith("shape_"):
            self._temp_rect = QRect(self._last_pixel, pixel).normalized().adjusted(0, 0, 1, 1)
            self.update()
        elif self.tool == "ruler":
            endpoint = self._snap_ruler_endpoint(self._last_pixel, pixel) if event.modifiers() & Qt.KeyboardModifier.ShiftModifier else pixel
            self._shape_points = [QPoint(self._last_pixel), QPoint(endpoint)]
            self._temp_rect = QRect(self._last_pixel, endpoint).normalized().adjusted(0, 0, 1, 1)
            self.update()
        elif self.tool == "free_frame":
            if not self._shape_points or self._shape_points[-1] != pixel:
                self._shape_points.append(QPoint(pixel)); self.update()
        event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if self._panning:
            self._panning = False
            self.set_tool(self.tool)
            event.accept()
            return
        if event.button() != Qt.MouseButton.LeftButton or not self._drawing:
            return super().mouseReleaseEvent(event)

        if self.tool == "select" and not self._temp_rect.isNull():
            self.selection = self._temp_rect.intersected(self.image.rect())
            self.selection_changed.emit(QRect(self.selection))
        elif self.tool == "collision" and not self._temp_rect.isNull():
            rect = self._temp_rect.intersected(self.image.rect())
            if rect.width() > 0 and rect.height() > 0:
                self.edit_started.emit()
                self.collision_added.emit(QRect(rect))
        elif (self.tool == "ruler" or self.tool.startswith("shape_")) and not self._temp_rect.isNull():
            self.edit_started.emit()
            endpoint = self._shape_points[-1] if self.tool == "ruler" and self._shape_points else self._temp_rect.bottomRight()
            self._commit_frame_shape(self.tool, self._last_pixel, endpoint)
        elif self.tool == "free_frame" and len(self._shape_points) > 1:
            self.edit_started.emit()
            self._commit_free_frame(self._shape_points)
        self._temp_rect = QRect()
        self._shape_points = []
        self._drawing = False
        self.image_changed.emit()
        self.update()
        event.accept()

    @staticmethod
    def _snap_ruler_endpoint(start: QPoint, end: QPoint) -> QPoint:
        dx, dy = end.x() - start.x(), end.y() - start.y()
        distance = math.hypot(dx, dy)
        if distance < 0.5:
            return QPoint(end)
        angle = round(math.atan2(dy, dx) / (math.pi / 4.0)) * (math.pi / 4.0)
        return QPoint(round(start.x() + math.cos(angle) * distance), round(start.y() + math.sin(angle) * distance))

    @staticmethod
    def _free_frame_path(points: list[QPoint], close: bool = True) -> QPainterPath:
        path = QPainterPath()
        if not points:
            return path
        path.moveTo(points[0])
        for point in points[1:]:
            path.lineTo(point)
        if close and len(points) > 2:
            path.closeSubpath()
        return path

    @staticmethod
    def _frame_shape_path(tool: str, start: QPoint, end: QPoint) -> QPainterPath:
        rect = QRect(start, end).normalized().adjusted(0, 0, 1, 1)
        box = QRectF(rect)
        path = QPainterPath()
        if tool == "ruler":
            path.moveTo(start); path.lineTo(end); return path
        if tool == "shape_ellipse":
            path.addEllipse(box); return path
        if tool == "shape_round_rect":
            radius = max(2.0, min(box.width(), box.height()) * 0.18)
            path.addRoundedRect(box, radius, radius); return path
        if tool in {"shape_triangle", "shape_right_triangle"}:
            if tool == "shape_right_triangle":
                points = [box.topLeft(), box.bottomLeft(), box.bottomRight()]
            else:
                points = [QPointF(box.center().x(), box.top()), box.bottomRight(), box.bottomLeft()]
            path.moveTo(points[0])
            for point in points[1:]: path.lineTo(point)
            path.closeSubpath(); return path
        if tool == "shape_star":
            center, outer = box.center(), min(box.width(), box.height()) / 2.0
            inner = outer * 0.43
            points = []
            for index in range(10):
                radius = outer if index % 2 == 0 else inner
                angle = -math.pi / 2 + index * math.pi / 5
                points.append(QPointF(center.x() + math.cos(angle) * radius, center.y() + math.sin(angle) * radius))
            if points:
                path.moveTo(points[0])
                for point in points[1:]: path.lineTo(point)
                path.closeSubpath()
            return path
        if tool == "shape_arrow":
            notch = box.left() + box.width() * 0.58
            shoulder = box.top() + box.height() * 0.27
            points = [
                QPointF(box.left(), shoulder), QPointF(notch, shoulder), QPointF(notch, box.top()),
                QPointF(box.right(), box.center().y()), QPointF(notch, box.bottom()),
                QPointF(notch, box.bottom() - box.height() * 0.27), QPointF(box.left(), box.bottom() - box.height() * 0.27),
            ]
            path.moveTo(points[0])
            for point in points[1:]: path.lineTo(point)
            path.closeSubpath(); return path
        if tool == "shape_speech":
            bubble = QRectF(box.left(), box.top(), box.width(), max(1.0, box.height() * 0.78))
            radius = min(bubble.width(), bubble.height()) * 0.22
            path.addRoundedRect(bubble, radius, radius)
            tail = QPainterPath(); tail.moveTo(box.left() + box.width() * 0.22, bubble.bottom() - 1)
            tail.lineTo(box.left() + box.width() * 0.18, box.bottom())
            tail.lineTo(box.left() + box.width() * 0.42, bubble.bottom() - 1); tail.closeSubpath()
            return path.united(tail)
        path.addRect(box)
        return path

    def _frame_pen(self) -> QPen:
        return QPen(
            self.quantize_color(self.brush_color), self.brush_size,
            Qt.PenStyle.SolidLine, Qt.PenCapStyle.SquareCap, Qt.PenJoinStyle.MiterJoin,
        )

    def _commit_frame_shape(self, tool: str, start: QPoint, end: QPoint) -> None:
        painter = QPainter(self.image); painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
        painter.setPen(self._frame_pen()); painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(self._frame_shape_path(tool, start, end)); painter.end()

    def _commit_free_frame(self, points: list[QPoint]) -> None:
        painter = QPainter(self.image); painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
        painter.setPen(self._frame_pen()); painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(self._free_frame_path(points, close=True)); painter.end()

    def wheelEvent(self, event: QWheelEvent) -> None:
        old_rect = self.image_display_rect()
        old_zoom = self.zoom
        factor = 1.18 if event.angleDelta().y() > 0 else 1 / 1.18
        self.set_zoom(self.zoom * factor)
        # Keep the image point under the pointer stable while zooming.
        if old_zoom > 0:
            pointer = event.position()
            ratio_x = (pointer.x() - old_rect.left()) / max(1.0, old_rect.width())
            ratio_y = (pointer.y() - old_rect.top()) / max(1.0, old_rect.height())
            new_rect = self.image_display_rect()
            target_x = new_rect.left() + ratio_x * new_rect.width()
            target_y = new_rect.top() + ratio_y * new_rect.height()
            self.pan += QPointF(pointer.x() - target_x, pointer.y() - target_y)
        self.update()
        event.accept()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)

    def _draw_segment(self, start: QPoint, end: QPoint) -> None:
        painter = QPainter(self.image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        if self.tool == "eraser":
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
            pen = QPen(QColorConstants.Transparent, self.brush_size, Qt.PenStyle.SolidLine, Qt.PenCapStyle.SquareCap, Qt.PenJoinStyle.MiterJoin)
        else:
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
            pen = QPen(self.quantize_color(self.brush_color), self.brush_size, Qt.PenStyle.SolidLine, Qt.PenCapStyle.SquareCap, Qt.PenJoinStyle.MiterJoin)
        painter.setPen(pen)
        painter.drawLine(start, end)
        painter.end()
        self.image_changed.emit()
        self.update()

    def _flood_fill(self, start: QPoint) -> None:
        target = self.image.pixelColor(start)
        replacement = self.quantize_color(self.brush_color)
        if target.rgba() == replacement.rgba():
            return
        width, height = self.image.width(), self.image.height()
        stack = [(start.x(), start.y())]
        visited = bytearray(width * height)
        while stack:
            x, y = stack.pop()
            idx = y * width + x
            if visited[idx]:
                continue
            visited[idx] = 1
            if self.image.pixelColor(x, y).rgba() != target.rgba():
                continue
            self.image.setPixelColor(x, y, replacement)
            if x > 0: stack.append((x - 1, y))
            if x + 1 < width: stack.append((x + 1, y))
            if y > 0: stack.append((x, y - 1))
            if y + 1 < height: stack.append((x, y + 1))
        self.image_changed.emit()
        self.update()


class AssetEditorDialog(QDialog):
    """Large frameless standalone window for editing project image assets."""

    asset_saved = Signal(str)

    def __init__(
        self,
        project_root: str | Path,
        initial_file: str | Path | None = None,
        initial_destination: str | Path | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.project_root = Path(project_root).resolve()
        self.current_source: Path | None = None
        self._editing_existing_project_asset = False
        self.saved_path: Path | None = None
        self.initial_destination = str(initial_destination or "").replace("\\", "/").strip("/")
        self._drag_offset: QPoint | None = None
        self._normal_geometry: QRect | None = None
        self._initial_maximize_pending = True
        self._undo: list[EditorSnapshot] = []
        self._redo: list[EditorSnapshot] = []
        self._max_history = 40
        self._background_color = QColor("#ffffff")
        self._collision_kind = "solid"
        self.pixel_mode_bits = 32
        self.scene_frames: list[SceneFrameRecord] = []
        self.selected_scene = -1
        self._playback_index = -1
        self._playback_backup: QImage | None = None
        self.playback_timer = QTimer(self)
        self.playback_timer.timeout.connect(self._playback_tick)
        self.animation_player_window: AnimationPlayerWindow | None = None
        self.animation_player_settings: dict = {
            "source_mode": "atlas_frames",
            "selected_by_source": {"atlas_frames": [], "scene_timeline": []},
            "selected_indices": [],
            "selection_mask_hex": "",
            "fps": 12,
            "loop": True,
            "background": "checker",
            "preview_zoom": 1,
        }

        self._toolbar_buttons: list[QToolButton] = []
        self._editor_tool_buttons: list[QToolButton] = []
        self._workspace_splitter: QSplitter | None = None
        self._frame_strip_widget: QWidget | None = None
        self._legacy_catalog: dict = {}
        self._legacy_selected_target = ""
        self._legacy_thumbnail_cache: dict[str, QIcon] = {}
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setModal(False)
        self.setWindowModality(Qt.WindowModality.NonModal)
        self.setMinimumSize(720, 500)
        self.resize(1280, 800)

        self.outer_layout = QVBoxLayout(self)
        self.outer_layout.setContentsMargins(14, 14, 14, 14)
        self.root = QFrame()
        self.root.setObjectName("AssetEditorRoot")
        self.outer_layout.addWidget(self.root)
        root_layout = QVBoxLayout(self.root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        root_layout.addWidget(self._build_title_bar())
        self.asset_toolbar = self._build_toolbar()
        root_layout.addWidget(self.asset_toolbar)
        self.workspace_tabs = QTabWidget()
        self.workspace_tabs.addTab(self._build_workspace(), "Assets · VXPEngine")
        self.vpe_pixel = VpePixelPanel(self)
        self.vpe_pixel.received.connect(self._receive_vpe_pixel)
        self.vpe_pixel.send_requested.connect(self._send_to_vpe_pixel)
        self.workspace_tabs.addTab(self.vpe_pixel, "VPE Pixel")
        self.workspace_tabs.currentChanged.connect(self._workspace_tab_changed)
        root_layout.addWidget(self.workspace_tabs, 1)
        root_layout.addWidget(self._build_footer())

        self._install_shortcuts()
        self._apply_initial_destination(self.initial_destination)
        if initial_file:
            self.load_image(Path(initial_file))
        else:
            self._update_document_title("Tài nguyên chưa lưu")
            self._refresh_all()

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        if self._initial_maximize_pending:
            self._initial_maximize_pending = False
            screen = self.screen() or QApplication.primaryScreen()
            if screen is not None:
                area = screen.availableGeometry()
                target_w = min(1420, max(self.minimumWidth(), int(area.width() * 0.94)))
                target_h = min(880, max(self.minimumHeight(), int(area.height() * 0.92)))
                self._normal_geometry = QRect(
                    area.center().x() - target_w // 2,
                    area.center().y() - target_h // 2,
                    target_w,
                    target_h,
                )
                self.setGeometry(self._normal_geometry)
            QTimer.singleShot(0, self._show_initially_maximized)
        self._sync_window_chrome()
        self._apply_responsive_editor_layout()

    def changeEvent(self, event) -> None:
        super().changeEvent(event)
        if event.type() == QEvent.Type.WindowStateChange:
            QTimer.singleShot(0, self._sync_window_chrome)

    def _show_initially_maximized(self) -> None:
        if not self.isVisible():
            return
        self.showMaximized()
        self._sync_window_chrome()

    def _sync_window_chrome(self) -> None:
        maximized = self.isMaximized()
        if hasattr(self, "outer_layout"):
            margin = 0 if maximized else 14
            self.outer_layout.setContentsMargins(margin, margin, margin, margin)
        if hasattr(self, "maximize_button"):
            self.maximize_button.setIcon(icon("fa5s.clone" if maximized else "fa5s.window-maximize"))
            self.maximize_button.setToolTip("Khôi phục" if maximized else "Phóng to")

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._apply_responsive_editor_layout()

    def _apply_responsive_editor_layout(self) -> None:
        very_compact = self.width() < 900
        for button in getattr(self, "_toolbar_buttons", []):
            text = str(button.property("responsiveText") or "")
            button.setText("")
            button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
            button.setToolTip(button.toolTip() or text)
        for button in getattr(self, "_editor_tool_buttons", []):
            text = str(button.property("responsiveText") or button.toolTip() or "")
            button.setText("")
            button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
            button.setToolTip(button.toolTip() or text)
        if hasattr(self, "source_label"):
            self.source_label.setVisible(not very_compact)
        if self._workspace_splitter is not None:
            total = max(1, self._workspace_splitter.width())
            left = 170 if very_compact else 220
            right = 220 if very_compact else 310
            center = max(260, total - left - right - 8)
            self._workspace_splitter.setSizes([left, center, right])
        if self._frame_strip_widget is not None:
            self._frame_strip_widget.setFixedHeight(150 if self.height() < 650 else 190)

    # ---------- UI construction ----------
    def _build_title_bar(self) -> QWidget:
        bar = _AssetEditorTitleBar(self)
        bar.setObjectName("AssetEditorTitleBar")
        bar.setFixedHeight(34)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(14, 0, 8, 0)
        logo = QLabel()
        logo.setPixmap(icon("fa5s.magic", "#62a2ff").pixmap(18, 18))
        layout.addWidget(logo)
        self.title_label = QLabel("Editor Assets")
        self.title_label.setObjectName("AssetEditorTitle")
        layout.addWidget(self.title_label)
        layout.addStretch()
        self.source_label = QLabel("Tài nguyên chưa lưu")
        self.source_label.setObjectName("AssetEditorSource")
        layout.addWidget(self.source_label)
        layout.addStretch()

        minimize = QPushButton()
        minimize.setObjectName("AssetEditorWindowButton")
        minimize.setIcon(icon("fa5s.minus"))
        minimize.setIconSize(QSize(10, 10))
        minimize.setFixedSize(42, 30)
        minimize.setToolTip("Thu nhỏ")
        minimize.clicked.connect(self.showMinimized)
        layout.addWidget(minimize)

        self.maximize_button = QPushButton()
        self.maximize_button.setObjectName("AssetEditorWindowButton")
        self.maximize_button.setIcon(icon("fa5s.window-maximize"))
        self.maximize_button.setIconSize(QSize(10, 10))
        self.maximize_button.setFixedSize(42, 30)
        self.maximize_button.setToolTip("Phóng to")
        self.maximize_button.clicked.connect(self.toggle_maximize_restore)
        layout.addWidget(self.maximize_button)

        close = QPushButton()
        close.setObjectName("AssetEditorClose")
        close.setIcon(icon("fa5s.times"))
        close.setFixedSize(46, 30)
        close.clicked.connect(self.reject)
        layout.addWidget(close)
        return bar

    def _format_shortcut_tooltip(self, title: str, shortcut: str = "", description: str = "") -> str:
        lines = [title]
        if shortcut:
            lines.append(f"Phím tắt: {shortcut}")
        if description:
            lines.append(description)
        return "\n".join(lines)

    def _make_icon_button(self, button: QToolButton, text: str, tooltip: str) -> None:
        button.setText("")
        button.setProperty("responsiveText", text)
        button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        button.setIconSize(QSize(16, 16))
        button.setFixedSize(34, 30)
        button.setToolTip(tooltip)
        button.setStatusTip(tooltip)

    def _build_toolbar(self) -> QWidget:
        bar = QWidget()
        bar.setObjectName("AssetEditorToolbar")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(8, 5, 8, 5)
        layout.setSpacing(3)

        def action_button(text: str, icon_name: str, callback, tooltip: str = "", shortcut: str = "") -> QToolButton:
            button = QToolButton()
            button.setIcon(icon(icon_name))
            self._make_icon_button(button, text, self._format_shortcut_tooltip(text, shortcut, tooltip))
            button.clicked.connect(callback)
            layout.addWidget(button)
            self._toolbar_buttons.append(button)
            return button

        action_button("Tạo trống", "fa5s.file", self.new_canvas, "Tạo canvas mới", "Ctrl+N")
        action_button("Nhập ảnh", "fa5s.file-import", self.import_image, "Mở ảnh từ Windows File Picker", "Ctrl+O")
        action_button("Nhập res cũ", "fa5s.folder-open", self.import_legacy_res_folder, "Quét res/ MRE cũ, tự phân loại và tạo catalog", "Ctrl+Alt+R")
        action_button("Ghép ảnh", "fa5s.layer-group", self.insert_image, "Chèn thêm ảnh/layer vào canvas", "Ctrl+Shift+I")
        layout.addWidget(self._separator())
        self.undo_button = action_button("Undo", "fa5s.undo", self.undo, "Hoàn tác thao tác gần nhất", "Ctrl+Z")
        self.redo_button = action_button("Redo", "fa5s.redo", self.redo, "Làm lại thao tác vừa hoàn tác", "Ctrl+Y")
        layout.addWidget(self._separator())
        action_button("Fit", "fa5s.expand", self.canvas_fit, "Vừa khung làm việc", "0")
        action_button("100%", "fa5s.search", lambda: self.canvas.set_zoom(1.0), "Đưa zoom về 100%", "1")

        self.grid_button = QToolButton()
        self.grid_button.setIcon(icon("fa5s.th"))
        self._make_icon_button(self.grid_button, "Lưới", self._format_shortcut_tooltip("Lưới", "G", "Bật / tắt lưới preview"))
        self.grid_button.setCheckable(True)
        self.grid_button.setChecked(True)
        self.grid_button.toggled.connect(self._toggle_grid)
        layout.addWidget(self.grid_button)
        self._toolbar_buttons.append(self.grid_button)

        layout.addStretch()
        action_button("Xóa nền", "fa5s.eraser", self.remove_background, "Tự xóa nền của ảnh hiện tại", "Ctrl+Shift+B")
        action_button("Cắt trong suốt", "fa5s.crop-alt", self.crop_transparent, "Cắt theo biên trong suốt", "Ctrl+Alt+C")
        action_button("Smart Slice", "fa5s.object-ungroup", self.smart_slice, "Nhận diện vùng nội dung và cắt thành phần thông minh", "Alt+Shift+S")
        action_button("Anim Player", "fa5s.film", self.open_animation_player, "Chọn frame, đặt FPS và xem animation loop", "Alt+A")
        return bar

    def _build_workspace(self) -> QWidget:
        splitter = QSplitter(Qt.Orientation.Horizontal)
        self._workspace_splitter = splitter
        splitter.setObjectName("AssetEditorSplitter")
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(4)

        self.canvas = AssetCanvas()
        self.canvas.edit_started.connect(self._push_undo)
        self.canvas.image_changed.connect(self._on_image_changed)
        self.canvas.color_picked.connect(self._set_brush_color)
        self.canvas.cursor_changed.connect(self._cursor_changed)
        self.canvas.collision_added.connect(self._add_collision)
        self.canvas.selection_changed.connect(self._selection_changed)
        self.canvas.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.canvas.customContextMenuRequested.connect(self._show_canvas_context_menu)

        splitter.addWidget(self._build_left_panel())

        center = QWidget()
        center.setObjectName("AssetEditorCenter")
        center_layout = QVBoxLayout(center)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(0)
        center_layout.addWidget(self.canvas, 1)
        center_layout.addWidget(self._build_frame_strip())
        splitter.addWidget(center)

        splitter.addWidget(self._build_right_panel())
        splitter.setSizes([220, 880, 310])
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 0)
        return splitter

    def _build_left_panel(self) -> QWidget:
        panel = QScrollArea()
        panel.setObjectName("AssetEditorSidePanel")
        panel.setWidgetResizable(True)
        panel.setFrameShape(QFrame.Shape.NoFrame)
        panel.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        panel.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        panel.setMinimumWidth(160)
        panel.setMaximumWidth(300)

        content = QWidget()
        content.setObjectName("AssetEditorSideContent")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        layout.addWidget(self._section_label("LOẠI TÀI NGUYÊN"))
        self.asset_type_combo = QComboBox()
        self.asset_type_combo.addItems([
            "Nhân vật / Sprite",
            "Tileset / Map",
            "UI / HUD",
            "Stage2D / Parallax Layer",
            "Stage2D / Water Band",
            "Stage2D / Ground",
            "Stage2D / Foreground",
            "2.5D / Billboard",
            "2.5D / Perspective Plane",
            "2.5D / Water Surface",
            "Nguyên liệu / Material",
            "Biểu tượng game / ứng dụng",
            "Tài nguyên 2D khác",
        ])
        self.asset_type_combo.currentTextChanged.connect(self._asset_type_changed)
        self.asset_type_combo.hide()

        type_content = QWidget()
        type_layout = QHBoxLayout(type_content)
        type_layout.setContentsMargins(0, 2, 0, 2)
        type_layout.setSpacing(5)
        self.asset_type_buttons: dict[str, QPushButton] = {}
        for index in range(self.asset_type_combo.count()):
            asset_type = self.asset_type_combo.itemText(index)
            button = QPushButton(asset_type.split("/")[0].strip())
            button.setCheckable(True)
            button.setProperty("assetTypeChip", True)
            button.setToolTip(asset_type)
            button.clicked.connect(lambda _checked=False, value=asset_type: self.asset_type_combo.setCurrentText(value))
            self.asset_type_buttons[asset_type] = button
            type_layout.addWidget(button)
        type_layout.addStretch()
        type_layout.activate()
        type_content.setMinimumWidth(type_layout.sizeHint().width())
        type_rail = _HorizontalChipRail(type_content)
        layout.addWidget(type_rail)
        self.asset_type_combo.currentTextChanged.connect(self._sync_asset_type_buttons)
        self._sync_asset_type_buttons(self.asset_type_combo.currentText())

        layout.addWidget(self._section_label("CÔNG CỤ VẼ"))
        grid = QGridLayout()
        grid.setSpacing(4)
        self.tool_buttons: dict[str, QToolButton] = {}
        tool_shortcuts = {
            "pencil": "B",
            "eraser": "E",
            "fill": "F",
            "picker": "I",
            "select": "V",
            "collision": "C",
            "pan": "H",
            "ruler": "R",
            "free_frame": "Shift+B",
            "shape_rect": "U",
        }
        tools = [
            ("pencil", "Bút pixel", "fa5s.pencil-alt"),
            ("eraser", "Tẩy", "fa5s.eraser"),
            ("fill", "Đổ màu", "fa5s.fill-drip"),
            ("picker", "Lấy màu", "fa5s.eye-dropper"),
            ("select", "Chọn vùng", "fa5s.vector-square"),
            ("collision", "Collision", "fa5s.draw-polygon"),
            ("ruler", "Thước đường thẳng", "fa5s.ruler"),
            ("free_frame", "Frame vẽ tay", "fa5s.signature"),
            ("shape_rect", "Frame hình học", "fa5s.shapes"),
            ("pan", "Di chuyển canvas", "fa5s.hand-paper"),
        ]
        self.shape_tool_labels = {
            "shape_rect": "Chữ nhật",
            "shape_round_rect": "Chữ nhật bo góc / nút",
            "shape_ellipse": "Tròn / ellipse",
            "shape_triangle": "Tam giác",
            "shape_right_triangle": "Tam giác vuông",
            "shape_arrow": "Mũi tên",
            "shape_star": "Ngôi sao",
            "shape_speech": "Khung hội thoại",
        }
        self.pixel_mode_actions: dict[int, QAction] = {}
        for index, (key, name, icon_name) in enumerate(tools):
            button = QToolButton()
            button.setIcon(icon(icon_name))
            self._make_icon_button(button, name, self._format_shortcut_tooltip(name, tool_shortcuts.get(key, ""), "Dùng chuột để thao tác trên canvas"))
            button.setCheckable(True)
            button.clicked.connect(lambda _checked=False, tool=key: self._set_tool(tool))
            if key == "pencil":
                button.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)
                menu = QMenu(button)
                for bits, shortcut in ((8, "Alt+1"), (16, "Alt+2"), (32, "Alt+3")):
                    action = QAction(f"Pixel Art {bits}-bit", button)
                    action.setCheckable(True)
                    action.setToolTip(self._format_shortcut_tooltip(f"Pixel Art {bits}-bit", shortcut))
                    action.triggered.connect(lambda _checked=False, value=bits: self._set_pixel_mode(value))
                    menu.addAction(action)
                    self.pixel_mode_actions[bits] = action
                button.setMenu(menu)
            elif key == "shape_rect":
                button.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)
                menu = QMenu(button)
                shape_icons = {
                    "shape_rect":"fa5s.square", "shape_round_rect":"fa5s.stop",
                    "shape_ellipse":"fa5s.circle", "shape_triangle":"fa5s.caret-up",
                    "shape_right_triangle":"fa5s.play", "shape_arrow":"fa5s.long-arrow-alt-right",
                    "shape_star":"fa5s.star", "shape_speech":"fa5s.comment-alt",
                }
                for shape_tool, shape_label in self.shape_tool_labels.items():
                    action = QAction(icon(shape_icons[shape_tool]), shape_label, menu)
                    action.triggered.connect(lambda _checked=False, value=shape_tool: self._set_tool(value))
                    menu.addAction(action)
                button.setMenu(menu)
            self.tool_buttons[key] = button
            self._editor_tool_buttons.append(button)
            grid.addWidget(button, index // 2, index % 2)
        layout.addLayout(grid)
        shortcut_hint = QLabel("V chọn • B bút • Shift+B frame tay • R thước • U hình học • E tẩy • F đổ màu • I lấy màu • C collision • H kéo canvas")
        shortcut_hint.setObjectName("AssetHelpText")
        shortcut_hint.setWordWrap(True)
        layout.addWidget(shortcut_hint)
        self._set_pixel_mode(32, activate=False)
        self._set_tool("pencil")

        layout.addWidget(self._section_label("MÀU & NÉT"))
        color_row = QHBoxLayout()
        self.color_button = QPushButton()
        self.color_button.setObjectName("AssetColorButton")
        self.color_button.setFixedHeight(34)
        self.color_button.clicked.connect(self.choose_brush_color)
        color_row.addWidget(self.color_button, 1)
        self.color_hex = QLineEdit("#ff8a3d")
        self.color_hex.setMaxLength(9)
        self.color_hex.editingFinished.connect(self._hex_color_changed)
        color_row.addWidget(self.color_hex)
        layout.addLayout(color_row)

        brush_row = QHBoxLayout()
        brush_row.addWidget(QLabel("Cọ pixel"))
        self.brush_size = QSpinBox()
        self.brush_size.setRange(1, 128)
        self.brush_size.setSingleStep(1)
        self.brush_size.setValue(1)
        self.brush_size.setSuffix(" px")
        self.brush_size.valueChanged.connect(lambda value: setattr(self.canvas, "brush_size", value))
        brush_row.addWidget(self.brush_size, 0)
        self.brush_slider = QSlider(Qt.Orientation.Horizontal)
        self.brush_slider.setRange(1, 128)
        self.brush_slider.setValue(1)
        self.brush_slider.valueChanged.connect(self.brush_size.setValue)
        self.brush_size.valueChanged.connect(self.brush_slider.setValue)
        brush_row.addWidget(self.brush_slider, 1)
        layout.addLayout(brush_row)
        brush_hint = QLabel("Tăng cỡ cọ để vẽ các ô pixel to hoặc nhỏ trong Pixel Art.")
        brush_hint.setObjectName("AssetHelpText")
        brush_hint.setWordWrap(True)
        layout.addWidget(brush_hint)

        layout.addWidget(self._section_label("THÔNG TIN"))
        self.info_label = QLabel()
        self.info_label.setObjectName("AssetInfoLabel")
        self.info_label.setWordWrap(True)
        layout.addWidget(self.info_label)
        layout.addStretch()
        self._set_brush_color(QColor("#ff8a3d"))
        panel.setWidget(content)
        return panel

    def _build_right_panel(self) -> QWidget:
        panel = QWidget()
        panel.setObjectName("AssetEditorSidePanel")
        panel.setMinimumWidth(210)
        panel.setMaximumWidth(400)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(8, 8, 8, 8)
        self.inspector_tabs = QTabWidget()
        self.inspector_tabs.setDocumentMode(True)
        self.inspector_tabs.addTab(self._build_slice_tab(), icon("fa5s.border-all"), "Cắt ô")
        self.inspector_tabs.addTab(self._build_collision_tab(), icon("fa5s.draw-polygon"), "Collision")
        self.inspector_tabs.addTab(self._build_texture_tab(), icon("fa5s.magic"), "Texture")
        self.inspector_tabs.addTab(self._build_stage2d_tab(), icon("fa5s.water"), "Stage2D")
        self.inspector_tabs.addTab(self._build_scene25d_tab(), icon("fa5s.cube"), "2.5D")
        self.inspector_tabs.addTab(self._build_legacy_tab(), icon("fa5s.archive"), "Legacy")
        self.inspector_tabs.addTab(self._build_export_tab(), icon("fa5s.save"), "Áp dụng")
        layout.addWidget(self.inspector_tabs)
        return panel

    def _build_slice_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(10, 12, 10, 10)
        form = QFormLayout()
        self.tile_w = QSpinBox(); self.tile_w.setRange(1, 2048); self.tile_w.setValue(16)
        self.tile_h = QSpinBox(); self.tile_h.setRange(1, 2048); self.tile_h.setValue(16)
        self.margin_spin = QSpinBox(); self.margin_spin.setRange(0, 2048)
        self.spacing_spin = QSpinBox(); self.spacing_spin.setRange(0, 2048)
        self.frame_duration = QSpinBox(); self.frame_duration.setRange(1, 60000); self.frame_duration.setValue(100); self.frame_duration.setSuffix(" ms")
        form.addRow("Rộng ô", self.tile_w)
        form.addRow("Cao ô", self.tile_h)
        form.addRow("Lề", self.margin_spin)
        form.addRow("Khoảng cách", self.spacing_spin)
        form.addRow("Thời lượng frame", self.frame_duration)
        layout.addLayout(form)
        self.ignore_empty = QCheckBox("Bỏ ô hoàn toàn trong suốt")
        self.ignore_empty.setChecked(True)
        layout.addWidget(self.ignore_empty)
        self.preview_grid = QCheckBox("Hiển thị lưới trên canvas")
        self.preview_grid.setChecked(True)
        self.preview_grid.toggled.connect(self._toggle_grid)
        layout.addWidget(self.preview_grid)

        row = QHBoxLayout()
        auto = QPushButton("Chia ô tự động")
        auto.setIcon(icon("fa5s.border-all"))
        auto.clicked.connect(self.auto_slice)
        clear = QPushButton("Xóa frame")
        clear.setIcon(icon("fa5s.trash-alt"))
        clear.clicked.connect(self.clear_frames)
        row.addWidget(auto)
        row.addWidget(clear)
        layout.addLayout(row)

        smart_label = QLabel("SMART SLICE · LOCAL AI")
        smart_label.setObjectName("AssetSectionLabel")
        layout.addWidget(smart_label)
        smart_help = QLabel("Nhận diện cụm pixel, gộp chi tiết rời và tạo khung cắt sát nội dung. Ảnh không rời khỏi máy.")
        smart_help.setObjectName("AssetHelpText")
        smart_help.setWordWrap(True)
        layout.addWidget(smart_help)
        smart_form = QFormLayout()
        self.smart_alpha = QSpinBox(); self.smart_alpha.setRange(1, 255); self.smart_alpha.setValue(8)
        self.smart_min_pixels = QSpinBox(); self.smart_min_pixels.setRange(1, 1000000); self.smart_min_pixels.setValue(8)
        self.smart_merge = QSpinBox(); self.smart_merge.setRange(0, 128); self.smart_merge.setValue(1); self.smart_merge.setSuffix(" px")
        self.smart_padding = QSpinBox(); self.smart_padding.setRange(0, 128); self.smart_padding.setValue(1); self.smart_padding.setSuffix(" px")
        smart_form.addRow("Ngưỡng alpha", self.smart_alpha)
        smart_form.addRow("Pixel tối thiểu", self.smart_min_pixels)
        smart_form.addRow("Gộp khoảng hở", self.smart_merge)
        smart_form.addRow("Padding", self.smart_padding)
        layout.addLayout(smart_form)
        smart_button = QPushButton("Smart Slice thành phần")
        smart_button.setIcon(icon("fa5s.object-ungroup"))
        smart_button.clicked.connect(self.smart_slice)
        layout.addWidget(smart_button)

        crop = QPushButton("Cắt theo vùng đang chọn")
        crop.setIcon(icon("fa5s.crop-alt"))
        crop.clicked.connect(self.crop_selection)
        layout.addWidget(crop)
        layout.addStretch()
        for spin in (self.tile_w, self.tile_h):
            spin.valueChanged.connect(self._sync_grid)
        return tab

    def _build_collision_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(10, 12, 10, 10)
        description = QLabel("Chọn công cụ Collision rồi kéo trực tiếp trên sprite/frame. Dữ liệu được lưu trong tệp .asset.dtfe.")
        description.setWordWrap(True)
        description.setObjectName("AssetHelpText")
        layout.addWidget(description)
        self.collision_kind = QComboBox()
        self.collision_kind.addItem("Solid / Vật cản", "solid")
        self.collision_kind.addItem("Trigger / Vùng kích hoạt", "trigger")
        self.collision_kind.addItem("Hurtbox", "hurtbox")
        self.collision_kind.addItem("Hitbox", "hitbox")
        self.collision_kind.currentIndexChanged.connect(self._collision_kind_changed)
        layout.addWidget(self.collision_kind)
        select_tool = QPushButton("Vẽ collision trên canvas")
        select_tool.setIcon(icon("fa5s.draw-polygon"))
        select_tool.clicked.connect(lambda: self._set_tool("collision"))
        layout.addWidget(select_tool)
        self.collision_list = QListWidget()
        self.collision_list.currentRowChanged.connect(self._collision_selected)
        layout.addWidget(self.collision_list, 1)
        row = QHBoxLayout()
        delete = QPushButton("Xóa chọn")
        delete.setIcon(icon("fa5s.trash-alt"))
        delete.clicked.connect(self.delete_collision)
        clear = QPushButton("Xóa tất cả")
        clear.clicked.connect(self.clear_collisions)
        row.addWidget(delete)
        row.addWidget(clear)
        layout.addLayout(row)
        return tab

    def _build_texture_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(10, 12, 10, 10)

        layout.addWidget(self._section_label("XÓA NỀN"))
        row = QHBoxLayout()
        self.bg_color_button = QPushButton("Màu nền")
        self.bg_color_button.clicked.connect(self.choose_background_color)
        use_corner = QPushButton("Lấy góc trái")
        use_corner.clicked.connect(self.use_top_left_background)
        row.addWidget(self.bg_color_button)
        row.addWidget(use_corner)
        layout.addLayout(row)
        self.tolerance = QSlider(Qt.Orientation.Horizontal)
        self.tolerance.setRange(0, 128)
        self.tolerance.setValue(16)
        self.tolerance_label = QLabel("Sai số: 16")
        self.tolerance.valueChanged.connect(lambda value: self.tolerance_label.setText(f"Sai số: {value}"))
        layout.addWidget(self.tolerance_label)
        layout.addWidget(self.tolerance)
        remove = QPushButton("Xóa màu nền")
        remove.setIcon(icon("fa5s.eraser"))
        remove.clicked.connect(self.remove_background)
        layout.addWidget(remove)

        layout.addWidget(self._section_label("BIẾN ĐỔI"))
        transform_row = QGridLayout()
        buttons = [
            ("Lật ngang", "fa5s.arrows-alt-h", self.flip_horizontal),
            ("Lật dọc", "fa5s.arrows-alt-v", self.flip_vertical),
            ("Xoay 90°", "fa5s.redo", self.rotate_90),
            ("Cắt alpha", "fa5s.crop-alt", self.crop_transparent),
        ]
        for i, (text, icon_name, callback) in enumerate(buttons):
            button = QPushButton(text)
            button.setIcon(icon(icon_name))
            button.clicked.connect(callback)
            transform_row.addWidget(button, i // 2, i % 2)
        layout.addLayout(transform_row)

        resize_form = QFormLayout()
        self.resize_w = QSpinBox(); self.resize_w.setRange(1, 8192)
        self.resize_h = QSpinBox(); self.resize_h.setRange(1, 8192)
        resize_form.addRow("Rộng mới", self.resize_w)
        resize_form.addRow("Cao mới", self.resize_h)
        layout.addLayout(resize_form)
        resize_button = QPushButton("Đổi kích thước — Nearest")
        resize_button.setIcon(icon("fa5s.expand-alt"))
        resize_button.clicked.connect(self.resize_image)
        layout.addWidget(resize_button)

        layout.addWidget(self._section_label("PHONG CÁCH 2D"))
        self.style_combo = QComboBox()
        self.style_combo.addItems([
            "Pixel Art · Classic Retro",
            "Pixel Art · Modern Pixel Art",
            "Pixel Art · Isometric RTS",
            "Pixel hóa 2×",
            "Pixel hóa 4×",
            "Retro 4-bit",
            "Posterize 8 màu",
            "Vector / Clean Art",
            "Hand-drawn / Painted · Watercolor",
            "Hand-drawn / Painted · Anime / Manga",
            "Silhouette Art",
            "Flat / Geometric Art",
            "Papercraft / Cutout Art",
            "Comic / Cel-shaded 2D",
            "Grayscale",
            "Tương phản cao",
            "Viền pixel tối",
        ])
        layout.addWidget(self.style_combo)
        self.style_combo.addItems(GAME_ART_STYLES)
        self.style_help = QLabel()
        self.style_help.setObjectName("AssetHelpText")
        self.style_help.setWordWrap(True)
        self.style_combo.currentTextChanged.connect(self._update_style_help)
        layout.addWidget(self.style_help)
        style_button = QPushButton("Áp dụng phong cách")
        style_button.setIcon(icon("fa5s.magic"))
        style_button.clicked.connect(self.apply_style)
        layout.addWidget(style_button)
        profile_form = QFormLayout()
        self.style_role_combo = QComboBox()
        self.style_role_combo.addItem("Asset / m?c ??nh", "asset")
        self.style_role_combo.addItem("Sprite / nh?n v?t", "sprite")
        self.style_role_combo.addItem("Environment / n?n", "environment")
        self.style_role_combo.addItem("UI", "ui")
        self.style_role_combo.addItem("VFX", "vfx")
        profile_form.addRow("Runtime role", self.style_role_combo)
        layout.addLayout(profile_form)
        layout.addStretch()
        self._update_style_help(self.style_combo.currentText())
        return tab

    def _update_style_help(self, style: str) -> None:
        if style in ART_STYLE_PROFILES:
            profile = ART_STYLE_PROFILES[style]
            self.style_help.setText(
                profile.get("description", "") +
                " Runtime: " + str(profile.get("runtime_preset", "")) +
                ". Profile ???c l?u trong .asset.dtfe; filter c? th? Undo."
            )
            return
        if style in GAME_ART_STYLES:
            self.style_help.setText(GAME_ART_STYLES[style][0] + " Giữ alpha và kích thước; có thể Undo.")
            return
        descriptions = {
            "Pixel Art · Classic Retro": "8-bit/16-bit cổ điển, bảng màu giới hạn, hợp game retro.",
            "Pixel Art · Modern Pixel Art": "Pixel art chi tiết cao, đổ bóng và nhấn sáng rõ hơn.",
            "Pixel Art · Isometric RTS": "Bảng màu đất/cỏ, tương phản và viền pixel cho game chiến thuật nhìn chéo.",
            "Vector / Clean Art": "Màu phẳng, sạch, sắc nét khi phóng to thu nhỏ.",
            "Hand-drawn / Painted · Watercolor": "Mềm, mộng mơ, nhẹ như màu nước/vẽ tay.",
            "Hand-drawn / Painted · Anime / Manga": "Tăng tương phản nét, hợp nhân vật anime/manga.",
            "Silhouette Art": "Tạo cảm giác bóng đen, tương phản mạnh với nền.",
            "Flat / Geometric Art": "Tối giản, chia lớp màu gọn, phù hợp UI/map clean.",
            "Papercraft / Cutout Art": "Tạo lớp viền và bóng nhẹ như cắt dán giấy.",
            "Comic / Cel-shaded 2D": "Viền dày, bóng cel-shade, phong cách truyện tranh.",
        }
        self.style_help.setText(descriptions.get(style, "Áp dụng bộ lọc nhanh cho texture, sprite hoặc tileset."))



    def _build_stage2d_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(10, 12, 10, 10)
        help_label = QLabel(
            "Stage2D cho fighting/arcade background: parallax band, water raster scanline, "
            "ground/foreground và palette/tint cycle. Preset Retro Beach Fighter mô phỏng "
            "sky + cliff + sea + beach kiểu Saturn trong video tham chiếu."
        )
        help_label.setObjectName("AssetHelpText")
        help_label.setWordWrap(True)
        layout.addWidget(help_label)

        preset_row = QHBoxLayout()
        self.stage2d_preset = QComboBox()
        self.stage2d_preset.addItems([
            "Retro Beach Fighter / Saturn",
            "Ocean Raster Band",
            "Cliff Parallax",
            "Ground / Foreground",
        ])
        preset_button = QPushButton("Áp preset")
        preset_button.clicked.connect(self._apply_stage2d_preset)
        preset_row.addWidget(self.stage2d_preset, 1)
        preset_row.addWidget(preset_button)
        layout.addLayout(preset_row)

        form = QFormLayout()
        self.stage2d_role = QComboBox()
        for label, value in (
            ("Background / Sky", "background"),
            ("Parallax Layer", "parallax"),
            ("Water Raster Band", "water"),
            ("Ground", "ground"),
            ("Foreground", "foreground"),
        ):
            self.stage2d_role.addItem(label, value)

        self.stage2d_parallax = QSpinBox(); self.stage2d_parallax.setRange(0, 200); self.stage2d_parallax.setValue(50); self.stage2d_parallax.setSuffix(" %")
        self.stage2d_y = QSpinBox(); self.stage2d_y.setRange(-1024, 2048); self.stage2d_y.setValue(96)
        self.stage2d_h = QSpinBox(); self.stage2d_h.setRange(1, 2048); self.stage2d_h.setValue(112)
        self.stage2d_repeat = QCheckBox("Lặp ngang"); self.stage2d_repeat.setChecked(True)
        self.stage2d_raster = QCheckBox("Raster wave từng scanline"); self.stage2d_raster.setChecked(False)
        self.stage2d_wave_amp = QSpinBox(); self.stage2d_wave_amp.setRange(0, 16); self.stage2d_wave_amp.setValue(3)
        self.stage2d_wave_shift = QSpinBox(); self.stage2d_wave_shift.setRange(0, 7); self.stage2d_wave_shift.setValue(2)
        self.stage2d_scroll_x = QSpinBox(); self.stage2d_scroll_x.setRange(-128, 128); self.stage2d_scroll_x.setValue(6); self.stage2d_scroll_x.setSuffix(" px/s")
        self.stage2d_scroll_y = QSpinBox(); self.stage2d_scroll_y.setRange(-128, 128); self.stage2d_scroll_y.setValue(0); self.stage2d_scroll_y.setSuffix(" px/s")
        self.stage2d_tint = QLineEdit("#FFFFFF")
        self.stage2d_alpha = QSpinBox(); self.stage2d_alpha.setRange(0, 255); self.stage2d_alpha.setValue(255)

        form.addRow("Runtime role", self.stage2d_role)
        form.addRow("Parallax", self.stage2d_parallax)
        form.addRow("Band Y", self.stage2d_y)
        form.addRow("Band height", self.stage2d_h)
        form.addRow("", self.stage2d_repeat)
        form.addRow("", self.stage2d_raster)
        form.addRow("Wave amplitude", self.stage2d_wave_amp)
        form.addRow("Wave period shift", self.stage2d_wave_shift)
        form.addRow("Scroll X", self.stage2d_scroll_x)
        form.addRow("Scroll Y", self.stage2d_scroll_y)
        form.addRow("Tint", self.stage2d_tint)
        form.addRow("Alpha", self.stage2d_alpha)
        layout.addLayout(form)
        layout.addStretch()
        return tab

    def _apply_stage2d_preset(self) -> None:
        preset = self.stage2d_preset.currentText()
        if preset.startswith("Retro Beach"):
            self.stage2d_role.setCurrentIndex(self.stage2d_role.findData("water"))
            self.stage2d_parallax.setValue(35)
            self.stage2d_y.setValue(92); self.stage2d_h.setValue(126)
            self.stage2d_repeat.setChecked(True); self.stage2d_raster.setChecked(True)
            self.stage2d_wave_amp.setValue(3); self.stage2d_wave_shift.setValue(2)
            self.stage2d_scroll_x.setValue(7); self.stage2d_scroll_y.setValue(1)
            self.stage2d_tint.setText("#A6B9D8"); self.stage2d_alpha.setValue(255)
        elif preset.startswith("Ocean"):
            self.stage2d_role.setCurrentIndex(self.stage2d_role.findData("water"))
            self.stage2d_parallax.setValue(40); self.stage2d_raster.setChecked(True)
            self.stage2d_wave_amp.setValue(4); self.stage2d_wave_shift.setValue(2)
        elif preset.startswith("Cliff"):
            self.stage2d_role.setCurrentIndex(self.stage2d_role.findData("parallax"))
            self.stage2d_parallax.setValue(25); self.stage2d_raster.setChecked(False)
            self.stage2d_scroll_x.setValue(0); self.stage2d_tint.setText("#FFFFFF")
        else:
            self.stage2d_role.setCurrentIndex(self.stage2d_role.findData("ground"))
            self.stage2d_parallax.setValue(100); self.stage2d_raster.setChecked(False)
            self.stage2d_scroll_x.setValue(0)
        self._set_status(f"Đã áp preset Stage2D: {preset}.")

    def _art_style_metadata(self) -> dict:
        name = self.style_combo.currentText()
        profile = ART_STYLE_PROFILES.get(name)
        if not profile:
            return {"name": name, "role": str(self.style_role_combo.currentData() or "asset")}
        return {
            "name": name,
            "role": str(self.style_role_combo.currentData() or "asset"),
            "runtime_preset": str(profile.get("runtime_preset") or "VXPE_ARTSTYLE_NEUTRAL"),
            "posterize_levels": int(profile.get("posterize", 0) or 0),
            "saturation": float(profile.get("saturation", 1.0) or 1.0),
            "contrast": float(profile.get("contrast", 1.0) or 1.0),
            "outline_px": int(profile.get("outline_px", 0) or 0),
            "fog": str(profile.get("fog") or "#808E96"),
            "fog_strength": int(profile.get("fog_strength", 0) or 0),
            "trail": profile.get("trail"),
        }

    def _load_art_style_metadata(self, metadata: dict) -> None:
        cfg = metadata.get("art_style") if isinstance(metadata.get("art_style"), dict) else {}
        if not cfg:
            return
        index = self.style_combo.findText(str(cfg.get("name") or ""))
        if index >= 0:
            self.style_combo.setCurrentIndex(index)
        index = self.style_role_combo.findData(str(cfg.get("role") or "asset"))
        if index >= 0:
            self.style_role_combo.setCurrentIndex(index)

    def _stage2d_metadata(self) -> dict:
        return {
            "role": str(self.stage2d_role.currentData() or "parallax"),
            "parallax_percent": self.stage2d_parallax.value(),
            "parallax_q8": round(self.stage2d_parallax.value() * 256 / 100),
            "band": {
                "y": self.stage2d_y.value(), "height": self.stage2d_h.value(),
                "repeat_x": self.stage2d_repeat.isChecked(),
                "raster_wave": self.stage2d_raster.isChecked(),
                "wave_amplitude": self.stage2d_wave_amp.value(),
                "wave_shift": self.stage2d_wave_shift.value(),
                "scroll_x_px_s": self.stage2d_scroll_x.value(),
                "scroll_y_px_s": self.stage2d_scroll_y.value(),
            },
            "tint": self.stage2d_tint.text().strip() or "#FFFFFF",
            "alpha": self.stage2d_alpha.value(),
        }

    def _load_stage2d_metadata(self, metadata: dict) -> None:
        cfg = metadata.get("stage2d") if isinstance(metadata.get("stage2d"), dict) else {}
        if not cfg:
            return
        index = self.stage2d_role.findData(str(cfg.get("role") or "parallax"))
        if index >= 0: self.stage2d_role.setCurrentIndex(index)
        self.stage2d_parallax.setValue(int(cfg.get("parallax_percent", 50)))
        band = cfg.get("band") if isinstance(cfg.get("band"), dict) else {}
        self.stage2d_y.setValue(int(band.get("y", 96)))
        self.stage2d_h.setValue(max(1, int(band.get("height", 112))))
        self.stage2d_repeat.setChecked(bool(band.get("repeat_x", True)))
        self.stage2d_raster.setChecked(bool(band.get("raster_wave", False)))
        self.stage2d_wave_amp.setValue(int(band.get("wave_amplitude", 3)))
        self.stage2d_wave_shift.setValue(int(band.get("wave_shift", 2)))
        self.stage2d_scroll_x.setValue(int(band.get("scroll_x_px_s", 0)))
        self.stage2d_scroll_y.setValue(int(band.get("scroll_y_px_s", 0)))
        self.stage2d_tint.setText(str(cfg.get("tint") or "#FFFFFF"))
        self.stage2d_alpha.setValue(int(cfg.get("alpha", 255)))

    def _build_scene25d_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(10, 12, 10, 10)
        help_label = QLabel(
            "Thiết lập metadata cho VxpScene25D: billboard theo depth, mặt phẳng phối cảnh, "
            "water ripple, fog/grade, bóng và dây/line. Preset Water Museum mô phỏng ánh sáng xanh, "
            "bàn/pool dạng trapezoid và dây câu như video tham chiếu."
        )
        help_label.setObjectName("AssetHelpText")
        help_label.setWordWrap(True)
        layout.addWidget(help_label)

        preset_row = QHBoxLayout()
        self.scene25d_preset = QComboBox()
        self.scene25d_preset.addItems([
            "Water Museum / Green Pool",
            "Billboard / Character",
            "Perspective Plane / Floor",
            "Fishing Rope / Line",
        ])
        preset_button = QPushButton("Áp preset")
        preset_button.clicked.connect(self._apply_scene25d_preset)
        preset_row.addWidget(self.scene25d_preset, 1)
        preset_row.addWidget(preset_button)
        layout.addLayout(preset_row)

        form = QFormLayout()
        self.scene25d_role = QComboBox()
        for label, value in (
            ("Billboard / sprite theo depth", "billboard"),
            ("Perspective Plane", "perspective_plane"),
            ("Water Surface", "water_surface"),
            ("Light / Glow sprite", "light"),
            ("Shadow sprite", "shadow"),
            ("Rope / Line", "rope"),
        ):
            self.scene25d_role.addItem(label, value)

        self.scene25d_pivot_x = QSpinBox(); self.scene25d_pivot_x.setRange(0, 100); self.scene25d_pivot_x.setValue(50); self.scene25d_pivot_x.setSuffix(" %")
        self.scene25d_pivot_y = QSpinBox(); self.scene25d_pivot_y.setRange(0, 100); self.scene25d_pivot_y.setValue(100); self.scene25d_pivot_y.setSuffix(" %")
        self.scene25d_world_w = QSpinBox(); self.scene25d_world_w.setRange(1, 2048); self.scene25d_world_w.setValue(32)
        self.scene25d_world_h = QSpinBox(); self.scene25d_world_h.setRange(1, 2048); self.scene25d_world_h.setValue(32)
        self.scene25d_fog_near = QSpinBox(); self.scene25d_fog_near.setRange(0, 4096); self.scene25d_fog_near.setValue(256)
        self.scene25d_fog_far = QSpinBox(); self.scene25d_fog_far.setRange(1, 8192); self.scene25d_fog_far.setValue(900)
        self.scene25d_fog_strength = QSpinBox(); self.scene25d_fog_strength.setRange(0, 255); self.scene25d_fog_strength.setValue(180)
        self.scene25d_fog_color = QLineEdit("#709174")
        self.scene25d_top_width = QSpinBox(); self.scene25d_top_width.setRange(1, 2048); self.scene25d_top_width.setValue(120)
        self.scene25d_bottom_width = QSpinBox(); self.scene25d_bottom_width.setRange(1, 2048); self.scene25d_bottom_width.setValue(330)
        self.scene25d_top_y = QSpinBox(); self.scene25d_top_y.setRange(-1024, 2048); self.scene25d_top_y.setValue(82)
        self.scene25d_bottom_y = QSpinBox(); self.scene25d_bottom_y.setRange(-1024, 2048); self.scene25d_bottom_y.setValue(248)
        self.scene25d_ripple = QSpinBox(); self.scene25d_ripple.setRange(0, 16); self.scene25d_ripple.setValue(1)
        self.scene25d_shadow_x = QSpinBox(); self.scene25d_shadow_x.setRange(0, 512); self.scene25d_shadow_x.setValue(12)
        self.scene25d_shadow_y = QSpinBox(); self.scene25d_shadow_y.setRange(0, 512); self.scene25d_shadow_y.setValue(4)
        self.scene25d_shadow_alpha = QSpinBox(); self.scene25d_shadow_alpha.setRange(0, 255); self.scene25d_shadow_alpha.setValue(96)
        self.scene25d_grade_alpha = QSpinBox(); self.scene25d_grade_alpha.setRange(0, 255); self.scene25d_grade_alpha.setValue(42)
        self.scene25d_vignette = QSpinBox(); self.scene25d_vignette.setRange(0, 255); self.scene25d_vignette.setValue(38)
        self.scene25d_dither = QSpinBox(); self.scene25d_dither.setRange(0, 64); self.scene25d_dither.setValue(6)

        form.addRow("Runtime role", self.scene25d_role)
        form.addRow("Pivot X", self.scene25d_pivot_x); form.addRow("Pivot Y", self.scene25d_pivot_y)
        form.addRow("World width", self.scene25d_world_w); form.addRow("World height", self.scene25d_world_h)
        form.addRow("Fog near Z", self.scene25d_fog_near); form.addRow("Fog far Z", self.scene25d_fog_far)
        form.addRow("Fog strength", self.scene25d_fog_strength); form.addRow("Fog / grade color", self.scene25d_fog_color)
        form.addRow("Plane top width", self.scene25d_top_width); form.addRow("Plane bottom width", self.scene25d_bottom_width)
        form.addRow("Plane top Y", self.scene25d_top_y); form.addRow("Plane bottom Y", self.scene25d_bottom_y)
        form.addRow("Water ripple", self.scene25d_ripple)
        form.addRow("Shadow radius X", self.scene25d_shadow_x); form.addRow("Shadow radius Y", self.scene25d_shadow_y)
        form.addRow("Shadow alpha", self.scene25d_shadow_alpha)
        form.addRow("Grade tint alpha", self.scene25d_grade_alpha)
        form.addRow("Vignette", self.scene25d_vignette); form.addRow("Dither", self.scene25d_dither)
        layout.addLayout(form)
        layout.addStretch()
        return tab

    def _apply_scene25d_preset(self) -> None:
        preset = self.scene25d_preset.currentText()
        if preset.startswith("Water Museum"):
            self.scene25d_role.setCurrentIndex(self.scene25d_role.findData("water_surface"))
            self.scene25d_fog_color.setText("#709174")
            self.scene25d_fog_near.setValue(220); self.scene25d_fog_far.setValue(900)
            self.scene25d_fog_strength.setValue(180)
            self.scene25d_top_width.setValue(120); self.scene25d_bottom_width.setValue(330)
            self.scene25d_top_y.setValue(82); self.scene25d_bottom_y.setValue(248)
            self.scene25d_ripple.setValue(1); self.scene25d_shadow_alpha.setValue(92)
            self.scene25d_grade_alpha.setValue(42); self.scene25d_vignette.setValue(38); self.scene25d_dither.setValue(6)
        elif preset.startswith("Billboard"):
            self.scene25d_role.setCurrentIndex(self.scene25d_role.findData("billboard"))
            self.scene25d_pivot_x.setValue(50); self.scene25d_pivot_y.setValue(100)
            self.scene25d_world_w.setValue(max(1, self.canvas.image.width()))
            self.scene25d_world_h.setValue(max(1, self.canvas.image.height()))
        elif preset.startswith("Perspective"):
            self.scene25d_role.setCurrentIndex(self.scene25d_role.findData("perspective_plane"))
            self.scene25d_ripple.setValue(0)
        else:
            self.scene25d_role.setCurrentIndex(self.scene25d_role.findData("rope"))
            self.scene25d_world_w.setValue(2); self.scene25d_world_h.setValue(2)
        self._set_status(f"Đã áp preset 2.5D: {preset}.")

    def _scene25d_metadata(self) -> dict:
        return {
            "role": str(self.scene25d_role.currentData() or "billboard"),
            "pivot_percent": [self.scene25d_pivot_x.value(), self.scene25d_pivot_y.value()],
            "pivot_q8": [round(self.scene25d_pivot_x.value() * 256 / 100), round(self.scene25d_pivot_y.value() * 256 / 100)],
            "world_size": [self.scene25d_world_w.value(), self.scene25d_world_h.value()],
            "fog": {
                "near_z": self.scene25d_fog_near.value(), "far_z": self.scene25d_fog_far.value(),
                "strength": self.scene25d_fog_strength.value(), "color": self.scene25d_fog_color.text().strip() or "#709174",
            },
            "plane": {
                "top_width": self.scene25d_top_width.value(), "bottom_width": self.scene25d_bottom_width.value(),
                "top_y": self.scene25d_top_y.value(), "bottom_y": self.scene25d_bottom_y.value(),
                "ripple_amplitude": self.scene25d_ripple.value(),
            },
            "shadow": {
                "radius_x": self.scene25d_shadow_x.value(), "radius_y": self.scene25d_shadow_y.value(),
                "alpha": self.scene25d_shadow_alpha.value(),
            },
            "grade": {
                "tint_alpha": self.scene25d_grade_alpha.value(), "vignette_alpha": self.scene25d_vignette.value(),
                "dither_strength": self.scene25d_dither.value(),
            },
        }

    def _load_scene25d_metadata(self, metadata: dict) -> None:
        cfg = metadata.get("scene25d") if isinstance(metadata.get("scene25d"), dict) else {}
        if not cfg:
            return
        role_index = self.scene25d_role.findData(str(cfg.get("role") or "billboard"))
        if role_index >= 0: self.scene25d_role.setCurrentIndex(role_index)
        pivot = cfg.get("pivot_percent") if isinstance(cfg.get("pivot_percent"), list) else [50, 100]
        if len(pivot) >= 2:
            self.scene25d_pivot_x.setValue(int(pivot[0])); self.scene25d_pivot_y.setValue(int(pivot[1]))
        size = cfg.get("world_size") if isinstance(cfg.get("world_size"), list) else [32, 32]
        if len(size) >= 2:
            self.scene25d_world_w.setValue(max(1, int(size[0]))); self.scene25d_world_h.setValue(max(1, int(size[1])))
        fog = cfg.get("fog") if isinstance(cfg.get("fog"), dict) else {}
        self.scene25d_fog_near.setValue(int(fog.get("near_z", 256))); self.scene25d_fog_far.setValue(int(fog.get("far_z", 900)))
        self.scene25d_fog_strength.setValue(int(fog.get("strength", 180))); self.scene25d_fog_color.setText(str(fog.get("color") or "#709174"))
        plane = cfg.get("plane") if isinstance(cfg.get("plane"), dict) else {}
        self.scene25d_top_width.setValue(int(plane.get("top_width", 120))); self.scene25d_bottom_width.setValue(int(plane.get("bottom_width", 330)))
        self.scene25d_top_y.setValue(int(plane.get("top_y", 82))); self.scene25d_bottom_y.setValue(int(plane.get("bottom_y", 248)))
        self.scene25d_ripple.setValue(int(plane.get("ripple_amplitude", 1)))
        shadow = cfg.get("shadow") if isinstance(cfg.get("shadow"), dict) else {}
        self.scene25d_shadow_x.setValue(int(shadow.get("radius_x", 12))); self.scene25d_shadow_y.setValue(int(shadow.get("radius_y", 4)))
        self.scene25d_shadow_alpha.setValue(int(shadow.get("alpha", 96)))
        grade = cfg.get("grade") if isinstance(cfg.get("grade"), dict) else {}
        self.scene25d_grade_alpha.setValue(int(grade.get("tint_alpha", 42)))
        self.scene25d_vignette.setValue(int(grade.get("vignette_alpha", 38)))
        self.scene25d_dither.setValue(int(grade.get("dither_strength", 6)))

    def _build_legacy_tab(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setObjectName("AssetLegacyScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        body = QWidget()
        layout = QVBoxLayout(body)
        layout.setContentsMargins(8, 10, 8, 10)
        layout.setSpacing(7)

        filter_row = QHBoxLayout()
        self.legacy_search = QLineEdit()
        self.legacy_search.setPlaceholderText("Tìm tên, role, tag…")
        self.legacy_search.setClearButtonEnabled(True)
        self.legacy_search.textChanged.connect(lambda _text: self._refresh_legacy_assets())
        filter_row.addWidget(self.legacy_search, 1)

        self.legacy_category_filter = QComboBox()
        self.legacy_category_filter.addItem("Tất cả", "")
        for category in LEGACY_CATEGORIES:
            self.legacy_category_filter.addItem(
                LEGACY_CATEGORY_LABELS.get(category, category.title()),
                category,
            )
        self.legacy_category_filter.currentIndexChanged.connect(
            lambda _index: self._refresh_legacy_assets()
        )
        filter_row.addWidget(self.legacy_category_filter)
        layout.addLayout(filter_row)

        count_row = QHBoxLayout()
        self.legacy_count_label = QLabel("0 asset")
        self.legacy_count_label.setObjectName("AssetHelpText")
        count_row.addWidget(self.legacy_count_label)
        count_row.addStretch()
        refresh = QToolButton()
        refresh.setIcon(icon("fa5s.sync-alt"))
        refresh.setToolTip("Đọc lại legacy_assets.catalog.json")
        refresh.clicked.connect(self._refresh_legacy_assets)
        count_row.addWidget(refresh)
        layout.addLayout(count_row)

        self.legacy_asset_list = QListWidget()
        self.legacy_asset_list.setViewMode(QListView.ViewMode.IconMode)
        self.legacy_asset_list.setResizeMode(QListView.ResizeMode.Adjust)
        self.legacy_asset_list.setMovement(QListView.Movement.Static)
        self.legacy_asset_list.setIconSize(QSize(72, 72))
        self.legacy_asset_list.setGridSize(QSize(112, 104))
        self.legacy_asset_list.setSpacing(4)
        self.legacy_asset_list.setWordWrap(True)
        self.legacy_asset_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.legacy_asset_list.setMinimumHeight(210)
        self.legacy_asset_list.currentItemChanged.connect(self._legacy_selection_changed)
        self.legacy_asset_list.itemDoubleClicked.connect(self._legacy_open_item)
        layout.addWidget(self.legacy_asset_list)

        self.legacy_preview = QLabel("Chọn một legacy asset")
        self.legacy_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.legacy_preview.setMinimumHeight(126)
        self.legacy_preview.setObjectName("AssetInfoLabel")
        layout.addWidget(self.legacy_preview)

        form = QFormLayout()
        self.legacy_category_edit = QComboBox()
        for category in LEGACY_CATEGORIES:
            self.legacy_category_edit.addItem(
                LEGACY_CATEGORY_LABELS.get(category, category.title()),
                category,
            )
        self.legacy_display_name = QLineEdit()
        self.legacy_display_name.setPlaceholderText("Tên hiển thị")
        self.legacy_role = QLineEdit()
        self.legacy_role.setPlaceholderText("vd: player_idle, water_band, hud_icon")
        self.legacy_tags = QLineEdit()
        self.legacy_tags.setPlaceholderText("hero, idle, combat")
        self.legacy_notes = QTextEdit()
        self.legacy_notes.setPlaceholderText("Ghi chú metadata…")
        self.legacy_notes.setFixedHeight(58)

        self.legacy_target_label = QLabel("—")
        self.legacy_target_label.setWordWrap(True)
        self.legacy_target_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.legacy_pair_label = QLabel("—")
        self.legacy_pair_label.setWordWrap(True)
        self.legacy_pair_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.legacy_hash_label = QLabel("—")
        self.legacy_hash_label.setWordWrap(True)
        self.legacy_hash_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        form.addRow("Category", self.legacy_category_edit)
        form.addRow("Display name", self.legacy_display_name)
        form.addRow("Role", self.legacy_role)
        form.addRow("Tags", self.legacy_tags)
        form.addRow("Notes", self.legacy_notes)
        form.addRow("Target", self.legacy_target_label)
        form.addRow("Paired asset", self.legacy_pair_label)
        form.addRow("SHA-256", self.legacy_hash_label)
        layout.addLayout(form)

        buttons = QHBoxLayout()
        self.legacy_open_button = QPushButton("Mở trên canvas")
        self.legacy_open_button.setIcon(icon("fa5s.external-link-alt"))
        self.legacy_open_button.clicked.connect(self._legacy_open_item)
        self.legacy_open_button.setEnabled(False)
        buttons.addWidget(self.legacy_open_button)

        self.legacy_save_button = QPushButton("Lưu metadata")
        self.legacy_save_button.setIcon(icon("fa5s.save"))
        self.legacy_save_button.clicked.connect(self._legacy_save_metadata)
        self.legacy_save_button.setEnabled(False)
        buttons.addWidget(self.legacy_save_button)
        layout.addLayout(buttons)
        layout.addStretch()

        scroll.setWidget(body)
        return scroll

    def _legacy_icon_for_row(self, row: dict) -> QIcon:
        preview = resolve_legacy_preview(self.project_root, row)
        if preview is not None:
            try:
                stat = preview.stat()
                cache_key = f"{preview.as_posix()}:{stat.st_mtime_ns}:{stat.st_size}"
            except OSError:
                cache_key = preview.as_posix()
            cached = self._legacy_thumbnail_cache.get(cache_key)
            if cached is not None:
                return cached
            pixmap = QPixmap(str(preview))
            if not pixmap.isNull():
                thumb = QPixmap(76, 76)
                thumb.fill(Qt.GlobalColor.transparent)
                scaled = pixmap.scaled(
                    72,
                    72,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.FastTransformation,
                )
                painter = QPainter(thumb)
                painter.drawPixmap(
                    (thumb.width() - scaled.width()) // 2,
                    (thumb.height() - scaled.height()) // 2,
                    scaled,
                )
                painter.end()
                result = QIcon(thumb)
                self._legacy_thumbnail_cache[cache_key] = result
                return result
        category = str(row.get("category") or "misc")
        return icon(LEGACY_CATEGORY_ICONS.get(category, "fa5s.file"))

    def _legacy_row_for_target(self, target: str) -> dict | None:
        normalized = str(target or "").replace("\\", "/").strip("/")
        for row in self._legacy_catalog.get("assets", []):
            if not isinstance(row, dict):
                continue
            candidate = str(row.get("target") or "").replace("\\", "/").strip("/")
            if candidate == normalized:
                return row
        return None

    def _refresh_legacy_assets(self) -> None:
        if not hasattr(self, "legacy_asset_list"):
            return
        selected_target = self._legacy_selected_target
        current = self.legacy_asset_list.currentItem()
        if current is not None:
            selected_target = str(current.data(Qt.ItemDataRole.UserRole) or selected_target)
        try:
            self._legacy_catalog = load_legacy_catalog(self.project_root)
        except (OSError, ValueError, json.JSONDecodeError) as error:
            self._legacy_catalog = {"assets": []}
            self.legacy_asset_list.clear()
            self.legacy_count_label.setText("Catalog lỗi")
            self.legacy_preview.setText(f"Không thể đọc catalog:\n{error}")
            return

        rows = [row for row in self._legacy_catalog.get("assets", []) if isinstance(row, dict)]
        category_filter = str(self.legacy_category_filter.currentData() or "")
        query = self.legacy_search.text().strip().casefold()
        self.legacy_asset_list.blockSignals(True)
        self.legacy_asset_list.clear()
        restore_item = None
        shown = 0
        for row in rows:
            category = str(row.get("category") or "misc")
            if category_filter and category != category_filter:
                continue
            metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
            tags = metadata.get("tags") if isinstance(metadata.get("tags"), list) else []
            searchable = " ".join([
                str(row.get("source") or ""),
                str(row.get("target") or ""),
                category,
                str(metadata.get("display_name") or ""),
                str(metadata.get("role") or ""),
                " ".join(str(tag) for tag in tags),
                str(metadata.get("notes") or ""),
            ]).casefold()
            if query and query not in searchable:
                continue

            target = str(row.get("target") or "")
            display_name = str(metadata.get("display_name") or "").strip()
            name = display_name or Path(target).name or str(row.get("source") or "asset")
            item = QListWidgetItem(self._legacy_icon_for_row(row), name)
            item.setData(Qt.ItemDataRole.UserRole, target)
            pair = str(row.get("paired_asset") or "")
            tooltip = f"{target}\nCategory: {category}"
            if pair:
                tooltip += f"\nPaired: {pair}"
            item.setToolTip(tooltip)
            self.legacy_asset_list.addItem(item)
            shown += 1
            if target == selected_target:
                restore_item = item

        self.legacy_asset_list.blockSignals(False)
        self.legacy_count_label.setText(f"{shown}/{len(rows)} asset")
        if restore_item is not None:
            self.legacy_asset_list.setCurrentItem(restore_item)
        elif self.legacy_asset_list.count() > 0:
            self.legacy_asset_list.setCurrentRow(0)
        else:
            self._legacy_clear_metadata_editor()

    def _legacy_clear_metadata_editor(self) -> None:
        self._legacy_selected_target = ""
        if hasattr(self, "legacy_preview"):
            self.legacy_preview.setPixmap(QPixmap())
            self.legacy_preview.setText("Không có asset phù hợp bộ lọc")
        for widget_name in ("legacy_display_name", "legacy_role", "legacy_tags"):
            widget = getattr(self, widget_name, None)
            if widget is not None:
                widget.clear()
        if hasattr(self, "legacy_notes"):
            self.legacy_notes.clear()
        if hasattr(self, "legacy_target_label"):
            self.legacy_target_label.setText("—")
            self.legacy_pair_label.setText("—")
            self.legacy_hash_label.setText("—")
            self.legacy_open_button.setEnabled(False)
            self.legacy_save_button.setEnabled(False)

    def _legacy_selection_changed(self, current: QListWidgetItem | None, _previous=None) -> None:
        if current is None:
            self._legacy_clear_metadata_editor()
            return
        target = str(current.data(Qt.ItemDataRole.UserRole) or "")
        row = self._legacy_row_for_target(target)
        if row is None:
            self._legacy_clear_metadata_editor()
            return
        self._legacy_selected_target = target
        metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
        category = str(row.get("category") or "misc")
        category_index = self.legacy_category_edit.findData(category)
        if category_index >= 0:
            self.legacy_category_edit.setCurrentIndex(category_index)
        self.legacy_display_name.setText(str(metadata.get("display_name") or ""))
        self.legacy_role.setText(str(metadata.get("role") or ""))
        tags = metadata.get("tags") if isinstance(metadata.get("tags"), list) else []
        self.legacy_tags.setText(", ".join(str(tag) for tag in tags))
        self.legacy_notes.setPlainText(str(metadata.get("notes") or ""))
        self.legacy_target_label.setText(target or "—")
        self.legacy_pair_label.setText(str(row.get("paired_asset") or "—"))
        sha = str(row.get("sha256") or "")
        self.legacy_hash_label.setText((sha[:16] + "…") if len(sha) > 18 else (sha or "—"))
        self.legacy_hash_label.setToolTip(sha)

        preview = resolve_legacy_preview(self.project_root, row)
        self.legacy_open_button.setEnabled(preview is not None)
        self.legacy_save_button.setEnabled(True)
        self.legacy_preview.setPixmap(QPixmap())
        if preview is not None:
            pixmap = QPixmap(str(preview))
            if not pixmap.isNull():
                scaled = pixmap.scaled(
                    190,
                    120,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.FastTransformation,
                )
                self.legacy_preview.setPixmap(scaled)
                self.legacy_preview.setToolTip(str(preview))
                return
        self.legacy_preview.setText(
            f"{LEGACY_CATEGORY_LABELS.get(category, category.title())}\n{Path(target).name}"
        )
        self.legacy_preview.setToolTip(target)

    def _legacy_open_item(self, item=None) -> None:
        if isinstance(item, QListWidgetItem):
            target = str(item.data(Qt.ItemDataRole.UserRole) or "")
        else:
            target = self._legacy_selected_target
        row = self._legacy_row_for_target(target)
        if row is None:
            return
        preview = resolve_legacy_preview(self.project_root, row)
        if preview is None:
            self._set_status("Asset này không có preview ảnh để mở trên canvas.", error=True)
            return
        self.load_image(preview)
        pair = str(row.get("paired_asset") or "")
        if pair and Path(target).suffix.lower() not in IMAGE_EXTENSIONS:
            self._set_status(f"Đã mở paired preview: {pair}")
        else:
            self._set_status(f"Đã mở legacy asset: {target}")

    def _legacy_save_metadata(self) -> None:
        target = self._legacy_selected_target
        if not target:
            return
        category = str(self.legacy_category_edit.currentData() or "misc")
        raw_tags = self.legacy_tags.text().replace(";", ",").replace("\n", ",")
        tags = [value.strip() for value in raw_tags.split(",") if value.strip()]
        try:
            update_legacy_asset_metadata(
                self.project_root,
                target,
                category=category,
                display_name=self.legacy_display_name.text(),
                role=self.legacy_role.text(),
                tags=tags,
                notes=self.legacy_notes.toPlainText(),
            )
        except (OSError, ValueError, KeyError, json.JSONDecodeError) as error:
            NoticeDialog("Không thể lưu metadata", str(error), self, error=True).exec()
            return
        self._legacy_selected_target = target
        active_filter = str(self.legacy_category_filter.currentData() or "")
        if active_filter and active_filter != category:
            self.legacy_category_filter.setCurrentIndex(0)
        else:
            self._refresh_legacy_assets()
        self._set_status(f"Đã lưu metadata legacy: {Path(target).name}")

    def _build_export_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(10, 12, 10, 10)
        note = QLabel("VXPEngine chỉ cho phép lưu vào các nhánh assets có sẵn để không làm hỏng cấu trúc CMake/resources của project VXP.")
        note.setWordWrap(True)
        note.setObjectName("AssetHelpText")
        layout.addWidget(note)
        form = QFormLayout()
        self.asset_name = QLineEdit("new_asset.png")
        self.destination_combo = QComboBox()
        for label, relative in IMAGE_DESTINATIONS:
            self.destination_combo.addItem(label, relative)
        self.metadata_name = QLineEdit("new_asset.asset.dtfe")
        self.animation_metadata_name = QLineEdit(f"new_asset{ANIMATION_SUFFIX}")
        self.pixels_per_unit = QSpinBox(); self.pixels_per_unit.setRange(1, 4096); self.pixels_per_unit.setValue(100)
        self.render_mode = QComboBox(); self.render_mode.addItems(["Nearest / Pixel", "Linear / Smooth"])
        form.addRow("Tên PNG", self.asset_name)
        form.addRow("Thư mục codebase", self.destination_combo)
        form.addRow("Metadata asset", self.metadata_name)
        form.addRow("Animation .ani..dtfe", self.animation_metadata_name)
        form.addRow("Pixels per unit", self.pixels_per_unit)
        form.addRow("Render mode", self.render_mode)
        layout.addLayout(form)
        self.write_metadata = QCheckBox("Lưu frame, collision, grid và cấu hình texture")
        self.write_metadata.setChecked(True)
        self.write_animation = QCheckBox("Lưu timeline animation dạng tên_assets.ani..dtfe")
        self.write_animation.setChecked(True)
        self.allow_overwrite = QCheckBox("Cho phép ghi đè tệp cùng tên")
        layout.addWidget(self.write_metadata)
        layout.addWidget(self.write_animation)
        layout.addWidget(self.allow_overwrite)
        self.export_preview = QLabel()
        self.export_preview.setObjectName("AssetExportPreview")
        self.export_preview.setWordWrap(True)
        layout.addWidget(self.export_preview)
        self.asset_name.textChanged.connect(self._sync_generated_names)
        self.asset_name.textChanged.connect(self._update_export_preview)
        self.destination_combo.currentIndexChanged.connect(self._update_export_preview)
        layout.addStretch()
        return tab

    def _build_frame_strip(self) -> QWidget:
        host = QWidget()
        host.setObjectName("AssetFrameStrip")
        self._frame_strip_widget = host
        host.setFixedHeight(230)
        layout = QHBoxLayout(host)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(8)

        title_box = QVBoxLayout()
        title_box.addWidget(self._section_label("ANIMATION"))
        self.animation_name = QLineEdit("default")
        self.animation_name.setPlaceholderText("Tên animation")
        title_box.addWidget(self.animation_name)
        self.animation_fps = QSpinBox(); self.animation_fps.setRange(1, 240); self.animation_fps.setValue(10); self.animation_fps.setSuffix(" FPS")
        title_box.addWidget(self.animation_fps)
        self.animation_loop = QCheckBox("Loop")
        self.animation_loop.setChecked(True)
        title_box.addWidget(self.animation_loop)
        play_row = QHBoxLayout()
        self.play_button = QPushButton("Phát")
        self.play_button.setIcon(icon("fa5s.play"))
        self.play_button.clicked.connect(self.toggle_playback)
        stop_button = QPushButton()
        stop_button.setIcon(icon("fa5s.stop"))
        stop_button.setToolTip("Dừng xem trước")
        stop_button.clicked.connect(self.stop_playback)
        play_row.addWidget(self.play_button, 1)
        play_row.addWidget(stop_button)
        title_box.addLayout(play_row)
        title_box.addStretch()
        layout.addLayout(title_box)

        self.timeline_tabs = QTabWidget()
        self.timeline_tabs.setDocumentMode(True)

        atlas_page = QWidget()
        atlas_layout = QVBoxLayout(atlas_page)
        atlas_layout.setContentsMargins(4, 4, 4, 4)
        atlas_help = QLabel("Atlas Frames: các ô được cắt từ spritesheet/tileset hiện tại.")
        atlas_help.setObjectName("AssetHelpText")
        atlas_layout.addWidget(atlas_help)
        self.frame_list = QListWidget()
        self.frame_list.setViewMode(QListView.ViewMode.IconMode)
        self.frame_list.setFlow(QListView.Flow.LeftToRight)
        self.frame_list.setResizeMode(QListView.ResizeMode.Adjust)
        self.frame_list.setMovement(QListView.Movement.Static)
        self.frame_list.setIconSize(QSize(62, 62))
        self.frame_list.setSpacing(5)
        self.frame_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.frame_list.currentRowChanged.connect(self._frame_selected)
        atlas_layout.addWidget(self.frame_list, 1)
        self.timeline_tabs.addTab(atlas_page, icon("fa5s.border-all"), "Atlas Frames")

        scene_page = QWidget()
        scene_layout = QVBoxLayout(scene_page)
        scene_layout.setContentsMargins(4, 4, 4, 4)
        scene_help = QLabel("Scene Timeline: mỗi thumbnail là một ảnh đầy đủ của cảnh/nhân vật. Áp dụng sẽ tạo spritesheet *_ani.png, các PNG frame và tệp điều khiển *.ani..dtfe cho VXP.")
        scene_help.setObjectName("AssetHelpText"); scene_help.setWordWrap(True)
        scene_layout.addWidget(scene_help)
        controls = QHBoxLayout()
        scene_actions = [
            ("Thêm Scene", "fa5s.plus", self.capture_scene, "Alt+Insert"),
            ("Nạp Scene", "fa5s.edit", self.load_scene_to_canvas, "Alt+Enter"),
            ("Cập nhật Scene", "fa5s.sync-alt", self.update_scene, "Alt+U"),
            ("Nhân đôi Scene", "fa5s.copy", self.duplicate_scene, "Alt+D"),
            ("Đưa Scene sang trái", "fa5s.arrow-left", lambda: self._move_scene(-1), "Alt+Left"),
            ("Đưa Scene sang phải", "fa5s.arrow-right", lambda: self._move_scene(1), "Alt+Right"),
            ("Xóa Scene", "fa5s.trash-alt", self.delete_scene, "Alt+Delete"),
        ]
        for title, icon_name, callback, shortcut in scene_actions:
            button = QToolButton()
            button.setIcon(icon(icon_name))
            self._make_icon_button(button, title, self._format_shortcut_tooltip(title, shortcut))
            button.clicked.connect(callback)
            controls.addWidget(button)
            self._editor_tool_buttons.append(button)
        controls.addStretch()
        self.scene_duration = QSpinBox()
        self.scene_duration.setRange(1, 60000)
        self.scene_duration.setValue(100)
        self.scene_duration.setSuffix(" ms")
        self.scene_duration.setToolTip("Thời lượng của Scene được thêm/cập nhật")
        self.scene_duration.valueChanged.connect(self._scene_duration_changed)
        controls.addWidget(QLabel("Duration"))
        controls.addWidget(self.scene_duration)
        scene_layout.addLayout(controls)

        advanced = QHBoxLayout()
        advanced_actions = [
            ("Nhập nhiều ảnh", "fa5s.file-import", self.import_scene_frames),
            ("Đảo timeline", "fa5s.exchange-alt", self.reverse_scene_timeline),
            ("Tạo Ping-Pong", "fa5s.retweet", self.make_scene_ping_pong),
            ("Cắt alpha", "fa5s.crop-alt", self.trim_scene_frames),
            ("Chuẩn hóa size", "fa5s.expand-arrows-alt", self.normalize_scene_frames),
            ("Lật frame chọn", "fa5s.arrows-alt-h", self.flip_selected_scene),
        ]
        for title, icon_name, callback in advanced_actions:
            button = QToolButton(); button.setIcon(icon(icon_name))
            self._make_icon_button(button, title, title)
            button.clicked.connect(callback); advanced.addWidget(button)
            self._editor_tool_buttons.append(button)
        self.onion_skin = QCheckBox("Onion Skin")
        self.onion_skin.setToolTip("Hiện mờ frame trước để căn chuyển động pixel")
        self.onion_skin.toggled.connect(self._update_onion_skin)
        advanced.addWidget(self.onion_skin)
        self.scene_target = QComboBox()
        self.scene_target.addItem("Nhân vật", "character")
        self.scene_target.addItem("Cảnh", "scene")
        self.scene_target.addItem("UI", "ui")
        self.scene_target.addItem("Hiệu ứng", "effect")
        self.scene_target.setToolTip("Loại animation được ghi trong .ani..dtfe")
        advanced.addWidget(self.scene_target)
        self.scene_name_edit = QLineEdit(); self.scene_name_edit.setPlaceholderText("Tên frame")
        self.scene_name_edit.setMaximumWidth(120)
        self.scene_name_edit.editingFinished.connect(self.rename_selected_scene)
        advanced.addWidget(self.scene_name_edit)
        advanced.addStretch()
        scene_layout.addLayout(advanced)

        self.scene_list = QListWidget()
        self.scene_list.setViewMode(QListView.ViewMode.IconMode)
        self.scene_list.setFlow(QListView.Flow.LeftToRight)
        self.scene_list.setResizeMode(QListView.ResizeMode.Adjust)
        self.scene_list.setMovement(QListView.Movement.Static)
        self.scene_list.setIconSize(QSize(76, 76))
        self.scene_list.setSpacing(5)
        self.scene_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.scene_list.currentRowChanged.connect(self._scene_selected)
        scene_layout.addWidget(self.scene_list, 1)
        self.timeline_tabs.addTab(scene_page, icon("fa5s.film"), "Scene Timeline")

        layout.addWidget(self.timeline_tabs, 1)
        return host

    def _animation_sources(self) -> dict[str, list[AnimationPreviewFrame]]:
        atlas_frames = [
            AnimationPreviewFrame(
                frame.name,
                self.canvas.image.copy(frame.rect),
                max(1, int(frame.duration_ms)),
            )
            for frame in self.canvas.frames
            if not frame.rect.isNull()
        ]
        scene_frames = [
            AnimationPreviewFrame(record.name, record.image.copy(), max(1, int(record.duration_ms)))
            for record in self.scene_frames
        ]
        return {"atlas_frames": atlas_frames, "scene_timeline": scene_frames}

    def _normalized_player_settings(self) -> dict:
        sources = self._animation_sources()
        settings = dict(self.animation_player_settings)
        selected_by_source = settings.get("selected_by_source")
        if not isinstance(selected_by_source, dict):
            selected_by_source = {}
        normalized: dict[str, list[int]] = {}
        for key, frames in sources.items():
            configured = selected_by_source.get(key)
            if isinstance(configured, list):
                values = sorted({int(index) for index in configured if isinstance(index, int) and 0 <= index < len(frames)})
            else:
                values = []
            if not values and frames:
                values = list(range(len(frames)))
            normalized[key] = values
        settings["selected_by_source"] = normalized
        source = str(settings.get("source_mode") or "atlas_frames")
        if not sources.get(source):
            source = "scene_timeline" if sources.get("scene_timeline") else "atlas_frames"
        settings["source_mode"] = source
        settings["selected_indices"] = list(normalized.get(source, []))
        settings["fps"] = max(1, min(60, int(settings.get("fps", self.animation_fps.value()))))
        settings["loop"] = bool(settings.get("loop", self.animation_loop.isChecked()))
        settings["background"] = str(settings.get("background") or "checker")
        settings["preview_zoom"] = max(1, min(8, int(settings.get("preview_zoom", 1))))
        return settings

    def open_animation_player(self) -> None:
        sources = self._animation_sources()
        if not sources["atlas_frames"] and not sources["scene_timeline"]:
            self._set_status(
                "Chưa có frame animation. Hãy Chia ô tự động hoặc thêm Scene vào Timeline trước.",
                error=True,
            )
            return
        settings = self._normalized_player_settings()
        if self.animation_player_window is not None:
            try:
                self.animation_player_window.close()
            except RuntimeError:
                pass
        player = AnimationPlayerWindow(sources, settings, parent=self)
        player.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        player.settings_applied.connect(self._apply_animation_player_settings)
        player.destroyed.connect(self._animation_player_destroyed)
        self.animation_player_window = player
        player.show()
        player.raise_()
        player.activateWindow()

    def _animation_player_destroyed(self, _object=None) -> None:
        self.animation_player_window = None

    def _apply_animation_player_settings(self, payload: dict) -> None:
        if not isinstance(payload, dict):
            return
        self.animation_player_settings.update(payload)
        self.animation_fps.setValue(max(1, int(payload.get("fps", self.animation_fps.value()))))
        self.animation_loop.setChecked(bool(payload.get("loop", self.animation_loop.isChecked())))
        source_label = "Atlas Frames" if payload.get("source_mode") == "atlas_frames" else "Scene Timeline"
        selected = payload.get("selected_indices") if isinstance(payload.get("selected_indices"), list) else []
        self._set_status(
            f"Anim Player: đã chọn {len(selected)} frame từ {source_label} ở {self.animation_fps.value()} FPS. "
            "Nhấn Áp dụng & lưu để ghi .ani..dtfe."
        )

    def _build_footer(self) -> QWidget:
        footer = QWidget()
        footer.setObjectName("AssetEditorFooter")
        layout = QHBoxLayout(footer)
        layout.setContentsMargins(10, 7, 10, 7)
        self.status_label = QLabel("Sẵn sàng")
        self.status_label.setObjectName("AssetEditorStatus")
        layout.addWidget(self.status_label, 1)
        cancel = QPushButton("Hủy")
        cancel.setObjectName("GhostBtn")
        cancel.setIcon(icon("fa5s.times"))
        cancel.clicked.connect(self.reject)
        apply_button = QPushButton("Áp dụng & lưu")
        apply_button.setObjectName("AccentBtn")
        apply_button.setIcon(icon("fa5s.check"))
        apply_button.setToolTip("Lưu PNG, metadata asset và tên_assets.ani..dtfe")
        apply_button.clicked.connect(self.save_and_apply)
        layout.addWidget(cancel)
        layout.addWidget(apply_button)
        return footer

    @staticmethod
    def _separator() -> QFrame:
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.VLine)
        separator.setObjectName("ToolbarSeparator")
        separator.setFixedHeight(24)
        return separator

    @staticmethod
    def _section_label(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("AssetSectionLabel")
        return label

    # ---------- document/history ----------
    def _snapshot(self) -> EditorSnapshot:
        return EditorSnapshot(
            image=self.canvas.image.copy(),
            frames=[FrameRecord(frame.name, QRect(frame.rect), frame.duration_ms) for frame in self.canvas.frames],
            collisions=[CollisionRecord(item.name, QRect(item.rect), item.kind) for item in self.canvas.collisions],
            selection=QRect(self.canvas.selection),
            scene_frames=[SceneFrameRecord(frame.name, QImage(frame.image), frame.duration_ms) for frame in self.scene_frames],
            selected_scene=self.selected_scene,
            player_settings=copy.deepcopy(self.animation_player_settings),
            fps=self.animation_fps.value(), loop=self.animation_loop.isChecked(),
            write_animation=self.write_animation.isChecked(),
        )

    def _restore(self, snapshot: EditorSnapshot) -> None:
        self.canvas.image = snapshot.image.copy()
        self.canvas.frames = [FrameRecord(frame.name, QRect(frame.rect), frame.duration_ms) for frame in snapshot.frames]
        self.canvas.collisions = [CollisionRecord(item.name, QRect(item.rect), item.kind) for item in snapshot.collisions]
        self.canvas.selection = QRect(snapshot.selection)
        self.scene_frames = [SceneFrameRecord(frame.name, QImage(frame.image), frame.duration_ms) for frame in snapshot.scene_frames]
        self.selected_scene = snapshot.selected_scene
        self.animation_player_settings = copy.deepcopy(snapshot.player_settings)
        self.animation_fps.setValue(snapshot.fps)
        self.animation_loop.setChecked(snapshot.loop)
        self.write_animation.setChecked(snapshot.write_animation)
        self._refresh_all()

    def _push_undo(self) -> None:
        if self.playback_timer.isActive() or self._playback_backup is not None:
            self.stop_playback()
        self._undo.append(self._snapshot())
        if len(self._undo) > self._max_history:
            self._undo.pop(0)
        self._redo.clear()
        self._update_history_buttons()

    def undo(self) -> None:
        if not self._undo:
            return
        self._redo.append(self._snapshot())
        self._restore(self._undo.pop())
        self._update_history_buttons()
        self._set_status("Đã Undo thao tác gần nhất.")

    def redo(self) -> None:
        if not self._redo:
            return
        self._undo.append(self._snapshot())
        self._restore(self._redo.pop())
        self._update_history_buttons()
        self._set_status("Đã Redo thao tác.")

    def _update_history_buttons(self) -> None:
        self.undo_button.setEnabled(bool(self._undo))
        self.redo_button.setEnabled(bool(self._redo))

    # ---------- file/canvas operations ----------
    def new_canvas(self) -> None:
        dialog = NewCanvasDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self._push_undo()
        self.stop_playback()
        self.current_source = None
        self.scene_frames.clear()
        self.selected_scene = -1
        self.canvas.new_image(dialog.width_spin.value(), dialog.height_spin.value(), dialog.transparent.isChecked())
        self.tile_w.setValue(dialog.tile_w_spin.value())
        self.tile_h.setValue(dialog.tile_h_spin.value())
        self.resize_w.setValue(self.canvas.image.width())
        self.resize_h.setValue(self.canvas.image.height())
        self.asset_name.setText("new_asset.png")
        self._refresh_scenes()
        self._update_document_title("Tài nguyên chưa lưu")
        self._set_status("Đã tạo canvas trong suốt mới.")

    def import_image(self) -> None:
        path, _selected_filter = QFileDialog.getOpenFileName(
            self,
            "Nhập ảnh vào Editor Assets",
            str(Path.home()),
            "Ảnh / VPE (*.png *.jpg *.jpeg *.webp *.bmp *.gif *.svg *.vpe *.vpea);;Tất cả tệp (*.*)",
        )
        if path:
            self.load_image(Path(path))

    def import_legacy_res_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(
            self,
            "Nhập thư mục res/ MRE cũ",
            str(Path.home()),
        )
        if not folder:
            return
        try:
            result = import_legacy_res(Path(folder), self.project_root)
        except (OSError, ValueError) as error:
            NoticeDialog("Không thể nhập resource", str(error), self, error=True).exec()
            return
        counts = result.get("counts", {})
        summary = ", ".join(f"{key}={value}" for key, value in sorted(counts.items()))
        self._refresh_scenes()
        self._legacy_thumbnail_cache.clear()
        self._refresh_legacy_assets()
        self._set_status(
            f"Đã nhập {len(result.get('assets', []))} resource legacy. {summary}"
        )

    def load_image(self, path: Path) -> None:
        if path.suffix.lower() in (".vpe", ".vpea"):
            try:
                if self.vpe_pixel.open_native(path):
                    self.workspace_tabs.setCurrentIndex(1)
            except (OSError, ValueError) as error:
                self._set_status(f"Không thể mở VPE: {error}", error=True)
            return
        self.stop_playback()
        descriptor_override: Path | None = None
        if path.name.lower().endswith((ANIMATION_SUFFIX, LEGACY_ANIMATION_SUFFIX)):
            try:
                descriptor_payload = json.loads(path.read_text(encoding="utf-8"))
                asset_rel = str(descriptor_payload.get("asset") or "") if isinstance(descriptor_payload, dict) else ""
                asset_path = (self.project_root / asset_rel).resolve()
                asset_path.relative_to(self.project_root)
                if not asset_path.is_file():
                    raise OSError(f"Không tìm thấy ảnh gốc {asset_rel}")
                descriptor_override, path = path.resolve(), asset_path
            except (OSError, ValueError, json.JSONDecodeError, TypeError) as error:
                NoticeDialog("Không thể đọc animation", f"Tệp .ani..dtfe không hợp lệ:\n{error}", self, error=True).exec()
                return
        image = QImage(str(path))
        if image.isNull():
            NoticeDialog("Không thể đọc ảnh", f"VXPEngine không thể nạp tệp:\n{path}", self, error=True).exec()
            return
        self._push_undo()
        self.current_source = path.resolve()
        try:
            self.current_source.relative_to(self.project_root)
            self._editing_existing_project_asset = True
        except ValueError:
            self._editing_existing_project_asset = False
        self.canvas.set_image(image)
        self.asset_name.setText(path.stem + ".png")
        self.metadata_name.setText(path.stem + ".asset.dtfe")
        self.animation_metadata_name.setText(path.stem + ANIMATION_SUFFIX)
        try:
            parent_relative = path.resolve().parent.relative_to(self.project_root).as_posix()
        except ValueError:
            parent_relative = ""
        if parent_relative:
            self._apply_initial_destination(parent_relative)
        self.allow_overwrite.setChecked(self._editing_existing_project_asset)
        self.allow_overwrite.setToolTip(
            "Tài nguyên đang mở sẽ được ghi đè để Canvas/Preview cập nhật ngay."
            if self._editing_existing_project_asset
            else "Bật để ghi đè tệp trùng tên."
        )
        self.resize_w.setValue(image.width())
        self.resize_h.setValue(image.height())
        self._load_metadata_for_image(path)
        self._load_animation_for_image(path, descriptor_override)
        self._update_document_title(path.name)
        self._set_status(f"Đã nạp {path.name} — {image.width()} × {image.height()} px.")
        self._refresh_all()

    def _load_metadata_for_image(self, image_path: Path) -> None:
        try:
            relative = image_path.resolve().relative_to(self.project_root).as_posix()
        except ValueError:
            return
        adjacent = image_path.with_name(f"{image_path.stem}.asset.dtfe")
        legacy_root = self.project_root / "assets" / "data"
        candidates = [adjacent]
        if legacy_root.exists():
            legacy_candidate = legacy_root / f"{image_path.stem}.asset.dtfe"
            candidates.append(legacy_candidate)
            candidates.extend(path for path in legacy_root.glob("*.asset.dtfe") if path not in candidates)
        metadata = None
        for candidate in candidates:
            try:
                payload = json.loads(candidate.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError, TypeError):
                continue
            if isinstance(payload, dict) and str(payload.get("asset", "")) == relative:
                metadata = payload
                self.metadata_name.setText(candidate.name)
                break
        if not isinstance(metadata, dict):
            return

        asset_type = str(metadata.get("asset_type") or "")
        index = self.asset_type_combo.findText(asset_type)
        if index >= 0:
            self.asset_type_combo.setCurrentIndex(index)
        grid = metadata.get("grid") if isinstance(metadata.get("grid"), dict) else {}
        self.tile_w.setValue(int(grid.get("width", self.tile_w.value())))
        self.tile_h.setValue(int(grid.get("height", self.tile_h.value())))
        self.margin_spin.setValue(int(grid.get("margin", 0)))
        self.spacing_spin.setValue(int(grid.get("spacing", 0)))

        texture = metadata.get("texture") if isinstance(metadata.get("texture"), dict) else {}
        self.pixels_per_unit.setValue(int(texture.get("pixels_per_unit", 100)))
        self.render_mode.setCurrentIndex(0 if texture.get("render_mode", "nearest") == "nearest" else 1)
        self._set_pixel_mode(int(texture.get("pixel_mode_bits", 32)), activate=False)

        self._load_art_style_metadata(metadata)
        self._load_stage2d_metadata(metadata)
        self._load_scene25d_metadata(metadata)

        animation = metadata.get("animation") if isinstance(metadata.get("animation"), dict) else {}
        self.animation_name.setText(str(animation.get("name") or "default"))
        self.animation_fps.setValue(int(animation.get("fps", 10)))
        self.animation_loop.setChecked(bool(animation.get("loop", True)))

        frames: list[FrameRecord] = []
        for index, item in enumerate(metadata.get("frames", []), 1):
            if not isinstance(item, dict):
                continue
            rect = QRect(
                int(item.get("x", 0)), int(item.get("y", 0)),
                int(item.get("width", 0)), int(item.get("height", 0)),
            ).intersected(self.canvas.image.rect())
            if rect.width() > 0 and rect.height() > 0:
                frames.append(FrameRecord(str(item.get("name") or f"frame_{index:03d}"), rect, int(item.get("duration_ms", 100))))
        self.canvas.frames = frames

        collisions: list[CollisionRecord] = []
        for index, item in enumerate(metadata.get("collisions", []), 1):
            if not isinstance(item, dict):
                continue
            rect = QRect(
                int(item.get("x", 0)), int(item.get("y", 0)),
                int(item.get("width", 0)), int(item.get("height", 0)),
            ).intersected(self.canvas.image.rect())
            if rect.width() > 0 and rect.height() > 0:
                collisions.append(CollisionRecord(str(item.get("name") or f"collision_{index:02d}"), rect, str(item.get("kind") or "solid")))
        self.canvas.collisions = collisions
        self.canvas.selected_frame = 0 if frames else -1
        self.canvas.selected_collision = 0 if collisions else -1

    def _load_animation_for_image(self, image_path: Path, descriptor_override: Path | None = None) -> None:
        """Restore a timeline from the canonical or legacy descriptor name."""
        try:
            image_path.resolve().relative_to(self.project_root)
        except ValueError:
            self.scene_frames.clear()
            self.selected_scene = -1
            return
        scene_root = self.project_root / "assets" / "scenes"
        legacy_root = self.project_root / "assets" / "data"
        candidates = [
            scene_root / f"{image_path.stem}{ANIMATION_SUFFIX}",
            scene_root / f"{image_path.stem}{LEGACY_ANIMATION_SUFFIX}",
            legacy_root / f"{image_path.stem}{ANIMATION_SUFFIX}",
            legacy_root / f"{image_path.stem}{LEGACY_ANIMATION_SUFFIX}",
        ]
        descriptor = descriptor_override or next((candidate for candidate in candidates if candidate.exists()), None)
        if descriptor is None:
            self.scene_frames.clear()
            self.selected_scene = -1
            return
        try:
            payload = json.loads(descriptor.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, TypeError):
            return
        if not isinstance(payload, dict):
            return
        animation = payload.get("animation") if isinstance(payload.get("animation"), dict) else {}
        self.animation_name.setText(str(animation.get("name") or self.animation_name.text()))
        self.animation_fps.setValue(max(1, int(animation.get("fps", self.animation_fps.value()))))
        self.animation_loop.setChecked(bool(animation.get("loop", self.animation_loop.isChecked())))
        source_mode = str(payload.get("source_mode") or animation.get("source_mode") or "atlas_frames")
        selected_indices = animation.get("selected_indices")
        if not isinstance(selected_indices, list):
            selected_indices = payload.get("selected_indices") if isinstance(payload.get("selected_indices"), list) else []
        selected_by_source = animation.get("selected_by_source")
        if not isinstance(selected_by_source, dict):
            selected_by_source = {source_mode: selected_indices}
        self.animation_player_settings.update({
            "source_mode": source_mode,
            "selected_indices": [int(value) for value in selected_indices if isinstance(value, int)],
            "selected_by_source": selected_by_source,
            "selection_mask_hex": str(animation.get("selection_mask_hex") or payload.get("selection_mask_hex") or ""),
            "fps": self.animation_fps.value(),
            "loop": self.animation_loop.isChecked(),
            "background": str(animation.get("preview_background") or payload.get("preview_background") or "checker"),
            "preview_zoom": max(1, int(animation.get("preview_zoom", payload.get("preview_zoom", 1)))),
        })
        asset_kind = str(payload.get("asset_kind") or animation.get("asset_kind") or "character")
        target_index = self.scene_target.findData(asset_kind)
        if target_index >= 0:
            self.scene_target.setCurrentIndex(target_index)
        if source_mode != "scene_timeline":
            self._sync_animation_player_selection("atlas_frames", len(self.canvas.frames))
            return
        texture_rel = str(payload.get("texture") or "")
        texture_path = (self.project_root / texture_rel).resolve()
        try:
            texture_path.relative_to(self.project_root)
        except ValueError:
            return
        sheet = QImage(str(texture_path))
        if sheet.isNull():
            return
        restored: list[SceneFrameRecord] = []
        for index, item in enumerate(payload.get("frames", []), 1):
            if not isinstance(item, dict):
                continue
            rect = QRect(
                int(item.get("x", 0)), int(item.get("y", 0)),
                int(item.get("width", 0)), int(item.get("height", 0)),
            ).intersected(sheet.rect())
            if rect.width() <= 0 or rect.height() <= 0:
                continue
            frame_image = sheet.copy(rect)
            content_rect = QRect(
                int(item.get("content_x", 0)), int(item.get("content_y", 0)),
                int(item.get("content_width", rect.width())), int(item.get("content_height", rect.height())),
            ).intersected(frame_image.rect())
            if content_rect.width() > 0 and content_rect.height() > 0:
                frame_image = frame_image.copy(content_rect)
            restored.append(SceneFrameRecord(
                str(item.get("name") or f"scene_{index:03d}"),
                frame_image,
                max(1, int(item.get("duration_ms", 100))),
            ))
        self.scene_frames = restored
        self.selected_scene = 0 if restored else -1
        self.animation_metadata_name.setText(descriptor.name)
        self._refresh_scenes()
        self._sync_animation_player_selection("scene_timeline", len(self.scene_frames))

    def insert_image(self) -> None:
        path, _selected_filter = QFileDialog.getOpenFileName(
            self,
            "Ghép ảnh/layer vào canvas",
            str(Path.home()),
            "Ảnh 2D (*.png *.jpg *.jpeg *.webp *.bmp *.gif *.svg)",
        )
        if not path:
            return
        overlay = QImage(path).convertToFormat(QImage.Format.Format_RGBA8888)
        if overlay.isNull():
            return
        self._push_undo()
        painter = QPainter(self.canvas.image)
        x = (self.canvas.image.width() - overlay.width()) // 2
        y = (self.canvas.image.height() - overlay.height()) // 2
        painter.drawImage(x, y, overlay)
        painter.end()
        self.canvas.image_changed.emit()
        self.canvas.update()
        self._set_status(f"Đã ghép {Path(path).name} vào giữa canvas.")

    def _show_canvas_context_menu(self, position: QPoint) -> None:
        menu = QMenu(self.canvas)
        selection = self.canvas.selection.intersected(self.canvas.image.rect())
        has_selection = selection.width() > 0 and selection.height() > 0

        copy_action = QAction(icon("fa5s.copy"), "Sao chép vùng chọn", menu)
        copy_action.setShortcut(QKeySequence.StandardKey.Copy)
        copy_action.setEnabled(has_selection)
        copy_action.triggered.connect(self.copy_selection)
        menu.addAction(copy_action)

        cut_action = QAction(icon("fa5s.cut"), "Cắt vùng chọn", menu)
        cut_action.setShortcut(QKeySequence.StandardKey.Cut)
        cut_action.setEnabled(has_selection)
        cut_action.triggered.connect(self.cut_selection)
        menu.addAction(cut_action)

        paste_action = QAction(icon("fa5s.paste"), "Dán ảnh", menu)
        paste_action.setShortcut(QKeySequence.StandardKey.Paste)
        paste_action.setEnabled(not QApplication.clipboard().image().isNull())
        paste_action.triggered.connect(self.paste_selection)
        menu.addAction(paste_action)

        delete_action = QAction(icon("fa5s.trash-alt"), "Xóa vùng chọn", menu)
        delete_action.setShortcut(QKeySequence.StandardKey.Delete)
        delete_action.setEnabled(has_selection)
        delete_action.triggered.connect(self.delete_selection)
        menu.addAction(delete_action)
        menu.addSeparator()

        crop_action = QAction(icon("fa5s.crop-alt"), "Cắt canvas theo vùng chọn", menu)
        crop_action.setEnabled(has_selection)
        crop_action.triggered.connect(self.crop_selection)
        menu.addAction(crop_action)
        menu.exec(self.canvas.mapToGlobal(position))

    def copy_selection(self) -> bool:
        selection = self.canvas.selection.intersected(self.canvas.image.rect())
        if selection.width() <= 0 or selection.height() <= 0:
            self._set_status("Hãy dùng công cụ Chọn vùng (V) trước khi sao chép.", error=True)
            return False
        QApplication.clipboard().setImage(self.canvas.image.copy(selection))
        self._set_status(f"Đã sao chép vùng {selection.width()} × {selection.height()} px.")
        return True

    def cut_selection(self) -> bool:
        selection = self.canvas.selection.intersected(self.canvas.image.rect())
        if selection.width() <= 0 or selection.height() <= 0:
            self._set_status("Hãy dùng công cụ Chọn vùng (V) trước khi cắt.", error=True)
            return False
        if not self.copy_selection():
            return False
        self._push_undo()
        painter = QPainter(self.canvas.image)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
        painter.fillRect(selection, Qt.GlobalColor.transparent)
        painter.end()
        self.canvas.image_changed.emit()
        self.canvas.update()
        self._set_status("Đã cắt vùng chọn vào clipboard.")
        return True

    def paste_selection(self) -> bool:
        image = QApplication.clipboard().image()
        if image.isNull():
            self._set_status("Clipboard không có ảnh để dán.", error=True)
            return False
        self._push_undo()
        selection = self.canvas.selection.intersected(self.canvas.image.rect())
        if selection.width() > 0 and selection.height() > 0:
            x, y = selection.x(), selection.y()
        else:
            x = max(0, (self.canvas.image.width() - image.width()) // 2)
            y = max(0, (self.canvas.image.height() - image.height()) // 2)
        painter = QPainter(self.canvas.image)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
        painter.drawImage(QPoint(x, y), image)
        painter.end()
        pasted = QRect(x, y, min(image.width(), self.canvas.image.width() - x), min(image.height(), self.canvas.image.height() - y))
        self.canvas.selection = pasted.intersected(self.canvas.image.rect())
        self.canvas.selection_changed.emit(QRect(self.canvas.selection))
        self.canvas.image_changed.emit()
        self.canvas.update()
        self._set_status(f"Đã dán ảnh {image.width()} × {image.height()} px vào canvas.")
        return True

    def delete_selection(self) -> bool:
        selection = self.canvas.selection.intersected(self.canvas.image.rect())
        if selection.width() <= 0 or selection.height() <= 0:
            self._set_status("Không có vùng chọn để xóa.", error=True)
            return False
        self._push_undo()
        painter = QPainter(self.canvas.image)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
        painter.fillRect(selection, Qt.GlobalColor.transparent)
        painter.end()
        self.canvas.image_changed.emit()
        self.canvas.update()
        self._set_status("Đã xóa vùng chọn.")
        return True

    def crop_selection(self) -> None:
        selection = self.canvas.selection.intersected(self.canvas.image.rect())
        if selection.isNull() or selection.width() <= 0 or selection.height() <= 0:
            self._set_status("Hãy dùng công cụ Chọn vùng và kéo một vùng cần cắt.", error=True)
            return
        self._push_undo()
        self.canvas.image = self.canvas.image.copy(selection)
        self.canvas.frames.clear()
        self.canvas.collisions.clear()
        self.canvas.selection = QRect()
        self.canvas.fit_to_view()
        self._refresh_all()
        self._set_status("Đã cắt canvas theo vùng chọn.")

    def crop_transparent(self) -> None:
        image = self.canvas.image
        min_x, min_y = image.width(), image.height()
        max_x = max_y = -1
        for y in range(image.height()):
            for x in range(image.width()):
                if image.pixelColor(x, y).alpha() > 0:
                    min_x = min(min_x, x); min_y = min(min_y, y)
                    max_x = max(max_x, x); max_y = max(max_y, y)
        if max_x < min_x or max_y < min_y:
            self._set_status("Ảnh đang hoàn toàn trong suốt.", error=True)
            return
        rect = QRect(min_x, min_y, max_x - min_x + 1, max_y - min_y + 1)
        if rect == image.rect():
            self._set_status("Không có viền trong suốt để cắt.")
            return
        self._push_undo()
        self.canvas.image = image.copy(rect)
        self.canvas.frames.clear()
        self.canvas.collisions.clear()
        self.canvas.selection = QRect()
        self.canvas.fit_to_view()
        self._refresh_all()
        self._set_status("Đã cắt bỏ vùng alpha trống.")

    def remove_background(self) -> None:
        self._push_undo()
        image = self.canvas.image.copy()
        tolerance = self.tolerance.value()
        bg = self._background_color
        removed = 0
        for y in range(image.height()):
            for x in range(image.width()):
                color = image.pixelColor(x, y)
                if (
                    abs(color.red() - bg.red()) <= tolerance
                    and abs(color.green() - bg.green()) <= tolerance
                    and abs(color.blue() - bg.blue()) <= tolerance
                ):
                    color.setAlpha(0)
                    image.setPixelColor(x, y, color)
                    removed += 1
        self.canvas.image = image
        self.canvas.image_changed.emit()
        self.canvas.update()
        self._set_status(f"Đã xóa nền gần màu {bg.name()} trên {removed:,} pixel.")

    def flip_horizontal(self) -> None:
        self._transform_image(self.canvas.image.mirrored(True, False), "Đã lật ảnh theo chiều ngang.")

    def flip_vertical(self) -> None:
        self._transform_image(self.canvas.image.mirrored(False, True), "Đã lật ảnh theo chiều dọc.")

    def rotate_90(self) -> None:
        transform = QTransform().rotate(90)
        self._transform_image(self.canvas.image.transformed(transform), "Đã xoay ảnh 90°.")

    def resize_image(self) -> None:
        width, height = self.resize_w.value(), self.resize_h.value()
        scaled = self.canvas.image.scaled(
            width,
            height,
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.FastTransformation,
        )
        self._transform_image(scaled, f"Đã đổi kích thước thành {width} × {height} px.")

    def _transform_image(self, image: QImage, message: str) -> None:
        self._push_undo()
        self.canvas.image = image.convertToFormat(QImage.Format.Format_RGBA8888)
        self.canvas.frames.clear()
        self.canvas.collisions.clear()
        self.canvas.selection = QRect()
        self.canvas.fit_to_view()
        self._refresh_all()
        self._set_status(message)

    # ---------- filters ----------
    def apply_style(self) -> None:
        style = self.style_combo.currentText()
        self._push_undo()
        image = self.canvas.image.copy()
        if style in ART_STYLE_PROFILES:
            profile = ART_STYLE_PROFILES[style]
            if style in GAME_ART_STYLES:
                image = apply_game_palette(image, style)
            levels = int(profile.get("posterize", 0) or 0)
            if levels >= 2:
                image = self._posterize(image, levels)
            saturation = float(profile.get("saturation", 1.0) or 1.0)
            contrast = float(profile.get("contrast", 1.0) or 1.0)
            if abs(saturation - 1.0) > 0.001:
                image = self._boost_saturation(image, saturation)
            if abs(contrast - 1.0) > 0.001:
                image = self._boost_contrast(image, contrast)
            if int(profile.get("outline_px", 0) or 0) > 0:
                image = self._outline(image)
        elif style in GAME_ART_STYLES:
            image = apply_game_palette(image, style)
        elif style.startswith("Pixel hóa"):
            factor = 4 if "4×" in style else 2
            small_w = max(1, image.width() // factor)
            small_h = max(1, image.height() // factor)
            image = image.scaled(small_w, small_h, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.FastTransformation)
            image = image.scaled(self.canvas.image.width(), self.canvas.image.height(), Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.FastTransformation)
        elif style == "Pixel Art · Classic Retro":
            image = self._posterize(image, 8)
            image = self._outline(image)
        elif style == "Pixel Art · Modern Pixel Art":
            image = self._posterize(image, 16)
            image = self._boost_saturation(image, 1.15)
            image = self._outline(image)
        elif style == "Pixel Art · Isometric RTS":
            image = self._posterize(image, 12)
            image = self._boost_saturation(image, 1.10)
            image = self._boost_contrast(image, 1.14)
            image = self._outline(image)
        elif style == "Retro 4-bit":
            image = self._posterize(image, 4)
        elif style == "Posterize 8 màu":
            image = self._posterize(image, 8)
        elif style == "Vector / Clean Art":
            image = self._posterize(image, 24)
            image = self._boost_contrast(image, 1.12)
        elif style == "Hand-drawn / Painted · Watercolor":
            image = self._soften_watercolor(image)
        elif style == "Hand-drawn / Painted · Anime / Manga":
            image = self._boost_contrast(image, 1.18)
            image = self._posterize(image, 18)
            image = self._outline(image)
        elif style == "Silhouette Art":
            image = self._silhouette(image)
        elif style == "Flat / Geometric Art":
            image = self._posterize(image, 6)
        elif style == "Papercraft / Cutout Art":
            image = self._posterize(image, 12)
            image = self._paper_cutout(image)
        elif style == "Comic / Cel-shaded 2D":
            image = self._posterize(image, 10)
            image = self._outline(image)
            image = self._boost_contrast(image, 1.2)
        elif style == "Grayscale":
            for y in range(image.height()):
                for x in range(image.width()):
                    c = image.pixelColor(x, y)
                    gray = int(0.299 * c.red() + 0.587 * c.green() + 0.114 * c.blue())
                    image.setPixelColor(x, y, QColor(gray, gray, gray, c.alpha()))
        elif style == "Tương phản cao":
            image = self._boost_contrast(image, 1.6)
        elif style == "Viền pixel tối":
            image = self._outline(image)
        self.canvas.image = image
        self.canvas.image_changed.emit()
        self.canvas.update()
        self._set_status(f"Đã áp dụng phong cách: {style}.")

    @staticmethod
    def _posterize(image: QImage, levels: int) -> QImage:
        output = image.copy()
        levels = max(2, levels)
        step = 255 / (levels - 1)
        for y in range(output.height()):
            for x in range(output.width()):
                c = output.pixelColor(x, y)
                r = int(round(c.red() / step) * step)
                g = int(round(c.green() / step) * step)
                b = int(round(c.blue() / step) * step)
                output.setPixelColor(x, y, QColor(r, g, b, c.alpha()))
        return output

    @staticmethod
    def _outline(image: QImage) -> QImage:
        source = image.copy()
        output = image.copy()
        outline = QColor(20, 24, 31, 255)
        for y in range(source.height()):
            for x in range(source.width()):
                if source.pixelColor(x, y).alpha() != 0:
                    continue
                neighbor_opaque = False
                for ox, oy in ((-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (1, -1), (-1, 1), (1, 1)):
                    nx, ny = x + ox, y + oy
                    if 0 <= nx < source.width() and 0 <= ny < source.height() and source.pixelColor(nx, ny).alpha() > 0:
                        neighbor_opaque = True
                        break
                if neighbor_opaque:
                    output.setPixelColor(x, y, outline)
        return output

    @staticmethod
    def _boost_contrast(image: QImage, amount: float) -> QImage:
        output = image.copy()
        for y in range(output.height()):
            for x in range(output.width()):
                c = output.pixelColor(x, y)
                channels = [max(0, min(255, int((v - 128) * amount + 128))) for v in (c.red(), c.green(), c.blue())]
                output.setPixelColor(x, y, QColor(channels[0], channels[1], channels[2], c.alpha()))
        return output

    @staticmethod
    def _boost_saturation(image: QImage, amount: float) -> QImage:
        output = image.copy()
        for y in range(output.height()):
            for x in range(output.width()):
                c = output.pixelColor(x, y)
                h, s, v, a = c.getHsv()
                s = max(0, min(255, int(s * amount)))
                out = QColor()
                out.setHsv(h if h >= 0 else 0, s, v, a)
                output.setPixelColor(x, y, out)
        return output

    @staticmethod
    def _soften_watercolor(image: QImage) -> QImage:
        output = image.copy()
        for y in range(output.height()):
            for x in range(output.width()):
                c = output.pixelColor(x, y)
                r = min(255, int(c.red() * 0.92 + 18))
                g = min(255, int(c.green() * 0.95 + 18))
                b = min(255, int(c.blue() * 1.02 + 22))
                output.setPixelColor(x, y, QColor(r, g, b, c.alpha()))
        return output

    @staticmethod
    def _silhouette(image: QImage) -> QImage:
        output = image.copy()
        for y in range(output.height()):
            for x in range(output.width()):
                c = output.pixelColor(x, y)
                if c.alpha() == 0:
                    continue
                brightness = int(0.299 * c.red() + 0.587 * c.green() + 0.114 * c.blue())
                shade = 28 if brightness > 80 else 8
                output.setPixelColor(x, y, QColor(shade, shade, shade, c.alpha()))
        return output

    @staticmethod
    def _paper_cutout(image: QImage) -> QImage:
        output = image.copy()
        shadow = QColor(40, 36, 30, 80)
        outlined = AssetEditorDialog._outline(output)
        for y in range(outlined.height()):
            for x in range(outlined.width()):
                c = outlined.pixelColor(x, y)
                if c.alpha() == 0:
                    continue
                if x + 1 < outlined.width() and y + 1 < outlined.height() and outlined.pixelColor(x + 1, y + 1).alpha() == 0:
                    outlined.setPixelColor(x + 1, y + 1, shadow)
        return outlined

    # ---------- frames/tiles ----------
    def auto_slice(self) -> None:
        tile_w, tile_h = self.tile_w.value(), self.tile_h.value()
        margin, spacing = self.margin_spin.value(), self.spacing_spin.value()
        if tile_w <= 0 or tile_h <= 0:
            return
        self._push_undo()
        frames: list[FrameRecord] = []
        index = 1
        y = margin
        while y + tile_h <= self.canvas.image.height():
            x = margin
            while x + tile_w <= self.canvas.image.width():
                rect = QRect(x, y, tile_w, tile_h)
                if not self.ignore_empty.isChecked() or not self._rect_is_transparent(rect):
                    frames.append(FrameRecord(f"frame_{index:03d}", rect, self.frame_duration.value()))
                    index += 1
                x += tile_w + spacing
            y += tile_h + spacing
        self.canvas.frames = frames
        self.canvas.selected_frame = 0 if frames else -1
        self._refresh_frames()
        self.canvas.update()
        self._set_status(f"Đã chia tự động {len(frames)} frame từ texture atlas.")

    def smart_slice(self) -> None:
        """Create component frames from visible content using the local detector."""
        image = self.canvas.image.convertToFormat(QImage.Format.Format_RGBA8888)
        width, height = image.width(), image.height()
        if width <= 0 or height <= 0:
            self._set_status("Canvas chưa có nội dung để Smart Slice.", error=True)
            return
        try:
            pixels = memoryview(image.constBits())
            stride = image.bytesPerLine()

            def alpha_at(x: int, y: int) -> int:
                return int(pixels[y * stride + x * 4 + 3])
        except (TypeError, BufferError):
            def alpha_at(x: int, y: int) -> int:
                return image.pixelColor(x, y).alpha()

        regions = detect_content_regions(
            width,
            height,
            alpha_at,
            alpha_threshold=self.smart_alpha.value(),
            min_pixels=self.smart_min_pixels.value(),
            merge_distance=self.smart_merge.value(),
            padding=self.smart_padding.value(),
        )
        self._push_undo()
        self.canvas.frames = [
            FrameRecord(
                f"component_{index:03d}",
                QRect(region.x, region.y, region.width, region.height),
                self.frame_duration.value(),
            )
            for index, region in enumerate(regions, 1)
        ]
        self.canvas.selected_frame = 0 if regions else -1
        self._refresh_frames()
        self.canvas.update()
        if regions:
            self._set_status(f"Smart Slice đã nhận diện {len(regions)} thành phần cục bộ.")
        else:
            self._set_status("Smart Slice không tìm thấy vùng đủ lớn; hãy giảm ngưỡng alpha/pixel tối thiểu.", error=True)

    def _rect_is_transparent(self, rect: QRect) -> bool:
        for y in range(rect.top(), rect.bottom() + 1):
            for x in range(rect.left(), rect.right() + 1):
                if self.canvas.image.pixelColor(x, y).alpha() > 0:
                    return False
        return True

    def clear_frames(self) -> None:
        if not self.canvas.frames:
            return
        self._push_undo()
        self.canvas.frames.clear()
        self.canvas.selected_frame = -1
        self._refresh_frames()
        self.canvas.update()

    def _refresh_frames(self) -> None:
        selected = self.canvas.selected_frame
        self.frame_list.blockSignals(True)
        self.frame_list.clear()
        for frame in self.canvas.frames:
            image = self.canvas.image.copy(frame.rect)
            pixmap = QPixmap.fromImage(image).scaled(62, 62, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.FastTransformation)
            item = QListWidgetItem(QIcon(pixmap), frame.name)
            item.setToolTip(f"{frame.rect.x()}, {frame.rect.y()} — {frame.rect.width()} × {frame.rect.height()} px")
            self.frame_list.addItem(item)
        if 0 <= selected < self.frame_list.count():
            self.frame_list.setCurrentRow(selected)
        self.frame_list.blockSignals(False)
        self._sync_animation_player_selection("atlas_frames", len(self.canvas.frames))

    def _sync_animation_player_selection(self, source: str, count: int) -> None:
        selected_by_source = self.animation_player_settings.setdefault("selected_by_source", {})
        current = selected_by_source.get(source)
        if not isinstance(current, list):
            current = []
        current = sorted({int(index) for index in current if isinstance(index, int) and 0 <= index < count})
        if not current and count:
            current = list(range(count))
        selected_by_source[source] = current
        if self.animation_player_settings.get("source_mode") == source:
            self.animation_player_settings["selected_indices"] = list(current)

    def _frame_selected(self, row: int) -> None:
        self.canvas.selected_frame = row
        self.canvas.update()

    # ---------- scene timeline / cel animation ----------
    def _capture_canvas_region(self) -> QImage:
        selection = self.canvas.selection.intersected(self.canvas.image.rect())
        if selection.width() > 0 and selection.height() > 0:
            return self.canvas.image.copy(selection)
        return self.canvas.image.copy()

    def capture_scene(self) -> None:
        self.stop_playback()
        image = self._capture_canvas_region()
        record = SceneFrameRecord(
            name=f"scene_{len(self.scene_frames) + 1:03d}",
            image=image,
            duration_ms=self.scene_duration.value(),
        )
        self.scene_frames.append(record)
        self.selected_scene = len(self.scene_frames) - 1
        self.animation_player_settings["source_mode"] = "scene_timeline"
        self._select_all_scene_frames()
        self.timeline_tabs.setCurrentIndex(1)
        self._refresh_scenes()
        self._update_info()
        self._set_status(f"Đã tạo {record.name} từ {'vùng chọn' if not self.canvas.selection.isNull() else 'canvas'}.")

    def import_scene_frames(self) -> None:
        paths, _selected_filter = QFileDialog.getOpenFileNames(
            self,
            "Nhập nhiều frame vào Scene Timeline",
            str(self.project_root / "assets"),
            "Ảnh animation (*.png *.jpg *.jpeg *.webp *.bmp *.gif)",
        )
        if not paths:
            return
        self.stop_playback()
        added = 0
        for path in paths:
            image = QImage(path).convertToFormat(QImage.Format.Format_RGBA8888)
            if image.isNull():
                continue
            self.scene_frames.append(SceneFrameRecord(Path(path).stem, image, self.scene_duration.value()))
            added += 1
        if not added:
            self._set_status("Không đọc được frame ảnh nào.", error=True); return
        self._renumber_scenes(keep_custom_names=True)
        self.selected_scene = len(self.scene_frames) - 1
        self.animation_player_settings["source_mode"] = "scene_timeline"
        self._select_all_scene_frames()
        self.timeline_tabs.setCurrentIndex(1); self._refresh_scenes(); self._update_info()
        self._set_status(f"Đã nhập {added} ảnh vào Scene Timeline.")

    def rename_selected_scene(self) -> None:
        row = self.scene_list.currentRow()
        if not 0 <= row < len(self.scene_frames):
            return
        clean = "_".join(self.scene_name_edit.text().strip().split())
        if not clean:
            self.scene_name_edit.setText(self.scene_frames[row].name); return
        self.scene_frames[row].name = clean
        self._refresh_scenes(); self.scene_list.setCurrentRow(row)

    def reverse_scene_timeline(self) -> None:
        if len(self.scene_frames) < 2:
            return
        self.stop_playback(); self.scene_frames.reverse()
        self.selected_scene = len(self.scene_frames) - 1 - max(0, self.selected_scene)
        self._refresh_scenes(); self._set_status("Đã đảo ngược thứ tự Scene Timeline.")

    def make_scene_ping_pong(self) -> None:
        if len(self.scene_frames) < 2:
            self._set_status("Cần ít nhất 2 frame để tạo Ping-Pong.", error=True); return
        self.stop_playback()
        backward = self.scene_frames[-2:0:-1]
        if not backward:
            backward = self.scene_frames[:1]
        self.scene_frames.extend(
            SceneFrameRecord(f"{record.name}_back", record.image.copy(), record.duration_ms)
            for record in backward
        )
        self._select_all_scene_frames()
        self.selected_scene = len(self.scene_frames) - 1
        self._refresh_scenes(); self._set_status("Đã tạo chuỗi Ping-Pong, không lặp frame đỉnh.")

    @staticmethod
    def _opaque_bounds(image: QImage) -> QRect:
        left, top, right, bottom = image.width(), image.height(), -1, -1
        for y in range(image.height()):
            for x in range(image.width()):
                if image.pixelColor(x, y).alpha() <= 0:
                    continue
                left, top = min(left, x), min(top, y)
                right, bottom = max(right, x), max(bottom, y)
        return QRect(left, top, right - left + 1, bottom - top + 1) if right >= left and bottom >= top else QRect()

    def trim_scene_frames(self) -> None:
        if not self.scene_frames:
            return
        self.stop_playback(); changed = 0
        for record in self.scene_frames:
            bounds = self._opaque_bounds(record.image)
            if not bounds.isNull() and bounds != record.image.rect():
                record.image = record.image.copy(bounds); changed += 1
        self._refresh_scenes(); self._update_onion_skin()
        self._set_status(f"Đã cắt biên alpha cho {changed}/{len(self.scene_frames)} frame.")

    def normalize_scene_frames(self) -> None:
        if not self.scene_frames:
            return
        self.stop_playback()
        width = max(record.image.width() for record in self.scene_frames)
        height = max(record.image.height() for record in self.scene_frames)
        for record in self.scene_frames:
            if record.image.size() == QSize(width, height):
                continue
            canvas = QImage(width, height, QImage.Format.Format_RGBA8888); canvas.fill(Qt.GlobalColor.transparent)
            painter = QPainter(canvas)
            painter.drawImage((width - record.image.width()) // 2, (height - record.image.height()) // 2, record.image)
            painter.end(); record.image = canvas
        self._refresh_scenes(); self._update_onion_skin()
        self._set_status(f"Đã chuẩn hóa {len(self.scene_frames)} frame về {width}×{height}px, neo giữa.")

    def flip_selected_scene(self) -> None:
        row = self.scene_list.currentRow()
        if not 0 <= row < len(self.scene_frames):
            return
        self.stop_playback(); self.scene_frames[row].image = self.scene_frames[row].image.mirrored(True, False)
        self._refresh_scenes(); self.scene_list.setCurrentRow(row); self._update_onion_skin()
        self._set_status(f"Đã lật ngang {self.scene_frames[row].name}.")

    def load_scene_to_canvas(self) -> None:
        row = self.scene_list.currentRow()
        if not 0 <= row < len(self.scene_frames):
            self._set_status("Hãy chọn một Scene cần nạp.", error=True)
            return
        self._push_undo()
        record = self.scene_frames[row]
        self.canvas.image = record.image.copy()
        self.canvas.selection = QRect()
        self.canvas.fit_to_view()
        self.resize_w.setValue(self.canvas.image.width())
        self.resize_h.setValue(self.canvas.image.height())
        self.scene_duration.setValue(record.duration_ms)
        self._update_info()
        self._set_status(f"Đã nạp {record.name} lên canvas. Chỉnh sửa rồi nhấn Cập nhật.")

    def update_scene(self) -> None:
        row = self.scene_list.currentRow()
        if not 0 <= row < len(self.scene_frames):
            self._set_status("Hãy chọn một Scene cần cập nhật.", error=True)
            return
        self.stop_playback()
        current = self.scene_frames[row]
        current.image = self._capture_canvas_region()
        current.duration_ms = self.scene_duration.value()
        self._refresh_scenes()
        self.scene_list.setCurrentRow(row)
        self._set_status(f"Đã cập nhật {current.name} từ canvas hiện tại.")

    def duplicate_scene(self) -> None:
        row = self.scene_list.currentRow()
        if not 0 <= row < len(self.scene_frames):
            return
        source = self.scene_frames[row]
        copy_record = SceneFrameRecord(
            name=f"scene_{len(self.scene_frames) + 1:03d}",
            image=source.image.copy(),
            duration_ms=source.duration_ms,
        )
        self.scene_frames.insert(row + 1, copy_record)
        self._select_all_scene_frames()
        self.selected_scene = row + 1
        self._refresh_scenes()
        self.scene_list.setCurrentRow(row + 1)

    def delete_scene(self) -> None:
        row = self.scene_list.currentRow()
        if not 0 <= row < len(self.scene_frames):
            return
        self.stop_playback()
        removed = self.scene_frames.pop(row)
        self.selected_scene = min(row, len(self.scene_frames) - 1)
        self._refresh_scenes()
        self._update_info()
        self._set_status(f"Đã xóa {removed.name} khỏi timeline.")

    def _move_scene(self, delta: int) -> None:
        row = self.scene_list.currentRow()
        target = row + delta
        if not (0 <= row < len(self.scene_frames) and 0 <= target < len(self.scene_frames)):
            return
        self.scene_frames[row], self.scene_frames[target] = self.scene_frames[target], self.scene_frames[row]
        self.selected_scene = target
        self._renumber_scenes()
        self._refresh_scenes()
        self.scene_list.setCurrentRow(target)

    def _renumber_scenes(self, keep_custom_names: bool = False) -> None:
        for index, record in enumerate(self.scene_frames, 1):
            if not keep_custom_names:
                record.name = f"scene_{index:03d}"

    def _select_all_scene_frames(self) -> None:
        indices = list(range(len(self.scene_frames)))
        selected_by_source = self.animation_player_settings.setdefault("selected_by_source", {})
        selected_by_source["scene_timeline"] = indices
        if self.animation_player_settings.get("source_mode") == "scene_timeline":
            self.animation_player_settings["selected_indices"] = list(indices)

    def _refresh_scenes(self) -> None:
        if not hasattr(self, "scene_list"):
            return
        selected = self.selected_scene
        self.scene_list.blockSignals(True)
        self.scene_list.clear()
        for index, record in enumerate(self.scene_frames, 1):
            preview = QPixmap.fromImage(record.image).scaled(
                76, 76, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.FastTransformation
            )
            item = QListWidgetItem(QIcon(preview), record.name)
            item.setToolTip(
                f"Scene {index} · {record.image.width()} × {record.image.height()} px · {record.duration_ms} ms"
            )
            self.scene_list.addItem(item)
        if 0 <= selected < self.scene_list.count():
            self.scene_list.setCurrentRow(selected)
        self.scene_list.blockSignals(False)
        self._sync_animation_player_selection("scene_timeline", len(self.scene_frames))

    def _scene_selected(self, row: int) -> None:
        self.selected_scene = row
        if 0 <= row < len(self.scene_frames):
            self.scene_duration.setValue(self.scene_frames[row].duration_ms)
            self.scene_name_edit.setText(self.scene_frames[row].name)
        else:
            self.scene_name_edit.clear()
        self._update_onion_skin()

    def _scene_duration_changed(self, value: int) -> None:
        row = self.scene_list.currentRow() if hasattr(self, "scene_list") else self.selected_scene
        if 0 <= row < len(self.scene_frames):
            self.scene_frames[row].duration_ms = max(1, int(value))
            item = self.scene_list.item(row)
            if item is not None:
                record = self.scene_frames[row]
                item.setToolTip(f"Scene {row + 1} · {record.image.width()} × {record.image.height()} px · {record.duration_ms} ms")

    def _update_onion_skin(self, _checked=None) -> None:
        enabled = hasattr(self, "onion_skin") and self.onion_skin.isChecked()
        row = self.scene_list.currentRow() if hasattr(self, "scene_list") else self.selected_scene
        if enabled and 0 < row < len(self.scene_frames):
            self.canvas.onion_image = self.scene_frames[row - 1].image.copy()
        else:
            self.canvas.onion_image = QImage()
        self.canvas.update()

    def toggle_playback(self) -> None:
        if self.playback_timer.isActive():
            self.stop_playback()
            return
        if not self.scene_frames:
            self._set_status("Timeline chưa có Scene. Nhấn “Thêm Scene” để chụp canvas thành frame.", error=True)
            return
        self._playback_backup = self.canvas.image.copy()
        self._playback_index = -1
        self.play_button.setText("Tạm dừng")
        self.play_button.setIcon(icon("fa5s.pause"))
        self._playback_tick()

    def _playback_tick(self) -> None:
        if not self.scene_frames:
            self.stop_playback()
            return
        next_index = self._playback_index + 1
        if next_index >= len(self.scene_frames):
            if not self.animation_loop.isChecked():
                self.stop_playback()
                return
            next_index = 0
        self._playback_index = next_index
        record = self.scene_frames[next_index]
        self.canvas.image = record.image.copy()
        self.canvas.fit_to_view()
        self.timeline_tabs.setCurrentIndex(1)
        self.scene_list.setCurrentRow(next_index)
        fps_interval = max(1, round(1000 / max(1, self.animation_fps.value())))
        self.playback_timer.start(max(record.duration_ms, fps_interval))

    def stop_playback(self) -> None:
        if self.playback_timer.isActive():
            self.playback_timer.stop()
        if self._playback_backup is not None:
            self.canvas.image = self._playback_backup
            self._playback_backup = None
            self.canvas.fit_to_view()
        self._playback_index = -1
        if hasattr(self, "play_button"):
            self.play_button.setText("Phát")
            self.play_button.setIcon(icon("fa5s.play"))
        if hasattr(self, "canvas"):
            self.canvas.update()

    # ---------- collisions ----------
    def _add_collision(self, rect: QRect) -> None:
        record = CollisionRecord(
            name=f"collision_{len(self.canvas.collisions) + 1:02d}",
            rect=QRect(rect),
            kind=self._collision_kind,
        )
        self.canvas.collisions.append(record)
        self.canvas.selected_collision = len(self.canvas.collisions) - 1
        self._refresh_collisions()
        self.canvas.update()
        self._set_status(f"Đã thêm {record.kind}: {rect.width()} × {rect.height()} px.")

    def _refresh_collisions(self) -> None:
        selected = self.canvas.selected_collision
        self.collision_list.blockSignals(True)
        self.collision_list.clear()
        for record in self.canvas.collisions:
            item = QListWidgetItem(icon("fa5s.vector-square"), f"{record.name} · {record.kind}")
            item.setToolTip(f"x={record.rect.x()}, y={record.rect.y()}, w={record.rect.width()}, h={record.rect.height()}")
            self.collision_list.addItem(item)
        if 0 <= selected < self.collision_list.count():
            self.collision_list.setCurrentRow(selected)
        self.collision_list.blockSignals(False)

    def _collision_selected(self, row: int) -> None:
        self.canvas.selected_collision = row
        self.canvas.update()

    def delete_collision(self) -> None:
        row = self.collision_list.currentRow()
        if not 0 <= row < len(self.canvas.collisions):
            return
        self._push_undo()
        self.canvas.collisions.pop(row)
        self.canvas.selected_collision = min(row, len(self.canvas.collisions) - 1)
        self._refresh_collisions()
        self.canvas.update()

    def clear_collisions(self) -> None:
        if not self.canvas.collisions:
            return
        self._push_undo()
        self.canvas.collisions.clear()
        self.canvas.selected_collision = -1
        self._refresh_collisions()
        self.canvas.update()

    # ---------- colors/tools ----------
    def choose_brush_color(self) -> None:
        color = ColorPickerDialog.get_color(
            self.canvas.brush_color, self, title="Chọn màu pixel", show_alpha=True
        )
        if color.isValid():
            self._set_brush_color(color)

    def _set_brush_color(self, color: QColor) -> None:
        if not color.isValid():
            return
        self.canvas.brush_color = QColor(color)
        self.color_hex.setText(color.name(QColor.NameFormat.HexArgb) if color.alpha() < 255 else color.name())
        self.color_button.setStyleSheet(f"background-color: {color.name()}; border: 1px solid #667085; border-radius: 6px;")

    def _hex_color_changed(self) -> None:
        color = QColor(self.color_hex.text().strip())
        if color.isValid():
            self._set_brush_color(color)

    def choose_background_color(self) -> None:
        color = ColorPickerDialog.get_color(
            self._background_color, self, title="Chọn màu cần xóa", show_alpha=False
        )
        if color.isValid():
            self._background_color = color
            self._update_background_button()

    def use_top_left_background(self) -> None:
        if self.canvas.image.isNull():
            return
        self._background_color = self.canvas.image.pixelColor(0, 0)
        self._update_background_button()

    def _update_background_button(self) -> None:
        self.bg_color_button.setText(self._background_color.name())
        self.bg_color_button.setStyleSheet(
            f"background-color: {self._background_color.name()}; color: {'#111' if self._background_color.lightness() > 150 else '#fff'};"
        )

    def _set_tool(self, tool: str) -> None:
        button_key = "shape_rect" if tool.startswith("shape_") else tool
        for key, button in self.tool_buttons.items():
            button.setChecked(key == button_key)
        self.canvas.set_tool(tool)
        if tool == "collision":
            self.inspector_tabs.setCurrentIndex(1)
        button = self.tool_buttons.get(button_key)
        label = getattr(self, "shape_tool_labels", {}).get(tool) or (button.property("responsiveText") if button is not None else tool)
        self._set_status(f"Công cụ: {label}." + (" Giữ Shift để khóa góc 0°/45°/90°." if tool == "ruler" else ""))

    def _set_pixel_mode(self, bits: int, activate: bool = True) -> None:
        bits = bits if bits in {8, 16, 32} else 32
        self.pixel_mode_bits = bits
        self.canvas.set_pixel_depth(bits)
        for value, action in getattr(self, "pixel_mode_actions", {}).items():
            action.setChecked(value == bits)
        pencil = getattr(self, "tool_buttons", {}).get("pencil")
        if pencil is not None:
            pencil.setText(f"Bút pixel · {bits}-bit")
        # Pixel modes also provide a practical cell-size preset for pixel-art work.
        if activate and hasattr(self, "tile_w"):
            self.tile_w.setValue(bits)
            self.tile_h.setValue(bits)
        if hasattr(self, "render_mode"):
            self.render_mode.setCurrentIndex(0)
        if activate and hasattr(self, "tool_buttons"):
            self._set_tool("pencil")
            self._set_status(
                f"Pixel Art {bits}-bit: màu được lượng tử hóa khi vẽ; lưới {bits} × {bits} px."
            )
        self._update_info() if hasattr(self, "info_label") else None

    def _toggle_grid(self, visible: bool) -> None:
        self.canvas.grid_visible = visible
        if self.grid_button.isChecked() != visible:
            self.grid_button.blockSignals(True); self.grid_button.setChecked(visible); self.grid_button.blockSignals(False)
        if self.preview_grid.isChecked() != visible:
            self.preview_grid.blockSignals(True); self.preview_grid.setChecked(visible); self.preview_grid.blockSignals(False)
        self.canvas.update()

    def _sync_grid(self) -> None:
        self.canvas.grid_width = self.tile_w.value()
        self.canvas.grid_height = self.tile_h.value()
        self.canvas.update()

    def _collision_kind_changed(self) -> None:
        self._collision_kind = str(self.collision_kind.currentData())

    def _apply_initial_destination(self, relative: str) -> None:
        value = str(relative or "").replace("\\", "/").strip("/")
        legacy_map = {
            "assets/textures": "assets/map/texture",
            "assets/maps": "assets/map/tileset",
            "assets/ui": "assets/map/texture",
            "scenes": "assets/scenes",
        }
        value = legacy_map.get(value, value)
        if value == "assets/map":
            value = "assets/map/texture"
        index = self.destination_combo.findData(value)
        if index >= 0:
            self.destination_combo.setCurrentIndex(index)

    def _asset_type_changed(self, text: str) -> None:
        if text.startswith("Tileset"):
            target = "assets/map/tileset"
        elif text.startswith("Nhân vật"):
            target = "assets/scenes"
        elif text.startswith("Stage2D"):
            target = "assets/scenes"
            if "Water Band" in text:
                role = "water"
            elif "Ground" in text:
                role = "ground"
            elif "Foreground" in text:
                role = "foreground"
            else:
                role = "parallax"
            if hasattr(self, "stage2d_role"):
                role_index = self.stage2d_role.findData(role)
                if role_index >= 0:
                    self.stage2d_role.setCurrentIndex(role_index)
        elif text.startswith("2.5D"):
            target = "assets/scenes"
            if "Perspective Plane" in text:
                role = "perspective_plane"
            elif "Water Surface" in text:
                role = "water_surface"
            else:
                role = "billboard"
            if hasattr(self, "scene25d_role"):
                role_index = self.scene25d_role.findData(role)
                if role_index >= 0:
                    self.scene25d_role.setCurrentIndex(role_index)
        elif text.startswith("Biểu tượng"):
            target = "assets/app-icon"
        elif text.startswith("UI") or text.startswith("Nguyên liệu"):
            target = "assets/map/texture"
        else:
            target = "assets/map/texture"
        index = self.destination_combo.findData(target)
        if index >= 0:
            self.destination_combo.setCurrentIndex(index)
        if hasattr(self, "scene_target"):
            target = "character" if text.startswith("Nhân vật") else ("ui" if text.startswith("UI") else "scene")
            target_index = self.scene_target.findData(target)
            if target_index >= 0:
                self.scene_target.setCurrentIndex(target_index)

    def _sync_asset_type_buttons(self, active: str) -> None:
        for asset_type, button in getattr(self, "asset_type_buttons", {}).items():
            button.blockSignals(True)
            button.setChecked(asset_type == active)
            button.blockSignals(False)

    # ---------- export ----------
    def save_and_apply(self) -> None:
        if self.workspace_tabs.currentIndex() == 1:
            self.vpe_pixel.receive_document()
        self.stop_playback()
        name = self.asset_name.text().strip()
        if not name:
            self._set_status("Vui lòng nhập tên PNG.", error=True)
            self.inspector_tabs.setCurrentIndex(self.inspector_tabs.count() - 1)
            return
        if Path(name).name != name or any(ch in name for ch in '<>:"/\\|?*'):
            self._set_status("Tên tệp không hợp lệ trên Windows.", error=True)
            return
        if not name.lower().endswith(".png"):
            name += ".png"
            self.asset_name.setText(name)
        relative = str(self.destination_combo.currentData())
        destination_dir = (self.project_root / relative).resolve()
        try:
            destination_dir.relative_to(self.project_root)
        except ValueError:
            self._set_status("Đường dẫn lưu nằm ngoài dự án.", error=True)
            return
        destination_dir.mkdir(parents=True, exist_ok=True)
        output = destination_dir / name
        overwrite_current = False
        if self.current_source is not None:
            try:
                overwrite_current = output.resolve() == self.current_source.resolve()
            except OSError:
                overwrite_current = False
        if output.exists() and not (self.allow_overwrite.isChecked() or overwrite_current):
            output = self._unique_path(output)
            self.asset_name.setText(output.name)
        if not self.canvas.image.save(str(output), "PNG"):
            self._set_status("Không thể ghi tệp PNG.", error=True)
            return

        metadata_path: Path | None = None
        if self.write_metadata.isChecked():
            metadata_name = self.metadata_name.text().strip() or f"{output.stem}.asset.dtfe"
            if not metadata_name.lower().endswith(".dtfe"):
                metadata_name += ".dtfe"
            metadata_path = output.with_name(Path(metadata_name).name)
            metadata_path.parent.mkdir(parents=True, exist_ok=True)
            metadata = self._build_metadata(output)
            metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")

        animation_path: Path | None = None
        if self.write_animation.isChecked() and (self.scene_frames or self.canvas.frames):
            try:
                animation_path = self._write_animation_package(output)
            except (OSError, ValueError) as error:
                self._set_status(f"Không thể lưu animation .ani..dtfe: {error}", error=True)
                return

        tileset_catalog: Path | None = None
        if self.canvas.frames:
            try:
                tileset_catalog = self._export_frames_to_titleset(output)
            except (OSError, ValueError) as error:
                self._set_status(f"Không thể đưa frame vào TitleSet: {error}", error=True)
                return

        self.saved_path = output
        self.asset_saved.emit(str(output))
        summary = f"Đã lưu project://{output.relative_to(self.project_root).as_posix()}"
        if metadata_path:
            summary += f" · {metadata_path.name}"
        if animation_path:
            summary += f" · {animation_path.name}"
        if tileset_catalog:
            summary += f" · TitleSet/{tileset_catalog.parent.name}"
        self._set_status(summary + ".")
        self.accept()

    def _auto_frame_category(self, output: Path) -> str:
        label = self.asset_type_combo.currentText().lower()
        name = output.stem.lower()
        parent = output.parent.as_posix().lower()
        if any(token in name for token in ("joystick", "button", "run", "jump", "dpad", "control")):
            return "control"
        if any(token in name for token in ("skill", "spell", "attack", "effect", "ult")) or "/skill" in parent:
            return "skill"
        if label.startswith("nhân vật") or any(token in name for token in ("hero", "player", "character", "enemy", "npc")):
            return "character"
        if label.startswith("tileset") or "/tileset" in parent:
            return "terrain"
        if label.startswith("ui"):
            return "ui"
        return "tile"

    def _export_frames_to_titleset(self, output: Path) -> Path:
        """Export every sliced atlas frame into the bottom-right TitleSet library."""
        category = self._auto_frame_category(output)
        folder = self.project_root / "assets" / "map" / "tileset" / output.stem
        folder.mkdir(parents=True, exist_ok=True)
        frames_payload: list[dict] = []
        for index, frame in enumerate(self.canvas.frames, 1):
            image = self.canvas.image.copy(frame.rect)
            safe_name = frame.name.strip().replace(" ", "_") or f"frame_{index:03d}"
            frame_path = folder / f"{safe_name}.png"
            if not image.save(str(frame_path), "PNG"):
                raise OSError(f"Không thể lưu {frame_path.name}")
            frames_payload.append({
                "name": frame.name,
                "file": frame_path.relative_to(self.project_root).as_posix(),
                "category": category,
                "rect": [frame.rect.x(), frame.rect.y(), frame.rect.width(), frame.rect.height()],
                "duration_ms": frame.duration_ms,
            })
        catalog = folder / f"{output.stem}.tileset.dtfe"
        payload = {
            "format": "VXPEngine TitleSet Catalog",
            "version": 1,
            "name": output.stem,
            "source": output.relative_to(self.project_root).as_posix(),
            "auto_category": category,
            "tile_width": self.tile_w.value(),
            "tile_height": self.tile_h.value(),
            "frames": frames_payload,
        }
        catalog.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return catalog

    def _write_animation_package(self, output: Path) -> Path:
        """Write a selected-frame ``<asset>.ani..dtfe`` package.

        The dedicated Anim Player decides which frames participate, FPS, loop,
        preview background and zoom. The descriptor stores both the selected
        indices and a compact hexadecimal selection mask for portability.
        """
        scene_root = self.project_root / "assets" / "scenes"
        scene_root.mkdir(parents=True, exist_ok=True)
        requested = self._normalize_animation_name(
            self.animation_metadata_name.text().strip(), output.stem
        )
        descriptor_path = scene_root / requested

        settings = self._normalized_player_settings()
        source_mode = str(settings.get("source_mode") or "atlas_frames")
        selected_by_source = settings.get("selected_by_source") if isinstance(settings.get("selected_by_source"), dict) else {}
        source_count = len(self.scene_frames) if source_mode == "scene_timeline" else len(self.canvas.frames)
        selected_indices = [
            int(index) for index in selected_by_source.get(source_mode, [])
            if isinstance(index, int) and 0 <= index < source_count
        ]
        if not selected_indices:
            selected_indices = list(range(source_count))
        selection_mask_hex = AnimationPlayerWindow._selection_mask_hex(selected_indices, source_count)

        frames_payload: list[dict] = []
        texture_path = output
        if source_mode == "scene_timeline" and self.scene_frames:
            selected_records = [(index, self.scene_frames[index]) for index in selected_indices]
            frame_folder = scene_root / f"{output.stem}_frames"
            frame_folder.mkdir(parents=True, exist_ok=True)
            max_w = max(frame.image.width() for _, frame in selected_records)
            max_h = max(frame.image.height() for _, frame in selected_records)
            columns = min(8, max(1, math.ceil(math.sqrt(len(selected_records)))))
            rows = math.ceil(len(selected_records) / columns)
            sheet = QImage(max_w * columns, max_h * rows, QImage.Format.Format_RGBA8888)
            sheet.fill(Qt.GlobalColor.transparent)
            painter = QPainter(sheet)
            for packed_index, (source_index, record) in enumerate(selected_records):
                column = packed_index % columns
                row = packed_index // columns
                cell_x = column * max_w
                cell_y = row * max_h
                draw_x = cell_x + (max_w - record.image.width()) // 2
                draw_y = cell_y + (max_h - record.image.height()) // 2
                painter.drawImage(draw_x, draw_y, record.image)
                safe_name = "_".join(record.name.strip().split()) or f"scene_{source_index + 1:03d}"
                safe_name = "".join(char for char in safe_name if char.isalnum() or char in {"_", "-"}) or f"scene_{source_index + 1:03d}"
                frame_path = frame_folder / f"{packed_index + 1:03d}_{safe_name}.png"
                if not record.image.save(str(frame_path), "PNG"):
                    raise OSError(f"Không thể ghi frame animation: {frame_path}")
                frames_payload.append({
                    "name": record.name,
                    "source_index": source_index,
                    "x": cell_x,
                    "y": cell_y,
                    "width": max_w,
                    "height": max_h,
                    "content_x": draw_x - cell_x,
                    "content_y": draw_y - cell_y,
                    "content_width": record.image.width(),
                    "content_height": record.image.height(),
                    "duration_ms": record.duration_ms,
                    "file": frame_path.relative_to(self.project_root).as_posix(),
                })
            painter.end()
            texture_path = scene_root / f"{output.stem}_ani.png"
            if not sheet.save(str(texture_path), "PNG"):
                raise OSError(f"Không thể ghi spritesheet animation: {texture_path}")
        else:
            source_mode = "atlas_frames"
            frames_payload = [
                {
                    "name": self.canvas.frames[index].name,
                    "source_index": index,
                    "x": self.canvas.frames[index].rect.x(),
                    "y": self.canvas.frames[index].rect.y(),
                    "width": self.canvas.frames[index].rect.width(),
                    "height": self.canvas.frames[index].rect.height(),
                    "duration_ms": self.canvas.frames[index].duration_ms,
                }
                for index in selected_indices
            ]

        payload = {
            "format": "VXPEngine Animation",
            "format_version": 2,
            "extension": ANIMATION_SUFFIX,
            "asset": output.relative_to(self.project_root).as_posix(),
            "texture": texture_path.relative_to(self.project_root).as_posix(),
            "source_mode": source_mode,
            "asset_kind": str(self.scene_target.currentData() or "character"),
            "package": "spritesheet+frames+descriptor" if source_mode == "scene_timeline" else "atlas+descriptor",
            "pixel_mode_bits": self.pixel_mode_bits,
            "selection_mask_hex": selection_mask_hex,
            "preview_background": settings.get("background", "checker"),
            "preview_zoom": settings.get("preview_zoom", 1),
            "animation": {
                "name": self.animation_name.text().strip() or output.stem,
                "fps": int(settings.get("fps", self.animation_fps.value())),
                "loop": bool(settings.get("loop", self.animation_loop.isChecked())),
                "frame_count": len(frames_payload),
                "source_mode": source_mode,
                "asset_kind": str(self.scene_target.currentData() or "character"),
                "selected_indices": selected_indices,
                "selected_by_source": selected_by_source,
                "selection_mask_hex": selection_mask_hex,
                "preview_background": settings.get("background", "checker"),
                "preview_zoom": settings.get("preview_zoom", 1),
                "keyboard": {"toggle": "SPACE", "previous": "LEFT", "next": "RIGHT"},
            },
            "frames": frames_payload,
        }
        descriptor_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        self.animation_metadata_name.setText(descriptor_path.name)
        self.animation_player_settings.update(settings)
        self.animation_player_settings["selected_indices"] = selected_indices
        self.animation_player_settings["selection_mask_hex"] = selection_mask_hex
        return descriptor_path

    def _build_metadata(self, output: Path) -> dict:
        return {
            "format": "VXPEngine Asset",
            "format_version": 2,
            "asset": output.relative_to(self.project_root).as_posix(),
            "asset_type": self.asset_type_combo.currentText(),
            "size": {"width": self.canvas.image.width(), "height": self.canvas.image.height()},
            "texture": {
                "pixels_per_unit": self.pixels_per_unit.value(),
                "render_mode": "nearest" if self.render_mode.currentIndex() == 0 else "linear",
                "transparent": True,
                "pixel_mode_bits": self.pixel_mode_bits,
            },
            "grid": {
                "width": self.tile_w.value(),
                "height": self.tile_h.value(),
                "margin": self.margin_spin.value(),
                "spacing": self.spacing_spin.value(),
            },
            "art_style": self._art_style_metadata(),
            "stage2d": self._stage2d_metadata(),
            "scene25d": self._scene25d_metadata(),
            "animation": {
                "name": self.animation_name.text().strip() or "default",
                "fps": self.animation_fps.value(),
                "loop": self.animation_loop.isChecked(),
                "descriptor": f"assets/scenes/{self._normalize_animation_name(self.animation_metadata_name.text(), output.stem)}",
                "source_mode": self._normalized_player_settings().get("source_mode", "atlas_frames"),
                "asset_kind": str(self.scene_target.currentData() or "character"),
                "selected_indices": self._normalized_player_settings().get("selected_indices", []),
                "selected_by_source": self._normalized_player_settings().get("selected_by_source", {}),
                "preview_background": self._normalized_player_settings().get("background", "checker"),
                "preview_zoom": self._normalized_player_settings().get("preview_zoom", 1),
            },
            "frames": [
                {
                    "name": frame.name,
                    "x": frame.rect.x(),
                    "y": frame.rect.y(),
                    "width": frame.rect.width(),
                    "height": frame.rect.height(),
                    "duration_ms": frame.duration_ms,
                }
                for frame in self.canvas.frames
            ],
            "scene_timeline": [
                {
                    "name": scene.name,
                    "width": scene.image.width(),
                    "height": scene.image.height(),
                    "duration_ms": scene.duration_ms,
                }
                for scene in self.scene_frames
            ],
            "collisions": [
                {
                    "name": item.name,
                    "kind": item.kind,
                    "x": item.rect.x(),
                    "y": item.rect.y(),
                    "width": item.rect.width(),
                    "height": item.rect.height(),
                }
                for item in self.canvas.collisions
            ],
        }

    @staticmethod
    def _normalize_animation_name(value: str, stem: str) -> str:
        """Return the canonical ``name.ani..dtfe`` file name."""
        requested = Path(str(value or "").strip()).name or f"{stem}{ANIMATION_SUFFIX}"
        lower = requested.lower()
        for suffix in (ANIMATION_SUFFIX, LEGACY_ANIMATION_SUFFIX):
            if lower.endswith(suffix):
                requested = requested[: -len(suffix)]
                break
        else:
            if lower.endswith(".dtfe"):
                requested = requested[:-5]
            if requested.lower().endswith(".ani"):
                requested = requested[:-4]
        base = requested.rstrip(". ") or stem
        return f"{base}{ANIMATION_SUFFIX}"

    @staticmethod
    def _unique_path(path: Path) -> Path:
        index = 1
        while True:
            candidate = path.with_name(f"{path.stem}_{index}{path.suffix}")
            if not candidate.exists():
                return candidate
            index += 1

    # ---------- misc UI ----------
    def _install_shortcuts(self) -> None:
        actions: list[tuple[str, str, object]] = [
            ("Undo", QKeySequence.StandardKey.Undo, self.undo),
            ("Redo", QKeySequence.StandardKey.Redo, self.redo),
            ("Save", QKeySequence.StandardKey.Save, self.save_and_apply),
            ("NewCanvas", "Ctrl+N", self.new_canvas),
            ("Import", "Ctrl+O", self.import_image),
            ("Insert", "Ctrl+Shift+I", self.insert_image),
            ("Fit", "0", self.canvas_fit),
            ("Zoom100", "1", lambda: self.canvas.set_zoom(1.0)),
            ("Grid", "G", lambda: self.grid_button.toggle()),
            ("RemoveBG", "Ctrl+Shift+B", self.remove_background),
            ("CropTransparent", "Ctrl+Alt+C", self.crop_transparent),
            ("AutoSlice", "Alt+S", self.auto_slice),
            ("SmartSlice", "Alt+Shift+S", self.smart_slice),
            ("AnimPlayer", "Alt+A", self.open_animation_player),
            ("ToolSelect", "V", lambda: self._set_tool("select")),
            ("ToolPencil", "B", lambda: self._set_tool("pencil")),
            ("ToolEraser", "E", lambda: self._set_tool("eraser")),
            ("ToolFill", "F", lambda: self._set_tool("fill")),
            ("ToolPicker", "I", lambda: self._set_tool("picker")),
            ("ToolCollision", "C", lambda: self._set_tool("collision")),
            ("ToolRuler", "R", lambda: self._set_tool("ruler")),
            ("ToolFreeFrame", "Shift+B", lambda: self._set_tool("free_frame")),
            ("ToolShape", "U", lambda: self._set_tool("shape_rect")),
            ("ToolPan", "H", lambda: self._set_tool("pan")),
            ("Pixel8", "Alt+1", lambda: self._set_pixel_mode(8)),
            ("Pixel16", "Alt+2", lambda: self._set_pixel_mode(16)),
            ("Pixel32", "Alt+3", lambda: self._set_pixel_mode(32)),
            ("CopySelection", QKeySequence.StandardKey.Copy, self.copy_selection),
            ("CutSelection", QKeySequence.StandardKey.Cut, self.cut_selection),
            ("PasteSelection", QKeySequence.StandardKey.Paste, self.paste_selection),
            ("DeleteSelection", QKeySequence.StandardKey.Delete, self.delete_selection),
            ("AddScene", "Alt+Insert", self.capture_scene),
            ("LoadScene", "Alt+Enter", self.load_scene_to_canvas),
            ("UpdateScene", "Alt+U", self.update_scene),
            ("DuplicateScene", "Alt+D", self.duplicate_scene),
            ("MoveSceneLeft", "Alt+Left", lambda: self._move_scene(-1)),
            ("MoveSceneRight", "Alt+Right", lambda: self._move_scene(1)),
            ("DeleteScene", "Alt+Delete", self.delete_scene),
            ("ImportSceneFrames", "Ctrl+Alt+I", self.import_scene_frames),
            ("ReverseTimeline", "Alt+R", self.reverse_scene_timeline),
            ("PingPongTimeline", "Alt+P", self.make_scene_ping_pong),
            ("NormalizeTimeline", "Alt+N", self.normalize_scene_frames),
            ("ShortcutsHelp", "F1", self._show_shortcuts_hint),
        ]
        for _name, shortcut, callback in actions:
            action = QAction(self)
            action.setShortcut(shortcut if isinstance(shortcut, QKeySequence.StandardKey) else QKeySequence(shortcut))
            action.triggered.connect(callback)
            self.addAction(action)
        self._asset_shortcut_actions = list(self.actions())

    def _workspace_tab_changed(self, index: int) -> None:
        self.asset_toolbar.setVisible(index == 0)
        for action in getattr(self, "_asset_shortcut_actions", []):
            action.setEnabled(index == 0)
        if index == 1:
            self.stop_playback()
            self.vpe_pixel.ensure_editor()
        else:
            self.vpe_pixel.stop()

    def _send_to_vpe_pixel(self) -> None:
        settings = self._normalized_player_settings()
        images = [frame.image.copy() for frame in self.scene_frames] if settings.get("source_mode") == "scene_timeline" and self.scene_frames else [self.canvas.image.copy()]
        delay_ms = max(10, round(1000 / max(1, self.animation_fps.value())))
        if settings.get("source_mode") == "scene_timeline" and self.scene_frames:
            durations = {frame.duration_ms for frame in self.scene_frames}
            if len(durations) == 1:
                delay_ms = self.scene_frames[0].duration_ms
        try:
            self.vpe_pixel.set_images(images, Path(self.asset_name.text() or "asset").stem,
                delay_ms, self.animation_loop.isChecked())
            if settings.get("source_mode") == "scene_timeline" and self.scene_frames and len(durations) > 1:
                self._set_status("VPE dùng một duration chung; timeline có duration khác nhau sẽ dùng FPS hiện tại.")
        except ValueError as error:
            self._set_status(str(error), error=True)

    def _receive_vpe_pixel(self, images, name: str, delay_ms: int, loop: bool) -> None:
        if not images:
            return
        self._push_undo()
        self.canvas.set_image(images[0].copy())
        self.current_source = None
        self._editing_existing_project_asset = False
        self.asset_name.setText(Path(name or "vpe_asset").stem + ".png")
        self.metadata_name.setText(Path(name or "vpe_asset").stem + ".asset.dtfe")
        self.animation_metadata_name.setText(Path(name or "vpe_asset").stem + ANIMATION_SUFFIX)
        self.scene_frames = [SceneFrameRecord(f"frame_{i:03d}", image.copy(), delay_ms) for i, image in enumerate(images)] if len(images) > 1 else []
        self.selected_scene = 0 if self.scene_frames else -1
        self.animation_fps.setValue(max(1, round(1000 / max(1, delay_ms))))
        self.animation_loop.setChecked(loop)
        self.write_animation.setChecked(bool(self.scene_frames))
        self.animation_player_settings.update({
            "source_mode": "scene_timeline" if self.scene_frames else "atlas_frames",
            "fps": self.animation_fps.value(), "loop": loop,
            "selected_indices": [], "selected_by_source": {"atlas_frames": [], "scene_timeline": []},
            "selection_mask_hex": "",
        })
        if self.scene_frames:
            self._select_all_scene_frames()
            self.timeline_tabs.setCurrentIndex(1)
        self.workspace_tabs.setCurrentIndex(0)
        self._refresh_all()
        self._set_status(f"Đã nhận {len(images)} frame từ VPE Pixel. Dùng Áp dụng & lưu để lưu vào project.")

    def _show_shortcuts_hint(self) -> None:
        self._set_status("Phím tắt: Ctrl+N/O/S tạo–mở–lưu • V/B/E/F/I/C/H tool cũ • R thước • Shift+B frame tay • U frame hình học • Alt+1/2/3 Pixel Art • G lưới")

    def canvas_fit(self) -> None:
        self.canvas.fit_to_view()

    def _on_image_changed(self) -> None:
        self.resize_w.setValue(self.canvas.image.width())
        self.resize_h.setValue(self.canvas.image.height())
        self._update_info()

    def _cursor_changed(self, x: int, y: int) -> None:
        if x >= 0 and y >= 0:
            self.status_label.setText(f"X: {x}   Y: {y}   •   {self.canvas.image.width()} × {self.canvas.image.height()} px")

    def _selection_changed(self, rect: QRect) -> None:
        self._set_status(f"Vùng chọn: x={rect.x()}, y={rect.y()}, {rect.width()} × {rect.height()} px.")

    def _refresh_all(self) -> None:
        self._sync_grid()
        self._refresh_frames()
        self._refresh_scenes()
        self._refresh_collisions()
        self._update_info()
        self._update_export_preview()
        self._refresh_legacy_assets()
        self._update_history_buttons()
        self.canvas.update()

    def _update_info(self) -> None:
        self.info_label.setText(
            f"Canvas: {self.canvas.image.width()} × {self.canvas.image.height()} px\n"
            f"Atlas frames: {len(self.canvas.frames)}\n"
            f"Scene timeline: {len(self.scene_frames)}\n"
            f"Pixel mode: {self.pixel_mode_bits}-bit\n"
            f"Collision: {len(self.canvas.collisions)}\n"
            f"Zoom: {self.canvas.zoom * 100:.0f}%"
        )

    def _sync_generated_names(self, text: str) -> None:
        stem = Path(text.strip() or "new_asset.png").stem
        if hasattr(self, "metadata_name") and not self.metadata_name.hasFocus():
            self.metadata_name.setText(f"{stem}.asset.dtfe")
        if hasattr(self, "animation_metadata_name") and not self.animation_metadata_name.hasFocus():
            self.animation_metadata_name.setText(f"{stem}{ANIMATION_SUFFIX}")

    def _update_export_preview(self) -> None:
        if not hasattr(self, "export_preview"):
            return
        relative = self.destination_combo.currentData() or "assets/map/texture"
        name = self.asset_name.text().strip() or "new_asset.png"
        stem = Path(name).stem
        self.export_preview.setText(
            f"Ảnh: project://{relative}/{Path(name).name}\n"
            f"Animation: project://assets/scenes/{stem}{ANIMATION_SUFFIX}"
        )

    def _update_document_title(self, name: str) -> None:
        self.source_label.setText(name)
        self.title_label.setText(f"Editor Assets — {name}")

    def _set_status(self, text: str, error: bool = False) -> None:
        if not hasattr(self, "status_label"):
            return
        self.status_label.setText(text)
        self.status_label.setProperty("error", error)
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)

    def reject(self) -> None:
        if not self.vpe_pixel.can_close():
            return
        self.vpe_pixel.stop()
        self.stop_playback()
        super().reject()

    def accept(self) -> None:
        self.vpe_pixel.stop()
        self.stop_playback()
        super().accept()

    def _title_mouse_press(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def _title_mouse_move(self, event: QMouseEvent) -> None:
        if self._drag_offset is not None and event.buttons() & Qt.MouseButton.LeftButton:
            global_pos = event.globalPosition().toPoint()
            if self.isMaximized():
                ratio = event.position().x() / max(1, self.width())
                self.showNormal()
                geometry = self._normal_geometry or QRect(0, 0, 1280, 800)
                x = int(global_pos.x() - geometry.width() * ratio)
                y = max(0, global_pos.y() - int(event.position().y()))
                self.setGeometry(x, y, geometry.width(), geometry.height())
                self._drag_offset = global_pos - self.frameGeometry().topLeft()
                self._sync_window_chrome()
            self.move(global_pos - self._drag_offset)
            event.accept()

    def _title_mouse_release(self, event: QMouseEvent) -> None:
        self._drag_offset = None
        event.accept()

    def toggle_maximize_restore(self) -> None:
        if self.isMaximized():
            self.showNormal()
            if self._normal_geometry is not None:
                self.setGeometry(self._normal_geometry)
        else:
            self._normal_geometry = self.geometry()
            self.showMaximized()
        self._sync_window_chrome()
