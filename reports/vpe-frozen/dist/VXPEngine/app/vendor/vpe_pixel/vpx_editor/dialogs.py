"""Modal dialogs: New Canvas, About, custom color, export options."""

from __future__ import annotations

from typing import Optional, Tuple

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QSpinBox,
    QComboBox, QLineEdit, QColorDialog, QFormLayout, QFrame, QWidget,
)

from . import APP_NAME, __version__, icons
from .paths import app_data_dir, is_frozen, project_dir
from .theme import get_theme
from .vpe import c565_to_rgb, rgb_to_565
from .widgets import AccentButton, SectionLabel, ShadowCard

PRESETS = [
    ("16 × 16", 16, 16),
    ("24 × 24", 24, 24),
    ("32 × 32", 32, 32),
    ("48 × 48", 48, 48),
    ("64 × 64", 64, 64),
    ("128 × 128", 128, 128),
    ("240 × 320 (QVGA)", 240, 320),
    ("Custom", 0, 0),
]


class NewCanvasDialog(QDialog):
    def __init__(self, parent=None, width: int = 16, height: int = 16) -> None:
        super().__init__(parent)
        self.setWindowTitle("New Canvas")
        self.setModal(True)
        self.setMinimumWidth(380)
        self._result: Optional[Tuple[int, int, int]] = None

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(14)

        card = ShadowCard("Canvas size")
        form = QFormLayout()
        form.setSpacing(10)

        self.preset = QComboBox()
        for label, w, h in PRESETS:
            self.preset.addItem(label, (w, h))
        self.preset.setToolTip("Start from a common canvas size")
        self.preset.setCurrentIndex(0 if width == 16 and height == 16 else -1)
        form.addRow("Preset", self.preset)

        self.w_spin = QSpinBox()
        self.w_spin.setRange(1, 640)
        self.w_spin.setValue(width)
        self.w_spin.setToolTip("Canvas width in pixels (max 640)")
        self.h_spin = QSpinBox()
        self.h_spin.setRange(1, 640)
        self.h_spin.setValue(height)
        self.h_spin.setToolTip("Canvas height in pixels (max 640)")
        form.addRow("Width", self.w_spin)
        form.addRow("Height", self.h_spin)

        self.fill = QComboBox()
        self.fill.addItem("White", 0xFFFF)
        self.fill.addItem("Black", 0x0000)
        self.fill.addItem("Transparent → White", 0xFFFF)
        self.fill.setToolTip("Fill colour — the editor has no alpha channel, "
                             "white (0xFFFF) is the transparent key")
        form.addRow("Background", self.fill)

        card.body().addLayout(form)
        root.addWidget(card)

        self.preset.currentIndexChanged.connect(self._on_preset)

        buttons = QHBoxLayout()
        buttons.addStretch()
        cancel = QPushButton("Cancel")
        icons.set_icon(cancel, "close", 15, text="Cancel",
                       tooltip="Discard and close (Esc)")
        cancel.clicked.connect(self.reject)
        create = AccentButton("Create")
        icons.set_icon(create, "check", 15, text="Create", token="on_accent",
                       tooltip="Create the canvas (Enter)")
        create.setDefault(True)
        create.clicked.connect(self._accept)
        buttons.addWidget(cancel)
        buttons.addWidget(create)
        root.addLayout(buttons)

    def _on_preset(self, index: int) -> None:
        w, h = self.preset.currentData()
        if w and h:
            self.w_spin.setValue(w)
            self.h_spin.setValue(h)

    def _accept(self) -> None:
        self._result = (
            self.w_spin.value(),
            self.h_spin.value(),
            int(self.fill.currentData()),
        )
        self.accept()

    def result_size(self) -> Optional[Tuple[int, int, int]]:
        return self._result


