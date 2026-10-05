"""Regression: build-arm must discard host/non-ARM CMake caches."""
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

from vxp_runner import VxpRunner


def write_system(build: Path, system: str, processor: str) -> None:
    out = build / "CMakeFiles" / "4.4.0" / "CMakeSystem.cmake"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        f'set(CMAKE_SYSTEM_NAME "{system}")\n'
        f'set(CMAKE_SYSTEM_PROCESSOR "{processor}")\n',
        encoding="utf-8",
    )


with tempfile.TemporaryDirectory(prefix="vxpe_arm_cache_") as tmp:
    root = Path(tmp)

    host = root / "host"
    host.mkdir()
    (host / "CMakeCache.txt").write_text(
        "CMAKE_C_COMPILER:FILEPATH=C:/msys64/mingw64/bin/cc.exe\n"
        "CMAKE_TOOLCHAIN_FILE:UNINITIALIZED=C:/project/.vxpe/cmake/toolchain-arm-none-eabi.cmake\n",
        encoding="utf-8",
    )
    write_system(host, "Windows", "AMD64")
    assert VxpRunner._cmake_arm_cache_mismatch(host), "host cache must be rejected"

    arm = root / "arm"
    arm.mkdir()
    (arm / "CMakeCache.txt").write_text(
        "CMAKE_C_COMPILER:FILEPATH=C:/Program Files/VXPEngine/engine/coremre/sdk/"
        "arm-toolchain/bin/arm-none-eabi-gcc.exe\n"
        "CMAKE_TOOLCHAIN_FILE:FILEPATH=C:/project/.vxpe/cmake/toolchain-arm-none-eabi.cmake\n",
        encoding="utf-8",
    )
    write_system(arm, "Generic", "ARM")
    assert not VxpRunner._cmake_arm_cache_mismatch(arm), "valid ARM cache must be reused"

print("PASS: Windows/MinGW build-arm cache is rejected; Generic/ARM cache is retained")
