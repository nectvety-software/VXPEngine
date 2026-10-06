"""Frameless top-level window: custom title bar, native drag/resize, no OS chrome."""

from __future__ import annotations

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QColor, QCursor
from PySide6.QtWidgets import (QApplication, QFrame, QGraphicsDropShadowEffect, QHBoxLayout,
                               QLabel, QPushButton, QVBoxLayout, QWidget)

from . import icons
from .theme import colors as theme_colors

SHADOW_MARGIN = 14
EDGE_GRAB = 9


class CaptionButton(QPushButton):
    """Minimise / maximise / close — drawn by us, tinted by the active palette."""

    def __init__(self, glyph: str, tip: str, kind: str = "", parent: QWidget | None = None):
        super().__init__(parent)
        self.glyph = glyph
        self.kind = kind
        self.setFlat(True)
        self.setFocusPolicy(Qt.NoFocus)
        self.setFixedSize(34, 28)
        self.setToolTip(tip)
        self.setProperty("role", "caption")
        if kind:
            self.setProperty("kind", kind)
        self.restyle()

    def restyle(self, palette: dict | None = None) -> None:
        pal = palette or theme_colors(self)
        hot = self.kind == "close" and self.underMouse()
        self.setIcon(icons.icon(self.glyph, "#ffffff" if hot else pal["text_muted"], 15))

    def enterEvent(self, event) -> None:
        self.restyle()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self.restyle()
        super().leaveEvent(event)


class TitleBar(QFrame):
    def __init__(self, window: "FramelessWindow"):
        super().__init__(window)
        self.window_ref = window
        self.setObjectName("TitleBar")
        self.setFixedHeight(42)
        self.setMouseTracking(True)

        row = QHBoxLayout(self)
        row.setContentsMargins(10, 0, 6, 0)
        row.setSpacing(8)

        self.icon_label = QLabel()
        self.icon_label.setFixedSize(20, 20)
        self.title = QLabel("Terra")
        self.title.setObjectName("AppTitle")
        self.subtitle = QLabel("")
        self.subtitle.setObjectName("AppSubtitle")

        self.leading = QHBoxLayout()
        self.leading.setSpacing(2)
        self.trailing = QHBoxLayout()
        self.trailing.setSpacing(2)

        self.menu_button = CaptionButton("menu", "Menu lệnh")
        self.min_button = CaptionButton("minimize", "Minh hoá")
        self.max_button = CaptionButton("maximize", "Phóng to / thu nhỏ")
        self.close_button = CaptionButton("close", "Đóng", "close")

        self.menu_button.clicked.connect(window.show_command_menu)
        self.min_button.clicked.connect(window.showMinimized)
        self.max_button.clicked.connect(window.toggle_maximize)
        self.close_button.clicked.connect(window.close)

        row.addWidget(self.icon_label)
        row.addSpacing(4)
        row.addWidget(self.title)
        row.addWidget(self.subtitle)
        row.addLayout(self.leading)
        row.addStretch(1)
        row.addLayout(self.trailing)
        row.addWidget(self.menu_button)
        row.addWidget(self.min_button)
        row.addWidget(self.max_button)
        row.addWidget(self.close_button)

    # Windows-native move loop keeps Aero Snap working on a frameless window.
    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton and not self.childAt(event.position().toPoint()):
            handle = self.window().windowHandle()
            if handle:
                handle.startSystemMove()
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:
        if not self.childAt(event.position().toPoint()):
            self.window_ref.toggle_maximize()
        super().mouseDoubleClickEvent(event)

    def set_max_glyph(self, maximized: bool) -> None:
        self.max_button.glyph = "restore" if maximized else "maximize"
        self.max_button.restyle()

    def restyle(self, palette: dict) -> None:
        self.icon_label.setPixmap(icons.pixmap("app", palette["accent"], 17))
        for button in (self.menu_button, self.min_button, self.max_button, self.close_button):
            button.restyle(palette)


