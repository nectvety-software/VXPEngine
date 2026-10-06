"""Animation timeline: frame strip, playback, onion-skin and frame tools.

The bar owns no pixel data — it reads and mutates `Document.frames`, then tells
the window that the canvas has to be rebuilt.
"""

from __future__ import annotations

from typing import List, Optional

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QColor, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QLineEdit, QPushButton,
    QScrollArea, QSpinBox, QSizePolicy,
)

from . import icons
from .document import Document
from .theme import get_theme
from .vpe import c565_to_rgb
from .vpea import MAX_FRAMES

CHIP_W, CHIP_H = 54, 54


def set_tip(widget: QWidget, text: str) -> None:
    """Tooltip for a control and the line edit embedded in a spin box."""
    widget.setToolTip(text)
    for line in widget.findChildren(QLineEdit):
        line.setToolTip(text)


def frame_image(width: int, height: int, pixels, alpha: int = 255) -> QImage:
    """RGB565 buffer → ARGB32 image with white keyed out (animation preview)."""
    img = QImage(width, height, QImage.Format_ARGB32)
    img.fill(0x00000000)
    for y in range(height):
        base = y * width
        for x in range(width):
            px = pixels[base + x]
            if px == 0xFFFF:
                continue
            r, g, b = c565_to_rgb(px)
            img.setPixel(x, y, (alpha << 24) | (r << 16) | (g << 8) | b)
    return img


class FrameChip(QWidget):
    """One frame in the strip: thumbnail, index, selected state."""

    clicked = Signal(int)

    def __init__(self, index: int, parent=None) -> None:
        super().__init__(parent)
        self.index = index
        self.selected = False
        self._pixmap: Optional[QPixmap] = None
        self.setFixedSize(CHIP_W + 8, CHIP_H + 24)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def set_frame(self, doc: Document, index: int, selected: bool) -> None:
        self.index, self.selected = index, selected
        self._pixmap = QPixmap.fromImage(
            frame_image(doc.width, doc.height, doc.frames[index]))
        self.setToolTip(f"Frame {index + 1} of {doc.frame_count()} — click to edit")
        self.update()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.index)
            event.accept()
        else:
            super().mousePressEvent(event)

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        t = get_theme().tokens
        p.fillRect(4, 4, CHIP_W, CHIP_H, QColor(t["input"]))
        if self._pixmap is not None:
            p.drawPixmap(4, 4, CHIP_W, CHIP_H, self._pixmap)
        pen = QPen(QColor(t["accent"] if self.selected else t["border"]))
        pen.setWidth(2 if self.selected else 1)
        p.setPen(pen)
        p.drawRect(4, 4, CHIP_W - 1, CHIP_H - 1)
        p.setPen(QColor(t["accent"] if self.selected else t["muted"]))
        p.drawText(0, CHIP_H + 8, self.width(), 14,
                   Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
                   str(self.index + 1))
        p.end()


