"""Thẩm tra gói core coremre: chữ ký RSA + toàn vẹn SHA-256 từng tệp.

Dùng:  python tools/verify_core.py [đường dẫn gói]
Mặc định chọn phiên bản mới nhất trong packaging/coremre/.
Exit 0 khi hợp lệ; khác 0 khi sai chữ ký / hỏng tệp.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

ROOT = Path(__file__).resolve().parent.parent


def latest_package_dir() -> Path | None:
    base = ROOT / "packaging" / "coremre"
    if not base.is_dir():
        return None
    versions = sorted([p for p in base.iterdir() if p.is_dir()])
    return versions[-1] if versions else None


def verify(package_dir: Path) -> tuple[bool, str]:
    manifest_path = package_dir / "manifest.json"
    sig_path = package_dir / "manifest.sig"
    pub_path = package_dir / "coremre-sign-pub.pem"
    for required in (manifest_path, sig_path, pub_path):
        if not required.is_file():
            return False, f"Thiếu {required.name} trong gói core."
    try:
        public_key = serialization.load_pem_public_key(pub_path.read_bytes())
        public_key.verify(
            sig_path.read_bytes(),
            manifest_path.read_bytes(),
            padding.PKCS1v15(),
            hashes.SHA256(),
        )
    except (ValueError, TypeError, InvalidSignature) as error:
        detail = str(error).strip() or error.__class__.__name__
        return False, f"Chữ ký KHÔNG hợp lệ: {detail}"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for rel, expected in manifest.get("files", {}).items():
        path = package_dir / rel
        if not path.is_file():
            return False, f"Thiếu tệp trong gói: {rel}"
        digest = hashlib.sha256()
        with path.open("rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                digest.update(chunk)
        if digest.hexdigest() != expected:
            return False, f"Tệp bị sửa đổi: {rel}"
    return True, f"coremre {manifest.get('version')} — chữ ký và toàn vẹn OK ({len(manifest['files'])} tệp)."


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else latest_package_dir()
    if target is None:
        print("Chưa có gói core nào: chạy tools/pack_core.py trước.")
        return 2
    ok, message = verify(target)
    print(("OK  " if ok else "FAIL ") + message)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
