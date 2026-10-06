"""Đóng gói + ký core coremre thành gói dùng chung cho nhiều ứng dụng.

Tạo:  packaging/coremre/<version>/
      ├── include/  src/          # nguồn core (tái sử dụng, không copy vào project)
      ├── cmake/UseCoremre.cmake  # target INTERFACE `coremre` + COREMRE_SOURCES
      ├── manifest.json           # sha256 từng tệp
      ├── manifest.sig            # chữ ký RSA của manifest.json (khóa của engine)
      └── coremre-sign-pub.pem    # khóa công khai để mọi bên thẩm tra
Và nén tất cả thành packaging/coremre-<version>.zip.

Ký bằng openssl (Git for Windows kèm openssl): khóa bí mật nằm ở
signing/coremre-sign-key.pem và KHÔNG bao giờ rời khỏi VXPEngine.
Xác minh: tools/verify_core.py (IDE chạy trước mỗi lần build).
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CORE_SRC = ROOT / "engine" / "coremre"
SIGN_KEY = ROOT / "signing" / "coremre-sign-key.pem"
PUB_KEY = ROOT / "signing" / "coremre-sign-pub.pem"
VERSION = "2.0.0"

USE_COREMRE_CMAKE = """# Dùng core coremre đã đóng gói: include(<gói>/cmake/UseCoremre.cmake)
# sau đó target_link_libraries(<app> PRIVATE coremre) và (tùy chọn) biên dịch
# ${COREMRE_SOURCES} vào app nếu app dùng phần C++ của core.
if(NOT TARGET coremre)
  get_filename_component(_COREMRE_ROOT "${CMAKE_CURRENT_LIST_DIR}/.." ABSOLUTE)
  include("${CMAKE_CURRENT_LIST_DIR}/CoremreSources.cmake")
  add_library(coremre STATIC ${COREMRE_SOURCES})
  add_library(VXPEngine::coremre ALIAS coremre)
  target_include_directories(coremre PUBLIC ${_COREMRE_ROOT}/include)
  if(MRE_SDK)
    target_include_directories(coremre PUBLIC ${MRE_SDK}/include)
  endif()
  target_compile_features(coremre PUBLIC cxx_std_17)
  target_compile_definitions(coremre PUBLIC COREMRE_PLATFORM_MRE=1 PIXELROOT32_ENABLE_PARTICLES=0 PIXELROOT32_ENABLE_DIRTY_REGIONS=1)
  set_target_properties(coremre PROPERTIES CXX_EXTENSIONS OFF POSITION_INDEPENDENT_CODE ON)
  if(CMAKE_SYSTEM_NAME STREQUAL "Generic")
    target_compile_options(coremre PRIVATE -Os -ffunction-sections -fdata-sections -fno-exceptions -fno-rtti)
  endif()
endif()
"""


def _openssl() -> str:
    found = shutil.which("openssl")
    if found:
        return found
    git_ssl = Path("C:/Program Files/Git/usr/bin/openssl.exe")
    if git_ssl.is_file():
        return str(git_ssl)
    raise RuntimeError("Không tìm thấy openssl (cần để ký gói core).")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def pack() -> Path:
    if not SIGN_KEY.is_file():
        raise RuntimeError(f"Thiếu khóa ký {SIGN_KEY} (engine sở hữu).")
    out = ROOT / "packaging" / "coremre" / VERSION
    if out.exists():
        shutil.rmtree(out)
    (out / "cmake").mkdir(parents=True)
    for part in ("include", "src"):
        shutil.copytree(CORE_SRC / part, out / part)
    shutil.copytree(CORE_SRC / "tests", out / "tests")

    # Ship the VXPGDX asset pipeline with the SDK package so projects can
    # convert Tiled JSON/TMJ and atlas manifests without cloning the repo.
    (out / "tools").mkdir(parents=True, exist_ok=True)
    for tool_name in ("vxpgdx_pack_tiled.py", "vxpgdx_pack_atlas.py"):
        shutil.copy2(ROOT / "tools" / tool_name, out / "tools" / tool_name)
    (out / "docs").mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / "docs" / "VXPGDX.md", out / "docs" / "VXPGDX.md")
    shutil.copy2(ROOT / "docs" / "GAME_ART_STYLES.md", out / "docs" / "GAME_ART_STYLES.md")
    shutil.copy2(ROOT / "docs" / "URBAN_TOON_3D.md", out / "docs" / "URBAN_TOON_3D.md")
    shutil.copy2(ROOT / "docs" / "DUNGEON_SYNTH_3D.md", out / "docs" / "DUNGEON_SYNTH_3D.md")
    shutil.copy2(ROOT / "docs" / "ACTOR_SPRITES.md", out / "docs" / "ACTOR_SPRITES.md")

    cmake_text = (CORE_SRC / "CMakeLists.txt").read_text(encoding="utf-8")
    match = re.search(r"set\(COREMRE_SOURCES\s+(.*?)\n\)", cmake_text, re.DOTALL)
    if not match:
        raise RuntimeError("Không đọc được danh sách COREMRE_SOURCES chuẩn.")
    sources_rel = [line.strip() for line in match.group(1).splitlines() if line.strip()]
    missing = [item for item in sources_rel if not (out / item).is_file()]
    if missing:
        raise RuntimeError(f"Thiếu source coremre: {', '.join(missing)}")
    (out / "cmake" / "CoremreSources.cmake").write_text(
        'set(COREMRE_SOURCES\n  ' + "\n  ".join(f"${{_COREMRE_ROOT}}/{r}" for r in sources_rel) + "\n)\n",
        encoding="utf-8",
    )
    (out / "cmake" / "UseCoremre.cmake").write_text(USE_COREMRE_CMAKE, encoding="utf-8")

    # The repository no longer tracks signing/coremre-sign-pub.pem.  Derive the
    # public key from the local private signing key when needed so packaging
    # remains reproducible without restoring a stale tracked public-key file.
    ssl = _openssl()
    packaged_pub = out / "coremre-sign-pub.pem"
    if PUB_KEY.is_file():
        shutil.copy2(PUB_KEY, packaged_pub)
    else:
        subprocess.run(
            [ssl, "pkey", "-in", str(SIGN_KEY), "-pubout", "-out", str(packaged_pub)],
            check=True, capture_output=True,
        )

    manifest = {"name": "coremre", "version": VERSION, "files": {}}
    for path in sorted(out.rglob("*")):
        if not path.is_file() or path.name in {"manifest.json", "manifest.sig"}:
            continue
        manifest["files"][path.relative_to(out).as_posix()] = _sha256(path)
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    subprocess.run(
        [ssl, "dgst", "-sha256", "-sign", str(SIGN_KEY),
         "-out", str(out / "manifest.sig"), str(out / "manifest.json")],
        check=True, capture_output=True,
    )

    zip_path = ROOT / "packaging" / f"coremre-{VERSION}.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(out.rglob("*")):
            if path.is_file():
                zf.write(path, path.relative_to(out).as_posix())
    print(f"Packed coremre {VERSION}: {len(manifest['files'])} files -> {out} and {zip_path}")
    return out


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    sys.exit(0 if pack() else 1)
