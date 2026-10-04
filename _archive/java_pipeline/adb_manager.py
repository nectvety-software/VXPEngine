"""ADB device discovery helpers for USB/Type-C Android deployment."""
from __future__ import annotations

import os
import re
import shutil
from pathlib import Path

from PySide6.QtCore import QObject, QProcess, QProcessEnvironment, Signal


class AdbDeviceManager(QObject):
    devices_changed = Signal(list)
    output = Signal(str)
    error = Signal(str)
    busy_changed = Signal(bool)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._project_root: Path | None = None
        self._devices: list[dict] = []
        self.process = QProcess(self)
        self.process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self.process.readyReadStandardOutput.connect(self._read_output)
        self.process.finished.connect(self._finished)
        self.process.errorOccurred.connect(self._process_error)
        self._buffer = ""
        self._mode = ""

    @property
    def devices(self) -> list[dict]:
        return [dict(item) for item in self._devices]

    @staticmethod
    def find_adb(project_root: str | Path | None = None) -> str | None:
        executable = "adb.exe" if os.name == "nt" else "adb"
        candidates: list[Path] = []

        for variable in ("ANDROID_SDK_ROOT", "ANDROID_HOME"):
            value = os.environ.get(variable, "").strip()
            if value:
                candidates.append(Path(value) / "platform-tools" / executable)

        if project_root:
            local_properties = Path(project_root).expanduser().resolve() / "local.properties"
            try:
                text = local_properties.read_text(encoding="utf-8", errors="replace")
            except OSError:
                text = ""
            match = re.search(r"(?m)^sdk\.dir\s*=\s*(.+?)\s*$", text)
            if match:
                raw = match.group(1).replace("\\\\", "\\").replace("\\:", ":")
                candidates.append(Path(raw) / "platform-tools" / executable)

        if os.name == "nt":
            local_app_data = os.environ.get("LOCALAPPDATA", "").strip()
            if local_app_data:
                candidates.append(Path(local_app_data) / "Android" / "Sdk" / "platform-tools" / executable)
            user_profile = os.environ.get("USERPROFILE", "").strip()
            if user_profile:
                candidates.append(Path(user_profile) / "AppData" / "Local" / "Android" / "Sdk" / "platform-tools" / executable)

        which = shutil.which("adb")
        if which:
            candidates.insert(0, Path(which))

        seen: set[str] = set()
        for candidate in candidates:
            try:
                resolved = candidate.expanduser().resolve()
            except OSError:
                continue
            key = str(resolved).lower()
            if key in seen:
                continue
            seen.add(key)
            if resolved.is_file():
                return str(resolved)
        return None

    def refresh(self, project_root: str | Path | None = None) -> bool:
        if self.process.state() != QProcess.ProcessState.NotRunning:
            return False
        self._project_root = Path(project_root).resolve() if project_root else None
        adb = self.find_adb(self._project_root)
        if not adb:
            self._devices = []
            self.devices_changed.emit([])
            self.error.emit(
                "Không tìm thấy adb. Hãy cài Android SDK Platform-Tools hoặc đặt ANDROID_SDK_ROOT/ANDROID_HOME."
            )
            return False
        self._buffer = ""
        self._mode = "devices"
        self.process.setProgram(adb)
        self.process.setArguments(["devices", "-l"])
        self.process.setProcessEnvironment(QProcessEnvironment.systemEnvironment())
        self.busy_changed.emit(True)
        self.output.emit(f"[ADB] Đang quét thiết bị bằng: {adb}")
        self.process.start()
        return True

    def restart_server(self, project_root: str | Path | None = None) -> bool:
        if self.process.state() != QProcess.ProcessState.NotRunning:
            return False
        self._project_root = Path(project_root).resolve() if project_root else None
        adb = self.find_adb(self._project_root)
        if not adb:
            self.error.emit("Không tìm thấy adb để khởi động lại ADB server.")
            return False
        self._buffer = ""
        self._mode = "restart"
        self.process.setProgram(adb)
        self.process.setArguments(["kill-server"])
        self.process.setProcessEnvironment(QProcessEnvironment.systemEnvironment())
        self.busy_changed.emit(True)
        self.output.emit("[ADB] Đang khởi động lại ADB server…")
        self.process.start()
        return True

    def _read_output(self) -> None:
        data = bytes(self.process.readAllStandardOutput())
        text = data.decode("utf-8", errors="replace").replace("\r\n", "\n")
        self._buffer += text
        if text.strip():
            self.output.emit(text.rstrip("\n"))

    def _finished(self, exit_code: int, _status: QProcess.ExitStatus) -> None:
        self.busy_changed.emit(False)
        if self._mode == "devices":
            devices = self._parse_devices(self._buffer)
            self._devices = devices
            self.devices_changed.emit(self.devices)
            self.output.emit(f"[ADB] Tìm thấy {len(devices)} thiết bị/giả lập.")
        elif self._mode == "restart":
            if exit_code == 0:
                adb = self.find_adb(self._project_root)
                if adb:
                    self._mode = "start"
                    self._buffer = ""
                    self.process.setProgram(adb)
                    self.process.setArguments(["start-server"])
                    self.busy_changed.emit(True)
                    self.process.start()
                    return
            else:
                self.error.emit(f"ADB server không thể dừng, mã {exit_code}.")
        elif self._mode == "start":
            if exit_code == 0:
                self.output.emit("[ADB] ADB server đã sẵn sàng.")
                self.refresh(self._project_root)
            else:
                self.error.emit(f"ADB server không thể khởi động, mã {exit_code}.")
        self._mode = ""

    @staticmethod
    def _parse_devices(text: str) -> list[dict]:
        result: list[dict] = []
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("List of devices") or line.startswith("*"):
                continue
            parts = line.split()
            if len(parts) < 2:
                continue
            serial, state = parts[0], parts[1]
            details: dict[str, str] = {}
            for token in parts[2:]:
                if ":" in token:
                    key, value = token.split(":", 1)
                    details[key] = value
            model = details.get("model", "").replace("_", " ")
            product = details.get("product", "").replace("_", " ")
            display = model or product or serial
            result.append({
                "serial": serial,
                "state": state,
                "model": model,
                "product": product,
                "device": details.get("device", ""),
                "transport_id": details.get("transport_id", ""),
                "display": display,
                "raw": line,
            })
        return result

    def _process_error(self, error: QProcess.ProcessError) -> None:
        self.busy_changed.emit(False)
        name = getattr(error, "name", str(error))
        self.error.emit(f"Lỗi tiến trình ADB: {name}")
