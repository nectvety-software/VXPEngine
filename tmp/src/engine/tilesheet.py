"""Tile atlas: slicing, manifest interchange, per-cell access."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from PIL import Image

CELL_CANDIDATES = (8, 16, 24, 32, 48, 64)
BLACK_MAX = 30
VISIBLE_MIN = 0.01


@dataclass(frozen=True)
class TileRef:
    index: int
    col: int
    row: int
    x: int
    y: int
    w: int
    h: int
    blank: bool = False

    @property
    def rect(self) -> tuple[int, int, int, int]:
        return self.x, self.y, self.x + self.w, self.y + self.h


def _grid_scores(image: Image.Image) -> dict[int, float]:
    """Edge energy sitting exactly on each candidate grid, normalised.

    `gx[i]` is the difference between columns i and i+1, so the seam in front of
    grid line x=k lives at index k-1. Sampling only k misses it by one pixel on
    atlases whose tiles are full-bleed, so both sides of the seam are averaged.
    """
    lum = np.asarray(image.convert("RGB")).astype(np.int32).sum(2)
    h, w = lum.shape
    gx = np.abs(np.diff(lum, axis=1)).mean(0)
    gy = np.abs(np.diff(lum, axis=0)).mean(1)
    out: dict[int, float] = {}
    for c in CELL_CANDIDATES:
        if w % c or h % c:
            continue
        xs = np.clip(np.arange(c - 1, w - 1, c)[:, None] + (0, 1), 0, gx.size - 1)
        ys = np.clip(np.arange(c - 1, h - 1, c)[:, None] + (0, 1), 0, gy.size - 1)
        ex, ey = gx[xs].mean() / gx.mean(), gy[ys].mean() / gy.mean()
        out[c] = round(float((ex + ey) / 2), 4)
    return out


def detect_cell(image: Image.Image) -> int:
    """Smallest candidate that explains nearly all the grid's edge energy.

    Coarse grids are a subset of fine ones, so a 64px guess always scores at
    least as well as the true 32px grid; the tie-break toward the finer cell is
    what stops the detector from doubling up.
    """
    scores = _grid_scores(image)
    if not scores:
        return 32
    best = max(scores.values())
    return min(c for c, s in scores.items() if s >= 0.85 * best)


@dataclass
class TileSheet:
    """A raster atlas plus its logical grid. `image` is the source of truth for pixels."""

    path: Path
    image: Image.Image = field(repr=False)
    cell: tuple[int, int] = (32, 32)
    tiles: list[TileRef] = field(default_factory=list, repr=False)
    cell_mode: str = "manual"
    scores: dict[int, float] = field(default_factory=dict, repr=False)

    def __post_init__(self) -> None:
        if not self.tiles:
            self._build_tiles()

    # ---------------------------------------------------------------- build

    def _build_tiles(self) -> None:
        arr = np.asarray(self.image.convert("RGBA"))
        w, h = self.image.size
        cw, ch = self.cell
        cols, rows = w // cw, h // ch
        out: list[TileRef] = []
        for r in range(rows):
            for c in range(cols):
                x, y = c * cw, r * ch
                crop = arr[y:y + ch, x:x + cw]
                vis = ((crop[:, :, 3] > 8) & (crop[:, :, :3].max(2) > BLACK_MAX)).mean()
                out.append(TileRef(r * cols + c, c, r, x, y, cw, ch, bool(vis < VISIBLE_MIN)))
        self.tiles = out

    @classmethod
    def open(cls, path: str | Path, cell: int | str | tuple[int, int] | None = "auto",
             cell_h: int | None = None) -> "TileSheet":
        p = Path(path)
        image = Image.open(p).convert("RGBA")
        scores = _grid_scores(image)
        if cell in (None, "auto"):
            size = detect_cell(image)
            mode = f"auto (score {scores.get(size, 0):.2f})"
            cw = ch = size
        elif isinstance(cell, (tuple, list)):
            cw, ch, mode = int(cell[0]), int(cell[1]), "manual"
        elif isinstance(cell, str) and "x" in cell.lower():
            a, b = cell.lower().split("x")
            cw, ch, mode = int(a), int(b), "manual"
        else:
            cw = int(cell)  # type: ignore[arg-type]
            ch = cell_h or cw
            mode = "manual"
        return cls(path=p, image=image, cell=(cw, ch), cell_mode=mode, scores=scores)

    @classmethod
    def from_manifest(cls, manifest: str | Path) -> "TileSheet":
        mpath = Path(manifest)
        data = json.loads(mpath.read_text(encoding="utf-8"))
        source = (mpath.parent / data["source"]).resolve()
        sheet = cls.open(source, cell=tuple(data["cell"]))
        sheet.cell_mode = data.get("cell_mode", sheet.cell_mode)
        return sheet

    # ---------------------------------------------------------------- access

    @property
    def size(self) -> tuple[int, int]:
        return self.image.size

    @property
    def grid(self) -> tuple[int, int]:
        w, h = self.image.size
        cw, ch = self.cell
        return w // cw, h // ch

    @property
    def count(self) -> int:
        return len(self.tiles)

    @property
    def solid(self) -> list[TileRef]:
        return [t for t in self.tiles if not t.blank]

    def tile(self, index: int) -> TileRef:
        return self.tiles[index]

    def is_solid(self, index: int) -> bool:
        return 0 <= index < len(self.tiles) and not self.tiles[index].blank

    def crop(self, index: int) -> Image.Image:
        t = self.tiles[index]
        return self.image.crop(t.rect)

    def digest(self, index: int) -> str:
        return hashlib.md5(self.crop(index).tobytes()).hexdigest()

    def unique_count(self) -> int:
        return len({self.digest(t.index) for t in self.solid})

    # ---------------------------------------------------------------- output

    def to_manifest(self) -> dict:
        w, h = self.image.size
        cols, rows = self.grid
        return {
            "source": self.path.name,
            "source_size": [w, h],
            "cell": [self.cell[0], self.cell[1]],
            "cell_mode": self.cell_mode,
            "grid": [cols, rows],
            "pad": 0,
            "count": len(self.solid),
            "blank": len(self.tiles) - len(self.solid),
            "tiles": [
                {"index": t.index, "col": t.col, "row": t.row, "x": t.x, "y": t.y,
                 "w": t.w, "h": t.h, "file": None if t.blank else f"cells/tile_{t.index:03d}.png",
                 "blank": t.blank}
                for t in self.tiles
            ],
        }

    def write(self, out_dir: str | Path, skip_blank: bool = True) -> Path:
        out = Path(out_dir)
        (out / "cells").mkdir(parents=True, exist_ok=True)
        for t in self.tiles:
            if t.blank and skip_blank:
                continue
            self.crop(t.index).save(out / "cells" / f"tile_{t.index:03d}.png")
        (out / "manifest.json").write_text(json.dumps(self.to_manifest(), indent=1),
                                           encoding="utf-8")
        return out
