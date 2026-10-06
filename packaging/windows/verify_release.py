"""Verify the staged Windows release before producing the installer."""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import pefile
from verify_vpe_bundle import verify_bundle


def require(path: Path) -> Path:
    if not path.is_file():
        raise SystemExit(f"Missing release file: {path}")
    return path


def main() -> int:
    stage = Path(sys.argv[1]).resolve()
    ide = require(stage / "VXPEngine.exe")
    print("VPE Pixel payload:", verify_bundle(stage / "app/vendor/vpe_pixel"))
    sdk_python = require(stage / "engine/coremre/sdk/python/VXPEPython.exe")
    require(stage / "engine/coremre/sdk/w64devkit/bin/cmake.exe")
    require(stage / "engine/coremre/sdk/w64devkit/bin/ninja.exe")
    arm_gcc = require(stage / "engine/coremre/sdk/arm-toolchain/bin/arm-none-eabi-gcc.exe")
    require(stage / "engine/coremre/sdk/arm-toolchain/bin/zlib1.dll")
    require(stage / "engine/coremre/sdk/mre/include/vmsys.h")
    require(stage / "engine/coremre/sdk/vxpemu/VXPEmu.exe")
    require(stage / "engine/coremre/tools/vxp_pack.py")

    # Do not trust file presence alone.  GCC may start successfully while its
    # internal cc1.exe fails later because a runtime DLL is missing.  Probe the
    # staged compiler with an isolated PATH so a developer machine cannot mask
    # an incomplete release with DLLs from another MinGW installation.
    arm_bin = arm_gcc.parent
    arm_env = dict(os.environ)
    windows_dir = Path(os.environ.get("WINDIR", r"C:\Windows"))
    arm_env["PATH"] = os.pathsep.join(
        (
            str(arm_bin),
            str(windows_dir / "System32"),
            str(windows_dir),
        )
    )
    with tempfile.TemporaryDirectory(prefix="vxpe-arm-probe-") as temp_dir:
        temp = Path(temp_dir)
        source = temp / "probe.c"
        obj = temp / "probe.o"
        source.write_text("int vxpe_arm_probe(void) { return 0; }\n", encoding="ascii")
        arm_probe = subprocess.run(
            [
                str(arm_gcc),
                "-march=armv5te",
                "-mthumb",
                "-c",
                str(source),
                "-o",
                str(obj),
            ],
            capture_output=True,
            text=True,
            env=arm_env,
            timeout=20,
        )
        if arm_probe.returncode != 0 or not obj.is_file():
            detail = (arm_probe.stdout + arm_probe.stderr).strip()
            raise SystemExit(
                "Bundled ARM GCC failed its compile probe"
                + (f": {detail}" if detail else "")
            )

    # QtCore must see the same MSVC runtime as PySide6. A stale runtime copied
    # from the Python installation can import on a developer PC but fail on a
    # clean Windows machine with "specified procedure could not be found".
    runtime_names = (
        "concrt140.dll", "msvcp140.dll", "msvcp140_1.dll", "msvcp140_2.dll",
        "msvcp140_codecvt_ids.dll", "vcruntime140.dll", "vcruntime140_1.dll",
    )
    for name in runtime_names:
        first_search = require(stage / "app" / name)
        pyside_copy = stage / "app/PySide6" / name
        if pyside_copy.is_file() and first_search.read_bytes() != pyside_copy.read_bytes():
            raise SystemExit(f"MSVC runtime mismatch before PySide6.QtCore import: {name}")

    # Qt 6.11 expects the unversioned Windows ICU compatibility API.  A
    # PyInstaller-collected ICU implementation may export only suffixed names
    # such as ucnv_open_78 and shadow System32, causing WinError 127.
    bundled_icu = sorted(path.name for path in (stage / "app").glob("icu*.dll"))
    if bundled_icu:
        raise SystemExit(
            "Incompatible ICU DLL must not shadow Windows System32: "
            + ", ".join(bundled_icu)
        )

    pe = pefile.PE(str(ide), fast_load=True)
    if pe.OPTIONAL_HEADER.Subsystem != pefile.SUBSYSTEM_TYPE["IMAGE_SUBSYSTEM_WINDOWS_GUI"]:
        raise SystemExit("VXPEngine.exe is not a Windows GUI executable")

    leaked = []
    private_pem = re.compile(
        rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----\r?\n"
        rb"[A-Za-z0-9+/=\r\n]{64,}"
        rb"-----END (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"
    )
    for candidate in stage.rglob("*"):
        if not candidate.is_file() or candidate.stat().st_size > 2_000_000:
            continue
        try:
            if private_pem.search(candidate.read_bytes()):
                leaked.append(str(candidate.relative_to(stage)))
        except OSError:
            continue
    if leaked:
        raise SystemExit("Private key material found in release: " + ", ".join(leaked))

    probe = subprocess.run(
        [str(sdk_python), str(stage / "engine/coremre/tools/vxp_resource.py"), "--help"],
        capture_output=True,
        text=True,
        timeout=20,
    )
    if probe.returncode != 0 or "usage:" not in (probe.stdout + probe.stderr).lower():
        raise SystemExit("Bundled SDK Python host failed its tool probe")

    env = dict(os.environ)
    env["QT_QPA_PLATFORM"] = "offscreen"
    env["VXPE_RELEASE_ACTION_PROBE"] = "1"
    # Deliberately poison PATH/cwd with VXPEmu's Qt 6.7 runtime. The IDE uses
    # PySide6 Qt 6.11 and must survive this exact DLL-name collision.
    vxpemu_dir = stage / "engine/coremre/sdk/vxpemu"
    env["PATH"] = str(vxpemu_dir) + os.pathsep + env.get("PATH", "")
    process = subprocess.Popen(
        [str(ide)],
        cwd=str(vxpemu_dir),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.terminate()
        process.wait(timeout=10)
    else:
        if process.returncode:
            raise SystemExit(f"Frozen GUI exited early with code {process.returncode}")

    result = {
        "gui_subsystem": "WINDOWS_GUI",
        "private_keys_in_release": 0,
        "sdk_tool_probe": "OK",
        "arm_toolchain_probe": "OK",
        "gui_startup_probe": "OK",
        "qt_msvc_runtime": "MATCHED",
        "qt_system_icu": "OK",
        "qt_collision_probe": "OK",
        "run_build_dynamic_imports": "OK",
    }
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
