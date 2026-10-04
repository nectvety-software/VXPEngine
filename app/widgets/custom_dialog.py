"""Frameless, responsive dialogs used across VXPEngine.

No helper in this module opens a native operating-system dialog.  File, folder,
text, number, color, confirmation, notification and run-session windows all use
the same Qt-drawn title bar and dark Figma-style surface.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QDir, QPoint, QSize, Qt, Signal
from PySide6.QtGui import QColor, QCloseEvent, QKeyEvent, QMouseEvent, QShowEvent
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QColorDialog,
    QComboBox,
    QDialog,
    QFileSystemModel,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

from .icons import app_icon, icon
from .log_format import append_colored_log


class _DialogTitleBar(QWidget):
    """Event-forwarding title bar rendered by Qt rather than Windows."""

    def __init__(self, owner: "CustomDialog") -> None:
        super().__init__(owner)
        self._owner = owner
        self.setObjectName("DialogTitleBar")
        self.setFixedHeight(32)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 0, 4, 0)
        layout.setSpacing(6)

        logo = QLabel()
        logo.setObjectName("DialogTitleIcon")
        logo.setPixmap(app_icon().pixmap(15, 15))
        logo.setFixedSize(18, 18)
        layout.addWidget(logo)

        self.title_label = QLabel(owner.windowTitle())
        self.title_label.setObjectName("DialogTitleText")
        self.title_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        layout.addWidget(self.title_label, 1)

        self.minimize_button = QPushButton()
        self.minimize_button.setObjectName("DialogMinButton")
        self.minimize_button.setIcon(icon("fa5s.minus"))
        self.minimize_button.setIconSize(QSize(10, 10))
        self.minimize_button.setFixedSize(42, 30)
        self.minimize_button.setToolTip("Thu nhỏ")
        self.minimize_button.clicked.connect(owner.showMinimized)
        layout.addWidget(self.minimize_button)

        self.maximize_button = QPushButton()
        self.maximize_button.setObjectName("DialogMaxButton")
        self.maximize_button.setIcon(icon("fa5s.square"))
        self.maximize_button.setIconSize(QSize(9, 9))
        self.maximize_button.setFixedSize(42, 30)
        self.maximize_button.setToolTip("Phóng to")
        self.maximize_button.clicked.connect(owner.toggle_maximize_restore)
        layout.addWidget(self.maximize_button)

        self.close_button = QPushButton()
        self.close_button.setObjectName("DialogCloseButton")
        self.close_button.setIcon(icon("fa5s.times"))
        self.close_button.setIconSize(QSize(11, 11))
        self.close_button.setFixedSize(44, 30)
        self.close_button.setToolTip("Đóng")
        self.close_button.clicked.connect(owner.request_close)
        layout.addWidget(self.close_button)

    def set_title(self, title: str) -> None:
        self.title_label.setText(title)

    def set_window_controls(self, *, minimize: bool, maximize: bool) -> None:
        self.minimize_button.setVisible(minimize)
        self.maximize_button.setVisible(maximize)

    def set_maximized(self, maximized: bool) -> None:
        self.maximize_button.setIcon(icon("fa5s.clone" if maximized else "fa5s.square"))
        self.maximize_button.setToolTip("Khôi phục" if maximized else "Phóng to")

    def mousePressEvent(self, event: QMouseEvent) -> None:
        self._owner._title_mouse_press(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        self._owner._title_mouse_move(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._owner._title_mouse_release(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self.maximize_button.isVisible():
            self._owner.toggle_maximize_restore()
            event.accept()


class CustomDialog(QDialog):
    """Responsive frameless dialog with a reusable custom title bar.

    ``resizable`` enables minimize/maximize/restore controls and a QSizeGrip.
    Small notification/input dialogs remain close-only.  Every dialog is drawn
    by Qt, so Windows never displays its native title bar.
    """

    close_requested = Signal()

    def __init__(
        self,
        title: str,
        parent=None,
        width: int = 500,
        *,
        height: int = 520,
        resizable: bool = False,
        modal: bool = True,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setWindowIcon(app_icon())
        self.setWindowFlags(
            Qt.WindowType.Dialog
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.NoDropShadowWindowHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setModal(modal)
        self._preferred_width = max(340, width)
        self._preferred_height = max(220, height)
        self._resizable = resizable
        self._drag_pos: QPoint | None = None
        self._normal_geometry = None
        self._close_handler = None
        self.setMinimumSize(340, 220)
        self.resize(self._preferred_width, self._preferred_height)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 12, 12, 12)

        self.root = QFrame()
        self.root.setObjectName("DialogRoot")
        self.root.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        outer.addWidget(self.root)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(30)
        shadow.setOffset(0, 7)
        shadow.setColor(QColor(0, 0, 0, 165))
        self.root.setGraphicsEffect(shadow)

        root_layout = QVBoxLayout(self.root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        self.dialog_title_bar = _DialogTitleBar(self)
        self.dialog_title_bar.set_window_controls(minimize=resizable, maximize=resizable)
        root_layout.addWidget(self.dialog_title_bar)

        self.body_scroll = QScrollArea()
        self.body_scroll.setObjectName("DialogBodyScroll")
        self.body_scroll.setWidgetResizable(True)
        self.body_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.body_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.body_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        self.body = QWidget()
        self.body.setObjectName("DialogBody")
        self.body_layout = QVBoxLayout(self.body)
        self.body_layout.setContentsMargins(18, 16, 18, 16)
        self.body_layout.setSpacing(10)
        self.body_scroll.setWidget(self.body)
        root_layout.addWidget(self.body_scroll, 1)

        self.footer = QWidget()
        self.footer.setObjectName("DialogFooter")
        self.footer_layout = QHBoxLayout(self.footer)
        self.footer_layout.setContentsMargins(18, 10, 18, 12)
        self.footer_layout.setSpacing(8)
        self.footer_layout.addStretch()
        root_layout.addWidget(self.footer)

        if resizable:
            from PySide6.QtWidgets import QSizeGrip

            grip_row = QHBoxLayout()
            grip_row.setContentsMargins(0, 0, 1, 1)
            grip_row.addStretch()
            grip = QSizeGrip(self.root)
            grip.setObjectName("DialogSizeGrip")
            grip.setFixedSize(14, 14)
            grip_row.addWidget(grip)
            root_layout.addLayout(grip_row)

    def set_title(self, title: str) -> None:
        self.setWindowTitle(title)
        self.dialog_title_bar.set_title(title)

    def set_close_handler(self, handler) -> None:
        """Override the X button behavior, e.g. hide a running session."""
        self._close_handler = handler

    def request_close(self) -> None:
        self.close_requested.emit()
        if callable(self._close_handler):
            self._close_handler()
        else:
            self.reject()

    def add_body_widget(self, widget: QWidget, stretch: int = 0) -> None:
        self.body_layout.addWidget(widget, stretch)

    def add_footer_button(
        self,
        text: str,
        accent: bool = False,
        ghost: bool = False,
        danger: bool = False,
        icon_name: str | None = None,
    ) -> QPushButton:
        button = QPushButton(text)
        if accent:
            button.setObjectName("AccentBtn")
        elif danger:
            button.setObjectName("DangerBtn")
        elif ghost:
            button.setObjectName("GhostBtn")
        if icon_name:
            button.setIcon(icon(icon_name, "#C9D6EA", "#FFFFFF"))
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setMinimumHeight(36)
        button.setMinimumWidth(88)
        button.setSizePolicy(QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.Fixed)
        self.footer_layout.addWidget(button)
        return button

    def hide_footer(self) -> None:
        self.footer.hide()

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        screen = self.screen() or QApplication.primaryScreen()
        if screen is None:
            return
        area = screen.availableGeometry()
        max_width = max(340, int(area.width() * 0.94))
        max_height = max(260, int(area.height() * 0.92))
        target_width = min(self._preferred_width, max_width)
        hint_height = self.root.sizeHint().height() + 24
        desired_height = max(self._preferred_height, hint_height)
        target_height = min(max(260, desired_height), max_height)
        self.resize(target_width, target_height)
        anchor = self.parentWidget().window() if self.parentWidget() is not None else None
        if anchor is not None and anchor.isVisible():
            # parentWidget may be a tiny Inspector control whose frameGeometry
            # is in local coordinates. Always center dialogs on its top-level
            # VXPEngine window using global frame coordinates.
            center = anchor.frameGeometry().center()
            anchor_screen = anchor.screen()
            if anchor_screen is not None:
                area = anchor_screen.availableGeometry()
        else:
            center = area.center()
        x = max(area.left(), min(center.x() - self.width() // 2, area.right() - self.width() + 1))
        y = max(area.top(), min(center.y() - self.height() // 2, area.bottom() - self.height() + 1))
        self.move(x, y)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        compact = self.width() < 470
        self.body_layout.setContentsMargins(12 if compact else 18, 12, 12 if compact else 18, 12)
        self.footer_layout.setContentsMargins(12 if compact else 18, 8, 12 if compact else 18, 10)
        for index in range(1, self.footer_layout.count()):
            item = self.footer_layout.itemAt(index)
            widget = item.widget()
            if isinstance(widget, QPushButton):
                widget.setMinimumWidth(72 if compact else 88)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.request_close()
            event.accept()
            return
        super().keyPressEvent(event)

    def closeEvent(self, event: QCloseEvent) -> None:
        if callable(self._close_handler):
            event.ignore()
            self._close_handler()
            return
        super().closeEvent(event)

    def toggle_maximize_restore(self) -> None:
        if not self._resizable:
            return
        if self.isMaximized():
            self.showNormal()
            if self._normal_geometry is not None:
                self.setGeometry(self._normal_geometry)
            self.dialog_title_bar.set_maximized(False)
        else:
            self._normal_geometry = self.geometry()
            self.showMaximized()
            self.dialog_title_bar.set_maximized(True)

    def _title_mouse_press(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def _title_mouse_move(self, event: QMouseEvent) -> None:
        if self._drag_pos is None or not event.buttons() & Qt.MouseButton.LeftButton:
            return
        global_pos = event.globalPosition().toPoint()
        if self.isMaximized() and self._resizable:
            ratio = event.position().x() / max(1, self.width())
            self.showNormal()
            restored_width = self._normal_geometry.width() if self._normal_geometry is not None else self._preferred_width
            restored_height = self._normal_geometry.height() if self._normal_geometry is not None else self._preferred_height
            x = int(global_pos.x() - restored_width * ratio)
            y = max(0, global_pos.y() - int(event.position().y()))
            self.setGeometry(x, y, restored_width, restored_height)
            self.dialog_title_bar.set_maximized(False)
            self._drag_pos = global_pos - self.frameGeometry().topLeft()
        self.move(global_pos - self._drag_pos)
        event.accept()

    def _title_mouse_release(self, event: QMouseEvent) -> None:
        self._drag_pos = None
        event.accept()


class NoticeDialog(CustomDialog):
    def __init__(
        self,
        title: str,
        message: str,
        parent=None,
        error: bool = False,
        warning: bool = False,
    ) -> None:
        super().__init__(title, parent=parent, width=480, height=260)
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(14)

        icon_label = QLabel()
        if error:
            icon_name, icon_color = "fa5s.exclamation-circle", "#FF6B72"
        elif warning:
            icon_name, icon_color = "fa5s.exclamation-triangle", "#F5B84B"
        else:
            icon_name, icon_color = "fa5s.info-circle", "#5B93FF"
        icon_label.setPixmap(icon(icon_name, icon_color).pixmap(28, 28))
        icon_label.setAlignment(Qt.AlignmentFlag.AlignTop)
        layout.addWidget(icon_label)

        text = QLabel(message)
        text.setWordWrap(True)
        text.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        text.setObjectName("NoticeText")
        layout.addWidget(text, 1)
        self.add_body_widget(row)

        ok = self.add_footer_button("Đồng ý", accent=True, icon_name="fa5s.check")
        ok.clicked.connect(self.accept)


class ConfirmDialog(CustomDialog):
    def __init__(
        self,
        title: str,
        message: str,
        parent=None,
        *,
        confirm_text: str = "Xác nhận",
        danger: bool = False,
    ) -> None:
        super().__init__(title, parent=parent, width=500, height=280)
        label = QLabel(message)
        label.setWordWrap(True)
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        label.setObjectName("NoticeText")
        self.add_body_widget(label)
        cancel = self.add_footer_button("Hủy", ghost=True, icon_name="fa5s.times")
        confirm = self.add_footer_button(
            confirm_text,
            accent=not danger,
            danger=danger,
            icon_name="fa5s.check" if not danger else "fa5s.trash-alt",
        )
        cancel.clicked.connect(self.reject)
        confirm.clicked.connect(self.accept)

    @classmethod
    def ask(cls, title: str, message: str, parent=None, **kwargs) -> bool:
        return cls(title, message, parent, **kwargs).exec() == QDialog.DialogCode.Accepted


class TextInputDialog(CustomDialog):
    def __init__(
        self,
        title: str,
        label: str,
        parent=None,
        *,
        text: str = "",
        placeholder: str = "",
        multiline: bool = False,
    ) -> None:
        super().__init__(title, parent=parent, width=520, height=300)
        prompt = QLabel(label)
        prompt.setWordWrap(True)
        prompt.setObjectName("DialogDescription")
        self.add_body_widget(prompt)
        if multiline:
            self.editor = QPlainTextEdit(text)
            self.editor.setMinimumHeight(120)
        else:
            self.editor = QLineEdit(text)
            self.editor.setPlaceholderText(placeholder)
            self.editor.setClearButtonEnabled(True)
            self.editor.returnPressed.connect(self.accept)
        self.add_body_widget(self.editor)
        cancel = self.add_footer_button("Hủy", ghost=True, icon_name="fa5s.times")
        confirm = self.add_footer_button("Áp dụng", accent=True, icon_name="fa5s.check")
        cancel.clicked.connect(self.reject)
        confirm.clicked.connect(self.accept)

    @property
    def value(self) -> str:
        if isinstance(self.editor, QPlainTextEdit):
            return self.editor.toPlainText()
        return self.editor.text()

    @classmethod
    def get_text(cls, parent, title: str, label: str, *, text: str = "") -> tuple[str, bool]:
        dialog = cls(title, label, parent, text=text)
        accepted = dialog.exec() == QDialog.DialogCode.Accepted
        return dialog.value, accepted


class IntInputDialog(CustomDialog):
    def __init__(
        self,
        title: str,
        label: str,
        parent=None,
        *,
        value: int = 0,
        minimum: int = -2147483647,
        maximum: int = 2147483647,
        step: int = 1,
    ) -> None:
        super().__init__(title, parent=parent, width=460, height=280)
        prompt = QLabel(label)
        prompt.setWordWrap(True)
        prompt.setObjectName("DialogDescription")
        self.add_body_widget(prompt)
        self.spin = QSpinBox()
        self.spin.setRange(minimum, maximum)
        self.spin.setSingleStep(step)
        self.spin.setValue(value)
        self.add_body_widget(self.spin)
        cancel = self.add_footer_button("Hủy", ghost=True, icon_name="fa5s.times")
        confirm = self.add_footer_button("Đi tới", accent=True, icon_name="fa5s.location-arrow")
        cancel.clicked.connect(self.reject)
        confirm.clicked.connect(self.accept)

    @classmethod
    def get_int(
        cls,
        parent,
        title: str,
        label: str,
        value: int = 0,
        minimum: int = -2147483647,
        maximum: int = 2147483647,
        step: int = 1,
    ) -> tuple[int, bool]:
        dialog = cls(
            title,
            label,
            parent,
            value=value,
            minimum=minimum,
            maximum=maximum,
            step=step,
        )
        accepted = dialog.exec() == QDialog.DialogCode.Accepted
        return dialog.spin.value(), accepted


class ColorPickerDialog(CustomDialog):
    """Embeds Qt's non-native color widget inside the engine's custom frame."""

    def __init__(
        self,
        initial: QColor,
        parent=None,
        *,
        title: str = "Chọn màu",
        show_alpha: bool = True,
    ) -> None:
        super().__init__(title, parent=parent, width=680, height=540, resizable=True)
        self.picker = QColorDialog(initial, self.body)
        options = QColorDialog.ColorDialogOption.DontUseNativeDialog | QColorDialog.ColorDialogOption.NoButtons
        if show_alpha:
            options |= QColorDialog.ColorDialogOption.ShowAlphaChannel
        self.picker.setOptions(options)
        self.picker.setWindowFlags(Qt.WindowType.Widget)
        self.add_body_widget(self.picker, 1)
        cancel = self.add_footer_button("Hủy", ghost=True, icon_name="fa5s.times")
        apply_button = self.add_footer_button("Áp dụng", accent=True, icon_name="fa5s.palette")
        cancel.clicked.connect(self.reject)
        apply_button.clicked.connect(self.accept)

    @property
    def color(self) -> QColor:
        return self.picker.currentColor()

    @classmethod
    def get_color(
        cls,
        initial: QColor,
        parent=None,
        *,
        title: str = "Chọn màu",
        show_alpha: bool = True,
    ) -> QColor:
        dialog = cls(initial, parent, title=title, show_alpha=show_alpha)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            return dialog.color
        return QColor()


class FilePickerDialog(CustomDialog):
    """A project-friendly file/folder picker with no native OS chrome."""

    MODE_FILE = "file"
    MODE_FILES = "files"
    MODE_DIRECTORY = "directory"

    def __init__(
        self,
        title: str,
        parent=None,
        *,
        start_directory: str | Path | None = None,
        name_filter: str = "Tất cả tệp (*.*)",
        mode: str = MODE_FILE,
    ) -> None:
        super().__init__(title, parent=parent, width=900, height=650, resizable=True)
        self.mode = mode
        self._selected_paths: list[str] = []
        self._filter_groups = self._parse_filter_groups(name_filter)

        toolbar = QWidget()
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(0, 0, 0, 0)
        toolbar_layout.setSpacing(6)

        for icon_name, tooltip, callback in (
            ("fa5s.arrow-up", "Lên thư mục cha", self._go_up),
            ("fa5s.home", "Thư mục người dùng", self._go_home),
            ("fa5s.sync-alt", "Làm mới", self._refresh),
            ("fa5s.folder-plus", "Tạo thư mục", self._create_folder),
        ):
            button = QPushButton()
            button.setObjectName("IconButton")
            button.setIcon(icon(icon_name))
            button.setFixedSize(38, 34)
            button.setToolTip(tooltip)
            button.clicked.connect(callback)
            toolbar_layout.addWidget(button)

        self.path_edit = QLineEdit()
        self.path_edit.setClearButtonEnabled(True)
        self.path_edit.returnPressed.connect(self._navigate_from_text)
        toolbar_layout.addWidget(self.path_edit, 1)

        self.filter_combo = QComboBox()
        for label, patterns in self._filter_groups:
            self.filter_combo.addItem(label, patterns)
        self.filter_combo.currentIndexChanged.connect(self._apply_filter)
        self.filter_combo.setMinimumWidth(180)
        toolbar_layout.addWidget(self.filter_combo)
        self.add_body_widget(toolbar)

        self.model = QFileSystemModel(self)
        self.model.setFilter(QDir.Filter.AllDirs | QDir.Filter.Files | QDir.Filter.NoDotAndDotDot | QDir.Filter.Drives)
        self.model.setNameFilterDisables(False)
        self.model.setReadOnly(False)
        self.model.directoryLoaded.connect(lambda _path: self._update_selection_label())

        self.tree = QTreeView()
        self.tree.setObjectName("CustomFileTree")
        self.tree.setModel(self.model)
        self.tree.setAlternatingRowColors(True)
        self.tree.setSortingEnabled(True)
        self.tree.sortByColumn(0, Qt.SortOrder.AscendingOrder)
        self.tree.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tree.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection
            if mode == self.MODE_FILES
            else QAbstractItemView.SelectionMode.SingleSelection
        )
        self.tree.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tree.doubleClicked.connect(self._double_clicked)
        self.tree.selectionModel().selectionChanged.connect(lambda *_: self._update_selection_label())
        header = self.tree.header()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column in range(1, 4):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        self.add_body_widget(self.tree, 1)

        self.selection_label = QLabel()
        self.selection_label.setObjectName("DialogHint")
        self.selection_label.setWordWrap(True)
        self.add_body_widget(self.selection_label)

        cancel = self.add_footer_button("Hủy", ghost=True, icon_name="fa5s.times")
        accept_text = "Chọn thư mục" if mode == self.MODE_DIRECTORY else "Mở"
        confirm = self.add_footer_button(accept_text, accent=True, icon_name="fa5s.check")
        cancel.clicked.connect(self.reject)
        confirm.clicked.connect(self._accept_selection)

        start = Path(start_directory or Path.home()).expanduser()
        if start.is_file():
            start = start.parent
        if not start.exists():
            start = Path.home()
        self._set_directory(start.resolve())
        self._apply_filter()

    @staticmethod
    def _parse_filter_groups(filter_text: str) -> list[tuple[str, list[str]]]:
        groups: list[tuple[str, list[str]]] = []
        for part in (filter_text or "Tất cả tệp (*.*)").split(";;"):
            part = part.strip()
            if not part:
                continue
            if "(" in part and part.endswith(")"):
                label, pattern_text = part.rsplit("(", 1)
                patterns = [item for item in pattern_text[:-1].split() if item]
                groups.append((label.strip() or part, patterns or ["*"]))
            else:
                groups.append((part, ["*"]))
        return groups or [("Tất cả tệp", ["*"])]

    @property
    def selected_paths(self) -> list[str]:
        return list(self._selected_paths)

    def _current_directory(self) -> Path:
        text = self.path_edit.text().strip()
        path = Path(text).expanduser() if text else Path.home()
        return path if path.is_dir() else path.parent

    def _set_directory(self, directory: Path) -> None:
        directory = directory.expanduser().resolve()
        root_index = self.model.setRootPath(str(directory))
        self.tree.setRootIndex(root_index)
        self.path_edit.setText(str(directory))
        self.path_edit.setCursorPosition(0)
        self._update_selection_label()

    def _go_up(self) -> None:
        current = self._current_directory()
        parent = current.parent
        self._set_directory(parent if parent != current else current)

    def _go_home(self) -> None:
        self._set_directory(Path.home())

    def _refresh(self) -> None:
        self._set_directory(self._current_directory())

    def _navigate_from_text(self) -> None:
        candidate = Path(self.path_edit.text().strip()).expanduser()
        if candidate.is_dir():
            self._set_directory(candidate)
        elif candidate.is_file() and self.mode != self.MODE_DIRECTORY:
            self._selected_paths = [str(candidate.resolve())]
            self.accept()
        else:
            NoticeDialog("Đường dẫn không hợp lệ", "Không tìm thấy tệp hoặc thư mục đã nhập.", self, error=True).exec()

    def _create_folder(self) -> None:
        name, accepted = TextInputDialog.get_text(self, "Tạo thư mục", "Tên thư mục mới:")
        if not accepted or not name.strip():
            return
        if any(char in name for char in '<>:"/\\|?*'):
            NoticeDialog("Tên không hợp lệ", "Tên thư mục chứa ký tự Windows không được hỗ trợ.", self, error=True).exec()
            return
        target = self._current_directory() / name.strip()
        try:
            target.mkdir(parents=False, exist_ok=False)
        except OSError as error:
            NoticeDialog("Không thể tạo thư mục", str(error), self, error=True).exec()
            return
        self._set_directory(target)

    def _apply_filter(self) -> None:
        if self.mode == self.MODE_DIRECTORY:
            self.model.setNameFilters([])
            return
        patterns = self.filter_combo.currentData() or ["*"]
        normalized = ["*" if item in {"*.*", "*"} else item for item in patterns]
        self.model.setNameFilters(normalized)

    def _double_clicked(self, index) -> None:
        path = Path(self.model.filePath(index))
        if path.is_dir():
            self._set_directory(path)
        elif self.mode != self.MODE_DIRECTORY:
            self._selected_paths = [str(path.resolve())]
            self.accept()

    def _selected_indexes(self):
        rows = self.tree.selectionModel().selectedRows(0)
        return [index for index in rows if index.isValid()]

    def _update_selection_label(self) -> None:
        paths = [Path(self.model.filePath(index)) for index in self._selected_indexes()]
        if not paths:
            if self.mode == self.MODE_DIRECTORY:
                self.selection_label.setText(f"Thư mục hiện tại: {self._current_directory()}")
            else:
                self.selection_label.setText("Chưa chọn tệp.")
            return
        shown = ", ".join(path.name for path in paths[:4])
        if len(paths) > 4:
            shown += f" và {len(paths) - 4} tệp khác"
        self.selection_label.setText(f"Đã chọn: {shown}")

    def _accept_selection(self) -> None:
        selected = [Path(self.model.filePath(index)) for index in self._selected_indexes()]
        if self.mode == self.MODE_DIRECTORY:
            directory = next((path for path in selected if path.is_dir()), self._current_directory())
            self._selected_paths = [str(directory.resolve())]
            self.accept()
            return
        files = [path for path in selected if path.is_file()]
        if not files:
            NoticeDialog("Chưa chọn tệp", "Hãy chọn ít nhất một tệp để tiếp tục.", self, warning=True).exec()
            return
        if self.mode == self.MODE_FILE:
            files = files[:1]
        self._selected_paths = [str(path.resolve()) for path in files]
        self.accept()

    @classmethod
    def get_existing_directory(
        cls,
        parent=None,
        title: str = "Chọn thư mục",
        start_directory: str | Path | None = None,
    ) -> str:
        dialog = cls(
            title,
            parent,
            start_directory=start_directory,
            mode=cls.MODE_DIRECTORY,
        )
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.selected_paths:
            return dialog.selected_paths[0]
        return ""

    @classmethod
    def get_open_file_name(
        cls,
        parent=None,
        title: str = "Mở tệp",
        start_directory: str | Path | None = None,
        name_filter: str = "Tất cả tệp (*.*)",
    ) -> str:
        dialog = cls(
            title,
            parent,
            start_directory=start_directory,
            name_filter=name_filter,
            mode=cls.MODE_FILE,
        )
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.selected_paths:
            return dialog.selected_paths[0]
        return ""

    @classmethod
    def get_open_file_names(
        cls,
        parent=None,
        title: str = "Mở tệp",
        start_directory: str | Path | None = None,
        name_filter: str = "Tất cả tệp (*.*)",
    ) -> list[str]:
        dialog = cls(
            title,
            parent,
            start_directory=start_directory,
            name_filter=name_filter,
            mode=cls.MODE_FILES,
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            return dialog.selected_paths
        return []


class RunSessionDialog(CustomDialog):
    """Custom-framed monitor for Run/Build/Debug tasks.

    It is window-modal rather than using ``exec()`` so QProcess signals continue
    to update the UI while the parent editor is blocked.  Closing the X hides the
    monitor; it never kills the user's game unexpectedly.  The explicit Stop
    button owns process termination.
    """

    stop_requested = Signal()

    def __init__(self, title: str, parent=None) -> None:
        super().__init__(title, parent=parent, width=900, height=620, resizable=True, modal=False)
        self.setWindowModality(Qt.WindowModality.WindowModal)
        self.set_close_handler(self.hide)

        status_row = QWidget()
        status_layout = QHBoxLayout(status_row)
        status_layout.setContentsMargins(0, 0, 0, 0)
        status_layout.setSpacing(10)
        self.status_icon = QLabel()
        self.status_icon.setPixmap(icon("fa5s.play-circle", "#64D28A").pixmap(24, 24))
        status_layout.addWidget(self.status_icon)
        self.status_label = QLabel("Đang chuẩn bị…")
        self.status_label.setObjectName("RunSessionStatus")
        status_layout.addWidget(self.status_label, 1)
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setTextVisible(False)
        self.progress.setFixedWidth(160)
        status_layout.addWidget(self.progress)
        self.add_body_widget(status_row)

        self.output = QPlainTextEdit()
        self.output.setObjectName("RunSessionOutput")
        self.output.setReadOnly(True)
        self.output.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.add_body_widget(self.output, 1)

        hide_button = self.add_footer_button("Ẩn cửa sổ", ghost=True, icon_name="fa5s.window-minimize")
        self.stop_button = self.add_footer_button("Dừng", danger=True, icon_name="fa5s.stop")
        hide_button.clicked.connect(self.hide)
        self.stop_button.clicked.connect(self.stop_requested.emit)

    def begin(
        self,
        title: str,
        status: str = "Đang khởi động",
        *,
        show_window: bool = True,
    ) -> None:
        self.set_title(title)
        self.output.clear()
        self.set_running(True)
        self.set_phase(status)
        if show_window:
            self.show()
            self.raise_()
            self.activateWindow()
        else:
            self.hide()

    def append_output(self, text: str) -> None:
        if not text:
            return
        append_colored_log(self.output, text.rstrip("\n"))
        scrollbar = self.output.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def set_phase(self, phase: str) -> None:
        self.status_label.setText(phase or "Đang chạy")

    def set_running(self, running: bool, success: bool | None = None) -> None:
        self.stop_button.setEnabled(running)
        if running:
            self.progress.setRange(0, 0)
            self.status_icon.setPixmap(icon("fa5s.circle-notch", "#64D28A").pixmap(24, 24))
            return
        self.progress.setRange(0, 1)
        self.progress.setValue(1)
        if success is True:
            self.status_icon.setPixmap(icon("fa5s.check-circle", "#64D28A").pixmap(24, 24))
            self.status_label.setText("Hoàn tất")
        elif success is False:
            self.status_icon.setPixmap(icon("fa5s.times-circle", "#FF6B72").pixmap(24, 24))
            self.status_label.setText("Tác vụ thất bại")
        else:
            self.status_icon.setPixmap(icon("fa5s.stop-circle", "#F5B84B").pixmap(24, 24))
            self.status_label.setText("Đã dừng")
