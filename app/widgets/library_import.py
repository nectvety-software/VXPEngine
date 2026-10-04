"""Library import dialog — đưa tài nguyên từ Thư viện VXPEngine vào project.

Kiểu Godot: tài nguyên gốc nằm trong thư viện của engine (``library/images``,
``library/sfx``); project mới sinh ra trống và người dùng chọn những gì cần
để **import vào project** (copy thật vào ``assets/``), sau đó Assets panel
refresh ngay.
"""
from __future__ import annotations

import shutil
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QFrame, QHBoxLayout, QLabel, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget

from .custom_dialog import CustomDialog
from .icons import icon


def library_root() -> Path:
    """Bộ nguyên liệu/tài nguyên gốc của VXPEngine: ``<repo>/assets``."""
    return Path(__file__).resolve().parent.parent.parent / "assets"


IMAGE_DESTINATIONS = [
    "assets/map/texture",
    "assets/backgrounds",
    "assets/ui",
    "assets/sprites",
    "assets/icons",
    "assets/scenes",
    "assets/map/tileset",
    "assets/map/skill",
    "assets/app-icon",
    "assets",
]
SFX_DESTINATION = "assets/audio"


class LibraryImportDialog(CustomDialog):
    """Chọn ảnh/SFX từ Thư viện VXPEngine và copy vào project đang mở."""

    def __init__(self, project_root: str | Path, parent=None) -> None:
        super().__init__("Nhập từ Thư viện Assets/SFX", parent, width=640, height=560, resizable=True, modal=True)
        self.project_root = Path(project_root).resolve()
        self.imported_paths: list[Path] = []

        intro = QLabel(
            "Tài nguyên nằm trong Thư viện của VXPEngine. Chọn mục cần dùng rồi nhấn "
            "“Nhập vào project” — file được copy vào assets/ của project (kiểu Godot)."
        )
        intro.setObjectName("DialogDescription")
        intro.setWordWrap(True)
        self.add_body_widget(intro)

        self.tree = QTreeWidget()
        self.tree.setColumnCount(2)
        self.tree.setHeaderLabels(["Tài nguyên", "Thư mục gốc"])
        self.tree.setRootIsDecorated(True)
        self.tree.setMinimumHeight(280)
        self._populate()
        self.add_body_widget(self.tree)

        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(QLabel("Ảnh nhập vào:"))
        self.destination_combo = QComboBox()
        for relative in IMAGE_DESTINATIONS:
            self.destination_combo.addItem(relative, relative)
        layout.addWidget(self.destination_combo, 1)
        layout.addWidget(QLabel("SFX nhập vào:"))
        sfx_label = QLabel(f"{SFX_DESTINATION} (cố định)")
        layout.addWidget(sfx_label)
        self.add_body_widget(row)

        self.status = QLabel("")
        self.status.setObjectName("DialogHint")
        self.status.setWordWrap(True)
        self.add_body_widget(self.status)

        cancel = self.add_footer_button("Hủy", ghost=True, icon_name="fa5s.times")
        do_import = self.add_footer_button("Nhập vào project", accent=True, icon_name="fa5s.file-import")
        cancel.clicked.connect(self.reject)
        do_import.clicked.connect(self._do_import)
        self.primary_button = do_import
        self.tree.itemChanged.connect(self._update_status)
        self._update_status()

    # ------------------------------------------------------------------ UI

    def _populate(self) -> None:
        lib = library_root()
        images_root = lib / "images"
        sfx_root = lib / "sfx"

        images = sorted(lib.rglob("*.png"))
        sfx = sorted(sfx_root.rglob("*.mp3")) if sfx_root.exists() else []

        group_img = QTreeWidgetItem(self.tree, [f"Thư viện ảnh ({len(images)})", "assets/"])
        group_img.setFlags(group_img.flags() & ~Qt.ItemFlag.ItemIsUserCheckable)
        font = group_img.font(0)
        font.setBold(True)
        group_img.setFont(0, font)
        for path in images:
            rel = path.relative_to(lib).as_posix()
            item = QTreeWidgetItem(group_img, [path.name, str(Path(rel).parent) if Path(rel).parent != Path(".") else ""])
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(0, Qt.CheckState.Unchecked)
            item.setData(0, Qt.ItemDataRole.UserRole, str(path))
            item.setToolTip(0, f"import từ assets/{rel}")
        group_img.setExpanded(True)

        group_sfx = QTreeWidgetItem(self.tree, [f"Thư viện SFX ({len(sfx)})", "assets/sfx"])
        group_sfx.setFlags(group_sfx.flags() & ~Qt.ItemFlag.ItemIsUserCheckable)
        group_sfx.setFont(0, font)
        for path in sfx:
            rel = path.relative_to(sfx_root).as_posix()
            item = QTreeWidgetItem(group_sfx, [path.name, ""])
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(0, Qt.CheckState.Unchecked)
            item.setData(0, Qt.ItemDataRole.UserRole, str(path))
            item.setToolTip(0, f"import từ assets/sfx/{rel}")
        group_sfx.setExpanded(False)

        self.tree.resizeColumnToContents(0)

    def _checked_files(self) -> tuple[list[Path], list[Path]]:
        images: list[Path] = []
        sfx: list[Path] = []
        root = self.tree.invisibleRootItem()
        for group_index in range(root.childCount()):
            group = root.child(group_index)
            for child_index in range(group.childCount()):
                item = group.child(child_index)
                value = item.data(0, Qt.ItemDataRole.UserRole)
                if not value or item.checkState(0) != Qt.CheckState.Checked:
                    continue
                path = Path(str(value))
                if path.suffix.lower() == ".png":
                    images.append(path)
                elif path.suffix.lower() == ".mp3":
                    sfx.append(path)
        return images, sfx

    def _update_status(self, *_args) -> None:
        images, sfx = self._checked_files()
        destination = str(self.destination_combo.currentData() or "assets")
        parts = []
        if images:
            parts.append(f"{len(images)} ảnh → {destination}/")
        if sfx:
            parts.append(f"{len(sfx)} SFX → {SFX_DESTINATION}/")
        self.status.setText("Đã chọn: " + " · ".join(parts) if parts else "Chưa chọn tài nguyên nào.")

    # -------------------------------------------------------------- import

    def _do_import(self) -> None:
        images, sfx = self._checked_files()
        if not images and not sfx:
            self.status.setText("Hãy tick chọn ít nhất một tài nguyên trước khi nhập.")
            return
        image_dest = (self.project_root / str(self.destination_combo.currentData() or "assets")).resolve()
        sfx_dest = (self.project_root / SFX_DESTINATION).resolve()
        copied: list[Path] = []
        errors: list[str] = []
        try:
            for path in images:
                image_dest.mkdir(parents=True, exist_ok=True)
                copied.append(self._copy_unique(path, image_dest))
            for path in sfx:
                sfx_dest.mkdir(parents=True, exist_ok=True)
                copied.append(self._copy_unique(path, sfx_dest))
        except OSError as error:
            errors.append(str(error))
        self.imported_paths = copied
        if errors:
            self.status.setText("Lỗi khi nhập: " + "; ".join(errors))
            return
        self.accept()

    @staticmethod
    def _copy_unique(src: Path, dest_dir: Path) -> Path:
        dest = dest_dir / src.name
        index = 2
        while dest.exists():
            dest = dest_dir / f"{src.stem}_{index}{src.suffix}"
            index += 1
        shutil.copy2(src, dest)
        return dest
