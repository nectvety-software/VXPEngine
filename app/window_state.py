"""Windows-like window placement and state management for VXPEngine.

The application uses a frameless QWidget, therefore Qt's native title bar does
not manage minimize/maximize/restore placement for us.  This controller keeps a
normal geometry, remembers the last non-minimized state, updates the custom
chrome, and persists placement with QSettings.
"""
from __future__ import annotations

from PySide6.QtCore import QObject, QPoint, QRect, QSettings, Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QFrame, QLayout, QWidget


class WindowStateController(QObject):
    """Own the custom window-control state machine for a frameless window."""

    SETTINGS_GEOMETRY = "window/qt_geometry"
    SETTINGS_NORMAL_GEOMETRY = "window/normal_geometry"
    SETTINGS_MAXIMIZED = "window/maximized"
    SETTINGS_LAST_STATE = "window/last_state"

    def __init__(
        self,
        window: QWidget,
        title_bar: QWidget,
        outer_layout: QLayout,
        root_frame: QFrame,
        normal_margin: int = 6,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent or window)
        self.window = window
        self.title_bar = title_bar
        self.outer_layout = outer_layout
        self.root_frame = root_frame
        self.normal_margin = max(0, normal_margin)
        self.settings = QSettings()

        self._normal_geometry = QRect(window.geometry())
        self._last_non_minimized_state = Qt.WindowState.WindowNoState
        self._state_before_hide = Qt.WindowState.WindowNoState
        self._initial_maximized = False
        self._restoring = False

    @property
    def normal_geometry(self) -> QRect:
        return QRect(self._normal_geometry)

    def show_initial(self) -> None:
        """Restore persisted placement and show the window visibly on-screen."""
        self._restore_persisted_placement()
        if self._initial_maximized:
            self.window.showMaximized()
        else:
            self.window.show()
        self.sync_from_window()

    def minimize(self) -> None:
        """Minimize while retaining whether restore should return maximized."""
        if self.window.isMinimized():
            return
        if self.window.isMaximized():
            self._last_non_minimized_state = Qt.WindowState.WindowMaximized
        else:
            self._capture_normal_geometry()
            self._last_non_minimized_state = Qt.WindowState.WindowNoState
        self.window.showMinimized()

    def toggle_maximize_restore(self) -> None:
        """Apply the behavior of the standard Windows maximize/restore button."""
        if self.window.isMinimized():
            self.show_window()
            return
        if self.window.isMaximized():
            self.restore_normal()
        else:
            self.maximize()

    def maximize(self) -> None:
        if not self.window.isMaximized():
            self._capture_normal_geometry()
        self._last_non_minimized_state = Qt.WindowState.WindowMaximized
        self.window.showMaximized()
        self.sync_from_window()

    def restore_normal(self) -> None:
        self.window.showNormal()
        if self._normal_geometry.isValid():
            self.window.setGeometry(self._safe_geometry(self._normal_geometry))
        self._last_non_minimized_state = Qt.WindowState.WindowNoState
        self.sync_from_window()

    def hide_window(self) -> None:
        """Hide without losing the state used when the window is shown again."""
        if not self.window.isVisible():
            return
        if self.window.isMaximized():
            self._state_before_hide = Qt.WindowState.WindowMaximized
        elif self.window.isMinimized():
            self._state_before_hide = self._last_non_minimized_state
        else:
            self._capture_normal_geometry()
            self._state_before_hide = Qt.WindowState.WindowNoState
        self.window.hide()

    def show_window(self) -> None:
        """Show/restore the app and bring it to the foreground."""
        restore_state = self._state_before_hide
        if self.window.isMinimized():
            restore_state = self._last_non_minimized_state

        if restore_state == Qt.WindowState.WindowMaximized:
            self.window.showMaximized()
            self._last_non_minimized_state = Qt.WindowState.WindowMaximized
        else:
            self.window.showNormal()
            if self._normal_geometry.isValid():
                self.window.setGeometry(self._safe_geometry(self._normal_geometry))
            self._last_non_minimized_state = Qt.WindowState.WindowNoState

        self.window.raise_()
        self.window.activateWindow()
        self.sync_from_window()

    def restore_from_title_drag(
        self,
        global_position: QPoint,
        horizontal_ratio: float,
        local_y: int,
    ) -> None:
        """Restore a maximized window under the pointer before title-bar drag."""
        if not self.window.isMaximized():
            return

        normal = self._normal_geometry
        if not normal.isValid():
            normal = QRect(0, 0, max(self.window.minimumWidth(), 1200), max(self.window.minimumHeight(), 760))

        width = normal.width()
        height = normal.height()
        ratio = min(1.0, max(0.0, horizontal_ratio))
        x = global_position.x() - int(width * ratio)
        y = global_position.y() - max(0, local_y)

        self.window.showNormal()
        self.window.setGeometry(self._safe_geometry(QRect(x, y, width, height), clamp_fully=False))
        self._last_non_minimized_state = Qt.WindowState.WindowNoState
        self.sync_from_window()

    def handle_window_state_change(self) -> None:
        """Call from MainWindow.changeEvent(WindowStateChange)."""
        state = self.window.windowState()
        if state & Qt.WindowState.WindowMinimized:
            # Keep the last normal/maximized state for the next restore.
            pass
        elif state & Qt.WindowState.WindowMaximized:
            self._last_non_minimized_state = Qt.WindowState.WindowMaximized
        else:
            self._last_non_minimized_state = Qt.WindowState.WindowNoState
            self._capture_normal_geometry()
        self.sync_from_window()

    def handle_geometry_change(self) -> None:
        """Call from moveEvent/resizeEvent so normal placement stays current."""
        if self._restoring:
            return
        if self.window.isVisible() and not self.window.isMaximized() and not self.window.isMinimized():
            self._capture_normal_geometry()

    def sync_from_window(self) -> None:
        is_maximized = self.window.isMaximized()
        margin = 0 if is_maximized else self.normal_margin
        self.outer_layout.setContentsMargins(margin, margin, margin, margin)

        self.root_frame.setProperty("windowMaximized", is_maximized)
        self.title_bar.setProperty("windowMaximized", is_maximized)
        self._repolish(self.root_frame)
        self._repolish(self.title_bar)

        set_icon = getattr(self.title_bar, "set_maximized_icon", None)
        if callable(set_icon):
            set_icon(is_maximized)

    def save_persisted_placement(self) -> None:
        """Persist the normal rectangle and last non-minimized state."""
        if not self.window.isMaximized() and not self.window.isMinimized():
            self._capture_normal_geometry()

        maximized = self.window.isMaximized()
        if self.window.isMinimized():
            maximized = self._last_non_minimized_state == Qt.WindowState.WindowMaximized

        self.settings.setValue(self.SETTINGS_GEOMETRY, self.window.saveGeometry())
        self.settings.setValue(self.SETTINGS_NORMAL_GEOMETRY, self._normal_geometry)
        self.settings.setValue(self.SETTINGS_MAXIMIZED, maximized)
        self.settings.setValue(
            self.SETTINGS_LAST_STATE,
            "maximized" if maximized else "normal",
        )
        self.settings.sync()

    def _restore_persisted_placement(self) -> None:
        self._restoring = True
        try:
            stored_normal = self.settings.value(self.SETTINGS_NORMAL_GEOMETRY)
            if isinstance(stored_normal, QRect) and stored_normal.isValid():
                self._normal_geometry = self._safe_geometry(stored_normal)
                self.window.setGeometry(self._normal_geometry)
            else:
                qt_geometry = self.settings.value(self.SETTINGS_GEOMETRY)
                restored = bool(qt_geometry) and self.window.restoreGeometry(qt_geometry)
                if restored:
                    self._normal_geometry = self._safe_geometry(self.window.geometry())
                    self.window.setGeometry(self._normal_geometry)
                else:
                    self._normal_geometry = self._centered_default_geometry()
                    self.window.setGeometry(self._normal_geometry)

            self._initial_maximized = self.settings.value(
                self.SETTINGS_MAXIMIZED,
                False,
                type=bool,
            )
            self._last_non_minimized_state = (
                Qt.WindowState.WindowMaximized
                if self._initial_maximized
                else Qt.WindowState.WindowNoState
            )
            self._state_before_hide = self._last_non_minimized_state
        finally:
            self._restoring = False

    def _capture_normal_geometry(self) -> None:
        geometry = self.window.geometry()
        if geometry.isValid():
            self._normal_geometry = QRect(geometry)

    def _centered_default_geometry(self) -> QRect:
        screen = QGuiApplication.primaryScreen()
        if screen is None:
            return QRect(80, 80, self.window.width(), self.window.height())
        available = screen.availableGeometry()
        width = min(max(self.window.minimumWidth(), self.window.width()), available.width())
        height = min(max(self.window.minimumHeight(), self.window.height()), available.height())
        x = available.x() + max(0, (available.width() - width) // 2)
        y = available.y() + max(0, (available.height() - height) // 2)
        return QRect(x, y, width, height)

    def _safe_geometry(self, geometry: QRect, clamp_fully: bool = True) -> QRect:
        """Keep restored windows accessible after monitor/DPI configuration changes."""
        rect = QRect(geometry)
        screens = QGuiApplication.screens()
        if not screens:
            return rect

        best_screen = None
        best_area = -1
        for screen in screens:
            intersection = rect.intersected(screen.availableGeometry())
            area = max(0, intersection.width()) * max(0, intersection.height())
            if area > best_area:
                best_area = area
                best_screen = screen

        if best_screen is None or best_area < 80 * 40:
            return self._centered_default_geometry()

        available = best_screen.availableGeometry()
        width = min(max(self.window.minimumWidth(), rect.width()), available.width())
        height = min(max(self.window.minimumHeight(), rect.height()), available.height())

        if clamp_fully:
            x = min(max(rect.x(), available.left()), available.right() - width + 1)
            y = min(max(rect.y(), available.top()), available.bottom() - height + 1)
        else:
            # During restore-and-drag, only keep enough title bar visible to grab.
            visible_title_width = min(160, width)
            x = min(max(rect.x(), available.left() - width + visible_title_width), available.right() - visible_title_width + 1)
            y = min(max(rect.y(), available.top()), available.bottom() - 40)
        return QRect(x, y, width, height)

    @staticmethod
    def _repolish(widget: QWidget) -> None:
        style = widget.style()
        if style is not None:
            style.unpolish(widget)
            style.polish(widget)
        widget.update()
