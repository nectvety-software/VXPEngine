"""Standalone keyframe/anchor editor for VXPEngine scene components."""
from __future__ import annotations

import copy
from pathlib import Path

from PySide6.QtCore import QPoint, QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QImage, QMouseEvent, QPainter, QPen, QPixmap, QShowEvent
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QDoubleSpinBox,
    QFrame,
    QGraphicsEllipseItem,
    QGraphicsItem,
    QGraphicsLineItem,
    QGraphicsPixmapItem,
    QGraphicsScene,
    QGraphicsView,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSpinBox,
    QSplitter,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .icons import icon


class _WindowTitleBar(QWidget):
    def __init__(self, owner: "KeyframeEditorWindow") -> None:
        super().__init__(owner)
        self.owner = owner

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self.owner._drag_offset = event.globalPosition().toPoint() - self.owner.frameGeometry().topLeft()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self.owner._drag_offset is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.owner.move(event.globalPosition().toPoint() - self.owner._drag_offset)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        self.owner._drag_offset = None
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self.owner._toggle_maximize()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)


class _AnchorHandle(QGraphicsEllipseItem):
    def __init__(self, owner: "KeyframeEditorWindow") -> None:
        super().__init__(-7, -7, 14, 14)
        self.owner = owner
        self.setBrush(QColor("#63D391"))
        self.setPen(QPen(QColor("#EAFBF0"), 1.5))
        self.setFlags(
            QGraphicsItem.GraphicsItemFlag.ItemIsMovable
            | QGraphicsItem.GraphicsItemFlag.ItemIsSelectable
            | QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges
        )
        self.setZValue(100)
        self.setCursor(Qt.CursorShape.CrossCursor)

    def itemChange(self, change, value):  # noqa: N802
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange:
            point = QPointF(value)
            rect = self.owner.preview_bounds
            point.setX(max(rect.left(), min(rect.right(), point.x())))
            point.setY(max(rect.top(), min(rect.bottom(), point.y())))
            return point
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            self.owner._anchor_changed(QPointF(value))
        return super().itemChange(change, value)