class NewAssetDialog(QDialog):
    """Create a titled game asset (titleset / sprite / texture / tile)."""

    SIZE_PRESETS = {
        "titleset": [("240 × 320 (QVGA screen)", 240, 320), ("128 × 128", 128, 128)],
        "sprite": [("16 × 16", 16, 16), ("24 × 24", 24, 24), ("32 × 32", 32, 32), ("48 × 48", 48, 48), ("64 × 64", 64, 64)],
        "texture": [("64 × 64", 64, 64), ("128 × 128", 128, 128), ("240 × 32 (bar)", 240, 32)],
        "tile": [("16 × 16", 16, 16), ("8 × 8", 8, 8), ("32 × 32", 32, 32)],
    }

    def __init__(self, parent=None, category: str = "sprite") -> None:
        super().__init__(parent)
        self.setWindowTitle("New game asset")
        self.setModal(True)
        self.setMinimumWidth(400)
        self._result = None

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(14)

        card = ShadowCard("Asset")
        form = QFormLayout()
        form.setSpacing(10)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("e.g. hero_walk, menu_bg")
        self.name_edit.setToolTip("File name without the .vpe extension")
        form.addRow("Name", self.name_edit)

        self.category = QComboBox()
        for key, label in (("titleset", "Titleset"), ("sprite", "Sprite"),
                           ("texture", "Texture"), ("tile", "Tile")):
            self.category.addItem(label, key)
        self.category.setToolTip("Which Documents\\VPE Pixel subfolder owns this asset")
        idx = self.category.findData(category if category != "all" else "sprite")
        self.category.setCurrentIndex(max(0, idx))
        form.addRow("Type", self.category)

        self.preset = QComboBox()
        self.preset.setToolTip("Common sizes for the selected type")
        form.addRow("Size preset", self.preset)

        self.w_spin = QSpinBox()
        self.w_spin.setRange(1, 640)
        self.w_spin.setToolTip("Asset width in pixels (max 640)")
        self.h_spin = QSpinBox()
        self.h_spin.setRange(1, 640)
        self.h_spin.setToolTip("Asset height in pixels (max 640)")
        form.addRow("Width", self.w_spin)
        form.addRow("Height", self.h_spin)

        self.fill = QComboBox()
        self.fill.addItem("White", 0xFFFF)
        self.fill.addItem("Black", 0x0000)
        self.fill.setToolTip("Starting fill — white is the transparent key")
        form.addRow("Fill", self.fill)

        card.body().addLayout(form)
        root.addWidget(card)

        self.category.currentIndexChanged.connect(self._load_presets)
        self.preset.currentIndexChanged.connect(self._on_preset)
        self._load_presets()

        buttons = QHBoxLayout()
        buttons.addStretch()
        cancel = QPushButton("Cancel")
        icons.set_icon(cancel, "close", 15, text="Cancel",
                       tooltip="Discard and close (Esc)")
        cancel.clicked.connect(self.reject)
        create = AccentButton("Create")
        icons.set_icon(create, "check", 15, text="Create", token="on_accent",
                       tooltip="Create the asset and open it on the canvas (Enter)")
        create.setDefault(True)
        create.clicked.connect(self._accept)
        buttons.addWidget(cancel)
        buttons.addWidget(create)
        root.addLayout(buttons)

    def _load_presets(self) -> None:
        self.preset.blockSignals(True)
        self.preset.clear()
        for label, w, h in self.SIZE_PRESETS.get(self.category.currentData(), []):
            self.preset.addItem(label, (w, h))
        self.preset.blockSignals(False)
        self._on_preset(0)

    def _on_preset(self, index: int) -> None:
        data = self.preset.currentData()
        if data:
            w, h = data
            self.w_spin.setValue(w)
            self.h_spin.setValue(h)

    def _accept(self) -> None:
        name = self.name_edit.text().strip() or f"{self.category.currentData()}_untitled"
        self._result = (name, self.category.currentData(),
                        self.w_spin.value(), self.h_spin.value(),
                        int(self.fill.currentData()))
        self.accept()

    def result_asset(self):
        return self._result


class AboutDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"About {APP_NAME}")
        self.setModal(True)
        self.setMinimumWidth(420)
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(12)

        title = QLabel(APP_NAME)
        title.setObjectName("Title")
        f = QFont()
        f.setPointSize(20)
        f.setBold(True)
        title.setFont(f)
        root.addWidget(title)

        ver = QLabel(f"Version {__version__}  ·  PySide6  ·  VPE565 native")
        ver.setObjectName("Muted")
        root.addWidget(ver)

        body = QLabel(
            "Professional pixel-art editor inspired by VXP Pixel Editor "
            "(LuaS30 / Nokia S30+).\n\n"
            "• Native .vpe project format (VPE565)\n"
            "• RGB565 color model with classic 16-color palette\n"
            "• Pencil, Eraser, Fill, Line, Rectangle, Eyedropper\n"
            "• Undo / Redo, zoomable grid canvas, Light & Dark themes\n"
            "• Export BMP / PNG, import PNG / BMP / VPE\n\n"
            "Right-drag to pan · Scroll to zoom · Double-click to fit\n\n"
            f"Projects:  {project_dir(False)}\n"
            f"App data:  {app_data_dir(False)}\n"
            f"Mode:      {'Portable EXE' if is_frozen() else 'Source'}"
        )
        body.setWordWrap(True)
        body.setObjectName("Muted")
        root.addWidget(body)

        close = AccentButton("Close")
        icons.set_icon(close, "check", 15, text="Close", token="on_accent",
                       tooltip="Close this dialog (Enter)")
        close.clicked.connect(self.accept)
        row = QHBoxLayout()
        row.addStretch()
        row.addWidget(close)
        root.addLayout(row)


def pick_color(parent, initial: int = 0xF800) -> Optional[int]:
    r, g, b = c565_to_rgb(initial)
    color = QColorDialog.getColor(QColor(r, g, b), parent, "Choose color")
    if not color.isValid():
        return None
    return rgb_to_565(color.red(), color.green(), color.blue())
