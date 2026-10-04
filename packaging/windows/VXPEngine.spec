# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
from PyInstaller.utils.hooks import collect_all

ROOT = Path(SPECPATH).resolve().parents[1]
qta_datas, qta_binaries, qta_hidden = collect_all("qtawesome")

a = Analysis(
    [str(ROOT / "app" / "main.py")],
    pathex=[str(ROOT / "app"), str(ROOT / "simulator"), str(ROOT / "tools")],
    binaries=qta_binaries,
    datas=[(str(ROOT / "app" / "resources"), "resources"), *qta_datas],
    # verify_core is loaded after the user presses Run/Build.  PyInstaller
    # cannot discover that dynamic import without listing it explicitly.
    hiddenimports=[*qta_hidden, "verify_core"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[str(ROOT / "packaging" / "windows" / "qt_runtime_hook.py")],
    excludes=["tkinter", "unittest", "pip", "setuptools"],
    noarchive=False,
    optimize=1,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="VXPEngine",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    icon=str(ROOT / "app" / "resources" / "resources" / "app-icon.ico"),
    contents_directory="app",
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="VXPEngine",
)
