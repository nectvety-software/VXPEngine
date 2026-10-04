"""Di trú core cũ (``vxpstore`` / ``corevxp``) sang ``coremre`` cho project tạo trước khi gộp core.

Hai core cũ từng là bản sao của nhau nên đã được gộp thành một thư mục duy nhất
``engine/coremre``. Project tạo ra *trước* thay đổi này vẫn mang ``engine/vxpstore``
(hoặc ``engine/corevxp``) và sẽ hỏng ngay khi configure CMake, vì ``template/``
không còn bản sao nào để copy bù vào.

Module này chạy khi mở project: đổi tên core cũ thành ``engine/coremre`` rồi quét
lại các tệp tham chiếu (CMakeLists, scripts, docs) để trỏ về tên mới.
"""
from __future__ import annotations

import os
from pathlib import Path

CORE_NAME = "coremre"

# Thứ tự ưu tiên: `vxpstore` là bản được template dùng trước đây.
LEGACY_CORE_NAMES = ("vxpstore", "corevxp")

_TEXT_SUFFIXES = {
    ".txt", ".cmake", ".c", ".h", ".cpp", ".hpp", ".cc", ".hh",
    ".sh", ".bat", ".cmd", ".md", ".json", ".py", ".ps1",
    ".ld", ".def", ".mk", ".yml", ".yaml", ".ini", ".cfg",
}

_SKIP_DIRS = {
    ".git", ".venv", "__pycache__", "node_modules", ".cache",
    "build-win32", "build-arm", "build-arm-signed", "build", "out",
}

_MAX_FILE_BYTES = 4 * 1024 * 1024


def legacy_core_dirs(root: str | Path) -> list[Path]:
    """Các thư mục core cũ còn sót lại trong ``<root>/engine``."""
    engine = Path(root) / "engine"
    return [engine / name for name in LEGACY_CORE_NAMES if (engine / name).is_dir()]


def needs_migration(root: str | Path) -> bool:
    """Kiểm tra rẻ (vài lệnh stat) — True khi project vẫn dùng core cũ."""
    engine = Path(root) / "engine"
    if not engine.is_dir():
        return False
    if (engine / CORE_NAME).is_dir():
        return False
    return bool(legacy_core_dirs(root))


def _dir_signature(path: Path) -> frozenset[tuple[str, int]]:
    """Chữ ký nội dung (đường dẫn tương đối + kích thước) để so sánh hai core.

    Bỏ qua ``CMakeLists.txt``: hai core cũ ``vxpstore``/``corevxp`` là bản sao của
    nhau, điểm khác biệt duy nhất là tên target bên trong CMakeLists — khác biệt đó
    là hệ quả của tên thư mục chứ không phải nội dung core.
    """
    entries: set[tuple[str, int]] = set()
    for dirpath, dirnames, filenames in os.walk(path):
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]
        base = Path(dirpath)
        for filename in filenames:
            if filename == "CMakeLists.txt":
                continue
            try:
                size = (base / filename).stat().st_size
            except OSError:
                size = -1
            entries.add(((base / filename).relative_to(path).as_posix(), size))
    return frozenset(entries)


def _iter_text_files(root: Path, exclude: set[Path] | None = None):
    """Duyệt tệp văn bản; ``exclude`` chứa các thư mục bị bỏ qua (cả cây con)."""
    skip = {os.path.normcase(os.path.abspath(p)) for p in (exclude or set())}
    for dirpath, dirnames, filenames in os.walk(root):
        # Cắt cả cây con bị loại (bản core thừa) chứ không chỉ tên thư mục.
        dirnames[:] = [
            d for d in dirnames
            if d not in _SKIP_DIRS
            and os.path.normcase(os.path.abspath(Path(dirpath) / d)) not in skip
        ]
        for filename in filenames:
            path = Path(dirpath) / filename
            if path.suffix.lower() not in _TEXT_SUFFIXES:
                continue
            try:
                if path.stat().st_size > _MAX_FILE_BYTES:
                    continue
            except OSError:
                continue
            yield path


def _rewrite_references(root: Path, exclude: set[Path] | None = None) -> int:
    """Thay mọi tham chiếu ``vxpstore``/``corevxp`` bằng ``coremre`` trong tệp văn bản.

    Chỉ thay dạng viết thường — tên nhà phát triển mặc định là ``VXPstore``
    (viết hoa chữ V) nên không bị ảnh hưởng.
    """
    changed = 0
    for path in _iter_text_files(root, exclude):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        updated = text
        for legacy in LEGACY_CORE_NAMES:
            updated = updated.replace(legacy, CORE_NAME)
        if updated == text:
            continue
        try:
            path.write_text(updated, encoding="utf-8")
            changed += 1
        except OSError:
            continue
    return changed


def migrate_core_layout(root: str | Path) -> list[str]:
    """Đưa project về layout một core duy nhất. Trả về danh sách thông báo (có thể rỗng).

    Không bao giờ xóa dữ liệu: core cũ được *đổi tên*, bản thừa (nếu có) được giữ lại.
    """
    root = Path(root)
    engine = root / "engine"
    target = engine / CORE_NAME
    notices: list[str] = []

    if not engine.is_dir():
        return notices

    legacy = legacy_core_dirs(root)

    if target.is_dir():
        if legacy:
            names = ", ".join(f"engine/{p.name}" for p in legacy)
            notices.append(
                f"[Core] Project đã có engine/{CORE_NAME} nên bỏ qua di trú. "
                f"Thư mục cũ không còn dùng, bạn có thể xóa thủ công: {names}."
            )
        return notices

    if not legacy:
        # Layout lạ (không có core nào trong engine/) — không đoán, để nguyên.
        return notices

    chosen = legacy[0]
    leftover: list[Path] = []

    if len(legacy) > 1:
        if _dir_signature(legacy[0]) != _dir_signature(legacy[1]):
            names = ", ".join(f"engine/{p.name}" for p in legacy)
            notices.append(
                f"[Core] Không thể tự gộp vì {names} khác nhau. "
                f"Hãy chọn một bản, đổi tên thành engine/{CORE_NAME} rồi mở lại project."
            )
            return notices
        chosen = next((p for p in legacy if p.name == LEGACY_CORE_NAMES[0]), legacy[0])
        leftover = [p for p in legacy if p is not chosen]
        notices.append(
            f"[Core] Hai core cũ là bản sao của nhau (chỉ khác tên target trong CMakeLists); "
            f"đã lấy engine/{chosen.name} làm engine/{CORE_NAME}. "
            f"Bản thừa engine/{leftover[0].name} được giữ lại (không tự xóa), bạn có thể xóa thủ công."
        )

    try:
        chosen.rename(target)
    except OSError as error:
        notices.append(
            f"[Core] Không thể đổi tên engine/{chosen.name} → engine/{CORE_NAME}: {error}"
        )
        return notices

    notices.append(
        f"[Core] Đã di trú engine/{chosen.name} → engine/{CORE_NAME} "
        f"(hai core cũ được gộp thành một)."
    )

    exclude = {p for p in leftover}
    changed = _rewrite_references(root, exclude)
    if changed:
        notices.append(
            f"[Core] Đã cập nhật {changed} tệp tham chiếu core cũ (CMakeLists, scripts, docs)."
        )
    return notices
