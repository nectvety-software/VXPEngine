"""Icon-font chrome: Segoe MDL2 Assets glyphs painted as QIcons, with text fallback.

The editor used to label its tools with 3-letter abbreviations ("Pen", "Rfl"),
which read as noise once the UI grew past seven buttons. This module renders the
system icon font instead and degrades to those abbreviations on platforms where
the family is not exposed to Qt (the offscreen plugin, Linux, older Windows).

Icons are drawn by a QIconEngine that resolves its colour from the live theme on
every paint, so a Light/Dark switch recolours them without re-applying anything.
"""

from __future__ import annotations

from typing import Dict, Optional, Tuple

from PySide6.QtCore import QRect, QSize, Qt
from PySide6.QtGui import QColor, QFont, QFontDatabase, QIcon, QIconEngine, QPainter, QPixmap
from PySide6.QtWidgets import QWidget

FAMILY = "Segoe MDL2 Assets"

# name -> (codepoint, abbreviation shown when the font is unavailable)
GLYPHS: Dict[str, Tuple[int, str]] = {
    "pencil":    (0xE70F, "Pen"),
    "eraser":    (0xE75C, "Ers"),
    "fill":      (0xE755, "Fil"),
    "line":      (0xE741, "Lin"),
    "rect":      (0xE739, "Rct"),
    "rectfill":  (0xE73B, "Rfl"),
    "pick":      (0xEF3C, "Pik"),
    "gallery":   (0xE80A, "Gal"),
    "library":   (0xE8F1, "Dir"),
    "new":       (0xE710, "New"),
    "import":    (0xE896, "Imp"),
    "export":    (0xE898, "Exp"),
    "open":      (0xE8AD, "Open"),
    "save":      (0xE74E, "Sav"),
    "refresh":   (0xE72C, "Ref"),
    "zoom_in":   (0xE71E, "+"),
    "zoom_out":  (0xE71F, "-"),
    "fit":       (0xE92C, "Fit"),
    "undo":      (0xE7A6, "Undo"),
    "redo":      (0xE7A7, "Redo"),
    "duplicate": (0xE8C8, "Dup"),
    "rename":    (0xE929, "Ren"),
    "delete":    (0xE74D, "Del"),
    "move":      (0xE8AB, "Mv"),
    "reveal":    (0xE8A7, "Show"),
    "swap":      (0xE8EB, "Swap"),
    "palette":   (0xE790, "Clr"),
    "grid":      (0xE75F, "Grid"),
    "eye":       (0xE890, "BG"),
    "none":      (0xE711, "No"),
    "sun":       (0xE706, "Light"),
    "moon":      (0xE708, "Dark"),
    "settings":  (0xE713, "Cfg"),
    "check":     (0xE73E, "OK"),
    "close":     (0xE894, "X"),
    "cursor":    (0xE8B0, "Pos"),
    "play":      (0xE768, "Play"),
    "pause":     (0xE769, "Pause"),
    "stop":      (0xE71A, "Stop"),
    "prev_frame": (0xE100, "<<"),
    "next_frame": (0xE101, ">>"),
    "onion":     (0xF156, "Onion"),
    "frames":    (0xE8B9, "Frm"),
    "animation": (0xE786, "Anim"),
}

_available: Optional[bool] = None


def available() -> bool:
    """True when the icon font is actually usable for text layout."""
    global _available
    if _available is None:
        db = QFontDatabase()
        _available = any(family.lower() == FAMILY.lower() for family in db.families())
    return _available


def glyph(name: str) -> str:
    return chr(GLYPHS[name][0])


def abbreviation(name: str) -> str:
    return GLYPHS[name][1]


class _GlyphEngine(QIconEngine):
    """Paints one glyph (or its abbreviation) in the current theme colour."""

    def __init__(self, name: str, token: str) -> None:
        super().__init__()
        self.name = name
        self.token = token

    def _color(self, mode) -> QColor:
        from .theme import get_theme

        if mode == QIcon.Mode.Disabled:
            key = "faint"
        elif mode in (QIcon.Mode.Selected, QIcon.Mode.Active):
            key = "accent"
        else:
            key = self.token
        return QColor(get_theme().token(key, "#E8EEF8"))

    def paint(self, painter: QPainter, rect: QRect, mode, state=QIcon.State.Off) -> None:
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        side = min(rect.width(), rect.height())
        if available():
            font, text, ratio = QFont(FAMILY), glyph(self.name), 0.62
        else:
            font, text, ratio = _ui_font(), abbreviation(self.name), 0.42
            font.setBold(True)
        font.setPixelSize(max(8, int(round(side * ratio))))
        painter.setFont(font)
        painter.setPen(self._color(mode))
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, text)
        painter.restore()

    def pixmap(self, size: QSize, mode=QIcon.Mode.Normal, state=QIcon.State.Off) -> QPixmap:
        pm = QPixmap(size)
        pm.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pm)
        self.paint(painter, QRect(0, 0, size.width(), size.height()), mode, state)
        painter.end()
        return pm

    def iconId(self) -> int:
        from .theme import get_theme

        return hash((self.name, self.token, get_theme().name, available()))

    def clone(self) -> QIconEngine:
        return _GlyphEngine(self.name, self.token)


def _ui_font() -> QFont:
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    return QFont(app.font()) if app else QFont("Segoe UI")


def icon(name: str, token: str = "text") -> QIcon:
    """Icon for `name`; `token` is a theme colour key (text / muted / accent …)."""
    return QIcon(_GlyphEngine(name, token))


def set_icon(widget: QWidget, name: str, pixel: int = 18, *,
             text: Optional[str] = None, token: str = "text",
             tooltip: Optional[str] = None) -> None:
    """Give `widget` an icon, an optional label and a hover title in one call.

    `text=""` marks an icon-only button: without the icon font the abbreviation
    becomes the label instead, so the control never renders as an empty box.
    """
    if available():
        widget.setIcon(icon(name, token))
        widget.setIconSize(QSize(pixel, pixel))
    else:
        widget.setIcon(QIcon())
        if text == "":
            text = abbreviation(name)
    if text is not None:
        widget.setText(text)
    if tooltip is not None:
        widget.setToolTip(tooltip)
    widget.setCursor(Qt.CursorShape.PointingHandCursor)
