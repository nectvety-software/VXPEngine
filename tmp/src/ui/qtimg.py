"""Qt<->PIL bridge and the tile image cache used by every widget that draws tiles."""

from __future__ import annotations

from PySide6.QtGui import QImage

_CACHE: dict[tuple[int, int], QImage] = {}


def qimage_from_pil(image) -> QImage:
    """RGBA PIL image -> QImage without depending on PIL's optional Qt glue."""
    rgba = image.convert("RGBA")
    data = rgba.tobytes("raw", "RGBA")
    qimg = QImage(data, rgba.width, rgba.height, rgba.width * 4, QImage.Format_RGBA8888)
    return qimg.copy()  # detach from the temporary buffer


def tile_image(sheet, index: int, version: int = 0) -> QImage | None:
    """Cached QImage of one atlas cell. `version` invalidates the whole cache."""
    if sheet is None or not (0 <= index < sheet.count):
        return None
    key = (version, index)
    cached = _CACHE.get(key)
    if cached is None:
        if sheet.tile(index).blank:
            return None
        _CACHE[key] = cached = qimage_from_pil(sheet.crop(index))
    return cached


def clear_cache() -> None:
    _CACHE.clear()
