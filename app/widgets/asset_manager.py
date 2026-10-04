"""Project-aware Assets tree with folder-owned action menus.

Each managed folder under ``assets`` has its own three-dot button. Imports are
therefore bound to a fixed VXP project destination, while arbitrary folder/file
creation remains unavailable so the generated codebase stays predictable.
"""
from __future__ import annotations

import os
import re
import shutil
from pathlib import Path

from file_utils import unique_destination

from PySide6.QtCore import (
    QFileSystemWatcher,
    QMimeData,
    QPoint,
    QPointF,
    QRectF,
    QSize,
    Qt,
    QTimer,
    QUrl,
    Signal,
)
from PySide6.QtGui import QAction, QColor, QDrag, QImage, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QPushButton,
    QToolButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .custom_dialog import CustomDialog, FilePickerDialog
from .icons import icon
from .panel_frame import PanelFrame


IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif", ".svg"}
AUDIO_EXTENSIONS = {".wav", ".ogg", ".mp3", ".flac", ".m4a"}
FONT_EXTENSIONS = {".ttf", ".otf", ".fnt"}
SHADER_EXTENSIONS = {".vert", ".frag", ".glsl"}
DATA_EXTENSIONS = {".json", ".xml", ".yaml", ".yml", ".csv", ".properties", ".atlas"}
NATIVE_EXTENSIONS = {".c", ".cc", ".cpp", ".cxx", ".h", ".hh", ".hpp"}
TEXT_EXTENSIONS = {
    ".c", ".cc", ".cpp", ".cxx", ".h", ".hh", ".hpp",
    ".json", ".dtfe", ".nova", ".xml", ".properties", ".md", ".txt",
    ".vert", ".frag", ".glsl", ".yaml", ".yml", ".csv", ".cmake", ".sh", ".bat",
}
IGNORED_DIRECTORIES = {
    ".git", ".idea", ".vscode", "build", "out", "bin",
    "build-win32", "build-arm", "build-arm-signed", "__pycache__",
}
INVALID_WINDOWS_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}


