"""VPE565 project format codec + BMP/PNG export helpers.

Binary layout (little-endian), matching LuaS30 VXP Pixel Editor:

    Offset  Size  Field
    0       6     Magic  b"VPE565"
    6       2     Version u16 = 1  (stored as 01 00)
    8       2     Width  u16
    10      2     Height u16
    12      4     Payload size u32  (= width * height * 2)
    16      N     RGB565 pixels, row-major, little-endian words

RGB565 packing: rrrrrggg gggbbbbb (high bits red).
"""

from __future__ import annotations

import struct
from pathlib import Path
from typing import Iterable, List, Sequence, Tuple

MAGIC = b"VPE565"
VERSION = 1
HEADER_SIZE = 16
MAX_DIM = 640


class VpeError(ValueError):
    """Raised when a .vpe blob is invalid."""


def rgb_to_565(r: int, g: int, b: int) -> int:
    return ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)


def c565_to_rgb(c: int) -> Tuple[int, int, int]:
    c &= 0xFFFF
    r = (c >> 11) & 0x1F
    g = (c >> 5) & 0x3F
    b = c & 0x1F
    return (
        (r * 255 + 15) // 31,
        (g * 255 + 31) // 63,
        (b * 255 + 15) // 31,
    )


def qcolor_to_565(qcolor) -> int:
    return rgb_to_565(qcolor.red(), qcolor.green(), qcolor.blue())


def encode_vpe(width: int, height: int, pixels: Sequence[int]) -> bytes:
    """Encode an RGB565 buffer into a .vpe blob."""
    if width < 1 or height < 1:
        raise VpeError("invalid-size")
    if width > MAX_DIM or height > MAX_DIM:
        raise VpeError("image-too-large")
    expected = width * height
    if len(pixels) != expected:
        raise VpeError("pixel-count")
    payload = bytearray(expected * 2)
    for i, px in enumerate(pixels):
        struct.pack_into("<H", payload, i * 2, int(px) & 0xFFFF)
    header = MAGIC + struct.pack("<HHHI", VERSION, width, height, len(payload))
    return header + bytes(payload)


def decode_vpe(blob: bytes) -> Tuple[int, int, List[int]]:
    """Decode a .vpe blob into (width, height, pixels)."""
    if not isinstance(blob, (bytes, bytearray)):
        raise VpeError("vpe-truncated")
    if len(blob) < HEADER_SIZE:
        raise VpeError("vpe-truncated")
    if bytes(blob[:8]) != MAGIC + struct.pack("<H", VERSION):
        raise VpeError("vpe-magic")
    width, height, payload_size = struct.unpack_from("<HHI", blob, 8)
    if width < 1 or height < 1:
        raise VpeError("vpe-size")
    if width > MAX_DIM or height > MAX_DIM:
        raise VpeError("image-too-large")
    expected = width * height * 2
    if payload_size != expected or len(blob) != HEADER_SIZE + payload_size:
        raise VpeError("vpe-payload-size")
    pixels = list(struct.unpack_from(f"<{width * height}H", blob, HEADER_SIZE))
    return width, height, pixels


def save_vpe(path: str | Path, width: int, height: int, pixels: Sequence[int]) -> None:
    Path(path).write_bytes(encode_vpe(width, height, pixels))


def load_vpe(path: str | Path) -> Tuple[int, int, List[int]]:
    data = Path(path).read_bytes()
    return decode_vpe(data)


def encode_bmp(width: int, height: int, pixels: Sequence[int]) -> bytes:
    """24-bit Windows BMP (bottom-up BGR) from RGB565 pixels."""
    if width < 1 or height < 1:
        raise VpeError("invalid-size")
    if len(pixels) != width * height:
        raise VpeError("pixel-count")
    row_bytes = width * 3
    pad = (4 - (row_bytes % 4)) % 4
    image_bytes = (row_bytes + pad) * height
    total = 54 + image_bytes
    file_header = b"BM" + struct.pack("<IHHI", total, 0, 0, 54)
    dib = struct.pack("<IiiHHIIiiII", 40, width, height, 1, 24, 0, image_bytes, 2835, 2835, 0, 0)
    rows = []
    for y in range(height - 1, -1, -1):
        row = bytearray()
        base = y * width
        for x in range(width):
            r, g, b = c565_to_rgb(pixels[base + x])
            row += bytes((b, g, r))
        if pad:
            row += b"\x00" * pad
        rows.append(bytes(row))
    return file_header + dib + b"".join(rows)


def save_bmp(path: str | Path, width: int, height: int, pixels: Sequence[int]) -> None:
    Path(path).write_bytes(encode_bmp(width, height, pixels))


def save_png(path: str | Path, width: int, height: int, pixels: Sequence[int]) -> None:
    """Write PNG via Qt (requires QApplication)."""
    try:
        from PySide6.QtGui import QImage, QColor
    except ImportError as exc:
        raise VpeError("qt-unavailable") from exc
    img = QImage(width, height, QImage.Format_RGB32)
    for y in range(height):
        base = y * width
        for x in range(width):
            r, g, b = c565_to_rgb(pixels[base + x])
            img.setPixelColor(x, y, QColor(r, g, b))
    if not img.save(str(path), "PNG"):
        raise VpeError("png-save-failed")


def load_image_as_565(path: str | Path) -> Tuple[int, int, List[int]]:
    """Load PNG/JPG/BMP into RGB565 pixels via Qt."""
    try:
        from PySide6.QtGui import QImage
        from PySide6.QtCore import Qt
    except ImportError as exc:
        raise VpeError("qt-unavailable") from exc
    img = QImage(str(path))
    if img.isNull():
        raise VpeError("image-load-failed")
    img = img.convertToFormat(QImage.Format_ARGB32)
    w, h = img.width(), img.height()
    if w < 1 or h < 1:
        raise VpeError("invalid-size")
    if w > MAX_DIM or h > MAX_DIM:
        raise VpeError("image-too-large")
    pixels: List[int] = []
    for y in range(h):
        for x in range(w):
            c = img.pixelColor(x, y)
            # Treat fully transparent as white (RGB565 has no alpha).
            if c.alpha() < 16:
                pixels.append(0xFFFF)
            else:
                pixels.append(rgb_to_565(c.red(), c.green(), c.blue()))
    return w, h, pixels
