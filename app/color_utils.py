"""CSS-like color parsing shared by Inspector and the Camera2D renderer."""
from __future__ import annotations

import re
from PySide6.QtGui import QColor

_RGB = re.compile(r"rgba?\s*\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)(?:\s*,\s*([\d.]+))?\s*\)", re.I)


def parse_color(value, fallback: str = "#000000") -> QColor:
    text = str(value or "").strip()
    match = _RGB.fullmatch(text)
    if match:
        red, green, blue = (max(0, min(255, int(match.group(i)))) for i in range(1, 4))
        alpha_value = match.group(4)
        alpha = 255
        if alpha_value is not None:
            number = float(alpha_value)
            alpha = round(number * 255) if number <= 1 else round(number)
            alpha = max(0, min(255, alpha))
        return QColor(red, green, blue, alpha)
    color = QColor(text)
    return color if color.isValid() else QColor(fallback)


def format_rgb(color: QColor) -> str:
    return f"rgb({color.red()}, {color.green()}, {color.blue()})"


def format_hex(color: QColor) -> str:
    """Canonical Editor Assets format, for example ``#ff8a3d``."""
    return color.name(QColor.NameFormat.HexRgb).lower()
