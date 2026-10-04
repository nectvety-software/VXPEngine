r"""Danh sách môi trường & thư viện kiểu "Extensions" của VS Code.

Mục đích: trả lời ngay câu hỏi *"cái nào đã cài đặt, cái nào chưa"* mà không
phải đợi chạy installer. Giao diện bám theo khung **Extensions** của VS Code:

* Một thanh tìm kiếm + bộ lọc (Tất cả / Đã cài đặt / Chưa cài đặt / Có thể cài
  tự động) giống đúng thanh ``…`` bên trái của VS Code.
* Mỗi dòng là một "extension": icon · tên đậm · mô tả nhỏ · huy hiệu trạng
  thái · nút hành động bên phải.
* Đếm tóm tắt phía trên: ``Đã cài đặt 8/10 · Chưa có 2 (1 cài tự động được)``.

Dùng chung :class:`~environment_setup.Requirement` với hộp thoại thiết lập lần
đầu, nên hai nơi luôn liệt kê cùng một danh sách. Không có gì tự cài khi chỉ
mở hộp thoại để xem.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from environment_setup import Requirement, all_requirements

from .custom_dialog import CustomDialog
from .icons import icon

#: Icon Font Awesome tương ứng từng thành phần (cột trái của mỗi dòng).
_ROW_ICONS: dict[str, str] = {
    "cmake": "fa5s.cog",
    "vs2022": "fa5s.window-maximize",
    "bash": "fa5s.terminal",
    "arm_gcc": "fa5s.microchip",
    "python_deps": "fa5s.python",
    "mre_sdk": "fa5s.cubes",
    "tiny_mresdk": "fa5s.file-signature",
    "w64devkit": "fa5s.tools",
    "packaging": "fa5s.box-open",
    "signing_backend": "fa5s.signature",
    "vxpemu": "fa5s.desktop",
    "signing_key": "fa5s.key",
}

#: Màu icon theo trạng thái — xanh khi đã có, vàng/đỏ khi còn thiếu.
_STATE_COLORS = {
    "installed": "#3FB27F",
    "auto": "#D9B27A",
    "manual": "#C2705A",
}

_FILTER_ALL = "all"
_FILTER_INSTALLED = "installed"
_FILTER_MISSING = "missing"
_FILTER_INSTALLABLE = "installable"


def _state_of(requirement: Requirement, satisfied: bool) -> tuple[str, str]:
    """Trả về ``(mã trạng thái, nhãn tiếng Việt)`` cho một thành phần."""
    if satisfied:
        return "installed", "Đã cài đặt"
    if requirement.is_installable:
        return "auto", "Chưa cài · có thể cài tự động"
    return "manual", "Chưa cài · cần làm thủ công"


class _EnvRow(QFrame):
    """Một dòng kiểu "extension" trong VS Code.

    Bố cục (trái → phải)::

        [icon 28] [ tên đậm                    ] [ huy hiệu ] [ nút ]
                  [ mô tả / gợi ý (xám nhỏ)    ]

    Dòng nào cài tự động được và đang thiếu sẽ có checkbox để gộp vào lượt
    cài hàng loạt ở footer; dòng đã cài đặt không có checkbox.
    """

    toggled = Signal()
    install_requested = Signal(object)

    def __init__(self, requirement: Requirement, satisfied: bool) -> None:
        super().__init__()
        self.requirement = requirement
        self._satisfied = satisfied
        self.setObjectName("EnvRow")
        self.setProperty("state", _state_of(requirement, satisfied)[0])

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(12)

        state, _label = _state_of(requirement, satisfied)
        self.icon_label = QLabel()
        self.icon_label.setObjectName("EnvRowIcon")
        self.icon_label.setPixmap(icon(_ROW_ICONS.get(requirement.key, "fa5s.puzzle-piece"),
                                       _STATE_COLORS[state]).pixmap(28, 28))
        self.icon_label.setFixedSize(28, 28)
        layout.addWidget(self.icon_label, 0, Qt.AlignmentFlag.AlignTop)

        text = QWidget()
        text_layout = QVBoxLayout(text)
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(3)

        title_row = QHBoxLayout()
        title_row.setContentsMargins(0, 0, 0, 0)
        title_row.setSpacing(8)
        self.name_label = QLabel(requirement.name)
        self.name_label.setObjectName("EnvRowName")
        self.name_label.setWordWrap(True)
        title_row.addWidget(self.name_label)
        if requirement.optional:
            tag = QLabel("tuỳ chọn")
            tag.setObjectName("EnvRowTag")
            title_row.addWidget(tag)
            title_row.addStretch(1)
        else:
            title_row.addStretch(1)
        text_layout.addLayout(title_row)

        self.hint_label = QLabel(requirement.hint or "—")
        self.hint_label.setObjectName("EnvRowHint")
        self.hint_label.setWordWrap(True)
        self.hint_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        text_layout.addWidget(self.hint_label)

        layout.addWidget(text, 1)

        self.badge = QLabel(_state_of(requirement, satisfied)[1])
        self.badge.setObjectName("EnvBadge")
        self.badge.setProperty("state", state)
        layout.addWidget(self.badge, 0, Qt.AlignmentFlag.AlignVCenter)

        self.check = QCheckBox()
        self.check.setToolTip("Chọn để cài tự động")
        self.check.toggled.connect(self.toggled.emit)
        layout.addWidget(self.check, 0, Qt.AlignmentFlag.AlignVCenter)

        self.action_button = QPushButton("Cài đặt")
        self.action_button.setObjectName("EnvRowAction")
        self.action_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.action_button.clicked.connect(lambda: self.install_requested.emit(self.requirement))
        layout.addWidget(self.action_button, 0, Qt.AlignmentFlag.AlignVCenter)

        self.refresh(satisfied)

    # ------------------------------------------------------------- trạng thái

    @property
    def satisfied(self) -> bool:
        return self._satisfied

    @property
    def selected(self) -> bool:
        return self.check.isChecked() and self.check.isEnabled()

    def refresh(self, satisfied: bool) -> None:
        """Cập nhật lại huy hiệu / nút sau khi quét lại môi trường."""
        self._satisfied = satisfied
        state, label = _state_of(self.requirement, satisfied)
        self.setProperty("state", state)
        self.badge.setText(label)
        self.badge.setProperty("state", state)
        self.icon_label.setPixmap(
            icon(_ROW_ICONS.get(self.requirement.key, "fa5s.puzzle-piece"),
                 _STATE_COLORS[state]).pixmap(28, 28)
        )
        # Chỉ mục còn thiếu + có lệnh cài mới cho phép tick / bấm "Cài đặt".
        actionable = (not satisfied) and self.requirement.is_installable
        self.check.setEnabled(actionable)
        self.check.setChecked(actionable)
        self.action_button.setVisible(actionable)
        self.action_button.setEnabled(actionable)
        # QSS đọc dynamic property nên phải polish lại để đổi màu ngay.
        self.style().unpolish(self)
        self.style().polish(self)
        self.style().unpolish(self.badge)
        self.style().polish(self.badge)

    def matches(self, needle: str, mode: str) -> bool:
        """Lọc theo ô tìm kiếm + combo bộ lọc (như thanh Extensions)."""
        if mode == _FILTER_INSTALLED and not self._satisfied:
            return False
        if mode == _FILTER_MISSING and self._satisfied:
            return False
        if mode == _FILTER_INSTALLABLE and not (
            (not self._satisfied) and self.requirement.is_installable
        ):
            return False
        if not needle:
            return True
        haystack = f"{self.requirement.name} {self.requirement.key} {self.requirement.hint}".lower()
        return needle in haystack


class EnvironmentListDialog(CustomDialog):
    """Liệt kê toàn bộ thành phần môi trường: đã cài / chưa cài.

    Tín hiệu :attr:`install_requested` mang danh sách :class:`Requirement` mà
    người dùng muốn cài; ``MainWindow`` nối tín hiệu này vào
    :class:`~environment_setup.EnvironmentInstaller` để chạy shell.
    """

    install_requested = Signal(object)

    def __init__(
        self,
        parent=None,
        *,
        requirements=None,
        auto_scan: bool = True,
        title: str = "Môi trường & thư viện",
    ) -> None:
        super().__init__(title, parent=parent, width=780, height=620, resizable=True)
        self._requirements: tuple[Requirement, ...] = tuple(
            requirements if requirements is not None else all_requirements()
        )
        self._rows: list[_EnvRow] = []

        self._build_header()
        self._build_list()
        if auto_scan:
            self.scan()

    # ------------------------------------------------------------------- UI

    def _build_header(self) -> None:
        intro = QLabel(
            "Danh sách đầy đủ mọi thư viện, công cụ và SDK mà VXPEngine dùng. "
            "Huy hiệu bên phải cho biết thành phần nào đã có trên máy và thành "
            "phần nào còn thiếu — giống khung Extensions của VS Code."
        )
        intro.setObjectName("EnvIntro")
        intro.setWordWrap(True)
        self.add_body_widget(intro)

        search_row = QWidget()
        search_layout = QHBoxLayout(search_row)
        search_layout.setContentsMargins(0, 0, 0, 0)
        search_layout.setSpacing(8)

        self.search_edit = QLineEdit()
        self.search_edit.setObjectName("EnvSearch")
        self.search_edit.setPlaceholderText("Tìm thành phần môi trường…")
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.textChanged.connect(self._apply_filter)
        search_layout.addWidget(self.search_edit, 1)

        self.filter_combo = QComboBox()
        self.filter_combo.setObjectName("EnvFilterCombo")
        for label, data in (
            ("Tất cả", _FILTER_ALL),
            ("Đã cài đặt", _FILTER_INSTALLED),
            ("Chưa cài đặt", _FILTER_MISSING),
            ("Có thể cài tự động", _FILTER_INSTALLABLE),
        ):
            self.filter_combo.addItem(label, data)
        self.filter_combo.currentIndexChanged.connect(self._apply_filter)
        search_layout.addWidget(self.filter_combo)
        self.add_body_widget(search_row)

        self.summary_label = QLabel("Đang kiểm tra…")
        self.summary_label.setObjectName("EnvSummary")
        self.summary_label.setWordWrap(True)
        self.add_body_widget(self.summary_label)

    def _build_list(self) -> None:
        self.scroll = QScrollArea()
        self.scroll.setObjectName("EnvListScroll")
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.list_widget = QWidget()
        self.list_widget.setObjectName("EnvList")
        self.list_layout = QVBoxLayout(self.list_widget)
        self.list_layout.setContentsMargins(0, 0, 4, 0)
        self.list_layout.setSpacing(6)
        self.list_layout.addStretch(1)
        self.scroll.setWidget(self.list_widget)
        self.add_body_widget(self.scroll, 1)

        self.empty_label = QLabel("Không có thành phần nào khớp với bộ lọc.")
        self.empty_label.setObjectName("EnvEmpty")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.empty_label.hide()
        self.add_body_widget(self.empty_label, 1)

        for requirement in self._requirements:
            row = _EnvRow(requirement, satisfied=False)
            row.toggled.connect(self._refresh_footer)
            row.install_requested.connect(self._install_one)
            self._rows.append(row)
            # Chèn trước stretch để các dòng dính lên trên.
            self.list_layout.insertWidget(self.list_layout.count() - 1, row)

        self.rescan_button = self.add_footer_button("Kiểm tra lại", icon_name="fa5s.redo")
        self.rescan_button.clicked.connect(self.scan)
        self.install_button = self.add_footer_button("Cài đặt", accent=True, icon_name="fa5s.download")
        self.install_button.clicked.connect(self._install_selected)
        self.close_button = self.add_footer_button("Đóng", ghost=True, icon_name="fa5s.times")
        self.close_button.clicked.connect(self.reject)

    # ---------------------------------------------------------------- quét

    def scan(self) -> None:
        """Quét lại từng thành phần và cập nhật huy hiệu / tóm tắt."""
        for row in self._rows:
            row.refresh(row.requirement.satisfied)
        self._apply_filter()
        self._refresh_footer()

    @property
    def missing(self) -> list[Requirement]:
        return [row.requirement for row in self._rows if not row.satisfied]

    @property
    def all_ready(self) -> bool:
        return not self.missing

    def _apply_filter(self) -> None:
        needle = self.search_edit.text().strip().lower()
        mode = self.filter_combo.currentData() or _FILTER_ALL
        shown = 0
        for row in self._rows:
            visible = row.matches(needle, mode)
            row.setVisible(visible)
            shown += 1 if visible else 0
        self.empty_label.setVisible(shown == 0)
        self.scroll.setVisible(shown != 0)
        self._update_summary(shown)

    def _update_summary(self, shown: int) -> None:
        total = len(self._rows)
        installed = sum(1 for row in self._rows if row.satisfied)
        missing = total - installed
        installable_count = sum(
            1 for row in self._rows
            if (not row.satisfied) and row.requirement.is_installable
        )
        if missing == 0:
            text = f"✅ Đã cài đặt {installed}/{total} — môi trường đầy đủ, không cần cập nhật."
        else:
            text = (
                f"Đã cài đặt {installed}/{total} · Chưa có {missing}"
                + (f" ({installable_count} cái có thể cài tự động)" if installable_count else "")
            )
        if shown != total:
            text += f" · Đang lọc {shown}/{total}"
        self.summary_label.setText(text)

    # ---------------------------------------------------------------- cài

    def _refresh_footer(self) -> None:
        selected = [row for row in self._rows if row.selected]
        self.install_button.setEnabled(bool(selected))
        self.install_button.setText(
            f"Cài đặt ({len(selected)})" if selected else "Cài đặt"
        )

    def _selected_requirements(self) -> list[Requirement]:
        return [row.requirement for row in self._rows if row.selected]

    def _install_selected(self) -> None:
        items = self._selected_requirements()
        if not items:
            return
        self.install_requested.emit(items)
        self.accept()

    def _install_one(self, requirement: Requirement) -> None:
        self.install_requested.emit([requirement])
        self.accept()
