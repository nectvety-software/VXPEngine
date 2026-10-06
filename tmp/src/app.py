"""Application bootstrap and the offscreen self-test harness."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication, QWidget

from .engine.project import Project
from .ui import dialogs, theme
from .ui.main_window import EditorWindow

APP_NAME = "Terra Editor"
ORG = "Terra"


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="terra", description=APP_NAME)
    parser.add_argument("project", nargs="?", help=".terra.json project to open")
    parser.add_argument("--sheet", help="tilesheet PNG to open instead")
    parser.add_argument("--theme", choices=sorted(theme.PALETTES), default="dark")
    parser.add_argument("--cell", default="auto", help="tile size: auto, N, or WxH")
    parser.add_argument("--selftest", action="store_true",
                        help="render the UI offscreen to out/selftest/ and exit")
    parser.add_argument("--size", default="1380x860", help="initial window size, WxH")
    return parser.parse_args(argv)


def make_application(args) -> QApplication:
    app = QApplication.instance() or QApplication([sys.argv[0] or APP_NAME])
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(ORG)
    app.setApplicationDisplayName(APP_NAME)
    theme.apply(app, args.theme)
    return app


def make_project(args) -> Project | None:
    if args.project:
        return Project.load(args.project)
    if args.sheet:
        return Project.new(args.sheet, 40, 24, args.cell)
    return None


def run(argv=None) -> int:
    args = parse_args(argv)
    app = make_application(args)
    if args.selftest:
        return selftest(app, args)

    window = EditorWindow(make_project(args))
    width, height = (int(v) for v in args.size.lower().split("x"))
    window.resize(width, height)
    window.apply_theme(args.theme)
    window.show()
    return app.exec()


# ------------------------------------------------------------------ selftest

def _shot(widget: QWidget, path: Path) -> None:
    widget.show()
    for _ in range(4):
        QApplication.processEvents()
    widget.grab().save(str(path))
    print(f"  wrote {path.name}  {path.stat().st_size // 1024} KB")


def selftest(app: QApplication, args) -> int:
    """Drive the real widgets offscreen and dump PNGs — the only way to see this UI here."""
    out = Path("out/selftest")
    out.mkdir(parents=True, exist_ok=True)
    sheet = Path(args.sheet or "tilemaps.png")
    if not sheet.is_file():
        print(f"ERROR: sheet not found: {sheet}")
        return 2

    project = Project.new(sheet, 26, 15, args.cell)
    m = project.map
    m.paint_rect(0, 0, m.width - 1, m.height - 1, 5, filled=False)
    m.paint_rect(3, 3, 14, 9, 1, filled=True)
    m.add_layer("Detail")
    m.paint_line(4, 4, 12, 10, 34)
    m.paint(16, 4, 100, m.layer(1))

    window = EditorWindow(project)
    window.resize(*(int(v) for v in args.size.lower().split("x")))
    window.apply_theme(args.theme)
    window.select_tool("brush")
    window._commit_paint("Vẽ tile", m.paint(18, 6, 140))
    window._show_cursor(12, 7)

    _shot(window, out / "editor-dark.png")
    window.label_button.setChecked(True)
    _shot(window, out / "editor-labels.png")
    window.label_button.setChecked(False)

    window.apply_theme("light")
    _shot(window, out / "editor-light.png")
    window.apply_theme("dark")

    info = dialogs.MessageDialog(window, "Đã lưu dự án", "demo.terra.json",
                                 "176 ô đã tách · engine v0.1.0", "success")
    _shot(info, out / "dialog-success.png")
    info.close()

    warn = dialogs.MessageDialog(window, "Thay đổi chưa lưu", "Tắt trình soạn thảo?",
                                 "Có 12 thao tác chưa lưu. Lưu trước khi thoát?", "warning",
                                 ("Bỏ thay đổi", "Huỷ", "Lưu"))
    _shot(warn, out / "dialog-warning.png")
    warn.close()

    files = dialogs.FileDialog(window, "Mở tilesheet", Path.cwd(), ["png", "jpg"], False)
    _shot(files, out / "dialog-files.png")
    files.close()

    about = dialogs.AboutDialog(window, "Terra Editor", "0.1.0",
                                {"Engine": "terra 0.1.0", "Raster": "Pillow + NumPy",
                                 "Sheet": sheet.name})
    _shot(about, out / "dialog-about.png")
    about.close()

    window.toggle_maximize()
    _shot(window, out / "editor-maximized.png")

    print(f"OK  selftest -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
