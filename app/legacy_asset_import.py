from __future__ import annotations

import hashlib
import json
import re
import shutil
from pathlib import Path

IMAGE_EXTS = {'.png', '.gif', '.jpg', '.jpeg', '.bmp', '.webp', '.img', '.vpe'}
AUDIO_EXTS = {'.mid', '.midi', '.wav', '.mp3'}
ANIM_EXTS = {'.ani', '.vpea', '.jmp', '.jop'}
MAP_EXTS = {'.map', '.str', '.wad'}

_RULES = (
    ('background', re.compile(r'^(bg|back|scene|mapbg|sky|cloud|water|sea|ground|gro|grass|road|floor)', re.I)),
    ('character', re.compile(r'^(hero|man|player|act_|role|char|chara)', re.I)),
    ('enemy', re.compile(r'^(e\d|enemy|gw|ghost|bird|mob|monster)', re.I)),
    ('boss', re.compile(r'^boss', re.I)),
    ('effect', re.compile(r'^(fx|blast|fire|boom|baozha|jiguang|spark|star|blood|hit|eff)', re.I)),
    ('item', re.compile(r'^(item|daoju|goods|coin|weapon|armor|seed|plant)', re.I)),
    ('ui', re.compile(r'^(ui|btn|button|panel|menu|icon|logo|font|text|arrow|head|hand|score|select)', re.I)),
)

_CATEGORY_DIR = {
    'background': 'assets/scenes/backgrounds',
    'character': 'assets/scenes/characters',
    'enemy': 'assets/scenes/enemies',
    'boss': 'assets/scenes/bosses',
    'effect': 'assets/scenes/effects',
    'item': 'assets/scenes/items',
    'ui': 'assets/ui',
    'audio': 'assets/audio',
    'map': 'assets/map/legacy',
    'animation': 'assets/legacy/animations',
    'misc': 'assets/legacy/misc',
}

def classify_legacy_asset(path: Path) -> str:
    ext = path.suffix.lower()
    if ext in AUDIO_EXTS:
        return 'audio'
    if ext in ANIM_EXTS:
        return 'animation'
    if ext in MAP_EXTS:
        return 'map'
    stem = path.stem.lower()
    for category, pattern in _RULES:
        if pattern.search(stem):
            return category
    return 'misc'

def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(65536), b''):
            h.update(chunk)
    return h.hexdigest()

def _unique_target(path: Path, source: Path) -> Path:
    if not path.exists():
        return path
    try:
        if path.stat().st_size == source.stat().st_size and _sha256(path) == _sha256(source):
            return path
    except OSError:
        pass
    index = 2
    while True:
        candidate = path.with_name(f'{path.stem}_{index}{path.suffix}')
        if not candidate.exists():
            return candidate
        index += 1

def scan_legacy_res(source_dir: str | Path) -> list[dict]:
    source = Path(source_dir).resolve()
    if not source.is_dir():
        raise OSError(f'Không tìm thấy thư mục resource: {source}')
    files = sorted((p for p in source.rglob('*') if p.is_file()), key=lambda p: p.as_posix().lower())
    images_by_stem: dict[str, Path] = {}
    for path in files:
        if path.suffix.lower() in IMAGE_EXTS:
            images_by_stem.setdefault(path.stem.lower(), path)
    result = []
    for path in files:
        category = classify_legacy_asset(path)
        pair = images_by_stem.get(path.stem.lower()) if path.suffix.lower() in ANIM_EXTS else None
        result.append({
            'source': path,
            'relative_source': path.relative_to(source).as_posix(),
            'category': category,
            'paired_image': pair,
        })
    return result

def import_legacy_res(source_dir: str | Path, project_root: str | Path) -> dict:
    source = Path(source_dir).resolve()
    project = Path(project_root).resolve()
    plan = scan_legacy_res(source)
    image_targets: dict[str, Path] = {}
    imported: list[dict] = []

    # Images/data first, so binary animation descriptors can follow the paired sprite.
    for item in sorted(plan, key=lambda x: x['category'] == 'animation'):
        src: Path = item['source']
        category = item['category']
        target_dir = project / _CATEGORY_DIR[category]
        if category == 'animation' and item['paired_image'] is not None:
            paired = image_targets.get(item['paired_image'].stem.lower())
            if paired is not None:
                target_dir = paired.parent
        target_dir.mkdir(parents=True, exist_ok=True)
        target = _unique_target(target_dir / src.name, src)
        if not target.exists() or _sha256(target) != _sha256(src):
            shutil.copy2(src, target)
        if src.suffix.lower() in IMAGE_EXTS:
            image_targets.setdefault(src.stem.lower(), target)
        imported.append({
            'source': item['relative_source'],
            'category': category,
            'target': target.relative_to(project).as_posix(),
            'paired_asset': None,
            'sha256': _sha256(target),
        })

    target_by_name = {Path(row['target']).stem.lower(): row['target'] for row in imported if Path(row['target']).suffix.lower() in IMAGE_EXTS}
    for row in imported:
        if Path(row['target']).suffix.lower() in ANIM_EXTS:
            row['paired_asset'] = target_by_name.get(Path(row['target']).stem.lower())

    counts: dict[str, int] = {}
    for row in imported:
        counts[row['category']] = counts.get(row['category'], 0) + 1
    catalog = {
        'format': 'vxpe-legacy-assets-v1',
        'source_name': source.name,
        'counts': counts,
        'assets': imported,
    }
    catalog_dir = project / 'assets' / 'legacy'
    catalog_dir.mkdir(parents=True, exist_ok=True)
    catalog_path = catalog_dir / 'legacy_assets.catalog.json'
    catalog_path.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    catalog['catalog_path'] = catalog_path
    return catalog