def _is_inside(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except (OSError, ValueError):
        return False


def _safe_relative(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except (OSError, ValueError):
        return str(path)


def _validate_entry_name(name: str, *, require_extension: bool = False) -> str:
    value = name.strip()
    if not value:
        raise ValueError("Vui lòng nhập tên.")
    if value in {".", ".."} or "/" in value or "\\" in value:
        raise ValueError("Tên chỉ được chứa một cấp, không nhập đường dẫn con.")
    if re.search(r'[<>:"|?*\x00-\x1F]', value):
        raise ValueError('Tên chứa ký tự Windows không hợp lệ: < > : " | ? *')
    if value.rstrip(". ") != value:
        raise ValueError("Tên không được kết thúc bằng dấu chấm hoặc khoảng trắng.")
    if value.split(".", 1)[0].upper() in INVALID_WINDOWS_NAMES:
        raise ValueError("Tên này được Windows dành riêng.")
    if require_extension and not Path(value).suffix:
        raise ValueError("Tên tệp cần có phần mở rộng, ví dụ player.c hoặc level.json.")
    return value


def _path_icon(path: Path) -> tuple[str, str]:
    if path.is_dir():
        return "fa5s.folder", "#72A8FF"
    suffix = path.suffix.lower()
    if suffix in NATIVE_EXTENSIONS:
        return "fa5s.microchip", "#B59CFF"
    if suffix in IMAGE_EXTENSIONS:
        return "fa5s.image", "#78D6A3"
    if suffix in AUDIO_EXTENSIONS:
        return "fa5s.music", "#C88EFF"
    if suffix in FONT_EXTENSIONS:
        return "fa5s.font", "#F4C35D"
    if suffix in SHADER_EXTENSIONS:
        return "fa5s.magic", "#77C7FF"
    if suffix in {".dtfe", ".nova", ".json"}:
        return "fa5s.cube", "#AF8AFF"
    if path.name.lower() in {"cmakelists.txt", "cmakepresets.json"} or suffix == ".cmake":
        return "fa5s.cogs", "#A4B6CA"
    if suffix in {".xml", ".properties", ".md", ".txt", ".yaml", ".yml", ".sh", ".bat"}:
        return "fa5s.file-code", "#A4B6CA"
    return "fa5s.file", "#8FA0B8"


def _recommended_destinations(project_root: Path, package_name: str) -> list[tuple[str, str]]:
    options = [
        ("Audio / music / SFX", "assets/audio"),
        ("Fonts", "assets/fonts"),
        ("Scene / animation", "assets/scenes"),
        ("Map / backgrounds", "assets/map/background"),
        ("Map / skills", "assets/map/skill"),
        ("Map / textures", "assets/map/texture"),
        ("Map / tilesets", "assets/map/tileset"),
        ("Game / app icons", "assets/app-icon"),
        ("Ảnh nền / title", "assets/backgrounds"),
        ("UI mockup", "assets/ui"),
        ("Mã nguồn C (src)", "src"),
        ("Bản đồ chữ (maps)", "maps"),
        ("Sprite đóng gói (resources)", "resources/gen"),
    ]
    return [(label, relative) for label, relative in options]


def _suggest_destination(paths: list[Path]) -> str:
    suffixes = {path.suffix.lower() for path in paths}
    if suffixes and suffixes <= IMAGE_EXTENSIONS:
        return "assets/map/texture"
    if suffixes and suffixes <= AUDIO_EXTENSIONS:
        return "assets/audio"
    if suffixes and suffixes <= FONT_EXTENSIONS:
        return "assets/fonts"
    if suffixes and suffixes <= NATIVE_EXTENSIONS:
        return "src"
    return "assets/map/texture"


class AssetTreeWidget(QTreeWidget):
    """Assets tree that exports file URLs for drag/drop into the 2D viewport."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setDragEnabled(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.DragOnly)
        self.setDefaultDropAction(Qt.DropAction.CopyAction)

    def startDrag(self, supported_actions) -> None:  # noqa: N802 - Qt API
        paths: list[Path] = []
        for item in self.selectedItems():
            value = item.data(0, Qt.ItemDataRole.UserRole)
            if not value:
                continue
            path = Path(str(value))
            if path.is_file():
                paths.append(path)
        if not paths:
            return
        mime = QMimeData()
        mime.setUrls([QUrl.fromLocalFile(str(path)) for path in paths])
        mime.setData(
            "application/x-vxp-asset",
            "\n".join(str(path) for path in paths).encode("utf-8"),
        )
        drag = QDrag(self)
        drag.setMimeData(mime)
        icon_name, color = _path_icon(paths[0])
        drag.setPixmap(icon(icon_name, color).pixmap(28, 28))
        drag.exec(Qt.DropAction.CopyAction)


class AssetDestinationDialog(CustomDialog):
    """Select a project-relative destination and optionally a new entry name."""

    def __init__(
        self,
        project_root: Path,
        package_name: str,
        title: str,
        description: str,
        suggested_relative: str,
        *,
        name_label: str | None = None,
        name_placeholder: str = "",
        require_extension: bool = False,
        parent=None,
    ) -> None:
        super().__init__(title, parent=parent, width=620)
        self.project_root = project_root.resolve()
        self.require_extension = require_extension

        intro = QLabel(description)
        intro.setObjectName("DialogDescription")
        intro.setWordWrap(True)
        self.add_body_widget(intro)

        label = QLabel("Vị trí lưu theo codebase")
        label.setProperty("class", "PropName")
        self.add_body_widget(label)

        self.destination_combo = QComboBox()
        for option_label, relative in _recommended_destinations(self.project_root, package_name):
            self.destination_combo.addItem(option_label, relative)
        self.add_body_widget(self.destination_combo)

        self.relative_path = QLineEdit()
        self.relative_path.setPlaceholderText("assets/map/texture")
        self.relative_path.setReadOnly(True)
        self.relative_path.setToolTip("Đường dẫn được khóa theo cấu trúc codebase chuẩn.")
        self.add_body_widget(self.relative_path)

        self.absolute_preview = QLabel()
        self.absolute_preview.setObjectName("ProjectPathPreview")
        self.absolute_preview.setWordWrap(True)
        self.add_body_widget(self.absolute_preview)

        self.name_edit: QLineEdit | None = None
        if name_label:
            entry_label = QLabel(name_label)
            entry_label.setProperty("class", "PropName")
            self.name_edit = QLineEdit()
            self.name_edit.setPlaceholderText(name_placeholder)
            self.name_edit.setClearButtonEnabled(True)
            self.add_body_widget(entry_label)
            self.add_body_widget(self.name_edit)

        self.error_label = QLabel()
        self.error_label.setObjectName("InlineError")
        self.error_label.setWordWrap(True)
        self.error_label.hide()
        self.add_body_widget(self.error_label)

        cancel = self.add_footer_button("Hủy", ghost=True, icon_name="fa5s.times")
        confirm_text = "Tạo" if name_label else "Chọn vị trí"
        confirm = self.add_footer_button(confirm_text, accent=True, icon_name="fa5s.check")
        cancel.clicked.connect(self.reject)
        confirm.clicked.connect(self._submit)

        self.destination_combo.currentIndexChanged.connect(self._combo_changed)
        self.relative_path.textChanged.connect(self._update_preview)
        if self.name_edit is not None:
            self.name_edit.returnPressed.connect(self._submit)

        index = self.destination_combo.findData(suggested_relative)
        if index < 0:
            index = self.destination_combo.findData("assets/map/texture")
        self.destination_combo.setCurrentIndex(max(0, index))
        if index < 0:
            self.relative_path.setText(suggested_relative)
        self._combo_changed()

    @property
    def destination_directory(self) -> Path:
        relative = self.relative_path.text().strip().replace("\\", "/") or "."
        return (self.project_root / relative).resolve()

    @property
    def entry_name(self) -> str:
        return self.name_edit.text().strip() if self.name_edit is not None else ""

    def _combo_changed(self) -> None:
        value = self.destination_combo.currentData()
        if value is not None:
            self.relative_path.setText(str(value))

    def _browse(self) -> None:
        start = self.destination_directory if _is_inside(self.destination_directory, self.project_root) else self.project_root
        selected = FilePickerDialog.get_existing_directory(
            self,
            "Chọn thư mục bên trong dự án",
            str(start),
        )
        if not selected:
            return
        selected_path = Path(selected).resolve()
        if not _is_inside(selected_path, self.project_root):
            self._show_error("Chỉ được chọn thư mục nằm bên trong dự án hiện tại.")
            return
        self.relative_path.setText(_safe_relative(selected_path, self.project_root))

    def _update_preview(self) -> None:
        destination = self.destination_directory
        self.absolute_preview.setText(
            f"project://{_safe_relative(destination, self.project_root)}\n{destination}"
        )
        self.error_label.hide()

    def _show_error(self, message: str) -> None:
        self.error_label.setText(message)
        self.error_label.show()

    def _submit(self) -> None:
        destination = self.destination_directory
        if not _is_inside(destination, self.project_root):
            self._show_error("Đường dẫn lưu phải nằm trong codebase của dự án.")
            return
        try:
            if self.name_edit is not None:
                _validate_entry_name(self.entry_name, require_extension=self.require_extension)
            destination.mkdir(parents=True, exist_ok=True)
        except (OSError, ValueError) as error:
            self._show_error(str(error))
            return
        self.accept()


class AssetsPanel(PanelFrame):
    """Filesystem-backed project tree with actions attached to asset folders.

    The panel header intentionally has no global three-dot menu. Every managed
    folder inside ``assets`` owns its own compact ellipsis button, so import and
    Editor Assets operations always know the exact codebase destination.
    """

    file_open_requested = Signal(str)
    asset_editor_requested = Signal(str, str)  # initial image, destination folder
    status_message = Signal(str)
    error_message = Signal(str)
    asset_insert_requested = Signal(str)

    ASSET_FOLDERS = (
        "assets/audio",
        "assets/fonts",
        "assets/scenes",
        "assets/map",
        "assets/map/background",
        "assets/map/skill",
        "assets/map/texture",
        "assets/map/tileset",
        "assets/app-icon",
    )
    IMAGE_EDITOR_FOLDERS = {
        "assets/scenes",
        "assets/map",
        "assets/map/background",
        "assets/map/skill",
        "assets/map/texture",
        "assets/map/tileset",
        "assets/app-icon",
    }

    # Tự động làm mới khi tài nguyên được thêm/xoá ngoài IDE (Explorer, git…).
    WATCH_DEBOUNCE_MS = 500
    WATCH_MAX_DIRS = 200
    WATCH_MAX_DEPTH = 6

    def __init__(self, project_path: str, package_name: str, parent=None) -> None:
        super().__init__("Assets", parent=parent)
        self.project_root = Path(project_path).resolve()
        self.package_name = package_name
        self._item_limit = 3000
        self._item_count = 0
        self._auto_refresh = True
        self._watcher = QFileSystemWatcher(self)
        self._watcher.directoryChanged.connect(self._on_watched_change)
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setSingleShot(True)
        self._refresh_timer.setInterval(self.WATCH_DEBOUNCE_MS)
        self._refresh_timer.timeout.connect(self._run_debounced_refresh)
        # Giữ tham chiếu Python của các item trong lúc dựng cây: QTreeWidgetItem
        # không phải QObject, nếu không giữ tham chiếu thì GC có thể thu hồi item
        # khi cây lớn và gây access violation lúc refresh.
        self._items_keep: list = []
        self._ensure_asset_layout()

        # Remove the old panel-level ellipsis. Folder rows now own the actions.
        if self.menu_button is not None:
            self.menu_button.hide()

        self.search = QLineEdit()
        self.search.setObjectName("SearchBox")
        self.search.setPlaceholderText("Tìm tài nguyên hoặc mã nguồn...")
        self.search.addAction(icon("fa5s.search", "#718096"), QLineEdit.ActionPosition.LeadingPosition)
        self.search.textChanged.connect(self._apply_filter)
        self.add_widget(self.search)

        self.tree = AssetTreeWidget()
        self.tree.setColumnCount(2)
        self.tree.setHeaderHidden(True)
        self.tree.setIndentation(14)
        self.tree.setAnimated(False)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._show_context_menu)
        self.tree.itemClicked.connect(self._on_item_clicked)
        self.tree.itemDoubleClicked.connect(self._activate_item)
        header = self.tree.header()
        from PySide6.QtWidgets import QHeaderView
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(1, 34)
        self.add_widget(self.tree)
        self.refresh()
        self._install_watcher()

    # ------------------------------------------------- tự động làm mới Assets

    def _install_watcher(self) -> None:
        """Theo dõi assets/ (đệ quy) để nhận tài nguyên mới thêm ngoài IDE."""
        if not self._auto_refresh:
            return
        self._watcher.blockSignals(True)
        watched = set(self._watcher.directories())
        for path in self._watch_candidates():
            key = str(path)
            if key not in watched:
                self._watcher.addPath(key)
        self._watcher.blockSignals(False)

    def _watch_candidates(self) -> list[Path]:
        roots = [self.project_root / "assets"]
        # Một số project để tài nguyên ở thư mục gốc dự án (maps/, resources/).
        for name in ("maps", "resources", "src"):
            candidate = self.project_root / name
            if candidate.is_dir():
                roots.append(candidate)
        found: list[Path] = []
        for root in roots:
            if not root.is_dir():
                continue
            found.append(root)
            stack = [(root, 0)]
            while stack and len(found) < self.WATCH_MAX_DIRS:
                directory, depth = stack.pop()
                if depth >= self.WATCH_MAX_DEPTH:
                    continue
                try:
                    children = sorted(directory.iterdir(), key=lambda p: p.name.lower())
                except OSError:
                    continue
                for child in children:
                    if not child.is_dir() or len(found) >= self.WATCH_MAX_DIRS:
                        continue
                    found.append(child)
                    stack.append((child, depth + 1))
        return found

    def _on_watched_change(self, _path: str = "") -> None:
        # Gộp các thay đổi dồn dập (copy nhiều tệp) thành một lần làm mới.
        self._refresh_timer.start()

    def _run_debounced_refresh(self) -> None:
        if not self._auto_refresh:
            return
        self.refresh()
        # Thư mục mới có thể vừa xuất hiện → đăng ký theo dõi lại.
        self._install_watcher()
        self.status_message.emit("[Assets] Đã làm mới tài nguyên thư mục Assets.")

    def set_auto_refresh(self, enabled: bool) -> None:
        self._auto_refresh = bool(enabled)
        if enabled:
            self._install_watcher()
        else:
            self._refresh_timer.stop()
            paths = self._watcher.directories()
            if paths:
                self._watcher.removePaths(paths)

    def refresh_now(self) -> None:
        """Làm mới ngay, bỏ qua debounce (dùng cho action thủ công)."""
        self._refresh_timer.stop()
        self.refresh()
        self._install_watcher()

    def _ensure_asset_layout(self) -> None:
        for relative in self.ASSET_FOLDERS:
            (self.project_root / relative).mkdir(parents=True, exist_ok=True)

    def refresh(self, select_path: Path | None = None) -> None:
        self.tree.blockSignals(True)
        self.tree.setUpdatesEnabled(False)
        building: list = []
        try:
            self.tree.clear()
            self._item_count = 0
            self._items_keep = building
            root_item = self._new_item("project://", self.project_root, "fa5s.folder-open", "#72A8FF")
            building.append(root_item)
            self.tree.addTopLevelItem(root_item)

            ordered_names = [
                "assets", "src", "maps", "data", "engine",
                "resources", "cmake", "common", "mreapi", "docs",
            ]
            paths: list[Path] = []
            for name in ordered_names:
                path = self.project_root / name
                if path.exists():
                    paths.append(path)
            paths.extend(
                path for path in sorted(self.project_root.iterdir(), key=lambda p: p.name.lower())
                if path.name not in ordered_names and path.name not in IGNORED_DIRECTORIES
            )

            for path in paths:
                self._append_path(root_item, path, depth=0)
                if self._item_count >= self._item_limit:
                    break

            root_item.setExpanded(True)
            self._expand_primary_roots(root_item)
        finally:
            self.tree.blockSignals(False)
            self.tree.setUpdatesEnabled(True)
        # Selection/scrolling must happen only after QTreeWidget has finished
        # replacing its item widgets. Doing this inside the rebuild caused a
        # native Qt access violation after Asset Editor's Apply action.
        self._apply_filter(self.search.text())
        if select_path is not None:
            self._select_path(select_path)

    def _append_path(self, parent: QTreeWidgetItem, path: Path, depth: int) -> None:
        if self._item_count >= self._item_limit or path.name in IGNORED_DIRECTORIES:
            return
        icon_name, color = _path_icon(path)
        item = self._new_item(path.name, path, icon_name, color)
        self._items_keep.append(item)
        parent.addChild(item)
        self._item_count += 1
        if path.is_dir() and self._is_asset_folder(path):
            self._attach_folder_menu(item, path)
        if not path.is_dir() or depth >= 12:
            return
        try:
            children = sorted(path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
        except OSError:
            return
        for child in children:
            self._append_path(item, child, depth + 1)
            if self._item_count >= self._item_limit:
                break

    def _new_item(self, text: str, path: Path, icon_name: str, color: str) -> QTreeWidgetItem:
        item = QTreeWidgetItem([text, ""])
        item.setIcon(0, icon(icon_name, color))
        item.setData(0, Qt.ItemDataRole.UserRole, str(path))
        flags = item.flags()
        if path.is_file():
            item.setFlags(flags | Qt.ItemFlag.ItemIsDragEnabled)
        else:
            item.setFlags(flags & ~Qt.ItemFlag.ItemIsDragEnabled)
        relative = _safe_relative(path, self.project_root)
        item.setToolTip(0, f"project://{relative}" if relative != "." else "project://")
        return item

    def _is_asset_folder(self, path: Path) -> bool:
        if not path.is_dir():
            return False
        try:
            relative = path.resolve().relative_to(self.project_root).as_posix()
        except ValueError:
            return False
        return relative == "assets" or relative.startswith("assets/")

    def _folder_relative(self, path: Path) -> str:
        try:
            return path.resolve().relative_to(self.project_root).as_posix()
        except ValueError:
            return "assets"

    def _attach_folder_menu(self, item: QTreeWidgetItem, path: Path) -> None:
        # A dedicated second column plus a right-aligned wrapper keeps every
        # folder menu pinned to the far-right edge, independent of tree depth.
        cell = QWidget(self.tree)
        cell.setObjectName("AssetFolderMenuCell")
        cell_layout = QHBoxLayout(cell)
        cell_layout.setContentsMargins(0, 0, 3, 0)
        cell_layout.setSpacing(0)
        cell_layout.addStretch(1)

        button = QToolButton(cell)
        button.setObjectName("AssetFolderMenuButton")
        button.setIcon(icon("fa5s.ellipsis-v"))
        button.setIconSize(QSize(12, 12))
        button.setFixedSize(25, 23)
        button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        button.setToolTip(f"Tùy chọn {self._folder_relative(path)}")
        button.setMenu(self._make_folder_menu(path, button))
        cell_layout.addWidget(button, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.tree.setItemWidget(item, 1, cell)

    def _make_folder_menu(self, folder: Path, parent=None) -> QMenu:
        relative = self._folder_relative(folder)
        menu = QMenu(parent or self)

        if relative in self.IMAGE_EDITOR_FOLDERS or relative.startswith("assets/map/"):
            destination = "assets/map/texture" if relative == "assets/map" else relative
            new_action = QAction(icon("fa5s.magic"), "Mở Editor Assets trống…", menu)
            new_action.triggered.connect(
                lambda _checked=False, target=destination: self.asset_editor_requested.emit("", target)
            )
            import_action = QAction(icon("fa5s.file-image"), "Nhập ảnh vào Editor Assets…", menu)
            import_action.triggered.connect(
                lambda _checked=False, target=destination: self._import_image_to_editor(target)
            )
            menu.addAction(new_action)
            menu.addAction(import_action)

        elif relative == "assets/audio":
            action = QAction(icon("fa5s.music"), "Nhập âm thanh…", menu)
            action.triggered.connect(
                lambda: self._copy_files_to_folder(folder, "Âm thanh (*.wav *.ogg *.mp3 *.flac *.m4a);;Tất cả tệp (*.*)")
            )
            menu.addAction(action)

        elif relative == "assets/fonts":
            action = QAction(icon("fa5s.font"), "Nhập font…", menu)
            action.triggered.connect(
                lambda: self._copy_files_to_folder(folder, "Font (*.ttf *.otf *.fnt);;Tất cả tệp (*.*)")
            )
            menu.addAction(action)

        elif relative == "assets":
            hint = QAction(icon("fa5s.info-circle"), "Chọn thư mục con để nhập tài nguyên", menu)
            hint.setEnabled(False)
            menu.addAction(hint)

        else:
            generic = QAction(icon("fa5s.file-import"), "Nhập tệp vào thư mục này…", menu)
            generic.triggered.connect(lambda: self._copy_files_to_folder(folder, "Tất cả tệp (*.*)"))
            menu.addAction(generic)

        if relative == "assets/scenes":
            descriptor = QAction(icon("fa5s.file-code"), "Nhập Scene/Animation .dtfe…", menu)
            descriptor.triggered.connect(
                lambda: self._copy_files_to_folder(folder, "VXPEngine (*.dtfe);;Tất cả tệp (*.*)")
            )
            menu.addAction(descriptor)

        menu.addSeparator()
        refresh_action = QAction(icon("fa5s.sync-alt"), "Làm mới", menu)
        refresh_action.triggered.connect(lambda: self.refresh())
        reveal_action = QAction(icon("fa5s.folder-open"), "Mở trong File Explorer", menu)
        reveal_action.triggered.connect(lambda: self._reveal_path(folder))
        menu.addAction(refresh_action)
        menu.addAction(reveal_action)
        return menu

    @staticmethod
    def _expand_primary_roots(root_item: QTreeWidgetItem) -> None:
        for index in range(root_item.childCount()):
            child = root_item.child(index)
            if child.text(0) in {"assets", "src", "maps", "engine"}:
                child.setExpanded(True)
                if child.text(0) == "assets":
                    for child_index in range(child.childCount()):
                        child.child(child_index).setExpanded(True)

    def _select_path(self, target: Path) -> None:
        normalized = os.path.normcase(str(target.resolve()))
        iterator = self.tree.invisibleRootItem()
        stack = [iterator.child(i) for i in range(iterator.childCount())]
        while stack:
            item = stack.pop()
            item_path = item.data(0, Qt.ItemDataRole.UserRole)
            if item_path and os.path.normcase(str(Path(item_path).resolve())) == normalized:
                self.tree.setCurrentItem(item)
                self.tree.scrollToItem(item)
                parent = item.parent()
                while parent is not None:
                    parent.setExpanded(True)
                    parent = parent.parent()
                return
            stack.extend(item.child(i) for i in range(item.childCount()))

    def _apply_filter(self, text: str) -> None:
        query = text.strip().lower()
        root = self.tree.invisibleRootItem()
        for index in range(root.childCount()):
            self._filter_item(root.child(index), query)

    def _filter_item(self, item: QTreeWidgetItem, query: str) -> bool:
        child_visible = False
        for index in range(item.childCount()):
            child_visible = self._filter_item(item.child(index), query) or child_visible
        own_match = not query or query in item.text(0).lower() or query in item.toolTip(0).lower()
        visible = own_match or child_visible
        item.setHidden(not visible)
        if query and child_visible:
            item.setExpanded(True)
        return visible

    def _on_item_clicked(self, item: QTreeWidgetItem, _column: int = 0) -> None:
        """Kiểu VSCode: bấm một lần vào thư mục = mở/đóng, vào tệp = mở tab."""
        value = item.data(0, Qt.ItemDataRole.UserRole)
        if not value:
            return
        path = Path(value)
        if path.is_dir():
            item.setExpanded(not item.isExpanded())
        elif path.exists():
            self.file_open_requested.emit(str(path))

    def _activate_item(self, item: QTreeWidgetItem) -> None:
        value = item.data(0, Qt.ItemDataRole.UserRole)
        if not value:
            return
        path = Path(value)
        if path.is_dir():
            return  # nhấp đơn đã đóng/mở thư mục như VSCode
        if path.exists():
            self.file_open_requested.emit(str(path))

    def _show_context_menu(self, position: QPoint) -> None:
        item = self.tree.itemAt(position)
        if item is None:
            return
        value = item.data(0, Qt.ItemDataRole.UserRole)
        path = Path(value) if value else None
        if path is None or not path.exists():
            return

        if path.is_dir() and self._is_asset_folder(path):
            menu = self._make_folder_menu(path, self.tree)
            menu.exec(self.tree.viewport().mapToGlobal(position))
            menu.deleteLater()
            return

        menu = QMenu(self)
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS:
            insert_action = QAction(icon("fa5s.plus-square"), "Thêm vào Frame Preview", self)
            insert_action.triggered.connect(lambda: self.asset_insert_requested.emit(str(path)))
            edit_action = QAction(icon("fa5s.magic"), "Editor Assets…", self)
            edit_action.triggered.connect(
                lambda: self.asset_editor_requested.emit(str(path), self._folder_relative(path.parent))
            )
            menu.addAction(insert_action)
            menu.addAction(edit_action)
        open_action = QAction(icon("fa5s.external-link-alt"), "Mở", self)
        open_action.triggered.connect(lambda: self._activate_item(item))
        reveal_action = QAction(icon("fa5s.folder-open"), "Hiển thị trong Explorer", self)
        reveal_action.triggered.connect(lambda: self._reveal_path(path))
        menu.addAction(open_action)
        menu.addAction(reveal_action)
        menu.exec(self.tree.viewport().mapToGlobal(position))

    def _import_image_to_editor(self, destination_relative: str) -> None:
        file_path, _selected_filter = QFileDialog.getOpenFileName(
            self,
            "Nhập ảnh vào Editor Assets",
            str(Path.home()),
            "Ảnh 2D (*.png *.jpg *.jpeg *.webp *.bmp *.gif *.svg);;Tất cả tệp (*.*)",
        )
        if not file_path:
            return
        self.import_image_to_editor(Path(file_path), destination_relative)

    def import_image_to_editor(self, source: Path, destination_relative: str) -> None:
        """Copy nguyên liệu vào thư mục đích rồi mở Editor Assets trên bản copy.

        Kiểu Godot: tài nguyên gốc xuất hiện ngay trong project khi import;
        Editor Assets chỉnh sửa trên chính bản copy đó nên lưu sẽ ghi tại chỗ.
        """
        dest_dir = (self.project_root / destination_relative).resolve()
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / source.name
        index = 2
        while dest.exists():
            dest = dest_dir / f"{source.stem}_{index}{source.suffix}"
            index += 1
        try:
            shutil.copy2(source, dest)
        except OSError as error:
            self.error_message.emit(f"Không thể copy {source.name} vào {destination_relative}: {error}")
            return
        self.refresh(dest)
        self.status_message.emit(
            f"[Assets] Đã nhập {source.name} vào {destination_relative}/ — mở Editor Assets để chỉnh sửa."
        )
        self.asset_editor_requested.emit(str(dest), destination_relative)

    def _copy_files_to_folder(self, folder: Path, file_filter: str) -> None:
        files, _selected_filter = QFileDialog.getOpenFileNames(
            self,
            "Nhập tài nguyên",
            str(Path.home()),
            file_filter,
        )
        if not files:
            return
        imported: list[Path] = []
        try:
            folder.mkdir(parents=True, exist_ok=True)
            for file_name in files:
                source = Path(file_name)
                if not source.is_file():
                    continue
                destination = unique_destination(folder / source.name)
                if source.resolve() == destination.resolve():
                    continue
                shutil.copy2(source, destination)
                imported.append(destination)
        except OSError as error:
            self.error_message.emit(f"Không thể nhập tài nguyên: {error}")
            return
        if imported:
            self.refresh(imported[-1])
            relative = self._folder_relative(folder)
            self.status_message.emit(f"[Assets] Đã nhập {len(imported)} tệp vào project://{relative}.")

    def import_resources(self) -> None:
        """Compatibility entry point used by older integrations.

        The new UI routes imports through a folder ellipsis. This method selects
        the current asset folder when possible, otherwise defaults to map/texture.
        """
        current = self.tree.currentItem()
        path = None
        if current is not None:
            value = current.data(0, Qt.ItemDataRole.UserRole)
            path = Path(value) if value else None
        if path is None or not path.is_dir() or not self._is_asset_folder(path):
            path = self.project_root / "assets" / "map" / "texture"
        relative = self._folder_relative(path)
        if relative in self.IMAGE_EDITOR_FOLDERS or relative.startswith("assets/map/"):
            self._import_image_to_editor("assets/map/texture" if relative == "assets/map" else relative)
        else:
            self._copy_files_to_folder(path, "Tất cả tệp (*.*)")

    def _reveal_path(self, path: Path) -> None:
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices
        target = path if path.is_dir() else path.parent
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(target)))

    def _open_project_folder(self) -> None:
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.project_root)))


def build_assets_panel(project_path: str, package_name: str) -> AssetsPanel:
    return AssetsPanel(project_path, package_name)
