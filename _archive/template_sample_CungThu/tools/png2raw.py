"""png2raw.py - convert PNG assets into the project's .raw sprite format.

.raw layout (same as sprites in resources/gen):
    header: uint16 width LE, uint16 height LE, uint8 opaque, uint8 reserved
    pixels: width*height RGB565 little-endian, row-major
    mask:   1 bit per pixel, row-major bitstream; bit index o = y*w + x,
            byte o>>3, bit 0x80 >> (o&7); 1 = opaque. Always written.

Usage (run with the VXPEngine IDE venv so PySide6 is available):
    python tools/png2raw.py <in.png> <out.raw> <w> <h> [--opaque]
"""
from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage


ALPHA_THRESHOLD = 128


def rgb565(r: int, g: int, b: int) -> int:
    return ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)


def convert(src: Path, dst: Path, width: int, height: int, force_opaque: bool) -> None:
    image = QImage(str(src))
    if image.isNull():
        raise SystemExit(f"Không đọc được ảnh: {src}")
    image = image.convertToFormat(QImage.Format.Format_ARGB32)
    if (image.width(), image.height()) != (width, height):
        image = image.scaled(
            width, height,
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )

    pixels = bytearray()
    mask_bits = bytearray((width * height + 7) // 8)
    opaque = 1
    for y in range(height):
        for x in range(width):
            value = image.pixel(x, y)
            a = (value >> 24) & 0xFF
            r = (value >> 16) & 0xFF
            g = (value >> 8) & 0xFF
            b = value & 0xFF
            if force_opaque or a >= ALPHA_THRESHOLD:
                pixels += rgb565(r, g, b).to_bytes(2, "little")
                o = y * width + x
                mask_bits[o >> 3] |= 0x80 >> (o & 7)
            else:
                pixels += (0).to_bytes(2, "little")
                opaque = 0
    if force_opaque:
        opaque = 1

    header = bytearray()
    header += width.to_bytes(2, "little")
    header += height.to_bytes(2, "little")
    header.append(opaque)
    header.append(0)
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(bytes(header) + bytes(pixels) + bytes(mask_bits))
    print(f"{src.name} -> {dst}  {width}x{height} opaque={opaque} ({dst.stat().st_size} bytes)")


def main() -> None:
    args = [a for a in sys.argv[1:]]
    force_opaque = "--opaque" in args
    args = [a for a in args if a != "--opaque"]
    if len(args) != 4:
        raise SystemExit(__doc__)
    convert(Path(args[0]), Path(args[1]), int(args[2]), int(args[3]), force_opaque)


if __name__ == "__main__":
    main()
