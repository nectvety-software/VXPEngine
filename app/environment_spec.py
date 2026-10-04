"""Bảng kê thành phần môi trường & SDK của VXPEngine — không phụ thuộc Qt.

Tách từ :mod:`app.environment_setup` để:

* :mod:`simulator.standalone_simulator` (chạy bằng Python chuẩn) có thể dùng
  chung nguồn dữ liệu với IDE mà không cần PySide6.
* :class:`~environment_setup.EnvironmentInstaller` (Qt-based) chỉ là lớp vỏ
  bọc quanh :class:`Requirement` ở đây, đỡ phải sửa chỗ khác khi đổi Qt API.

Mọi hàm ``detect()`` chỉ dùng :mod:`shutil`, :mod:`pathlib` và
:mod:`importlib` — chạy được trên bất kỳ máy nào có Python 3.11+.
"""
from __future__ import annotations

import importlib.util
import os
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable

REPO_ROOT = Path(__file__).resolve().parent.parent
MSYS2_ROOT = Path("C:/msys64")
try:
    from .sdk_layout import status as sdk_status
except ImportError:
    from sdk_layout import status as sdk_status


def winget_path() -> str:
    """Đường dẫn winget.exe.

    winget thường là App Execution Alias nằm trong WindowsApps, thư mục này
    không phải lúc nào cũng có trong PATH của tiến trình con do IDE sinh ra,
    nên cần dò thêm các vị trí chuẩn.
    """
    found = shutil.which("winget")
    if found:
        return found
    local_app_data = os.environ.get("LOCALAPPDATA") or ""
    if local_app_data:
        candidate = Path(local_app_data) / "Microsoft" / "WindowsApps" / "winget.exe"
        if candidate.exists():
            return str(candidate)
    return ""


def has_winget() -> bool:
    return bool(winget_path())


def winget_install(package_id: str, *extra: str) -> list[str] | None:
    """Lệnh cài một gói qua winget. Trả về ``None`` nếu không có winget."""
    if not has_winget():
        return None
    return [
        winget_path(), "install", "-e",
        "--accept-source-agreements",
        "--accept-package-agreements",
        "--disable-interactivity",
        "--id", package_id, *extra,
    ]


# ---------------------------------------------------------------------------
# Detect helpers
# ---------------------------------------------------------------------------

def _sdk_available(key: str) -> bool:
    return sdk_status()[key][1]


def _detect_arm_gcc() -> bool:
    return _sdk_available("arm_gcc")


def _detect_python_deps() -> bool:
    return all(importlib.util.find_spec(name) is not None for name in ("PySide6", "qtawesome", "cryptography"))


# ---------------------------------------------------------------------------
# Install helpers
# ---------------------------------------------------------------------------

def _install_arm_gcc() -> list[str] | None:
    """Ưu tiên pacman của MSYS2 nếu đã có, nếu không thì dùng winget."""
    bash = MSYS2_ROOT / "usr" / "bin" / "bash.exe"
    if bash.exists():
        return [
            str(bash), "-lc",
            "pacman -S --noconfirm --needed mingw-w64-x86_64-arm-none-eabi-toolchain",
        ]
    return winget_install("Arm.GNUArmEmbeddedToolchain")


def _install_python_deps() -> list[str] | None:
    requirements = REPO_ROOT / "requirements.txt"
    if not requirements.exists():
        return None
    return [sys.executable, "-m", "pip", "install", "-r", str(requirements)]


# ---------------------------------------------------------------------------
# Requirement
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Requirement:
    """Một thành phần môi trường mà VXPEngine cần."""

    key: str
    name: str
    detect: Callable[[], bool]
    command: Callable[[], list[str] | None] = field(default=lambda: None)
    hint: str = ""
    optional: bool = False

    @property
    def satisfied(self) -> bool:
        try:
            return bool(self.detect())
        except OSError:
            return False

    @property
    def is_installable(self) -> bool:
        return self.command() is not None


# ---------------------------------------------------------------------------
# REQUIREMENTS — bảng kê nguồn duy nhất, dùng chung IDE + simulator.
# ---------------------------------------------------------------------------

REQUIREMENTS: tuple[Requirement, ...] = (
    Requirement(
        key="w64devkit",
        name="w64devkit (CMake/Make/Ninja/GCC host)",
        detect=lambda: _sdk_available("w64devkit"),
        hint="Đặt w64devkit trong engine/coremre/sdk/w64devkit hoặc khai báo VXPE_W64DEVKIT.",
    ),
    Requirement(
        key="arm_gcc",
        name="arm-none-eabi-gcc (MSYS2 MinGW)",
        detect=_detect_arm_gcc,
        command=_install_arm_gcc,
        hint="Cần cho build ARM (.vxp chạy máy thật). MSYS2: "
             "pacman -S mingw-w64-x86_64-arm-none-eabi-toolchain",
    ),
    Requirement(
        key="python_deps",
        name="Thư viện Python (PySide6, QtAwesome, cryptography)",
        detect=_detect_python_deps,
        command=_install_python_deps,
        hint=f"Chạy: {Path(sys.executable).name} -m pip install -r requirements.txt",
    ),
    Requirement(
        key="mre_sdk",
        name="MRE API SDK tích hợp",
        detect=lambda: _sdk_available("mre_sdk"),
        hint="Cần engine/coremre/sdk/mre/include và lib.",
    ),
    Requirement(
        key="packaging",
        name="VXPEngine VXP/resource packer",
        detect=lambda: _sdk_available("packaging"),
        hint="Cần engine/coremre/tools/vxp_pack.py và vxp_resource.py.",
    ),
    Requirement(
        key="vxpemu",
        name="VXPEmu (runtime duy nhất)",
        detect=lambda: _sdk_available("vxpemu"),
        hint="Đặt VXPEmu trong SDK hoặc khai báo VXPE_VXPEMU.",
    ),
    Requirement(
        key="signing_backend",
        name="Backend ký và tạo khóa riêng theo ứng dụng",
        detect=lambda: (REPO_ROOT / "engine" / "coremre" / "tools" / "vxp_signer.py").exists(),
        hint="Cần engine/coremre/tools/vxp_signer.py và cryptography.",
    ),
)


def all_requirements() -> tuple[Requirement, ...]:
    return REQUIREMENTS


def detect_missing(
    requirements: Iterable[Requirement] | None = None,
    *,
    include_optional: bool = True,
) -> list[Requirement]:
    """Danh sách thành phần chưa có trên máy."""
    items = tuple(requirements) if requirements is not None else REQUIREMENTS
    missing = [item for item in items if not item.satisfied]
    if not include_optional:
        missing = [item for item in missing if not item.optional]
    return missing


def installable(missing: Iterable[Requirement]) -> list[Requirement]:
    """Trong số còn thiếu, những cái có thể cài tự động bằng shell."""
    return [item for item in missing if item.is_installable]
