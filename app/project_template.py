"""Manifest-driven, non-destructive project template synchronization."""
from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import dataclass
from pathlib import Path, PurePosixPath


STATE_PATH = Path(".vxpe") / "template-state.json"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _safe_relative(value: str) -> Path:
    pure = PurePosixPath(str(value).replace("\\", "/"))
    if pure.is_absolute() or not pure.parts or ".." in pure.parts or ":" in pure.parts[0]:
        raise ValueError(f"Đường dẫn template không an toàn: {value!r}")
    return Path(*pure.parts)


@dataclass(frozen=True, slots=True)
class TemplateFile:
    source: Path
    target: Path
    policy: str


class ProjectTemplateManager:
    """Create and update layout-v2 projects from ``template.manifest.json``.

    ``managed`` files are updated only while their local hash still matches the
    last materialized base. ``seed`` files are created once and then permanently
    owned by the project author.
    """

    def __init__(self, template_root: Path):
        self.template_root = Path(template_root).resolve()
        manifest_path = self.template_root / "template.manifest.json"
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("template.manifest.json phải là object JSON.")
        self.version = str(data.get("version", "")).strip()
        self.layout_version = int(data.get("layout_version", 0))
        if not self.version or self.layout_version < 2:
            raise ValueError("Manifest template thiếu version/layout_version hợp lệ.")
        self.directories = tuple(_safe_relative(item) for item in data.get("directories", []))
        files: list[TemplateFile] = []
        seen: set[Path] = set()
        for item in data.get("files", []):
            if not isinstance(item, dict):
                raise ValueError("Mỗi file trong manifest phải là object.")
            source = _safe_relative(item["source"])
            target = _safe_relative(item.get("target", item["source"]))
            policy = str(item.get("policy", "managed"))
            if policy not in {"managed", "seed"}:
                raise ValueError(f"Policy template không hỗ trợ: {policy}")
            if target in seen:
                raise ValueError(f"Target bị lặp trong manifest: {target}")
            source_path = (self.template_root / source).resolve()
            if not source_path.is_relative_to(self.template_root):
                raise ValueError(f"Source template nằm ngoài template_blank: {source}")
            if not source_path.is_file():
                raise FileNotFoundError(source_path)
            seen.add(target)
            files.append(TemplateFile(source, target, policy))
        self.files = tuple(files)

    def create(self, project_root: Path) -> list[Path]:
        root = Path(project_root).resolve()
        root.mkdir(parents=True, exist_ok=True)
        for relative in self.directories:
            (root / relative).mkdir(parents=True, exist_ok=True)
        copied: list[Path] = []
        for entry in self.files:
            destination = root / entry.target
            if destination.exists():
                raise FileExistsError(f"Không ghi đè tệp project khi khởi tạo: {destination}")
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(self.template_root / entry.source, destination)
            copied.append(entry.target)
        return copied

    def sync(self, project_root: Path) -> tuple[list[Path], list[Path]]:
        root = Path(project_root).resolve()
        state = self._read_state(root)
        prior = state.get("files", {}) if isinstance(state, dict) else {}
        updated: list[Path] = []
        preserved: list[Path] = []
        for relative in self.directories:
            (root / relative).mkdir(parents=True, exist_ok=True)
        for entry in self.files:
            if entry.policy != "managed":
                continue
            source = self.template_root / entry.source
            destination = root / entry.target
            record = prior.get(entry.target.as_posix(), {}) if isinstance(prior, dict) else {}
            if not destination.exists():
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, destination)
                updated.append(entry.target)
                continue
            base_hash = record.get("base_sha256") if isinstance(record, dict) else None
            template_hash = record.get("template_sha256") if isinstance(record, dict) else None
            source_hash = _sha256(source)
            if not base_hash or _sha256(destination) != base_hash:
                if template_hash and source_hash != template_hash:
                    preserved.append(entry.target)
                continue
            if source_hash != template_hash:
                shutil.copy2(source, destination)
                updated.append(entry.target)
        return updated, preserved

    def finalize(self, project_root: Path, refreshed: list[Path], *, initialize: bool = False) -> None:
        root = Path(project_root).resolve()
        old = self._read_state(root)
        records = old.get("files", {}) if isinstance(old, dict) else {}
        records = dict(records) if isinstance(records, dict) else {}
        selected = set(refreshed)
        for entry in self.files:
            if entry.policy != "managed" or (not initialize and entry.target not in selected):
                continue
            destination = root / entry.target
            if destination.is_file():
                records[entry.target.as_posix()] = {
                    "base_sha256": _sha256(destination),
                    "template_sha256": _sha256(self.template_root / entry.source),
                }
        payload = {
            "format": "VXPEngine Project Template State",
            "layout_version": self.layout_version,
            "template_version": self.version,
            "files": records,
        }
        state_path = root / STATE_PATH
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    @staticmethod
    def _read_state(root: Path) -> dict:
        path = root / STATE_PATH
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
        return data if isinstance(data, dict) else {}