class KeyframeEditorWindow(QDialog):
    """Frameless, non-modal editor for component animation keyframes and anchor."""

    keyframes_applied = Signal(str, list, dict)

    def __init__(self, project_root: str | Path, node: dict, parent=None) -> None:
        super().__init__(parent)
        self.project_root = Path(project_root).resolve()
        self.node = copy.deepcopy(node)
        self.node_id = str(self.node.get("id", ""))
        self._drag_offset: QPoint | None = None
        self._normal_geometry = None
        self._updating = False
        self.keyframes: list[dict] = [
            copy.deepcopy(item)
            for item in self.node.get("animation_keyframes", [])
            if isinstance(item, dict)
        ]
        anchor = self.node.get("anchor") if isinstance(self.node.get("anchor"), dict) else {}
        self.anchor = {
            "x": float(anchor.get("x", 0.0)),
            "y": float(anchor.get("y", 0.0)),
            "space": str(anchor.get("space", "pixel")),
        }

        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setModal(False)
        self.setMinimumSize(840, 560)
        self.resize(1180, 760)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 10, 10, 10)
        self.root = QFrame()
        self.root.setObjectName("KeyframeEditorRoot")
        outer.addWidget(self.root)
        root_layout = QVBoxLayout(self.root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        root_layout.addWidget(self._build_title_bar())
        root_layout.addWidget(self._build_workspace(), 1)
        root_layout.addWidget(self._build_footer())

        self._load_preview()
        self._refresh_keyframe_list()
        if not self.keyframes:
            self._add_keyframe(initial=True)

    def _build_title_bar(self) -> QWidget:
        bar = _WindowTitleBar(self)
        bar.setObjectName("AssetEditorTitleBar")
        bar.setFixedHeight(34)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(12, 0, 6, 0)
        layout.setSpacing(8)
        logo = QLabel()
        logo.setPixmap(icon("fa5s.bezier-curve", "#69A6FF").pixmap(17, 17))
        layout.addWidget(logo)
        title = QLabel(f"Keyframe & Anchor — {self.node.get('name', 'Component')}")
        title.setObjectName("AssetEditorTitle")
        layout.addWidget(title)
        layout.addStretch()
        minimize = QToolButton()
        minimize.setIcon(icon("fa5s.minus"))
        minimize.setFixedSize(38, 28)
        minimize.clicked.connect(self.showMinimized)
        maximize = QToolButton()
        maximize.setIcon(icon("fa5s.window-maximize"))
        maximize.setFixedSize(38, 28)
        maximize.clicked.connect(self._toggle_maximize)
        close = QToolButton()
        close.setIcon(icon("fa5s.times"))
        close.setFixedSize(42, 28)
        close.clicked.connect(self.close)
        layout.addWidget(minimize)
        layout.addWidget(maximize)
        layout.addWidget(close)
        return bar

    def _build_workspace(self) -> QWidget:
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(4)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(10, 10, 10, 10)
        header = QLabel("KEYFRAMES")
        header.setObjectName("AssetSectionLabel")
        left_layout.addWidget(header)
        self.keyframe_list = QListWidget()
        self.keyframe_list.currentRowChanged.connect(self._load_keyframe_row)
        left_layout.addWidget(self.keyframe_list, 1)
        row = QHBoxLayout()
        add = QPushButton("Thêm")
        add.setIcon(icon("fa5s.plus"))
        add.clicked.connect(self._add_keyframe)
        update = QPushButton("Cập nhật")
        update.setIcon(icon("fa5s.sync-alt"))
        update.clicked.connect(self._update_keyframe)
        remove = QPushButton("Xóa")
        remove.setIcon(icon("fa5s.trash-alt"))
        remove.clicked.connect(self._delete_keyframe)
        row.addWidget(add)
        row.addWidget(update)
        row.addWidget(remove)
        left_layout.addLayout(row)
        splitter.addWidget(left)

        center = QWidget()
        center_layout = QVBoxLayout(center)
        center_layout.setContentsMargins(0, 0, 0, 0)
        self.scene = QGraphicsScene(self)
        self.preview = QGraphicsView(self.scene)
        self.preview.setObjectName("KeyframePreview")
        self.preview.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        self.preview.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
        self.preview.setBackgroundBrush(QColor("#0D131D"))
        self.preview.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        center_layout.addWidget(self.preview, 1)
        hint = QLabel("Kéo điểm neo màu xanh để đặt tọa độ pivot. Mỗi keyframe lưu vị trí, xoay, scale, opacity và thời gian.")
        hint.setObjectName("DialogHint")
        hint.setWordWrap(True)
        center_layout.addWidget(hint)
        splitter.addWidget(center)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(10, 10, 10, 10)
        right_layout.addWidget(QLabel("THUỘC TÍNH KEYFRAME"))
        self.time_spin = QSpinBox(); self.time_spin.setRange(0, 600000); self.time_spin.setSuffix(" ms")
        self.x_spin = self._double_spin(-100000, 100000, 0.1)
        self.y_spin = self._double_spin(-100000, 100000, 0.1)
        self.rotation_spin = self._double_spin(-36000, 36000, 0.1); self.rotation_spin.setSuffix("°")
        self.scale_x_spin = self._double_spin(-100, 100, 0.01); self.scale_x_spin.setValue(1.0)
        self.scale_y_spin = self._double_spin(-100, 100, 0.01); self.scale_y_spin.setValue(1.0)
        self.opacity_spin = self._double_spin(0, 1, 0.01); self.opacity_spin.setValue(1.0)
        self.anchor_x_spin = self._double_spin(-100000, 100000, 0.1)
        self.anchor_y_spin = self._double_spin(-100000, 100000, 0.1)
        for label, widget in (
            ("Thời gian", self.time_spin),
            ("Position X", self.x_spin),
            ("Position Y", self.y_spin),
            ("Rotation", self.rotation_spin),
            ("Scale X", self.scale_x_spin),
            ("Scale Y", self.scale_y_spin),
            ("Opacity", self.opacity_spin),
            ("Anchor X", self.anchor_x_spin),
            ("Anchor Y", self.anchor_y_spin),
        ):
            row = QHBoxLayout()
            row.addWidget(QLabel(label), 1)
            row.addWidget(widget, 1)
            right_layout.addLayout(row)
        self.anchor_x_spin.valueChanged.connect(self._anchor_spin_changed)
        self.anchor_y_spin.valueChanged.connect(self._anchor_spin_changed)
        right_layout.addStretch()
        splitter.addWidget(right)
        splitter.setSizes([250, 660, 270])
        splitter.setStretchFactor(1, 1)
        return splitter

    @staticmethod
    def _double_spin(minimum: float, maximum: float, step: float) -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setRange(minimum, maximum)
        spin.setDecimals(3)
        spin.setSingleStep(step)
        return spin

    def _build_footer(self) -> QWidget:
        footer = QWidget()
        footer.setObjectName("AssetEditorFooter")
        layout = QHBoxLayout(footer)
        layout.setContentsMargins(10, 7, 10, 7)
        self.status = QLabel("Điểm neo dùng tọa độ pixel tương đối theo góc trên-trái của asset.")
        self.status.setObjectName("AssetEditorStatus")
        layout.addWidget(self.status, 1)
        close = QPushButton("Đóng")
        close.setObjectName("GhostBtn")
        close.clicked.connect(self.close)
        apply_button = QPushButton("Áp dụng keyframe")
        apply_button.setObjectName("AccentBtn")
        apply_button.setIcon(icon("fa5s.check"))
        apply_button.clicked.connect(self._apply)
        layout.addWidget(close)
        layout.addWidget(apply_button)
        return footer

    def _load_preview(self) -> None:
        self.scene.clear()
        asset = str(self.node.get("asset", ""))
        path = Path(asset)
        if asset and not path.is_absolute():
            path = self.project_root / asset.replace("project://", "", 1)
        pixmap = QPixmap(str(path)) if path.exists() else QPixmap()
        if pixmap.isNull():
            image = QImage(256, 256, QImage.Format.Format_ARGB32_Premultiplied)
            image.fill(QColor("#182232"))
            painter = QPainter(image)
            painter.setPen(QColor("#AAB8CE"))
            painter.drawText(image.rect(), Qt.AlignmentFlag.AlignCenter, str(self.node.get("name", "Component")))
            painter.end()
            pixmap = QPixmap.fromImage(image)
        item = QGraphicsPixmapItem(pixmap)
        item.setTransformationMode(Qt.TransformationMode.FastTransformation)
        self.scene.addItem(item)
        self.preview_bounds = QRectF(0, 0, pixmap.width(), pixmap.height())
        self.scene.setSceneRect(self.preview_bounds.adjusted(-80, -80, 80, 80))
        center_x = self.anchor["x"] if self.anchor["x"] else pixmap.width() / 2
        center_y = self.anchor["y"] if self.anchor["y"] else pixmap.height() / 2
        self.anchor_handle = _AnchorHandle(self)
        self.anchor_handle.setPos(center_x, center_y)
        self.scene.addItem(self.anchor_handle)
        self.anchor_h = QGraphicsLineItem()
        self.anchor_v = QGraphicsLineItem()
        pen = QPen(QColor("#63D391"), 1)
        pen.setStyle(Qt.PenStyle.DashLine)
        self.anchor_h.setPen(pen); self.anchor_v.setPen(pen)
        self.anchor_h.setZValue(90); self.anchor_v.setZValue(90)
        self.scene.addItem(self.anchor_h); self.scene.addItem(self.anchor_v)
        self._anchor_changed(self.anchor_handle.pos())
        self.preview.fitInView(self.scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def _anchor_changed(self, point: QPointF) -> None:
        self.anchor = {"x": round(point.x(), 3), "y": round(point.y(), 3), "space": "pixel"}
        if hasattr(self, "anchor_h"):
            self.anchor_h.setLine(self.preview_bounds.left(), point.y(), self.preview_bounds.right(), point.y())
            self.anchor_v.setLine(point.x(), self.preview_bounds.top(), point.x(), self.preview_bounds.bottom())
        if hasattr(self, "anchor_x_spin") and not self._updating:
            self._updating = True
            self.anchor_x_spin.setValue(point.x())
            self.anchor_y_spin.setValue(point.y())
            self._updating = False

    def _anchor_spin_changed(self) -> None:
        if self._updating or not hasattr(self, "anchor_handle"):
            return
        self.anchor_handle.setPos(self.anchor_x_spin.value(), self.anchor_y_spin.value())

    def _frame_from_controls(self) -> dict:
        return {
            "time_ms": int(self.time_spin.value()),
            "position": [round(self.x_spin.value(), 3), round(self.y_spin.value(), 3)],
            "rotation": round(self.rotation_spin.value(), 3),
            "scale": [round(self.scale_x_spin.value(), 4), round(self.scale_y_spin.value(), 4)],
            "opacity": round(self.opacity_spin.value(), 4),
            "anchor": copy.deepcopy(self.anchor),
            "interpolation": "linear",
        }

    def _add_keyframe(self, _checked=False, initial: bool = False) -> None:
        if initial:
            position = self.node.get("position", [0, 0])
            scale = self.node.get("scale", [1, 1])
            self.x_spin.setValue(float(position[0] if len(position) else 0))
            self.y_spin.setValue(float(position[1] if len(position) > 1 else 0))
            self.rotation_spin.setValue(float(self.node.get("rotation", 0)))
            self.scale_x_spin.setValue(float(scale[0] if len(scale) else 1))
            self.scale_y_spin.setValue(float(scale[1] if len(scale) > 1 else self.scale_x_spin.value()))
            self.opacity_spin.setValue(float(self.node.get("opacity", 1)))
        frame = self._frame_from_controls()
        if not initial and self.keyframes:
            frame["time_ms"] = max(item.get("time_ms", 0) for item in self.keyframes) + 100
        self.keyframes.append(frame)
        self.keyframes.sort(key=lambda item: int(item.get("time_ms", 0)))
        self._refresh_keyframe_list()
        self.keyframe_list.setCurrentRow(self.keyframes.index(frame))

    def _update_keyframe(self) -> None:
        row = self.keyframe_list.currentRow()
        if 0 <= row < len(self.keyframes):
            self.keyframes[row] = self._frame_from_controls()
            self.keyframes.sort(key=lambda item: int(item.get("time_ms", 0)))
            self._refresh_keyframe_list()

    def _delete_keyframe(self) -> None:
        row = self.keyframe_list.currentRow()
        if 0 <= row < len(self.keyframes):
            self.keyframes.pop(row)
            self._refresh_keyframe_list()
            if self.keyframes:
                self.keyframe_list.setCurrentRow(min(row, len(self.keyframes) - 1))

    def _refresh_keyframe_list(self) -> None:
        self.keyframe_list.clear()
        for index, frame in enumerate(self.keyframes, 1):
            position = frame.get("position", [0, 0])
            item = QListWidgetItem(
                icon("fa5s.map-marker-alt"),
                f"Keyframe {index} · {int(frame.get('time_ms', 0))} ms · X {position[0]:g} / Y {position[1]:g}",
            )
            item.setData(Qt.ItemDataRole.UserRole, copy.deepcopy(frame))
            self.keyframe_list.addItem(item)

    def _load_keyframe_row(self, row: int) -> None:
        if not (0 <= row < len(self.keyframes)):
            return
        frame = self.keyframes[row]
        position = frame.get("position", [0, 0])
        scale = frame.get("scale", [1, 1])
        anchor = frame.get("anchor") if isinstance(frame.get("anchor"), dict) else self.anchor
        self._updating = True
        self.time_spin.setValue(int(frame.get("time_ms", 0)))
        self.x_spin.setValue(float(position[0] if len(position) else 0))
        self.y_spin.setValue(float(position[1] if len(position) > 1 else 0))
        self.rotation_spin.setValue(float(frame.get("rotation", 0)))
        self.scale_x_spin.setValue(float(scale[0] if len(scale) else 1))
        self.scale_y_spin.setValue(float(scale[1] if len(scale) > 1 else self.scale_x_spin.value()))
        self.opacity_spin.setValue(float(frame.get("opacity", 1)))
        self.anchor_x_spin.setValue(float(anchor.get("x", self.anchor["x"])))
        self.anchor_y_spin.setValue(float(anchor.get("y", self.anchor["y"])))
        self._updating = False
        self.anchor_handle.setPos(self.anchor_x_spin.value(), self.anchor_y_spin.value())

    def _apply(self) -> None:
        self._update_keyframe()
        self.keyframes_applied.emit(self.node_id, copy.deepcopy(self.keyframes), copy.deepcopy(self.anchor))
        self.status.setText(f"Đã áp dụng {len(self.keyframes)} keyframe và điểm neo ({self.anchor['x']:.1f}, {self.anchor['y']:.1f}).")

    def _toggle_maximize(self) -> None:
        if self.isMaximized():
            self.showNormal()
            if self._normal_geometry is not None:
                self.setGeometry(self._normal_geometry)
        else:
            self._normal_geometry = self.geometry()
            self.showMaximized()

    def showEvent(self, event: QShowEvent) -> None:  # noqa: N802
        super().showEvent(event)
        screen = self.screen() or QApplication.primaryScreen()
        if screen is None:
            return
        area = screen.availableGeometry()
        width = min(1320, max(self.minimumWidth(), int(area.width() * 0.9)))
        height = min(860, max(self.minimumHeight(), int(area.height() * 0.86)))
        self.resize(width, height)
        self.move(area.center().x() - width // 2, area.center().y() - height // 2)
        self.preview.fitInView(self.scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)
