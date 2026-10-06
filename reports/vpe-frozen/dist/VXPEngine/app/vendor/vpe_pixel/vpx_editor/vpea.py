"""VPEA1 animation container: N VPE565 frames + timing, one file.

Binary layout (little-endian):

    Offset  Size  Field
    0       6     Magic  b"VPEA01"
    6       2     Version u16 = 1
    8       2     Width  u16
    10      2     Height u16
    12      2     Frame count u16      (1 .. 256)
    14      2     Delay u16 (ms/frame)
    16      1     Loop u8 (0 or 1)
    17      3     Reserved, zero
    20      N     Frame count VPE565 blobs, each exactly 16 + w*h*2 bytes

Every frame is a complete, self-describing .vpe payload, so a frame can be cut
out of the container and opened by any VPE565 decoder unchanged.
"""

from __future__ import annotations

import struct
from pathlib import Path
from typing import List, Sequence, Tuple

from .vpe import MAX_DIM, VpeError, decode_vpe, encode_vpe

MAGIC = b"VPEA01"
VERSION = 1
HEADER_SIZE = 20
MAX_FRAMES = 256
MIN_DELAY_MS = 10
MAX_DELAY_MS = 60_000


def encode_vpea(width: int, height: int, frames: Sequence[Sequence[int]],
                delay_ms: int = 120, loop: bool = True) -> bytes:
    if width < 1 or height < 1:
        raise VpeError("vpea-size")
    if width > MAX_DIM or height > MAX_DIM:
        raise VpeError("image-too-large")
    n = len(frames)
    if n < 1 or n > MAX_FRAMES:
        raise VpeError("vpea-frames")
    delay = min(max(int(delay_ms), MIN_DELAY_MS), MAX_DELAY_MS)
    blobs = [encode_vpe(width, height, px) for px in frames]
    header = MAGIC + struct.pack("<HHHHH", VERSION, width, height, n, delay)
    header += bytes((1 if loop else 0,)) + b"\x00" * 3
    return header + b"".join(blobs)


def decode_vpea(blob: bytes) -> Tuple[int, int, List[List[int]], int, bool]:
    """Return (width, height, frames, delay_ms, loop)."""
    if not isinstance(blob, (bytes, bytearray)):
        raise VpeError("vpea-truncated")
    if len(blob) < HEADER_SIZE:
        raise VpeError("vpea-truncated")
    if bytes(blob[:8]) != MAGIC + struct.pack("<H", VERSION):
        raise VpeError("vpea-magic")
    _version, width, height, count, delay = struct.unpack_from("<HHHHH", blob, 6)
    if width < 1 or height < 1 or count < 1:
        raise VpeError("vpea-size")
    if width > MAX_DIM or height > MAX_DIM:
        raise VpeError("image-too-large")
    if count > MAX_FRAMES:
        raise VpeError("vpea-frames")
    frame_size = 16 + width * height * 2
    if len(blob) != HEADER_SIZE + frame_size * count:
        raise VpeError("vpea-payload-size")
    frames: List[List[int]] = []
    for i in range(count):
        start = HEADER_SIZE + i * frame_size
        w, h, pixels = decode_vpe(bytes(blob[start:start + frame_size]))
        if (w, h) != (width, height):
            raise VpeError("vpea-frame-dims")
        frames.append(pixels)
    return width, height, frames, delay, bool(blob[16] & 1)


def save_vpea(path: str | Path, width: int, height: int,
              frames: Sequence[Sequence[int]], delay_ms: int = 120,
              loop: bool = True) -> None:
    Path(path).write_bytes(encode_vpea(width, height, frames, delay_ms, loop))


def load_vpea(path: str | Path) -> Tuple[int, int, List[List[int]], int, bool]:
    return decode_vpea(Path(path).read_bytes())


def header_of(path: str | Path) -> Tuple[int, int, int, int, bool]:
    """(width, height, frames, delay_ms, loop) from the 20-byte header only."""
    with Path(path).open("rb") as handle:
        data = handle.read(HEADER_SIZE)
    if len(data) < HEADER_SIZE or bytes(data[:8]) != MAGIC + struct.pack("<H", VERSION):
        raise VpeError("vpea-magic")
    _v, width, height, count, delay = struct.unpack_from("<HHHHH", data, 6)
    return width, height, count, delay, bool(data[16] & 1)


def frame_count_of(path: str | Path) -> int:
    """Frame count straight from the header, without decoding the payload."""
    return header_of(path)[2]


def load_frame(path: str | Path, index: int = 0) -> Tuple[int, int, List[int]]:
    """One frame as (width, height, pixels) without decoding the others."""
    data = Path(path).read_bytes()
    if len(data) < HEADER_SIZE or bytes(data[:8]) != MAGIC + struct.pack("<H", VERSION):
        raise VpeError("vpea-magic")
    _v, width, height, count, _delay = struct.unpack_from("<HHHHH", data, 6)
    frame_size = 16 + width * height * 2
    index = int(index)
    if not 0 <= index < count or len(data) < HEADER_SIZE + frame_size * (index + 1):
        raise VpeError("vpea-payload-size")
    start = HEADER_SIZE + index * frame_size
    return decode_vpe(bytes(data[start:start + frame_size]))


def save_png_strip(path: str | Path, width: int, height: int,
                   frames: Sequence[Sequence[int]]) -> None:
    """Write every frame side by side into one PNG, white keyed transparent.

    Sprite-sheet layout: pixel (x, y) of frame i lands at (i*width + x, y).
    """
    try:
        from PySide6.QtGui import QImage, QColor
    except ImportError as exc:
        raise VpeError("qt-unavailable") from exc
    from .vpe import c565_to_rgb

    if not frames:
        raise VpeError("vpea-frames")
    img = QImage(width * len(frames), height, QImage.Format_ARGB32)
    img.fill(0x00000000)
    for i, pixels in enumerate(frames):
        if len(pixels) != width * height:
            raise VpeError("pixel-count")
        for y in range(height):
            base = y * width
            for x in range(width):
                px = pixels[base + x]
                if px == 0xFFFF:
                    continue
                r, g, b = c565_to_rgb(px)
                img.setPixelColor(i * width + x, y, QColor(r, g, b))
    if not img.save(str(path), "PNG"):
        raise VpeError("png-save-failed")