class FramelessWindow(QWidget):
    """Translucent shell with a shadowed rounded container and a custom title bar."""

    def __init__(self, title: str = "Terra", parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setMinimumSize(940, 620)
        self.setWindowTitle(title)
        self._manual_max = False
        self._pre_max = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(*([SHADOW_MARGIN] * 4))
        outer.setSpacing(0)

        self.container = QFrame(self)
        self.container.setObjectName("RootContainer")
        shadow = QGraphicsDropShadowEffect(self.container)
        shadow.setBlurRadius(36)
        shadow.setOffset(0, 9)
        shadow.setColor(QColor(0, 0, 0, 140))
        self.container.setGraphicsEffect(shadow)

        inner = QVBoxLayout(self.container)
        inner.setContentsMargins(0, 0, 0, 0)
        inner.setSpacing(0)

        self.title_bar = TitleBar(self)
        self.body = QWidget(self.container)
        self.body_layout = QVBoxLayout(self.body)
        self.body_layout.setContentsMargins(0, 0, 0, 0)
        self.body_layout.setSpacing(0)

        inner.addWidget(self.title_bar)
        inner.addWidget(self.body, 1)
        outer.addWidget(self.container)

        self.setMouseTracking(True)

    # ------------------------------------------------------------------ api

    def show_command_menu(self) -> None:
        """Overridden by the editor; the title bar menu button calls this."""

    def set_body(self, widget: QWidget) -> None:
        self.body_layout.addWidget(widget)

    def set_title(self, text: str, subtitle: str = "") -> None:
        self.title_bar.title.setText(text)
        self.title_bar.subtitle.setText(subtitle)
        self.setWindowTitle(text)

    def add_title_action(self, widget: QWidget, leading: bool = False) -> None:
        (self.title_bar.leading if leading else self.title_bar.trailing).addWidget(widget)

    # ------------------------------------------------------------- maximize

    @property
    def maximized(self) -> bool:
        return self._manual_max or bool(self.windowState() & Qt.WindowMaximized)

    def toggle_maximize(self) -> None:
        if self.maximized:
            self._manual_max = False
            self.showNormal()
            if self._pre_max:
                self.setGeometry(self._pre_max)
        else:
            self._pre_max = self.geometry()
            self._manual_max = True
            screen = self.screen() or QApplication.primaryScreen()
            self.setGeometry(screen.availableGeometry())
        self._sync_frame()

    def _sync_frame(self) -> None:
        margin = 0 if self.maximized else SHADOW_MARGIN
        self.layout().setContentsMargins(*([margin] * 4))
        state = "maximized" if self.maximized else "normal"
        for widget in (self.container, self.title_bar):
            widget.setProperty("state", state)
            widget.style().unpolish(widget)
            widget.style().polish(widget)
        self.title_bar.set_max_glyph(self.maximized)
        self.container.update()

    def changeEvent(self, event) -> None:
        if event.type() == QEvent.WindowStateChange:
            self._sync_frame()
        super().changeEvent(event)

    # --------------------------------------------------------------- resize

    def _edges_at(self, pos) -> Qt.Edges:
        if self.maximized:
            return Qt.Edges()
        rect = self.rect()
        edges = Qt.Edges()
        if pos.x() <= rect.left() + EDGE_GRAB:
            edges |= Qt.LeftEdge
        if pos.x() >= rect.right() - EDGE_GRAB:
            edges |= Qt.RightEdge
        if pos.y() <= rect.top() + EDGE_GRAB:
            edges |= Qt.TopEdge
        if pos.y() >= rect.bottom() - EDGE_GRAB:
            edges |= Qt.BottomEdge
        return edges

    _CURSORS = {
        Qt.LeftEdge: Qt.SizeHorCursor, Qt.RightEdge: Qt.SizeHorCursor,
        Qt.TopEdge: Qt.SizeVerCursor, Qt.BottomEdge: Qt.SizeVerCursor,
        Qt.LeftEdge | Qt.TopEdge: Qt.SizeFDiagCursor,
        Qt.RightEdge | Qt.BottomEdge: Qt.SizeFDiagCursor,
        Qt.RightEdge | Qt.TopEdge: Qt.SizeBDiagCursor,
        Qt.LeftEdge | Qt.BottomEdge: Qt.SizeBDiagCursor,
    }

    def mouseMoveEvent(self, event) -> None:
        edges = self._edges_at(event.position().toPoint())
        shape = self._CURSORS.get(edges)
        self.setCursor(QCursor(Qt.CursorShape(shape)) if shape else Qt.ArrowCursor)
        super().mouseMoveEvent(event)

    def mousePressEvent(self, event) -> None:
        edges = self._edges_at(event.position().toPoint())
        if event.button() == Qt.LeftButton and edges:
            handle = self.windowHandle()
            if handle:
                handle.startSystemResize(edges)
            event.accept()
            return
        super().mousePressEvent(event)

    def refresh_theme(self) -> None:
        self.title_bar.restyle(theme_colors(self))
        self._sync_frame()
