"""Standalone frame-selection animation player for VXPEngine.

The workflow is inspired by compact sprite animation checkers: select only the
frames that belong to a clip, preview them at an adjustable FPS, step with the
keyboard, switch preview backgrounds, and apply the selection back to the
project's ``.ani..dtfe`` descriptor.
"""
from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QPoint, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QIcon, QImage, QMouseEvent, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListView,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSizeGrip,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from .icons import icon


@dataclass(slots=True)
class AnimationPreviewFrame:
    name: str
    image: QImage
    duration_ms: int = 100


class AnimationPreview(QWidget):
    zoom_toggled = Signal(int)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("AnimationPreview")
        self.setMinimumSize(300, 280)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.image = QImage()
        self.background_mode = "checker"
        self.zoom_multiplier = 1
        self._checker_a = QColor("#242A35")
        self._checker_b = QColor("#303746")

    def set_frame(self, image: QImage) -> None:
        self.image = image.copy()
        self.update()

    def set_background_mode(self, mode: str) -> None:
        self.background_mode = mode
        self.update()

    def set_zoom_multiplier(self, multiplier: int) -> None:
        self.zoom_multiplier = max(1, min(8, int(multiplier)))
        self.update()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            next_zoom = 2 if self.zoom_multiplier == 1 else 1
            self.set_zoom_multiplier(next_zoom)
            self.zoom_toggled.emit(next_zoom)
            event.accept()
            return
        super().mousePressEvent(event)

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#0C111A"))
        inner = self.rect().adjusted(12, 12, -12, -12)
        if self.background_mode == "black":
            painter.fillRect(inner, QColor("#000000"))
        elif self.background_mode == "green":
            painter.fillRect(inner, QColor("#00B400"))
        elif self.background_mode == "transparent":
            painter.fillRect(inner, QColor("#111722"))
        else:
            cell = 18
            for y in range(inner.top(), inner.bottom() + 1, cell):
                for x in range(inner.left(), inner.right() + 1, cell):
                    color = self._checker_a if ((x - inner.left()) // cell + (y - inner.top()) // cell) % 2 == 0 else self._checker_b
                    painter.fillRect(x, y, cell, cell, color)

        if not self.image.isNull():
            fit = min(inner.width() / max(1, self.image.width()), inner.height() / max(1, self.image.height()))
            scale = min(fit, float(self.zoom_multiplier)) if self.zoom_multiplier == 1 else min(fit * self.zoom_multiplier, 8.0)
            width = max(1, int(self.image.width() * scale))
            height = max(1, int(self.image.height() * scale))
            target = QRectF(
                inner.center().x() - width / 2,
                inner.center().y() - height / 2,
                width,
                height,
            )
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
            painter.drawImage(target, self.image)
        painter.setPen(QPen(QColor("#46536A"), 1))
        painter.drawRect(inner)
        painter.setPen(QColor("#8FA0B8"))
        painter.drawText(18, self.height() - 12, "Nhấp preview để chuyển Fit / x2")


class _TitleBar(QWidget):
    def __init__(self, owner: "AnimationPlayerWindow") -> None:
        super().__init__(owner)
        self.owner = owner
        self.setObjectName("AnimationPlayerTitleBar")
        self.setFixedHeight(34)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.owner._drag_offset = event.globalPosition().toPoint() - self.owner.frameGeometry().topLeft()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self.owner._drag_offset is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.owner.move(event.globalPosition().toPoint() - self.owner._drag_offset)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self.owner._drag_offset = None
        super().mouseReleaseEvent(event)


class AnimationPlayerWindow(QDialog):
    """Frame selection and playback window used by Editor Assets."""

    settings_applied = Signal(dict)

    def __init__(
        self,
        sources: dict[str, list[AnimationPreviewFrame]],
        settings: dict | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.sources = {key: list(value) for key, value in sources.items()}
        self.settings = dict(settings or {})
        self.selected_by_source: dict[str, set[int]] = {}
        for key, frames in self.sources.items():
            configured = self.settings.get("selected_by_source", {}).get(key)
            if isinstance(configured, list):
                selected = {int(value) for value in configured if isinstance(value, int) and 0 <= value < len(frames)}
            else:
                selected = set(range(len(frames)))
            self.selected_by_source[key] = selected
        self._last_clicked = -1
        self._current_sequence_position = 0
        self._current_frame_index = -1
        self._drag_offset: QPoint | None = None
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)

        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setModal(False)
        self.setMinimumSize(760, 560)
        self.resize(1120, 720)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 10, 10, 10)
        root = QFrame()
        root.setObjectName("AnimationPlayerRoot")
        outer.addWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._build_title_bar())
        layout.addWidget(self._build_controls())

        body = QWidget()
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(10, 8, 10, 8)
        body_layout.setSpacing(10)
        self.preview = AnimationPreview()
        self.preview.zoom_toggled.connect(self._preview_zoom_toggled)
        body_layout.addWidget(self.preview, 3)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        self.frame_status = QLabel("Chưa có frame")
        self.frame_status.setObjectName("AnimationPlayerStatus")
        right_layout.addWidget(self.frame_status)
        self.frame_list = QListWidget()
        self.frame_list.setViewMode(QListView.ViewMode.IconMode)
        self.frame_list.setFlow(QListView.Flow.LeftToRight)
        self.frame_list.setResizeMode(QListView.ResizeMode.Adjust)
        self.frame_list.setMovement(QListView.Movement.Static)
        self.frame_list.setIconSize(QSize(76, 76))
        self.frame_list.setSpacing(6)
        self.frame_list.itemClicked.connect(self._frame_clicked)
        right_layout.addWidget(self.frame_list, 1)
        body_layout.addWidget(right, 4)
        layout.addWidget(body, 1)
        layout.addWidget(self._build_footer())

        source = str(self.settings.get("source_mode") or "")
        index = self.source_combo.findData(source)
        if index < 0:
            index = 0
        self.source_combo.setCurrentIndex(index)
        self.fps_spin.setValue(max(1, min(60, int(self.settings.get("fps", 12)))))
        self.loop_box.setChecked(bool(self.settings.get("loop", True)))
        bg = str(self.settings.get("background", "checker"))
        bg_index = self.background_combo.findData(bg)
        self.background_combo.setCurrentIndex(max(0, bg_index))
        self.zoom_combo.setCurrentText(f"x{max(1, int(self.settings.get('preview_zoom', 1)))}")
        self._source_changed()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        screen = self.screen() or QApplication.primaryScreen()
        if screen is not None:
            area = screen.availableGeometry()
            width = min(1220, int(area.width() * 0.88))
            height = min(780, int(area.height() * 0.86))
            self.resize(max(self.minimumWidth(), width), max(self.minimumHeight(), height))
            self.move(area.center().x() - self.width() // 2, area.center().y() - self.height() // 2)

    def _build_title_bar(self) -> QWidget:
        bar = _TitleBar(self)
        row = QHBoxLayout(bar)
        row.setContentsMargins(12, 0, 6, 0)
        logo = QLabel()
        logo.setPixmap(icon("fa5s.film", "#70A6FF").pixmap(17, 17))
        row.addWidget(logo)
        title = QLabel("Animation Player · VXPEngine")
        title.setObjectName("AnimationPlayerTitle")
        row.addWidget(title)
        row.addStretch()
        close = QPushButton()
        close.setObjectName("AnimationPlayerClose")
        close.setIcon(icon("fa5s.times"))
        close.setFixedSize(44, 30)
        close.clicked.connect(self.close)
        row.addWidget(close)
        return bar

    def _build_controls(self) -> QWidget:
        host = QWidget()
        host.setObjectName("AnimationPlayerToolbar")
        row = QHBoxLayout(host)
        row.setContentsMargins(10, 6, 10, 6)
        row.setSpacing(6)

        self.play_button = QPushButton("Phát")
        self.play_button.setIcon(icon("fa5s.play"))
        self.play_button.clicked.connect(self.toggle_playback)
        row.addWidget(self.play_button)
        prev = QPushButton()
        prev.setIcon(icon("fa5s.step-backward"))
        prev.setToolTip("Frame trước (←)")
        prev.clicked.connect(lambda: self.step_frame(-1))
        row.addWidget(prev)
        nxt = QPushButton()
        nxt.setIcon(icon("fa5s.step-forward"))
        nxt.setToolTip("Frame sau (→)")
        nxt.clicked.connect(lambda: self.step_frame(1))
        row.addWidget(nxt)

        row.addWidget(QLabel("Nguồn"))
        self.source_combo = QComboBox()
        for key, label in (("atlas_frames", "Atlas Frames"), ("scene_timeline", "Scene Timeline")):
            self.source_combo.addItem(label, key)
        self.source_combo.currentIndexChanged.connect(self._source_changed)
        row.addWidget(self.source_combo)

        row.addWidget(QLabel("FPS"))
        self.fps_slider = QSlider(Qt.Orientation.Horizontal)
        self.fps_slider.setRange(1, 60)
        self.fps_slider.setFixedWidth(150)
        self.fps_spin = QSpinBox()
        self.fps_spin.setRange(1, 60)
        self.fps_spin.setSuffix(" fps")
        self.fps_slider.valueChanged.connect(self.fps_spin.setValue)
        self.fps_spin.valueChanged.connect(self.fps_slider.setValue)
        self.fps_spin.valueChanged.connect(self._fps_changed)
        row.addWidget(self.fps_slider)
        row.addWidget(self.fps_spin)

        self.loop_box = QCheckBox("Loop")
        self.loop_box.setChecked(True)
        row.addWidget(self.loop_box)
        row.addWidget(QLabel("Nền"))
        self.background_combo = QComboBox()
        self.background_combo.addItem("Ô trong suốt", "checker")
        self.background_combo.addItem("Đen", "black")
        self.background_combo.addItem("Green screen", "green")
        self.background_combo.addItem("Trong suốt", "transparent")
        self.background_combo.currentIndexChanged.connect(self._background_changed)
        row.addWidget(self.background_combo)
        row.addWidget(QLabel("Preview"))
        self.zoom_combo = QComboBox()
        self.zoom_combo.addItems(["x1", "x2", "x4", "x8"])
        self.zoom_combo.currentTextChanged.connect(self._zoom_changed)
        row.addWidget(self.zoom_combo)
        row.addStretch()
        return host

    def _build_footer(self) -> QWidget:
        host = QWidget()
        host.setObjectName("AnimationPlayerFooter")
        row = QHBoxLayout(host)
        row.setContentsMargins(10, 7, 10, 7)
        all_button = QPushButton("Chọn tất cả")
        none_button = QPushButton("Bỏ chọn")
        invert_button = QPushButton("Đảo chọn")
        all_button.clicked.connect(lambda: self._set_all(True))
        none_button.clicked.connect(lambda: self._set_all(False))
        invert_button.clicked.connect(self._invert_selection)
        row.addWidget(all_button)
        row.addWidget(none_button)
        row.addWidget(invert_button)
        row.addStretch()
        help_label = QLabel("SPACE: phát/dừng · ←/→: chuyển frame · Shift+click: chọn dải")
        help_label.setObjectName("AnimationPlayerHelp")
        row.addWidget(help_label)
        apply_button = QPushButton("Áp dụng vào .ani..dtfe")
        apply_button.setObjectName("AccentBtn")
        apply_button.setIcon(icon("fa5s.check"))
        apply_button.clicked.connect(self.apply_settings)
        row.addWidget(apply_button)
        row.addWidget(QSizeGrip(host), 0, Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignRight)
        return host

    def current_source(self) -> str:
        return str(self.source_combo.currentData() or "atlas_frames")

    def current_frames(self) -> list[AnimationPreviewFrame]:
        return self.sources.get(self.current_source(), [])

    def current_selected(self) -> set[int]:
        return self.selected_by_source.setdefault(self.current_source(), set())

    def _source_changed(self) -> None:
        self.stop_playback()
        self._last_clicked = -1
        self._current_sequence_position = 0
        self._refresh_frame_list()
        sequence = self._selected_sequence()
        if sequence:
            self._show_frame(sequence[0])
        else:
            frames = self.current_frames()
            if frames:
                self._show_frame(0)
            else:
                self.preview.set_frame(QImage())
                self.frame_status.setText("Nguồn chưa có frame")

    def _refresh_frame_list(self) -> None:
        frames = self.current_frames()
        selected = self.current_selected()
        self.frame_list.blockSignals(True)
        self.frame_list.clear()
        for index, frame in enumerate(frames):
            pixmap = QPixmap.fromImage(frame.image).scaled(
                76,
                76,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.FastTransformation,
            )
            if index not in selected:
                faded = QPixmap(pixmap.size())
                faded.fill(Qt.GlobalColor.transparent)
                painter = QPainter(faded)
                painter.setOpacity(0.25)
                painter.drawPixmap(0, 0, pixmap)
                painter.end()
                pixmap = faded
            marker = "✓ " if index in selected else "○ "
            item = QListWidgetItem(QIcon(pixmap), f"{marker}{index:03d}")
            item.setData(Qt.ItemDataRole.UserRole, index)
            item.setToolTip(f"{frame.name} · {frame.image.width()}×{frame.image.height()} · {frame.duration_ms} ms")
            item.setBackground(QColor("#554A20") if index in selected else QColor("#171C26"))
            self.frame_list.addItem(item)
        self.frame_list.blockSignals(False)

    def _frame_clicked(self, item: QListWidgetItem) -> None:
        index = int(item.data(Qt.ItemDataRole.UserRole))
        selected = self.current_selected()
        shift = bool(QApplication.keyboardModifiers() & Qt.KeyboardModifier.ShiftModifier)
        if shift and self._last_clicked >= 0:
            value = self._last_clicked in selected
            start, end = sorted((self._last_clicked, index))
            for frame_index in range(start, end + 1):
                if value:
                    selected.add(frame_index)
                else:
                    selected.discard(frame_index)
        else:
            if index in selected:
                selected.discard(index)
            else:
                selected.add(index)
        self._last_clicked = index
        self._refresh_frame_list()
        self._show_frame(index)

    def _set_all(self, enabled: bool) -> None:
        selected = self.current_selected()
        selected.clear()
        if enabled:
            selected.update(range(len(self.current_frames())))
        self._refresh_frame_list()
        sequence = self._selected_sequence()
        if sequence:
            self._show_frame(sequence[0])

    def _invert_selection(self) -> None:
        selected = self.current_selected()
        selected.symmetric_difference_update(range(len(self.current_frames())))
        self._refresh_frame_list()

    def _selected_sequence(self) -> list[int]:
        return sorted(index for index in self.current_selected() if 0 <= index < len(self.current_frames()))

    def _show_frame(self, index: int) -> None:
        frames = self.current_frames()
        if not 0 <= index < len(frames):
            return
        self._current_frame_index = index
        frame = frames[index]
        self.preview.set_frame(frame.image)
        selected_count = len(self._selected_sequence())
        self.frame_status.setText(
            f"Frame {index + 1}/{len(frames)} · {frame.name} · đã chọn {selected_count} · {self.fps_spin.value()} fps"
        )
        for row in range(self.frame_list.count()):
            item = self.frame_list.item(row)
            if int(item.data(Qt.ItemDataRole.UserRole)) == index:
                self.frame_list.setCurrentItem(item)
                self.frame_list.scrollToItem(item)
                break

    def toggle_playback(self) -> None:
        if self.timer.isActive():
            self.stop_playback()
            return
        sequence = self._selected_sequence()
        if not sequence:
            self.frame_status.setText("Không có frame nào được chọn")
            return
        if self._current_frame_index in sequence:
            self._current_sequence_position = sequence.index(self._current_frame_index)
        else:
            self._current_sequence_position = 0
            self._show_frame(sequence[0])
        self.play_button.setText("Tạm dừng")
        self.play_button.setIcon(icon("fa5s.pause"))
        self.timer.start(max(1, round(1000 / self.fps_spin.value())))

    def stop_playback(self) -> None:
        self.timer.stop()
        self.play_button.setText("Phát")
        self.play_button.setIcon(icon("fa5s.play"))

    def _tick(self) -> None:
        sequence = self._selected_sequence()
        if not sequence:
            self.stop_playback()
            return
        self._current_sequence_position += 1
        if self._current_sequence_position >= len(sequence):
            if not self.loop_box.isChecked():
                self.stop_playback()
                return
            self._current_sequence_position = 0
        self._show_frame(sequence[self._current_sequence_position])

    def step_frame(self, delta: int) -> None:
        self.stop_playback()
        sequence = self._selected_sequence()
        if not sequence:
            sequence = list(range(len(self.current_frames())))
        if not sequence:
            return
        if self._current_frame_index in sequence:
            position = sequence.index(self._current_frame_index)
        else:
            position = 0
        position = (position + delta) % len(sequence)
        self._current_sequence_position = position
        self._show_frame(sequence[position])

    def _fps_changed(self, value: int) -> None:
        if self.timer.isActive():
            self.timer.start(max(1, round(1000 / max(1, value))))
        if self._current_frame_index >= 0:
            self._show_frame(self._current_frame_index)

    def _background_changed(self) -> None:
        self.preview.set_background_mode(str(self.background_combo.currentData() or "checker"))

    def _zoom_changed(self, text: str) -> None:
        try:
            zoom = int(text.lstrip("x"))
        except ValueError:
            zoom = 1
        self.preview.set_zoom_multiplier(zoom)

    def _preview_zoom_toggled(self, zoom: int) -> None:
        self.zoom_combo.setCurrentText(f"x{zoom}")

    @staticmethod
    def _selection_mask_hex(indices: list[int], total: int) -> str:
        selected = set(indices)
        chars: list[str] = []
        for start in range(0, total, 4):
            value = 0
            for bit in range(4):
                if start + bit in selected:
                    value |= 1 << bit
            chars.append(format(value, "x"))
        return "".join(chars)

    def apply_settings(self) -> None:
        source = self.current_source()
        selected = self._selected_sequence()
        payload = {
            "source_mode": source,
            "selected_indices": selected,
            "selected_by_source": {key: sorted(values) for key, values in self.selected_by_source.items()},
            "selection_mask_hex": self._selection_mask_hex(selected, len(self.current_frames())),
            "fps": self.fps_spin.value(),
            "loop": self.loop_box.isChecked(),
            "background": str(self.background_combo.currentData() or "checker"),
            "preview_zoom": int(self.zoom_combo.currentText().lstrip("x") or "1"),
        }
        self.settings_applied.emit(payload)
        self.frame_status.setText("Đã áp dụng lựa chọn vào Editor Assets. Nhấn “Áp dụng & lưu” để ghi .ani..dtfe.")

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Space:
            self.toggle_playback()
            event.accept()
            return
        if event.key() == Qt.Key.Key_Left:
            self.step_frame(-1)
            event.accept()
            return
        if event.key() == Qt.Key.Key_Right:
            self.step_frame(1)
            event.accept()
            return
        super().keyPressEvent(event)

    def closeEvent(self, event) -> None:
        self.stop_playback()
        super().closeEvent(event)
