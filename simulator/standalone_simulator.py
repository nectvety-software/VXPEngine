r"""Standalone Frame Simulator — chỉ hiện *khung máy* VXPEmu cùng panel SDK.

Khác với :mod:`app.widgets.emulator_panel` (nhúng trong IDE) và VXPEmu gốc
(toàn bộ UI có menu, dock, cây project, cửa sổ log…), simulator này **chỉ giữ
lại đúng phần khung** giống ảnh tham chiếu ``8687567.PNG``:

* Top toolbar 7 nút (khung ảnh · nạp · camera · folder · record · xoay · tách)
* Ô màn hình 240×320 viền mỏng
* Dòng nhắc ``Multi-tan: 2=a·b·c 3=d·e·f 7=p·q·r·s 0=space``
* Bàn phím MRE 20 phím (12 số + 7 D-pad/OK + 1 phím mềm)

Bên cạnh khung máy là **panel SDK** kiểu "Extensions" của VS Code:

* Tiêu đề đậm + mô tả nhỏ cho từng thành phần môi trường
* Huy hiệu trạng thái (Đã cài · Có thể cài tự động · Cần làm thủ công)
* Tìm kiếm + bộ lọc (Tất cả / Đã cài / Chưa cài / Có thể cài tự động)
* Nút **Install** / **Uninstall** theo từng dòng (gộp cả hàng loạt ở footer)
* Nút **Check for updates** — khi *mọi* thành phần đã được cài (môi trường đầy
  đủ), trả về "No update needed" — đúng yêu cầu: sau khi cài SDK mới nhất, bấm
  kiểm tra cập nhật sẽ báo không phải cập nhật nữa.

Chạy::

    python simulator/standalone_simulator.py            # mặc định cổng 8765
    python simulator/standalone_simulator.py --port 9000

Hoặc từ ``run_windows.bat`` không — đây là tiện ích độc lập.

Không phụ thuộc PySide6/Qt: chỉ dùng ``http.server`` của Python chuẩn để có thể
chạy trên bất kỳ máy nào có Python 3.11+. Logic phát hiện môi trường dùng thẳng
:mod:`app.environment_setup` — cùng nguồn với IDE, nên luôn đồng bộ.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import threading
import time
import webbrowser
from dataclasses import asdict
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse
from urllib.request import ProxyHandler, build_opener

# ---------------------------------------------------------------------------
# Bootstrap: cho phép chạy từ mọi nơi (script độc lập với IDE) bằng cách thêm
# thư mục gốc repo vào sys.path rồi import app.environment_setup giống IDE.
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

try:
    # Dùng module *không Qt* để simulator chạy được bằng Python chuẩn — không
    # cần cài PySide6. ``app.environment_setup`` (Qt-based) re-export cùng tên
    # nên hai nơi dùng chung một nguồn dữ liệu REQUIREMENTS.
    from app.environment_spec import (  # type: ignore
        REQUIREMENTS,
        Requirement,
        all_requirements,
        detect_missing,
        installable,
    )
except Exception:  # pragma: no cover - chạy ngoài repo thì fallback
    REQUIREMENTS = ()
    Requirement = None  # type: ignore
    all_requirements = lambda: ()  # type: ignore
    detect_missing = lambda *a, **k: []  # type: ignore
    installable = lambda *a, **k: []  # type: ignore

TEMPLATES_DIR = SCRIPT_DIR / "templates"
STATIC_DIR = SCRIPT_DIR / "static"

#: Số cổng liên tiếp được thử khi cổng mặc định đã bận.
_PORT_RETRY = 10

# Phiên bản "manifest" mà ta coi là mới nhất để so sánh khi bấm Check for
# updates. Trong tình huống thật ta sẽ GET một manifest từ GitHub releases;
# ở đây ta để "latest" là danh sách thành phần hiện tại trong
# ``REQUIREMENTS`` — mọi máy có đủ những thứ này là "đã cập nhật".
LATEST_MANIFEST: dict[str, str] = {
    "engine_version": "2026.08",
    "sdk_latest": "VXPEngine-SDK-2.0",
    "vxpemu_latest": "integrated",
    "python_runtime": "3.11+",
    "checked_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
}


# ---------------------------------------------------------------------------
# Environment model — JSON-serialisable cho frontend.
# ---------------------------------------------------------------------------

_ICON_FOR_KEY = {
    "cmake": "fa5s.cog",
    "vs2022": "fa5s.window-maximize",
    "bash": "fa5s.terminal",
    "arm_gcc": "fa5s.microchip",
    "python_deps": "fa5s.python",
    "mre_sdk": "fa5s.cubes",
    "packaging": "fa5s.file-signature",
    "signing_backend": "fa5s.key",
    "vxpemu": "fa5s.desktop",
    "signing_key": "fa5s.key",
}


def _state_of(requirement: Requirement, satisfied: bool) -> tuple[str, str]:
    if satisfied:
        return "installed", "Đã cài đặt"
    if requirement.is_installable:
        return "auto", "Chưa cài · có thể cài tự động"
    return "manual", "Chưa cài · cần làm thủ công"


def _serialize_requirement(requirement: Requirement) -> dict[str, Any]:
    satisfied = bool(requirement.satisfied)
    state, label = _state_of(requirement, satisfied)
    return {
        "key": requirement.key,
        "name": requirement.name,
        "hint": requirement.hint or "",
        "optional": bool(requirement.optional),
        "satisfied": satisfied,
        "installable": bool(requirement.is_installable),
        "state": state,
        "state_label": label,
        "icon": _ICON_FOR_KEY.get(requirement.key, "fa5s.puzzle-piece"),
    }


def _summary(requirements: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(requirements)
    installed = sum(1 for row in requirements if row["satisfied"])
    missing = total - installed
    auto = sum(1 for row in requirements if row["state"] == "auto")
    manual = sum(1 for row in requirements if row["state"] == "manual")
    if missing == 0:
        headline = "✅ Môi trường đầy đủ — không cần cập nhật."
    else:
        headline = (
            f"Đã cài {installed}/{total} · Thiếu {missing}"
            + (f" ({auto} cài tự động được)" if auto else "")
            + (f" · {manual} cần làm thủ công" if manual else "")
        )
    return {
        "total": total,
        "installed": installed,
        "missing": missing,
        "installable_auto": auto,
        "manual": manual,
        "headline": headline,
    }


def _all_requirements_serialised() -> list[dict[str, Any]]:
    return [_serialize_requirement(req) for req in all_requirements()]


def _update_check_payload(requirements: list[dict[str, Any]]) -> dict[str, Any]:
    """Logic "Check for updates" cho frontend.

    Một bản manifest "latest" được so với trạng thái thực tế trên máy. Khi *mọi*
    thành phần đã cài (không còn missing), ta trả về "no_update_needed". Ngược
    lại liệt kê những thành phần chưa có — đúng yêu cầu: "khi đã cài đặt thư
    viện môi trường SDK mới nhất rồi thì khi kiểm tra cập nhật sẽ báo không
    phải cập nhật nữa".
    """
    missing = [row for row in requirements if not row["satisfied"]]
    if not missing:
        return {
            "status": "up_to_date",
            "code": "NO_UPDATE_NEEDED",
            "message": "Đã cài đặt SDK và thư viện môi trường mới nhất. Không cần cập nhật.",
            "manifest": LATEST_MANIFEST,
            "checked_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "missing": [],
        }
    return {
        "status": "updates_available",
        "code": "UPDATE_AVAILABLE",
        "message": f"Có {len(missing)} thành phần chưa cập nhật.",
        "manifest": LATEST_MANIFEST,
        "checked_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "missing": missing,
    }


def _install(requirement_keys: list[str]) -> dict[str, Any]:
    """Chạy lệnh cài thẳng qua :mod:`subprocess` (không cần Qt).

    Logic y hệt :meth:`EnvironmentInstaller.install` của IDE nhưng dùng
    :mod:`subprocess` vì :class:`EnvironmentInstaller` là ``QObject`` cần Qt
    event loop — simulator chạy ngoài IDE không có.
    """
    if Requirement is None:
        return {"ok": False, "error": "Không thể truy cập environment_spec.", "log": []}
    if not shutil.which("bash") and not shutil.which("cmd"):
        return {"ok": False, "error": "Không có shell để chạy lệnh cài.", "log": []}

    # Map key → Requirement.
    by_key = {req.key: req for req in all_requirements()}
    log: list[str] = []
    results: list[tuple[str, int]] = []
    for key in requirement_keys:
        req = by_key.get(key)
        if req is None:
            log.append(f"[Setup] ⚠ Không tìm thấy thành phần: {key}")
            continue
        if req.satisfied:
            log.append(f"[Setup] ✓ Đã có sẵn: {req.name}")
            results.append((req.name, 0))
            continue
        command = req.command()
        if not command:
            log.append(
                f"[Setup] ⚠ Bỏ qua {req.name}: cần làm thủ công — {req.hint}"
            )
            results.append((req.name, -1))
            continue
        program, *args = command
        log.append(f"[Setup] ▶ {req.name}")
        log.append(f"[Setup]   $ {program} {' '.join(args)}".rstrip())
        try:
            completed = subprocess.run(  # noqa: S603 - trusted install commands
                [program, *args],
                capture_output=True,
                text=True,
                timeout=600,
            )
        except (subprocess.TimeoutExpired, FileNotFoundError) as error:
            log.append(f"[Setup] ✗ {req.name}: {error}")
            results.append((req.name, -1))
            continue
        for line in completed.stdout.splitlines():
            line = line.rstrip()
            if line:
                log.append(f"[Setup]   {line}")
        if completed.returncode == 0:
            log.append(f"[Setup] ✓ {req.name}")
        else:
            log.append(
                f"[Setup] ✗ {req.name} (mã {completed.returncode})"
                + (f" — {req.hint}" if req.hint else "")
            )
        results.append((req.name, completed.returncode))

    failed = [name for name, code in results if code != 0]
    return {
        "ok": not failed,
        "log": log,
        "failed": failed,
        "results": [{"name": name, "code": code} for name, code in results],
    }


# ---------------------------------------------------------------------------
# HTTP handler.
# ---------------------------------------------------------------------------

class _Handler(BaseHTTPRequestHandler):
    server_version = "VXPEngineFrameSimulator/1.0"

    # Tránh in log mỗi lần request để console dễ đọc.
    def log_message(self, format: str, *args: Any) -> None:  # noqa: A003 - stdlib name
        return

    # -------- helpers --------

    def _send_json(self, payload: Any, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, path: Path, *, content_type: str) -> None:
        if not path.exists() or not path.is_file():
            self.send_error(HTTPStatus.NOT_FOUND, f"{path.name} not found")
            return
        body = path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    # -------- routing --------

    def do_GET(self) -> None:  # noqa: N802 - stdlib name
        url = urlparse(self.path)
        path = url.path

        if path in ("/", "/index.html"):
            self._send_file(TEMPLATES_DIR / "index.html", content_type="text/html; charset=utf-8")
            return
        if path == "/static/style.css":
            self._send_file(STATIC_DIR / "style.css", content_type="text/css; charset=utf-8")
            return
        if path == "/static/app.js":
            self._send_file(STATIC_DIR / "app.js", content_type="application/javascript; charset=utf-8")
            return
        if path == "/api/environment":
            requirements = _all_requirements_serialised()
            self._send_json(
                {
                    "requirements": requirements,
                    "summary": _summary(requirements),
                    "manifest_latest": LATEST_MANIFEST,
                }
            )
            return
        if path == "/api/check-updates":
            requirements = _all_requirements_serialised()
            self._send_json(_update_check_payload(requirements))
            return
        if path == "/api/health":
            self._send_json({"ok": True, "time": time.time()})
            return

        self.send_error(HTTPStatus.NOT_FOUND, f"No route for {path}")

    def do_POST(self) -> None:  # noqa: N802 - stdlib name
        url = urlparse(self.path)
        path = url.path
        length = int(self.headers.get("Content-Length") or 0)
        try:
            raw = self.rfile.read(length) if length else b"{}"
            payload = json.loads(raw.decode("utf-8")) if raw else {}
        except json.JSONDecodeError as error:
            self._send_json({"ok": False, "error": f"JSON lỗi: {error}"}, status=400)
            return

        if path == "/api/install":
            keys = payload.get("keys") or []
            if not isinstance(keys, list):
                self._send_json(
                    {"ok": False, "error": "Trường 'keys' phải là danh sách."}, status=400
                )
                return
            result = _install([str(key) for key in keys])
            # Sau khi cài xong, trả thêm trạng thái mới nhất để frontend refresh.
            requirements = _all_requirements_serialised()
            result["requirements"] = requirements
            result["summary"] = _summary(requirements)
            self._send_json(result)
            return

        if path == "/api/check-updates":
            requirements = _all_requirements_serialised()
            self._send_json(_update_check_payload(requirements))
            return

        self.send_error(HTTPStatus.NOT_FOUND, f"No route for {path}")


# ---------------------------------------------------------------------------
# Entry.
# ---------------------------------------------------------------------------

def _print_check() -> int:
    """In bảng môi trường + kết quả check-updates ra stdout, rồi thoát.

    Dùng cho ``run_windows.bat`` (mục "Kiểm tra môi trường"), CI hoặc script:
    exit code ``0`` = mọi thứ đã cài (không cần cập nhật), ``1`` = còn thiếu.
    """
    requirements = _all_requirements_serialised()
    summary = _summary(requirements)
    result = _update_check_payload(requirements)

    line = "=" * 72
    print(line)
    print("  VXPEngine - Kiem tra moi truong & SDK")
    print(line)
    for row in requirements:
        mark = "+" if row["satisfied"] else "-"
        print(f"  [{mark}] {row['name']:<46} {row['state_label']}")
    print("-" * 72)
    print(f"  {summary['headline']}")
    print("-" * 72)
    if result["status"] == "up_to_date":
        print(f"  >> {result['message']}")
        print(f"  >> manifest: {result['manifest']}")
        return 0
    print(f"  >> {result['message']}")
    for row in result["missing"]:
        print(f"       - {row['name']}  ({row['state_label']})")
        if row["hint"]:
            print(f"         goi y: {row['hint']}")
    return 1


def _print_update() -> int:
    """Chỉ in verdict của ``Check for updates`` — gọn, dùng cho script/CI.

    Trả về ``0`` khi ``NO_UPDATE_NEEDED`` (mọi SDK/thư viện đã ở bản mới nhất),
    ``1`` khi ``UPDATE_AVAILABLE``. Không liệt kê chi tiết — muốn xem danh sách
    thì dùng ``--check``.
    """
    requirements = _all_requirements_serialised()
    result = _update_check_payload(requirements)
    manifest = result["manifest"]

    print(f"engine_version : {manifest['engine_version']}")
    print(f"sdk_latest     : {manifest['sdk_latest']}")
    print(f"vxpemu_latest  : {manifest['vxpemu_latest']}")
    print(f"checked_at     : {result['checked_at']}")
    print("-" * 72)
    if result["status"] == "up_to_date":
        print(result["code"])
        print("  " + result["message"])
        return 0
    print(result["code"])
    print(f"  {result['message']}")
    for row in result["missing"]:
        print(f"    - {row['name']}  ({row['state_label']})")
    print("  Chạy với --check để xem gợi ý cài đặt cho từng mục.")
    return 1


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="VXPEngine Frame Simulator",
        epilog=(
            "Ví dụ:  %(prog)s                (mở server + trình duyệt)\n"
            "        %(prog)s --port 9000\n"
            "        %(prog)s --check        (quét, exit 0 = đủ, 1 = thiếu)\n"
            "        %(prog)s --update       (chỉ in verdict cập nhật)"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--host", default="127.0.0.1", help="Bind host (mặc định 127.0.0.1)")
    parser.add_argument(
        "--port", type=int, default=8765, help="Bind port (mặc định 8765)"
    )
    parser.add_argument(
        "--no-browser", action="store_true",
        help="Không mở trình duyệt khi khởi động (mặc định có mở)."
    )
    parser.add_argument(
        "--check", action="store_true",
        help="Chỉ quét môi trường rồi in bảng ra stdout (không khởi động server). "
             "Exit 0 = đã đầy đủ, 1 = còn thiếu.",
    )
    parser.add_argument(
        "--update", action="store_true",
        help="Chỉ in verdict của Check for updates: NO_UPDATE_NEEDED (exit 0) "
             "hoặc UPDATE_AVAILABLE (exit 1). Không khởi động server.",
    )
    return parser.parse_args()


def _probe_running(base_url: str, timeout: float = 1.5) -> bool:
    """``True`` nếu đã có instance simulator đang chạy ở ``base_url``.

    Probe ``/api/health`` và kiểm tra đúng payload của ta (``{"ok": true}``) để
    không nhầm với thứ khác đang nghe cùng cổng.

    **Bắt buộc tắt proxy**: biến môi trường ``http_proxy`` có thể đưa cả request
    ``127.0.0.1`` qua một proxy trung gian và trả 502 giả, làm ta tưởng instance
    đã chết. ``ProxyHandler({})`` dựng opener không dùng proxy.
    """
    opener = build_opener(ProxyHandler({}))
    try:
        with opener.open(urljoin(base_url, "/api/health"), timeout=timeout) as response:
            if response.status != 200:
                return False
            payload = json.loads(response.read().decode("utf-8", "replace"))
    except Exception:  # noqa: BLE001 - mọi lỗi mạng đều nghĩa là "chưa chạy"
        return False
    return bool(payload.get("ok"))


def _force_utf8_stdout() -> None:
    """Ép stdout/stderr sang UTF-8 để in được tiếng Việt trên console Windows.

    ``run_windows.bat`` đã ``chcp 65001``, nhưng khi chạy trực tiếp
    (hoặc pipe qua ``more``/file) Python vẫn dùng cp1252 → UnicodeEncodeError
    ở các dấu tiếng Việt. Bắt lỗi để không phá hỏng luồng chạy bình thường.
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (ValueError, OSError):
            pass


