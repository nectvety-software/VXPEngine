"""Per-application VXP identities backed by the integrated re3 format."""
from __future__ import annotations

import json
import os
import secrets
import re
import sys
from pathlib import Path

# App ID hợp lệ cho PackApp (-tai): 0 = bản dev, -1 = personal (khóa theo IMSI).
# Engine cấp cho mỗi project một id trong khoảng dưới đây để chạy trên máy retail.
APP_ID_MIN = 100_000
APP_ID_MAX = 9_999_999

RETAIL_CERT_ID = "100"
DEV_CERT_ID = "1"

DESCRIPTOR_NAME = "project.vxp.json"

# Tên biến môi trường mà engine truyền cho script build của project.
ENV_APP_ID = "VXP_APPID"
ENV_CERT_ID = "VXP_CERTID"
ENV_CERT_KEY = "VXP_CERT"

# Tệp khóa do engine sở hữu. Nếu xuất hiện trong project nghĩa là đã bị copy
# nhầm từ bản cũ — bị xóa khi mở project (chỉ đúng các tên này, không dùng wildcard).
ENGINE_OWNED_KEY_NAMES = {
    "cert100-key.pem",
    "cert2-key.pem",
    "private_key_0x64.pem",
}

# Thư mục chứng thư không bao giờ thuộc về project.
SIGNING_DIR_NAME = "signing"

# Thư mục sinh ra khi build — không cần quét khi dọn khóa ký.
_SCAN_SKIP_DIRS = {
    ".git", ".venv", "__pycache__", "node_modules",
    "build-win32", "build-arm", "build-arm-signed",
}


def engine_root() -> Path:
    return Path(__file__).resolve().parent.parent


def signing_dir() -> Path:
    # Bản cài đặt không phát hành bất kỳ private key nào và không ghi vào thư
    # mục chương trình. Mỗi tài khoản Windows tự sinh identity trong AppData.
    if getattr(sys, "frozen", False):
        local = Path(os.environ.get("LOCALAPPDATA") or (Path.home() / "AppData" / "Local"))
        return local / "VXPEngine" / "signing"
    return engine_root() / "signing"


def retail_key_path() -> Path:
    return signing_dir() / "cert100-key.pem"


