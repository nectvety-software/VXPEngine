"""Single source of truth for the VXPEngine SDK and external tools."""
from __future__ import annotations

import os
import sys
from pathlib import Path


ENGINE_ROOT = Path(__file__).resolve().parent.parent
CORE_ROOT = ENGINE_ROOT / "engine" / "coremre"
SDK_ROOT = CORE_ROOT / "sdk"


def _first_file(candidates: list[Path]) -> Path:
    return next((path for path in candidates if path.is_file()), candidates[0])


def _first_dir(candidates: list[Path]) -> Path:
    return next((path for path in candidates if path.is_dir()), candidates[0])


def w64devkit_root() -> Path:
    configured = os.environ.get("VXPE_W64DEVKIT", "").strip()
    candidates = [
        SDK_ROOT / "w64devkit",
        Path(configured) if configured else SDK_ROOT / "w64devkit",
        Path("D:/MRE/lib/w64devkit"),
        Path("D:/MRE/keystore/HelloWorld/w64devkit"),
    ]
    return _first_dir(candidates)


def arm_toolchain_root() -> Path:
    configured = os.environ.get("VXPE_ARM_TOOLCHAIN", "").strip()
    candidates = [
        SDK_ROOT / "arm-toolchain",
        Path(configured) if configured else SDK_ROOT / "arm-toolchain",
        Path("C:/msys64/mingw64"),
    ]
    return _first_dir(candidates)


def mre_sdk_root() -> Path:
    configured = os.environ.get("MRE_SDK", "").strip()
    candidates = [
        SDK_ROOT / "mre",
        Path(configured) if configured else SDK_ROOT / "mre",
        Path("D:/MRE/XimikBoda/third_party/mre-sdk/app"),
    ]
    return _first_dir(candidates)


def packaging_tools_root() -> Path:
    """Native VXPEngine resource/VXP tools with no legacy packer fallback."""
    return CORE_ROOT / "tools"


def vxpemu_executable() -> Path:
    configured = os.environ.get("VXPE_VXPEMU", "").strip()
    candidates = [
        SDK_ROOT / "vxpemu" / "VXPEmu.exe",
        Path(configured) if configured else SDK_ROOT / "vxpemu" / "VXPEmu.exe",
        Path("D:/MRE/VXPEmu/deploy/VXPEmu.exe"),
        Path("D:/MRE/VXPEmu/build/Release/VXPEmu.exe"),
    ]
    return _first_file(candidates)


def host_tool(name: str) -> str:
    """Return a bundled w64devkit tool when available, otherwise its PATH name."""
    executable = w64devkit_root() / "bin" / f"{name}.exe"
    return str(executable) if executable.is_file() else name


def sdk_python() -> str:
    """Python-compatible SDK tool host bundled with the Windows release."""
    bundled = SDK_ROOT / "python" / "VXPEPython.exe"
    return str(bundled) if bundled.is_file() else sys.executable


def build_environment() -> dict[str, str]:
    paths = [w64devkit_root() / "bin", arm_toolchain_root() / "bin"]
    current = os.environ.get("PATH", "")
    return {
        "PATH": os.pathsep.join([str(path) for path in paths if path.is_dir()] + [current]),
        "W64DEVKIT_HOME": str(w64devkit_root()),
        "MRE_SDK": str(mre_sdk_root()),
        "VXPE_SDK_TOOLS": str(packaging_tools_root()),
    }


def status() -> dict[str, tuple[Path, bool]]:
    w64 = w64devkit_root()
    arm = arm_toolchain_root()
    mre = mre_sdk_root()
    pack = packaging_tools_root()
    emulator = vxpemu_executable()
    arm_bin = arm / "bin"
    arm_ready = (
        (arm_bin / "arm-none-eabi-gcc.exe").is_file()
        and (arm_bin / "arm-none-eabi-g++.exe").is_file()
        and (arm_bin / "zlib1.dll").is_file()
    )
    return {
        "w64devkit": (w64, (w64 / "bin" / "cmake.exe").is_file() and (w64 / "bin" / "make.exe").is_file()),
        "arm_gcc": (arm, arm_ready),
        "mre_sdk": (mre, (mre / "include").is_dir() and (mre / "lib").is_dir()),
        "packaging": (pack, (pack / "vxp_pack.py").is_file() and (pack / "vxp_resource.py").is_file()),
        "vxpemu": (emulator, emulator.is_file()),
    }
