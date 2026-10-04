"""Hộp thoại thiết lập lần đầu — tự kiểm tra môi trường rồi chạy shell cài nốt.

Chạy tự động ở lần khởi động đầu tiên (hoặc khi người dùng bấm "Chạy lại thiết
lập lần đầu…" trong menu Settings). Hộp thoại:

1. Quét môi trường ngay khi mở (không cần bấm nút).
2. Liệt kê từng thành phần: đã sẵn sàng / có thể cài tự động / cần làm thủ công.
3. Nút "Tự động cài đặt" chạy các lệnh shell nối tiếp nhau, log chảy trực tiếp
   vào hộp thoại.
4. Ghi nhận đã hoàn tất vào QSettings để không hiện lại mỗi lần mở IDE.

Không có gì tự cài nếu người dùng không bấm xác nhận.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSettings, Qt, QTimer, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from environment_setup import (
    EnvironmentInstaller,
    Requirement,
    detect_missing,
    installable,
)

from .custom_dialog import CustomDialog
from .icons import icon

SETTINGS_ORG = "VXPEngine"
SETTINGS_APP = "VXPEngine"
SETTINGS_KEY_DONE = "setup/firstRunCompleted"
SETTINGS_KEY_VERSION = "setup/firstRunVersion"


def is_first_run(current_version: str) -> bool:
    """True khi chưa từng chạy thiết lập (hoặc thiết lập ở phiên bản cũ hơn)."""
    settings = QSettings(SETTINGS_ORG, SETTINGS_APP)
    if not bool(settings.value(SETTINGS_KEY_DONE, False)):
        return True
    # Phiên bản mới có thể cần thành phần môi trường mới → nhắc lại một lần.
    return str(settings.value(SETTINGS_KEY_VERSION, "") or "") != str(current_version)


def mark_setup_done(current_version: str) -> None:
    settings = QSettings(SETTINGS_ORG, SETTINGS_APP)
    settings.setValue(SETTINGS_KEY_DONE, True)
    settings.setValue(SETTINGS_KEY_VERSION, str(current_version))


def reset_setup_flag() -> None:
    """Dùng khi cần chạy lại thiết lập từ đầu."""
    settings = QSettings(SETTINGS_ORG, SETTINGS_APP)
    settings.remove(SETTINGS_KEY_DONE)
    settings.remove(SETTINGS_KEY_VERSION)


class _RequirementRow(QFrame):
    """Một dòng trạng thái: tên thành phần + nhãn + checkbox (nếu cài được)."""

    toggled = Signal()

    def __init__(self, requirement: Requirement, satisfied: bool) -> None:
        super().__init__()
        self.requirement = requirement
        self.setObjectName("SetupRow")
        self.setProperty("satisfied", "true" if satisfied else "false")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 7, 10, 7)
        layout.setSpacing(10)

        self.check = QCheckBox()
        self.check.setChecked(not satisfied and requirement.is_installable)
        self.check.setEnabled(not satisfied and requirement.is_installable)
        self.check.setToolTip("Chọn để cài tự động")
        self.check.toggled.connect(self.toggled.emit)
        layout.addWidget(self.check)

        name = QLabel(requirement.name)
        name.setObjectName("SetupRowName")
        name.setWordWrap(True)
        layout.addWidget(name, 1)

        if satisfied:
            state_text, state_prop = "Đã có", "ok"
        elif requirement.is_installable:
            state_text, state_prop = "Có thể cài tự động", "auto"
        else:
            state_text, state_prop = "Cần làm thủ công", "manual"
        state = QLabel(state_text)
        state.setObjectName("SetupRowState")
        state.setProperty("state", state_prop)
        layout.addWidget(state)

    @property
    def selected(self) -> bool:
        return self.check.isChecked() and self.check.isEnabled()


class FirstRunDialog(CustomDialog):
    """Quét môi trường ngay khi mở; người dùng quyết định có cài hay không."""

    setup_completed = Signal(bool)

    def __init__(self, parent=None, *, force: bool = False) -> None:
        super().__init__(
            "Thiết lập VXPEngine lần đầu",
            parent=parent,
            width=640,
            height=560,
            resizable=True,
        )
        self._force = force
        self._rows: list[_RequirementRow] = []
        self._installer = EnvironmentInstaller(self)
        self._installer.log.connect(self._append_log)
        self._installer.step_started.connect(self._on_step_started)
        self._installer.finished.connect(self._on_install_finished)

        self._build_body()
        self._build_footer()

        # Quét ngay khi hộp thoại đã hiện, để người dùng thấy danh sách tức thì.
        QTimer.singleShot(0, self._scan)

    # ------------------------------------------------------------------- UI

    def _build_body(self) -> None:
        intro = QLabel(
            "VXPEngine cần một số công cụ để build và chạy ứng dụng MRE VXP.\n"
            "Dưới đây là kết quả kiểm tra máy của bạn. Những mục có thể cài tự động "
            "đã được chọn sẵn — bấm “Tự động cài đặt” để VXPEngine chạy trình cài "
            "cho bạn (có thể mất vài phút và cần quyền quản trị)."
        )
        intro.setObjectName("SetupIntro")
        intro.setWordWrap(True)
        self.add_body_widget(intro)

        self.status_label = QLabel("Đang kiểm tra môi trường…")
        self.status_label.setObjectName("SetupStatus")
        self.status_label.setWordWrap(True)
        self.add_body_widget(self.status_label)

        self.progress = QProgressBar()
        self.progress.setObjectName("SetupProgress")
        self.progress.setRange(0, 1)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(6)
        self.add_body_widget(self.progress)

        self.list_widget = QWidget()
        self.list_layout = QVBoxLayout(self.list_widget)
        self.list_layout.setContentsMargins(0, 6, 0, 6)
        self.list_layout.setSpacing(6)
        self.add_body_widget(self.list_widget, 1)

        self.log_label = QLabel("Nhật ký")
        self.log_label.setObjectName("SetupLogLabel")
        self.add_body_widget(self.log_label)

        self.log_view = QLabel("")
        self.log_view.setObjectName("SetupLog")
        self.log_view.setWordWrap(True)
        self.log_view.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.log_view.setMinimumHeight(90)
        self.log_view.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.add_body_widget(self.log_view)
        self.log_view.hide()
        self.log_label.hide()

    def _build_footer(self) -> None:
        self.skip_button = self.add_footer_button("Bỏ qua", ghost=True, icon_name="fa5s.times")
        self.skip_button.clicked.connect(self._skip)

        self.rescan_button = self.add_footer_button("Kiểm tra lại", icon_name="fa5s.redo")
        self.rescan_button.clicked.connect(self._scan)

        self.install_button = self.add_footer_button(
            "Tự động cài đặt", accent=True, icon_name="fa5s.download"
        )
        self.install_button.setEnabled(False)
        self.install_button.clicked.connect(self._install_selected)

        self.done_button = self.add_footer_button("Hoàn tất", accent=True, icon_name="fa5s.check")
        self.done_button.clicked.connect(self._finish)
        self.done_button.hide()

    # --------------------------------------------------------------- quét

    def _scan(self) -> None:
        for row in self._rows:
            row.setParent(None)
            row.deleteLater()
        self._rows.clear()

        missing = detect_missing()
        missing_keys = {item.key for item in missing}
        for requirement in _ordered_requirements():
            row = _RequirementRow(requirement, requirement.key not in missing_keys)
            row.toggled.connect(self._refresh_footer)
            self._rows.append(row)
            self.list_layout.addWidget(row)

        installable_count = len(installable(missing))
        if not missing:
            self.status_label.setText("Mọi thành phần môi trường đã sẵn sàng. Bạn có thể bắt đầu.")
        else:
            manual = len(missing) - installable_count
            parts = [f"Thiếu {len(missing)} thành phần"]
            if installable_count:
                parts.append(f"{installable_count} cái có thể cài tự động")
            if manual:
                parts.append(f"{manual} cái cần làm thủ công")
            self.status_label.setText(" · ".join(parts) + ".")
        self._refresh_footer()

    def _refresh_footer(self) -> None:
        selected = [row for row in self._rows if row.selected]
        self.install_button.setEnabled(bool(selected) and not self._installer.is_running)
        self.install_button.setText(f"Tự động cài đặt ({len(selected)})" if selected else "Tự động cài đặt")

    # ---------------------------------------------------------------- cài

    def _install_selected(self) -> None:
        selected = [row.requirement for row in self._rows if row.selected]
        if not selected:
            return
        self.log_view.show()
        self.log_label.show()
        self.log_view.setText("")
        self.install_button.setEnabled(False)
        self.skip_button.setEnabled(False)
        self.rescan_button.setEnabled(False)
        self.status_label.setText(f"Đang cài {len(selected)} thành phần — vui lòng chờ…")
        if not self._installer.install(selected):
            self.status_label.setText("Không có gói nào có thể cài tự động.")
            self._set_controls_enabled(True)

    def _on_step_started(self, name: str, done: int, total: int) -> None:
        self.progress.setRange(0, max(total, 1))
        self.progress.setValue(done - 1)
        self.status_label.setText(f"Đang cài ({done}/{total}): {name}")

    def _on_install_finished(self, ok: bool, results) -> None:
        self.progress.setValue(self.progress.maximum())
        failed = [name for name, code in results if code != 0]
        if ok:
            self.status_label.setText("Đã cài xong mọi thành phần. Mở lại VXPEngine để PATH mới có hiệu lực.")
        elif failed:
            self.status_label.setText(
                f"Hoàn tất nhưng {len(failed)} mục lỗi: {', '.join(failed)}. Xem nhật ký bên dưới."
            )
        else:
            self.status_label.setText("Quá trình cài đặt kết thúc — xem nhật ký để biết chi tiết.")
        self.install_button.hide()
        self.done_button.show()
        self._set_controls_enabled(True)
        self._scan()

    def _append_log(self, line: str) -> None:
        existing = self.log_view.text()
        # Giữ nhật ký gọn: chỉ lưu ~200 dòng gần nhất.
        lines = (existing.split("\n") if existing else []) + [line]
        self.log_view.setText("\n".join(lines[-200:]))

    def _set_controls_enabled(self, enabled: bool) -> None:
        self.skip_button.setEnabled(enabled)
        self.rescan_button.setEnabled(enabled)
        self._refresh_footer()

    # -------------------------------------------------------------- kết thúc

    def _skip(self) -> None:
        self._installer.stop()
        self.reject()

    def _finish(self) -> None:
        self._installer.stop()
        mark_setup_done(_current_version())
        self.setup_completed.emit(True)
        self.accept()

    def request_close(self) -> None:
        # Đóng bằng X cũng được coi là "đã xem" để không hiện lại mãi.
        self._installer.stop()
        mark_setup_done(_current_version())
        self.setup_completed.emit(False)
        self.reject()


def _ordered_requirements():
    from environment_setup import REQUIREMENTS

    return REQUIREMENTS


def _current_version() -> str:
    try:
        from project_store import ENGINE_VERSION

        return str(ENGINE_VERSION)
    except Exception:
        return "0.0.0"
