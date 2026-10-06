"""Embed the Terra tilemap editor in the project Asset Editor."""
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QLabel

from vendor.terra.engine.project import Project
from vendor.terra.ui.main_window import EditorWindow
from vendor.terra.ui.qtimg import qimage_from_pil


class EmbeddedTerraWindow(EditorWindow):
    def toggle_maximize(self):
        pass

    def closeEvent(self, event):
        event.ignore()
        host = self.parent()
        while host is not None:
            if hasattr(host, "reject"):
                host.reject()
                break
            host = host.parent()


class TerraPanel(QWidget):
    received = Signal(object, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFont(QFont("Segoe UI", 9))
        self.editor = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        receive = QPushButton("Đưa tilemap vào Assets")
        receive.clicked.connect(self.receive_map)
        layout.addWidget(receive)
        note = QLabel("Mở tilesheet hoặc dự án .terra.json · Vẽ theo layer · Lưu JSON / xuất PNG")
        note.setWordWrap(True)
        layout.addWidget(note)
        self.body = QVBoxLayout()
        layout.addLayout(self.body, 1)

    def ensure_editor(self):
        if self.editor is None:
            sheet = Path(__file__).resolve().parents[1] / "vendor/terra/sheets/tilemaps.png"
            project = Project.new(sheet, 10, 7, 32)
            project.mark_dirty(False)
            self.editor = EmbeddedTerraWindow(project)
            self.editor.setWindowFlags(Qt.WindowType.Widget)
            self.editor.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
            self.editor.setMinimumSize(640, 440)
            self.editor.layout().setContentsMargins(0, 0, 0, 0)
            self.editor.container.setGraphicsEffect(None)
            for button in (self.editor.title_bar.min_button,
                           self.editor.title_bar.max_button,
                           self.editor.title_bar.close_button):
                button.hide()
            self.body.addWidget(self.editor)
            self.editor.apply_theme("dark")
        return self.editor

    def receive_map(self):
        editor = self.ensure_editor()
        if not editor.project or not editor.project.sheet:
            editor._toast("Mở tilesheet trước khi đưa tilemap vào Assets.", "warning")
            return
        image = qimage_from_pil(editor.project.render(transparent=True))
        self.received.emit([image], editor.project.name or "tilemap")

    def can_close(self):
        return self.editor is None or self.editor._confirm_discard()
