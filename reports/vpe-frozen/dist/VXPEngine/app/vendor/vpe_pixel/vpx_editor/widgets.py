"""Custom enterprise widgets: shadow panels, tool buttons, palette grid, swatches."""

from __future__ import annotations

from typing import List, Optional, Tuple

from PySide6.QtCore import Qt, QSize, Signal, QPropertyAnimation, QEasingCurve, QPoint, QRectF
from PySide6.QtGui import QColor, QPainter, QPen, QBrush, QLinearGradient, QFont, QIcon, QPixmap
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QToolButton,
    QButtonGroup, QGridLayout, QFrame, QGraphicsDropShadowEffect, QSizePolicy,
    QColorDialog, QSlider, QSpinBox, QCheckBox, QComboBox, QSizePolicy,
)

from . import icons
from .palette import PALETTE_565, PALETTE_NAMES
from .theme import get_theme
from .vpe import c565_to_rgb, rgb_to_565


class ShadowCard(QFrame):
    """Rounded surface card with soft drop shadow."""

    def __init__(self, title: Optional[str] = None, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("Card")
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(14, 12, 14, 14)
        self._layout.setSpacing(10)
        if title:
            lbl = QLabel(title.upper())
            lbl.setObjectName("Heading")
            self._layout.addWidget(lbl)
        self._shadow = QGraphicsDropShadowEffect(self)
        self._shadow.setBlurRadius(28)
        self._shadow.setOffset(0, 6)
        self._shadow.setColor(QColor(0, 0, 0, 55))
        self.setGraphicsEffect(self._shadow)

    def body(self) -> QVBoxLayout:
        return self._layout


class SectionLabel(QLabel):
    def __init__(self, text: str, parent=None) -> None:
        super().__init__(text.upper(), parent)
        self.setObjectName("Heading")


class AccentButton(QPushButton):
    def __init__(self, text: str, parent=None) -> None:
        super().__init__(text, parent)
        self.setObjectName("Primary")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(36)


class ToolRailButton(QToolButton):
    """Icon-font tool button; the title lives in the hover tooltip."""

    def __init__(self, key: str, icon_name: str, tooltip: str, parent=None) -> None:
        super().__init__(parent)
        self.key = key
        self.icon_name = icon_name
        self.setToolTip(tooltip)
        self.setAccessibleName(tooltip)
        self.setCheckable(True)
        self.setAutoRaise(False)
        self.setFixedSize(52, 48)
        # Without the icon font the abbreviation label is the only readable thing.
        self.setToolButtonStyle(
            Qt.ToolButtonStyle.ToolButtonIconOnly if icons.available()
            else Qt.ToolButtonStyle.ToolButtonTextOnly)
        self.set_active(False)

    def set_active(self, active: bool) -> None:
        icons.set_icon(
            self, self.icon_name, 24, text="",
            token="accent" if active else "muted",
        )


class ToolButtonGroup(QButtonGroup):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setExclusive(True)


class PaletteGrid(QWidget):
    """16-swatch color palette with selection ring + custom color."""

    color_selected = Signal(int)  # RGB565

    def __init__(self, columns: int = 8, parent=None) -> None:
        super().__init__(parent)
        self._columns = columns
        self._selected = 5  # RED default like Lua editor
        self._swatches: List[int] = list(PALETTE_565)
        self._buttons: List[QPushButton] = []
        self._grid = QGridLayout(self)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setSpacing(5)
        self._build()

    def _build(self) -> None:
        while self._grid.count():
            item = self._grid.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        self._buttons.clear()
        for i, c in enumerate(self._swatches):
            btn = QPushButton()
            btn.setFixedSize(24, 24)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            r, g, b = c565_to_rgb(c)
            name = PALETTE_NAMES[i] if i < len(PALETTE_NAMES) else f"Swatch {i + 1}"
            btn.setToolTip(f"{name} — #{r:02X}{g:02X}{b:02X} (RGB565 {c:04X})")
            btn.clicked.connect(lambda _=False, idx=i: self.select_index(idx))
            self._grid.addWidget(btn, i // self._columns, i % self._columns)
            self._buttons.append(btn)
        self._refresh_styles()

    def _refresh_styles(self) -> None:
        t = get_theme().tokens
        for i, btn in enumerate(self._buttons):
            r, g, b = c565_to_rgb(self._swatches[i])
            bg = f"#{r:02X}{g:02X}{b:02X}"
            # Contrast border
            lum = 0.299 * r + 0.587 * g + 0.114 * b
            border = "#0B0E14" if lum > 140 else "#FFFFFF"
            if i == self._selected:
                btn.setStyleSheet(
                    f"QPushButton {{ background: {bg}; border: 2px solid {t['accent']};"
                    f" border-radius: 8px; }}"
                    f"QPushButton:hover {{ border-color: {t['accent_hover']}; }}"
                )
            else:
                btn.setStyleSheet(
                    f"QPushButton {{ background: {bg}; border: 1px solid {border};"
                    f" border-radius: 8px; }}"
                    f"QPushButton:hover {{ border-color: {t['accent']}; }}"
                )

    def select_index(self, idx: int) -> None:
        if 0 <= idx < len(self._swatches):
            self._selected = idx
            self._refresh_styles()
            self.color_selected.emit(self._swatches[idx])

    def set_color_565(self, color: int) -> None:
        for i, c in enumerate(self._swatches):
            if c == (color & 0xFFFF):
                self._selected = i
                self._refresh_styles()
                return

    def current_565(self) -> int:
        return self._swatches[self._selected]


class ColorPreview(QWidget):
    """Live RGB565 color chip + hex label."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._color = 0xF800
        self.setFixedHeight(36)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_color(self, c: int) -> None:
        self._color = c & 0xFFFF
        self.update()

    def color(self) -> int:
        return self._color

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        r, g, b = c565_to_rgb(self._color)
        t = get_theme().tokens
        p.setPen(QPen(QColor(t["border"]), 1))
        p.setBrush(QBrush(QColor(r, g, b)))
        p.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 10, 10)
        # Hex text
        lum = 0.299 * r + 0.587 * g + 0.114 * b
        p.setPen(QColor("#0B0E14" if lum > 140 else "#FFFFFF"))
        f = QFont()
        f.setFamilies(["Consolas", "Cascadia Mono", "monospace"])
        f.setPointSize(10)
        f.setBold(True)
        p.setFont(f)
        p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, f"#{r:02X}{g:02X}{b:02X}  ·  {self._color:04X}")
        p.end()


class SizeSelector(QWidget):
    """Brush size chips 1..5."""

    size_changed = Signal(int)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._size = 1
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._btns = []
        for s in range(1, 6):
            b = QPushButton(str(s))
            b.setCheckable(True)
            b.setFixedSize(32, 28)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setToolTip(f"Brush {s}×{s} px — press {s}, or [ and ] to step")
            b.clicked.connect(lambda _=False, v=s: self.set_size(v))
            self._group.addButton(b, s)
            lay.addWidget(b)
            self._btns.append(b)
        self.set_size(1)

    def set_size(self, size: int) -> None:
        self._size = max(1, min(5, int(size)))
        for i, b in enumerate(self._btns, start=1):
            b.setChecked(i == self._size)
            b.setStyleSheet(self._style(i == self._size))
        self.size_changed.emit(self._size)

    def size(self) -> int:
        return self._size

    def _style(self, active: bool) -> str:
        t = get_theme().tokens
        if active:
            return (
                f"QPushButton {{ background: {t['accent']}; color: #FFFFFF; border: none;"
                f" border-radius: 8px; font-weight: 700; font-size: 12px; padding: 0px; }}"
            )
        return (
            f"QPushButton {{ background: {t['surface2']}; color: {t['text']};"
            f" border: 1px solid {t['border']}; border-radius: 8px; font-size: 12px;"
            f" font-weight: 600; padding: 0px; }}"
            f"QPushButton:hover {{ border-color: {t['accent']}; color: {t['accent']}; }}"
        )


class ThemeToggleButton(QPushButton):
    """Light / Dark toggle drawn from the icon font, with slide animation."""

    theme_toggled = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__("Dark", parent)
        self.setObjectName("Ghost")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(52, 44)
        self.clicked.connect(self._on_click)
        self._sync_label()

    def _on_click(self) -> None:
        name = get_theme().toggle()
        self._sync_label()
        self.theme_toggled.emit(name)

    def _sync_label(self) -> None:
        dark = get_theme().is_dark()
        icons.set_icon(self, "sun" if dark else "moon", 18, text="")
        self.setAccessibleName("Switch to Light mode" if dark else "Switch to Dark mode")
        self.setToolTip("Switch to Light mode (Ctrl+T)" if dark
                        else "Switch to Dark mode (Ctrl+T)")


class GlyphLabel(QLabel):
    """Label with an icon-font glyph painted in front of its text."""

    def __init__(self, icon_name: str, token: str = "text", pixel: int = 14,
                 parent=None) -> None:
        super().__init__(parent)
        self._glyph = icons.icon(icon_name, token)
        self._pixel = pixel
        self.setContentsMargins(pixel + 6, 0, 0, 0)

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        pm = self._glyph.pixmap(self._pixel, self._pixel)
        p = QPainter(self)
        p.drawPixmap(1, (self.height() - pm.height()) // 2, pm)
        p.end()


class InfoChip(GlyphLabel):
    """Compact icon + key/value chip for the status bar and panels."""

    def __init__(self, icon_name: str, key: str, value: str = "—", parent=None) -> None:
        super().__init__(icon_name, "muted", 13, parent)
        self.setObjectName("Hi")
        self._key = key
        self._value = value
        self._render()

    def _render(self) -> None:
        self.setText(f"{self._key}  {self._value}")

    def set_value(self, value: str) -> None:
        self._value = value
        self._render()


class AnimatedStackHint(QLabel):
    """Fades in a status hint — micro-interaction polish."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("Muted")
        self._anim = QPropertyAnimation(self, b"windowOpacity", self)
        self._anim.setDuration(280)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    def show_hint(self, text: str) -> None:
        self.setText(text)
        self.setWindowOpacity(0.0)
        self.show()
        self._anim.stop()
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)
        self._anim.start()
