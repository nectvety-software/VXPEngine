"""Embed the Terra tilemap editor in the project Asset Editor."""
from pathlib import Path
import copy

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QCheckBox, QSpinBox

from vendor.terra.engine.project import Project
from vendor.terra.engine.tilesheet import TileSheet
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
        tools = QHBoxLayout()
        sample = QPushButton("Mẫu địa hình 240×320")
        sample.clicked.connect(self.load_terrain_sample)
        tools.addWidget(sample)
        bind = QPushButton("Bộ 16 ô")
        bind.setToolTip("Chọn ô đầu của bộ 16 biến thể; thứ tự mask 0–15 (Bắc=1, Đông=2, Nam=4, Tây=8).")
        bind.clicked.connect(self.bind_terrain)
        tools.addWidget(bind)
        self.terrain_toggle = QCheckBox("Tự nối viền")
        self.terrain_toggle.setToolTip("Dùng atlas 16 ô theo mask Bắc/Đông/Nam/Tây; mẫu đã có sẵn atlas.")
        self.terrain_toggle.toggled.connect(self.set_terrain_enabled)
        tools.addWidget(self.terrain_toggle)
        tools.addWidget(QLabel("Cọ (ô):"))
        self.brush_size = QSpinBox()
        self.brush_size.setRange(1, 9)
        self.brush_size.valueChanged.connect(lambda value: setattr(self.ensure_editor().canvas, "brush_size", value))
        tools.addWidget(self.brush_size)
        layout.addLayout(tools)
        scatter_tools = QHBoxLayout()
        self.scatter_toggle = QCheckBox("Cọ rải vật thể")
        self.scatter_toggle.toggled.connect(lambda on: self.ensure_editor().select_tool("scatter" if on else "brush"))
        scatter_tools.addWidget(self.scatter_toggle)
        for attr, label, low, high, default in (("scatter_density", "Mật độ %", 0, 100, 35),
                ("scatter_spacing", "Cách (ô)", 1, 16, 1), ("scatter_seed", "Seed", 0, 999999, 1),
                ("scatter_count", "Biến thể", 1, 32, 4)):
            scatter_tools.addWidget(QLabel(label))
            control = QSpinBox(); control.setRange(low, high); control.setValue(default)
            setattr(self, attr, control)
            if attr != "scatter_count":
                control.valueChanged.connect(lambda value, name=attr: setattr(self.ensure_editor().canvas, name, value))
            scatter_tools.addWidget(control)
        bind_scatter = QPushButton("Gắn từ ô chọn")
        bind_scatter.clicked.connect(self.bind_scatter)
        scatter_tools.addWidget(bind_scatter)
        rocks = QPushButton("Mẫu đá")
        rocks.clicked.connect(self.load_scatter_sample)
        scatter_tools.addWidget(rocks)
        layout.addLayout(scatter_tools)
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

    def set_terrain_enabled(self, enabled):
        editor = self.ensure_editor()
        variants = editor.project.terrain.get("variants", [])
        if len(variants) != 16:
            self.terrain_toggle.blockSignals(True)
            self.terrain_toggle.setChecked(False)
            self.terrain_toggle.blockSignals(False)
            editor._toast("Mở Mẫu địa hình hoặc .terra.json có bộ 16 biến thể trước.", "warning")
            return
        editor.project.terrain["enabled"] = enabled
        editor._mark_dirty()

    def bind_terrain(self):
        editor = self.ensure_editor()
        start = editor.canvas.tile
        if not editor.project.sheet or start < 0 or start + 16 > len(editor.project.sheet.tiles):
            editor._toast("Chọn ô đầu của 16 biến thể liên tiếp trong tilesheet.", "warning")
            return
        editor.project.terrain = {"enabled": True, "variants": list(range(start, start+16)),
                                  "mask_order": "N=1,E=2,S=4,W=8"}
        self.terrain_toggle.setChecked(True)
        editor._mark_dirty()

    def load_terrain_sample(self):
        editor = self.ensure_editor()
        if not editor._confirm_discard():
            return
        source = Path(__file__).resolve().parents[2] / "assets/map/tileset/terrain_video_demo/terrain_portrait.terra.json"
        if not source.is_file():
            editor._toast("Thiếu bộ mẫu terrain_video_demo.", "warning")
            return
        editor.load_project(Project.load(source), str(source))
        editor.canvas.set_tile(15)
        editor.canvas.brush_size = self.brush_size.value()
        self.terrain_toggle.blockSignals(True)
        self.terrain_toggle.setChecked(True)
        self.terrain_toggle.blockSignals(False)

    def bind_scatter(self):
        editor = self.ensure_editor()
        start = editor.canvas.tile
        count = self.scatter_count.value()
        if not editor.project.sheet or start < 0 or start + count > len(editor.project.sheet.tiles):
            editor._toast("Chọn đủ ô biến thể liên tiếp trong atlas.", "warning")
            return
        editor.canvas.scatter_variants = list(range(start, start + count))
        self.scatter_toggle.setChecked(True)
        editor.select_tool("scatter")

    def load_scatter_sample(self):
        editor = self.ensure_editor()
        if not editor._confirm_discard():
            return
        source = Path(__file__).resolve().parents[2] / "assets/map/tileset/rock_scatter/rocks.terra.json"
        if not source.is_file():
            editor._toast("Thiếu mẫu rock_scatter.", "warning")
            return
        editor.load_project(Project.load(source), str(source))
        self.terrain_toggle.setChecked(False)
        editor.canvas.set_tile(0)
        self.scatter_count.setValue(4)
        self.bind_scatter()

    @staticmethod
    def save_editable(project, output: Path):
        """Save a portable map next to the exported image, retaining cells/layers."""
        folder = output.parent / f"{output.stem}_tiles"
        folder.mkdir(parents=True, exist_ok=True)
        sheet_path = folder / "atlas.png"
        project.sheet.image.save(sheet_path)
        document = copy.copy(project)
        document.sheet = TileSheet.open(sheet_path, project.sheet.cell)
        return document.save(output.with_suffix(".terra.json"))

    def receive_map(self):
        editor = self.ensure_editor()
        if not editor.project or not editor.project.sheet:
            editor._toast("Mở tilesheet trước khi đưa tilemap vào Assets.", "warning")
            return
        image = qimage_from_pil(editor.project.render(transparent=True))
        self.received.emit([image], editor.project.name or "tilemap")

    def can_close(self):
        return self.editor is None or self.editor._confirm_discard()
