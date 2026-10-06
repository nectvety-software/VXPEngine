"""Map canvas: engine batches painted through QPainter, with pan/zoom/paint input."""

from __future__ import annotations

from PySide6.QtCore import QPoint, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QApplication, QWidget, QSizePolicy

from ..engine.camera import Camera2D
from ..engine.renderer import build_batches
from ..engine.tilemap import EMPTY
from . import qtimg
from .theme import colors as theme_colors

TOOLS = ("brush", "eraser", "fill", "line", "rect")


class MapCanvas(QWidget):
    """The editor viewport. Holds no document state of its own beyond the camera."""

    paintCommitted = Signal(str, list)      # label, edits
    cursorMoved = Signal(int, int)          # tile coords, -1 when outside
    zoomChanged = Signal(float)
    toolChanged = Signal(str)

    def __init__(self, project=None, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("Canvas")
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setAttribute(Qt.WA_OpaquePaintEvent, False)

        self.project = project
        self.camera = Camera2D()
        self.tool = "brush"
        self.tile = 0
        self.show_grid = True
        self.show_labels = False
        self._panning = False
        self._painting = False
        self._last_tile = QPoint()
        self._anchor = QPoint()
        self._preview: list[tuple[int, int]] = []
        self._edits: list = []
        self._space = False
        self._pending_tool = "brush"
        self._hover: QPoint | None = None
        self._last_pos = QPointF()

    # ------------------------------------------------------------------ doc

    def set_project(self, project) -> None:
        self.project = project
        qtimg.clear_cache()
        self.camera.viewport = (self.width(), self.height())
        if project:
            self.camera.fit(*project.map.pixel_size)
        self.update()

    def set_tool(self, tool: str) -> None:
        if tool in TOOLS:
            self.tool = tool
            self.toolChanged.emit(tool)
            self.update()

    def set_tile(self, tile: int) -> None:
        self.tile = tile
        if self.tool == "eraser":
            self.set_tool("brush")
        self.update()

    def set_grid(self, value: bool) -> None:
        self.show_grid = value
        self.update()

    def set_labels(self, value: bool) -> None:
        self.show_labels = value
        self.update()

    # ------------------------------------------------------------- geometry

    def tile_at(self, point: QPointF) -> QPoint:
        if not self.project:
            return QPoint(-1, -1)
        wx, wy = self.camera.screen_to_world(point.x(), point.y())
        return QPoint(int(wx // self.project.map.tile_w), int(wy // self.project.map.tile_h))

    def inside(self, tile: QPoint) -> bool:
        if not self.project:
            return False
        m = self.project.map
        return m.width > 0 and m.height > 0 and 0 <= tile.x() < m.width and 0 <= tile.y() < m.height

    # --------------------------------------------------------------- events

    def resizeEvent(self, event) -> None:
        self.camera.viewport = (self.width(), self.height())
        self.update()
        super().resizeEvent(event)

    def wheelEvent(self, event) -> None:
        delta = event.angleDelta().y()
        if delta == 0:
            return
        factor = 1.0015 ** delta
        self.camera.zoom_at(factor, event.position().x(), event.position().y())
        self.zoomChanged.emit(self.camera.zoom)
        self.update()
        event.accept()

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key_Space and not event.isAutoRepeat():
            self._space = True
            self.setCursor(Qt.OpenHandCursor)
            return
        step = {Qt.Key_Left: (-1, 0), Qt.Key_Right: (1, 0), Qt.Key_Up: (0, -1),
                Qt.Key_Down: (0, 1)}.get(event.key())
        if step:
            scale = 16 / self.camera.zoom
            self.camera.x += step[0] * scale
            self.camera.y += step[1] * scale
            self.update()
            return
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event) -> None:
        if event.key() == Qt.Key_Space and not event.isAutoRepeat():
            self._space = False
            if not self._panning:
                self.unsetCursor()
        super().keyReleaseEvent(event)

    def mousePressEvent(self, event) -> None:
        pos = event.position()
        middle = event.button() == Qt.MiddleButton
        if middle or self._space or (event.button() == Qt.LeftButton
                                     and event.modifiers() & Qt.AltModifier):
            self._panning = True
            self._last_pos = pos
            self.setCursor(Qt.ClosedHandCursor)
            self.setFocus()
            return
        if not self.project:
            return
        tile = self.tile_at(pos)
        if not self.inside(tile):
            return
        self.setFocus()
        if event.button() == Qt.RightButton:
            self._begin(tile, "eraser")
        elif event.button() == Qt.LeftButton:
            self._begin(tile, self.tool)

    def mouseMoveEvent(self, event) -> None:
        pos = event.position()
        tile = self.tile_at(pos)
        inside = self.inside(tile)
        self.cursorMoved.emit(tile.x() if inside else -1, tile.y() if inside else -1)
        if inside and tile != self._hover:
            self._hover = tile
            self.update()
        if self._panning:
            self.camera.pan_pixels(pos.x() - self._last_pos.x(), pos.y() - self._last_pos.y())
            self._last_pos = pos
            self.update()
            return
        if self._painting:
            if self.tool in ("line", "rect") or self._pending_tool in ("line", "rect"):
                self._update_shape(tile)
            elif tile != self._anchor:
                self._stroke_to(tile)
            return
        if self.inside(tile):
            self.update()

    def mouseReleaseEvent(self, event) -> None:
        if self._panning:
            self._panning = False
            self.setCursor(Qt.OpenHandCursor if self._space else Qt.ArrowCursor)
            return
        if not self._painting:
            return
        tile = self.tile_at(event.position())
        if self._pending_tool in ("line", "rect"):
            self._commit_shape(tile)
        self._painting = False
        self._preview = []
        self._commit()
        self.update()

    # ------------------------------------------------------------- painting

    def _begin(self, tile: QPoint, tool: str) -> None:
        self._painting = True
        self._pending_tool = tool
        self._anchor = tile
        self._last_tile = tile
        self._edits = []
        if tool == "fill":
            self._edits += self.project.map.flood_fill(tile.x(), tile.y(),
                                                       EMPTY if tool == "eraser" else self.tile)
            self._painting = False
            self._commit("Nền vùng")
        elif tool in ("line", "rect"):
            self._preview = [(tile.x(), tile.y())]
        else:
            value = EMPTY if tool == "eraser" else self.tile
            self._edits += self.project.map.paint(tile.x(), tile.y(), value)
        self.update()

    def _stroke_to(self, tile: QPoint) -> None:
        value = EMPTY if self._pending_tool == "eraser" else self.tile
        self._edits += self.project.map.paint_line(self._last_tile.x(), self._last_tile.y(),
                                                   tile.x(), tile.y(), value)
        self._last_tile = tile
        self.update()

    def _shape_coords(self, tile: QPoint):
        m = self.project.map
        xa, xb = sorted((self._anchor.x(), max(0, min(m.width - 1, tile.x()))))
        ya, yb = sorted((self._anchor.y(), max(0, min(m.height - 1, tile.y()))))
        if self._pending_tool == "rect":
            return [(x, y) for y in range(ya, yb + 1) for x in range(xa, xb + 1)
                    if x in (xa, xb) or y in (ya, yb)]
        return _bresenham(self._anchor.x(), self._anchor.y(), xb if xa == xb else tile.x(),
                          yb if ya == yb else tile.y())

    def _update_shape(self, tile: QPoint) -> None:
        self._preview = self._shape_coords(tile)
        self.update()

    def _commit_shape(self, tile: QPoint) -> None:
        value = EMPTY if self._pending_tool == "eraser" else self.tile
        for x, y in self._shape_coords(tile):
            self._edits += self.project.map.paint(x, y, value)
        self._preview = []

    def _commit(self, label: str | None = None) -> None:
        if not self._edits:
            return
        name = label or {"brush": "Vẽ tile", "eraser": "Xoá tile", "fill": "Đổ vùng",
                         "line": "Đường thẳng", "rect": "Khung chữ nhật"}.get(
            self._pending_tool, "Sửa tile")
        self.paintCommitted.emit(name, list(self._edits))
        self._edits = []

    # ---------------------------------------------------------------- render

    def drawBackground(self, painter: QPainter, pal: dict) -> None:
        painter.fillRect(self.rect(), QColor(pal["canvas"]))
        if not self.project:
            return
        w, h = self.project.map.pixel_size
        x0, y0 = self.camera.world_to_screen(0, 0)
        rect = QRectF(x0, y0, w * self.camera.zoom, h * self.camera.zoom)
        step = max(6.0, 12 * self.camera.zoom)
        checker = QColor(pal["checker_a"]), QColor(pal["checker_b"])
        painter.save()
        painter.setClipRect(rect)
        painter.fillRect(rect, checker[0])
        painter.setPen(Qt.NoPen)
        painter.setBrush(checker[1])
        ty = 0
        y = rect.top()
        while y < rect.bottom():
            tx = 0
            x = rect.left()
            while x < rect.right():
                if (tx + ty) % 2 == 0:
                    painter.drawRect(QRectF(x, y, step, step))
                x += step
                tx += 1
            y += step
            ty += 1
        painter.restore()
        painter.setPen(QPen(QColor(pal["border_strong"]), 1))
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(rect)

    def drawTiles(self, painter: QPainter, pal: dict) -> None:
        batches = build_batches(self.project.map, self.camera)
        painter.setRenderHint(QPainter.Antialiasing, False)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, self.camera.zoom > 2.4)
        for batch in batches:
            if not batch.placements:
                continue
            painter.setOpacity(batch.opacity)
            for place in batch.placements:
                image = qtimg.tile_image(self.project.sheet, place.tile)
                if image:
                    painter.drawImage(QRectF(place.x, place.y, place.w, place.h), image)
            painter.setOpacity(1.0)

    def drawPreview(self, painter: QPainter, pal: dict) -> None:
        value = EMPTY if getattr(self, "_pending_tool", "") == "eraser" else self.tile
        tw, th = self.project.map.tile_w * self.camera.zoom, self.project.map.tile_h * self.camera.zoom
        for x, y in self._preview:
            sx, sy = self.camera.world_to_screen(x * self.project.map.tile_w,
                                                 y * self.project.map.tile_h)
            if value == EMPTY:
                painter.fillRect(QRectF(sx, sy, tw, th), QColor(255, 95, 109, 90))
            else:
                painter.setOpacity(0.55)
                image = qtimg.tile_image(self.project.sheet, value)
                if image:
                    painter.drawImage(QRectF(sx, sy, tw, th), image)
                painter.setOpacity(1.0)

    def drawGrid(self, painter: QPainter, pal: dict) -> None:
        if not self.show_grid or self.camera.zoom < 0.35:
            return
        m = self.project.map
        x0, x1, y0, y1 = self._map_span()
        left, right = max(0.0, x0), min(float(self.width()), x1)
        top, bottom = max(0.0, y0), min(float(self.height()), y1)
        if left >= right or top >= bottom:
            return
        grid_color = QColor(pal["grid"])
        grid_color.setAlpha(150)
        pen = QPen(grid_color)
        painter.setPen(pen)
        for c in range(m.width + 1):
            sx, _ = self.camera.world_to_screen(c * m.tile_w, 0)
            if left <= sx <= right:
                painter.drawLine(QPointF(sx, top), QPointF(sx, bottom))
        for r in range(m.height + 1):
            _, sy = self.camera.world_to_screen(0, r * m.tile_h)
            if top <= sy <= bottom:
                painter.drawLine(QPointF(left, sy), QPointF(right, sy))

    def _map_span(self) -> tuple[float, float, float, float]:
        w, h = self.project.map.pixel_size
        x0, y0 = self.camera.world_to_screen(0, 0)
        return x0, x0 + w * self.camera.zoom, y0, y0 + h * self.camera.zoom

    def drawLabels(self, painter: QPainter, pal: dict) -> None:
        if not self.show_labels or self.camera.zoom < 0.5:
            return
        m = self.project.map
        cols, rows = self.camera.visible_tiles(m.width, m.height, m.tile_w, m.tile_h, 0)
        font = painter.font()
        font.setPixelSize(max(8, int(9 * self.camera.zoom)))
        painter.setFont(font)
        painter.setPen(QColor(pal["danger"]))
        for y in rows:
            for x in cols:
                sx, sy = self.camera.world_to_screen(x * m.tile_w, y * m.tile_h)
                painter.drawText(QPointF(sx + 2, sy + font.pixelSize() + 2), f"{x}.{y}")

    def drawHover(self, painter: QPainter, pal: dict) -> None:
        tile = getattr(self, "_hover", None)
        if not tile or not self.inside(tile):
            return
        m = self.project.map
        tw, th = m.tile_w * self.camera.zoom, m.tile_h * self.camera.zoom
        sx, sy = self.camera.world_to_screen(tile.x() * m.tile_w, tile.y() * m.tile_h)
        painter.setPen(QPen(QColor(pal["accent"]), 2))
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(QRectF(sx, sy, tw, th))

    def paintEvent(self, event) -> None:
        pal = theme_colors(QApplication.instance())
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        self.drawBackground(painter, pal)
        if not self.project or not self.project.sheet:
            painter.setPen(QColor(pal["text_faint"]))
            painter.drawText(self.rect(), Qt.AlignCenter,
                             "Chưa có tilesheet — mở File ▸ Mở tilesheet…")
            return
        self.drawTiles(painter, pal)
        self.drawPreview(painter, pal)
        self.drawGrid(painter, pal)
        self.drawLabels(painter, pal)
        self.drawHover(painter, pal)
        painter.end()

def _bresenham(x0: int, y0: int, x1: int, y1: int) -> list[tuple[int, int]]:
    dx, dy = abs(x1 - x0), -abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx + dy
    out = []
    for _ in range(8192):
        out.append((x0, y0))
        if (x0, y0) == (x1, y1):
            break
        e2 = 2 * err
        if e2 >= dy:
            err += dy
            x0 += sx
        if e2 <= dx:
            err += dx
            y0 += sy
    return out
