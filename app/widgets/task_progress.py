"""Compact bottom task indicator inspired by IDE build progress surfaces."""
from __future__ import annotations

from PySide6.QtCore import QPoint, QTimer, Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QProgressBar, QToolButton, QWidget

from .icons import icon


class BottomTaskProgress(QFrame):
    """Status-bar task chip for Run/Build/Debug without opening a dialog.

    The detailed custom-framed RunSessionDialog remains available through the
    terminal button, while the main editor stays unobstructed during builds.
    """

    open_requested = Signal()
    cancel_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("BottomTaskProgress")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._base_title = ""
        self._drag_active = False
        self._drag_offset = QPoint()
        self._host_widget: QWidget | None = None
        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self.hide)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 2, 4, 2)
        layout.setSpacing(7)

        self.state_icon = QLabel()
        self.state_icon.setObjectName("BottomTaskStateIcon")
        self.state_icon.setFixedSize(14, 14)
        layout.addWidget(self.state_icon)

        self.title_label = QLabel("Task")
        self.title_label.setObjectName("BottomTaskTitle")
        self.title_label.setMinimumWidth(120)
        self.title_label.setMaximumWidth(280)
        layout.addWidget(self.title_label)

        self.progress = QProgressBar()
        self.progress.setObjectName("BottomTaskProgressBar")
        self.progress.setTextVisible(False)
        self.progress.setFixedWidth(128)
        self.progress.setFixedHeight(5)
        layout.addWidget(self.progress)

        self.open_button = QToolButton()
        self.open_button.setObjectName("BottomTaskOpenButton")
        self.open_button.setIcon(icon("fa5s.terminal"))
        self.open_button.setToolTip("Mở cửa sổ log chi tiết")
        self.open_button.setFixedSize(24, 24)
        self.open_button.clicked.connect(self.open_requested.emit)
        layout.addWidget(self.open_button)

        self.cancel_button = QToolButton()
        self.cancel_button.setObjectName("BottomTaskCancelButton")
        self.cancel_button.setIcon(icon("fa5s.times"))
        self.cancel_button.setToolTip("Dừng tác vụ")
        self.cancel_button.setFixedSize(24, 24)
        self.cancel_button.clicked.connect(self.cancel_requested.emit)
        layout.addWidget(self.cancel_button)

        self.setFixedHeight(32)
        self.setMinimumWidth(320)
        self.hide()


    def attach_to_host(self, host: QWidget) -> None:
        self._host_widget = host
        self.setParent(host)
        self.raise_()
        self.snap_to_default()

    def snap_to_default(self) -> None:
        host = self._host_widget or self.parentWidget()
        if host is None:
            return
        right_margin = 22
        top_margin = 74
        x = max(8, host.width() - self.width() - right_margin)
        y = max(8, top_margin)
        self.move(x, y)

    def begin(self, title: str) -> None:
        self._hide_timer.stop()
        self._base_title = title.strip() or "Run / Build"
        self.title_label.setText(self._base_title)
        self.title_label.setToolTip(self._base_title)
        self.state_icon.setPixmap(icon("fa5s.circle-notch", "#70A6FF").pixmap(12, 12))
        self.progress.setRange(0, 0)
        self.cancel_button.setEnabled(True)
        self.open_button.setEnabled(True)
        self.adjustSize()
        if self._host_widget is not None and not self.isVisible():
            self.snap_to_default()
        self.show()
        self.raise_()

    def set_phase(self, phase: str) -> None:
        phase = phase.strip()
        if not phase or phase in {"Đang chạy", "Đang khởi động"}:
            text = self._base_title
        else:
            text = f"{self._base_title} · {phase}"
        self.title_label.setText(text)
        self.title_label.setToolTip(text)

    def finish(self, success: bool, message: str = "") -> None:
        self.progress.setRange(0, 1)
        self.progress.setValue(1)
        self.cancel_button.setEnabled(False)
        if success:
            self.state_icon.setPixmap(icon("fa5s.check-circle", "#62D690").pixmap(12, 12))
            suffix = message or "Hoàn tất"
        else:
            self.state_icon.setPixmap(icon("fa5s.times-circle", "#FF727A").pixmap(12, 12))
            suffix = message or "Thất bại"
        text = f"{self._base_title} · {suffix}"
        self.title_label.setText(text)
        self.title_label.setToolTip(text)
        self._hide_timer.start(5000 if success else 10000)

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802 - Qt API
        if event.button() == Qt.MouseButton.LeftButton:
            self.open_requested.emit()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)


    def mousePressEvent(self, event) -> None:  # noqa: N802 - Qt API
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_active = True
            self._drag_offset = event.position().toPoint()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802 - Qt API
        if self._drag_active:
            parent = self.parentWidget()
            if parent is not None:
                pos = self.mapToParent(event.position().toPoint() - self._drag_offset)
                x = max(6, min(parent.width() - self.width() - 6, pos.x()))
                y = max(6, min(parent.height() - self.height() - 6, pos.y()))
                self.move(x, y)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802 - Qt API
        if event.button() == Qt.MouseButton.LeftButton and self._drag_active:
            self._drag_active = False
            event.accept()
            return
        super().mouseReleaseEvent(event)
