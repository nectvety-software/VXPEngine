"""Main application window — enterprise dark/light pixel editor chrome."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, QSize, QTimer, QSettings
from PySide6.QtGui import QAction, QKeySequence, QIcon, QColor, QPainter, QPixmap, QCloseEvent
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QFrame, QLabel,
    QFileDialog, QMessageBox, QStatusBar, QApplication,
    QPushButton, QScrollArea, QButtonGroup, QStackedWidget,
)

from . import APP_NAME, __version__, icons
from .canvas import CanvasView
from .document import Document
from .dialogs import NewCanvasDialog, NewAssetDialog, AboutDialog, pick_color
from .gallery import GalleryPanel, ensure_category_dirs, asset_kind
from .palette import PALETTE_565, name_for_index
from .paths import (
    app_data_dir, autosave_file, ensure_layout, export_dir,
    is_frozen, project_dir, settings_file,
)
from .theme import get_theme
from .timeline import TimelineBar
from .vpe import (
    VpeError, save_vpe, load_vpe, save_bmp, save_png, load_image_as_565,
    c565_to_rgb, rgb_to_565,
)
from .vpea import save_png_strip
from .widgets import (
    AccentButton, ColorPreview, GlyphLabel, InfoChip, PaletteGrid, SectionLabel,
    ShadowCard, SizeSelector, ThemeToggleButton, ToolRailButton,
)

TOOLS = [
    ("pencil", "pencil", "Pencil (B)", "Draw pixels"),
    ("eraser", "eraser", "Eraser (E)", "Erase to background"),
    ("fill", "fill", "Fill (G)", "Flood fill"),
    ("line", "line", "Line (L)", "Draw straight line"),
    ("rect", "rect", "Rectangle (U)", "Stroke rectangle"),
    ("rectfill", "rectfill", "Filled Rect (R)", "Filled rectangle"),
    ("pick", "pick", "Eyedropper (I)", "Pick color from canvas"),
]

TOOL_KEYS = {
    "B": "pencil", "E": "eraser", "G": "fill", "L": "line",
    "U": "rect", "R": "rectfill", "I": "pick",
}


def selected_ext(filter_text: str, fallback: str) -> str:
    """Extension implied by the chosen save dialog filter."""
    found = set(re.findall(r"\*\.vpea?", (filter_text or "").lower()))
    if len(found) == 1:
        return ".vpea" if found == {"*.vpea"} else ".vpe"
    return fallback


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.setMinimumSize(1100, 720)
        self.resize(1360, 860)

        self._doc = Document.blank(32, 32, 0xFFFF, "Untitled")
        self._current_path: Optional[str] = None
        self._current_tool = "pencil"
        self._asset_category = "sprite"  # where untitled assets get saved
        # Settings live in %APPDATA%\VXP Pixel Editor\settings.ini
        self._settings = QSettings(str(settings_file()), QSettings.Format.IniFormat)
        self._paths = ensure_layout()
        self._cursor_x = 0
        self._cursor_y = 0

        self._build_ui()
        self._build_menus()
        self._build_shortcuts()
        self._bind()
        self._apply_theme()
        self._update_title()
        self._update_status()

        # Animate window fade-in
        self.setWindowOpacity(0.0)
        self._fade = QTimer(self)
        self._fade.timeout.connect(self._fade_step)
        self._fade.start(8)
        self._fade_target = 1.0

    # ------------------------------------------------------------------ UI
    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # --- Tool rail (left) ---
        rail = QFrame()
        rail.setObjectName("ToolRail")
        rail.setFixedWidth(72)
        rail_lay = QVBoxLayout(rail)
        rail_lay.setContentsMargins(10, 14, 10, 14)
        rail_lay.setSpacing(8)

        logo = QLabel("PX")
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo.setFixedHeight(40)
        logo.setStyleSheet(
            "QLabel { background: #4C8DFF; color: white; border-radius: 12px;"
            " font-weight: 700; font-size: 15px; }"
        )
        rail_lay.addWidget(logo)
        rail_lay.addSpacing(8)

        self._tool_buttons = {}
        self._tool_group = QButtonGroup(self)
        self._tool_group.setExclusive(True)

        for key, icon_name, title, desc in TOOLS:
            btn = ToolRailButton(key, icon_name, f"{title} — {desc}")
            btn.clicked.connect(lambda _=False, k=key: self._select_tool(k))
            self._tool_group.addButton(btn)
            self._tool_buttons[key] = btn
            rail_lay.addWidget(btn)

        rail_lay.addSpacing(6)
        self._gallery_btn = ToolRailButton(
            "gallery", "gallery", "Asset collection (Ctrl+E) — browse Documents\\VPE Pixel")
        self._gallery_btn.clicked.connect(self._toggle_view)
        rail_lay.addWidget(self._gallery_btn)

        rail_lay.addStretch()
        self._theme_btn = ThemeToggleButton()
        self._theme_btn.theme_toggled.connect(self._on_theme_changed)
        rail_lay.addWidget(self._theme_btn)
        root.addWidget(rail)

        # --- Center canvas ---
        center = QWidget()
        center_lay = QVBoxLayout(center)
        center_lay.setContentsMargins(0, 0, 0, 0)
        center_lay.setSpacing(0)

        # Top bar with doc title + zoom
        topbar = QFrame()
        topbar.setObjectName("StatusBar")
        topbar.setFixedHeight(48)
        top_lay = QHBoxLayout(topbar)
        top_lay.setContentsMargins(18, 0, 18, 0)
        self._doc_title = QLabel("Untitled")
        self._doc_title.setObjectName("Title")
        self._doc_title.setStyleSheet("font-size: 15px; font-weight: 600;")
        top_lay.addWidget(self._doc_title)
        top_lay.addStretch()

        self._zoom_out_btn = QPushButton()
        icons.set_icon(self._zoom_out_btn, "zoom_out", 16, text="",
                       token="muted", tooltip="Zoom out (−)")
        self._zoom_out_btn.setObjectName("Ghost")
        self._zoom_out_btn.setFixedSize(32, 32)
        self._zoom_out_btn.clicked.connect(self._zoom_out)
        self._zoom_label = QLabel("100%")
        self._zoom_label.setObjectName("Hi")
        self._zoom_label.setMinimumWidth(56)
        self._zoom_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._zoom_in_btn = QPushButton()
        icons.set_icon(self._zoom_in_btn, "zoom_in", 16, text="",
                       token="muted", tooltip="Zoom in (+)")
        self._zoom_in_btn.setObjectName("Ghost")
        self._zoom_in_btn.setFixedSize(32, 32)
        self._zoom_in_btn.clicked.connect(self._zoom_in)
        fit_btn = QPushButton()
        icons.set_icon(fit_btn, "fit", 16, text="", token="muted",
                       tooltip="Fit canvas to window (Ctrl+0)")
        fit_btn.setObjectName("Ghost")
        fit_btn.setFixedSize(32, 32)
        fit_btn.clicked.connect(self._fit)
        top_lay.addWidget(self._zoom_out_btn)
        top_lay.addWidget(self._zoom_label)
        top_lay.addWidget(self._zoom_in_btn)
        top_lay.addSpacing(8)
        top_lay.addWidget(fit_btn)
        center_lay.addWidget(topbar)

        # Stacked views: editor canvas / asset gallery
        self._views = QStackedWidget()
        host = QWidget()
        host_lay = QVBoxLayout(host)
        host_lay.setContentsMargins(12, 12, 12, 12)
        self.canvas = CanvasView()
        host_lay.addWidget(self.canvas, 1)
        self.timeline = TimelineBar()
        host_lay.addWidget(self.timeline)
        self._views.addWidget(host)  # page 0: editor

        self._gallery = GalleryPanel()
        self._gallery.open_requested.connect(self._open_gallery_asset)
        self._gallery.create_requested.connect(self._new_asset)
        self._gallery.imported.connect(
            lambda p: self.statusBar().showMessage(f"Imported {p.name} as .vpe asset", 3000))
        self._views.addWidget(self._gallery)  # page 1: gallery
        self._views.setCurrentIndex(0)
        center_lay.addWidget(self._views, 1)
        root.addWidget(center, 1)

        # --- Right side panel ---
        side = QFrame()
        side.setObjectName("SidePanel")
        side.setFixedWidth(310)
        side_lay = QVBoxLayout(side)
        side_lay.setContentsMargins(14, 14, 14, 14)
        side_lay.setSpacing(12)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        panel = QWidget()
        panel_lay = QVBoxLayout(panel)
        panel_lay.setContentsMargins(0, 0, 4, 0)
        panel_lay.setSpacing(12)

        # Color card
        color_card = ShadowCard("Color")
        self._color_preview = ColorPreview()
        color_card.body().addWidget(self._color_preview)
        self._palette = PaletteGrid(columns=8)
        self._palette.color_selected.connect(self._on_palette_color)
        color_card.body().addWidget(self._palette)
        btn_row = QHBoxLayout()
        custom_btn = QPushButton()
        icons.set_icon(custom_btn, "palette", 16, text="Custom…",
                       tooltip="Pick any RGB565 color")
        custom_btn.clicked.connect(self._pick_custom_color)
        swap_btn = QPushButton()
        icons.set_icon(swap_btn, "swap", 16, text="Swap",
                       tooltip="Swap foreground and background")
        swap_btn.setObjectName("Ghost")
        swap_btn.clicked.connect(self._swap_fg_bg)
        btn_row.addWidget(custom_btn)
        btn_row.addWidget(swap_btn)
        color_card.body().addLayout(btn_row)
        self._bg_preview = ColorPreview()
        self._bg_preview.set_color(0xFFFF)
        color_card.body().addWidget(self._bg_preview)
        panel_lay.addWidget(color_card)

        # Brush card
        brush_card = ShadowCard("Brush")
        self._size_sel = SizeSelector()
        self._size_sel.size_changed.connect(self._on_size_changed)
        brush_card.body().addWidget(SectionLabel("Size"))
        brush_card.body().addWidget(self._size_sel)
        panel_lay.addWidget(brush_card)

        # View card — background / no-background / grid
        view_card = ShadowCard("View")
        view_card.body().addWidget(SectionLabel("Canvas"))
        toggles = QHBoxLayout()
        toggles.setSpacing(6)
        self._bg_check = QPushButton("BG")
        icons.set_icon(self._bg_check, "eye", 15,
                       tooltip="Checker background under the sprite (Ctrl+B)")
        self._bg_check.setCheckable(True)
        self._bg_check.setChecked(True)
        self._bg_check.clicked.connect(self._toggle_background)
        self._nbg_check = QPushButton("No BG")
        icons.set_icon(self._nbg_check, "none", 15,
                       tooltip="No background — white becomes transparent (Ctrl+Shift+B)")
        self._nbg_check.setCheckable(True)
        self._nbg_check.clicked.connect(self._toggle_transparent)
        self._grid_check = QPushButton("Grid")
        icons.set_icon(self._grid_check, "grid", 15,
                       tooltip="Pixel grid overlay (Ctrl+G)")
        self._grid_check.setCheckable(True)
        self._grid_check.setChecked(True)
        self._grid_check.clicked.connect(self._toggle_grid)
        for b in (self._bg_check, self._nbg_check, self._grid_check):
            b.setMinimumHeight(32)
            toggles.addWidget(b)
        view_card.body().addLayout(toggles)
        panel_lay.addWidget(view_card)

        # Document card
        doc_card = ShadowCard("Document")
        self._info_size = InfoChip("rect", "Size", "32×32")
        self._info_tool = InfoChip("pencil", "Tool", "Pencil")
        self._info_color = InfoChip("palette", "Color", "#F80000")
        self._info_pos = InfoChip("cursor", "Cursor", "0, 0")
        self._info_frames = InfoChip("frames", "Frames", "1")
        self._info_size.setToolTip("Canvas size in pixels — Resize Canvas (Ctrl+Alt+R)")
        self._info_tool.setToolTip("Active tool — B / E / G / L / U / R / I")
        self._info_color.setToolTip("Foreground RGB565 colour")
        self._info_pos.setToolTip("Pixel under the cursor")
        self._info_frames.setToolTip(
            "Animation frames — Space plays, , and . step, Ctrl+O onion skin")
        for w in (self._info_size, self._info_tool, self._info_color,
                  self._info_pos, self._info_frames):
            doc_card.body().addWidget(w)

        undo_row = QHBoxLayout()
        self._undo_btn = QPushButton("Undo")
        icons.set_icon(self._undo_btn, "undo", 15, tooltip="Undo last change (Ctrl+Z)")
        self._undo_btn.clicked.connect(self._undo)
        self._redo_btn = QPushButton("Redo")
        icons.set_icon(self._redo_btn, "redo", 15, tooltip="Redo (Ctrl+Shift+Z)")
        self._redo_btn.clicked.connect(self._redo)
        undo_row.addWidget(self._undo_btn)
        undo_row.addWidget(self._redo_btn)
        doc_card.body().addLayout(undo_row)
        panel_lay.addWidget(doc_card)

        # Actions card
        act_card = ShadowCard("Export")
        save_btn = AccentButton("Save .vpe")
        icons.set_icon(save_btn, "save", 15, token="on_accent",
                       tooltip="Save as a native .vpe asset (Ctrl+S)")
        save_btn.clicked.connect(self._save)
        export_bmp = QPushButton("Export BMP")
        icons.set_icon(export_bmp, "export", 15,
                       tooltip="Write an RGB565 BMP into the export folder")
        export_bmp.clicked.connect(self._export_bmp)
        export_png = QPushButton("Export PNG")
        icons.set_icon(export_png, "export", 15,
                       tooltip="Write a PNG (white = transparent in No BG mode)")
        export_png.clicked.connect(self._export_png)
        act_card.body().addWidget(save_btn)
        act_card.body().addWidget(export_bmp)
        act_card.body().addWidget(export_png)
        panel_lay.addWidget(act_card)

        panel_lay.addStretch()
        scroll.setWidget(panel)
        side_lay.addWidget(scroll)
        root.addWidget(side)

        # Status bar
        self._status = QStatusBar()
        self.setStatusBar(self._status)
        self._st_pos = QLabel("x: 0  y: 0")
        self._st_tool = QLabel("Pencil")
        self._st_zoom = QLabel("100%")
        self._st_color = GlyphLabel("palette", "muted")
        self._st_path = QLabel("Unsaved document")
        self._status.addWidget(self._st_pos)
        self._status.addWidget(self._st_tool)
        self._status.addWidget(self._st_zoom)
        self._status.addWidget(self._st_color)
        self._status.addPermanentWidget(self._st_path)
        for w, tip in (
            (self._st_pos, "Cursor pixel position"),
            (self._st_tool, "Active tool"),
            (self._st_zoom, "Zoom level"),
            (self._st_color, "Foreground colour (RGB565)"),
        ):
            w.setToolTip(tip)

        self.canvas.set_document(self._doc)
        self.timeline.set_document(self._doc)
        self._select_tool("pencil")

        # Restore last view (editor / gallery)
        if str(self._settings.value("view", "editor")) == "gallery":
            self._show_gallery()

    def _build_menus(self) -> None:
        mb = self.menuBar()

        file_m = mb.addMenu("&File")
        file_m.addAction(self._act("New…", QKeySequence.StandardKey.New, self._new, "new"))
        file_m.addAction(self._act("Open .vpe…", QKeySequence.StandardKey.Open, self._open, "open"))
        file_m.addAction(self._act("Asset collection…", "Ctrl+E", self._show_gallery, "gallery"))
        file_m.addAction(self._act("Import Image…", "Ctrl+I", self._import_image, "import"))
        file_m.addSeparator()
        file_m.addAction(self._act("Save", QKeySequence.StandardKey.Save, self._save, "save"))
        file_m.addAction(self._act("Save As…", QKeySequence.StandardKey.SaveAs, self._save_as, "save"))
        file_m.addSeparator()
        file_m.addAction(self._act("Export BMP…", "Ctrl+Shift+B", self._export_bmp, "export"))
        file_m.addAction(self._act("Export PNG…", "Ctrl+Shift+P", self._export_png, "export"))
        file_m.addSeparator()
        file_m.addAction(self._act("E&xit", QKeySequence.StandardKey.Quit, self.close, "close"))

        edit_m = mb.addMenu("&Edit")
        edit_m.addAction(self._act("Undo", QKeySequence.StandardKey.Undo, self._undo, "undo"))
        edit_m.addAction(self._act("Redo", QKeySequence.StandardKey.Redo, self._redo, "redo"))
        edit_m.addSeparator()
        edit_m.addAction(self._act("Clear Canvas", "Ctrl+Shift+Del", self._clear_canvas, "eraser"))
        edit_m.addAction(self._act("Resize Canvas…", "Ctrl+Alt+R", self._resize_canvas, "fit"))

        anim_m = mb.addMenu("&Animation")
        anim_m.addAction(self._act("Next Frame", ".", self._next_frame, "next_frame"))
        anim_m.addAction(self._act("Previous Frame", ",", self._prev_frame, "prev_frame"))
        play = self._act("Play / Pause", "", self._toggle_play, "play")
        play.setToolTip("Play / pause the animation (Space)")
        anim_m.addAction(play)
        anim_m.addSeparator()
        anim_m.addAction(self._act("Add Frame", "Ctrl+Alt+N", self._add_frame, "new"))
        anim_m.addAction(self._act("Duplicate Frame", "Ctrl+D", self._duplicate_frame, "duplicate"))
        anim_m.addAction(self._act("Delete Frame", "Ctrl+Shift+K", self._delete_frame, "delete"))
        anim_m.addAction(self._act("Move Frame Back", "Ctrl+Alt+Left", self._move_frame_back, "undo"))
        anim_m.addAction(self._act("Move Frame Forward", "Ctrl+Alt+Right", self._move_frame_fwd, "redo"))
        anim_m.addSeparator()
        onion = self._act("Onion Skin", "Ctrl+O", self._toggle_onion, "onion")
        onion.setToolTip("Ghost the neighbouring frames behind the one you edit (Ctrl+O)")
        anim_m.addAction(onion)
        anim_m.addAction(self._act(
            "Export PNG Strip…", "Ctrl+Alt+P", self._export_strip, "frames"))

        view_m = mb.addMenu("&View")
        view_m.addAction(self._act("Zoom In", QKeySequence.StandardKey.ZoomIn, self._zoom_in, "zoom_in"))
        view_m.addAction(self._act("Zoom Out", QKeySequence.StandardKey.ZoomOut, self._zoom_out, "zoom_out"))
        view_m.addAction(self._act("Fit to Window", "Ctrl+0", self._fit, "fit"))
        view_m.addSeparator()
        view_m.addAction(self._act("Asset collection (gallery)", "Ctrl+Shift+G", self._toggle_view, "gallery"))
        view_m.addAction(self._act("Toggle Background", "Ctrl+B", self._toggle_background, "eye"))
        view_m.addAction(self._act("No Background (transparent white)", "Ctrl+Shift+B", self._toggle_transparent, "none"))
        view_m.addAction(self._act("Toggle Grid", "Ctrl+G", self._toggle_grid, "grid"))
        view_m.addAction(self._act("Toggle Theme", "Ctrl+T", self._toggle_theme, "sun"))

        tools_m = mb.addMenu("&Tools")
        for key, icon_name, title, desc in TOOLS:
            act = QAction(f"{title} — {desc}", self)
            act.setIcon(icons.icon(icon_name, "text"))
            shortcut = title.split("(")[-1].rstrip(")") if "(" in title else ""
            if shortcut and len(shortcut) == 1:
                act.setShortcut(shortcut)
            act.triggered.connect(lambda _=False, k=key: self._select_tool(k))
            tools_m.addAction(act)

        help_m = mb.addMenu("&Help")
        help_m.addAction(self._act("Check Environment…", "", self._check_environment, "refresh"))
        help_m.addAction(self._act("About", QKeySequence.StandardKey.HelpContents, self._about, "settings"))

    def _act(self, text: str, shortcut, slot, icon_name: str = "") -> QAction:
        a = QAction(text, self)
        if icon_name:
            a.setIcon(icons.icon(icon_name, "text"))
        if shortcut:
            a.setShortcut(shortcut)
        seq = QKeySequence(shortcut).toString() if shortcut else ""
        title = text.replace("&", "")
        a.setToolTip(f"{title} ({seq})" if seq else title)
        a.triggered.connect(slot)
        return a

    def _build_shortcuts(self) -> None:
        # Extra numeric shortcuts for brush size
        for i in range(1, 6):
            act = QAction(self)
            act.setShortcut(str(i))
            act.triggered.connect(lambda _=False, n=i: self._size_sel.set_size(n))
            self.addAction(act)

    def _bind(self) -> None:
        self.canvas.cursor_moved.connect(self._on_cursor)
        self.canvas.pixel_picked.connect(self._on_picked)
        self.canvas.document_edited.connect(self._on_edited)
        self.canvas.zoom_changed.connect(self._on_zoom)
        self.timeline.frame_selected.connect(self._on_frame_selected)
        self.timeline.structure_changed.connect(self._on_frame_structure)
        self.timeline.onion_changed.connect(self._on_onion_changed)

    # ------------------------------------------------------------- theme
    def _apply_theme(self) -> None:
        app = QApplication.instance()
        if app:
            get_theme().apply_to_app(app)
        t = get_theme().tokens
        self._color_preview.update()
        self._bg_preview.update()
        if hasattr(self, "_palette"):
            self._palette._refresh_styles()
        if hasattr(self, "_size_sel"):
            self._size_sel.set_size(self._size_sel.size())
        # Refresh canvas checker
        self.canvas._checker = self.canvas._make_checker()
        self.canvas.refresh()
        self.timeline.rebuild()
        if hasattr(self, "_gallery"):
            self._gallery.apply_theme()

    def _on_theme_changed(self, name: str) -> None:
        self._apply_theme()
        self.statusBar().showMessage(f"Theme: {name.title()}", 2000)

    def _toggle_theme(self) -> None:
        self._theme_btn._on_click()

    # ------------------------------------------------------------ tools
    def _select_tool(self, key: str) -> None:
        self._current_tool = key
        btn = self._tool_buttons.get(key)
        if btn:
            btn.setChecked(True)
        for other in self._tool_buttons.values():
            other.set_active(other is btn)
        self._gallery_btn.set_active(self._views.currentIndex() == 1)
        self.canvas.set_tool(key)
        pretty = {
            "pencil": "Pencil", "eraser": "Eraser", "fill": "Fill",
            "line": "Line", "rect": "Rectangle", "rectfill": "Filled Rect",
            "pick": "Eyedropper",
        }.get(key, key)
        self._info_tool.set_value(pretty)
        self._st_tool.setText(pretty)
        if hasattr(self, "_views") and self._views.currentIndex() == 0:
            self._gallery_btn.setChecked(False)

    def _on_size_changed(self, size: int) -> None:
        self.canvas.set_brush_size(size)

    def _on_palette_color(self, c: int) -> None:
        self.canvas.set_color(c)
        self._color_preview.set_color(c)
        self._info_color.set_value(self._hex(c))
        self._st_color.setText(self._hex(c))

    def _pick_custom_color(self) -> None:
        c = pick_color(self, self.canvas.color())
        if c is not None:
            self.canvas.set_color(c)
            self._color_preview.set_color(c)
            self._palette.set_color_565(c)
            self._info_color.set_value(self._hex(c))
            self._st_color.setText(self._hex(c))

    def _swap_fg_bg(self) -> None:
        # Swap current color with background preview
        a = self.canvas.color()
        b = self._bg_preview.color()
        self.canvas.set_color(b)
        self._color_preview.set_color(b)
        self._bg_preview.set_color(a)

    def _toggle_grid(self, checked: Optional[bool] = None) -> None:
        if checked is None:
            checked = not self._grid_check.isChecked()
            self._grid_check.setChecked(checked)
        self.canvas.set_show_grid(bool(checked))

    def _toggle_background(self, checked: Optional[bool] = None) -> None:
        if checked is None:
            checked = not self._bg_check.isChecked()
            self._bg_check.setChecked(checked)
        self.canvas.set_show_background(bool(checked))

    def _toggle_transparent(self, checked: Optional[bool] = None) -> None:
        if checked is None:
            checked = not self._nbg_check.isChecked()
            self._nbg_check.setChecked(checked)
        self.canvas.set_transparent_white(bool(checked))
        # Keep the checker bed on so transparency is readable.
        if checked and not self._bg_check.isChecked():
            self._bg_check.setChecked(True)
            self.canvas.set_show_background(True)

    # ---------------------------------------------------------- cursor
    def _on_cursor(self, x: int, y: int) -> None:
        self._cursor_x, self._cursor_y = x, y
        self._st_pos.setText(f"x: {x}  y: {y}")
        self._info_pos.set_value(f"{x}, {y}")

    def _on_picked(self, color: int) -> None:
        self._color_preview.set_color(color)
        self.canvas.set_color(color)
        self._palette.set_color_565(color)
        self._info_color.set_value(self._hex(color))
        self._st_color.setText(self._hex(color))
        self.statusBar().showMessage(f"Picked {self._hex(color)}", 1500)

    def _on_edited(self) -> None:
        self._update_title()
        self._update_undo_state()
        self.timeline.refresh_thumbnails()

    # ---------------------------------------------------------- animation
    def _on_frame_selected(self, index: int) -> None:
        self.canvas.refresh()
        self.statusBar().showMessage(
            f"Frame {index + 1} / {self._doc.frame_count()}", 1200)
        self._update_frame_info()
        self._update_title()

    def _on_frame_structure(self) -> None:
        self.canvas.refresh()
        self._update_frame_info()
        self._update_title()
        self._update_undo_state()

    def _on_onion_changed(self, enabled: bool, back: int) -> None:
        self.canvas.set_onion_skin(enabled, back)

    def _next_frame(self) -> None:
        self.timeline.next_frame()

    def _prev_frame(self) -> None:
        self.timeline.prev_frame()

    def _toggle_play(self) -> None:
        self.timeline.toggle_play()

    def _add_frame(self) -> None:
        self.timeline.add_frame()

    def _duplicate_frame(self) -> None:
        self.timeline.duplicate_frame()

    def _delete_frame(self) -> None:
        self.timeline.delete_frame()

    def _move_frame_back(self) -> None:
        self.timeline.move_frame(-1)

    def _move_frame_fwd(self) -> None:
        self.timeline.move_frame(1)

    def _toggle_onion(self) -> None:
        self.timeline.toggle_onion()

    def _export_strip(self) -> None:
        doc = self._doc
        default = str(export_dir(True) / f"{doc.name or 'animation'}.png")
        path, _ = QFileDialog.getSaveFileName(
            self, "Export PNG Strip", default,
            "PNG Sprite Strip (*.png)",
        )
        if not path:
            return
        if not path.lower().endswith(".png"):
            path += ".png"
        try:
            save_png_strip(path, doc.width, doc.height, doc.frames)
            n = doc.frame_count()
            self.statusBar().showMessage(
                f"Exported strip {Path(path).name} — {doc.width * n}×{doc.height}, {n} frames",
                4000)
        except (OSError, VpeError) as exc:
            QMessageBox.critical(self, "Export failed", f"Could not export strip:\n{exc}")

    def _on_zoom(self, z: float) -> None:
        text = f"{z:.0f}x"
        self._zoom_label.setText(text)
        self._st_zoom.setText(text)

    def _zoom_in(self) -> None:
        self.canvas.zoom_in()

    def _zoom_out(self) -> None:
        self.canvas.zoom_out()

    def _fit(self) -> None:
        self.canvas.fit_to_view()

    # ------------------------------------------------------- views / gallery
    def _toggle_view(self) -> None:
        if self._views.currentIndex() == 0:
            self._show_gallery()
        else:
            self._show_editor()

    def _show_gallery(self) -> None:
        ensure_category_dirs()
        self._gallery.refresh()
        self._views.setCurrentIndex(1)
        self._gallery_btn.setChecked(True)
        self._gallery_btn.set_active(True)
        for other in self._tool_buttons.values():
            other.set_active(False)
        self.statusBar().showMessage("Asset collection — Documents\\VPE Pixel", 2500)

    def _show_editor(self) -> None:
        self._views.setCurrentIndex(0)
        self._gallery_btn.setChecked(False)
        self._gallery_btn.set_active(False)
        self._tool_buttons[self._current_tool].set_active(True)

    def _open_gallery_asset(self, path) -> None:
        """Open a .vpe from the gallery, or import an image into a canvas."""
        if not self._confirm_discard():
            return
        try:
            if path.suffix.lower() in (".vpe", ".vpea"):
                doc = self._load_doc(str(path))
                self._asset_category = asset_kind(path)
                self._set_doc(doc, str(path))
                self.statusBar().showMessage(f"Opened {path.name}", 3000)
            else:
                w, h, pixels = load_image_as_565(path)
                doc = Document.from_pixels(w, h, pixels, path.stem, None)
                self._asset_category = asset_kind(path)
                self._set_doc(doc, None)
                self.statusBar().showMessage(f"Imported {path.name} into canvas (unsaved)", 3000)
        except (OSError, VpeError) as exc:
            QMessageBox.critical(self, "Open failed", f"Could not open asset:\n{exc}")
            return
        self._show_editor()

    def _new_asset(self, category: str) -> None:
        if not self._confirm_discard():
            return
        dlg = NewAssetDialog(self, category)
        if dlg.exec() != NewAssetDialog.DialogCode.Accepted:
            return
        result = dlg.result_asset()
        if not result:
            return
        name, key, w, h, fill = result
        self._asset_category = key
        self._set_doc(Document.blank(w, h, fill, name), None)
        self._show_editor()
        self.statusBar().showMessage(
            f"New {key} '{name}' {w}×{h} — Ctrl+S saves into Documents\\VPE Pixel\\{key}", 5000)

    # ------------------------------------------------------- document
    def _set_doc(self, doc: Document, path: Optional[str] = None) -> None:
        self._doc = doc
        self._current_path = path
        self.timeline.set_document(doc)
        self.canvas.set_document(doc)
        self._info_size.set_value(f"{doc.width}×{doc.height}")
        self._update_title()
        self._update_frame_info()
        self._update_undo_state()
        self._st_path.setText(path or "Unsaved document")

    def _new(self) -> None:
        if not self._confirm_discard():
            return
        dlg = NewCanvasDialog(self, self._doc.width, self._doc.height)
        if dlg.exec() == NewCanvasDialog.DialogCode.Accepted:
            result = dlg.result_size()
            if result:
                w, h, fill = result
                self._set_doc(Document.blank(w, h, fill, "Untitled"), None)

    def _open(self) -> None:
        if not self._confirm_discard():
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "Open VPE Project", self._default_dir(),
            "VPE Files (*.vpe *.vpea);;Animation (*.vpea);;Still frame (*.vpe);;All Files (*)",
        )
        if not path:
            return
        try:
            self._set_doc(self._load_doc(path), path)
            self.statusBar().showMessage(f"Opened {Path(path).name}", 3000)
        except (OSError, VpeError) as exc:
            QMessageBox.critical(self, "Open failed", f"Could not open file:\n{exc}")

    def _load_doc(self, path: str) -> Document:
        """Dispatch on suffix: .vpea carries frames, .vpe is one still frame."""
        p = Path(path)
        if p.suffix.lower() == ".vpea":
            return Document.from_vpea_bytes(p.read_bytes(), p.stem, str(p))
        w, h, pixels = load_vpe(p)
        return Document.from_pixels(w, h, pixels, p.stem, str(p))

    def _import_image(self) -> None:
        if not self._confirm_discard():
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "Import Image", self._default_dir(),
            "Images (*.png *.jpg *.jpeg *.bmp);;All Files (*)",
        )
        if not path:
            return
        try:
            w, h, pixels = load_image_as_565(path)
            doc = Document.from_pixels(w, h, pixels, Path(path).stem, None)
            self._set_doc(doc, None)
            self.statusBar().showMessage(f"Imported {Path(path).name} as {w}×{h} RGB565", 3000)
        except (OSError, VpeError) as exc:
            QMessageBox.critical(self, "Import failed", f"Could not import image:\n{exc}")

    def _save(self) -> None:
        if self._current_path and not (
                self._doc.is_animated() and self._current_path.lower().endswith(".vpe")):
            self._write_vpe(self._current_path)
        else:
            if self._current_path:
                self.statusBar().showMessage(
                    "This canvas has several frames — .vpe stores one frame, "
                    "so choose a name for the .vpea animation", 4000)
            self._save_as()

    def _save_as(self) -> None:
        default_folder = self._gallery.current_folder() \
            if hasattr(self, "_gallery") else project_dir()
        animated = self._doc.is_animated()
        ext = ".vpea" if animated else ".vpe"
        path, selected = QFileDialog.getSaveFileName(
            self, "Save VPE Project",
            str(default_folder / f"untitled{ext}"),
            "VPE Files (*.vpe *.vpea);;Animation (*.vpea);;Still frame (*.vpe)",
        )
        if not path:
            return
        if not path.lower().endswith((".vpe", ".vpea")):
            path += selected_ext(selected, ext)
        self._write_vpe(path)

    def _write_vpe(self, path: str) -> None:
        try:
            p = Path(path)
            if p.suffix.lower() == ".vpea":
                p.write_bytes(self._doc.to_vpea_bytes())
                frames = self._doc.frame_count()
                note = f"{frames} frames · {self._doc.delay_ms} ms"
            else:
                # A .vpe holds one frame: whatever is on screen right now.
                save_vpe(path, self._doc.width, self._doc.height, self._doc.pixels)
                note = f"frame {self._doc.frame + 1}/{self._doc.frame_count()}" \
                    if self._doc.is_animated() else "1 frame"
            self._current_path = path
            self._doc.path = path
            self._doc.name = p.stem
            self._doc.dirty = False
            self._asset_category = asset_kind(p)
            self._st_path.setText(path)
            self._update_title()
            self._gallery.refresh()
            self.statusBar().showMessage(f"Saved {p.name} — {note}", 3000)
        except (OSError, VpeError) as exc:
            QMessageBox.critical(self, "Save failed", f"Could not save:\n{exc}")

    def _export_bmp(self) -> None:
        default = str(export_dir() / f"{self._doc.name or 'pixel_art'}.bmp")
        path, _ = QFileDialog.getSaveFileName(
            self, "Export BMP", default, "Bitmap (*.bmp)",
        )
        if not path:
            return
        if not path.lower().endswith(".bmp"):
            path += ".bmp"
        try:
            save_bmp(path, self._doc.width, self._doc.height, self._doc.pixels)
            self.statusBar().showMessage(f"Exported {Path(path).name}", 3000)
        except (OSError, VpeError) as exc:
            QMessageBox.critical(self, "Export failed", f"Could not export BMP:\n{exc}")

    def _export_png(self) -> None:
        default = str(export_dir() / f"{self._doc.name or 'pixel_art'}.png")
        path, _ = QFileDialog.getSaveFileName(
            self, "Export PNG", default, "PNG Image (*.png)",
        )
        if not path:
            return
        if not path.lower().endswith(".png"):
            path += ".png"
        try:
            save_png(path, self._doc.width, self._doc.height, self._doc.pixels)
            self.statusBar().showMessage(f"Exported {Path(path).name}", 3000)
        except (OSError, VpeError) as exc:
            QMessageBox.critical(self, "Export failed", f"Could not export PNG:\n{exc}")

    def _clear_canvas(self) -> None:
        if QMessageBox.question(
            self, "Clear Canvas", "Fill the canvas with white?"
        ) != QMessageBox.StandardButton.Yes:
            return
        self._doc.begin_stroke("Clear")
        for y in range(self._doc.height):
            for x in range(self._doc.width):
                self._doc.stroke_set(x, y, 0xFFFF)
        self._doc.end_stroke()
        self.canvas.refresh()
        self.timeline.refresh_thumbnails()
        self._update_title()

    def _resize_canvas(self) -> None:
        dlg = NewCanvasDialog(self, self._doc.width, self._doc.height)
        if dlg.exec() == NewCanvasDialog.DialogCode.Accepted:
            result = dlg.result_size()
            if result:
                w, h, fill = result
                self._doc.resize(w, h, fill)
                self.canvas.set_document(self._doc)
                self.timeline.rebuild()
                self._info_size.set_value(f"{w}×{h}")
                self._update_title()

    def _undo(self) -> None:
        if self._doc.undo():
            self.canvas.refresh()
            self.timeline.rebuild()
            self._update_frame_info()
            self._update_title()
            self._update_undo_state()

    def _redo(self) -> None:
        if self._doc.redo():
            self.canvas.refresh()
            self.timeline.rebuild()
            self._update_frame_info()
            self._update_title()
            self._update_undo_state()

    def _update_undo_state(self) -> None:
        self._undo_btn.setEnabled(self._doc.can_undo())
        self._redo_btn.setEnabled(self._doc.can_redo())

    def _update_title(self) -> None:
        mark = " *" if self._doc.dirty else ""
        self.setWindowTitle(f"{APP_NAME} — {self._doc.name}{mark}")
        self._doc_title.setText(f"{self._doc.name}{mark}")
        where = self._current_path or "not saved yet"
        extra = ""
        if self._doc.is_animated():
            extra = (f" · {self._doc.frame_count()} frames "
                     f"@ {self._doc.delay_ms} ms")
        self._doc_title.setToolTip(
            f"{self._doc.width}×{self._doc.height} RGB565{extra}\n{where}")
        self._st_path.setToolTip(where)

    def _update_status(self) -> None:
        self._info_size.set_value(f"{self._doc.width}×{self._doc.height}")
        self._info_color.set_value(self._hex(self.canvas.color()))
        self._st_color.setText(self._hex(self.canvas.color()))
        self._update_frame_info()

    def _update_frame_info(self) -> None:
        doc = self._doc
        n = doc.frame_count()
        self._info_frames.set_value(
            f"{doc.frame + 1}/{n} · {doc.delay_ms} ms" if n > 1 else "1")

    def _hex(self, c: int) -> str:
        r, g, b = c565_to_rgb(c)
        return f"#{r:02X}{g:02X}{b:02X}"

    def _default_dir(self) -> str:
        """Projects always live under Documents/VPE Pixel (exe + source)."""
        return str(project_dir(True))

    def _export_dir(self) -> str:
        return str(export_dir(True))

    def _confirm_discard(self) -> bool:
        if not self._doc.dirty:
            return True
        ret = QMessageBox.question(
            self,
            "Unsaved changes",
            "Discard unsaved changes to this canvas?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        return ret == QMessageBox.StandardButton.Yes

    def _about(self) -> None:
        AboutDialog(self).exec()

    def _check_environment(self) -> None:
        from . import bootstrap

        bootstrap.show_environment_dialog(self)

    # -------------------------------------------------------- window
    def _fade_step(self) -> None:
        op = self.windowOpacity()
        if op < self._fade_target - 0.02:
            self.setWindowOpacity(min(1.0, op + 0.08))
        else:
            self.setWindowOpacity(self._fade_target)
            self._fade.stop()

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._confirm_discard():
            self._settings.setValue("last_dir", self._default_dir())
            self._settings.setValue("theme", get_theme().name)
            self._settings.setValue("view", "gallery" if self._views.currentIndex() == 1 else "editor")
            self._settings.sync()
            event.accept()
        else:
            event.ignore()

    def keyPressEvent(self, event) -> None:
        if self._views.currentIndex() == 1:
            # Gallery page: keep theme/tool shortcuts out of the way of typing.
            mods = event.modifiers()
            if mods & Qt.KeyboardModifier.ControlModifier and \
                    event.key() == Qt.Key.Key_T:
                self._toggle_theme()
                return
            if mods & Qt.KeyboardModifier.ControlModifier and \
                    event.key() in (Qt.Key.Key_E, Qt.Key.Key_G):
                self._toggle_view()
                return
            super().keyPressEvent(event)
            return
        key = event.key()
        mods = event.modifiers()
        if key == Qt.Key.Key_BracketRight:
            self._size_sel.set_size(min(5, self._size_sel.size() + 1))
            return
        if key == Qt.Key.Key_BracketLeft:
            self._size_sel.set_size(max(1, self._size_sel.size() - 1))
            return
        if not (mods & Qt.KeyboardModifier.ControlModifier):
            if key == Qt.Key.Key_Space:
                self._toggle_play()
                return
            if key == Qt.Key.Key_Escape and self.timeline.playing():
                self.timeline.stop()
                return
            if key in (Qt.Key.Key_Comma, Qt.Key.Key_Period):
                if key == Qt.Key.Key_Comma:
                    self._prev_frame()
                else:
                    self._next_frame()
                return
        if key == Qt.Key.Key_Plus or key == Qt.Key.Key_Equal:
            self._zoom_in()
            return
        if key == Qt.Key.Key_Minus:
            self._zoom_out()
            return
        if key == Qt.Key.Key_Z and mods & Qt.KeyboardModifier.ControlModifier and \
                mods & Qt.KeyboardModifier.ShiftModifier:
            self._redo()
            return
        text = event.text().upper()
        if text in TOOL_KEYS and not (mods & Qt.KeyboardModifier.ControlModifier):
            self._select_tool(TOOL_KEYS[text])
            return
        super().keyPressEvent(event)
