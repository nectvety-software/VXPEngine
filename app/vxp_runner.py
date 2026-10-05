"""Asynchronous build/run pipeline for VXPEngine projects (MRE VXP, core coremre).

The runner drives the CMake-based .vxp toolchain of the generated projects:
Host builds use w64devkit; ARM builds use the bundled MRE SDK. VXPEmu is the
only emulator and receives the generated ARM .vxp through its command line.
"""
from __future__ import annotations

import os
import re
import shutil
import sys
from pathlib import Path

from PySide6.QtCore import QObject, QProcess, QProcessEnvironment, QTimer, Signal

from diagnostics import parse_diagnostic_line
from environment_setup import EnvironmentInstaller, detect_missing
from process_command import display_command
from sdk_layout import (
    arm_toolchain_root,
    build_environment,
    host_tool,
    mre_sdk_root,
    sdk_python,
    status as sdk_status,
    vxpemu_executable,
    w64devkit_root,
)
from signing_service import describe, ensure_signing_identity, signer_arguments


class VxpRunner(QObject):
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
    vxpemu_output = Signal(str)
    vxpemu_started = Signal(str, int)
    vxpemu_stopped = Signal(int)

    MRE_SDK_DIR = mre_sdk_root()
    SDK_TOOLS_DIR = Path(__file__).resolve().parent.parent / "engine" / "coremre" / "tools"
    ARM_TOOLCHAIN_DIR = arm_toolchain_root()
    ARM_GCC = ARM_TOOLCHAIN_DIR / "bin" / "arm-none-eabi-gcc.exe"
    W64DEVKIT_DIR = w64devkit_root()
    VXPEMU_EXE = vxpemu_executable()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.process = QProcess(self)
        self.process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self.process.readyReadStandardOutput.connect(self._read_output)
        self.process.finished.connect(self._process_finished)
        self.process.errorOccurred.connect(self._process_error)
        self.emulator_process = QProcess(self)
        self.emulator_process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self.emulator_process.readyReadStandardOutput.connect(self._read_vxpemu_output)
        self.emulator_process.finished.connect(self._vxpemu_finished)
        self.emulator_process.errorOccurred.connect(self._vxpemu_error)
        self._vxpemu_buffer = ""
        self._vxpemu_log_offsets: dict[Path, int] = {}
        self._vxpemu_log_buffers: dict[Path, str] = {}
        self._vxpemu_log_timer = QTimer(self)
        self._vxpemu_log_timer.setInterval(250)
        self._vxpemu_log_timer.timeout.connect(self._tail_vxpemu_logs)

        self._label = ""
        self._project_root: Path | None = None
        self._steps: list[dict] = []
        self._artifact_candidates: list[Path] = []
        self._last_artifact: Path | None = None
        self._post_action = ""
        # Hành động sau build được giữ lại để MainWindow đọc sau khi pipeline kết
        # thúc (``_post_action`` bị xóa trước khi phát tín hiệu ``finished``).
        self._last_post_action = ""
        self._output_buffer = ""
        # Lỗi xảy ra trước khi pipeline phát ``started`` — MainWindow hiện dialog
        # thay vì chỉ ghi vào console đang ẩn.
        self.last_error = ""

        # Trình cài môi trường chạy độc lập với pipeline build/run.
        self._installer = EnvironmentInstaller(self)
        self._installer.log.connect(self.output.emit)
        self._installer.finished.connect(self._on_environment_installed)

    def _on_environment_installed(self, ok: bool, _results) -> None:
        self.environment_install_completed.emit(bool(ok))

    # ------------------------------------------------------------------ API

    @property
    def is_running(self) -> bool:
        return self.process.state() != QProcess.ProcessState.NotRunning

    def _fail_early(self, message: str) -> bool:
        self.last_error = message
        self.output.emit(message)
        return False

    @property
    def last_post_action(self) -> str:
        """Hành động sau build của pipeline vừa chạy xong.

        Trả về ``"vxpemu"`` / ``""``. MainWindow dùng giá trị này
        trong ``_on_runner_finished`` để quyết định có nạp artifact vào giả lập
        hay không — kể cả khi người dùng không bấm nút Run trên toolbar.
        """
        return self._last_post_action

    def build_arm(self, project_path: str) -> bool:
        return self._run_arm_pipeline(project_path, signed=False)

    def build_arm_signed(self, project_path: str) -> bool:
        return self._run_arm_pipeline(project_path, signed=True)

    def _run_arm_pipeline(self, project_path: str, *, signed: bool, post_action: str = "") -> bool:
        """Build ARM bằng CMake (Ninja + arm-none-eabi).

        Không cần Git Bash: configure và build chạy thẳng qua ``cmake``.
        Bản signed nhận khóa ký của engine qua ``-DAPPID/-DCERTID/-DCERT``;
        project luôn giữ trạng thái chưa ký (CERTID=1, CERT=none).
        """
        self.last_error = ""
        root = self._resolve(project_path)
        if root is None:
            return False
        label = "Build ARM Signed (.vxp)" if signed else "Build ARM (.vxp)"
        build_dir = "build-arm-signed" if signed else "build-arm"

        try:
            cache_reset = self._reset_foreign_cmake_cache(root, build_dir)
        except OSError as error:
            return self._fail_early(f"[CMake] Không thể làm mới cache build: {error}")
        if cache_reset:
            self.output.emit(
                "[CMake] Đã phát hiện cache thuộc project/vị trí khác và tạo lại "
                f"{build_dir} cho {root.name}."
            )

        if signed:
            try:
                ensure_signing_identity(root)
                self.output.emit(f"[VXPEngine] {describe(root)}")
            except (FileNotFoundError, ValueError, OSError) as error:
                return self._fail_early(f"[VXPEngine] ✗ {error}")

        env = build_environment()
        cmake = host_tool("cmake")
        # Ninja handles paths with spaces (Program Files, "VXP Projects");
        # MinGW Makefiles breaks try_compile with unquoted 'C:/Program ...'.
        ninja = host_tool("ninja")
        arm_root = self.ARM_TOOLCHAIN_DIR.as_posix()
        core_defs = self._core_defines()
        if core_defs is None:
            detail = self.last_error or "Gói core không hợp lệ (chữ ký/toàn vẹn) — dừng build."
            return self._fail_early(f"[VXPEngine] {detail}")
        build_root = root / build_dir
        generator_mismatch = self._cmake_generator_mismatch(build_root, "Ninja")
        arm_cache_mismatch = self._cmake_arm_cache_mismatch(build_root)
        if (generator_mismatch or arm_cache_mismatch) and build_root.is_dir():
            if generator_mismatch:
                reason = "generator cũ không phải Ninja"
            else:
                reason = "cache cũ là host/non-ARM"
            self.output.emit(
                f"[CMake] {reason} — xóa cache cũ trong {build_dir} và cấu hình lại ARM."
            )
            shutil.rmtree(build_root, ignore_errors=True)
        configure = {
            "program": cmake,
            "args": [
                "-S", str(root), "-B", str(build_root),
                "-G", "Ninja",
                f"-DCMAKE_TOOLCHAIN_FILE={self._project_toolchain(root)}",
                "-DCMAKE_BUILD_TYPE=Release",
                f"-DTOOLCHAIN_PREFIX={arm_root}",
                f"-DCMAKE_MAKE_PROGRAM={ninja}",
                f"-DMRE_SDK={self.MRE_SDK_DIR.as_posix()}",
                f"-DVXPE_PYTHON={Path(sdk_python()).as_posix()}",
                f"-DVXPE_SDK_TOOLS={self.SDK_TOOLS_DIR.as_posix()}",
                *core_defs,
            ],
            "phase": "Cấu hình CMake (ARM)" + (" — ký bằng khóa engine" if signed else ""),
            "env": env,
        }
        build = {
            "program": cmake,
            "args": ["--build", str(build_root), "--target", "main_vxp"],
            "phase": "Biên dịch ARM (.vxp cho máy thật)",
            "env": env,
        }
        app_name = self._read_app_name(root)
        unsigned = root / build_dir / "main" / f"{app_name}.vxp"
        steps = [configure, build]
        artifacts = [unsigned]
        if signed:
            signed_output = root / build_dir / "main" / f"{app_name}-signed.vxp"
            try:
                args = signer_arguments(unsigned, signed_output, root)
            except (FileNotFoundError, ValueError, OSError) as error:
                return self._fail_early(f"[VXPEngine] ✗ {error}")
            steps.append({
                "program": sdk_python(),
                "args": args,
                "phase": "Ký RSA-SHA1 và xác minh bằng backend re3",
                "env": env,
            })
            artifacts = [signed_output]
        self._post_action = post_action
        return self._run_pipeline(root, label, steps, artifacts)

    @staticmethod
    def _project_toolchain(root: Path) -> Path:
        """Resolve layout-v2 toolchain while retaining legacy-project support."""
        modern = root / ".vxpe" / "cmake" / "toolchain-arm-none-eabi.cmake"
        return modern if modern.is_file() else root / "cmake" / "toolchain-arm-none-eabi.cmake"

    @staticmethod
    def _reset_foreign_cmake_cache(root: Path, build_dir_name: str) -> bool:
        """Xóa build tree nếu CMakeCache được tạo cho project/vị trí khác.

        CMake ghi đường dẫn tuyệt đối vào cache. Vì vậy một project được sao chép,
        đổi tên hoặc di chuyển sẽ lỗi ngay ở bước configure nếu mang theo thư mục
        build cũ. Chỉ các thư mục build do VXPEngine quản lý mới được phép xóa.
        """
        allowed = {"build-arm", "build-arm-signed", "build-win32"}
        if build_dir_name not in allowed:
            raise ValueError(f"Thư mục build không được quản lý: {build_dir_name}")

        project_root = root.expanduser().resolve()
        build_root = (project_root / build_dir_name).resolve()
        if build_root.parent != project_root or build_root.name != build_dir_name:
            raise ValueError("Đường dẫn build nằm ngoài project.")

        cache_path = build_root / "CMakeCache.txt"
        if not cache_path.is_file():
            return False

        entries: dict[str, str] = {}
        for line in cache_path.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.startswith("CMAKE_HOME_DIRECTORY:INTERNAL="):
                entries["source"] = line.split("=", 1)[1].strip()
            elif line.startswith("CMAKE_CACHEFILE_DIR:INTERNAL="):
                entries["build"] = line.split("=", 1)[1].strip()

        def same_path(recorded: str | None, expected: Path) -> bool:
            if not recorded:
                return True
            # ``resolve`` also expands Windows 8.3 names (DOXUAN~1), which may
            # be written by tempfile/CMake even though Qt gives us the long path.
            recorded_path = Path(recorded).expanduser().resolve()
            return os.path.normcase(str(recorded_path)) == os.path.normcase(str(expected.resolve()))

        source_matches = same_path(entries.get("source"), project_root)
        build_matches = same_path(entries.get("build"), build_root)
        if source_matches and build_matches:
            return False

        shutil.rmtree(build_root)
        return True

    @staticmethod
    def _cmake_generator_mismatch(build_root: Path, expected: str) -> bool:
        """True khi cache CMake cũ dùng generator khác (không đổi generator in-place)."""
        cache_path = build_root / "CMakeCache.txt"
        if not cache_path.is_file():
            return False
        try:
            text = cache_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return False
        for line in text.splitlines():
            if line.startswith("CMAKE_GENERATOR:INTERNAL="):
                current = line.split("=", 1)[1].strip()
                return current != expected
        return False

    @staticmethod
    def _cmake_arm_cache_mismatch(build_root: Path) -> bool:
        """True khi build-arm cache thực tế là host/non-ARM.

        CMake khóa compiler/platform ở lần configure đầu. Chỉ truyền lại
        CMAKE_TOOLCHAIN_FILE không thể chuyển một cache Windows/MinGW sang
        Generic/ARM; build tree phải được tạo lại.
        """
        cache_path = build_root / "CMakeCache.txt"
        if not cache_path.is_file():
            return False
        try:
            text = cache_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return False

        compiler = ""
        toolchain = ""
        for line in text.splitlines():
            if line.startswith("CMAKE_C_COMPILER:FILEPATH="):
                compiler = line.split("=", 1)[1].strip().replace("\\", "/").lower()
            elif line.startswith("CMAKE_TOOLCHAIN_FILE:"):
                toolchain = line.split("=", 1)[1].strip().replace("\\", "/").lower()

        # The toolchain variable may be UNINITIALIZED in a stale host cache;
        # the actual compiler is the authoritative signal.
        if compiler and "arm-none-eabi-gcc" not in compiler:
            return True
        if toolchain and "toolchain-arm-none-eabi.cmake" not in toolchain:
            return True

        # CMAKE_SYSTEM_NAME is stored in CMakeFiles, not always in cache.
        system_files = list((build_root / "CMakeFiles").glob("*/CMakeSystem.cmake"))
        for system_file in system_files:
            try:
                system_text = system_file.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if 'set(CMAKE_SYSTEM_NAME "Generic")' not in system_text:
                return True
            if 'set(CMAKE_SYSTEM_PROCESSOR "ARM")' not in system_text:
                return True
        return False

    def run_vxpemu(self, project_path: str) -> bool:
        """Build an ARM VXP and launch the real VXPEmu executable."""
        self.last_error = ""
        if not self.VXPEMU_EXE.is_file():
            return self._fail_early(f"[VXPEngine] ✗ Không tìm thấy VXPEmu: {self.VXPEMU_EXE}")
        return self._run_arm_pipeline(project_path, signed=False, post_action="vxpemu")

    def launch_vxpemu_artifact(self, artifact_path: str) -> bool:
        """Load an existing ARM VXP directly from the emulator toolbar."""
        artifact = Path(artifact_path).expanduser().resolve()
        if artifact.suffix.lower() != ".vxp" or not artifact.is_file():
            self.output.emit(f"[VXPEmu] Tệp VXP không hợp lệ: {artifact}")
            return False
        if not self.VXPEMU_EXE.is_file():
            self.output.emit(f"[VXPEmu] Không tìm thấy VXPEmu: {self.VXPEMU_EXE}")
            return False
        self._last_artifact = artifact
        self.artifact_found.emit(str(artifact))
        self._launch_vxpemu()
        return True

    def clean(self, project_path: str) -> bool:
        root = self._resolve(project_path)
        if root is None:
            return False
        if self.is_running:
            return self._fail_early("[VXPEngine] Một tiến trình build/run khác đang hoạt động.")
        removed = []
        for name in ("build-win32", "build-arm", "build-arm-signed"):
            target = root / name
            if target.exists():
                shutil.rmtree(target, ignore_errors=True)
                removed.append(name)
        self._project_root = root
        self.output.emit(
            f"[VXPEngine] Đã xóa {', '.join(removed)}." if removed else "[VXPEngine] Không có thư mục build nào để xóa."
        )
        self.finished.emit(0, True)
        return True

    def check_environment(self, project_path: str) -> bool:
        root = self._resolve(project_path)
        if root is None:
            return False
        found: list[str] = []
        missing_required: list[str] = []
        missing_optional: list[str] = []

        labels = {
            "w64devkit": "w64devkit (CMake/Make/Ninja/GCC host)",
            "arm_gcc": "ARM GCC (arm-none-eabi)",
            "mre_sdk": "MRE API SDK (include/lib)",
            "packaging": "VXPEngine packer/resource tools",
            "vxpemu": "VXPEmu",
        }
        for key, (path, available) in sdk_status().items():
            text = f"{labels[key]} — {path}"
            (found if available else missing_required).append(text)

        found.append("Kho khóa riêng theo App ID/Vendor (tạo tự động khi ký)")

        for item in found:
            self.output.emit(f"[VXPEngine] ✓ {item}")
        for item in missing_required + missing_optional:
            self.output.emit(f"[VXPEngine] ✗ Thiếu: {item}")
        self.environment_checked.emit(
            {
                "found": found,
                "missing_required": missing_required,
                "missing_optional": missing_optional,
            }
        )
        return True

    def environment_install_packages(self, report: dict) -> list[tuple[str, str]]:
        """Cặp (tên hiển thị, id gói) cho mọi thành phần còn thiếu."""
        return [(item.name, item.key) for item in detect_missing()]

    def install_environment(self, report: dict) -> bool:
        """Chạy shell để cài các thư viện/SDK còn thiếu (bất đồng bộ)."""
        missing = detect_missing()
        if not missing:
            self.output.emit("[Setup] Môi trường đã đầy đủ — không có gì để cài.")
            self.environment_install_completed.emit(True)
            return True
        return self._installer.install(missing)

    def stop(self) -> None:
        # Dừng cả trình cài môi trường, kẻo winget/pacman chạy sót sau khi đóng IDE.
        if self._installer.is_running:
            self._installer.stop()
        if not self.is_running:
            return
        self.output.emit("[VXPEngine] Đang dừng tiến trình build/run...")
        self._steps.clear()
        self.process.kill()

    def stop_vxpemu(self) -> None:
        if self.emulator_process.state() == QProcess.ProcessState.NotRunning:
            return
        message = "[VXPEmu] Đang dừng runtime…"
        self.output.emit(message)
        self.vxpemu_output.emit(message)
        self.emulator_process.terminate()
        if not self.emulator_process.waitForFinished(500):
            self.emulator_process.kill()

    _DEBUG_NOTES = {
        "continue": "Pipeline VXP không giữ breakpoint — ứng dụng chạy liên tục, không có điểm dừng để tiếp tục.",
        "pause": "Không thể tạm dừng tiến trình VXP từ xa; dùng Stop để hủy tác vụ build/run.",
        "step_over": "Gỡ lỗi từng bước cần debugger native; pipeline VXP chỉ build/run nên không hỗ trợ step.",
        "step_into": "Gỡ lỗi từng bước cần debugger native; pipeline VXP chỉ build/run nên không hỗ trợ step.",
        "step_out": "Gỡ lỗi từng bước cần debugger native; pipeline VXP chỉ build/run nên không hỗ trợ step.",
        "stack": "Pipeline VXP không giữ call stack của thiết bị; xem log build/run ở tab Console.",
        "locals": "Pipeline VXP không đọc được biến cục bộ trên thiết bị; dùng log trong mã C để gỡ lỗi.",
        "threads": "Pipeline VXP không quan sát được thread của thiết bị; MRE chạy single-thread trong VM.",
    }

    def debug_command(self, command: str = "", *_args, **_kwargs) -> None:
        cmd = str(command or "").strip()
        note = self._DEBUG_NOTES.get(
            cmd, f"Lệnh '{cmd or '?'}' chưa được hỗ trợ trong pipeline VXP."
        )
        self.debugger_output.emit(f"[Debugger] {cmd or 'lệnh'}: {note}")
        self.output.emit(f"[VXPEngine] Debugger: {note}")

    # ------------------------------------------------------------- internal

    def _resolve(self, project_path: str) -> Path | None:
        root = Path(project_path).expanduser().resolve()
        if not (root / "CMakeLists.txt").exists():
            return self._fail_early(f"[VXPEngine] Dự án thiếu CMakeLists.txt: {root}")
        return root

    def _core_package_dir(self) -> Path | None:
        base = Path(__file__).resolve().parent.parent / "packaging" / "coremre"
        if not base.is_dir():
            return None
        versions = sorted(p for p in base.iterdir() if p.is_dir())
        return versions[-1] if versions else None

    def _core_defines(self) -> list[str] | None:
        """[-DCOREMRE_PACKAGE_DIR=...] sau khi xác minh chữ ký gói core.

        Trả về [] khi không có gói (project tự mang core cũ); None khi gói
        có nhưng chữ ký/toàn vẹn SAI — build phải dừng vì lý do bảo mật.
        """
        pkg = self._core_package_dir()
        if pkg is None:
            return []
        tools = Path(__file__).resolve().parent.parent / "tools"
        if tools.is_dir() and str(tools) not in sys.path:
            sys.path.insert(0, str(tools))
        try:
            import verify_core
            ok, message = verify_core.verify(pkg)
        except (ImportError, OSError, ValueError, TypeError) as error:
            detail = f"Không thể nạp bộ xác minh coremre: {error}"
            self.last_error = f"[Core] {detail}"
            self.output.emit(f"[Core] {detail}")
            return None
        self.output.emit(f"[Core] {message}")
        if not ok:
            self.last_error = f"[Core] {message}"
            return None
        return [f"-DCOREMRE_PACKAGE_DIR={pkg.as_posix()}"]

    def _run_pipeline(self, root: Path, label: str, steps: list[dict], artifacts: list[Path]) -> bool:
        if self.is_running:
            return self._fail_early("[VXPEngine] Một tiến trình build/run khác đang hoạt động.")
        self._project_root = root
        self._label = label
        self._steps = list(steps)
        self._artifact_candidates = list(artifacts)
        # Xóa dấu vết của lần chạy trước để MainWindow không nạp nhầm artifact.
        self._last_post_action = ""
        self.last_error = ""
        self.output.emit(f"\n[VXPEngine] Bắt đầu: {label}")
        self.output.emit(f"[VXPEngine] Thư mục: {root}")
        self.started.emit(label)
        self.running_changed.emit(True)
        return self._start_next_step()

    def _start_next_step(self) -> bool:
        if not self._steps:
            return True
        step = self._steps.pop(0)
        program = str(step["program"])
        args = [str(item) for item in step["args"]]
        phase = str(step.get("phase") or self._label)
        if not shutil.which(program) and not Path(program).exists():
            self.last_error = f"[VXPEngine] Không tìm thấy lệnh: {program}"
            self.output.emit(self.last_error)
            self._fail_pipeline(-1)
            return False
        self.phase_changed.emit(phase)
        self.output.emit(f"[VXPEngine] {phase}")
        self.output.emit(f"[VXPEngine] Lệnh: {display_command(program, args)}")
        self._output_buffer = ""
        environment = QProcessEnvironment.systemEnvironment()
        for key, value in (step.get("env") or {}).items():
            environment.insert(str(key), str(value))
        self.process.setProcessEnvironment(environment)
        self.process.setWorkingDirectory(str(self._project_root))
        self.process.start(program, args)
        return True

    def _read_output(self) -> None:
        data = bytes(self.process.readAllStandardOutput()).decode("utf-8", "replace")
        if not data:
            return
        self._output_buffer += data
        while "\n" in self._output_buffer:
            line, self._output_buffer = self._output_buffer.split("\n", 1)
            line = line.rstrip("\r")
            if line.strip():
                self.output.emit(line)
                self._emit_diagnostic(line)

    def _emit_diagnostic(self, line: str) -> None:
        if self._project_root is None:
            return
        diagnostic = parse_diagnostic_line(line, self._project_root)
        if diagnostic is not None:
            self.diagnostic.emit(diagnostic.to_dict())

    def _process_finished(self, exit_code: int, _status) -> None:
        if self._output_buffer.strip():
            self.output.emit(self._output_buffer.rstrip("\r"))
            self._emit_diagnostic(self._output_buffer)
            self._output_buffer = ""
        if exit_code == 0 and self._steps:
            self._start_next_step()
            return
        success = exit_code == 0
        self._last_post_action = self._post_action if success else ""
        if success:
            self._last_artifact = self._emit_artifact()
            if self._post_action == "vxpemu":
                self._launch_vxpemu()
            self.output.emit(f"[VXPEngine] {self._label} hoàn tất.")
        else:
            self.output.emit(f"[VXPEngine] {self._label} thất bại với mã {exit_code}.")
        self._post_action = ""
        self.phase_changed.emit("")
        self.running_changed.emit(False)
        self.finished.emit(exit_code, success)

    def _process_error(self, error) -> None:
        if error == QProcess.ProcessError.FailedToStart:
            self.output.emit(f"[VXPEngine] Không thể khởi chạy tiến trình: {self.process.program()}")
            self._post_action = ""
            self.running_changed.emit(False)
            self.finished.emit(-1, False)

    def _fail_pipeline(self, exit_code: int) -> None:
        self._steps.clear()
        self._post_action = ""
        self.phase_changed.emit("")
        self.running_changed.emit(False)
        self.finished.emit(exit_code, False)

    def _emit_artifact(self) -> Path | None:
        for candidate in self._artifact_candidates:
            if candidate.exists():
                self.artifact_found.emit(str(candidate))
                return candidate
        if self._project_root is not None:
            for pattern in ("build-arm/main/*.vxp", "build-arm-signed/main/*.vxp"):
                matches = sorted(self._project_root.glob(pattern))
                if matches:
                    self.artifact_found.emit(str(matches[-1]))
                    return matches[-1]
        return None

    def _launch_vxpemu(self) -> None:
        artifact = self._last_artifact
        emulator = self.VXPEMU_EXE
        if artifact is None or not artifact.is_file():
            self.output.emit("[VXPEngine] Không tìm thấy VXP để mở bằng VXPEmu.")
            return
        if not emulator.is_file():
            self.output.emit(f"[VXPEngine] Không tìm thấy VXPEmu: {emulator}")
            return
        self.stop_vxpemu()
        self._vxpemu_buffer = ""
        self._prepare_vxpemu_logs(emulator)
        self.emulator_process.setWorkingDirectory(str(emulator.parent))
        self.emulator_process.setProgram(str(emulator))
        # The framebuffer-only child is hosted by VXPEngine's separate Nokia
        # shell; diagnostics continue to arrive through the process streams.
        self.emulator_process.setArguments(
            [str(artifact), "--autostart", "--testapi", "--screen-only"]
        )
        self.emulator_process.start()
        if self.emulator_process.waitForStarted(1500):
            pid = int(self.emulator_process.processId())
            message = f"[VXPEmu] Khởi động {artifact.name} (PID {pid})"
            self.output.emit(message)
            self.vxpemu_output.emit(message)
            self._vxpemu_log_timer.start()
            self.vxpemu_started.emit(str(artifact), pid)
        else:
            message = f"[VXPEmu] Không thể khởi chạy: {emulator}"
            self.output.emit(message)
            self.vxpemu_output.emit(message)

    def _vxpemu_log_paths(self, emulator: Path) -> list[Path]:
        """Các log native của VXPEmu, tương ứng Logger và ARM bridge."""
        paths = [emulator.parent / "mremu_debug.log"]
        appdata = os.environ.get("APPDATA", "").strip()
        if appdata:
            paths.append(Path(appdata) / "VXPEmu" / "VXPEmu" / "logs" / "mkemu.log")
        return paths

    def _prepare_vxpemu_logs(self, emulator: Path) -> None:
        self._vxpemu_log_timer.stop()
        self._vxpemu_log_offsets.clear()
        self._vxpemu_log_buffers.clear()
        for path in self._vxpemu_log_paths(emulator):
            try:
                self._vxpemu_log_offsets[path] = path.stat().st_size
            except OSError:
                self._vxpemu_log_offsets[path] = 0
            self._vxpemu_log_buffers[path] = ""

    def _tail_vxpemu_logs(self) -> None:
        """Đưa log do runtime ghi file vào tab VXPEmu theo thời gian thực."""
        for path, offset in tuple(self._vxpemu_log_offsets.items()):
            try:
                size = path.stat().st_size
                if size < offset:  # runtime đã xoay hoặc ghi lại file log
                    offset = 0
                if size == offset:
                    continue
                with path.open("rb") as stream:
                    stream.seek(offset)
                    data = stream.read()
                self._vxpemu_log_offsets[path] = offset + len(data)
            except OSError:
                continue
            buffer = self._vxpemu_log_buffers.get(path, "") + data.decode("utf-8", "replace")
            lines = buffer.splitlines(keepends=True)
            self._vxpemu_log_buffers[path] = ""
            if lines and not lines[-1].endswith(("\n", "\r")):
                self._vxpemu_log_buffers[path] = lines.pop()
            source = "core" if path.name == "mkemu.log" else "arm"
            for line in lines:
                clean = line.rstrip("\r\n")
                if clean:
                    message = f"[VXPEmu/{source}] {clean}"
                    self.output.emit(message)
                    self.vxpemu_output.emit(message)

    def _read_vxpemu_output(self) -> None:
        data = bytes(self.emulator_process.readAllStandardOutput()).decode("utf-8", "replace")
        self._vxpemu_buffer += data
        while "\n" in self._vxpemu_buffer:
            line, self._vxpemu_buffer = self._vxpemu_buffer.split("\n", 1)
            line = line.rstrip("\r")
            if line:
                message = f"[VXPEmu] {line}"
                self.output.emit(message)
                self.vxpemu_output.emit(message)

    def _vxpemu_finished(self, code: int, _status) -> None:
        self._tail_vxpemu_logs()
        self._vxpemu_log_timer.stop()
        if self._vxpemu_buffer.strip():
            message = f"[VXPEmu] {self._vxpemu_buffer.strip()}"
            self.output.emit(message); self.vxpemu_output.emit(message)
        self._vxpemu_buffer = ""
        message = f"[VXPEmu] Runtime đã thoát (code {code})."
        self.output.emit(message)
        self.vxpemu_output.emit(message)
        self.vxpemu_stopped.emit(int(code))

    def _vxpemu_error(self, error) -> None:
        if error == QProcess.ProcessError.FailedToStart:
            message = f"[VXPEmu] Không thể khởi động: {self.emulator_process.errorString()}"
            self.output.emit(message); self.vxpemu_output.emit(message)

    @staticmethod
    def _read_app_name(root: Path) -> str:
        try:
            text = (root / "CMakeLists.txt").read_text(encoding="utf-8", errors="replace")
        except OSError:
            return root.name
        match = re.search(r'set\(APP_NAME\s+"([^"]+)"\)', text)
        return match.group(1) if match else root.name
