"""Vector glyph factory: every icon is painted, so tinting and DPI stay under control."""

from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap

_CACHE: dict[tuple, QIcon] = {}
STROKE_W = 1.55


def _pt(pad: float, inner: float, x: float, y: float) -> QPointF:
    return QPointF(pad + x * inner, pad + y * inner)


def _poly(p: QPainter, pad: float, inner: float, pts, close: bool = False) -> None:
    path = QPainterPath()
    path.moveTo(_pt(pad, inner, *pts[0]))
    for x, y in pts[1:]:
        path.lineTo(_pt(pad, inner, x, y))
    if close:
        path.closeSubpath()
    p.drawPath(path)


def _box(p: QPainter, pad: float, inner: float, x: float, y: float, w: float, h: float,
         r: float = 0.08, filled: bool = False) -> None:
    rect = QRectF(pad + x * inner, pad + y * inner, w * inner, h * inner)
    if filled:
        p.setBrush(p.pen().color())
    p.drawRoundedRect(rect, r * inner, r * inner)
    p.setBrush(Qt.NoBrush)


def _draw(name: str, p: QPainter, size: float) -> None:
    pad, i = size * 0.19, size * 0.62

    if name == "close":
        _poly(p, pad, i, [(0, 0), (1, 1)])
        _poly(p, pad, i, [(1, 0), (0, 1)])
    elif name == "minimize":
        _poly(p, pad, i, [(0, 0.55), (1, 0.55)])
    elif name == "maximize":
        _box(p, pad, i, 0, 0, 1, 1, 0.12)
    elif name == "restore":
        _box(p, pad, i, 0.18, 0.0, 0.82, 0.82, 0.1)
        p.setClipRect(QRectF(pad + 0.05 * i, pad + 0.28 * i, 0.7 * i, 0.7 * i))
        _box(p, pad, i, 0.0, 0.18, 0.82, 0.82, 0.1)
        p.setClipping(False)
    elif name == "menu":
        for y in (0.1, 0.5, 0.9):
            _poly(p, pad, i, [(0, y), (1, y)])
    elif name == "folder":
        _poly(p, pad, i, [(0, 0.15), (0.35, 0.15), (0.5, 0.35), (1, 0.35), (1, 0.95), (0, 0.95)],
              close=True)
    elif name == "save":
        _poly(p, pad, i, [(0, 0), (0.72, 0), (1, 0.28), (1, 1), (0, 1)], close=True)
        _box(p, pad, i, 0.24, 0.55, 0.52, 0.45, 0.05)
        _box(p, pad, i, 0.28, 0.06, 0.34, 0.3, 0.05)
    elif name == "plus":
        _poly(p, pad, i, [(0.5, 0), (0.5, 1)])
        _poly(p, pad, i, [(0, 0.5), (1, 0.5)])
    elif name == "minus":
        _poly(p, pad, i, [(0, 0.5), (1, 0.5)])
    elif name == "trash":
        _poly(p, pad, i, [(0, 0.18), (1, 0.18)])
        _poly(p, pad, i, [(0.15, 0.18), (0.22, 1), (0.78, 1), (0.85, 0.18)])
        _poly(p, pad, i, [(0.35, 0.02), (0.35, 0.18)])
        _poly(p, pad, i, [(0.65, 0.02), (0.65, 0.18)])
    elif name == "eye":
        path = QPainterPath()
        path.moveTo(_pt(pad, i, 0, 0.5))
        path.quadTo(_pt(pad, i, 0.5, -0.15), _pt(pad, i, 1, 0.5))
        path.quadTo(_pt(pad, i, 0.5, 1.15), _pt(pad, i, 0, 0.5))
        p.drawPath(path)
        p.drawEllipse(_pt(pad, i, 0.5, 0.5), i * 0.16, i * 0.16)
    elif name == "eye-off":
        _poly(p, pad, i, [(0, 0.5), (0.5, -0.05), (1, 0.5)])
        _poly(p, pad, i, [(0.15, 0.85), (0.85, 0.15)])
    elif name == "lock":
        _box(p, pad, i, 0.05, 0.42, 0.9, 0.58, 0.12)
        _poly(p, pad, i, [(0.25, 0.42), (0.25, 0.25), (0.75, 0.25), (0.75, 0.42)])
    elif name == "up":
        _poly(p, pad, i, [(0.1, 0.65), (0.5, 0.2), (0.9, 0.65)])
    elif name == "down":
        _poly(p, pad, i, [(0.1, 0.35), (0.5, 0.8), (0.9, 0.35)])
    elif name == "chevron":
        _poly(p, pad, i, [(0.25, 0.15), (0.75, 0.5), (0.25, 0.85)])
    elif name == "grid":
        for v in (0, 1 / 3, 2 / 3, 1):
            _poly(p, pad, i, [(v, 0), (v, 1)])
            _poly(p, pad, i, [(0, v), (1, v)])
    elif name == "zoom-in":
        p.drawEllipse(QRectF(pad, pad, i * 0.72, i * 0.72))
        _poly(p, pad, i, [(0.72, 0.72), (1, 1)])
        _poly(p, pad, i, [(0.18, 0.36), (0.54, 0.36)])
        _poly(p, pad, i, [(0.36, 0.18), (0.36, 0.54)])
    elif name == "zoom-out":
        p.drawEllipse(QRectF(pad, pad, i * 0.72, i * 0.72))
        _poly(p, pad, i, [(0.72, 0.72), (1, 1)])
        _poly(p, pad, i, [(0.18, 0.36), (0.54, 0.36)])
    elif name == "fit":
        for corners in ([(0, 0.28), (0, 0), (0.28, 0)], [(0.72, 0), (1, 0), (1, 0.28)],
                        [(1, 0.72), (1, 1), (0.72, 1)], [(0.28, 1), (0, 1), (0, 0.72)]):
            _poly(p, pad, i, corners)
    elif name == "sun":
        p.drawEllipse(QRectF(pad + i * 0.28, pad + i * 0.28, i * 0.44, i * 0.44))
        for a, b in ((0.5, 0), (0.5, 1), (0, 0.5), (1, 0.5), (0.15, 0.15), (0.85, 0.15),
                     (0.15, 0.85), (0.85, 0.85)):
            _poly(p, pad, i, [(a, b), (a + (a - 0.5) * 0.22, b + (b - 0.5) * 0.22)])
    elif name == "moon":
        path = QPainterPath()
        path.moveTo(_pt(pad, i, 0.62, 0))
        path.arcTo(QRectF(pad, pad, i, i), 70, -250)
        path.cubicTo(_pt(pad, i, 0.35, 0.35), _pt(pad, i, 0.35, 0.65), _pt(pad, i, 0.62, 1))
        p.drawPath(path)
    elif name == "brush":
        _poly(p, pad, i, [(0.05, 0.95), (0.3, 0.85), (0.2, 0.6)], close=True)
        _poly(p, pad, i, [(0.32, 0.72), (1, 0.08)])
        _poly(p, pad, i, [(0.12, 0.78), (0.28, 0.92)])
    elif name == "eraser":
        _poly(p, pad, i, [(0.05, 0.7), (0.55, 0.2), (0.95, 0.6), (0.45, 1.05)], close=True)
        _poly(p, pad, i, [(0.3, 0.45), (0.7, 0.85)])
    elif name == "bucket":
        _poly(p, pad, i, [(0.12, 0.35), (0.62, 0.85), (0.98, 0.5), (0.5, 0.02)], close=True)
        _poly(p, pad, i, [(0.3, 0.55), (0.8, 0.28)])
        p.drawEllipse(QRectF(pad + i * 0.86, pad + i * 0.6, i * 0.16, i * 0.24))
    elif name == "line":
        _poly(p, pad, i, [(0.02, 0.98), (0.98, 0.02)])
        _box(p, pad, i, -0.06, 0.88, 0.2, 0.2, 0.04)
        _box(p, pad, i, 0.86, -0.06, 0.2, 0.2, 0.04)
    elif name == "rect":
        _box(p, pad, i, 0, 0.12, 1, 0.78, 0.1)
    elif name == "undo":
        p.drawArc(QRectF(pad, pad, i, i), 40 * 16, 250 * 16)
        _poly(p, pad, i, [(0.02, 0.18), (0.06, 0.55), (0.42, 0.42)])
    elif name == "redo":
        p.drawArc(QRectF(pad, pad, i, i), -70 * 16, -250 * 16)
        _poly(p, pad, i, [(0.98, 0.18), (0.94, 0.55), (0.58, 0.42)])
    elif name == "check":
        _poly(p, pad, i, [(0.02, 0.55), (0.38, 0.95), (1.0, 0.08)])
    elif name == "info":
        p.drawEllipse(QRectF(pad * 0.75, pad * 0.75, i * 1.18, i * 1.18))
        _poly(p, pad, i, [(0.5, 0.42), (0.5, 0.9)])
        p.setBrush(p.pen().color())
        p.drawEllipse(_pt(pad, i, 0.5, 0.16), i * 0.06, i * 0.06)
        p.setBrush(Qt.NoBrush)
    elif name == "warn":
        _poly(p, pad, i, [(0.5, 0), (1, 0.98), (0, 0.98)], close=True)
        _poly(p, pad, i, [(0.5, 0.34), (0.5, 0.66)])
        p.setBrush(p.pen().color())
        p.drawEllipse(_pt(pad, i, 0.5, 0.83), i * 0.055, i * 0.055)
        p.setBrush(Qt.NoBrush)
    elif name == "question":
        p.drawEllipse(QRectF(pad * 0.75, pad * 0.75, i * 1.18, i * 1.18))
        path = QPainterPath()
        path.moveTo(_pt(pad, i, 0.3, 0.32))
        path.cubicTo(_pt(pad, i, 0.35, 0.05), _pt(pad, i, 0.78, 0.08), _pt(pad, i, 0.62, 0.42))
        path.cubicTo(_pt(pad, i, 0.55, 0.55), _pt(pad, i, 0.5, 0.55), _pt(pad, i, 0.5, 0.68))
        p.drawPath(path)
        p.setBrush(p.pen().color())
        p.drawEllipse(_pt(pad, i, 0.5, 0.87), i * 0.055, i * 0.055)
        p.setBrush(Qt.NoBrush)
    elif name == "settings":
        c = _pt(pad, i, 0.5, 0.5)
        p.drawEllipse(c, i * 0.2, i * 0.2)
        for k in range(8):
            a = k * math.tau / 8
            p.drawLine(QPointF(c.x() + math.cos(a) * i * 0.3, c.y() + math.sin(a) * i * 0.3),
                       QPointF(c.x() + math.cos(a) * i * 0.48, c.y() + math.sin(a) * i * 0.48))
    elif name == "layers":
        for dy in (0.0, 0.3, 0.6):
            _poly(p, pad, i, [(0.5, dy), (1, 0.22 + dy), (0.5, 0.44 + dy), (0, 0.22 + dy)],
                  close=True)
    elif name == "tiles":
        for x, y in ((0, 0), (0.52, 0), (0, 0.52), (0.52, 0.52)):
            _box(p, pad, i, x, y, 0.48, 0.48, 0.1)
    elif name == "image":
        _box(p, pad, i, 0, 0.06, 1, 0.88, 0.1)
        p.setBrush(p.pen().color())
        p.drawEllipse(QRectF(pad + i * 0.18, pad + i * 0.24, i * 0.16, i * 0.16))
        p.setBrush(Qt.NoBrush)
        _poly(p, pad, i, [(0.08, 0.86), (0.4, 0.5), (0.62, 0.72), (0.8, 0.52), (0.94, 0.86)])
    elif name == "export":
        _poly(p, pad, i, [(0.5, 0.95), (0.5, 0.05)])
        _poly(p, pad, i, [(0.18, 0.35), (0.5, 0.03), (0.82, 0.35)])
        _poly(p, pad, i, [(0.02, 0.72), (0.02, 1), (0.98, 1), (0.98, 0.72)])
    elif name == "new":
        _poly(p, pad, i, [(0.12, 0), (0.62, 0), (1, 0.38), (1, 1), (0.12, 1)], close=True)
        _poly(p, pad, i, [(0.62, 0.04), (0.62, 0.38), (0.96, 0.38)])
    elif name == "keyboard":
        _box(p, pad, i, 0, 0.18, 1, 0.64, 0.12)
        for x in (0.16, 0.4, 0.64, 0.86):
            _poly(p, pad, i, [(x, 0.42), (x, 0.58)])
        _poly(p, pad, i, [(0.3, 0.7), (0.7, 0.7)])
    elif name == "dot":
        p.setBrush(p.pen().color())
        p.drawEllipse(_pt(pad, i, 0.5, 0.5), i * 0.12, i * 0.12)
    elif name == "app":
        _box(p, pad, i, 0, 0, 1, 1, 0.22)
        _poly(p, pad, i, [(0, 0.5), (1, 0.5)])
        _poly(p, pad, i, [(0.5, 0), (0.5, 1)])
    else:
        p.drawEllipse(QRectF(pad, pad, i, i))


def pixmap(name: str, color: str = "#e6eaf2", size: int = 18,
           stroke: float = STROKE_W) -> QPixmap:
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    pen = QPen(QColor(color))
    pen.setWidthF(stroke * size / 18.0)
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)
    _draw(name, p, float(size))
    p.end()
    return pm


def icon(name: str, color: str = "#e6eaf2", size: int = 18,
         stroke: float = STROKE_W) -> QIcon:
    key = (name, color, size, stroke)
    if key not in _CACHE:
        _CACHE[key] = QIcon(pixmap(name, color, size, stroke))
    return _CACHE[key]
