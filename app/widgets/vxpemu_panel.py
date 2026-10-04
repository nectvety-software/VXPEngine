"""Realtime diagnostics for the separately-windowed VXPEmu runtime."""
from __future__ import annotations

import re
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPlainTextEdit, QTabWidget, QToolButton,
    QVBoxLayout, QWidget,
)

from .icons import icon


class VxpEmuPanel(QWidget):
    """Shows telemetry emitted by the real Unicorn-backed VXPEmu process."""

    run_requested = Signal()
    stop_requested = Signal()
    log_message = Signal(str)
    _FIELD = re.compile(r"([a-zA-Z][a-zA-Z0-9_]*)=([^\s]*)")

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("VxpEmuDiagnostics")
        self._artifact: Path | None = None
        self._last_telemetry: dict[str, str] = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 6, 8, 8)
        root.setSpacing(6)

        bar = QHBoxLayout()
        title = QLabel("VXPEmu · ARM diagnostics")
        title.setStyleSheet("font-weight:700;color:#dce7f7")
        bar.addWidget(title)
        self.run_button = QToolButton()
        self.run_button.setText("Chạy cửa sổ VXPEmu")
        self.run_button.setIcon(icon("fa5s.external-link-alt", "#57d38c"))
        self.run_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.run_button.clicked.connect(self.run_requested)
        bar.addWidget(self.run_button)
        self.stop_button = QToolButton()
        self.stop_button.setText("Dừng")
        self.stop_button.setIcon(icon("fa5s.stop", "#f08a91"))
        self.stop_button.setEnabled(False)
        self.stop_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.stop_button.clicked.connect(self.stop_requested)
        bar.addWidget(self.stop_button)
        self.status = QLabel("Chưa chạy")
        self.status.setStyleSheet("color:#8191aa")
        bar.addWidget(self.status, 1, Qt.AlignmentFlag.AlignRight)
        root.addLayout(bar)

        metrics = QFrame()
        metrics.setObjectName("VxpEmuMetrics")
        metrics.setStyleSheet(
            "#VxpEmuMetrics{background:#101722;border:1px solid #27344a;border-radius:6px}"
        )
        metric_layout = QHBoxLayout(metrics)
        metric_layout.setContentsMargins(10, 5, 10, 5)
        self.cpu_metric = self._metric("CPU", "--")
        self.fps_metric = self._metric("FPS", "--")
        self.memory_metric = self._metric("MEMORY", "--")
        self.pc_metric = self._metric("PC", "--------")
        for widget in (self.cpu_metric, self.fps_metric, self.memory_metric, self.pc_metric):
            metric_layout.addWidget(widget, 1)
        root.addWidget(metrics)

        self.views = QTabWidget()
        self.views.setDocumentMode(True)
        self.cpu_log = self._log_view("Đang chờ trạng thái thanh ghi ARM thật…")
        self.hex_log = self._log_view("Đang chờ byte mã tại địa chỉ PC…")
        self.memory_log = self._log_view("Đang chờ thông tin heap MRE…")
        self.testapi_log = self._log_view("TestAPI tự chạy sau khi VXP được nạp…")
        self.runtime_log = self._log_view("Đang chờ log runtime VXPEmu…")
        self.log = self.runtime_log
        self.views.addTab(self.cpu_log, "CPU Registers")
        self.views.addTab(self.hex_log, "Hex")
        self.views.addTab(self.memory_log, "Memory")
        self.views.addTab(self.testapi_log, "TestAPI")
        self.views.addTab(self.runtime_log, "Runtime Log")
        root.addWidget(self.views, 1)

    @staticmethod
    def _metric(name: str, value: str) -> QWidget:
        box = QWidget()
        layout = QVBoxLayout(box)
        layout.setContentsMargins(2, 0, 2, 0)
        layout.setSpacing(0)
        caption = QLabel(name)
        caption.setStyleSheet("color:#72839d;font-size:9px")
        number = QLabel(value)
        number.setStyleSheet("color:#dce7f7;font-family:'Cascadia Mono','Consolas';font-weight:600")
        layout.addWidget(caption)
        layout.addWidget(number)
        box.value_label = number
        return box

    @staticmethod
    def _log_view(placeholder: str) -> QPlainTextEdit:
        view = QPlainTextEdit()
        view.setReadOnly(True)
        view.setMaximumBlockCount(5000)
        view.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        view.setPlaceholderText(placeholder)
        view.setFont(QFont("Cascadia Mono", 9))
        return view

    def set_artifact(self, path: str | Path) -> None:
        self._artifact = Path(path)
        if not self.stop_button.isEnabled():
            self.status.setText(self._artifact.name)

    def append_log(self, text: str) -> None:
        for line in text.rstrip().splitlines():
            if "[Telemetry]" in line:
                payload = line.split("[Telemetry]", 1)[1].strip()
                self._apply_telemetry(dict(self._FIELD.findall(payload)))
                continue
            if "[TestAPI]" in line:
                self.testapi_log.appendPlainText(line)
            self.runtime_log.appendPlainText(line)

    def process_started(self, artifact: str, pid: int) -> None:
        self.set_artifact(artifact)
        self.stop_button.setEnabled(True)
        self.status.setText(f"Cửa sổ riêng đang chạy · PID {pid}")
        self.runtime_log.appendPlainText(
            f"\n=== {self._artifact.name if self._artifact else 'VXP'} · PID {pid} ==="
        )

    def process_stopped(self, code: int) -> None:
        self.stop_button.setEnabled(False)
        self.status.setText(f"Đã dừng · code {code}")

    def _apply_telemetry(self, values: dict[str, str]) -> None:
        if not values:
            return
        self._last_telemetry = values
        fps = self._float(values.get("fps"))
        cpu = self._float(values.get("cpu"))
        used = self._int(values.get("mem_used"))
        free = self._int(values.get("mem_free"))
        total = self._int(values.get("mem_total"))
        pc = self._int(values.get("pc"))
        cpsr = self._int(values.get("cpsr"))

        self.cpu_metric.value_label.setText(f"{cpu:.1f}%")
        self.fps_metric.value_label.setText(f"{fps:.1f}")
        self.memory_metric.value_label.setText(f"{used / 1024:.1f}/{total / 1024:.1f} KB")
        self.pc_metric.value_label.setText(f"0x{pc:08X}")

        registers = [self._int(values.get(f"r{i}")) for i in range(13)]
        registers.extend((self._int(values.get("sp")), self._int(values.get("lr")), pc))
        rows = []
        for start in range(0, 16, 4):
            rows.append("  ".join(
                f"R{index:02d} 0x{registers[index]:08X}" for index in range(start, start + 4)
            ))
        flags = " ".join(
            f"{name}={(cpsr >> bit) & 1}"
            for name, bit in (("N", 31), ("Z", 30), ("C", 29), ("V", 28), ("T", 5))
        )
        rows.extend(("", f"SP  0x{registers[13]:08X}    LR  0x{registers[14]:08X}",
                     f"PC  0x{pc:08X}    CPSR 0x{cpsr:08X}", flags,
                     "Nguồn: uc_reg_read trên Unicorn ARM runtime"))
        self.cpu_log.setPlainText("\n".join(rows))

        address = self._int(values.get("hex_addr"))
        try:
            raw = bytes.fromhex(values.get("hex", ""))
        except ValueError:
            raw = b""
        hex_rows = []
        for offset in range(0, len(raw), 16):
            block = raw[offset:offset + 16]
            hex_part = " ".join(f"{byte:02X}" for byte in block)
            ascii_part = "".join(chr(byte) if 32 <= byte < 127 else "." for byte in block)
            hex_rows.append(f"{address + offset:08X}  {hex_part:<47}  |{ascii_part}|")
        self.hex_log.setPlainText(
            "Byte mã thật đọc bằng uc_mem_read quanh PC\n\n" +
            ("\n".join(hex_rows) if hex_rows else "Chưa đọc được vùng nhớ tại PC.")
        )
        percent = (used * 100.0 / total) if total else 0.0
        self.memory_log.setPlainText(
            "MRE application heap (runtime thật)\n\n"
            f"Total : {total:>10} bytes  ({total / 1024:.1f} KB)\n"
            f"Used  : {used:>10} bytes  ({used / 1024:.1f} KB)\n"
            f"Free  : {free:>10} bytes  ({free / 1024:.1f} KB)\n"
            f"Usage : {percent:>9.2f}%\n\n"
            "Nguồn: App::app_memory của VXP đang chạy"
        )

    @staticmethod
    def _int(value: str | None) -> int:
        try:
            return int(value or "0", 0)
        except ValueError:
            return 0

    @staticmethod
    def _float(value: str | None) -> float:
        try:
            return float(value or "0")
        except ValueError:
            return 0.0

    def shutdown(self) -> None:
        pass
