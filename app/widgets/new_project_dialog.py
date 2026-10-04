"""Responsive New Project modal for VXPEngine MRE VXP projects (core coremre)."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from project_store import ENGINE_VERSION, ProjectStore, COREMRE_VERSION
from .custom_dialog import CustomDialog, FilePickerDialog
from .icons import icon


class NewProjectDialog(CustomDialog):
    ASPECT_PRESETS = {
        "240×320 — Dọc (S30+ chuẩn)": (240, 320, "3:4"),
        "320×240 — Ngang (S30+ landscape)": (320, 240, "4:3"),
    }
    """Create a project and immediately open it in the 2D workspace.

    The package field follows the project name until the user deliberately edits
    it. Typing ``My Action Game`` therefore produces
    ``com.vxp.myactiongame``. A user can still replace the complete package
    ID with any valid identifier.
    """

    ACTION_CREATE_OPEN = "create_open"

    def __init__(self, default_path: str, parent=None):
        super().__init__("Tạo dự án VXP mới", parent=parent, width=620)
        self.selected_action: str | None = None
        self._package_edited_manually = False
        self._last_auto_package = "com.vxp.ten_project"
        self.setMinimumWidth(380)

        intro = QLabel(
            "Khởi tạo project MRE VXP dọc 240×320 hoặc ngang 320×240 với "
            "coremre; build ARM và chạy bằng VXPEmu."
        )
        intro.setObjectName("DialogDescription")
        intro.setWordWrap(True)
        self.add_body_widget(intro)

        tech_row = QHBoxLayout()
        tech_row.setSpacing(8)
        for text, icon_name in [
            ("MRE VXP 3.0", "fa5s.mobile-alt"),
            (f"coremre {COREMRE_VERSION}", "fa5s.gamepad"),
            ("ARM + VXPEmu", "fa5s.microchip"),
        ]:
            badge = QLabel(text)
            badge.setObjectName("TechBadge")
            badge.setToolTip(f"{text} • dùng font icon trong toàn bộ nút điều khiển")
            tech_row.addWidget(badge)
        tech_row.addStretch()
        tech_wrap = QWidget()
        tech_wrap.setLayout(tech_row)
        self.add_body_widget(tech_wrap)

        label_name = QLabel("Tên dự án")
        label_name.setProperty("class", "PropName")
        self.edit_name = QLineEdit()
        self.edit_name.setPlaceholderText("Ví dụ: Platformer Adventure")
        self.edit_name.setClearButtonEnabled(True)
        self.add_body_widget(label_name)
        self.add_body_widget(self.edit_name)

        label_package = QLabel("Package ID (định danh ứng dụng)")
        label_package.setProperty("class", "PropName")
        self.edit_package = QLineEdit(self._last_auto_package)
        self.edit_package.setPlaceholderText("com.vxp.ten_project")
        self.edit_package.setClearButtonEnabled(True)
        self.add_body_widget(label_package)
        self.add_body_widget(self.edit_package)

        package_hint = QLabel(
            "Mặc định giữ tiền tố com.vxp. và tự đổi phần cuối theo tên dự án. "
            "Bạn vẫn có thể sửa toàn bộ Package ID bằng tay."
        )
        package_hint.setObjectName("DialogHint")
        package_hint.setWordWrap(True)
        self.add_body_widget(package_hint)

        label_path = QLabel("Vị trí thư mục lưu")
        label_path.setProperty("class", "PropName")
        self.add_body_widget(label_path)

        path_row = QWidget()
        path_layout = QHBoxLayout(path_row)
        path_layout.setContentsMargins(0, 0, 0, 0)
        path_layout.setSpacing(8)
        self.edit_path = QLineEdit(default_path)
        self.edit_path.setPlaceholderText("D:/VXP Projects")
        browse = QPushButton()
        browse.setObjectName("IconButton")
        browse.setIcon(icon("fa5s.folder-open"))
        browse.setToolTip("Chọn thư mục")
        browse.setFixedSize(38, 36)
        browse.clicked.connect(self._browse)
        path_layout.addWidget(self.edit_path, 1)
        path_layout.addWidget(browse)
        self.add_body_widget(path_row)

        ratio_card = QFrame()
        ratio_card.setObjectName("NativeOptionCard")
        ratio_layout = QVBoxLayout(ratio_card)
        ratio_layout.setContentsMargins(12, 10, 12, 10)
        ratio_layout.setSpacing(7)
        ratio_title = QLabel("Tỉ lệ khung hình / Frame Preview")
        ratio_title.setProperty("class", "PropName")
        ratio_layout.addWidget(ratio_title)
        self.aspect_combo = QComboBox()
        self.aspect_combo.addItems(self.ASPECT_PRESETS.keys())
        ratio_layout.addWidget(self.aspect_combo)
        dimensions = QWidget()
        dim_layout = QGridLayout(dimensions)
        dim_layout.setContentsMargins(0, 0, 0, 0)
        dim_layout.setHorizontalSpacing(8)
        self.viewport_width_spin = QSpinBox()
        self.viewport_width_spin.setRange(64, 8192)
        self.viewport_width_spin.setValue(240)
        self.viewport_width_spin.setSuffix(" px")
        self.viewport_height_spin = QSpinBox()
        self.viewport_height_spin.setRange(64, 8192)
        self.viewport_height_spin.setValue(320)
        self.viewport_height_spin.setSuffix(" px")
        dim_layout.addWidget(QLabel("Rộng"), 0, 0)
        dim_layout.addWidget(self.viewport_width_spin, 0, 1)
        dim_layout.addWidget(QLabel("Cao"), 0, 2)
        dim_layout.addWidget(self.viewport_height_spin, 0, 3)
        ratio_layout.addWidget(dimensions)
        ratio_hint = QLabel("Frame Preview, FitViewport và VXPEmu dùng cùng hướng màn hình S30+ này.")
        ratio_hint.setObjectName("DialogHint")
        ratio_hint.setWordWrap(True)
        ratio_layout.addWidget(ratio_hint)
        self.add_body_widget(ratio_card)

        native_box = QFrame()
        native_box.setObjectName("NativeOptionCard")
        native_layout = QVBoxLayout(native_box)
        native_layout.setContentsMargins(12, 10, 12, 10)
        native_layout.setSpacing(4)
        self.native_checkbox = QCheckBox("Bật build C/C++17 (core coremre) cho ARM VXP")
        self.native_checkbox.setChecked(True)
        self.native_checkbox.setIcon(icon("fa5s.microchip", "#72A8FF"))
        native_desc = QLabel(
            "Game chạy trực tiếp trên core coremre; IDE điều khiển build CMake và đóng gói .vxp."
        )
        native_desc.setObjectName("DialogHint")
        native_desc.setWordWrap(True)
        native_layout.addWidget(self.native_checkbox)
        native_layout.addWidget(native_desc)
        self.add_body_widget(native_box)

        self.preview_path = QLabel()
        self.preview_path.setObjectName("ProjectPathPreview")
        self.preview_path.setWordWrap(True)
        self.add_body_widget(self.preview_path)

        self.error_label = QLabel()
        self.error_label.setObjectName("InlineError")
        self.error_label.setWordWrap(True)
        self.error_label.hide()
        self.add_body_widget(self.error_label)

        cancel = self.add_footer_button("Hủy", ghost=True, icon_name="fa5s.times")
        create_open = self.add_footer_button(
            "Tạo dự án và mở 2D Engine", accent=True, icon_name="fa5s.play"
        )
        cancel.clicked.connect(self.reject)
        create_open.clicked.connect(self._submit)
        self.primary_button = create_open

        self.edit_name.textChanged.connect(self._name_changed)
        self.edit_package.textEdited.connect(self._package_changed_manually)
        self.edit_package.textChanged.connect(self._update_preview)
        self.edit_path.textChanged.connect(self._update_preview)
        self.native_checkbox.toggled.connect(self._update_preview)
        self.aspect_combo.currentTextChanged.connect(self._aspect_changed)
        self.viewport_width_spin.valueChanged.connect(self._dimension_changed)
        self.viewport_height_spin.valueChanged.connect(self._dimension_changed)
        self.edit_name.returnPressed.connect(self._submit)
        self._aspect_changed(self.aspect_combo.currentText())
        self._update_preview()
        self.edit_name.setFocus()

    @property
    def project_name(self) -> str:
        return self.edit_name.text().strip()

    @property
    def package_name(self) -> str:
        return self.edit_package.text().strip()

    @property
    def base_directory(self) -> str:
        return self.edit_path.text().strip()

    @property
    def native_enabled(self) -> bool:
        return self.native_checkbox.isChecked()

    @property
    def viewport_width(self) -> int:
        return self.viewport_width_spin.value()

    @property
    def viewport_height(self) -> int:
        return self.viewport_height_spin.value()

    @property
    def aspect_ratio(self) -> str:
        preset = self.ASPECT_PRESETS.get(self.aspect_combo.currentText())
        if preset and preset[2] != "Custom":
            return preset[2]
        return f"{self.viewport_width}:{self.viewport_height}"

    def show_error(self, message: str) -> None:
        self.error_label.setText(message)
        self.error_label.show()

    def _browse(self) -> None:
        selected = FilePickerDialog.get_existing_directory(
            self,
            "Chọn thư mục lưu dự án",
            self.base_directory or str(Path.home()),
        )
        if selected:
            self.edit_path.setText(selected)

    def _name_changed(self, _text: str = "") -> None:
        suggested = ProjectStore.package_from_project_name(self.project_name or "ten_project")
        current = self.edit_package.text().strip()
        may_follow_name = (
            not self._package_edited_manually
            or not current
            or current == self._last_auto_package
            or current == "com.vxp."
        )
        self._last_auto_package = suggested
        if may_follow_name and current != suggested:
            self.edit_package.blockSignals(True)
            self.edit_package.setText(suggested)
            self.edit_package.blockSignals(False)
            self._package_edited_manually = False
        self._update_preview()

    def _package_changed_manually(self, text: str) -> None:
        value = text.strip()
        # Returning to the brand prefix re-enables automatic suffix generation.
        self._package_edited_manually = value not in {"", "com.vxp.", self._last_auto_package}
        if value == "com.vxp.":
            self._name_changed()
        else:
            self._update_preview()

    def _aspect_changed(self, text: str) -> None:
        width, height, _ratio = self.ASPECT_PRESETS.get(text, (1280, 720, "Custom"))
        custom = text == "Tùy chỉnh"
        self.viewport_width_spin.blockSignals(True)
        self.viewport_height_spin.blockSignals(True)
        if not custom:
            self.viewport_width_spin.setValue(width)
            self.viewport_height_spin.setValue(height)
        self.viewport_width_spin.setEnabled(custom)
        self.viewport_height_spin.setEnabled(custom)
        self.viewport_width_spin.blockSignals(False)
        self.viewport_height_spin.blockSignals(False)
        self._update_preview()

    def _dimension_changed(self, _value: int = 0) -> None:
        if self.aspect_combo.currentText() != "Tùy chỉnh":
            self.aspect_combo.blockSignals(True)
            self.aspect_combo.setCurrentText("Tùy chỉnh")
            self.aspect_combo.blockSignals(False)
            self.viewport_width_spin.setEnabled(True)
            self.viewport_height_spin.setEnabled(True)
        self._update_preview()

    def _update_preview(self) -> None:
        name = self.project_name or "Tên dự án"
        base = self.base_directory or "Thư mục lưu"
        native = "C/C++ coremre" if self.native_enabled else "chỉ tài nguyên"
        self.preview_path.setText(
            f"Tạo tại: {Path(base) / name}\n"
            f"Package: {self.package_name or self._last_auto_package}  •  {native}\n"
            f"Frame: {self.viewport_width} × {self.viewport_height}  •  {self.aspect_ratio}"
        )
        self.error_label.hide()

    def _submit(self) -> None:
        if not self.project_name:
            self.show_error("Vui lòng nhập tên dự án.")
            self.edit_name.setFocus()
            return
        if not self.package_name:
            self.show_error("Vui lòng nhập Package ID.")
            self.edit_package.setFocus()
            return
        if not self.base_directory:
            self.show_error("Vui lòng nhập hoặc chọn vị trí thư mục lưu.")
            self.edit_path.setFocus()
            return
        try:
            ProjectStore.validate_project_name(self.project_name)
            ProjectStore.validate_package_name(self.package_name)
        except ValueError as error:
            self.show_error(str(error))
            return
        self.selected_action = self.ACTION_CREATE_OPEN
        self.accept()
