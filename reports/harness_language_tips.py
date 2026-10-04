"""Regression: contextual library tips, language preference, and menu contrast."""
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

from PySide6.QtCore import QSettings
from PySide6.QtGui import QColor, QPalette
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from main import MainWindow
from widgets.panels import build_tilemap_panel

app = QApplication.instance() or QApplication([])
settings = QSettings("VXPEngine", "VXPEngine")
old_language = settings.value("ui/language", None)
settings.setValue("ui/language", "system")

try:
    window = MainWindow()
    assert window.ui_language == "system"
    assert len(window.language_group.actions()) >= 8
    assert any(action.isChecked() and action.data() == "system" for action in window.language_group.actions())

    window._set_ui_language("vi")
    assert window._top_menus["menu.settings"].title() == "Cài đặt"
    assert settings.value("ui/language") == "vi"
    window._set_ui_language("en")
    assert window._top_menus["menu.help"].title() == "Help"

    palette = window.menu_bar.palette()
    foreground = palette.color(QPalette.ColorRole.WindowText)
    background = palette.color(QPalette.ColorRole.Window)
    assert foreground.lightness() > background.lightness() + 80
    assert palette.color(QPalette.ColorRole.HighlightedText) == QColor("#FFFFFF")

    with tempfile.TemporaryDirectory(prefix="vxpe_tip_") as tmp:
        panel = build_tilemap_panel(tmp)
        panel.tabs.setCurrentIndex(1)
        panel.show_current_tip(35)
        assert not panel.info.isHidden()
        assert "Frame Perspective" in panel.info.text()
        QTest.qWait(80)
        app.processEvents()
        assert panel.info.isHidden()
        panel.tabs.setCurrentIndex(2)
        assert not panel.info.isHidden()
        panel.deleteLater()

    window.deleteLater()
    app.processEvents()
finally:
    if old_language is None:
        settings.remove("ui/language")
    else:
        settings.setValue("ui/language", old_language)

print("PASS: auto-hide context tips + Help entry + system language + dark menu contrast")
