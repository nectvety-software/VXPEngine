"""Tích hợp ffmpeg bundled tại <repo>/libs/ffmpeg.exe.

Dùng để tách khung hình video thành ảnh PNG nhập vào tài nguyên project
(Tools → "Tách khung hình video (ffmpeg)…"). Không sửa đổi video gốc.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

ENGINE_ROOT = Path(__file__).resolve().parent.parent


def ffmpeg_path() -> Path | None:
    bundled = ENGINE_ROOT / "libs" / "ffmpeg.exe"
    if bundled.is_file():
        return bundled
    found = shutil.which("ffmpeg")
    return Path(found) if found else None


def extract_frames(
    video: Path,
    out_dir: Path,
    *,
    fps: float = 2.0,
    max_frames: int = 120,
    scale_width: int | None = None,
) -> list[Path]:
    """Tách khung hình video thành PNG (ffmpeg -vf fps=...).

    Trả về danh sách tệp đã sinh; ném RuntimeError khi ffmpeg thiếu hoặc lỗi.
    """
    exe = ffmpeg_path()
    if exe is None:
        raise RuntimeError("Không tìm thấy ffmpeg (đặt ffmpeg.exe vào libs/).")
    out_dir.mkdir(parents=True, exist_ok=True)
    vf = f"fps={fps}"
    if scale_width:
        vf += f",scale={scale_width}:-1"
    pattern = out_dir / "frame_%03d.png"
    cmd = [
        str(exe), "-y", "-i", str(video),
        "-vf", vf, "-frames:v", str(max_frames), str(pattern),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if proc.returncode != 0:
        tail = (proc.stderr or "").strip().splitlines()[-3:]
        raise RuntimeError("ffmpeg báo lỗi: " + " | ".join(tail))
    return sorted(out_dir.glob("frame_*.png"))
