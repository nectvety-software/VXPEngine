"""
PanelFrame
----------
Khung chuẩn cho các panel bên trong dock (Scene, Assets, Inspector, Console...).
Có header với tiêu đề + nút menu (⋮), bo góc, viền mảnh, đúng phong cách
editor chuyên nghiệp trong ảnh mẫu.
"""
from PySide6.QtCore import Qt, QSize
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QToolButton

from .icons import icon


class PanelFrame(QWidget):
    def __init__(self, title: str, parent=None, show_header: bool = True):
        super().__init__(parent)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(4, 4, 4, 4)
        outer.setSpacing(0)

        self.frame = QWidget()
        self.frame.setObjectName("PanelFrame")
        outer.addWidget(self.frame)

        self.frame_layout = QVBoxLayout(self.frame)
        self.frame_layout.setContentsMargins(0, 0, 0, 0)
        self.frame_layout.setSpacing(0)

        self.header = None
        self.title_label = None
        self.menu_button = None

        if show_header:
            header = QWidget()
            self.header = header
            header.setObjectName("PanelHeader")
            h_layout = QHBoxLayout(header)
            h_layout.setContentsMargins(4, 2, 4, 2)

            title_lbl = QLabel(title)
            self.title_label = title_lbl
            title_lbl.setObjectName("PanelHeaderTitle")
            h_layout.addWidget(title_lbl)
            h_layout.addStretch()

            menu_btn = QToolButton()
            self.menu_button = menu_btn
            menu_btn.setObjectName("PanelMenuBtn")
            menu_btn.setIcon(icon("fa5s.ellipsis-v"))
            menu_btn.setIconSize(QSize(12, 12))
            menu_btn.setToolTip("Tùy chọn panel")
            h_layout.addWidget(menu_btn)

            self.frame_layout.addWidget(header)

        self.content = QWidget()
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(8, 8, 8, 8)
        self.content_layout.setSpacing(6)
        self.frame_layout.addWidget(self.content, 1)

    def add_widget(self, widget: QWidget):
        self.content_layout.addWidget(widget)

    def set_content_margins(self, l, t, r, b):
        self.content_layout.setContentsMargins(l, t, r, b)