LEGACY_CATEGORIES = (
    "background",
    "character",
    "enemy",
    "boss",
    "effect",
    "item",
    "ui",
    "animation",
    "audio",
    "map",
    "misc",
)


def legacy_catalog_path(project_root: str | Path) -> Path:
    return Path(project_root).resolve() / "assets" / "legacy" / "legacy_assets.catalog.json"


def load_legacy_catalog(project_root: str | Path) -> dict:
    path = legacy_catalog_path(project_root)
    if not path.is_file():
        return {
            "format": "vxpe-legacy-assets-v1",
            "source_name": "",
            "counts": {},
            "assets": [],
            "catalog_path": path,
        }
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Catalog legacy không hợp lệ: {path}")
    assets = payload.get("assets")
    if not isinstance(assets, list):
        raise ValueError(f"Catalog legacy thiếu assets[]: {path}")
    payload["catalog_path"] = path
    return payload


def save_legacy_catalog(project_root: str | Path, catalog: dict) -> Path:
    path = legacy_catalog_path(project_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = dict(catalog)
    payload.pop("catalog_path", None)
    assets = payload.get("assets")
    if not isinstance(assets, list):
        raise ValueError("Catalog legacy thiếu assets[]")
    counts: dict[str, int] = {}
    for row in assets:
        if not isinstance(row, dict):
            continue
        category = str(row.get("category") or "misc")
        counts[category] = counts.get(category, 0) + 1
    payload["counts"] = counts
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    catalog["counts"] = counts
    catalog["catalog_path"] = path
    return path


def find_legacy_asset(catalog: dict, target: str) -> dict | None:
    normalized = str(target or "").replace("\\", "/").strip("/")
    for row in catalog.get("assets", []):
        if isinstance(row, dict) and str(row.get("target") or "").replace("\\", "/").strip("/") == normalized:
            return row
    return None


def resolve_legacy_preview(project_root: str | Path, row: dict) -> Path | None:
    project = Path(project_root).resolve()
    target = str(row.get("target") or "").replace("\\", "/").strip("/")
    paired = str(row.get("paired_asset") or "").replace("\\", "/").strip("/")
    candidates = []
    if Path(target).suffix.lower() in ANIM_EXTS and paired:
        candidates.append(paired)
    candidates.append(target)
    if paired and paired not in candidates:
        candidates.append(paired)
    for relative in candidates:
        if not relative:
            continue
        candidate = (project / relative).resolve()
        try:
            candidate.relative_to(project)
        except ValueError:
            continue
        if candidate.is_file() and candidate.suffix.lower() in IMAGE_EXTS:
            return candidate
    return None


def update_legacy_asset_metadata(
    project_root: str | Path,
    target: str,
    *,
    category: str | None = None,
    display_name: str | None = None,
    role: str | None = None,
    tags: list[str] | tuple[str, ...] | None = None,
    notes: str | None = None,
) -> dict:
    catalog = load_legacy_catalog(project_root)
    row = find_legacy_asset(catalog, target)
    if row is None:
        raise KeyError(f"Không tìm thấy legacy asset: {target}")
    if category is not None:
        clean_category = str(category).strip().lower() or "misc"
        if clean_category not in LEGACY_CATEGORIES:
            raise ValueError(f"Category legacy không hợp lệ: {clean_category}")
        row["category"] = clean_category
    metadata = row.get("metadata")
    if not isinstance(metadata, dict):
        metadata = {}
        row["metadata"] = metadata
    if display_name is not None:
        metadata["display_name"] = str(display_name).strip()
    if role is not None:
        metadata["role"] = str(role).strip()
    if tags is not None:
        clean_tags = []
        seen = set()
        for value in tags:
            tag = str(value).strip()
            key = tag.casefold()
            if tag and key not in seen:
                seen.add(key)
                clean_tags.append(tag)
        metadata["tags"] = clean_tags
    if notes is not None:
        metadata["notes"] = str(notes).strip()
    save_legacy_catalog(project_root, catalog)
    return row
