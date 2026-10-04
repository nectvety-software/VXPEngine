"""Secure, non-blocking MSI downloader and launcher for VXPEngine updates."""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import QObject, QStandardPaths, QUrl, Signal
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest


class UpdateInstaller(QObject):
    progress = Signal(int)
    failed = Signal(str)
    launched = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.network = QNetworkAccessManager(self)
        self._release: dict = {}
        self._expected_sha256 = ""
        self._part_path: Path | None = None
        self._msi_path: Path | None = None
        self._stream = None

    def install(self, release: dict) -> bool:
        if self._stream is not None:
            self.failed.emit("Một bản cập nhật khác đang được tải.")
            return False
        msi_url = str(release.get("msi_url") or "").strip()
        checksum_url = str(release.get("sha256_url") or "").strip()
        if not self._safe_https(msi_url) or not self._safe_https(checksum_url):
            self.failed.emit("Bản phát hành thiếu liên kết HTTPS tới MSI hoặc SHA-256.")
            return False
        self._release = dict(release)
        request = self._request(checksum_url)
        reply = self.network.get(request)
        reply.finished.connect(lambda current=reply: self._checksum_finished(current))
        return True

    @staticmethod
    def _safe_https(value: str) -> bool:
        url = QUrl(value)
        return url.isValid() and url.scheme().lower() == "https" and bool(url.host())

    @staticmethod
    def _request(url: str) -> QNetworkRequest:
        request = QNetworkRequest(QUrl(url))
        request.setRawHeader(b"User-Agent", b"VXPEngine-Secure-Updater")
        request.setAttribute(
            QNetworkRequest.Attribute.RedirectPolicyAttribute,
            QNetworkRequest.RedirectPolicy.NoLessSafeRedirectPolicy,
        )
        return request

    def _checksum_finished(self, reply: QNetworkReply) -> None:
        try:
            if reply.error() != QNetworkReply.NetworkError.NoError:
                self.failed.emit(f"Không tải được checksum: {reply.errorString()}")
                return
            text = bytes(reply.readAll()).decode("ascii", "replace")
            match = re.search(r"(?i)\b([0-9a-f]{64})\b", text)
            if not match:
                self.failed.emit("Tệp checksum không chứa SHA-256 hợp lệ.")
                return
            self._expected_sha256 = match.group(1).lower()
            self._start_msi_download()
        finally:
            reply.deleteLater()

    def _start_msi_download(self) -> None:
        temp_base = QStandardPaths.writableLocation(QStandardPaths.TempLocation)
        update_dir = Path(temp_base or os.environ.get("TEMP", ".")) / "VXPEngineUpdates"
        update_dir.mkdir(parents=True, exist_ok=True)
        version = re.sub(r"[^0-9A-Za-z._-]+", "_", str(self._release.get("version") or "update"))
        self._msi_path = update_dir / f"VXPEngine-{version}-x64.msi"
        self._part_path = self._msi_path.with_suffix(".msi.part")
        try:
            self._part_path.unlink(missing_ok=True)
            self._stream = self._part_path.open("wb")
        except OSError as error:
            self._stream = None
            self.failed.emit(f"Không tạo được tệp cập nhật tạm: {error}")
            return
        reply = self.network.get(self._request(str(self._release["msi_url"])))
        reply.readyRead.connect(lambda current=reply: self._write_chunk(current))
        reply.downloadProgress.connect(self._download_progress)
        reply.finished.connect(lambda current=reply: self._msi_finished(current))

    def _write_chunk(self, reply: QNetworkReply) -> None:
        if self._stream is not None:
            self._stream.write(bytes(reply.readAll()))

    def _download_progress(self, received: int, total: int) -> None:
        if total > 0:
            self.progress.emit(max(0, min(100, int(received * 100 / total))))

    def _msi_finished(self, reply: QNetworkReply) -> None:
        self._write_chunk(reply)
        stream, self._stream = self._stream, None
        if stream is not None:
            stream.close()
        try:
            if reply.error() != QNetworkReply.NetworkError.NoError:
                self._discard_part()
                self.failed.emit(f"Không tải được MSI: {reply.errorString()}")
                return
            assert self._part_path is not None and self._msi_path is not None
            hasher = hashlib.sha256()
            with self._part_path.open("rb") as source:
                for block in iter(lambda: source.read(1024 * 1024), b""):
                    hasher.update(block)
            digest = hasher.hexdigest()
            if digest.lower() != self._expected_sha256:
                self._discard_part()
                self.failed.emit("SHA-256 của MSI không khớp; đã hủy bản cập nhật.")
                return
            os.replace(self._part_path, self._msi_path)
            policy = self._load_policy()
            if policy.get("require_authenticode", True):
                ok, message = self._verify_authenticode(
                    self._msi_path, str(policy.get("signer_thumbprint") or "")
                )
                if not ok:
                    self._msi_path.unlink(missing_ok=True)
                    self.failed.emit(message)
                    return
            started, _pid = subprocess_start_msi(self._msi_path)
            if not started:
                self.failed.emit("Không khởi động được Windows Installer.")
                return
            self.launched.emit(str(self._msi_path))
        except (OSError, AssertionError) as error:
            self.failed.emit(f"Không thể chuẩn bị bản cập nhật: {error}")
        finally:
            reply.deleteLater()

    def _discard_part(self) -> None:
        if self._part_path is not None:
            try:
                self._part_path.unlink(missing_ok=True)
            except OSError:
                pass

    @staticmethod
    def _load_policy() -> dict:
        root = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parents[1]
        try:
            value = json.loads((root / "update-policy.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {"require_authenticode": True}
        return value if isinstance(value, dict) else {"require_authenticode": True}

    @staticmethod
    def _verify_authenticode(path: Path, expected_thumbprint: str) -> tuple[bool, str]:
        quoted = str(path).replace("'", "''")
        command = (
            f"$s=Get-AuthenticodeSignature -LiteralPath '{quoted}';"
            "$o=[ordered]@{Status=[string]$s.Status;Thumbprint=[string]$s.SignerCertificate.Thumbprint};"
            "$o|ConvertTo-Json -Compress"
        )
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        try:
            result = subprocess.run(
                ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command],
                capture_output=True, text=True, timeout=30, creationflags=flags, check=False,
            )
            data = json.loads(result.stdout.strip() or "{}")
        except (OSError, subprocess.SubprocessError, ValueError) as error:
            return False, f"Không xác minh được chữ ký Authenticode: {error}"
        if result.returncode != 0 or data.get("Status") != "Valid":
            return False, "MSI không có chữ ký Authenticode hợp lệ; đã hủy cập nhật."
        actual = re.sub(r"\s+", "", str(data.get("Thumbprint") or "")).upper()
        expected = re.sub(r"\s+", "", expected_thumbprint).upper()
        if expected and actual != expected:
            return False, "Chứng thư ký MSI không khớp publisher đã ghim; đã hủy cập nhật."
        return True, "OK"


def subprocess_start_msi(path: Path) -> tuple[bool, int]:
    from PySide6.QtCore import QProcess

    return QProcess.startDetached("msiexec.exe", ["/i", str(path), "/passive", "/norestart"])
