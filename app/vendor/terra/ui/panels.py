"""Editor panels: tile grid browser, layer stack, inspector, log."""

from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import QPoint, QRect, QSize, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (QAbstractItemView, QAbstractScrollArea, QApplication, QCheckBox,
                               QFrame, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
                               QPlainTextEdit, QPushButton, QSpinBox, QVBoxLayout, QWidget)

from . import icons, qtimg
from .theme import colors as theme_colors

THUMB = 32
PAD = 6
ROW_HEIGHT = 34


class Section(QFrame):
    """Titled group used across the side panels."""

    def __init__(self, title: str, parent: QWidget | None = None, action: QWidget | None = None):
        super().__init__(parent)
        self.setProperty("role", "panel")
        box = QVBoxLayout(self)
        box.setContentsMargins(12, 10, 12, 12)
        box.setSpacing(8)

        head = QHBoxLayout()
        cap = QLabel(title)
        cap.setProperty("role", "section")
        head.addWidget(cap)
        head.addStretch(1)
        if action:
            head.addWidget(action)
        box.addLayout(head)
        self.content = QVBoxLayout()
        self.content.setSpacing(8)
        box.addLayout(self.content)

    def add(self, widget: QWidget) -> QWidget:
        self.content.addWidget(widget)
        return widget

    def add_row(self, layout: QHBoxLayout) -> None:
        self.content.addLayout(layout)


def labelled(caption: str, widget: QWidget) -> QHBoxLayout:
    row = QHBoxLayout()
    row.setSpacing(8)
    label = QLabel(caption)
    label.setProperty("role", "muted")
    label.setMinimumWidth(86)
    row.addWidget(label)
    row.addWidget(widget, 1)
    return row


def divider() -> QFrame:
    line = QFrame()
    line.setProperty("role", "divider")
    line.setFixedHeight(1)
    return line


class IconButton(QPushButton):
    """Flat glyph button whose icon follows the palette and the checked state."""

    def __init__(self, glyph: str, tip: str = "", checkable: bool = False, size: int = 16,
                 role: str = "tool", parent: QWidget | None = None):
        super().__init__(parent)
        self.glyph = glyph
        self._size = size
        self.setProperty("role", role)
        self.setCheckable(checkable)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip(tip)
        self.setFlat(True)
        self.toggled.connect(lambda _: self.restyle())
        self.restyle()

    def restyle(self) -> None:
        pal = theme_colors(self)
        tint = pal["accent"] if (self.isCheckable() and self.isChecked()) else pal["text_muted"]
        self.setIcon(icons.icon(self.glyph, tint, self._size))


