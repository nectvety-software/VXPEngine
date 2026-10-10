"""Small authenticated SSH operations gateway with a mobile-first web UI."""

from __future__ import annotations

import hmac
import json
import logging
import os
import re
import secrets
import shlex
import threading
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

MAX_BODY = 2048
MAX_OUTPUT = 8192
SSH_TIMEOUT = 6
RATE_LIMIT = 20
RATE_WINDOW = 60
SERVICE_RE = re.compile(r"^[A-Za-z0-9_.@-]{1,64}$")
MACRO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,32}$")
MQTT_TOPIC_RE = re.compile(r"^[A-Za-z0-9_/-]{1,128}$")
SCRIPT_RE = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")
LOG = logging.getLogger("sshwebbridge")

PAGE = r'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no"><meta name="theme-color" content="#09221f"><title>SSH Bridge</title>
<link rel="stylesheet" href="/style.css"></head><body>
<header><div class="mark">S</div><div><h1>SSH WEB BRIDGE</h1><small>Remote operations · low data mode</small></div></header>
<section class="card"><p class="label">Gateway access</p><input id="token" type="password" autocomplete="off" placeholder="Bearer token" aria-label="Gateway bearer token"><div class="row"><button id="connect">CONNECT</button><button id="forget">CLEAR TOKEN</button></div><p id="status" class="status">Token stays in this browser tab only.</p></section>
<section class="card"><p class="label">Target server</p><select id="target" aria-label="Target server"><option value="">Connect to load targets</option></select></section>
<section class="card"><p class="label">Health checks · read only</p><div class="row"><button data-action="health">SYSTEM STATUS</button><button data-action="disk">DISK SPACE</button><button data-action="memory">MEMORY</button><button data-action="processes">TOP PROCESSES</button></div></section>
<section class="card"><p class="label">Managed service</p><select id="service"><option value="">Select allowed service</option></select><button id="restart" class="warn">RESTART SERVICE</button><p class="hint danger">Restart requires typing RESTART in the confirmation prompt.</p></section>
<section class="card"><p class="label">Smart home macros</p><div id="macros" class="row"><span class="hint">Connect and choose a target to load macros.</span></div></section>
<section class="card"><p class="label">Result</p><div id="output" class="out" role="log" aria-live="polite">Connected output will appear here.</div></section>
<footer>SSH keys stay on the gateway · Unknown SSH host keys are rejected</footer>
<script src="/app.js" defer></script></body></html>'''


class BridgeError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status


class SlidingRateLimit:
    def __init__(self, limit: int = RATE_LIMIT, window: int = RATE_WINDOW) -> None:
        self.limit = limit
        self.window = window
        self._hits: dict[str, list[float]] = {}
        self._lock = threading.Lock()

    def allow(self, key: str, now: float | None = None) -> bool:
        now = time.monotonic() if now is None else now
        with self._lock:
            hits = [t for t in self._hits.get(key, []) if now - t < self.window]
            if len(hits) >= self.limit:
                self._hits[key] = hits
                return False
            hits.append(now)
            self._hits[key] = hits
            return True


def load_config(path: str | Path) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("configuration root must be a JSON object")
    known_hosts_value = data.get("known_hosts")
    if not isinstance(known_hosts_value, str) or not known_hosts_value:
        raise ValueError("known_hosts path is required")
    known_hosts = Path(known_hosts_value).expanduser()
    if not known_hosts.is_file():
        raise ValueError("known_hosts file must exist and be provisioned out of band")
    targets: dict[str, dict[str, Any]] = {}
    configured_targets = data.get("targets", [])
    if not isinstance(configured_targets, list):
        raise ValueError("targets must be a JSON array")
    for item in configured_targets:
        if not isinstance(item, dict):
            raise ValueError("each target must be a JSON object")
        target_id = item.get("id", "")
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,32}", target_id):
            raise ValueError("target IDs must use 1-32 letters, digits, _ or -")
        host = item.get("host", "")
        if not isinstance(host, str) or not host or len(host) > 253:
            raise ValueError(f"invalid host for target {target_id}")
        if not isinstance(item.get("username"), str) or not item["username"]:
            raise ValueError(f"username is required for target {target_id}")
        label = item.get("label", target_id)
        if not isinstance(label, str) or len(label) > 48:
            raise ValueError(f"invalid label for target {target_id}")
        port = item.get("port", 22)
        if not isinstance(port, int) or not 1 <= port <= 65535:
            raise ValueError(f"invalid port for target {target_id}")
        services = item.get("services", [])
        if not isinstance(services, list) or any(not isinstance(s, str) or not SERVICE_RE.fullmatch(s) for s in services):
            raise ValueError(f"invalid service allowlist for target {target_id}")
        macros = item.get("macros", [])
        if not isinstance(macros, list):
            raise ValueError(f"macros must be an array for target {target_id}")
        macro_ids: set[str] = set()
        for macro in macros:
            if not isinstance(macro, dict) or not isinstance(macro.get("id"), str) or not MACRO_ID_RE.fullmatch(macro["id"]):
                raise ValueError(f"invalid macro ID for target {target_id}")
            if macro["id"] in macro_ids or macro["id"] in {"health", "disk", "memory", "processes", "restart_service"}:
                raise ValueError(f"duplicate or reserved macro ID for target {target_id}")
            macro_ids.add(macro["id"])
            if not isinstance(macro.get("label"), str) or len(macro["label"]) > 48:
                raise ValueError(f"invalid macro label for target {target_id}")
            kind = macro.get("kind")
            if kind == "mqtt":
                if not MQTT_TOPIC_RE.fullmatch(str(macro.get("topic", ""))):
                    raise ValueError(f"invalid MQTT topic in macro {macro['id']}")
                if not re.fullmatch(r"[A-Za-z0-9_-]{1,32}", str(macro.get("payload", ""))):
                    raise ValueError(f"invalid MQTT payload in macro {macro['id']}")
            elif kind == "script":
                if not SCRIPT_RE.fullmatch(str(macro.get("script", ""))):
                    raise ValueError(f"invalid script basename in macro {macro['id']}")
            else:
                raise ValueError(f"unsupported macro kind in macro {macro['id']}")
            if not isinstance(macro.get("confirm", False), bool) or not isinstance(macro.get("read_only", False), bool):
                raise ValueError(f"invalid macro flags in macro {macro['id']}")
        key_file = Path(item.get("key_file", "")).expanduser()
        if not key_file.is_file():
            raise ValueError(f"SSH key file must exist for target {target_id}")
        if target_id in targets:
            raise ValueError(f"duplicate target ID {target_id}")
        targets[target_id] = {**item, "key_file": str(key_file)}
    if not targets:
        raise ValueError("configure at least one SSH target")
    return {"known_hosts": str(known_hosts), "targets": targets}


def action_catalog(target: dict[str, Any]) -> list[dict[str, Any]]:
    actions = [
        {"id": "health", "label": "System status", "read_only": True},
        {"id": "disk", "label": "Disk space", "read_only": True},
        {"id": "memory", "label": "Memory", "read_only": True},
        {"id": "processes", "label": "Top processes", "read_only": True},
    ]
    if target.get("services"):
        actions.append({"id": "restart_service", "label": "Restart allowed service", "read_only": False})
    for target_macro in target.get("macros", []):
        actions.append({"id": target_macro["id"], "label": target_macro["label"], "read_only": bool(target_macro.get("read_only", False))})
    return actions


def build_command(action: str, service: str | None, target: dict[str, Any], confirm: str | None) -> str:
    commands = {
        "health": "uptime",
        "disk": "df -h",
        "memory": "free -m",
        "processes": "ps -eo pid,comm,%cpu,%mem --sort=-%cpu | head -n 8",
    }
    if action in commands:
        return commands[action]
    if action == "restart_service":
        allowed = target.get("services", [])
        if not isinstance(service, str) or service not in allowed or not SERVICE_RE.fullmatch(service):
            raise BridgeError(HTTPStatus.BAD_REQUEST, "Service is not in this target's allowlist")
        if confirm != "RESTART":
            raise BridgeError(HTTPStatus.BAD_REQUEST, "Type RESTART to confirm this operation")
        # Service names are validated and still quoted as a final boundary.
        return "systemctl restart -- " + service
    for macro in target.get("macros", []):
        if macro.get("id") != action:
            continue
        if macro.get("confirm") and confirm != "CONFIRM":
            raise BridgeError(HTTPStatus.BAD_REQUEST, "Type CONFIRM to confirm this operation")
        if macro["kind"] == "mqtt":
            return "mosquitto_pub -h localhost -t " + shlex.quote(macro["topic"]) + " -m " + shlex.quote(macro["payload"])
        if macro["kind"] == "script":
            return "/usr/local/lib/sshwebbridge/actions/" + macro["script"]
    raise BridgeError(HTTPStatus.BAD_REQUEST, "Unknown action")


def execute_ssh(config: dict[str, Any], target: dict[str, Any], command: str) -> tuple[str, int]:
    try:
        import paramiko
    except ImportError as exc:
        raise BridgeError(HTTPStatus.SERVICE_UNAVAILABLE, "Install the gateway requirements first") from exc
    client = paramiko.SSHClient()
    client.load_host_keys(config["known_hosts"])
    client.set_missing_host_key_policy(paramiko.RejectPolicy())
    try:
        client.connect(
            hostname=target["host"], port=target.get("port", 22), username=target["username"],
            key_filename=target["key_file"], timeout=SSH_TIMEOUT, banner_timeout=SSH_TIMEOUT,
            auth_timeout=SSH_TIMEOUT, allow_agent=False, look_for_keys=False,
            compress=True, channel_timeout=SSH_TIMEOUT,
        )
        _stdin, stdout, stderr = client.exec_command(command, timeout=SSH_TIMEOUT, get_pty=False)
        chunks = stdout.read(MAX_OUTPUT + 1)
        if len(chunks) > MAX_OUTPUT:
            chunks = chunks[:MAX_OUTPUT] + b"\n[output truncated]"
        err = stderr.read(max(0, MAX_OUTPUT - len(chunks)) + 1)
        raw = chunks + (b"\n" if chunks and err else b"") + err[:MAX_OUTPUT]
        if len(err) > max(0, MAX_OUTPUT - len(chunks)):
            raw += b"\n[output truncated]"
        return raw.decode("utf-8", errors="replace")[:MAX_OUTPUT], stdout.channel.recv_exit_status()
    except BridgeError:
        raise
    except Exception as exc:
        LOG.warning("SSH operation failed for target %s (%s)", target.get("id", "?"), type(exc).__name__)
        raise BridgeError(HTTPStatus.BAD_GATEWAY, "SSH connection or command failed; check gateway logs") from exc
    finally:
        client.close()


class BridgeServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, server_address: tuple[str, int], token: str, config: dict[str, Any], pair_code: str = ""):
        super().__init__(server_address, BridgeHandler)
        self.token = token
        self.pair_code = pair_code
        self.config = config
        self.limiter = SlidingRateLimit()
        self.pair_limiter = SlidingRateLimit(5, 600)
        self.sessions: dict[str, float] = {}
        self.sessions_lock = threading.Lock()


class BridgeHandler(BaseHTTPRequestHandler):
    server: BridgeServer

    def log_message(self, fmt: str, *args: Any) -> None:
        # Never log headers or body: the authorization token is a secret.
        LOG.info("%s %s", self.client_address[0], args[0] if args else "request")

    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self'; script-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
        self.send_header("Referrer-Policy", "no-referrer")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, status: int, value: Any) -> None:
        self._send(status, json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8"), "application/json; charset=utf-8")

    def _authorize(self) -> None:
        expected = "Bearer " + self.server.token
        supplied = self.headers.get("Authorization", "")
        valid_master = hmac.compare_digest(supplied.encode(), expected.encode())
        session_token = supplied[7:] if supplied.startswith("Bearer ") else ""
        now = time.monotonic()
        with self.server.sessions_lock:
            self.server.sessions = {key: expiry for key, expiry in self.server.sessions.items() if expiry > now}
            valid_session = session_token in self.server.sessions
        if not (valid_master or valid_session):
            raise BridgeError(HTTPStatus.UNAUTHORIZED, "Authorization required")
        if not self.server.limiter.allow(self.client_address[0]):
            raise BridgeError(HTTPStatus.TOO_MANY_REQUESTS, "Rate limit exceeded")

    def _read_json(self) -> dict[str, Any]:
        raw_len = self.headers.get("Content-Length", "0")
        try:
            length = int(raw_len)
        except ValueError as exc:
            raise BridgeError(HTTPStatus.BAD_REQUEST, "Invalid content length") from exc
        if not 0 < length <= MAX_BODY:
            raise BridgeError(HTTPStatus.BAD_REQUEST, "Request body is empty or too large")
        try:
            data = json.loads(self.rfile.read(length))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise BridgeError(HTTPStatus.BAD_REQUEST, "Invalid JSON body") from exc
        if not isinstance(data, dict):
            raise BridgeError(HTTPStatus.BAD_REQUEST, "JSON object required")
        return data

    def do_GET(self) -> None:
        path = urlsplit(self.path).path
        if path == "/" or path == "/index.html":
            self._send(HTTPStatus.OK, PAGE.encode(), "text/html; charset=utf-8")
            return
        if path in ("/style.css", "/app.js"):
            asset = Path(__file__).parent / "static" / path.rsplit("/", 1)[1]
            try:
                body = asset.read_bytes()
            except OSError:
                self._json(HTTPStatus.NOT_FOUND, {"error": "Not found"})
                return
            mime = "text/css; charset=utf-8" if path.endswith(".css") else "text/javascript; charset=utf-8"
            self._send(HTTPStatus.OK, body, mime)
            return
        try:
            self._authorize()
            if path == "/api/targets":
                targets = [{"id": t["id"], "label": t.get("label", t["id"]), "services": t.get("services", []),
                            "actions": [{"id": m["id"], "label": m["label"], "confirm": m.get("confirm", False)} for m in t.get("macros", [])]}
                           for t in self.server.config["targets"].values()]
                self._json(HTTPStatus.OK, {"targets": targets})
            elif path == "/api/actions":
                actions = action_catalog({"services": [s for t in self.server.config["targets"].values() for s in t.get("services", [])],
                                          "macros": [m for t in self.server.config["targets"].values() for m in t.get("macros", [])]})
                self._json(HTTPStatus.OK, {"actions": actions})
            else:
                raise BridgeError(HTTPStatus.NOT_FOUND, "Not found")
        except BridgeError as exc:
            self._json(exc.status, {"error": str(exc)})

    def do_POST(self) -> None:
        path = urlsplit(self.path).path
        if path == "/api/pair":
            self._pair()
            return
        if path != "/api/run":
            self._json(HTTPStatus.NOT_FOUND, {"error": "Not found"})
            return
        started = time.monotonic()
        try:
            self._authorize()
            request = self._read_json()
            target_id = request.get("target")
            target = self.server.config["targets"].get(target_id) if isinstance(target_id, str) else None
            if target is None:
                raise BridgeError(HTTPStatus.BAD_REQUEST, "Unknown target")
            command = build_command(request.get("action", ""), request.get("service"), target, request.get("confirm"))
            output, exit_code = execute_ssh(self.server.config, target, command)
            elapsed = int((time.monotonic() - started) * 1000)
            LOG.info("action=%s target=%s exit=%s elapsed_ms=%d", request.get("action"), target_id, exit_code, elapsed)
            self._json(HTTPStatus.OK, {"output": output[:MAX_OUTPUT], "exit_code": exit_code, "elapsed_ms": elapsed})
        except BridgeError as exc:
            self._json(exc.status, {"error": str(exc)})
        except (BrokenPipeError, ConnectionResetError):
            return

    def _pair(self) -> None:
        if not self.server.pair_code:
            self._json(HTTPStatus.NOT_FOUND, {"error": "Device pairing is not enabled"})
            return
        if not self.server.pair_limiter.allow(self.client_address[0]):
            self._json(HTTPStatus.TOO_MANY_REQUESTS, {"error": "Pairing rate limit exceeded"})
            return
        try:
            request = self._read_json()
            code = request.get("code", "")
            valid = isinstance(code, str) and hmac.compare_digest(code.encode(), self.server.pair_code.encode())
            if not valid:
                raise BridgeError(HTTPStatus.UNAUTHORIZED, "Pairing failed")
            token = secrets.token_urlsafe(32)
            with self.server.sessions_lock:
                if len(self.server.sessions) >= 64:
                    oldest = min(self.server.sessions, key=self.server.sessions.get)
                    del self.server.sessions[oldest]
                self.server.sessions[token] = time.monotonic() + 1800
            LOG.info("device paired from %s; session expires in 30 minutes", self.client_address[0])
            self._json(HTTPStatus.OK, {"token": token, "expires_in": 1800})
        except BridgeError as exc:
            self._json(exc.status, {"error": str(exc)})


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    token = os.environ.get("SSHWB_TOKEN", "")
    if len(token) < 32:
        raise SystemExit("Set SSHWB_TOKEN to a random secret of at least 32 characters")
    config_path = os.environ.get("SSHWB_CONFIG", "config.json")
    pair_code = os.environ.get("SSHWB_PAIR_CODE", "")
    if pair_code and not re.fullmatch(r"[0-9]{8,12}", pair_code):
        raise SystemExit("SSHWB_PAIR_CODE must be 8-12 digits")
    try:
        config = load_config(config_path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise SystemExit(f"Invalid SSHWB_CONFIG: {exc}") from exc
    host = os.environ.get("SSHWB_HOST", "127.0.0.1")
    port = int(os.environ.get("SSHWB_PORT", "8765"))
    server = BridgeServer((host, port), token, config, pair_code)
    LOG.info("SSH Web Bridge listening on %s:%d", host, port)
    try:
        server.serve_forever(poll_interval=0.4)
    except KeyboardInterrupt:
        LOG.info("Shutting down")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
