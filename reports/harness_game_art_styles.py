"""Verify editor palette operations and generate a visual comparison."""
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtWidgets import QApplication
from game_art_styles import GAME_ART_STYLES, apply_game_palette
from widgets.asset_editor import AssetEditorDialog

app = QApplication.instance() or QApplication([])
source = QImage(str(ROOT / "reports/video_style_reference/0.png"))
assert not source.isNull()
probe = QImage(3, 1, QImage.Format.Format_ARGB32)
for x, alpha in enumerate((0, 127, 255)):
    probe.setPixelColor(x, 0, QColor(103, 149, 198, alpha))
for style, (_, codes) in GAME_ART_STYLES.items():
    result = apply_game_palette(probe, style)
    assert result.size() == probe.size()
    palette = {QColor(code).rgb() for code in codes.split()}
    for x, alpha in enumerate((0, 127, 255)):
        assert result.pixelColor(x, 0).alpha() == alpha
        if alpha:
            assert result.pixelColor(x, 0).rgb() in palette
    assert probe.pixelColor(1, 0) == QColor(103, 149, 198, 127)

with tempfile.TemporaryDirectory(prefix="game-art-") as td:
    dialog = AssetEditorDialog(Path(td))
    dialog.canvas.image = probe.copy()
    for style in GAME_ART_STYLES:
        dialog.style_combo.setCurrentText(style)
        dialog.apply_style()
        assert dialog.canvas.image.size() == probe.size()
        assert dialog.canvas.image.pixelColor(1, 0).alpha() == 127
    dialog.close()

preview = QImage(960, ((len(GAME_ART_STYLES) + 3) // 3) * 220, QImage.Format.Format_RGB32)
preview.fill(QColor("#181a24"))
paint = QPainter(preview)
paint.setPen(QColor("white"))
for i, style in enumerate(["Original", *GAME_ART_STYLES]):
    x, y = (i % 3) * 320, (i // 3) * 220
    paint.drawText(x + 8, y + 20, style)
    image = source if i == 0 else apply_game_palette(source, style)
    paint.drawImage(x, y + 30, image)
paint.end()
assert preview.save(str(ROOT / "reports/game_art_styles_preview.png"))
print(f"PASS: {len(GAME_ART_STYLES)} palettes, dimensions, alpha, source preservation, editor integration")
