"""Game asset collection — gallery of titlesets, sprites, textures and tiles.

Assets live under ``Documents\\VPE Pixel`` in per-category folders:

    titleset/   large screens / title sets (recommended 240x320)
    sprite/     character + item sprites  (recommended 16x16 .. 64x64)
    texture/    albedo / background / UI panels (recommended 64x64 .. 240x120)
    tile/       tilesets                  (recommended 16x16)

Each category may be grouped into sub-folders (``sprite/characters/player``,
``tile/topdown/terrain``, ``texture/background/parallax``); the nearest known
category ancestor decides the kind, so grouping never changes classification.
See ``docs/ASSET_TAXONOMY.md`` for the folder layout the sample library uses.

Anything saved straight into ``Documents\\VPE Pixel`` still shows up under the
*All* filter. ``.vpe`` files open in the editor, ``.vpea`` files open as
animations (their first frame is the preview); ``png/jpg/bmp`` are shown as
previews and imported into a RGB565 canvas on demand.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import List, Optional, Tuple

from PySide6.QtCore import Qt, QTimer, QSize, QPoint, Signal
from PySide6.QtGui import QColor, QImage, QPixmap
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QFrame, QLabel,
    QPushButton, QLineEdit, QScrollArea, QMenu, QFileDialog, QMessageBox,
    QSizePolicy, QGraphicsDropShadowEffect,
)

from . import icons
from .paths import project_dir
from .theme import get_theme
from .vpe import VpeError, c565_to_rgb, load_image_as_565, load_vpe, save_vpe
from .vpea import header_of, load_frame

CATEGORIES = [
    ("all", "All"),
    ("titleset", "Titleset"),
    ("sprite", "Sprite"),
    ("texture", "Texture"),
    ("tile", "Tile"),
]

CATEGORY_KEYS = [key for key, _ in CATEGORIES if key != "all"]

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".bmp"}
PROJECT_SUFFIXES = {".vpe", ".vpea"}
ASSET_SUFFIXES = PROJECT_SUFFIXES | IMAGE_SUFFIXES

THUMB_BOX = QSize(112, 84)


def read_pixels(path: Path) -> Tuple[int, int, List[int]]:
    """RGB565 buffer of a .vpe file, or the first frame of a .vpea animation."""
    if path.suffix.lower() == ".vpea":
        w, h, pixels = load_frame(path, 0)
        return w, h, pixels
    return load_vpe(path)


def asset_label(path: Path, kind: str) -> str:
    """Category chip text — animations also show their frame count."""
    label = kind.upper()
    if path.suffix.lower() == ".vpea":
        try:
            label = f"{label} · {header_of(path)[2]}F"
        except (OSError, VpeError):
            pass
    return label


def category_dir(key: str, create: bool = True) -> Path:
    """Documents\\VPE Pixel\\<category> folder."""
    root = project_dir(create=create) / key
    if create:
        try:
            root.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass
    return root


def ensure_category_dirs() -> None:
    for key in CATEGORY_KEYS:
        category_dir(key, create=True)


def asset_kind(path: Path) -> str:
    """Category of a file: its folder if known, else guessed from size."""
    for parent in path.parents:
        if parent.name in CATEGORY_KEYS:
            return parent.name
    return kind_from_dims(path)


def kind_from_dims(path: Path) -> str:
    try:
        if path.suffix.lower() in PROJECT_SUFFIXES:
            w, h, _ = read_pixels(path)
        else:
            pm = QPixmap(str(path))
            if pm.isNull():
                return "sprite"
            w, h = pm.width(), pm.height()
    except (OSError, VpeError):
        return "sprite"
    if w >= 128 and h >= 128:
        return "titleset"
    if max(w, h) >= 4 * min(w, h):
        return "texture"
    if w <= 24 and h <= 24:
        return "tile"
    return "sprite"


SKIP_DIRS = {"exports"}
# root -> category -> group -> sub-group, e.g. sprite/characters/player
MAX_SCAN_DEPTH = 4


def scan_assets() -> List[Path]:
    """All asset files under Documents\\VPE Pixel (category + project folders)."""
    ensure_category_dirs()
    root = project_dir()
    files, seen = [], set()

    def walk(folder: Path, depth: int) -> None:
        if depth > MAX_SCAN_DEPTH:
            return
        try:
            entries = sorted(folder.iterdir(), key=lambda p: p.name.lower())
        except OSError:
            return
        for p in entries:
            if p.name.startswith(".") or p in seen:
                continue
            if p.is_dir():
                if p.name.lower() in SKIP_DIRS:
                    continue
                walk(p, depth + 1)
            elif p.suffix.lower() in ASSET_SUFFIXES:
                seen.add(p)
                files.append(p)

    walk(root, 1)
    return files


def make_thumbnail(path: Path, kind: str = "") -> QPixmap:
    """Nearest-neighbour preview so pixel art stays crisp.

    For sprite/tile assets, RGB565 white is treated as transparent (the same
    convention the canvas "No BG" mode uses) so cards do not show white slabs.
    """
    transparent_white = kind in ("sprite", "tile")
    pixmap: Optional[QPixmap] = None
    try:
        if path.suffix.lower() in PROJECT_SUFFIXES:
            w, h, pixels = read_pixels(path)
            buf = bytearray(w * h * 4)
            for y in range(h):
                base = y * w
                row = y * w * 4
                for x in range(w):
                    src = pixels[base + x]
                    off = row + x * 4
                    if transparent_white and src == 0xFFFF:
                        buf[off] = buf[off + 1] = buf[off + 2] = buf[off + 3] = 0
                        continue
                    r, g, b = c565_to_rgb(src)
                    buf[off] = b
                    buf[off + 1] = g
                    buf[off + 2] = r
                    buf[off + 3] = 255
            img = QImage(bytes(buf), w, h, w * 4, QImage.Format_ARGB32)
            pixmap = QPixmap.fromImage(img.copy())
        else:
            loaded = QPixmap(str(path))
            if not loaded.isNull():
                pixmap = loaded
    except (OSError, VpeError):
        pixmap = None
    if pixmap is None:
        pm = QPixmap(THUMB_BOX)
        pm.fill(QColor(0, 0, 0, 0))
        return pm
    return pixmap.scaled(THUMB_BOX, Qt.AspectRatioMode.KeepAspectRatio,
                         Qt.TransformationMode.FastTransformation)


def unique_asset_path(folder: Path, stem: str, suffix: str) -> Path:
    suffix = suffix if suffix.startswith(".") else f".{suffix}"
    candidate = folder / f"{stem}{suffix}"
    n = 2
    while candidate.exists():
        candidate = folder / f"{stem} {n}{suffix}"
        n += 1
    return candidate


def reveal_in_explorer(path: Path) -> None:
    if not sys.platform.startswith("win"):
        return
    try:
        if path.is_file():
            subprocess.Popen(["explorer", "/select", str(path)])
        else:
            subprocess.Popen(["explorer", str(path)])
    except OSError:
        pass


class AssetCard(QFrame):
    """One gallery tile: preview, name, kind chip, click / context menu."""

    clicked = Signal(object)                # Path
    context_requested = Signal(object, object)  # Path, global QPoint

    def __init__(self, path: Path, kind: str, parent=None) -> None:
        super().__init__(parent)
        self.path = path
        self.kind = kind
        self.setObjectName("AssetCard")
        self.setToolTip(f"{path.stem} — {kind}\n{path}\nClick to open, right-click for actions")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(150, 138)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(4)

        self._thumb = QLabel()
        self._thumb.setObjectName("AssetThumb")
        self._thumb.setFixedSize(THUMB_BOX.width() + 14, THUMB_BOX.height() + 10)
        self._thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._thumb.setPixmap(make_thumbnail(path, kind))
        lay.addWidget(self._thumb, 0, Qt.AlignmentFlag.AlignCenter)

        self._name = QLabel(path.stem)
        self._name.setObjectName("AssetName")
        self._name.setFixedWidth(134)
        f = self._name.font()
        f.setPointSize(8)
        self._name.setFont(f)
        self._name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._name.setWordWrap(True)
        self._name.setMaximumHeight(28)
        lay.addWidget(self._name, 0, Qt.AlignmentFlag.AlignCenter)

        chip = QLabel(asset_label(path, kind))
        chip.setObjectName("AssetKind")
        chip.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ff = chip.font()
        ff.setPointSize(7)
        ff.setBold(True)
        chip.setFont(ff)
        lay.addWidget(chip)
        lay.addStretch()

        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(260)
        self._debounce.timeout.connect(lambda: self.clicked.emit(self.path))

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(event.pos()):
            self._debounce.start()
        super().mouseReleaseEvent(event)

    def contextMenuEvent(self, event) -> None:
        self.context_requested.emit(self.path, event.globalPos())
        event.accept()


class GalleryPanel(QWidget):
    """Scrollable collection grid with category filters and search."""

    open_requested = Signal(object)     # Path — open in editor
    create_requested = Signal(str)      # suggested category key
    imported = Signal(object)           # Path — image imported as .vpe

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._category = "all"
        self._search = ""
        self._paths: List[Path] = []
        self._kinds: dict = {}
        self._cards: List[AssetCard] = []
        self._filter_buttons = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 14)
        root.setSpacing(10)

        # --- header row ---
        header = QHBoxLayout()
        header.setSpacing(8)
        title = QLabel("Asset collection")
        title.setObjectName("Title")
        title.setStyleSheet("font-size: 16px; font-weight: 700;")
        header.addWidget(title)
        self._count_label = QLabel("0 items")
        self._count_label.setObjectName("Muted")
        header.addWidget(self._count_label)
        header.addStretch()

        self._search_edit = QLineEdit()
        self._search_edit.setPlaceholderText("Search assets…")
        self._search_edit.setFixedWidth(190)
        self._search_edit.setToolTip("Filter the grid by file name")
        self._search_edit.textChanged.connect(self._on_search)
        header.addWidget(self._search_edit)

        new_btn = QPushButton("New asset")
        new_btn.setObjectName("Primary")
        icons.set_icon(new_btn, "new", 15, token="on_accent", text="New asset",
                       tooltip="Create an asset in the selected category")
        new_btn.clicked.connect(
            lambda: self.create_requested.emit(
                self._category if self._category != "all" else "sprite"))
        header.addWidget(new_btn)

        import_btn = QPushButton("Import image")
        icons.set_icon(import_btn, "import", 15, text="Import image",
                       tooltip="Convert a PNG/JPG/BMP into a .vpe asset in this folder")
        import_btn.clicked.connect(self._import_image)
        header.addWidget(import_btn)

        folder_btn = QPushButton("Folder")
        folder_btn.setObjectName("Ghost")
        icons.set_icon(folder_btn, "library", 15, text="Folder",
                       tooltip=f"Open {project_dir(False)} in Explorer")
        folder_btn.clicked.connect(lambda: reveal_in_explorer(project_dir()))
        header.addWidget(folder_btn)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.setObjectName("Ghost")
        icons.set_icon(refresh_btn, "refresh", 15, text="Refresh",
                       tooltip="Rescan the asset folders")
        refresh_btn.clicked.connect(self.refresh)
        header.addWidget(refresh_btn)
        root.addLayout(header)

        # --- category chips ---
        chips = QHBoxLayout()
        chips.setSpacing(6)
        for key, label in CATEGORIES:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setToolTip(
                "Show every asset type" if key == "all"
                else f"Show only {label.lower()}s — {project_dir(False)}\\{key}")
            btn.setChecked(key == self._category)
            btn.clicked.connect(lambda _=False, k=key: self._select_category(k))
            self._filter_buttons[key] = btn
            chips.addWidget(btn)
        chips.addStretch()
        root.addLayout(chips)

        # --- grid ---
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._grid_host = QWidget()
        self._grid_lay = QGridLayout(self._grid_host)
        self._grid_lay.setContentsMargins(2, 6, 2, 6)
        self._grid_lay.setSpacing(12)
        self._grid_lay.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

        self._empty = QLabel(
            "No assets yet.\n"
            "Save a .vpe into Documents\\VPE Pixel\\titleset|sprite|texture|tile,\n"
            "or press “Import image” to convert a PNG/JPG/BMP."
        )
        self._empty.setObjectName("Muted")
        self._empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._grid_lay.addWidget(self._empty, 0, 0)
        self._scroll.setWidget(self._grid_host)
        root.addWidget(self._scroll, 1)

        self._scroll.verticalScrollBar().rangeChanged.connect(
            lambda _a, _b: self._relayout())

    # -------------------------------------------------------------- state
    def current_category(self) -> str:
        return self._category

    def current_folder(self) -> Path:
        """Where a newly saved asset should go for the current filter."""
        if self._category != "all":
            return category_dir(self._category)
        return project_dir()

    def _select_category(self, key: str) -> None:
        self._category = key
        for k, btn in self._filter_buttons.items():
            btn.setChecked(k == key)
            btn.setStyleSheet(self._chip_style(k == key))
        self._rebuild()

    def _on_search(self, text: str) -> None:
        self._search = text.strip().lower()
        self._rebuild()

    # ------------------------------------------------------------- refresh
    def refresh(self) -> None:
        self._paths = scan_assets()
        self._kinds = {p: asset_kind(p) for p in self._paths}
        self._rebuild()

    def _visible_paths(self) -> List[Path]:
        out = []
        for p in self._paths:
            if self._category != "all" and self._kinds.get(p) != self._category:
                continue
            if self._search and self._search not in p.name.lower():
                continue
            out.append(p)
        return out

    def _rebuild(self) -> None:
        for card in self._cards:
            card.setParent(None)
            card.deleteLater()
        self._cards.clear()

        paths = self._visible_paths()
        self._count_label.setText(f"{len(paths)} item{'s' if len(paths) != 1 else ''}")
        self._empty.setVisible(not paths)
        if not paths:
            self._grid_lay.addWidget(self._empty, 0, 0)
            return

        for i, path in enumerate(paths):
            card = AssetCard(path, self._kinds.get(path) or asset_kind(path))
            card.clicked.connect(self._on_card_clicked)
            card.context_requested.connect(self._show_context_menu)
            self._cards.append(card)
        self._relayout()

    def _relayout(self) -> None:
        count = len(self._cards)
        if not count:
            return
        cols = max(1, (self._scroll.viewport().width() - 8) // (150 + 12))
        for i, card in enumerate(self._cards):
            self._grid_lay.removeWidget(card)
            self._grid_lay.addWidget(card, i // cols, i % cols)
        self._grid_lay.setColumnStretch(cols, 1)

    def _chip_style(self, active: bool) -> str:
        t = get_theme().tokens
        if active:
            return (
                f"QPushButton {{ background: {t['accent']}; color: #FFFFFF;"
                " border: none; border-radius: 8px; padding: 6px 14px;"
                " font-weight: 700; font-size: 12px; }"
            )
        return (
            f"QPushButton {{ background: {t['surface2']}; color: {t['text']};"
            f" border: 1px solid {t['border']}; border-radius: 8px;"
            " padding: 6px 14px; font-weight: 600; font-size: 12px; }"
            f"QPushButton:hover {{ border-color: {t['accent']}; color: {t['accent']}; }}"
        )

    def apply_theme(self) -> None:
        for key, btn in self._filter_buttons.items():
            btn.setStyleSheet(self._chip_style(key == self._category))
        for card in self._cards:
            card._thumb.update()

    # ------------------------------------------------------------- actions
    def _on_card_clicked(self, path: Path) -> None:
        self.open_requested.emit(path)

    def _menu_action(self, menu: QMenu, text: str, icon_name: str, path: Path):
        act = menu.addAction(icons.icon(icon_name, "text"), text)
        act.setToolTip(f"{text} — {path.name}")
        return act

    def _show_context_menu(self, path: Path, point) -> None:
        menu = QMenu(self)
        open_act = self._menu_action(menu, "Open in editor", "open", path)
        dup_act = self._menu_action(menu, "Duplicate", "duplicate", path)
        move_act = self._menu_action(menu, "Move to category…", "move", path)
        rename_act = self._menu_action(menu, "Rename", "rename", path)
        reveal_act = self._menu_action(menu, "Reveal in Explorer", "reveal", path)
        menu.addSeparator()
        del_act = self._menu_action(menu, "Delete", "delete", path)
        del_act.setEnabled(sys.platform.startswith("win"))
        chosen = menu.exec(point)
        if chosen is None:
            return
        if chosen == open_act:
            self.open_requested.emit(path)
        elif chosen == dup_act:
            self._duplicate(path)
        elif chosen == move_act:
            self._move(path)
        elif chosen == rename_act:
            self._rename(path)
        elif chosen == reveal_act:
            reveal_in_explorer(path)
        elif chosen == del_act:
            self._delete(path)

    def _duplicate(self, path: Path) -> None:
        target = unique_asset_path(path.parent, f"{path.stem} copy", path.suffix)
        try:
            target.write_bytes(path.read_bytes())
        except OSError as exc:
            QMessageBox.critical(self, "Duplicate failed", str(exc))
            return
        self.refresh()

    def _move(self, path: Path) -> None:
        start = project_dir(False)
        folder = QFileDialog.getExistingDirectory(self, "Move asset into folder", str(start))
        if not folder:
            return
        dest = Path(folder) / path.name
        if dest.exists():
            dest = unique_asset_path(Path(folder), path.stem, path.suffix)
        try:
            shutil_move(path, dest)
        except OSError as exc:
            QMessageBox.critical(self, "Move failed", str(exc))
            return
        self.refresh()

    def _rename(self, path: Path) -> None:
        from PySide6.QtWidgets import QInputDialog
        stem, ok = QInputDialog.getText(self, "Rename asset", "New name",
                                        text=path.stem)
        if not ok or not stem.strip():
            return
        dest = path.with_name(f"{stem.strip()}{path.suffix}")
        if dest.exists():
            QMessageBox.warning(self, "Rename", "An asset with that name already exists.")
            return
        try:
            path.rename(dest)
        except OSError as exc:
            QMessageBox.critical(self, "Rename failed", str(exc))
            return
        self.refresh()

    def _delete(self, path: Path) -> None:
        if not recycle(path):
            QMessageBox.warning(self, "Delete", f"Could not move '{path.name}' to Recycle Bin.")
            return
        self.refresh()

    def _import_image(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Import image as asset", str(project_dir(False)),
            "Images (*.png *.jpg *.jpeg *.bmp);;All Files (*)",
        )
        if not path:
            return
        try:
            w, h, pixels = load_image_as_565(path)
            target = unique_asset_path(self.current_folder(), Path(path).stem, ".vpe")
            save_vpe(target, w, h, pixels)
        except (OSError, VpeError) as exc:
            QMessageBox.critical(self, "Import failed", f"Could not import image:\n{exc}")
            return
        self.refresh()
        self.imported.emit(target)


# ------------------------------------------------------------------ helpers
def shutil_move(src: Path, dest: Path) -> None:
    import shutil
    shutil.move(str(src), str(dest))


def recycle(path: Path) -> bool:
    """Move a file to the Windows Recycle Bin (undoable), else False."""
    if not sys.platform.startswith("win"):
        return False
    try:
        import ctypes

        class SHFILEOPSTRUCTW(ctypes.Structure):
            _fields_ = [
                ("hwnd", ctypes.c_void_p),
                ("wFunc", ctypes.c_uint),
                ("pFrom", ctypes.c_wchar_p),
                ("pTo", ctypes.c_wchar_p),
                ("fFlags", ctypes.c_uint16),
                ("fAnyOperationsAbandoned", ctypes.c_bool),
                ("hNameMappings", ctypes.c_void_p),
                ("lpszProgressTitle", ctypes.c_wchar_p),
            ]

        op = SHFILEOPSTRUCTW()
        op.wFunc = 3  # FO_DELETE
        op.pFrom = str(path) + "\0\0"
        op.fFlags = 0x0004 | 0x0010 | 0x0040 | 0x0400  # SILENT|NOCONFIRMATION|ALLOWUNDO|NOERRORUI
        result = ctypes.windll.shell32.SHFileOperationW(ctypes.byref(op))
        return result == 0 and not path.exists()
    except Exception:
        return False
