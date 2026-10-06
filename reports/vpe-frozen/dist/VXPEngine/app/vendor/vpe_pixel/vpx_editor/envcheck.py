"""Environment + library checks shared by the app bootstrap and the installer.

Stdlib only on purpose: this runs before PySide6 is known to be importable, so a
missing Qt install must be reportable, not the reason the reporter crashes.
"""

from __future__ import annotations

import ctypes
import importlib.util
import os
import platform
import shutil
import subprocess
import sys
import webbrowser
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, List, Optional

MIN_PYTHON = (3, 10)
MIN_PYSIDE6 = (6, 6)
MIN_WINDOWS_BUILD = 16299          # Windows 10 1709
SPACE_MARGIN = 200 * 1024 * 1024   # keep 200 MB free on top of the payload

PACKAGE_ROOT = Path(__file__).resolve().parent.parent
REQUIREMENTS = PACKAGE_ROOT / "requirements.txt"


@dataclass
class Check:
    key: str
    label: str
    ok: bool
    value: str = ""                  # one-line status shown in the table
    detail: str = ""                 # explanation, only when something is wrong
    required: bool = True
    fix_label: str = ""
    fix: Optional[Callable[[Callable[[str], None]], bool]] = None
    log: List[str] = field(default_factory=list)

    @property
    def fixable(self) -> bool:
        return self.fix is not None


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False)) or hasattr(sys, "_MEIPASS")


def running_python() -> str:
    return sys.executable


def pip_command(*packages: str) -> List[str]:
    """pip argv for the *current* interpreter — never a bare `pip` from PATH."""
    return [running_python(), "-m", "pip", "install", "--upgrade", *packages]


def install_requirements(log: Callable[[str], None]) -> bool:
    """`pip install -r requirements.txt`, streaming one log line per output line."""
    if is_frozen():
        log("running from the packaged executable — nothing to install")
        return False
    if not REQUIREMENTS.exists():
        log(f"missing {REQUIREMENTS}")
        return False
    cmd = pip_command("-r", str(REQUIREMENTS))
    log("$ " + " ".join(cmd))
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
    try:
        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace",
            cwd=str(PACKAGE_ROOT), creationflags=flags,
        )
    except OSError as exc:
        log(f"could not start pip: {exc}")
        return False
    assert proc.stdout is not None
    for line in proc.stdout:
        line = line.rstrip()
        if line:
            log(line)
    code = proc.wait()
    log(f"pip exited with {code}")
    return code == 0


def _version_tuple(raw: str) -> tuple:
    parts = []
    for chunk in raw.split(".")[:3]:
        digits = "".join(c for c in chunk if c.isdigit())
        parts.append(int(digits) if digits else 0)
    return tuple(parts)


def check_windows() -> Check:
    build = 0
    if platform.system() == "Windows":
        try:
            build = int(platform.version().split(".")[2])
        except (IndexError, ValueError):
            build = 0
    ok = platform.system() == "Windows" and build >= MIN_WINDOWS_BUILD
    return Check(
        "windows", "Operating system", ok,
        f"Windows 10 build {build}" if ok else f"{platform.system()} build {build}",
        "" if ok else "Windows 10 build 16299 or newer is required",
    )


def check_arch() -> Check:
    machine = platform.machine().lower()
    ok = machine in ("amd64", "x86_64")
    return Check("arch", "64-bit processor", ok, machine or "unknown",
                 "" if ok else "the packaged executable is 64-bit only")


def check_python() -> Check:
    if is_frozen():
        return Check("python", "Python runtime", True, "bundled in the executable",
                     required=False)
    ok = sys.version_info[:2] >= MIN_PYTHON
    return Check(
        "python", "Python interpreter", ok,
        f"{platform.python_version()} at {running_python()}",
        "" if ok else f"Python {'.'.join(map(str, MIN_PYTHON))}+ is required",
    )


