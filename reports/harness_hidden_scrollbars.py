"""Regression: scrollbar chrome is hidden globally while scroll ranges remain usable."""
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

from PySide6.QtWidgets import QApplication, QPlainTextEdit

app = QApplication.instance() or QApplication([])
app.setStyleSheet((ROOT / "app/resources/dark_theme.qss").read_text(encoding="utf-8"))
editor = QPlainTextEdit()
editor.resize(120, 80)
editor.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
editor.setPlainText((("VXPEngine" * 40) + "\n") * 100)
editor.show()
app.processEvents()

vertical = editor.verticalScrollBar()
horizontal = editor.horizontalScrollBar()
assert vertical.width() == 0 and vertical.sizeHint().width() == 0
assert horizontal.height() == 0 and horizontal.sizeHint().height() == 0
assert vertical.maximum() > 0 and horizontal.maximum() > 0
vertical.setValue(vertical.maximum())
horizontal.setValue(horizontal.maximum())
assert vertical.value() == vertical.maximum() and horizontal.value() == horizontal.maximum()

print("PASS: all scrollbar chrome hidden; wheel/touch/keyboard scroll ranges preserved")