class TimelineBar(QWidget):
    frame_selected = Signal(int)
    structure_changed = Signal()
    onion_changed = Signal(bool, int)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._doc: Optional[Document] = None
        self._chips: List[FrameChip] = []
        self._playing = False
        self._onion_paused = False
        self.setObjectName("Panel")

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 6, 10, 6)
        outer.setSpacing(5)
        row = QHBoxLayout()
        row.setSpacing(6)
        outer.addLayout(row)

        caption = QLabel("ANIMATION")
        caption.setObjectName("Muted")
        row.addWidget(caption)
        self._count = QLabel("1 frame")
        self._count.setObjectName("Muted")
        row.addWidget(self._count)
        row.addSpacing(8)

        def button(icon_name: str, tip: str, slot) -> QPushButton:
            b = QPushButton()
            b.setObjectName("Ghost")
            b.setFixedSize(28, 28)
            icons.set_icon(b, icon_name, 14, token="text", tooltip=tip)
            b.clicked.connect(slot)
            row.addWidget(b)
            return b

        button("prev_frame", "Previous frame (,)", lambda: self.step_frame(-1))
        self._play_btn = button("play", "Play the animation (Space)", self.toggle_play)
        button("next_frame", "Next frame (.)", lambda: self.step_frame(1))
        button("stop", "Stop playback (Esc)", self.stop)
        row.addSpacing(6)
        button("new", "Add an empty frame after the current one (Ctrl+Alt+N)",
               self.add_frame)
        button("duplicate", "Duplicate the current frame (Ctrl+D)", self.duplicate_frame)
        button("delete", "Delete the current frame (Ctrl+Shift+K)", self.delete_frame)
        button("undo", "Move the current frame one place back (Ctrl+Alt+Left)",
               lambda: self.move_frame(-1))
        button("redo", "Move the current frame one place forward (Ctrl+Alt+Right)",
               lambda: self.move_frame(1))
        row.addSpacing(6)

        self._fps = QSpinBox()
        self._fps.setRange(1, 30)
        self._fps.setValue(8)
        self._fps.setSuffix(" fps")
        set_tip(self._fps, "Playback speed — frame delay is 1000/fps ms")
        self._fps.valueChanged.connect(self._fps_changed)
        row.addWidget(self._fps)

        self._loop = QPushButton("Loop")
        self._loop.setObjectName("Ghost")
        self._loop.setCheckable(True)
        self._loop.setChecked(True)
        self._loop.setMinimumHeight(28)
        self._loop.setToolTip("Restart at frame 1 after the last frame")
        self._loop.toggled.connect(self._loop_changed)

        self._onion = QPushButton()
        icons.set_icon(self._onion, "onion", 15, token="text",
                       tooltip="Ghost the neighbouring frames behind the one "
                               "you edit (Ctrl+O)")
        self._onion.setObjectName("Ghost")
        self._onion.setCheckable(True)
        self._onion.setMinimumHeight(28)
        self._onion.toggled.connect(self._onion_toggled)
        row.addWidget(self._onion)

        self._onion_count = QSpinBox()
        self._onion_count.setRange(1, 5)
        self._onion_count.setValue(1)
        set_tip(self._onion_count, "How many frames back to ghost")
        self._onion_count.valueChanged.connect(
            lambda _n: self._onion_toggled(self._onion.isChecked()))
        row.addWidget(self._onion_count)
        row.addWidget(self._loop)

        row.addStretch(1)

        # The strip owns the whole second row: with N frames it is the part of
        # the bar that has to grow, not the fixed transport controls.
        self._strip_host = QScrollArea()
        self._strip_host.setWidgetResizable(True)
        self._strip_host.setFrameShape(QScrollArea.Shape.NoFrame)
        self._strip_host.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._strip_host.setFixedHeight(CHIP_H + 24)
        self._strip = QWidget()
        self._strip_lay = QHBoxLayout(self._strip)
        self._strip_lay.setContentsMargins(0, 0, 0, 0)
        self._strip_lay.setSpacing(2)
        self._strip_lay.addStretch(1)
        self._strip_host.setWidget(self._strip)
        outer.addWidget(self._strip_host)

    # ------------------------------------------------------------------ api
    def set_document(self, doc: Document) -> None:
        self.stop()
        self._doc = doc
        self._fps.blockSignals(True)
        self._fps.setValue(max(1, min(round(1000 / max(doc.delay_ms, 1)), 30)))
        self._fps.blockSignals(False)
        self._loop.blockSignals(True)
        self._loop.setChecked(doc.loop)
        self._loop.blockSignals(False)
        self.rebuild()

    def document(self) -> Optional[Document]:
        return self._doc

    def rebuild(self) -> None:
        doc = self._doc
        if doc is None:
            return
        while len(self._chips) < doc.frame_count():
            chip = FrameChip(len(self._chips))
            chip.clicked.connect(self.select)
            self._chips.append(chip)
            self._strip_lay.insertWidget(self._strip_lay.count() - 1, chip)
        while len(self._chips) > doc.frame_count():
            chip = self._chips.pop()
            self._strip_lay.removeWidget(chip)
            chip.deleteLater()
        for i, chip in enumerate(self._chips):
            chip.set_frame(doc, i, i == doc.frame)
        n = doc.frame_count()
        self._count.setText(
            f"{n} frame{'s' if n != 1 else ''} · {doc.delay_ms} ms · "
            f"frame {doc.frame + 1}")

    def refresh_thumbnails(self) -> None:
        """Call after painting: only the current chip's bitmap changed."""
        doc = self._doc
        if doc is not None and doc.frame < len(self._chips):
            self._chips[doc.frame].set_frame(doc, doc.frame, True)

    def select(self, index: int) -> None:
        doc = self._doc
        if doc is None:
            return
        doc.goto_frame(index)
        for i, chip in enumerate(self._chips):
            chip.selected = (i == doc.frame)
            chip.update()
        self._count.setText(
            f"{doc.frame_count()} frame"
            f"{'s' if doc.frame_count() != 1 else ''} · {doc.delay_ms} ms · "
            f"frame {doc.frame + 1}")
        self.frame_selected.emit(doc.frame)

    # ------------------------------------------------------------- playback
    def toggle_play(self) -> None:
        if self._playing:
            self.stop()
        else:
            self.start()

    def start(self) -> None:
        doc = self._doc
        if doc is None or doc.frame_count() < 2:
            return
        self._playing = True
        icons.set_icon(self._play_btn, "pause", 14, token="text",
                       tooltip="Pause playback (Space)")
        if self._onion.isChecked():
            self._onion_paused = True
            self._onion.setChecked(False)
        self._timer.start(max(20, doc.delay_ms))

    def stop(self) -> None:
        self._playing = False
        self._timer.stop()
        icons.set_icon(self._play_btn, "play", 14, token="text",
                       tooltip="Play the animation (Space)")
        if self._onion_paused:
            self._onion_paused = False
            self._onion.setChecked(True)

    def playing(self) -> bool:
        return self._playing

    def _tick(self) -> None:
        doc = self._doc
        if doc is None:
            self.stop()
            return
        nxt = doc.frame + 1
        if nxt >= doc.frame_count():
            if not doc.loop:
                self.stop()
                return
            nxt = 0
        self.select(nxt)

    # ---------------------------------------------------------- frame tools
    def step_frame(self, delta: int) -> None:
        """Wrap around the strip so , and . keep cycling."""
        doc = self._doc
        if doc:
            self.select((doc.frame + int(delta)) % doc.frame_count())

    def prev_frame(self) -> None:
        self.step_frame(-1)

    def next_frame(self) -> None:
        self.step_frame(1)

    def add_frame(self) -> None:
        if self._doc and self._doc.frame_count() < MAX_FRAMES:
            self._doc.add_frame()
            self.rebuild()
            self.structure_changed.emit()

    def duplicate_frame(self) -> None:
        if self._doc and self._doc.frame_count() < MAX_FRAMES:
            self._doc.duplicate_frame()
            self.rebuild()
            self.structure_changed.emit()

    def delete_frame(self) -> None:
        if self._doc and self._doc.delete_frame():
            self.rebuild()
            self.structure_changed.emit()

    def move_frame(self, delta: int) -> None:
        if self._doc and self._doc.move_frame(self._doc.frame,
                                              self._doc.frame + int(delta)):
            self.rebuild()
            self.structure_changed.emit()

    def toggle_onion(self) -> None:
        self._onion.toggle()

    def _fps_changed(self, fps: int) -> None:
        if self._doc:
            self._doc.delay_ms = max(10, round(1000 / max(1, int(fps))))
            if self._playing:
                self._timer.setInterval(max(20, self._doc.delay_ms))
            self.rebuild()
            self.structure_changed.emit()

    def _loop_changed(self, on: bool) -> None:
        if self._doc:
            self._doc.loop = bool(on)
            self._doc.dirty = True
            self.structure_changed.emit()

    def _onion_toggled(self, on: bool) -> None:
        if self._onion.isChecked() != bool(on):
            self._onion.setChecked(bool(on))
        self.onion_changed.emit(bool(on), self._onion_count.value())