def _read_descriptor(project_root: str | Path) -> dict:
    try:
        value = json.loads(descriptor_path(project_root).read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def read_vendor(project_root: str | Path) -> str:
    return str(_read_descriptor(project_root).get("developer") or "VXPstore").strip() or "VXPstore"


def identity_dir(project_root: str | Path) -> Path:
    app_id = read_app_id(project_root)
    vendor = read_vendor(project_root)
    slug = re.sub(r"[^A-Za-z0-9_.-]+", "_", vendor).strip("._")[:48] or "vendor"
    return signing_dir() / "apps" / f"{app_id}-{slug}"


def app_key_path(project_root: str | Path) -> Path:
    return identity_dir(project_root) / "private.pem"


def ensure_signing_identity(project_root: str | Path) -> Path:
    """Create and persist one private RSA-512 identity per App ID/Vendor pair."""
    app_id = read_app_id(project_root)
    if app_id == "0":
        raise ValueError("Project chưa có App ID riêng.")
    key_path = app_key_path(project_root)
    if key_path.is_file():
        return key_path
    tool_dir = signer_path().parent
    import sys
    if str(tool_dir) not in sys.path:
        sys.path.insert(0, str(tool_dir))
    from vxp_signer import create_key
    fingerprint = create_key(key_path)
    metadata = {
        "format": "VXPEngine VXP signing identity",
        "app_id": int(app_id),
        "vendor": read_vendor(project_root),
        "cert_id": int(RETAIL_CERT_ID),
        "algorithm": "RSA-512/SHA-1/PKCS#1-v1.5",
        "public_key_sha256": fingerprint,
        "firmware_note": "A newly generated key must be trusted by target firmware.",
    }
    (key_path.parent / "identity.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    return key_path


def signer_path() -> Path:
    return engine_root() / "engine" / "coremre" / "tools" / "vxp_signer.py"


def has_retail_key() -> bool:
    return retail_key_path().is_file()


def has_signer() -> bool:
    return signer_path().is_file()


def generate_app_id(reserved: set[str] | None = None) -> str:
    """Sinh App ID riêng, không trùng với các id đã cấp."""
    taken = {str(item) for item in (reserved or set())}
    for _ in range(64):
        candidate = str(secrets.randbelow(APP_ID_MAX - APP_ID_MIN + 1) + APP_ID_MIN)
        if candidate not in taken:
            return candidate
    # Cực kỳ khó xảy ra: quét tuần tự để bảo đảm luôn có id.
    for value in range(APP_ID_MIN, APP_ID_MAX + 1):
        if str(value) not in taken:
            return str(value)
    raise RuntimeError("Không còn App ID khả dụng.")


def validate_app_id(value: str) -> str:
    text = str(value).strip()
    if not text.isdigit():
        raise ValueError("App ID phải là số nguyên không âm.")
    number = int(text)
    if number < 0:
        raise ValueError("App ID phải là số nguyên không âm.")
    return str(number)


def descriptor_path(project_root: str | Path) -> Path:
    return Path(project_root) / DESCRIPTOR_NAME


def read_app_id(project_root: str | Path) -> str:
    """Đọc App ID từ descriptor của project; 0 nghĩa là bản dev chưa cấp id."""
    try:
        data = json.loads(descriptor_path(project_root).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return "0"
    if not isinstance(data, dict):
        return "0"
    app_id = data.get("app_id")
    if app_id is None:
        mre = data.get("mre")
        if isinstance(mre, dict):
            app_id = mre.get("app_id")
    try:
        return validate_app_id(app_id) if app_id is not None else "0"
    except ValueError:
        return "0"


def write_app_id(project_root: str | Path, app_id: str) -> str:
    """Ghi App ID vào descriptor, giữ nguyên mọi trường khác. Trả về id đã ghi."""
    value = validate_app_id(app_id)
    path = descriptor_path(project_root)
    data: dict = {}
    if path.exists():
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                data = loaded
        except (OSError, ValueError):
            data = {}
    data["app_id"] = value
    mre = data.get("mre")
    if isinstance(mre, dict):
        mre.pop("appid", None)
        mre["app_id"] = value
    # Dọn key legacy để không còn hai nguồn sự thật.
    data.pop("appid", None)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return value


def ensure_app_id(project_root: str | Path, reserved: set[str] | None = None) -> str:
    """Trả về App ID của project; cấp mới nếu project chưa có."""
    current = read_app_id(project_root)
    if current != "0":
        return current
    return write_app_id(project_root, generate_app_id(reserved))


def signing_parameters(project_root: str | Path) -> dict[str, str]:
    """Return the stable per-application identity used by the post-build signer."""
    key = ensure_signing_identity(project_root)
    app_id = read_app_id(project_root)
    if app_id == "0":
        raise ValueError(
            "Project chưa có App ID riêng. Mở lại project bằng VXPEngine để engine cấp App ID."
        )
    return {"APPID": app_id, "CERTID": RETAIL_CERT_ID, "CERT": key.as_posix()}


def cmake_defines(project_root: str | Path) -> list[str]:
    """Các tham số -D truyền thẳng cho CMake."""
    params = signing_parameters(project_root)
    return [f"-D{name}={value}" for name, value in params.items()]


def signer_arguments(source: str | Path, output: str | Path, project_root: str | Path) -> list[str]:
    """Arguments for the bundled re3-compatible post-build signer."""
    params = signing_parameters(project_root)
    tool = signer_path()
    if not tool.is_file():
        raise FileNotFoundError(f"Thiếu backend ký VXP: {tool}")
    return [
        str(tool), str(Path(source)), str(Path(output)), params["CERT"],
        "--appid", params["APPID"], "--certid", params["CERTID"],
        "--vendor", read_vendor(project_root),
    ]


def build_environment(project_root: str | Path) -> dict[str, str]:
    """Biến môi trường mà script build của project đọc để ký.

    Khóa ký không bao giờ nằm trong project, nên script chỉ nhận đường dẫn tới
    khóa của engine thông qua môi trường, không tự tìm trong thư mục dự án.
    """
    params = signing_parameters(project_root)
    return {
        ENV_APP_ID: params["APPID"],
        ENV_CERT_ID: params["CERTID"],
        ENV_CERT_KEY: params["CERT"],
    }


def _scan_leaked_keys(root: Path, skip_dirs: set[str]) -> list[Path]:
    """Quét project tìm đúng tên tệp khóa do engine sở hữu."""
    found: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in skip_dirs]
        for filename in filenames:
            if filename in ENGINE_OWNED_KEY_NAMES:
                found.append(Path(dirpath) / filename)
    return found


def leaked_signing_artifacts(project_root: str | Path) -> list[Path]:
    """Tìm khóa/thư mục chứng thư bị copy nhầm vào project.

    Thư mục ``signing/`` chỉ bị liệt kê khi rỗng hoặc **chỉ** chứa khóa của
    engine — nếu trong đó có tệp lạ, nó được bỏ qua hoàn toàn để không đụng
    vào tài sản của người dùng.
    """
    root = Path(project_root)
    if not root.is_dir():
        return []
    found = _scan_leaked_keys(root, _SCAN_SKIP_DIRS | {SIGNING_DIR_NAME})

    stray_dir = root / SIGNING_DIR_NAME
    if stray_dir.is_dir():
        try:
            files = [p for p in stray_dir.rglob("*") if p.is_file()]
        except OSError:
            files = []
        owned = [p for p in files if p.name in ENGINE_OWNED_KEY_NAMES]
        found.extend(owned)
        if not files or len(owned) == len(files):
            found.append(stray_dir)
    return sorted(set(found))


def purge_signing_artifacts(project_root: str | Path) -> list[str]:
    """Xóa khóa/thư mục chứng thư lọt vào project. Trả về danh sách đã xóa.

    Chỉ động tới đúng các tệp do engine sở hữu và thư mục ``signing/`` không còn
    gì khác bên trong — tuyệt đối không dùng wildcard xóa bừa.
    """
    root = Path(project_root)
    removed: list[str] = []
    for path in leaked_signing_artifacts(root):
        try:
            if path.is_dir():
                continue  # xóa sau, khi đã rỗng
            path.unlink()
        except OSError:
            continue
        removed.append(path.relative_to(root).as_posix())

    stray_dir = root / SIGNING_DIR_NAME
    if stray_dir.is_dir():
        try:
            if not any(stray_dir.iterdir()):
                stray_dir.rmdir()
                removed.append(SIGNING_DIR_NAME)
        except OSError:
            pass
    return removed


def describe(project_root: str | Path) -> str:
    """Dòng mô tả ngắn dùng cho log/console."""
    try:
        params = signing_parameters(project_root)
    except (FileNotFoundError, ValueError) as error:
        return f"Ký: không sẵn sàng ({error})"
    return (f"Ký re3: khóa riêng RSA-512 · App ID {params['APPID']} · "
            f"Vendor {read_vendor(project_root)} · certid {params['CERTID']}")
