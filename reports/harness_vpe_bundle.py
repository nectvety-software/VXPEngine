"""Verify first-run library installation with isolated writable folders."""
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))
sys.path.insert(0, str(ROOT / "packaging/windows"))
from verify_vpe_bundle import verify_bundle
from vendor.vpe_pixel.vpx_editor import paths

bundle = ROOT / "app/vendor/vpe_pixel"
counts = verify_bundle(bundle)
with tempfile.TemporaryDirectory(prefix="vxpe-pixel-library-") as temporary:
    destination = Path(temporary) / "Documents/VPE Pixel"
    assert paths.seed_library(destination) == counts["library"]
    file = next(destination.rglob("*.vpe"))
    file.write_bytes(b"user-edited-artwork")
    assert paths.seed_library(destination) == 0
    assert file.read_bytes() == b"user-edited-artwork"
    other = next(path for path in destination.rglob("*.vpe") if path != file)
    other.unlink()
    assert paths.seed_library(destination) == 1
    # Reproduce PyInstaller's contents_directory='app' without relying on cwd.
    sys._MEIPASS = str(ROOT / "app")
    try:
        assert paths.bundle_dir() == bundle
        assert paths.seed_library(destination) == 0
    finally:
        del sys._MEIPASS
print("PASS: bundled", counts, "first-run seeding, user edits, repair, frozen paths")
