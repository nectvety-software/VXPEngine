"""Create deterministic project-local pixel art and short PCM sound cues.

These files keep the sample runnable before optional Sprite Fusion replacements
are generated.  The RAW format is the VXPEngine RGB565 + one-bit alpha format.
"""
from __future__ import annotations

import math
import struct
import wave
from pathlib import Path

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPen, QPolygon

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets" / "spritefusion"
GEN = ROOT / "resources" / "gen"


def new_image(width: int, height: int, color: str | None = None) -> QImage:
    image = QImage(width, height, QImage.Format.Format_RGBA8888)
    image.fill(QColor(color) if color else Qt.GlobalColor.transparent)
    return image


def save_raw(image: QImage, path: Path) -> None:
    image = image.convertToFormat(QImage.Format.Format_RGBA8888)
    width, height = image.width(), image.height()
    opaque = all(image.pixelColor(x, y).alpha() == 255 for y in range(height) for x in range(width))
    pixels = bytearray()
    mask = bytearray((width * height + 7) // 8)
    for y in range(height):
        for x in range(width):
            color = image.pixelColor(x, y)
            rgb565 = ((color.red() & 0xF8) << 8) | ((color.green() & 0xFC) << 3) | (color.blue() >> 3)
            pixels += struct.pack("<H", rgb565)
            index = y * width + x
            if color.alpha() >= 128:
                mask[index >> 3] |= 0x80 >> (index & 7)
    path.write_bytes(struct.pack("<HHBBBB", width, height, int(opaque), 0, 0, 0) + pixels + mask)


def battlefield() -> QImage:
    image = new_image(240, 340, "#18243b")
    p = QPainter(image); p.setRenderHint(QPainter.RenderHint.Antialiasing, False)
    bands = ("#1b2944", "#243453", "#314462", "#49536d")
    for y in range(0, 250):
        p.fillRect(0, y, 240, 1, QColor(bands[min(3, y // 64)]))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor("#e7c77b")); p.drawRect(184, 36, 25, 25)
    p.setBrush(QColor("#54516d"))
    p.drawPolygon(QPolygon([QPoint(0, 189), QPoint(38, 137), QPoint(75, 178), QPoint(112, 119), QPoint(160, 176), QPoint(204, 132), QPoint(240, 176), QPoint(240, 245), QPoint(0, 245)]))
    p.setBrush(QColor("#333b50"))
    p.drawPolygon(QPolygon([QPoint(0, 220), QPoint(54, 169), QPoint(98, 218), QPoint(147, 155), QPoint(195, 215), QPoint(240, 183), QPoint(240, 264), QPoint(0, 264)]))
    p.setBrush(QColor("#172c2c"))
    for x in range(-8, 248, 15):
        h = 22 + (x * 7 % 19)
        p.drawPolygon(QPolygon([QPoint(x, 270), QPoint(x + 7, 270 - h), QPoint(x + 14, 270)]))
    p.fillRect(0, 270, 240, 70, QColor("#3d4b2d"))
    p.fillRect(0, 270, 240, 5, QColor("#82924b"))
    for x in range(0, 240, 9):
        p.fillRect(x, 277 + (x % 4), 5, 2, QColor("#586336"))
    p.end(); return image


def archer(enemy: bool) -> QImage:
    image = new_image(40, 54)
    p = QPainter(image); p.setRenderHint(QPainter.RenderHint.Antialiasing, False)
    outline = QColor("#191923"); skin = QColor("#d7a66d"); leather = QColor("#6f4528")
    cloth = QColor("#a47731" if enemy else "#2e6c4d")
    accent = QColor("#68436f" if enemy else "#476d3b")
    p.fillRect(12, 12, 16, 13, outline); p.fillRect(14, 14, 12, 11, skin)
    if enemy:
        p.fillRect(11, 9, 18, 8, QColor("#727887")); p.fillRect(14, 6, 3, 5, QColor("#a47731")); p.fillRect(24, 5, 3, 6, QColor("#a47731"))
        p.fillRect(16, 16, 9, 3, QColor("#343846"))
    else:
        p.drawPolygon(QPolygon([QPoint(10, 15), QPoint(20, 4), QPoint(30, 15), QPoint(27, 21), QPoint(13, 21)])); p.setBrush(cloth)
        p.fillRect(10, 14, 20, 7, cloth)
    p.fillRect(11, 25, 18, 19, outline); p.fillRect(13, 26, 14, 17, cloth); p.fillRect(9, 29, 4, 12, accent)
    p.fillRect(13, 43, 6, 9, outline); p.fillRect(23, 43, 6, 9, outline)
    p.setPen(QPen(QColor("#c28b4c"), 2)); p.drawArc(26, 15, 12, 30, -90 * 16, 180 * 16)
    p.setPen(QPen(QColor("#d8c9a0"), 1)); p.drawLine(32, 17, 32, 43)
    p.fillRect(18, 17, 2, 2, QColor("#231b1a")); p.end(); return image


def arrow() -> QImage:
    image = new_image(16, 8); p = QPainter(image)
    p.fillRect(2, 3, 11, 2, QColor("#b87b3e")); p.fillRect(12, 2, 3, 4, QColor("#d8d2b0"))
    p.fillRect(0, 2, 3, 1, QColor("#c45f45")); p.fillRect(0, 5, 3, 1, QColor("#c45f45")); p.end(); return image


def logo() -> QImage:
    image = new_image(176, 70); p = QPainter(image); p.setRenderHint(QPainter.RenderHint.Antialiasing, False)
    bronze = QColor("#b77a38"); gold = QColor("#f1d27a"); dark = QColor("#132536"); cream = QColor("#fff0c2")
    p.setPen(QPen(bronze, 4)); p.setBrush(dark); p.drawRect(7, 13, 162, 50)
    p.setPen(QPen(gold, 3)); p.drawLine(40, 55, 68, 19); p.drawLine(108, 19, 136, 55)
    p.setPen(QPen(cream, 2)); p.drawLine(65, 20, 111, 55); p.drawLine(111, 20, 65, 55)
    # Block-letter mark; runtime adds readable title text.
    p.setPen(Qt.PenStyle.NoPen); p.setBrush(gold)
    p.drawPolygon(QPolygon([QPoint(78, 5), QPoint(85, 12), QPoint(92, 5), QPoint(99, 12), QPoint(106, 5), QPoint(103, 18), QPoint(81, 18)]))
    p.end(); return image


def tone(path: Path, frequency: float, duration: float) -> None:
    rate = 8000; count = int(rate * duration)
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1); wav.setsampwidth(1); wav.setframerate(rate)
        data = bytes(int(128 + 65 * math.sin(2 * math.pi * frequency * i / rate) * (1 - i / count)) for i in range(count))
        wav.writeframes(data)


def main() -> None:
    ASSETS.mkdir(parents=True, exist_ok=True); GEN.mkdir(parents=True, exist_ok=True)
    images = {"battlefield": battlefield(), "player_archer": archer(False), "enemy_archer": archer(True), "arrow": arrow(), "logo": logo()}
    reused = 0
    for name, placeholder in images.items():
        source_path = ASSETS / f"{name}.png"
        image = QImage(str(source_path)) if source_path.is_file() else QImage()
        if image.isNull():
            image = placeholder
            image.save(str(source_path), "PNG")
        else:
            reused += 1
        # Runtime slots have fixed sizes; preserve a replacement's source PNG
        # and normalize only its packed RAW copy with nearest-neighbour pixels.
        if image.size() != placeholder.size():
            image = image.scaled(placeholder.size(), Qt.AspectRatioMode.IgnoreAspectRatio,
                                 Qt.TransformationMode.FastTransformation)
        save_raw(image, GEN / f"{name}.raw")
    tone(GEN / "bow.wav", 520, 0.10); tone(GEN / "hit.wav", 170, 0.14); tone(GEN / "victory.wav", 760, 0.30)
    print(f"Prepared {len(images)} images ({reused} existing) and 3 sound cues")


if __name__ == "__main__":
    main()
