"""Pin the frozen IDE to its own PySide6/MSVC DLL set before importing Qt."""
from __future__ import annotations

import ctypes
import os
import sys
from pathlib import Path


if sys.platform == "win32" and getattr(sys, "frozen", False):
    contents = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent)).resolve()
    pyside = contents / "PySide6"
    shiboken = contents / "shiboken6"
    for directory in (contents, shiboken, pyside):
        if directory.is_dir():
            os.add_dll_directory(str(directory))
    os.environ["PATH"] = os.pathsep.join(
        [str(pyside), str(shiboken), str(contents), os.environ.get("PATH", "")]
    )
    os.environ.setdefault("QT_PLUGIN_PATH", str(pyside / "plugins"))

    # LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR | LOAD_LIBRARY_SEARCH_DEFAULT_DIRS.
    # Absolute preloading prevents Qt6Core 6.7 shipped for VXPEmu from
    # satisfying PySide6 6.11's import when another application polluted PATH.
    flags = 0x00000100 | 0x00001000
    for name in (
        "vcruntime140.dll",
        "vcruntime140_1.dll",
        "msvcp140.dll",
        "msvcp140_1.dll",
        "msvcp140_2.dll",
        "concrt140.dll",
    ):
        candidate = contents / name
        if candidate.is_file():
            ctypes.WinDLL(str(candidate), winmode=flags)

    # Qt for Windows imports the stable, unversioned ICU API from the Windows
    # System32 compatibility shim.  A third-party icuuc.dll on PATH may only
    # export version-suffixed names (for example ucnv_open_78), which makes
    # Qt6Core fail with WinError 127.  Pin the OS shim before loading Qt.
    load_library_search_system32 = 0x00000800
    ctypes.WinDLL("icuuc.dll", winmode=load_library_search_system32)
    qt_core = pyside / "Qt6Core.dll"
    if qt_core.is_file():
        ctypes.WinDLL(str(qt_core), winmode=flags)

    # Release verification exercises modules that are imported only after a
    # toolbar action.  This prevents a frozen build from starting normally but
    # crashing as soon as Run/Build requests coremre verification.
    if os.environ.get("VXPE_RELEASE_ACTION_PROBE") == "1":
        import verify_core

        packages = contents.parent / "packaging" / "coremre"
        versions = sorted(path for path in packages.iterdir() if path.is_dir())
        if not versions:
            raise RuntimeError("Release action probe: missing coremre package")
        core_ok, core_message = verify_core.verify(versions[-1])
        if not core_ok:
            raise RuntimeError(f"Release action probe: {core_message}")
