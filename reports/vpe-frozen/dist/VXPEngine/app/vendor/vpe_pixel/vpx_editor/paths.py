"""App data / project folder locations.

When frozen (PyInstaller .exe):
  - settings & cache  → %APPDATA%\\VXP Pixel Editor
  - projects/exports  → %USERPROFILE%\\Documents\\VPE Pixel

When run from source:
  - same Documents\\VPE Pixel folder for projects (shared with the exe)
  - settings still go to APPDATA via QSettings, or a local override under APPDATA
"""

from __future__ import annotations

import os
import sys
import json
import shutil
from pathlib import Path
from typing import Optional

APP_DIR_NAME = "VXP Pixel Editor"
PROJECT_DIR_NAME = "VPE Pixel"  # Documents\VPE Pixel


def bundle_dir() -> Path:
    """Read-only bundled tools, styles and starter library, also inside an EXE."""
    if hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / "vendor" / "vpe_pixel"
    return Path(__file__).resolve().parent.parent


def seed_library(destination: Path) -> int:
    """Install missing starter files; never replace a user's existing artwork."""
    bundled = bundle_dir()
    manifest = json.loads((bundled / "library-manifest.json").read_text(encoding="utf-8"))
    copied = 0
    for entry in manifest["files"]:
        relative = Path(entry["path"])
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("Invalid bundled library path")
        target = destination / relative
        if target.exists():
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            with (bundled / "library" / relative).open("rb") as source, target.open("xb") as output:
                shutil.copyfileobj(source, output)
            copied += 1
        except FileExistsError:
            pass
    return copied


def is_frozen() -> bool:
    """True when running as a PyInstaller executable."""
    return bool(getattr(sys, "frozen", False)) or hasattr(sys, "_MEIPASS")


def exe_dir() -> Path:
    """Directory containing the executable (or the project root when sourced)."""
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def app_data_dir(create: bool = True) -> Path:
    """%APPDATA%\\VXP Pixel Editor — settings, cache, autosave."""
    base = os.environ.get("APPDATA") or os.environ.get("LOCALAPPDATA")
    if base:
        root = Path(base) / APP_DIR_NAME
    else:
        root = Path.home() / "AppData" / "Roaming" / APP_DIR_NAME
    if create:
        root.mkdir(parents=True, exist_ok=True)
    return root


def documents_dir() -> Path:
    r"""User Documents folder (CSIDL_PERSONAL / USERPROFILE\\Documents)."""
    # Known folder first (handles OneDrive-redirected Documents)
    try:
        from PySide6.QtCore import QStandardPaths

        docs = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DocumentsLocation)
        if docs:
            return Path(docs)
    except Exception:
        pass
    home = Path.home()
    for cand in (
        home / "Documents",
        home / "My Documents",
        home / "OneDrive" / "Documents",
    ):
        if cand.is_dir():
            return cand
    return home / "Documents"


def project_dir(create: bool = True) -> Path:
    """Documents\\VPE Pixel — default folder for .vpe / BMP / PNG exports."""
    root = documents_dir() / PROJECT_DIR_NAME
    if create:
        try:
            root.mkdir(parents=True, exist_ok=True)
        except OSError:
            # Keep writable artwork outside the installation directory.
            root = app_data_dir() / PROJECT_DIR_NAME
            root.mkdir(parents=True, exist_ok=True)
    return root


def settings_file() -> Path:
    """INI settings path under APPDATA."""
    return app_data_dir() / "settings.ini"


def autosave_file() -> Path:
    return app_data_dir() / "autosave.vpe"


def export_dir(create: bool = True) -> Path:
    """Subfolder for BMP/PNG exports inside Documents\\VPE Pixel."""
    root = project_dir(create=create) / "exports"
    if create:
        root.mkdir(parents=True, exist_ok=True)
    return root


def ensure_layout() -> dict:
    """Create folders and return the resolved paths (used by startup & build)."""
    projects = project_dir(True)
    seed_library(projects)
    paths = {
        "app_data": app_data_dir(True),
        "documents": documents_dir(),
        "projects": projects,
        "exports": export_dir(True),
        "settings": settings_file(),
        "frozen": is_frozen(),
        "exe_dir": exe_dir(),
    }
    return paths


if __name__ == "__main__":
    info = ensure_layout()
    for k, v in info.items():
        print(f"{k}: {v}")
