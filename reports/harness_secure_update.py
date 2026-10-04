"""Static security checks for the MSI update channel."""
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])

from update_checker import is_newer_version
from update_installer import UpdateInstaller

assert is_newer_version("2.0.1", "2.0.0")
assert not is_newer_version("2.0.0", "2.0.0")
assert UpdateInstaller._safe_https("https://github.com/vxpstore/VXPEngine/releases/download/v2.0.1/a.msi")
assert not UpdateInstaller._safe_https("http://example.com/a.msi")
assert not UpdateInstaller._safe_https("file:///C:/tmp/a.msi")
policy = UpdateInstaller._load_policy()
assert policy.get("require_authenticode") is True, policy
print("PASS: update requires HTTPS; source mode fails closed on Authenticode")
