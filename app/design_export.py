"""Xuất component của màn thiết kế Camera 2D thành sprite .raw cho build.

Mỗi component có ảnh (asset) được raster hóa đúng kích thước hiển thị,
xoay theo góc thiết kế rồi ghi thành .raw RGB565 (header 8 byte + pixel +
mask alpha 1-bit) vào resources/gen/ — cùng định dạng sprite của coremre.
Nhờ vậy bản build vẽ đúng đồ họa đang thấy trong Camera 2D / giả lập.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPainter

MANIFEST_NAME = ".design_export.json"

# main.c trống của bản template cũ — không nạp scene_bindings.h nên thiết bị
# chỉ vẽ màn mặc định, trong khi giả lập vẽ bảng thiết kế.
LEGACY_BLANK_MARKER = "MRE VXP TRỐNG do VXPEngine sinh ra"


def refresh_legacy_main_c(project_root: Path) -> bool:
    """Thay main.c trống bản cũ bằng bản vẽ theo bảng thiết kế của template.

    Chỉ thay khi tệp đúng là boilerplate trống cũ nguyên vẹn (có marker và
    không include scene_bindings.h) — code người dùng tự viết giữ nguyên.
    Trả về True nếu đã thay.
    """
    project_root = Path(project_root)
    target = project_root / "src" / "main.c"
    template = Path(__file__).resolve().parent.parent / "template_blank" / "src" / "main.c"
    try:
        if not target.is_file() or not template.is_file():
            return False
        current = target.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    if LEGACY_BLANK_MARKER not in current or "scene_bindings.h" in current:
        return False
    try:
        target.write_text(template.read_text(encoding="utf-8"), encoding="utf-8")
    except OSError:
        return False
    return True


def _read_manifest(gen_dir: Path) -> list[str]:
    manifest = gen_dir / MANIFEST_NAME
    if not manifest.exists():
        return []
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
        return [str(name) for name in data] if isinstance(data, list) else []
    except (OSError, ValueError, TypeError):
        return []


def _write_raw(image: QImage, dest: Path) -> None:
    """Ghi ảnh ARGB32 thành sprite .raw: header 8 byte + RGB565 + mask 1-bit."""
    argb = image.convertToFormat(QImage.Format.Format_ARGB32)
    width, height = argb.width(), argb.height()
    alpha_has_transparency = False
    fully_opaque = True
    mask_bits = bytearray((width * height + 7) // 8)
    for y in range(height):
        for x in range(width):
            alpha = (argb.pixel(x, y) >> 24) & 0xFF
            order = y * width + x
            if alpha >= 128:
                mask_bits[order >> 3] |= 0x80 >> (order & 7)
                if alpha < 255:
                    fully_opaque = False
            else:
                alpha_has_transparency = True
    rgb16 = argb.convertToFormat(QImage.Format.Format_RGB16)
    pixels = bytearray()
    bits = rgb16.constBits()
    bytes_per_line = rgb16.bytesPerLine()
    for y in range(height):
        row_start = y * bytes_per_line
        for x in range(width):
            offset = row_start + x * 2
            pixels.append(bits[offset])
            pixels.append(bits[offset + 1])
    header = bytes([width & 0xFF, (width >> 8) & 0xFF, height & 0xFF, (height >> 8) & 0xFF,
                    1 if fully_opaque and not alpha_has_transparency else 0, 0, 0, 0])
    dest.write_bytes(header + bytes(pixels) + bytes(mask_bits))


def _rasterize(source: QImage, width: float, height: float, rotation: float, mode: str = "Stretch") -> QImage:
    target_w = max(1, int(round(width)))
    target_h = max(1, int(round(height)))
    mode_key = str(mode or "Stretch").strip().lower()
    prepared = QImage(target_w, target_h, QImage.Format.Format_ARGB32)
    prepared.fill(Qt.GlobalColor.transparent)
    painter = QPainter(prepared)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
    if mode_key == "tile":
        for y in range(0, target_h, max(1, source.height())):
            for x in range(0, target_w, max(1, source.width())):
                painter.drawImage(x, y, source)
    else:
        aspect = {
            "fit": Qt.AspectRatioMode.KeepAspectRatio,
            "stretch": Qt.AspectRatioMode.IgnoreAspectRatio,
        }.get(mode_key, Qt.AspectRatioMode.KeepAspectRatioByExpanding)
        scaled = source.scaled(target_w, target_h, aspect, Qt.TransformationMode.FastTransformation)
        painter.drawImage((target_w - scaled.width()) // 2, (target_h - scaled.height()) // 2, scaled)
    painter.end()
    angle = round(float(rotation) % 360, 3)
    if angle in (0.0, 360.0):
        return prepared
    diagonal = int(math.ceil(math.hypot(target_w, target_h))) + 2
    canvas = QImage(diagonal, diagonal, QImage.Format.Format_ARGB32)
    canvas.fill(Qt.GlobalColor.transparent)
    painter = QPainter(canvas)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
    painter.translate(diagonal / 2, diagonal / 2)
    painter.rotate(angle)
    painter.drawImage(-target_w / 2, -target_h / 2, prepared)
    painter.end()
    return canvas


def export_design_sprites(project_root: Path) -> int:
    """Rasterize mọi component có ảnh của các màn thiết kế vào resources/gen/.

    Trả về số sprite đã xuất. Chạy trước mỗi lần build để .vxp chứa đúng
    đồ họa của màn thiết kế Camera 2D.
    """
    from scene_screen_store import ScreenStore

    project_root = Path(project_root)
    store = ScreenStore(project_root)
    store.generate_c_bindings()
    rows = getattr(store, "last_component_rows", [])

    gen_dir = project_root / "resources" / "gen"
    gen_dir.mkdir(parents=True, exist_ok=True)

    exported_names: list[str] = []
    exported = 0
    seen: set[str] = set()
    for row in rows:
        res_name = str(row.get("res", ""))
        asset_rel = str(row.get("asset", "")).replace('\\"', '"')
        if not res_name or not asset_rel or res_name in seen:
            continue
        seen.add(res_name)
        source_path = project_root / asset_rel.replace("\\", "/")
        if not source_path.exists():
            continue
        image = QImage(str(source_path))
        if image.isNull():
            continue
        width = float(row.get("width") or 0)
        height = float(row.get("height") or 0)
        scale_x = float(row.get("scale_x") or 1)
        scale_y = float(row.get("scale_y") or scale_x)
        if width <= 0:
            width = image.width() * scale_x
        if height <= 0:
            height = image.height() * scale_y
        sprite = _rasterize(
            image,
            width,
            height,
            float(row.get("rotation") or 0),
            str(row.get("background_bitmap_mode") or "Stretch") if row.get("background_bitmap") else "Stretch",
        )
        _write_raw(sprite, gen_dir / res_name)
        exported_names.append(res_name)
        exported += 1

    # Dọn sprite design cũ không còn trong thiết kế (chỉ file do chính lần
    # xuất trước tạo ra — không đụng sprite .raw người dùng tự thêm).
    for stale in _read_manifest(gen_dir):
        if stale not in exported_names:
            stale_path = gen_dir / stale
            try:
                if stale_path.exists():
                    stale_path.unlink()
            except OSError:
                pass
    try:
        (gen_dir / MANIFEST_NAME).write_text(
            json.dumps(exported_names, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except OSError:
        pass
    return exported