def main() -> int:
    args = _parse_args()

    # ``--check`` / ``--update`` không khởi động server: chỉ quét rồi in kết
    # quả (dùng cho run_windows.bat, CI, hoặc kiểm tra nhanh trong terminal).
    if args.check or args.update:
        _force_utf8_stdout()
        return _print_check() if args.check else _print_update()

    # Bước 0 — đã có instance nào chạy ở cổng này chưa?
    # Nếu có, mở trình duyệt tới nó rồi thoát (đỡ mở hai server vô ích).
    if _probe_running(f"http://{args.host}:{args.port}/"):
        url = f"http://{args.host}:{args.port}/"
        print(f"[VXPEngine Frame Simulator] Đã có instance chạy tại {url}")
        if not args.no_browser:
            try:
                webbrowser.open(url)
            except Exception:
                pass
        return 0

    # Bước 1 — bind. Hai bẫy cần tránh:
    #
    # (a) Phải TẠO server bên trong vòng lặp: ``ThreadingHTTPServer(...)`` đã
    #     gọi ``server_bind()`` + ``server_activate()`` ngay trong constructor,
    #     nên cách cũ (tạo xong rồi gọi lại ``server_bind()`` trong try) là code
    #     chết — constructor ném OSError trước khi vòng lặp kịp chạy.
    # (b) KHÔNG bật ``allow_reuse_address`` (= SO_REUSEADDR). Trên Windows cờ
    #     này cho phép socket thứ hai bind đè lên cùng một cổng ĐANG LẮNG NGHE,
    #     không hề ném lỗi → vòng retry bị vô hiệu hóa và hai server tranh nhau
    #     kết nối. Python mặc định bật cờ này, nên phải tắt explicit.
    ThreadingHTTPServer.allow_reuse_address = False
    httpd: ThreadingHTTPServer | None = None
    url = ""
    last_error: OSError | None = None
    for offset in range(_PORT_RETRY):
        port = args.port + offset
        try:
            httpd = ThreadingHTTPServer((args.host, port), _Handler)
            url = f"http://{args.host}:{port}/"
            break
        except OSError as error:
            last_error = error
            continue
    if httpd is None:
        print(
            f"[VXPEngine Frame Simulator] Không bind được {args.host}:"
            f"{args.port}..{args.port + _PORT_RETRY - 1} — {last_error}"
        )
        return 1
    if args.port != httpd.server_address[1]:
        print(f"[VXPEngine Frame Simulator] Cổng {args.port} bận — dùng {httpd.server_address[1]}.")

    thread = threading.Thread(target=httpd.serve_forever, name="sim-http", daemon=True)
    thread.start()

    print(f"[VXPEngine Frame Simulator] {url}")
    print("Nhấn Ctrl+C để dừng.")

    if not args.no_browser:
        try:
            webbrowser.open(url)
        except Exception:
            pass

    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        print("\n[VXPEngine Frame Simulator] Đang tắt…")
    finally:
        httpd.shutdown()
        httpd.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
