"""Render khung 240x320 cho giả lập đúng từng pixel như thiết bị vẽ.

Mô phỏng 1:1 các hàm trong ``template_blank/src/main.c``:

* ``backdrop()`` — nền gradient xanh theo dòng y;
* ``draw_design()`` — đi qua bảng ``VXP_DESIGN_ACTIVE_COMPONENTS`` (đã sắp
  theo z_index ở ``scene_screen_store.generate_c_bindings``): blit sprite
  ``.raw`` trong ``resources/gen/`` với tâm tại ``(int(x+sw/2), int(y+sh/2))``;
  khi thiếu sprite thì tô màu theo loại component + viền sáng, đúng như
  nhánh fallback trên thiết bị;
* ``draw_default()`` — khung màn hình + thanh chạy theo tick khi màn thiết
  kế trống (HAS_DESIGN=0).

Kết quả là QImage RGB565 (Format_RGB16) — cùng định dạng framebuffer của
máy, nên đồ họa giả lập giống 100% với bản build .vxp và ứng dụng đã ký.
"""
from __future__ import annotations

import struct
from pathlib import Path

from PySide6.QtGui import QImage

SCREEN_W = 240
SCREEN_H = 320


def _rgb565(r: int, g: int, b: int) -> int:
    return (((r) & 0xF8) << 8) | (((g) & 0xFC) << 3) | ((b) >> 3)


def _design_type_color(type_name: str) -> int:
    if "Text" in type_name:
        return _rgb565(255, 214, 102)
    if "Circle" in type_name:
        return _rgb565(122, 198, 255)
    if "Rectangle" in type_name:
        return _rgb565(150, 168, 200)
    return _rgb565(96, 200, 140)


def _fill(fb: bytearray, sw: int, sh: int, x: int, y: int, w: int, h: int, color: int) -> None:
    x0 = x if x > 0 else 0
    y0 = y if y > 0 else 0
    x1 = x + w if x + w < sw else sw
    y1 = y + h if y + h < sh else sh
    if x0 >= x1 or y0 >= y1:
        return
    row = struct.pack("<H", color) * (x1 - x0)
    span = (x1 - x0) * 2
    for j in range(y0, y1):
        offset = (j * sw + x0) * 2
        fb[offset:offset + span] = row


def _frame(fb: bytearray, sw: int, sh: int, x: int, y: int, w: int, h: int, color: int) -> None:
    _fill(fb, sw, sh, x, y, w, 1, color)
    _fill(fb, sw, sh, x, y + h - 1, w, 1, color)
    _fill(fb, sw, sh, x, y, 1, h, color)
    _fill(fb, sw, sh, x + w - 1, y, 1, h, color)


def _backdrop(fb: bytearray, sw: int, sh: int) -> None:
    for y in range(sh):
        color = _rgb565(10 + (y >> 4), 18 + (y >> 3), 32 + (y >> 3))
        row = struct.pack("<H", color) * sw
        offset = y * sw * 2
        fb[offset:offset + sw * 2] = row


def _blit_raw(fb: bytearray, sw: int, sh: int, data: bytes, cx: int, cy: int) -> None:
    """Blit sprite .raw (header 8 byte + RGB565 + mask 1-bit) với tâm (cx, cy)."""
    if len(data) <= 8:
        return
    w = data[0] | (data[1] << 8)
    h = data[2] | (data[3] << 8)
    opaque = data[4]
    pixel_end = 8 + w * h * 2
    if w <= 0 or h <= 0 or len(data) < pixel_end:
        return
    pixels = data[8:pixel_end]
    mask = data[pixel_end:]
    x0 = cx - w // 2
    y0 = cy - h // 2
    i_start = max(0, -x0)
    i_end = min(w, sw - x0)
    if i_start >= i_end:
        return
    span = (i_end - i_start) * 2
    j_start = max(0, -y0)
    j_end = min(h, sh - y0)
    for j in range(j_start, j_end):
        dy = y0 + j
        row_offset = dy * sw * 2
        if opaque:
            src = (j * w + i_start) * 2
            dst = row_offset + (x0 + i_start) * 2
            fb[dst:dst + span] = pixels[src:src + span]
            continue
        base = j * w
        for i in range(i_start, i_end):
            order = base + i
            if mask[order >> 3] & (0x80 >> (order & 7)):
                dst = row_offset + (x0 + i) * 2
                src = order * 2
                fb[dst:dst + 2] = pixels[src:src + 2]


def _to_image(fb: bytearray, sw: int, sh: int) -> QImage:
    image = QImage(bytes(fb), sw, sh, QImage.Format.Format_RGB16)
    return image.copy()


def active_design_rows(project_root: Path) -> list[dict]:
    """Bảng component của màn hoạt động — đúng thứ tự bảng C (theo z_index)."""
    from scene_screen_store import ScreenStore

    store = ScreenStore(project_root)
    registry = store.ensure()
    active_id = str(registry.get("active_screen") or "main")
    store.generate_c_bindings()
    rows = [row for row in store.last_component_rows if row.get("screen_id") == active_id]
    rows.sort(key=lambda item: item.get("z_index", 0))
    return rows


def render_design_frame(project_root: Path, rows: list[dict]) -> QImage | None:
    """Vẽ màn thiết kế như ``draw_design`` của máy; None khi màn trống."""
    sw, sh = SCREEN_W, SCREEN_H
    fb = bytearray(sw * sh * 2)
    _backdrop(fb, sw, sh)
    gen_dir = Path(project_root) / "resources" / "gen"
    for row in rows:
        if not row.get("visible", 1):
            continue
        cx = int(float(row.get("x", 0)) + sw / 2)
        cy = int(float(row.get("y", 0)) + sh / 2)
        width = int(float(row.get("width", 0)))
        height = int(float(row.get("height", 0)))
        res_name = str(row.get("res", ""))
        sprite = None
        if res_name:
            sprite_path = gen_dir / res_name
            try:
                if sprite_path.exists() and sprite_path.stat().st_size > 8:
                    sprite = sprite_path.read_bytes()
            except OSError:
                sprite = None
        if sprite is not None:
            _blit_raw(fb, sw, sh, sprite, cx, cy)
        elif width > 0 and height > 0:
            color = _design_type_color(str(row.get("type", "")))
            _fill(fb, sw, sh, cx - width // 2, cy - height // 2, width, height, color)
            _frame(fb, sw, sh, cx - width // 2, cy - height // 2, width, height, _rgb565(230, 238, 250))
    return _to_image(fb, sw, sh)


def render_default_frame(tick: int) -> QImage:
    """Vẽ ``draw_default`` — màn hình mặc định khi không có thiết kế."""
    sw, sh = SCREEN_W, SCREEN_H
    fb = bytearray(sw * sh * 2)
    _backdrop(fb, sw, sh)
    border = _rgb565(120, 160, 220)
    inner = _rgb565(8, 12, 20)
    for y in range(40, 120):
        row_offset = y * sw * 2
        for x in range(20, sw - 20):
            edge = x <= 21 or x >= sw - 22 or y <= 41 or y >= 118
            color = border if edge else inner
            offset = row_offset + x * 2
            fb[offset:offset + 2] = struct.pack("<H", color)
    bar = (tick * 2) % (sw + 40) - 20
    gold = struct.pack("<H", _rgb565(255, 200, 60))
    for y in range(150, 162):
        row_offset = y * sw * 2
        for x in range(bar, bar + 24):
            if 4 <= x < sw - 4:
                offset = row_offset + x * 2
                fb[offset:offset + 2] = gold
    return _to_image(fb, sw, sh)
