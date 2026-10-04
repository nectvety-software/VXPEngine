"""Non-blocking release manifest checker for VXPEngine."""
from __future__ import annotations

import json
import os
import re

from PySide6.QtCore import QObject, QUrl, Signal
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest


# "vxpstore" ở đây là TÊN OWNER TRÊN GITHUB, không phải tên core — đừng đổi.
DEFAULT_UPDATE_URL = (
    "https://api.github.com/repos/vxpstore/VXPEngine/releases/latest"
)


def version_tuple(value: str) -> tuple[int, ...]:
    stable_part = str(value).split("+", 1)[0].split("-", 1)[0]
    numbers = [int(item) for item in re.findall(r"\d+", stable_part)]
    return tuple((numbers + [0, 0, 0])[:4])


def is_newer_version(candidate: str, current: str) -> bool:
    return version_tuple(candidate) > version_tuple(current)


class UpdateChecker(QObject):
    update_available = Signal(dict)
    up_to_date = Signal()
    failed = Signal(str)
    # Kênh phát hành chưa tồn tại (GitHub 404) — không phải lỗi mạng.
    channel_unavailable = Signal()

    def __init__(self, current_version: str, parent=None, update_url: str | None = None) -> None:
        super().__init__(parent)
        self.current_version = current_version
        self.update_url = (update_url or os.environ.get("VXPE_UPDATE_URL") or DEFAULT_UPDATE_URL).strip()
        self.network = QNetworkAccessManager(self)
        self._manual = False
        self._channel_missing = False

    @property
    def last_check_was_manual(self) -> bool:
        return self._manual

    def check(self, *, manual: bool = False) -> None:
        self._manual = manual
        if not self.update_url:
            self.failed.emit("Chưa cấu hình VXPE_UPDATE_URL.")
            return
        if self._channel_missing and not manual:
            return
        request = QNetworkRequest(QUrl(self.update_url))
        request.setRawHeader(b"Accept", b"application/vnd.github+json, application/json")
        request.setRawHeader(b"User-Agent", b"VXPEngine-Update-Checker")
        reply = self.network.get(request)
        reply.finished.connect(lambda current=reply: self._finished(current))

    def _finished(self, reply: QNetworkReply) -> None:
        try:
            status = reply.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute)
            if reply.error() != QNetworkReply.NetworkError.NoError:
                if status in (403, 404, 410) or reply.error() in (
                    QNetworkReply.NetworkError.ContentNotFoundError,
                    QNetworkReply.NetworkError.AuthenticationRequiredError,
                ):
                    self._channel_missing = True
                    self.channel_unavailable.emit()
                else:
                    self.failed.emit(reply.errorString())
                return
            body = reply.readAll() if reply.isReadable() else b""
            if not body:
                self.failed.emit("Kết nối cập nhật bị đóng trước khi nhận đủ dữ liệu.")
                return
            payload = json.loads(bytes(body).decode("utf-8", errors="replace"))
            if isinstance(payload, dict) and str(payload.get("message", "")).lower() == "not found":
                self._channel_missing = True
                self.channel_unavailable.emit()
                return
            candidate = str(payload.get("version") or payload.get("tag_name") or "").lstrip("vV")
            download_url = str(
                payload.get("download_url")
                or payload.get("html_url")
                or payload.get("release_url")
                or ""
            )
            assets = payload.get("assets") if isinstance(payload.get("assets"), list) else []
            msi_asset = next(
                (item for item in assets if isinstance(item, dict) and str(item.get("name", "")).lower().endswith(".msi")),
                {},
            )
            msi_name = str(msi_asset.get("name") or "")
            checksum_asset = next(
                (
                    item for item in assets
                    if isinstance(item, dict)
                    and str(item.get("name", "")).lower() in {
                        f"{msi_name.lower()}.sha256", "sha256sums.txt", "checksums.txt"
                    }
                ),
                {},
            )
            if not candidate:
                self.failed.emit("Manifest cập nhật không có trường version/tag_name.")
                return
            if is_newer_version(candidate, self.current_version):
                self.update_available.emit({
                    "version": candidate,
                    "url": download_url,
                    "msi_url": str(msi_asset.get("browser_download_url") or payload.get("msi_url") or ""),
                    "sha256_url": str(checksum_asset.get("browser_download_url") or payload.get("sha256_url") or ""),
                    "notes": str(payload.get("notes") or payload.get("body") or ""),
                })
            else:
                self.up_to_date.emit()
        except (TypeError, ValueError, json.JSONDecodeError) as error:
            self.failed.emit(f"Không đọc được manifest cập nhật: {error}")
        finally:
            reply.deleteLater()
