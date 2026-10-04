"""Small in-app toast surface used for update and environment messages."""
from __future__ import annotations

from PySide6.QtCore import QTimer, Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QToolButton

from .icons import icon


class AppToast(QFrame):
    action_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("AppToast")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setMinimumWidth(360)
        self.setMaximumWidth(520)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 10, 8, 10)
        layout.setSpacing(9)
        self.icon_label = QLabel()
        layout.addWidget(self.icon_label)
        self.message_label = QLabel()
        self.message_label.setObjectName("AppToastText")
        self.message_label.setWordWrap(True)
        layout.addWidget(self.message_label, 1)
        self.action_button = QPushButton("Cập nhật")
        self.action_button.setObjectName("AppToastAction")
        self.action_button.clicked.connect(self.action_requested.emit)
        layout.addWidget(self.action_button)
        close = QToolButton()
        close.setObjectName("AppToastClose")
        close.setIcon(icon("fa5s.times"))
        close.clicked.connect(self.hide)
        layout.addWidget(close)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.hide)
        self.hide()

    def show_message(self, message: str, *, action_text: str = "", timeout_ms: int = 7000) -> None:
        self._timer.stop()
        self.icon_label.setPixmap(icon("fa5s.bell", "#70A6FF").pixmap(18, 18))
        self.message_label.setText(message)
        self.action_button.setText(action_text)
        self.action_button.setVisible(bool(action_text))
        self.adjustSize()
        parent = self.parentWidget()
        if parent is not None:
            self.move(max(12, parent.width() - self.width() - 24), 48)
        self.show()
        self.raise_()
        if timeout_ms > 0:
            self._timer.start(timeout_ms)