def check_pyside6() -> Check:
    def fix(log: Callable[[str], None]) -> bool:
        return install_requirements(log)

    found = importlib.util.find_spec("PySide6") is not None
    if is_frozen():
        return Check(
            "pyside6", "Qt libraries (PySide6)", found,
            "bundled in the executable",
            "" if found else "the executable shipped without its Qt payload",
            fix=None,
        )

    version = ""
    if found:
        try:
            from importlib.metadata import version as dist_version

            version = dist_version("PySide6")
        except Exception:
            version = ""
    too_old = bool(version) and _version_tuple(version) < MIN_PYSIDE6
    ok = found and not too_old
    return Check(
        "pyside6", "Qt libraries (PySide6)", ok,
        f"PySide6 {version}" if version else ("PySide6 present" if found else "not installed"),
        "PySide6 >= 6.6 is required" if too_old else (
            "" if ok else "Qt is required to run the editor — install it automatically below"
        ),
        fix_label="Install with pip",
        fix=None if ok else fix,
    )


def check_vc_runtime() -> Check:
    if platform.system() != "Windows":
        return Check("vc", "Visual C++ runtime", True, "not needed here", required=False)
    missing = []
    for dll in ("vcruntime140.dll", "vcruntime140_1.dll", "msvcp140.dll"):
        try:
            ctypes.WinDLL(dll)
        except OSError:
            missing.append(dll)
    ok = not missing

    def fix(log: Callable[[str], None]) -> bool:
        log("opening the Microsoft Visual C++ redistributable download")
        webbrowser.open("https://aka.ms/vs/17/release/vc_redist.x64.exe")
        return False

    return Check(
        "vc", "Visual C++ runtime", ok,
        "present" if ok else "missing " + ", ".join(missing),
        "" if ok else "Qt needs the 64-bit VC++ runtime; install it then restart",
        required=False,
        fix_label="Download from Microsoft",
        fix=None if ok else fix,
    )


def check_writable(key: str, label: str, folder: Path, create: bool = True) -> Check:
    def fix(log: Callable[[str], None]) -> bool:
        try:
            folder.mkdir(parents=True, exist_ok=True)
            probe = folder / ".vpe_write_probe"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink()
            log(f"created {folder}")
            return True
        except OSError as exc:
            log(f"cannot use {folder}: {exc}")
            return False

    try:
        if create:
            folder.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        return Check(key, label, False, str(folder),
                     f"{folder} could not be created ({exc.__class__.__name__})",
                     fix_label="Create / fix folder", fix=fix)
    if _writable(folder):
        return Check(key, label, True, str(folder))
    return Check(key, label, False, str(folder),
                 f"{folder} is not writable",
                 fix_label="Create / fix folder", fix=fix)


def _writable(folder: Path) -> bool:
    try:
        probe = folder / ".vpe_write_probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        return True
    except OSError:
        return False


def check_creatable(label: str, folder: Path) -> Check:
    """Can `folder` be created? Tests the nearest existing ancestor instead of
    leaving a half-empty install directory behind."""
    def fix(log: Callable[[str], None]) -> bool:
        try:
            folder.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            log(f"cannot create {folder}: {exc}")
            return False
        log(f"created {folder}")
        return _writable(folder)

    probe = folder
    while not probe.exists() and probe.parent != probe:
        probe = probe.parent
    ok = probe.exists() and _writable(probe)
    return Check(
        "target", label, ok,
        str(folder) if folder.exists() else f"{folder} (will be created)",
        "" if ok else f"{probe} is not writable — pick another folder",
        fix_label="Create folder", fix=None if ok else fix,
    )


def check_disk(target: Path, payload_bytes: int = 0) -> Check:
    probe = target
    while not probe.exists() and probe.parent != probe:
        probe = probe.parent      # a not-yet-created folder still lives on a volume
    try:
        free = shutil.disk_usage(str(probe)).free
    except OSError:
        return Check("disk", "Free disk space", True, "unknown", required=False)
    need = payload_bytes + SPACE_MARGIN
    ok = free >= need
    return Check(
        "disk", "Free disk space", ok,
        f"{free // (1024 * 1024)} MB free on {probe.drive or probe}",
        "" if ok else f"needs {need // (1024 * 1024)} MB (payload + 200 MB headroom)",
    )


