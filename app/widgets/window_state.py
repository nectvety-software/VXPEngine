"""Window state manager following Windows standard behavior.

Tracks the window's normal geometry (position and size) across
minimize, restore, maximize, and close state transitions.
"""
from __future__ import annotations

from enum import Enum

from PySide6.QtCore import QObject, QRect, Signal
from PySide6.QtWidgets import QWidget


class WindowStage(Enum):
    NORMAL = "normal"
    MINIMIZED = "minimized"
    MAXIMIZED = "maximized"


class WindowState(QObject):
    stageChanged = Signal(WindowStage)

    def __init__(self, window: QWidget) -> None:
        super().__init__(window)
        self._window = window
        self._stage = WindowStage.NORMAL
        self._normal_geometry: QRect = window.geometry()

    @property
    def stage(self) -> WindowStage:
        return self._stage

    @property
    def is_minimized(self) -> bool:
        return self._stage == WindowStage.MINIMIZED

    @property
    def is_maximized(self) -> bool:
        return self._stage == WindowStage.MAXIMIZED

    @property
    def is_normal(self) -> bool:
        return self._stage == WindowStage.NORMAL

    @property
    def normal_geometry(self) -> QRect:
        return self._normal_geometry

    def save_normal_geometry(self) -> None:
        self._normal_geometry = self._window.geometry()

    def minimize(self) -> None:
        if self._stage == WindowStage.MAXIMIZED:
            self.save_normal_geometry()
        self._stage = WindowStage.MINIMIZED
        self.stageChanged.emit(self._stage)
        self._window.showMinimized()

    def restore(self) -> None:
        if self._stage == WindowStage.MINIMIZED:
            self._stage = WindowStage.NORMAL
            self._window.setGeometry(self._normal_geometry)
            self._window.showNormal()
        elif self._stage == WindowStage.MAXIMIZED:
            self._stage = WindowStage.NORMAL
            self._window.setGeometry(self._normal_geometry)
            self._window.showNormal()
        self.stageChanged.emit(self._stage)

    def maximize(self) -> None:
        if self._stage == WindowStage.NORMAL:
            self.save_normal_geometry()
        self._stage = WindowStage.MAXIMIZED
        self.stageChanged.emit(self._stage)
        self._window.showMaximized()

    def toggle_maximize_restore(self) -> None:
        if self._stage == WindowStage.MAXIMIZED:
            self.restore()
        else:
            self.maximize()

    def on_shown(self) -> None:
        if self._stage == WindowStage.NORMAL and self._normal_geometry.isValid():
            self._window.setGeometry(self._normal_geometry)

    def on_geometry_changed(self) -> None:
        if self._stage == WindowStage.NORMAL:
            self._normal_geometry = self._window.geometry()

    def on_qt_state_changed(self, is_minimized: bool, is_maximized: bool) -> None:
        if is_minimized and self._stage != WindowStage.MINIMIZED:
            self._stage = WindowStage.MINIMIZED
            self.stageChanged.emit(self._stage)
        elif is_maximized and self._stage != WindowStage.MAXIMIZED:
            self._stage = WindowStage.MAXIMIZED
            self.stageChanged.emit(self._stage)
        elif not is_minimized and not is_maximized and self._stage != WindowStage.NORMAL:
            self._stage = WindowStage.NORMAL
            self.stageChanged.emit(self._stage)