"""Đóng gói thư viện mẫu của VXPEngine (assets/) thành gói nén.

Chạy:  .venv\\Scripts\\python.exe tools\\pack_sample_library.py
Tạo:   packaging/vxp_sample_assets.zip  (sprite PNG + atlas.json + SFX mp3)

TitleSet / Component Library trong IDE nạp mẫu từ gói nén này (giải nén vào
cache người dùng), còn Library Import vẫn quét thẳng thư mục assets/.
"""
from __future__ import annotations

import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
OUT = ROOT / "packaging" / "vxp_sample_assets.zip"


def pack() -> Path:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(ASSETS.rglob("*")):
            if not path.is_file():
                continue
            if path.suffix.lower() not in {".png", ".mp3", ".json"}:
                continue
            zf.write(path, path.relative_to(ASSETS).as_posix())
            count += 1
    print(f"Packed {count} files -> {OUT} ({OUT.stat().st_size / 1024 / 1024:.1f} MB)")
    return OUT


if __name__ == "__main__":
    pack()
