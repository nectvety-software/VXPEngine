"""Terra editor window: toolbar, docks, canvas, status bar, commands."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (QApplication, QButtonGroup, QFrame, QHBoxLayout, QLabel, QMenu,
                                QPushButton, QSizePolicy, QVBoxLayout, QWidget)

from ..engine import __version__ as ENGINE_VERSION
from ..engine.history import FnCommand, History, PaintCommand
from ..engine.project import Project
from ..engine.tilemap import EMPTY
from . import dialogs, icons, panels, qtimg, theme
from .canvas import TOOLS, MapCanvas
from .theme import colors as theme_colors
from .window import CaptionButton, FramelessWindow

IMAGE_EXT = ["png", "jpg", "jpeg", "webp", "bmp"]
PROJECT_EXT = ["json"]


class EditorWindow(FramelessWindow):
    def __init__(self, project: Project | None = None):
        super().__init__("Terra Editor")
        self.theme_name = "dark"
        self.project = project
        self.history = History()
        self.resize(1380, 860)

        self._build_toolbar()
        self._build_body()
        self._build_status()
        self._build_actions()
        self.toast = dialogs.Toast(self.container)

        if self.project:
            self.load_project(self.project, source="khởi động")
        else:
            self._start_empty()
        self.refresh_theme()

    # ------------------------------------------------------------------ ui

    def _build_toolbar(self) -> None:
        bar = QFrame(self.body)
        bar.setProperty("role", "panel")
        bar.setFixedHeight(46)
        row = QHBoxLayout(bar)
        row.setContentsMargins(10, 6, 10, 6)
        row.setSpacing(4)

        self.file_buttons = [
            panels.IconButton("new", "Dự án mới\tCtrl+N"),
            panels.IconButton("folder", "Mở tilesheet\tCtrl+O"),
            panels.IconButton("save", "Lưu dự án\tCtrl+S"),
            panels.IconButton("export", "Xuất PNG\tCtrl+E"),
        ]
        for button in self.file_buttons:
            row.addWidget(button)
        row.addWidget(self._sep())

        self.tool_buttons: dict[str, panels.IconButton] = {}
        glyphs = {"brush": "brush", "eraser": "eraser", "fill": "bucket", "line": "line",
                  "rect": "rect"}
        self.tool_group = QButtonGroup(self)
        self.tool_group.setExclusive(True)
        for tool in TOOLS:
            button = panels.IconButton(glyphs[tool], f"Công cụ: {tool}", checkable=True)
            button.setProperty("tool", tool)
            self.tool_group.addButton(button)
            self.tool_buttons[tool] = button
            row.addWidget(button)
        row.addWidget(self._sep())

        self.grid_button = panels.IconButton("grid", "Bật/tắt lưới\tG", checkable=True)
        self.grid_button.setChecked(True)
        self.label_button = panels.IconButton("tiles", "Nhãn ô col.row\tShift+L", checkable=True)
        self.zoom_out_button = panels.IconButton("zoom-out", "Thu nhỏ\tCtrl+-")
        self.zoom_in_button = panels.IconButton("zoom-in", "Phóng to\tCtrl++")
        self.fit_button = panels.IconButton("fit", "Vừa khung\tF")
        for button in (self.grid_button, self.label_button, self.zoom_out_button,
                       self.zoom_in_button, self.fit_button):
            row.addWidget(button)
        row.addWidget(self._sep())

        self.undo_button = panels.IconButton("undo", "Hoàn tác\tCtrl+Z")
        self.redo_button = panels.IconButton("redo", "Làm lại\tCtrl+Shift+Z")
        row.addWidget(self.undo_button)
        row.addWidget(self.redo_button)
        row.addStretch(1)

        self.theme_button = panels.IconButton("moon", "Đổi giao diện\tCtrl+T")
        self.settings_button = panels.IconButton("settings", "Cài đặt\tCtrl+,")
        self.about_button = panels.IconButton("info", "Giới thiệu\tCtrl+I")
        for button in (self.theme_button, self.settings_button, self.about_button):
            row.addWidget(button)
        self.toolbar = bar

    def _sep(self) -> QFrame:
        line = QFrame()
        line.setProperty("role", "divider")
        line.setFixedWidth(1)
        line.setFixedHeight(22)
        return line

    def _build_body(self) -> None:
        content = QHBoxLayout()
        content.setContentsMargins(10, 10, 10, 6)
        content.setSpacing(10)

        # left dock — tile browser
        self.sheet_section = panels.Section("Tilesheet")
        self.tile_grid = panels.TileGrid()
        self.tile_grid.setMinimumWidth(196)
        self.sheet_section.add(self.tile_grid)
        self.sheet_caption = QLabel("—")
        self.sheet_caption.setProperty("role", "faint")
        self.sheet_section.add(self.sheet_caption)
        left = QFrame()
        left.setProperty("role", "panel")
        left.setFixedWidth(236)
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        inner = QVBoxLayout()
        inner.setContentsMargins(8, 8, 8, 8)
        inner.addWidget(self.sheet_section, 1)
        left_layout.addLayout(inner)

        # center — canvas
        self.canvas = MapCanvas(self.project)
        canvas_frame = QFrame()
        canvas_frame.setProperty("role", "panel")
        cf_layout = QVBoxLayout(canvas_frame)
        cf_layout.setContentsMargins(6, 6, 6, 6)
        cf_layout.addWidget(self.canvas)
        self.canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # right dock — layers, inspector, log
        layer_actions = QWidget()
        la = QHBoxLayout(layer_actions)
        la.setContentsMargins(0, 0, 0, 0)
        la.setSpacing(2)
        self.layer_add = panels.IconButton("plus", "Thêm lớp", size=15)
        self.layer_up = panels.IconButton("up", "Đẩy lớp lên", size=15)
        self.layer_down = panels.IconButton("down", "Hạ lớp xuống", size=15)
        self.layer_del = panels.IconButton("trash", "Xoá lớp", size=15)
        for button in (self.layer_add, self.layer_up, self.layer_down, self.layer_del):
            la.addWidget(button)

        self.layers_section = panels.Section("Lớp", action=layer_actions)
        self.layers = panels.LayersPanel()
        self.layers.setMinimumHeight(170)
        self.layers.setMaximumHeight(230)
        self.layers_section.add(self.layers)

        self.inspector = panels.InspectorPanel()
        self.log_section = panels.Section("Nhật ký")
        self.log = panels.LogPanel()
        self.log.setMinimumHeight(96)
        self.log_section.add(self.log)

        right = QFrame()
        right.setProperty("role", "panel")
        right.setFixedWidth(292)
        rl = QVBoxLayout(right)
        rl.setContentsMargins(8, 8, 8, 8)
        rl.setSpacing(8)
        rl.addWidget(self.layers_section)
        rl.addWidget(self.inspector)
        rl.addWidget(self.log_section, 1)

        content.addWidget(left)
        content.addWidget(canvas_frame, 1)
        content.addWidget(right)

        holder = QWidget(self.body)
        holder.setLayout(content)
        self.set_body(holder)

    def _build_status(self) -> None:
        bar = QFrame(self.body)
        bar.setProperty("role", "panel")
        bar.setFixedHeight(30)
        row = QHBoxLayout(bar)
        row.setContentsMargins(12, 0, 12, 0)
        row.setSpacing(16)

        def cap(text: str) -> QLabel:
            label = QLabel(text)
            label.setProperty("role", "stat")
            return label

        self.cursor_label = cap("Ô: —, —")
        self.tile_label = cap("Tile: —")
        self.zoom_label = cap("Zoom: 100%")
        self.mode_label = cap("Công cụ: brush")
        self.doc_label = cap("Chưa có dự án")
        self.dirty_badge = QLabel("● chưa lưu")
        self.dirty_badge.setProperty("role", "badge")
        self.dirty_badge.setProperty("tone", "warn")
        self.version_label = cap(f"engine v{ENGINE_VERSION}")

        for widget in (self.cursor_label, self.tile_label, self.zoom_label, self.mode_label):
            row.addWidget(widget)
        row.addStretch(1)
        row.addWidget(self.doc_label)
        row.addWidget(self.dirty_badge)
        row.addWidget(self.version_label)
        self.status_bar = bar

        body = self.body.layout()
        body.insertWidget(0, self.toolbar)
        body.insertWidget(2, bar)

    # ------------------------------------------------------------- actions

    def _build_actions(self) -> None:
        self.file_buttons[0].clicked.connect(self.new_project)
        self.file_buttons[1].clicked.connect(self.open_sheet)
        self.file_buttons[2].clicked.connect(self.save_project)
        self.file_buttons[3].clicked.connect(self.export_png)
        self.undo_button.clicked.connect(self.undo)
        self.redo_button.clicked.connect(self.redo)
        self.theme_button.clicked.connect(self.toggle_theme)
        self.settings_button.clicked.connect(self.open_settings)
        self.about_button.clicked.connect(self.show_about)

        for tool, button in self.tool_buttons.items():
            button.clicked.connect(lambda _=False, t=tool: self.select_tool(t))
        self.grid_button.toggled.connect(self._toggle_grid)
        self.label_button.toggled.connect(self.canvas.set_labels)
        self.zoom_out_button.clicked.connect(lambda: self.zoom_step(1 / 1.25))
        self.zoom_in_button.clicked.connect(lambda: self.zoom_step(1.25))
        self.fit_button.clicked.connect(self.fit_view)

        self.layer_add.clicked.connect(lambda: self.change_layers("add"))
        self.layer_del.clicked.connect(lambda: self.change_layers("remove"))
        self.layer_up.clicked.connect(lambda: self.change_layers("up"))
        self.layer_down.clicked.connect(lambda: self.change_layers("down"))
        self.layers.layerSelected.connect(self._select_layer)
        self.layers.visibilityToggled.connect(self._toggle_visible)
        self.layers.lockToggled.connect(self._toggle_lock)

        self.tile_grid.tilePicked.connect(self._pick_tile)
        self.canvas.paintCommitted.connect(self._commit_paint)
        self.canvas.cursorMoved.connect(self._show_cursor)
        self.canvas.zoomChanged.connect(self._show_zoom)
        self.inspector.zoomRequested.connect(self._set_zoom_percent)
        self.inspector.gridToggled.connect(self.grid_button.setChecked)
        self.inspector.labelsToggled.connect(self.label_button.setChecked)

        shortcuts = {
            "Ctrl+N": self.new_project, "Ctrl+O": self.open_sheet, "Ctrl+S": self.save_project,
            "Ctrl+E": self.export_png, "Ctrl+Z": self.undo, "Ctrl+Shift+Z": self.redo,
            "Ctrl+Y": self.redo, "Ctrl+T": self.toggle_theme, "Ctrl+,": self.open_settings,
            "Ctrl+I": self.show_about, "G": lambda: self.grid_button.toggle(),
            "F": self.fit_view, "B": lambda: self.select_tool("brush"),
            "E": lambda: self.select_tool("eraser"), "Q": lambda: self.select_tool("fill"),
            "L": lambda: self.select_tool("line"), "R": lambda: self.select_tool("rect"),
            "Shift+L": self.label_button.toggle,
            "Ctrl+Plus": lambda: self.zoom_step(1.25), "Ctrl+-": lambda: self.zoom_step(1 / 1.25),
        }
        for key, slot in shortcuts.items():
            QShortcut(QKeySequence(key), self, activated=slot)

    # ----------------------------------------------------------- documents

    def _start_empty(self) -> None:
        self.set_title("Terra Editor", "— chưa có dự án")
        self.canvas.set_project(None)
        self._sync_all()

    def new_project(self) -> None:
        if not self._confirm_discard():
            return
        path = dialogs.FileDialog.get_open_name(self, "Tilesheet cho dự án mới",
                                                self._start_dir(), IMAGE_EXT)
        if not path:
            return
        self.load_project(Project.new(path, 40, 24), source=Path(path).name)

    def open_sheet(self) -> None:
        path = dialogs.FileDialog.get_open_name(self, "Mở tilesheet", self._start_dir(),
                                                IMAGE_EXT)
        if not path:
            return
        if self.project is None:
            self.load_project(Project.new(path, 40, 24), source=Path(path).name)
            return
        previous = str(self.project.sheet.path) if self.project.sheet else None
        try:
            self.history.push(FnCommand("Gắn tilesheet",
                                        lambda: self._attach(path),
                                        lambda: self._attach(previous)))
            self._log(f"Đã đổi tilesheet → {Path(path).name}", "ok")
        except Exception as exc:  # surfaced as a dialog, never a crash
            dialogs.MessageDialog.ask(self, "Không mở được", str(exc),
                                      "Kiểm tra đường dẫn hoặc định dạng file.", "critical")

    def _attach(self, path: str | None) -> None:
        if path is None:
            self.project.sheet = None
        else:
            self.project.attach_sheet(path)
        qtimg.clear_cache()
        self._sync_all()
        self._mark_dirty()

    def load_project(self, project: Project, source: str = "") -> None:
        self.project = project
        self.history.clear()
        self.canvas.set_project(project)
        self._sync_all()
        self._mark_dirty(project.dirty)
        self._log(f"Nạp dự án · {source or project.name} · "
                  f"{project.stats()['placed']} tile", "ok")

    def save_project(self) -> None:
        if not self.project:
            return
        target = dialogs.FileDialog.get_save_name(self, "Lưu dự án",
                                                  self._start_dir(), PROJECT_EXT,
                                                  self.project.name)
        if not target:
            return
        try:
            saved = self.project.save(target)
        except Exception as exc:
            dialogs.MessageDialog.ask(self, "Không lưu được", str(exc), kind="critical")
            return
        self._mark_dirty(False)
        self._sync_title()
        self._log(f"Đã lưu {saved.name}", "ok")
        self._toast(f"Đã lưu {saved.name}", "success")

    def export_png(self) -> None:
        if not self.project or not self.project.sheet:
            self._toast("Chưa có tilesheet để xuất", "warning")
            return
        target = dialogs.FileDialog.get_save_name(self, "Xuất PNG", self._start_dir(),
                                                  IMAGE_EXT, f"{self.project.name}.png")
        if not target:
            return
        try:
            path = self.project.export_png(target)
        except Exception as exc:
            dialogs.MessageDialog.ask(self, "Xuất thất bại", str(exc), kind="critical")
            return
        self._log(f"Xuất {Path(path).name} · {self.project.map.pixel_size[0]}x"
                  f"{self.project.map.pixel_size[1]}", "ok")
        self._toast(f"Đã xuất {Path(path).name}", "success")

    def _start_dir(self) -> Path:
        if self.project and self.project.path:
            return self.project.path.parent
        if self.project and self.project.sheet:
            return self.project.sheet.path.parent
        return Path.cwd()

    # ------------------------------------------------------------- editing

    def select_tool(self, tool: str) -> None:
        self.canvas.set_tool(tool)
        self.tool_buttons[tool].setChecked(True)
        self.mode_label.setText(f"Công cụ: {tool}")

    def _pick_tile(self, index: int) -> None:
        self.canvas.set_tile(index)
        self.tile_label.setText(f"Tile: #{index}")
        self._sync_sheet_caption()

    def _commit_paint(self, label: str, edits: list) -> None:
        if not edits:
            return
        self.history.push(PaintCommand(label, self.project.map, edits))
        self._sync_history_buttons()
        self._mark_dirty()
        self._sync_layers()
        self.inspector.refresh(self.project, self.canvas.camera.zoom)

    def undo(self) -> None:
        if self.history.undo():
            self._after_history("Hoàn tác", self.history.undo_label)
        else:
            self._toast("Không còn gì để hoàn tác", "info")

    def redo(self) -> None:
        if self.history.redo():
            self._after_history("Làm lại", self.history.redo_label)
        else:
            self._toast("Không còn gì để làm lại", "info")

    def _sync_history_buttons(self) -> None:
        self.undo_button.setEnabled(self.history.can_undo)
        self.redo_button.setEnabled(self.history.can_redo)

    def _after_history(self, verb: str, label: str) -> None:
        self._sync_history_buttons()
        self._mark_dirty()
        self._sync_layers()
        self.inspector.refresh(self.project, self.canvas.camera.zoom)
        self.canvas.update()
        self._log(f"{verb}: {label}" if label else verb)

    def change_layers(self, action: str) -> None:
        if not self.project:
            return
        m = self.project.map
        if action == "add":
            name = dialogs.InputDialog.ask_text(self, "Lớp mới", "Tên lớp",
                                                f"Layer {len(m.layers) + 1}")
            if name is None:
                return
            self.history.push(FnCommand(f"Thêm lớp {name}",
                                        lambda: m.add_layer(name),
                                        lambda: m.remove_layer(m.active)))
        elif action == "remove":
            index = m.active
            if len(m.layers) <= 1:
                self._toast("Phải giữ lại ít nhất một lớp", "warning")
                return
            layer = m.layers[index]
            self.history.push(FnCommand(
                f"Xoá lớp {layer.name}", lambda i=index: m.remove_layer(i),
                lambda l=layer, i=index: (m.layers.insert(i, l), setattr(m, "active", i))))
        else:
            index, delta = m.active, (1 if action == "up" else -1)
            target = index + delta
            if not 0 <= target < len(m.layers):
                self._toast("Không thể dời lớp này", "warning")
                return
            m.move_layer(index, delta)
            self.history.push(FnCommand(f"Dời lớp {m.layers[target].name}",
                                        lambda: m.move_layer(index, delta),
                                        lambda: m.move_layer(target, -delta),
                                        run_on_push=False))
        self._sync_layers()
        self._mark_dirty()
        self._sync_history_buttons()
        self.canvas.update()

    def _select_layer(self, index: int) -> None:
        if self.project:
            self.project.map.active = index
            self.canvas.update()

    def _toggle_visible(self, index: int, value: bool) -> None:
        if not self.project or index >= len(self.project.map.layers):
            return
        layer = self.project.map.layers[index]
        self.history.push(FnCommand(f"{'Ẩn' if value else 'Hiện'} lớp {layer.name}",
                                    lambda: setattr(layer, "visible", value),
                                    lambda: setattr(layer, "visible", not value)))
        self._mark_dirty()
        self.canvas.update()

    def _toggle_lock(self, index: int, value: bool) -> None:
        if not self.project or index >= len(self.project.map.layers):
            return
        self.project.map.layers[index].locked = value
        self._sync_layers()
        self.canvas.update()

    # -------------------------------------------------------------- camera

    def zoom_step(self, factor: float) -> None:
        self.canvas.camera.zoom_at(factor)
        self._show_zoom(self.canvas.camera.zoom)
        self.canvas.update()

    def _set_zoom_percent(self, percent: int) -> None:
        self.canvas.camera.zoom = max(0.05, min(12.0, percent / 100.0))
        self._show_zoom(self.canvas.camera.zoom)
        self.canvas.update()

    def fit_view(self) -> None:
        if self.project:
            self.canvas.camera.fit(*self.project.map.pixel_size)
            self._show_zoom(self.canvas.camera.zoom)
            self.canvas.update()

    def _toggle_grid(self, value: bool) -> None:
        self.canvas.set_grid(value)
        if self.inspector.grid_check.isChecked() != value:
            self.inspector.grid_check.setChecked(value)

    # ------------------------------------------------------------- chrome

    def toggle_theme(self) -> None:
        self.apply_theme("light" if self.theme_name == "dark" else "dark")

    def apply_theme(self, name: str) -> None:
        self.theme_name = name
        theme.apply(QApplication.instance(), name)
        pal = theme_colors(QApplication.instance())
        self.theme_button.glyph = "sun" if name == "dark" else "moon"
        self.theme_button.restyle()
        for button in self.findChildren(panels.IconButton):
            button.restyle()
        for button in self.title_bar.findChildren(CaptionButton):
            button.restyle(pal)
        self.refresh_theme()
        self.canvas.update()
        self.tile_grid.viewport().update()
        self._log(f"Giao diện: {theme.theme(name).label}")

    def open_settings(self) -> None:
        rows = [("Chiều rộng map", self.project.map.width if self.project else 40, 1, 400),
                ("Chiều cao map", self.project.map.height if self.project else 24, 1, 400)]
        dialog = dialogs.NumberDialog(self, "Cài đặt dự án", rows)
        if not dialog.exec() or not self.project:
            return
        width, height = list(dialog.values.values())
        before = (self.project.map.width, self.project.map.height)
        self.history.push(FnCommand("Đổi kích thước map",
                                    lambda: self._resize_map(width, height),
                                    lambda: self._resize_map(*before)))
        self._sync_all()

    def _resize_map(self, width: int, height: int) -> None:
        m = self.project.map
        m.width, m.height = width, height
        for layer in m.layers:
            layer.width, layer.height = width, height
            layer.cells = [EMPTY] * (width * height)
        self.canvas.update()

    def show_about(self) -> None:
        rows = {"Engine": f"terra {ENGINE_VERSION}",
                "Toolkit": f"PySide6 {getattr(__import__('PySide6'), '__version__', '6')}",
                "Raster": "Pillow + NumPy",
                "Sheet": (self.project.sheet.path.name if self.project and self.project.sheet
                          else "—")}
        dialogs.AboutDialog(self, "Terra Editor", ENGINE_VERSION, rows).exec()

    def show_command_menu(self) -> None:
        menu = QMenu(self)
        menu.setToolTipsVisible(True)
        for label, slot, glyph in (
            ("Dự án mới", self.new_project, "new"),
            ("Mở tilesheet…", self.open_sheet, "folder"),
            ("Lưu dự án", self.save_project, "save"),
            ("Xuất PNG…", self.export_png, "export"),
            ("Hoàn tác", self.undo, "undo"),
            ("Làm lại", self.redo, "redo"),
            ("Vừa khung", self.fit_view, "fit"),
            ("Đổi giao diện", self.toggle_theme, "moon"),
            ("Cài đặt", self.open_settings, "settings"),
            ("Giới thiệu", self.show_about, "info"),
        ):
            action = menu.addAction(icons.icon(glyph, theme_colors(
                QApplication.instance())["text_muted"], 15), label)
            action.triggered.connect(slot)
        menu.addSeparator()
        menu.addAction(icons.icon("close", theme_colors(QApplication.instance())["danger"], 15),
                       "Thoát").triggered.connect(self.close)
        button = self.title_bar.menu_button
        menu.exec(button.mapToGlobal(button.rect().bottomLeft()))

    # -------------------------------------------------------------- status

    def _show_cursor(self, x: int, y: int) -> None:
        self.cursor_label.setText("Ô: —, —" if x < 0 else f"Ô: {x}, {y}")

    def _show_zoom(self, zoom: float) -> None:
        self.zoom_label.setText(f"Zoom: {int(round(zoom * 100))}%")
        self.inspector.refresh(self.project, zoom)

    def _sync_sheet_caption(self) -> None:
        sheet = self.project.sheet if self.project else None
        if not sheet:
            self.sheet_caption.setText("—")
            return
        self.sheet_caption.setText(f"{sheet.path.name} · {sheet.cell[0]}×{sheet.cell[1]} · "
                                   f"{len(sheet.solid)}/{sheet.count} ô")

    def _sync_layers(self) -> None:
        if self.project:
            self.layers.sync(self.project.map.layers, self.project.map.active)

    def _sync_title(self) -> None:
        name = self.project.name if self.project else "— chưa có dự án"
        self.set_title("Terra Editor", name)
        self.doc_label.setText(f"Dự án: {name}")

    def _mark_dirty(self, value: bool = True) -> None:
        if self.project:
            self.project.mark_dirty(value)
        self._sync_title()

    @property
    def dirty(self) -> bool:
        return bool(self.project and self.project.dirty)

    def _sync_all(self) -> None:
        self.tile_grid.set_sheet(self.project.sheet if self.project else None)
        self._sync_sheet_caption()
        self._sync_layers()
        self._sync_title()
        if self.project:
            self.inspector.refresh(self.project, self.canvas.camera.zoom)
            self.select_tool(self.canvas.tool)
        self.undo_button.setEnabled(bool(self.history.can_undo))
        self.redo_button.setEnabled(bool(self.history.can_redo))

    def _log(self, message: str, kind: str = "info") -> None:
        self.log.log(message, kind)

    def _toast(self, message: str, kind: str = "info") -> None:
        self.toast.popup(message, kind)

    def _confirm_discard(self) -> bool:
        if not self.dirty:
            return True
        answer = dialogs.MessageDialog.ask(
            self, "Thay đổi chưa lưu", "Dự án hiện tại có thay đổi chưa được lưu.",
            "Lưu trước khi tiếp tục?", "warning", ("Bỏ thay đổi", "Huỷ", "Lưu"))
        if answer == "Lưu":
            self.save_project()
            return not self.dirty
        return answer == "Bỏ thay đổi"

    # --------------------------------------------------------------- life

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.fit_view()

    def closeEvent(self, event) -> None:
        if not self._confirm_discard():
            event.ignore()
            return
        super().closeEvent(event)
