"""Regression: copied/moved projects automatically discard foreign CMake cache."""
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

from vxp_runner import VxpRunner


with tempfile.TemporaryDirectory(prefix="vxpe_cache_relocation_") as tmp:
    project = Path(tmp) / "MedievalArcheryDemo"
    build = project / "build-arm"
    generated = build / "main" / "old.vxp"
    generated.parent.mkdir(parents=True)
    generated.write_bytes(b"stale")
    (build / "CMakeCache.txt").write_text(
        "CMAKE_CACHEFILE_DIR:INTERNAL=D:/old/PocketToolkitDemo/build-arm\n"
        "CMAKE_HOME_DIRECTORY:INTERNAL=D:/old/PocketToolkitDemo\n",
        encoding="utf-8",
    )

    assert VxpRunner._reset_foreign_cmake_cache(project, "build-arm")
    assert not build.exists(), "foreign build tree was not removed"

    build.mkdir()
    (build / "CMakeCache.txt").write_text(
        f"CMAKE_CACHEFILE_DIR:INTERNAL={build.as_posix()}\n"
        f"CMAKE_HOME_DIRECTORY:INTERNAL={project.as_posix()}\n",
        encoding="utf-8",
    )
    assert not VxpRunner._reset_foreign_cmake_cache(project, "build-arm")
    assert build.exists(), "matching build tree must be preserved"

    try:
        VxpRunner._reset_foreign_cmake_cache(project, "unmanaged-output")
    except ValueError:
        pass
    else:
        raise AssertionError("unmanaged directory must never be deleted")

print("PASS: relocated project cache is reset safely; matching cache is reused")
