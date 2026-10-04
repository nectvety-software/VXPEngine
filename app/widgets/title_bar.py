"""Compact Windows-style custom title bar for the frameless VXPEngine window."""
from __future__ import annotations

from PySide6.QtCore import QPoint, QSize, Qt, Signal
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QHBoxLayout, QLabel, QMenuBar, QPushButton, QSizePolicy, QWidget

from .icons import app_icon, icon


class CustomTitleBar(QWidget):
    minimizeRequested = Signal()
    maximizeRestoreRequested = Signal()
    closeRequested = Signal()
    homeRequested = Signal()

    def __init__(
        self,
        window: QWidget,
        title: str = "VXPEngine",
        project_name: str = "",
        parent=None,
    ):
        super().__init__(parent)
        self._window = window
        self._drag_pos: QPoint | None = None
        self._menu_bar: QMenuBar | None = None
        self._compact = False
        self._home_mode = True
        self.setObjectName("TitleBar")
        self.setFixedHeight(31)

        root = QHBoxLayout(self)
        root.setContentsMargins(7, 0, 0, 0)
        root.setSpacing(5)

        self.logo_button = QPushButton()
        self.logo_button.setObjectName("TitleLogoButton")
        self.logo_button.setIcon(app_icon())
        self.logo_button.setIconSize(QSize(16, 16))
        self.logo_button.setFixedSize(24, 24)
        self.logo_button.setToolTip("Trang chủ VXPEngine")
        self.logo_button.clicked.connect(self.homeRequested.emit)
        root.addWidget(self.logo_button)

        self.app_name = QLabel(title)
        self.app_name.setObjectName("TitleBarText")
        self.app_name.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Preferred)
        root.addWidget(self.app_name)

        self.project_separator = QLabel("/")
        self.project_separator.setObjectName("TitleBarProject")
        root.addWidget(self.project_separator)

        self.project_label = QLabel(project_name)
        self.project_label.setObjectName("TitleBarProject")
        self.project_label.setMaximumWidth(220)
        self.project_label.setToolTip(project_name)
        root.addWidget(self.project_label)

        self.menu_host = QWidget()
        self.menu_host_layout = QHBoxLayout(self.menu_host)
        self.menu_host_layout.setContentsMargins(8, 0, 0, 0)
        self.menu_host_layout.setSpacing(0)
        root.addWidget(self.menu_host)

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        root.addWidget(spacer)

        self.btn_info = QPushButton()
        self.btn_info.setObjectName("BtnMin")
        self.btn_info.setIcon(icon("fa5s.info-circle"))
        self.btn_info.setToolTip("Thông tin VXPEngine")
        self.btn_info.setFixedSize(34, 30)
        root.addWidget(self.btn_info)

        self.btn_min = QPushButton()
        self.btn_min.setObjectName("BtnMin")
        self.btn_min.setIcon(icon("fa5s.minus"))
        self.btn_min.setToolTip("Thu nhỏ")
        self.btn_min.clicked.connect(self.minimizeRequested.emit)

        self.btn_max = QPushButton()
        self.btn_max.setObjectName("BtnMax")
        self.btn_max.setIcon(icon("fa5s.square"))
        self.btn_max.setToolTip("Phóng to")
        self.btn_max.clicked.connect(self.maximizeRestoreRequested.emit)

        self.btn_close = QPushButton()
        self.btn_close.setObjectName("BtnClose")
        self.btn_close.setIcon(icon("fa5s.times"))
        self.btn_close.setToolTip("Đóng")
        self.btn_close.clicked.connect(self.closeRequested.emit)

        for button in (self.btn_min, self.btn_max, self.btn_close):
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setIconSize(QSize(10, 10))
            button.setFixedSize(46, 30)
            root.addWidget(button)

        self.set_home_mode(True)

    def set_menu_bar(self, menu_bar: QMenuBar) -> None:
        self._menu_bar = menu_bar
        menu_bar.setObjectName("MainMenuBar")
        menu_bar.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        self.menu_host_layout.addWidget(menu_bar)

    def set_project_name(self, name: str) -> None:
        self.project_label.setText(name)
        self.project_label.setToolTip(name)

    def set_home_mode(self, enabled: bool) -> None:
        self._home_mode = enabled
        self.project_separator.setVisible(not enabled and not self._compact)
        self.project_label.setVisible(not enabled and not self._compact)
        self.menu_host.setVisible(not enabled)
        if enabled:
            self.project_label.clear()

    def set_compact_mode(self, enabled: bool) -> None:
        self._compact = enabled
        self.app_name.setVisible(not enabled)
        self.project_separator.setVisible(not self._home_mode and not enabled)
        self.project_label.setVisible(not self._home_mode and not enabled)
        self.btn_info.setVisible(not enabled)
        self.menu_host_layout.setContentsMargins(2 if enabled else 8, 0, 0, 0)

    def set_maximized_icon(self, is_maximized: bool) -> None:
        icon_name = "fa5s.clone" if is_maximized else "fa5s.square"
        self.btn_max.setIcon(icon(icon_name))
        self.btn_max.setToolTip("Khôi phục" if is_maximized else "Phóng to")

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self._window.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._drag_pos is not None and event.buttons() & Qt.MouseButton.LeftButton:
            global_pos = event.globalPosition().toPoint()
            if self._window.isMaximized():
                ratio_x = event.position().x() / max(self.width(), 1)
                restore_for_drag = getattr(self._window, "restore_from_title_drag", None)
                if callable(restore_for_drag):
                    restore_for_drag(global_pos, ratio_x, int(event.position().y()))
                else:
                    self.maximizeRestoreRequested.emit()
                self._drag_pos = global_pos - self._window.frameGeometry().topLeft()
            else:
                self._window.move(global_pos - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._drag_pos = None
        event.accept()

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.maximizeRestoreRequested.emit()
