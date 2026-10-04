"""Font icon helpers for VXPEngine.

QtAwesome supplies Font Awesome as a Python dependency, so the project does
not bundle or distribute any font file itself.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from PySide6.QtGui import QColor, QIcon

try:
    import qtawesome as qta
except Exception:  # App still opens if QtAwesome was not installed yet.
    qta = None


@lru_cache(maxsize=256)
def _cached_icon(name: str, color: str, color_active: str) -> QIcon:
    if qta is None:
        return QIcon()
    try:
        options = {}
        if color:
            options["color"] = QColor(color)
        if color_active:
            options["color_active"] = QColor(color_active)
        return qta.icon(name, **options)
    except Exception:
        return QIcon()


def icon(name: str, color: str = "#9AA8BD", color_active: str = "#FFFFFF") -> QIcon:
    """Return a safe Font Awesome icon; invalid names degrade to an empty icon."""
    return _cached_icon(name, color, color_active)


@lru_cache(maxsize=1)
def app_icon() -> QIcon:
    """Return the bundled VXPEngine application icon."""
    path = Path(__file__).resolve().parent.parent / "resources" / "app-icon.ico"
    if not path.exists():
        path = path.with_suffix(".png")
    return QIcon(str(path)) if path.exists() else icon("fa5s.gamepad", "#6D9FFF")
