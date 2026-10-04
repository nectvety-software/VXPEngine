"""Shared file-system helpers for VXPEngine."""
from __future__ import annotations

from pathlib import Path


def unique_destination(path: str | Path) -> Path:
    """Return *path* or a sibling with ``_N`` when the path already exists."""
    candidate = Path(path)
    if not candidate.exists():
        return candidate
    index = 1
    while True:
        numbered = candidate.with_name(f"{candidate.stem}_{index}{candidate.suffix}")
        if not numbered.exists():
            return numbered
        index += 1
