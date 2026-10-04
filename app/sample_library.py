"""Thư viện mẫu nén (packaging/vxp_sample_assets.zip) cho TitleSet / Component Library.

Gói nén được giải nén một lần vào cache người dùng; các panel mẫu đọc từ cache.
Khi assets/ thay đổi, chạy ``tools/pack_sample_library.py`` để đóng gói lại —
IDE tự giải nén lại khi thấy zip mới hơn cache.
"""
from __future__ import annotations

import os
import zipfile
from pathlib import Path

ENGINE_ROOT = Path(__file__).resolve().parent.parent
SAMPLE_ZIP = ENGINE_ROOT / "packaging" / "vxp_sample_assets.zip"


def cache_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA", str(Path.home()))
    return Path(base) / "VXPEngine" / "sample_library"


def _marker() -> Path:
    return cache_dir() / ".extracted_from"


def ensure_extracted() -> Path | None:
    """Giải nén gói mẫu vào cache khi cần; trả về thư mục cache (None nếu không có zip)."""
    if not SAMPLE_ZIP.is_file():
        return None
    out = cache_dir()
    marker = _marker()
    need = True
    if marker.exists():
        try:
            stamp = float(marker.read_text(encoding="utf-8").strip())
            need = stamp < SAMPLE_ZIP.stat().st_mtime
        except (OSError, ValueError):
            need = True
    if not need and out.exists():
        return out
    out.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(SAMPLE_ZIP) as zf:
        zf.extractall(out)
    marker.write_text(f"{SAMPLE_ZIP.stat().st_mtime}", encoding="utf-8")
    return out


def is_sample_path(path: str | Path) -> bool:
    """True khi đường dẫn nằm trong cache thư viện mẫu (không thuộc project)."""
    try:
        Path(path).resolve().relative_to(cache_dir().resolve())
        return True
    except (OSError, ValueError):
        return False
