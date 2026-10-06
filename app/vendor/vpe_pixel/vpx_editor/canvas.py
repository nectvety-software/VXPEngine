"""Pixel canvas widget — zoomable, grid-aware, tool-driven painting surface."""

from __future__ import annotations

from typing import List, Optional, Sequence, Tuple

from PySide6.QtCore import Qt, QPoint, QPointF, Signal, QPropertyAnimation, QEasingCurve, Property
from PySide6.QtGui import (
    QPainter, QColor, QPen, QBrush, QPixmap, QImage, QMouseEvent, QWheelEvent,
    QPaintEvent, QResizeEvent, QKeyEvent, QEnterEvent, QLinearGradient,
)
from PySide6.QtWidgets import QWidget, QSizePolicy

from .document import Document
from .theme import get_theme
from .vpe import c565_to_rgb


class CanvasView(QWidget):
    """Interactive RGB565 pixel canvas."""

    cursor_moved = Signal(int, int)          # pixel coords
    pixel_picked = Signal(int)               # RGB565
    document_edited = Signal()
    status_message = Signal(str)
    zoom_changed = Signal(float)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("CanvasHost")
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumSize(280, 240)

        self._doc: Optional[Document] = None
        self._zoom: float = 12.0
        self._offset = QPointF(0, 0)
        self._panning = False
        self._pan_start = QPoint()
        self._painting = False
        self._stroke_active = False
        self._last_px: Optional[tuple] = None
        self._hover_px: Optional[tuple] = None
        self._show_grid = True
        self._show_background = True       # checker / solid bed under the art
        self._transparent_white = False    # "no background": white → see-through
        self._tool = "pencil"
        self._brush_size = 1
        self._color = 0xF800
        self._eraser_color = 0xFFFF
        self._shadow_opacity = 1.0
        self._line_start: Optional[tuple] = None
        self._line_end: Optional[tuple] = None
        self._rect_start: Optional[tuple] = None
        self._rect_end: Optional[tuple] = None
        self._rect_filled = False

        self._pixmap: Optional[QPixmap] = None
        self._ghosts: List[Tuple[int, QPixmap]] = []
        self._onion = False
        self._onion_back = 1
        self._onion_forward = 0
        self._checker = self._make_checker()
        self._theme_on = False

        # Soft drop-shadow under canvas (signature moment).
        self._shadow_anim = QPropertyAnimation(self, b"shadowOpacity", self)
        self._shadow_anim.setDuration(220)
        self._shadow_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._shadow_anim.setStartValue(0.35)
        self._shadow_anim.setEndValue(1.0)

    # --- properties --------------------------------------------------
    def get_shadow_opacity(self) -> float:
        return self._shadow_opacity

    def set_shadow_opacity(self, value: float) -> None:
        self._shadow_opacity = float(value)
        self.update()

    shadowOpacity = Property(float, get_shadow_opacity, set_shadow_opacity)

    # --- public api --------------------------------------------------
    def set_document(self, doc: Optional[Document]) -> None:
        self._doc = doc
        self._rebuild_pixmap()
        self.fit_to_view()
        self.update()

    def document(self) -> Optional[Document]:
        return self._doc

    def set_tool(self, tool: str) -> None:
        self._tool = tool
        self.update()

    def set_brush_size(self, size: int) -> None:
        self._brush_size = max(1, min(int(size), 16))

    def set_color(self, color: int) -> None:
        self._color = color & 0xFFFF

    def color(self) -> int:
        return self._color

    def set_show_grid(self, show: bool) -> None:
        self._show_grid = bool(show)
        self.update()

    def show_grid(self) -> bool:
        return self._show_grid

    def set_show_background(self, show: bool) -> None:
        """Toggle the checker/solid bed painted under the sprite."""
        self._show_background = bool(show)
        self.update()

    def show_background(self) -> bool:
        return self._show_background

    def set_transparent_white(self, on: bool) -> None:
        """No-background mode: treat pure white as transparent."""
        self._transparent_white = bool(on)
        self._rebuild_pixmap()
        self.update()

    def transparent_white(self) -> bool:
        return self._transparent_white

    def set_onion_skin(self, enabled: bool, back: int = 1, forward: int = 0) -> None:
        """Paint neighbouring frames behind the active one as translucent ghosts."""
        self._onion = bool(enabled)
        self._onion_back = max(0, min(int(back), 5))
        self._onion_forward = max(0, min(int(forward), 5))
        self._rebuild_pixmap()
        self.update()

    def onion_skin(self) -> bool:
        return self._onion

    def zoom(self) -> float:
        return self._zoom

    def set_zoom(self, z: float) -> None:
        self._zoom = max(1.0, min(float(z), 64.0))
        self.zoom_changed.emit(self._zoom)
        self.update()

    def zoom_in(self) -> None:
        self.set_zoom(self._zoom * 1.25)

    def zoom_out(self) -> None:
        self.set_zoom(self._zoom / 1.25)

    def fit_to_view(self) -> None:
        if not self._doc:
            return
        margin = 48
        avail_w = max(80, self.width() - margin)
        avail_h = max(80, self.height() - margin)
        zx = avail_w / self._doc.width
        zy = avail_h / self._doc.height
        self.set_zoom(max(1.0, min(zx, zy, 32.0)))
        self._center_content()
        self._shadow_anim.start()

    def _center_content(self) -> None:
        if not self._doc:
            return
        w = self._doc.width * self._zoom
        h = self._doc.height * self._zoom
        self._offset = QPointF((self.width() - w) / 2, (self.height() - h) / 2)

    def refresh(self) -> None:
        self._rebuild_pixmap()
        self.update()

    def toggle_theme_transition(self) -> None:
        self._shadow_anim.setDirection(
            QPropertyAnimation.Direction.Backward
            if self._shadow_opacity > 0.7
            else QPropertyAnimation.Direction.Forward
        )
        self._shadow_anim.start()

    # --- internals ---------------------------------------------------
    def _make_checker(self) -> QPixmap:
        t = get_theme().tokens
        size = 8
        pm = QPixmap(size * 2, size * 2)
        pm.fill(QColor(t["check_a"]))
        p = QPainter(pm)
        p.fillRect(0, 0, size, size, QColor(t["check_b"]))
        p.fillRect(size, size, size, size, QColor(t["check_b"]))
        p.end()
        return pm

    def _rebuild_pixmap(self) -> None:
        doc = self._doc
        if not doc:
            self._pixmap = None
            self._ghosts = []
            return
        transparent = self._transparent_white
        img = QImage(doc.width, doc.height, QImage.Format_ARGB32)
        for y in range(doc.height):
            base = y * doc.width
            for x in range(doc.width):
                px = doc.pixels[base + x]
                r, g, b = c565_to_rgb(px)
                # RGB565 white 0xFFFF → transparent when "no background" is on
                if transparent and px == 0xFFFF:
                    img.setPixel(x, y, 0x00000000)
                else:
                    img.setPixel(x, y, (0xFF << 24) | (r << 16) | (g << 8) | b)
        self._pixmap = QPixmap.fromImage(img)
        self._ghosts = [
            (delta, QPixmap.fromImage(self._ghost_image(pixels, delta)))
            for delta, pixels in doc.onion_frames(
                self._onion_back, self._onion_forward)
        ] if self._onion else []

    def _ghost_image(self, pixels: Sequence, delta: int) -> QImage:
        """Neighbour frame: white always keys out, alpha fades with distance."""
        doc = self._doc
        steps = max(self._onion_back, self._onion_forward, 1)
        alpha = int(150 * (1.0 - (abs(delta) - 1) / steps))
        img = QImage(doc.width, doc.height, QImage.Format_ARGB32)
        img.fill(0x00000000)
        for y in range(doc.height):
            base = y * doc.width
            for x in range(doc.width):
                px = pixels[base + x]
                if px == 0xFFFF:
                    continue
                r, g, b = c565_to_rgb(px)
                img.setPixel(x, y, (alpha << 24) | (r << 16) | (g << 8) | b)
        return img

    def _pixel_at(self, pos: QPoint) -> Optional[tuple]:
        if not self._doc:
            return None
        lx = (pos.x() - self._offset.x()) / self._zoom
        ly = (pos.y() - self._offset.y()) / self._zoom
        x, y = int(lx), int(ly)
        if 0 <= x < self._doc.width and 0 <= y < self._doc.height:
            return x, y
        return None

    def _canvas_rect(self):
        if not self._doc:
            return None
        return (
            self._offset.x(),
            self._offset.y(),
            self._doc.width * self._zoom,
            self._doc.height * self._zoom,
        )

    # --- painting ----------------------------------------------------
    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        t = get_theme().tokens
        painter.fillRect(self.rect(), QColor(t["canvas_bg"]))

        rect = self._canvas_rect()
        if not rect or not self._pixmap:
            painter.setPen(QColor(t["muted"]))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "No document")
            painter.end()
            return

        x, y, w, h = rect

        # Soft elevated drop shadow (signature moment).
        shadow = QColor(0, 0, 0, int(70 * self._shadow_opacity))
        for i in range(8, 0, -2):
            painter.fillRect(
                int(x - i), int(y - i + 4), int(w + i * 2), int(h + i * 2),
                QColor(0, 0, 0, int((10 + i) * self._shadow_opacity * 0.35)),
            )
        painter.fillRect(int(x), int(y), int(w), int(h), QColor(t["canvas_border"]))

        # Background bed: checker under the sprite (off = plain canvas bg)
        painter.save()
        painter.translate(QPointF(x, y))
        painter.setClipRect(0, 0, int(w), int(h))
        if self._show_background:
            painter.fillRect(0, 0, int(w), int(h), QBrush(self._checker))
        else:
            painter.fillRect(0, 0, int(w), int(h), QColor(t["canvas_bg"]))
        for _delta, ghost in self._ghosts:
            painter.drawPixmap(0, 0, int(w), int(h), ghost)
        painter.drawPixmap(0, 0, int(w), int(h), self._pixmap)

        # Grid
        if self._show_grid and self._zoom >= 4:
            pen = QPen(QColor(t["grid"]))
            pen.setWidth(1)
            pen.setCosmetic(True)
            painter.setPen(pen)
            # Fade grid at low zoom via lighter alpha
            for gx in range(self._doc.width + 1):
                px = gx * self._zoom
                painter.drawLine(QPointF(px, 0), QPointF(px, h))
            for gy in range(self._doc.height + 1):
                py = gy * self._zoom
                painter.drawLine(QPointF(0, py), QPointF(w, py))

        # Hover outline
        if self._hover_px:
            hx, hy = self._hover_px
            pen = QPen(QColor(t["accent"]))
            pen.setWidth(2)
            painter.setPen(pen)
            painter.drawRect(int(hx * self._zoom), int(hy * self._zoom),
                             int(self._zoom), int(self._zoom))

        # Preview: line / rect
        if self._tool == "line" and self._line_start and self._line_end:
            pen = QPen(QColor(t["accent"]))
            pen.setWidth(max(1, int(self._brush_size * self._zoom * 0.5)))
            painter.setPen(pen)
            x0, y0 = self._line_start
            x1, y1 = self._line_end
            painter.drawLine(
                QPointF((x0 + 0.5) * self._zoom, (y0 + 0.5) * self._zoom),
                QPointF((x1 + 0.5) * self._zoom, (y1 + 0.5) * self._zoom),
            )
        if self._tool in ("rect", "rectfill") and self._rect_start and self._rect_end:
            pen = QPen(QColor(t["accent"]))
            pen.setWidth(2)
            painter.setPen(pen)
            xa, ya = self._rect_start
            xb, yb = self._rect_end
            rx0 = min(xa, xb) * self._zoom
            ry0 = min(ya, yb) * self._zoom
            rw = (abs(xb - xa) + 1) * self._zoom
            rh = (abs(yb - ya) + 1) * self._zoom
            if self._rect_filled:
                painter.fillRect(QPointF(rx0, ry0).toPoint(), int(rw), int(rh),
                                 QColor(t["accent"]))
            painter.drawRect(int(rx0), int(ry0), int(rw), int(rh))

        painter.restore()

        # Outer canvas frame
        painter.setPen(QPen(QColor(t["canvas_border"]), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(int(x) - 1, int(y) - 1, int(w) + 1, int(h) + 1)
        painter.end()

    # --- interaction -------------------------------------------------
    def wheelEvent(self, event: QWheelEvent) -> None:
        if event.angleDelta().y() > 0:
            self.zoom_in()
        else:
            self.zoom_out()
        event.accept()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        pos = event.position().toPoint()
        if event.button() == Qt.MouseButton.MiddleButton or (
            event.button() == Qt.MouseButton.RightButton
        ):
            self._panning = True
            self._pan_start = pos
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            return

        px = self._pixel_at(pos)
        if px is None:
            return
        x, y = px

        if self._tool == "pick":
            c = self._doc.pick(x, y)
            if c is not None:
                self._color = c
                self.pixel_picked.emit(c)
            return

        if self._tool == "fill":
            self._doc.begin_stroke("Fill")
            self._doc.flood_fill(x, y, self._color)
            self._doc.end_stroke()
            self._rebuild_pixmap()
            self.document_edited.emit()
            self.update()
            return

        if self._tool == "line":
            self._line_start = (x, y)
            self._line_end = (x, y)
            self.update()
            return

        if self._tool in ("rect", "rectfill"):
            self._rect_start = (x, y)
            self._rect_end = (x, y)
            self._rect_filled = self._tool == "rectfill"
            self.update()
            return

        # pencil / eraser
        self._painting = True
        self._stroke_active = True
        self._doc.begin_stroke("Draw" if self._tool == "pencil" else "Erase")
        color = self._color if self._tool != "eraser" else self._eraser_color
        self._doc.paint_brush(x, y, self._brush_size, color)
        self._last_px = (x, y)
        self._rebuild_pixmap()
        self.update()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        pos = event.position().toPoint()
        if self._panning:
            delta = pos - self._pan_start
            self._pan_start = pos
            self._offset += QPointF(delta)
            self.update()
            return

        px = self._pixel_at(pos)
        self._hover_px = px
        if px:
            self.cursor_moved.emit(px[0], px[1])

        if self._tool == "line" and self._line_start and (event.buttons() & Qt.MouseButton.LeftButton):
            if px:
                self._line_end = px
            self.update()
            return

        if self._tool in ("rect", "rectfill") and self._rect_start and (event.buttons() & Qt.MouseButton.LeftButton):
            if px:
                self._rect_end = px
            self.update()
            return

        if self._painting and px and self._last_px:
            x, y = px
            lx, ly = self._last_px
            color = self._color if self._tool != "eraser" else self._eraser_color
            self._doc.paint_line(lx, ly, x, y, self._brush_size, color)
            self._last_px = (x, y)
            self._rebuild_pixmap()
            self.document_edited.emit()
            self.update()
        else:
            self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if self._panning and event.button() in (
            Qt.MouseButton.MiddleButton, Qt.MouseButton.RightButton
        ):
            self._panning = False
            self.unsetCursor()
            return

        if self._tool == "line" and self._line_start and self._line_end:
            self._doc.begin_stroke("Line")
            x0, y0 = self._line_start
            x1, y1 = self._line_end
            self._doc.paint_line(x0, y0, x1, y1, self._brush_size, self._color)
            self._doc.end_stroke()
            self._line_start = self._line_end = None
            self._rebuild_pixmap()
            self.document_edited.emit()
            self.update()
            return

        if self._tool in ("rect", "rectfill") and self._rect_start and self._rect_end:
            self._doc.begin_stroke("Rect")
            xa, ya = self._rect_start
            xb, yb = self._rect_end
            self._doc.paint_rect(xa, ya, xb, yb, self._brush_size, self._color,
                                filled=self._tool == "rectfill")
            self._doc.end_stroke()
            self._rect_start = self._rect_end = None
            self._rebuild_pixmap()
            self.document_edited.emit()
            self.update()
            return

        if self._painting and self._stroke_active:
            self._painting = False
            self._stroke_active = False
            self._last_px = None
            self._doc.end_stroke()
            self.document_edited.emit()
            self.update()

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.fit_to_view()

    def leaveEvent(self, event) -> None:
        self._hover_px = None
        self.update()
        super().leaveEvent(event)

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        if self._doc:
            self._center_content()
