"""Qt-based installer cho môi trường VXPEngine.

Detection & danh sách thành phần nằm ở :mod:`app.environment_spec` (không phụ
thuộc Qt) — file này chỉ chứa :class:`EnvironmentInstaller` chạy các lệnh cài
bằng :class:`QProcess` và phát log từng dòng qua tín hiệu Qt.

Không có gì ở đây tự chạy khi import: mọi lệnh cài đều phải do người dùng
xác nhận qua giao diện.

Re-export từ :mod:`app.environment_spec` để giữ tương thích ngược với các
import cũ (``from environment_setup import Requirement``, v.v.).
"""
from __future__ import annotations

from typing import Iterable

from PySide6.QtCore import QObject, QProcess, QProcessEnvironment, Signal

# Import kép: ``app/main.py`` được chạy dưới dạng script
# (``python app/main.py``) nên sys.path[0] là ``app/`` — mọi module app được
# import **phẳng** (``from environment_setup import ...``), khi đó relative
# import nổ "no known parent package". Ngược lại khi import dưới dạng package
# (``from app.environment_setup import ...``, dùng trong test) thì cần relative.
# Thử relative trước, rớt xuống absolute để chạy được cả hai kiểu.
try:  # package context: app.environment_setup
    from .environment_spec import (  # noqa: F401  (re-export)
        MSYS2_ROOT,
        REQUIREMENTS,
        Requirement,
        all_requirements,
        detect_missing,
        installable,
        winget_path,
    )
except ImportError:  # script context: top-level environment_setup
    from environment_spec import (  # type: ignore[no-redef]  # noqa: F401
        MSYS2_ROOT,
        REQUIREMENTS,
        Requirement,
        all_requirements,
        detect_missing,
        installable,
        winget_path,
    )


class EnvironmentInstaller(QObject):
    """Chạy nối tiếp các lệnh cài môi trường, phát log từng dòng."""

    log = Signal(str)                       # một dòng output
    step_started = Signal(str, int, int)    # tên gói, số thứ tự (1-based), tổng số
    step_finished = Signal(str, int)        # tên gói, exit code
    finished = Signal(bool, object)         # ok?, [(name, exit_code), ...]

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._queue: list[tuple[Requirement, list[str]]] = []
        self._results: list[tuple[str, int]] = []
        self._current: Requirement | None = None
        self._running = False

        self._process = QProcess(self)
        self._process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self._process.setProcessEnvironment(QProcessEnvironment.systemEnvironment())
        self._process.readyReadStandardOutput.connect(self._read_output)
        self._process.finished.connect(self._step_finished)

    @property
    def is_running(self) -> bool:
        return self._running

    def install(self, items: Iterable[Requirement]) -> bool:
        """Bắt đầu cài các thành phần còn thiếu. False khi không có gì để chạy."""
        if self._running:
            self.log.emit("[Setup] Đang có tiến trình cài đặt khác.")
            return False
        queue: list[tuple[Requirement, list[str]]] = []
        for item in items:
            command = item.command()
            if not command:
                self.log.emit(
                    f"[Setup] ⚠ Bỏ qua {item.name}: "
                    f"{item.hint or 'không có lệnh cài tự động.'}"
                )
                continue
            queue.append((item, list(command)))
        if not queue:
            self.log.emit("[Setup] Không có gói nào có thể cài tự động.")
            self.finished.emit(False, [])
            return False

        self._queue = queue
        self._results = []
        self._running = True
        self._start_next()
        return True

    def stop(self) -> None:
        if self._running and self._process.state() != QProcess.ProcessState.NotRunning:
            self.log.emit("[Setup] Đang dừng tiến trình cài đặt…")
            self._queue.clear()
            self._process.kill()

    # ------------------------------------------------------------- internal

    def _start_next(self) -> None:
        if not self._queue:
            self._running = False
            self._current = None
            ok = all(code == 0 for _name, code in self._results)
            self.finished.emit(ok, list(self._results))
            return
        item, command = self._queue.pop(0)
        self._current = item
        done = len(self._results) + 1
        total = done + len(self._queue)
        self.step_started.emit(item.name, done, total)
        self.log.emit(f"[Setup] ▶ ({done}/{total}) {item.name}")
        program, args = command[0], command[1:]
        self.log.emit(f"[Setup]   $ {program} {' '.join(args)}".rstrip())
        self._process.start(program, args)

    def _read_output(self) -> None:
        data = bytes(self._process.readAllStandardOutput()).decode("utf-8", "replace")
        for line in data.splitlines():
            line = line.rstrip()
            if line:
                self.log.emit(f"[Setup]   {line}")

    def _step_finished(self, code: int, _status) -> None:
        item = self._current
        name = item.name if item is not None else "?"
        self._results.append((name, int(code)))
        self.step_finished.emit(name, int(code))
        if code == 0:
            self.log.emit(f"[Setup] ✓ {name}")
        else:
            hint = item.hint if item is not None else ""
            self.log.emit(
                f"[Setup] ✗ {name} (mã {code})"
                + (f" — {hint}" if hint else "")
            )
        self._current = None
        self._start_next()
