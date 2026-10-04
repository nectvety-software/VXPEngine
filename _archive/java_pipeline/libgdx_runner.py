"""Asynchronous run/build/debug pipeline for 2Dutiful libGDX projects."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

from PySide6.QtCore import QObject, QProcess, QProcessEnvironment, QTimer, Signal

from adb_manager import AdbDeviceManager
from android_diagnostics import android_pipeline_failure_hint
from diagnostics import parse_diagnostic_line
from process_command import display_command, windows_batch_invocation
from project_store import ProjectStore


class LibGDXRunner(QObject):
    output = Signal(str)
    started = Signal(str)
    finished = Signal(int, bool)
    running_changed = Signal(bool)
    project_structure_changed = Signal(str)
    diagnostic = Signal(dict)
    artifact_found = Signal(str)
    phase_changed = Signal(str)
    debugger_output = Signal(str)
    debugger_state = Signal(str)
    environment_checked = Signal(dict)
    environment_install_completed = Signal(bool)

    DEBUG_PORT = 5005

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.process = QProcess(self)
        self.process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self.process.readyReadStandardOutput.connect(self._read_output)
        self.process.started.connect(self._process_started)
        self.process.finished.connect(self._finished)
        self.process.errorOccurred.connect(self._process_error)

        self.debugger = QProcess(self)
        self.debugger.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self.debugger.readyReadStandardOutput.connect(self._read_debugger_output)
        self.debugger.started.connect(lambda: self.debugger_state.emit("Đang kết nối JDB"))
        self.debugger.finished.connect(self._debugger_finished)
        self.debugger.errorOccurred.connect(self._debugger_error)

        self._label = ""
        self._task = ""
        self._project_root: Path | None = None
        self._debug_mode = False
        self._debug_attach_started = False
        self._debug_initialized = False
        self._debug_attach_attempts = 0
        self._pending_breakpoints: list[dict] = []
        self._output_buffer = ""
        self._pipeline_mode = ""
        self._pipeline_stage = ""
        self._android_serial = ""
        self._android_package = ""
        self._adb_path = ""
        self._android_apk: Path | None = None
        self._process_output_tail = ""
        self._environment_report: dict = {}
        self._environment_install_queue: list[tuple[str, str]] = []

    @property
    def is_running(self) -> bool:
        return (
            self.process.state() != QProcess.ProcessState.NotRunning
            or self.debugger.state() != QProcess.ProcessState.NotRunning
        )

    def run_gradle(
        self,
        project_path: str,
        task: str,
        extra_args: list[str] | None = None,
        *,
        label: str | None = None,
        debug_mode: bool = False,
        breakpoints: list[dict] | None = None,
    ) -> bool:
        root = Path(project_path).expanduser().resolve()
        self._pipeline_mode = ""
        self._pipeline_stage = ""
        if task == "android" or task.startswith("android:"):
            try:
                created, message = ProjectStore.ensure_android_module(root)
            except (OSError, ValueError) as error:
                self.output.emit(f"[2Dutiful] Không thể chuẩn bị module Android: {error}")
                return False
            self.output.emit(f"[2Dutiful] {message}")
            if created:
                self.project_structure_changed.emit(str(root))

        wrapper = root / ("gradlew.bat" if os.name == "nt" else "gradlew")
        if not wrapper.exists():
            self.output.emit("[2Dutiful] Không tìm thấy gradlew/gradlew.bat trong dự án.")
            return False
        args = [task]
        if extra_args:
            args.extend(extra_args)
        args.extend(["--console=plain", "--stacktrace"])
        self._task = task
        self._project_root = root
        self._debug_mode = debug_mode
        self._debug_attach_started = False
        self._debug_initialized = False
        self._debug_attach_attempts = 0
        self._pending_breakpoints = list(breakpoints or [])
        return self._start(root, wrapper, args, label or f"Gradle {task}")

    def run_desktop(self, project_path: str) -> bool:
        return self.run_gradle(project_path, "lwjgl3:run", label="Run Desktop (LWJGL3)")

    def debug_desktop(self, project_path: str, breakpoints: list[dict] | None = None) -> bool:
        # JavaExec supports --debug-jvm and suspends the child JVM on port 5005.
        return self.run_gradle(
            project_path,
            "lwjgl3:run",
            ["--debug-jvm", "--no-daemon"],
            label="Debug Desktop (JDWP/JDB)",
            debug_mode=True,
            breakpoints=breakpoints,
        )

    def compile_java(self, project_path: str) -> bool:
        # lwjgl3:classes also depends on core compilation, so this validates the
        # shared gameplay code and the desktop launcher in one task.
        return self.run_gradle(
            project_path,
            "lwjgl3:classes",
            label="Compile Java (core + lwjgl3)",
        )

    def build_desktop_jad(self, project_path: str) -> bool:
        """Build the desktop JAR, then generate a companion .jad descriptor."""
        started = self.run_gradle(project_path, "lwjgl3:dist", label="Desktop JAR + JAD")
        if started:
            self._pipeline_mode = "desktop_jad"
        return started


    def run_android_device(
        self,
        project_path: str,
        serial: str,
        package_name: str,
        device_label: str = "Android device",
    ) -> bool:
        """Build, install and launch the debug APK on one selected ADB device."""
        root = Path(project_path).expanduser().resolve()
        if self.is_running:
            self.output.emit("[2Dutiful] Một tiến trình run/build/debug khác đang hoạt động.")
            return False
        try:
            created, message = ProjectStore.ensure_android_module(root)
        except (OSError, ValueError) as error:
            self.output.emit(f"[ADB] Không thể chuẩn bị module Android: {error}")
            return False
        self.output.emit(f"[ADB] {message}")
        if created:
            self.project_structure_changed.emit(str(root))

        wrapper = root / ("gradlew.bat" if os.name == "nt" else "gradlew")
        if not wrapper.exists():
            self.output.emit("[ADB] Không tìm thấy Gradle wrapper trong dự án.")
            return False
        adb = AdbDeviceManager.find_adb(root)
        if not adb:
            self.output.emit(
                "[ADB] Không tìm thấy adb. Cài Android SDK Platform-Tools hoặc đặt ANDROID_SDK_ROOT."
            )
            return False
        if not serial.strip():
            self.output.emit("[ADB] Chưa chọn thiết bị Android.")
            return False
        try:
            state_check = subprocess.run(
                [adb, "-s", serial.strip(), "get-state"],
                capture_output=True,
                text=True,
                timeout=4,
                check=False,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
        except (OSError, subprocess.SubprocessError) as error:
            self.output.emit(f"[ADB] Không thể kiểm tra trạng thái thiết bị: {error}")
            return False
        device_state = state_check.stdout.strip().lower()
        if state_check.returncode != 0 or device_state != "device":
            details = (state_check.stderr or state_check.stdout).strip()
            hint = android_pipeline_failure_hint(details or device_state, "preflight")
            self.output.emit(f"[ADB] Thiết bị {serial.strip()} chưa sẵn sàng ({device_state or 'không phản hồi'}).")
            if hint:
                self.output.emit(f"[ADB] Gợi ý: {hint}")
            return False

        self._task = "android:runDevice"
        self._project_root = root
        self._debug_mode = False
        self._pipeline_mode = "android_device"
        self._pipeline_stage = "build"
        self._android_serial = serial.strip()
        self._android_package = package_name.strip()
        self._adb_path = adb
        self._android_apk = None
        label = f"Run Android • {device_label}"
        return self._start(
            root,
            wrapper,
            ["android:assembleDebug", "--console=plain", "--stacktrace"],
            label,
        )

    def run_native_windows(self, project_path: str) -> bool:
        root = Path(project_path).expanduser().resolve()
        script = root / "native" / "build_native_windows.bat"
        if not script.exists():
            self.output.emit("[2Dutiful] Dự án không bật module C/C++ native.")
            return False
        self._task = "native"
        self._project_root = root
        self._debug_mode = False
        self._pipeline_mode = ""
        self._pipeline_stage = ""
        return self._start(root / "native", script, [], "CMake Native Windows")

    def check_environment(self, project_path: str) -> bool:
        root = Path(project_path).expanduser().resolve()
        wrapper = root / ("gradlew.bat" if os.name == "nt" else "gradlew")
        tools = {
            "java": shutil.which("java"),
            "javac": shutil.which("javac"),
            "jdb": self._find_jdb(),
            "gradle_wrapper": str(wrapper) if wrapper.exists() else None,
            "adb": AdbDeviceManager.find_adb(root),
            "cmake": shutil.which("cmake"),
            "ninja": shutil.which("ninja"),
        }
        required = ("java", "javac", "jdb", "gradle_wrapper")
        self._environment_report = {
            "tools": tools,
            "missing_required": [name for name in required if not tools[name]],
            "missing_optional": [name for name in ("adb", "cmake", "ninja") if not tools[name]],
            "gradle_ok": False,
        }
        self._task = "environment"
        self._project_root = root
        self._debug_mode = False
        self._pipeline_mode = ""
        self._pipeline_stage = ""
        if not wrapper.exists():
            self.started.emit("Kiểm tra môi trường / thư viện")
            self.output.emit("\n[Environment] Kiểm tra công cụ phát triển")
            for name, path in tools.items():
                state = "OK" if path else "THIẾU"
                self.output.emit(f"[Environment] {name:<14} [{state}] {path or 'Không tìm thấy'}")
            self.output.emit("[Environment] Không có Gradle wrapper để kiểm tra phiên bản.")
            QTimer.singleShot(0, lambda: self.environment_checked.emit(dict(self._environment_report)))
            return False
        started = self._start(root, wrapper, ["--version"], "Kiểm tra môi trường / thư viện")
        self.output.emit("\n[Environment] Kiểm tra công cụ phát triển")
        for name, path in tools.items():
            state = "OK" if path else "THIẾU"
            self.output.emit(f"[Environment] {name:<14} [{state}] {path or 'Không tìm thấy'}")
        return started

    @staticmethod
    def environment_install_packages(report: dict) -> list[tuple[str, str]]:
        """Map missing tools to conservative winget packages without duplicates."""
        missing = set(report.get("missing_required", [])) | set(report.get("missing_optional", []))
        packages: list[tuple[str, str]] = []
        if missing & {"java", "javac", "jdb"}:
            packages.append(("JDK 17", "EclipseAdoptium.Temurin.17.JDK"))
        if "adb" in missing:
            packages.append(("Android Platform Tools", "Google.PlatformTools"))
        if "cmake" in missing:
            packages.append(("CMake", "Kitware.CMake"))
        if "ninja" in missing:
            packages.append(("Ninja", "Ninja-build.Ninja"))
        return packages

    def install_environment(self, report: dict) -> bool:
        if self.is_running:
            return False
        winget = shutil.which("winget")
        packages = self.environment_install_packages(report)
        if not winget or not packages:
            return False
        self._environment_install_queue = list(packages)
        self._task = "environment_install"
        self._project_root = Path.cwd()
        self._label = "Cài đặt môi trường lập trình"
        self._pipeline_mode = "environment_install"
        self.started.emit(self._label)
        self.running_changed.emit(True)
        self.output.emit("\n[Environment] Bắt đầu cài đặt ẩn bằng Windows Package Manager.")
        self._start_next_environment_package(Path(winget))
        return True

    def _start_next_environment_package(self, winget: Path) -> None:
        name, package_id = self._environment_install_queue[0]
        args = [
            "install", "--id", package_id, "--exact", "--silent",
            "--accept-package-agreements", "--accept-source-agreements",
        ]
        self.phase_changed.emit(f"Cài {name}")
        self.output.emit(f"[Environment] Cài {name} ({package_id})…")
        self.process.setProcessEnvironment(QProcessEnvironment.systemEnvironment())
        self.process.setWorkingDirectory(str(Path.home()))
        self.process.setProgram(str(winget))
        self.process.setArguments(args)
        self._output_buffer = ""
        self._process_output_tail = ""
        self.process.start()

    def debug_command(self, command: str) -> bool:
        if self.debugger.state() == QProcess.ProcessState.NotRunning:
            self.debugger_output.emit("[JDB] Chưa có phiên debug đang kết nối.\n")
            return False
        mapping = {
            "continue": "cont",
            "pause": "suspend",
            "step_over": "next",
            "step_into": "step",
            "step_out": "step up",
            "stack": "where",
            "locals": "locals",
            "threads": "threads",
        }
        actual = mapping.get(command, command).strip()
        if not actual:
            return False
        self.debugger.write((actual + "\n").encode("utf-8"))
        self.debugger_output.emit(f"> {actual}\n")
        return True

    def stop(self) -> None:
        if not self.is_running:
            return
        self.output.emit("[2Dutiful] Đang dừng toàn bộ tiến trình con...")
        for process in (self.debugger, self.process):
            if process.state() == QProcess.ProcessState.NotRunning:
                continue
            pid = int(process.processId())
            if os.name == "nt" and pid > 0:
                try:
                    subprocess.run(
                        ["taskkill", "/PID", str(pid), "/T", "/F"],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        timeout=4,
                        check=False,
                        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                    )
                except (OSError, subprocess.SubprocessError):
                    process.kill()
            else:
                process.terminate()
                if not process.waitForFinished(1800):
                    process.kill()
        self.debugger_state.emit("Debugger đã dừng")

    def _start(self, working_dir: Path, executable: Path, args: list[str], label: str) -> bool:
        if self.is_running:
            self.output.emit("[2Dutiful] Một tiến trình run/build/debug khác đang hoạt động.")
            return False
        if not executable.exists():
            self.output.emit(f"[2Dutiful] Không tìm thấy: {executable}")
            return False

        environment = QProcessEnvironment.systemEnvironment()
        current_options = environment.value("JAVA_TOOL_OPTIONS", "").strip()
        encoding_option = "-Dfile.encoding=UTF-8"
        environment.insert("JAVA_TOOL_OPTIONS", f"{current_options} {encoding_option}".strip())
        environment.insert("GRADLE_OPTS", "-Dorg.gradle.console=plain")
        self.process.setProcessEnvironment(environment)
        self.process.setWorkingDirectory(str(working_dir))
        self._label = label
        self._output_buffer = ""
        self._process_output_tail = ""

        if os.name == "nt" and executable.suffix.lower() in {".bat", ".cmd"}:
            # QProcess already quotes every argument for CreateProcess(). Passing a
            # second, pre-quoted command string to ``cmd /s /c`` makes paths with
            # spaces arrive as a literal value such as \"C:\\My Project\\gradlew.bat\".
            # CMD then reports that the quoted text is not a command. Run the batch
            # file through the internal ``call`` command instead, with each token
            # supplied separately. Because the working directory is the script's
            # directory for all engine tasks, a relative script name also avoids
            # quoting the project path completely.
            comspec = environment.value("ComSpec", "").strip() or None
            program, process_args = windows_batch_invocation(
                working_dir,
                executable,
                args,
                comspec=comspec,
            )
            self.process.setProgram(program)
            self.process.setArguments(process_args)
        else:
            self.process.setProgram(str(executable))
            self.process.setArguments(args)

        self.phase_changed.emit("Đang khởi động")
        self.started.emit(label)
        self.output.emit(f"\n[2Dutiful] Bắt đầu: {label}")
        self.output.emit(f"[2Dutiful] Thư mục: {working_dir}")
        shown_command = display_command(executable, args)
        self.output.emit(f"[2Dutiful] Lệnh: {shown_command}")
        self.process.start()
        return True

    def _process_started(self) -> None:
        self.running_changed.emit(True)
        if self._pipeline_mode == "android_device" and self._pipeline_stage == "install":
            self.phase_changed.emit("Cài APK qua ADB")
        elif self._pipeline_mode == "android_device" and self._pipeline_stage == "launch":
            self.phase_changed.emit("Khởi chạy trên thiết bị")
        else:
            self.phase_changed.emit("Đang chạy")
        if self._debug_mode:
            self.debugger_state.emit(f"Chờ JVM tại cổng {self.DEBUG_PORT}")
            # Fallback attach: some Gradle versions do not print the listening line
            # immediately, but the JavaExec debug server is normally ready soon.
            QTimer.singleShot(2200, self._attach_jdb)

    def _read_output(self) -> None:
        data = bytes(self.process.readAllStandardOutput())
        text = data.decode("utf-8", errors="replace").replace("\r\n", "\n")
        if not text:
            return
        self.output.emit(text.rstrip("\n"))
        self._process_output_tail = (self._process_output_tail + text)[-50000:]
        self._output_buffer += text
        lines = self._output_buffer.split("\n")
        self._output_buffer = lines.pop() if lines else ""
        for line in lines:
            diagnostic = parse_diagnostic_line(line, self._project_root)
            if diagnostic:
                self.diagnostic.emit(diagnostic.to_dict())
            lowered = line.lower()
            if self._debug_mode and (
                "listening for transport dt_socket" in lowered
                or f"address: {self.DEBUG_PORT}" in lowered
            ):
                QTimer.singleShot(100, self._attach_jdb)
            if line.startswith("> Task"):
                self.phase_changed.emit(line.replace("> Task", "").strip())

    def _attach_jdb(self) -> None:
        if not self._debug_mode or self._debug_attach_started:
            return
        if self.process.state() == QProcess.ProcessState.NotRunning:
            return
        jdb = self._find_jdb()
        if not jdb:
            self.debugger_output.emit(
                "[JDB] Không tìm thấy jdb. Hãy cài JDK 17 đầy đủ và đặt JAVA_HOME/PATH.\n"
            )
            self.debugger_state.emit("Thiếu JDB")
            return
        self._debug_attach_started = True
        self._debug_attach_attempts += 1
        self.debugger.setWorkingDirectory(str(self._project_root or Path.cwd()))
        env = QProcessEnvironment.systemEnvironment()
        self.debugger.setProcessEnvironment(env)
        source_path = ""
        if self._project_root:
            source_path = str(self._project_root / "core" / "src" / "main" / "java")
        args = ["-attach", str(self.DEBUG_PORT)]
        if source_path:
            args.extend(["-sourcepath", source_path])
        self.debugger.setProgram(jdb)
        self.debugger.setArguments(args)
        self.debugger_output.emit(
            f"[JDB] Kết nối tới localhost:{self.DEBUG_PORT} (lần {self._debug_attach_attempts})...\n"
        )
        self.debugger.start()
        QTimer.singleShot(1300, self._initialize_debug_session)

    def _initialize_debug_session(self) -> None:
        if self.debugger.state() == QProcess.ProcessState.NotRunning or self._debug_initialized:
            return
        self._debug_initialized = True
        for breakpoint in self._pending_breakpoints:
            class_name = str(breakpoint.get("class", "")).strip()
            try:
                line = int(breakpoint.get("line", 0))
            except (TypeError, ValueError):
                line = 0
            if class_name and line > 0:
                command = f"stop at {class_name}:{line}"
                self.debugger.write((command + "\n").encode("utf-8"))
                self.debugger_output.emit(f"> {command}\n")
        self.debugger.write(b"cont\n")
        self.debugger_output.emit("> cont\n")
        self.debugger_state.emit("Đang debug")

    def _read_debugger_output(self) -> None:
        data = bytes(self.debugger.readAllStandardOutput())
        text = data.decode("utf-8", errors="replace").replace("\r\n", "\n")
        if text:
            self.debugger_output.emit(text)

    def _debugger_finished(self, _exit_code: int, _exit_status: QProcess.ExitStatus) -> None:
        if (
            self._debug_mode
            and not self._debug_initialized
            and self.process.state() != QProcess.ProcessState.NotRunning
            and self._debug_attach_attempts < 15
        ):
            self._debug_attach_started = False
            self.debugger_state.emit("Chờ JVM Debug — đang thử kết nối lại")
            QTimer.singleShot(700, self._attach_jdb)
            return
        self.debugger_state.emit("Debugger đã dừng")

    @staticmethod
    def _find_jdb() -> str | None:
        java_home = os.environ.get("JAVA_HOME", "").strip()
        if java_home:
            candidate = Path(java_home) / "bin" / ("jdb.exe" if os.name == "nt" else "jdb")
            if candidate.exists():
                return str(candidate)
        return shutil.which("jdb")

    def _finished(self, exit_code: int, _exit_status: QProcess.ExitStatus) -> None:
        if self._output_buffer.strip():
            diagnostic = parse_diagnostic_line(self._output_buffer, self._project_root)
            if diagnostic:
                self.diagnostic.emit(diagnostic.to_dict())
            self._output_buffer = ""

        success = exit_code == 0
        if self._pipeline_mode == "environment_install":
            if not success:
                name = self._environment_install_queue[0][0] if self._environment_install_queue else "môi trường"
                self.output.emit(f"[Environment] Không thể cài {name}, mã thoát {exit_code}.")
                self._environment_install_queue.clear()
                self.environment_install_completed.emit(False)
                self._finalize_task(exit_code, False)
                return
            if self._environment_install_queue:
                completed_name, _package_id = self._environment_install_queue.pop(0)
                self.output.emit(f"[Environment] Đã cài/cập nhật {completed_name}.")
            if self._environment_install_queue:
                winget = shutil.which("winget")
                if winget:
                    self._start_next_environment_package(Path(winget))
                    return
            self.environment_install_completed.emit(True)
            self._finalize_task(0, True)
            return
        if self._pipeline_mode == "android_device":
            if not success:
                hint = android_pipeline_failure_hint(self._process_output_tail, self._pipeline_stage)
                if hint:
                    self.output.emit(f"[ADB] Nguyên nhân/Gợi ý: {hint}")
                self.output.emit(
                    f"[ADB] Giai đoạn {self._pipeline_stage} thất bại, mã thoát {exit_code}."
                )
                self._finalize_task(exit_code, False)
                return
            if self._pipeline_stage == "build":
                apk = self._latest_android_apk()
                if apk is None:
                    self.output.emit("[ADB] Build thành công nhưng không tìm thấy APK debug.")
                    self._finalize_task(2, False)
                    return
                self._android_apk = apk
                self.artifact_found.emit(str(apk))
                self._pipeline_stage = "install"
                self.phase_changed.emit("Cài APK qua ADB")
                self.output.emit(f"[ADB] Cài {apk.name} lên {self._android_serial}…")
                self._start_pipeline_process(
                    Path(self._adb_path),
                    ["-s", self._android_serial, "install", "-r", "-t", str(apk)],
                    self._project_root or Path.cwd(),
                )
                return
            if self._pipeline_stage == "install":
                self._pipeline_stage = "launch"
                component = (
                    f"{self._android_package}/"
                    f"{self._android_package}.android.AndroidLauncher"
                )
                self.phase_changed.emit("Khởi chạy trên thiết bị")
                self.output.emit(f"[ADB] Khởi chạy {component}…")
                self._start_pipeline_process(
                    Path(self._adb_path),
                    ["-s", self._android_serial, "shell", "am", "start", "-S", "-n", component],
                    self._project_root or Path.cwd(),
                )
                return
            if self._pipeline_stage == "launch":
                self.output.emit(
                    f"[ADB] Ứng dụng đã chạy trên thiết bị {self._android_serial}."
                )
                self._finalize_task(0, True)
                return

        self._finalize_task(exit_code, success)

    def _start_pipeline_process(
        self, executable: Path, args: list[str], working_dir: Path
    ) -> None:
        environment = QProcessEnvironment.systemEnvironment()
        environment.insert("ANDROID_SERIAL", self._android_serial)
        self.process.setProcessEnvironment(environment)
        self.process.setWorkingDirectory(str(working_dir))
        self.process.setProgram(str(executable))
        self.process.setArguments(args)
        self._output_buffer = ""
        self._process_output_tail = ""
        self.output.emit(f"[ADB] Lệnh: {display_command(executable, args)}")
        self.process.start()

    def _latest_android_apk(self) -> Path | None:
        root = self._project_root
        if root is None:
            return None
        candidates = [
            path for path in root.glob("android/build/outputs/apk/debug/*.apk") if path.is_file()
        ]
        if not candidates:
            candidates = [
                path for path in root.glob("android/build/outputs/apk/**/*.apk") if path.is_file()
            ]
        candidates.sort(key=lambda path: path.stat().st_mtime, reverse=True)
        return candidates[0] if candidates else None

    def _finalize_task(self, exit_code: int, success: bool) -> None:
        state = "hoàn tất" if success else "thất bại"
        self.output.emit(f"[2Dutiful] {self._label} {state}, mã thoát {exit_code}.\n")
        self.phase_changed.emit("Hoàn tất" if success else "Lỗi")
        if success and self._pipeline_mode == "desktop_jad":
            jad = self._write_jad_descriptor()
            if jad is not None:
                self.artifact_found.emit(str(self._stage_artifact(jad)))
        if success and self._pipeline_mode != "android_device":
            self._discover_artifacts()
        if self.debugger.state() != QProcess.ProcessState.NotRunning:
            self.debugger.terminate()
            if not self.debugger.waitForFinished(700):
                self.debugger.kill()
        self.running_changed.emit(False)
        self.finished.emit(exit_code, success)
        if self._task == "environment":
            self._environment_report["gradle_ok"] = bool(success)
            if not success and "gradle" not in self._environment_report.get("missing_required", []):
                self._environment_report.setdefault("missing_required", []).append("gradle")
            self.environment_checked.emit(dict(self._environment_report))
        self._debug_mode = False
        self._debug_attach_started = False
        self._debug_initialized = False
        self._debug_attach_attempts = 0
        self._pipeline_mode = ""
        self._pipeline_stage = ""
        self._android_serial = ""
        self._android_package = ""
        self._adb_path = ""
        self._android_apk = None
        self._environment_install_queue.clear()

    def _write_jad_descriptor(self) -> Path | None:
        root = self._project_root
        if root is None:
            return None
        jars = [path for path in root.glob("lwjgl3/build/libs/*.jar") if path.is_file()]
        jars.sort(key=lambda path: path.stat().st_mtime, reverse=True)
        if not jars:
            self.output.emit("[Build] Không tìm thấy JAR để tạo JAD.")
            return None
        jar = jars[0]
        descriptor = {}
        try:
            descriptor = json.loads((root / "project.dtfe").read_text(encoding="utf-8"))
        except (OSError, ValueError, json.JSONDecodeError):
            descriptor = {}
        name = str(descriptor.get("name") or root.name)
        version = str(descriptor.get("app_version") or "1.0.0")
        vendor = str(descriptor.get("vendor") or "2Dutiful")
        package_name = str(descriptor.get("package_name") or "com.dutiful2d.game")
        jad = jar.with_suffix(".jad")
        content = "\n".join([
            f"MIDlet-Name: {name}",
            f"MIDlet-Version: {version}",
            f"MIDlet-Vendor: {vendor}",
            f"MIDlet-Jar-URL: {jar.name}",
            f"MIDlet-Jar-Size: {jar.stat().st_size}",
            f"2Dutiful-Main-Package: {package_name}",
            "2Dutiful-Target: Desktop-LWJGL3",
            "MicroEdition-Profile: Not-Applicable",
            "",
        ])
        jad.write_text(content, encoding="utf-8")
        self.output.emit(f"[Build] Đã tạo JAD companion: {jad}")
        return jad

    def _stage_artifact(self, artifact: Path) -> Path:
        root = self._project_root
        if root is None:
            return artifact
        destination_dir = root / "dist"
        destination_dir.mkdir(parents=True, exist_ok=True)
        destination = destination_dir / artifact.name
        try:
            if artifact.resolve() != destination.resolve():
                shutil.copy2(artifact, destination)
            self.output.emit(f"[Build] Đã đóng gói vào: {destination}")
            return destination
        except OSError as error:
            self.output.emit(f"[Build] Không thể sao chép artifact vào dist/: {error}")
            return artifact

    def _discover_artifacts(self) -> None:
        root = self._project_root
        if root is None:
            return
        patterns: list[str] = []
        task = self._task.lower()
        if "dist" in task:
            patterns = ["lwjgl3/build/libs/*.jar", "lwjgl3/build/libs/*.jad"]
        elif "android" in task:
            patterns = ["android/build/outputs/apk/**/*.apk", "android/build/outputs/bundle/**/*.aab"]
        elif task == "native":
            patterns = ["native/build/**/*.dll", "native/build/**/*.so", "native/build/**/*.dylib"]
        for pattern in patterns:
            candidates = [path for path in root.glob(pattern) if path.is_file()]
            candidates.sort(key=lambda path: path.stat().st_mtime, reverse=True)
            if candidates:
                staged = self._stage_artifact(candidates[0])
                self.artifact_found.emit(str(staged))

    def _debugger_error(self, error: QProcess.ProcessError) -> None:
        name = getattr(error, "name", str(error))
        self.debugger_output.emit(f"[JDB] Lỗi tiến trình: {name}\n")

    def _process_error(self, error: QProcess.ProcessError) -> None:
        name = getattr(error, "name", str(error))
        self.output.emit(f"[2Dutiful] Lỗi tiến trình: {name}")
        self.phase_changed.emit("Lỗi tiến trình")
        if error == QProcess.ProcessError.FailedToStart:
            self._finalize_task(-1, False)