class TileGrid(QAbstractScrollArea):
    """Virtualised tile browser over the engine's sheet."""

    tilePicked = Signal(int)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.sheet = None
        self.version = 0
        self.current = 0
        self.hover = -1
        self.cell = THUMB + PAD * 2
        self.setFrameShape(QFrame.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.viewport().setMouseTracking(True)
        self.viewport().setCursor(Qt.PointingHandCursor)

    def set_sheet(self, sheet, version: int = 0) -> None:
        self.sheet = sheet
        self.version = version
        self.current = 0
        self._relayout()
        self.viewport().update()

    # ------------------------------------------------------------ geometry

    def _columns(self) -> int:
        return max(1, (self.viewport().width() - 4) // self.cell)

    def _rows(self) -> int:
        return 0 if not self.sheet else -(-self.sheet.count // self._columns())

    def _relayout(self) -> None:
        need = self._rows() * self.cell + PAD
        bar = self.verticalScrollBar()
        bar.setRange(0, max(0, need - self.viewport().height()))
        bar.setSingleStep(self.cell)
        bar.setPageStep(self.viewport().height())

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._relayout()

    def wheelEvent(self, event) -> None:
        bar = self.verticalScrollBar()
        bar.setValue(bar.value() - (event.angleDelta().y() // 120) * self.cell * 2)
        event.accept()

    def _index_at(self, pos: QPoint) -> int:
        if not self.sheet:
            return -1
        cols = self._columns()
        y = pos.y() + self.verticalScrollBar().value() - PAD
        if y < 0 or pos.x() < 2:
            return -1
        row, col = y // self.cell, (pos.x() - 2) // self.cell
        if col >= cols or row >= self._rows():
            return -1
        index = int(row * cols + col)
        return index if index < self.sheet.count else -1

    # --------------------------------------------------------------- input

    def mousePressEvent(self, event) -> None:
        index = self._index_at(event.position().toPoint())
        if index >= 0 and self.sheet and not self.sheet.tile(index).blank:
            self.current = index
            self.tilePicked.emit(index)
            self.viewport().update()

    def mouseMoveEvent(self, event) -> None:
        index = self._index_at(event.position().toPoint())
        if index != self.hover:
            self.hover = index
            self.viewport().update()

    def leaveEvent(self, event) -> None:
        self.hover = -1
        self.viewport().update()

    # -------------------------------------------------------------- render

    def paintEvent(self, event) -> None:
        pal = theme_colors(self)
        painter = QPainter(self.viewport())
        painter.fillRect(self.viewport().rect(), QColor(pal["panel"]))
        if not self.sheet:
            painter.setPen(QColor(pal["text_faint"]))
            painter.drawText(self.viewport().rect(), Qt.AlignCenter, "Chưa nạp tilesheet")
            return
        painter.setRenderHint(QPainter.Antialiasing, False)
        cols = self._columns()
        offset = self.verticalScrollBar().value()
        first = max(0, (offset - PAD) // self.cell)
        last = min(self._rows(), first + self.viewport().height() // self.cell + 2)
        for row in range(first, last):
            for col in range(cols):
                index = row * cols + col
                if index >= self.sheet.count:
                    break
                rect = QRect(2 + col * self.cell, PAD + row * self.cell - offset, THUMB, THUMB)
                tile = self.sheet.tile(index)
                if tile.blank:
                    painter.fillRect(rect, QColor(pal["input"]))
                    painter.setPen(QPen(QColor(pal["border"]), 1))
                    painter.drawLine(rect.topLeft(), rect.bottomRight())
                    continue
                painter.fillRect(rect, QColor(pal["checker_a"]))
                image = qtimg.tile_image(self.sheet, index, self.version)
                if image:
                    painter.drawImage(rect, image)
                if index == self.current:
                    painter.setPen(QPen(QColor(pal["accent"]), 2))
                    painter.setBrush(Qt.NoBrush)
                    painter.drawRect(rect.adjusted(-1, -1, 1, 1))
                elif index == self.hover:
                    painter.setPen(QPen(QColor(pal["border_strong"]), 1))
                    painter.setBrush(Qt.NoBrush)
                    painter.drawRect(rect)
        painter.end()


class LayersPanel(QListWidget):
    """Top layer first; each row carries visibility, opacity readout and lock."""

    layerSelected = Signal(int)
    visibilityToggled = Signal(int, bool)
    lockToggled = Signal(int, bool)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setSpacing(1)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.itemSelectionChanged.connect(
            lambda: self.currentRow() >= 0 and self.layerSelected.emit(
                self.count() - 1 - self.currentRow()))

    def sync(self, layers, active: int) -> None:
        self.blockSignals(True)
        self.clear()
        for index in range(len(layers) - 1, -1, -1):
            item = QListWidgetItem()
            item.setSizeHint(QSize(0, ROW_HEIGHT))
            self.addItem(item)
            self.setItemWidget(item, self._make_row(layers[index], index))
        row = self.count() - 1 - min(active, len(layers) - 1)
        self.setCurrentRow(max(0, row))
        self.blockSignals(False)

    def _make_row(self, layer, index: int) -> QWidget:
        row = QWidget()
        lay = QHBoxLayout(row)
        lay.setContentsMargins(6, 3, 6, 3)
        lay.setSpacing(7)

        eye = IconButton("eye" if layer.visible else "eye-off", "Ẩn / hiện lớp",
                         checkable=True, size=15)
        eye.setChecked(layer.visible)
        eye.toggled.connect(lambda v: self.visibilityToggled.emit(index, v))

        name = QLabel(layer.name)
        lock = IconButton("lock", "Khóa lớp", checkable=True, size=15)
        lock.setChecked(layer.locked)
        lock.toggled.connect(lambda v: self.lockToggled.emit(index, v))
        opacity = QLabel(f"{int(layer.opacity * 100)}%")
        opacity.setProperty("role", "faint")

        lay.addWidget(eye)
        lay.addWidget(name, 1)
        lay.addWidget(opacity)
        lay.addWidget(lock)
        return row


class InspectorPanel(Section):
    """Live document statistics plus view toggles."""

    gridToggled = Signal(bool)
    labelsToggled = Signal(bool)
    zoomRequested = Signal(int)

    def __init__(self, parent: QWidget | None = None):
        super().__init__("Inspector", parent)
        self.stats: dict[str, QLabel] = {}
        self._build()

    def _build(self) -> None:
        checks = QHBoxLayout()
        checks.setSpacing(14)
        self.grid_check = QCheckBox("Lưới tile")
        self.grid_check.setChecked(True)
        self.grid_check.toggled.connect(self.gridToggled)
        self.labels_check = QCheckBox("Nhãn ô")
        self.labels_check.toggled.connect(self.labelsToggled)
        checks.addWidget(self.grid_check)
        checks.addWidget(self.labels_check)
        checks.addStretch(1)
        self.add_row(checks)
        self.add(divider())

        self.zoom = QSpinBox()
        self.zoom.setRange(5, 1200)
        self.zoom.setSuffix(" %")
        self.zoom.setFixedWidth(104)
        self.zoom.valueChanged.connect(self.zoomRequested)
        self.add_row(labelled("Phóng to", self.zoom))

        for key, caption in (("map", "Map"), ("pixels", "Pixel"), ("tile", "Tile"),
                             ("layers", "Lớp"), ("placed", "Đã đặt"),
                             ("distinct", "Tile lạ"), ("sheet", "Sheet")):
            value = QLabel("—")
            value.setProperty("role", "statValue")
            self.stats[key] = value
            self.add_row(labelled(caption, value))

    def refresh(self, project, zoom: float | None = None) -> None:
        if not project:
            return
        st = project.stats()
        for key, text in (("map", st["map"]), ("pixels", st["pixels"]),
                          ("tile", st["tile_size"]), ("layers", str(st["layers"])),
                          ("placed", str(st["placed"])),
                          ("distinct", str(st["distinct_tiles"])),
                          ("sheet", f"{st['sheet_solid']}/{st['sheet_tiles']}"
                           if st["sheet_tiles"] else "—")):
            self.stats[key].setText(text)
        if zoom is not None:
            self.zoom.blockSignals(True)
            self.zoom.setValue(int(round(zoom * 100)))
            self.zoom.blockSignals(False)


class LogPanel(QPlainTextEdit):
    """Timestamped activity feed — the panel an agent reads to audit a session."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setMaximumBlockCount(300)
        self.setFrameShape(QFrame.NoFrame)

    def log(self, message: str, kind: str = "info") -> None:
        pal = theme_colors(self)
        tone = {"info": pal["text_muted"], "ok": pal["success"], "warn": pal["warn"],
                "error": pal["danger"]}.get(kind, pal["text_muted"])
        stamp = datetime.now().strftime("%H:%M:%S")
        self.appendHtml(f'<span style="color:{pal["text_faint"]}">{stamp}</span>'
                        f'&nbsp;&nbsp;<span style="color:{tone}">{message}</span>')