def check_icon_font() -> Check:
    """Informational: the chrome falls back to text labels when this fails."""
    if platform.system() != "Windows":
        return Check("font", "Icon font (Segoe MDL2 Assets)", True, "not needed here",
                     required=False)
    path = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts" / "segmdl2.ttf"
    return Check(
        "font", "Icon font (Segoe MDL2 Assets)", path.is_file(),
        "installed" if path.is_file() else "missing",
        "" if path.is_file() else "tool buttons will show short text labels instead",
        required=False,
    )


def collect(target_dir: Optional[Path] = None, payload_bytes: int = 0,
            include_folders: bool = True) -> List[Check]:
    """Run every check. `paths` is imported late so this module stays standalone."""
    checks = [check_windows(), check_arch(), check_python(), check_pyside6(),
              check_vc_runtime()]
    if include_folders:
        from .paths import app_data_dir, project_dir

        checks.append(check_writable("appdata", "App data folder", app_data_dir(False)))
        checks.append(check_writable("projects", "Projects folder", project_dir(False)))
    if target_dir is not None:
        target = Path(target_dir)
        checks.append(check_creatable("Install folder", target))
        checks.append(check_disk(target, payload_bytes))
    else:
        checks.append(check_disk(Path.home(), payload_bytes))
    checks.append(check_icon_font())
    return checks


def blocking(checks: List[Check]) -> List[Check]:
    return [c for c in checks if c.required and not c.ok]


def fixable(checks: List[Check]) -> List[Check]:
    return [c for c in checks if not c.ok and c.fixable]


# ---------------------------------------------------------------------------
# Pre-Qt gate: when PySide6 itself is missing there is no way to show a Qt
# dialog about it, so this path stays in the console.
# ---------------------------------------------------------------------------

def qt_importable() -> bool:
    if importlib.util.find_spec("PySide6") is None:
        return False
    try:
        import PySide6.QtWidgets  # noqa: F401  (missing VC++ DLL raises here)

        return True
    except (ImportError, OSError):
        return False


def ensure_runtime() -> bool:
    """True when Qt can be imported; otherwise offer to install it."""
    if is_frozen() or qt_importable():
        return True
    return console_install()


def _report(checks: List[Check]) -> None:
    for c in checks:
        mark = "ok  " if c.ok else ("FAIL" if c.required else "warn")
        print(f"  [{mark}] {c.label:<34} {c.value}".rstrip())
        if c.detail:
            print(f"         {c.detail}")


def console_install() -> bool:
    print("VXP Pixel Editor — environment check")
    checks = collect()
    _report(checks)
    missing = blocking(checks)
    if not missing:
        return True
    print(f"\nCannot start: {', '.join(c.key for c in missing)}")
    if sys.stdin is None or not sys.stdin.isatty():
        print("Run: python -m pip install -r requirements.txt")
        return False
    if input("Install the missing libraries now? [Y/n] ").strip().lower() not in ("", "y", "yes"):
        return False
    if not install_requirements(lambda line: print("  " + line)):
        print("pip failed — see the output above")
        return False
    importlib.invalidate_caches()
    if qt_importable():
        print("Installed. Run 'python main.py' again.")
        return True
    print("Installed, but Qt still cannot load — install the Visual C++ runtime "
          "from https://aka.ms/vs/17/release/vc_redist.x64.exe")
    return False


if __name__ == "__main__":  # `python -m vpx_editor.envcheck`
    results = collect()
    for c in results:
        mark = "OK  " if c.ok else ("FAIL" if c.required else "warn")
        print(f"[{mark}] {c.label:<34} {c.value}".rstrip())
        if c.detail:
            print(f"       {c.detail}")
    raise SystemExit(1 if blocking(results) else 0)
