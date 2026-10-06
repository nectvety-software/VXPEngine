"""Project document: the atlas + tilemap pair, its file format, and PNG export."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image

from .tilemap import EMPTY, TileMap
from .tilesheet import TileSheet

FORMAT = "terra.project"
VERSION = 1


@dataclass
class Project:
    name: str = "untitled"
    path: Path | None = None
    sheet: TileSheet | None = field(default=None, repr=False)
    map: TileMap = field(default_factory=TileMap)
    background: tuple[int, int, int, int] = (18, 20, 24, 255)
    dirty: bool = False

    # ---------------------------------------------------------------- setup

    @classmethod
    def new(cls, sheet_path: str | Path | None = None, width: int = 40, height: int = 24,
            cell: int | str = "auto") -> "Project":
        project = cls(name=Path(sheet_path).stem if sheet_path else "untitled",
                      map=TileMap(width, height, 32, 32))
        if sheet_path:
            project.attach_sheet(sheet_path, cell)
        return project

    def attach_sheet(self, path: str | Path, cell: int | str = "auto") -> TileSheet:
        sheet = TileSheet.open(path, cell)
        self.sheet = sheet
        self.map.tile_w, self.map.tile_h = sheet.cell
        for layer in self.map.layers:
            layer.tile_w, layer.tile_h = sheet.cell
        self.mark_dirty()
        return sheet

    def mark_dirty(self, value: bool = True) -> None:
        self.dirty = value

    # ---------------------------------------------------------------- io

    def to_dict(self) -> dict:
        return {"format": FORMAT, "version": VERSION, "name": self.name,
                "sheet": self._sheet_ref(),
                "sheet_cell": list(self.sheet.cell) if self.sheet else None,
                "background": list(self.background), "map": self.map.to_dict()}

    def _sheet_ref(self) -> str | None:
        if not self.sheet:
            return None
        sheet, base = self.sheet.path, self.path.parent if self.path else Path(".")
        try:
            return str(sheet.resolve().relative_to(base.resolve()))
        except ValueError:
            return str(sheet.resolve())

    def save(self, path: str | Path | None = None) -> Path:
        target = Path(path or self.path)
        if target.suffix.lower() != ".json":
            target = target.with_suffix(".terra.json")
        self.path = target
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(self.to_dict(), indent=1), encoding="utf-8")
        self.name = target.stem
        self.mark_dirty(False)
        return target

    @classmethod
    def load(cls, path: str | Path) -> "Project":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        if data.get("format") != FORMAT:
            raise ValueError(f"not a {FORMAT} file")
        project = cls(name=data.get("name", "project"), map=TileMap.from_dict(data["map"]),
                      background=tuple(data.get("background", (18, 20, 24, 255))))
        project.path = Path(path)
        ref = data.get("sheet")
        resolved = project._resolve_sheet(ref) if ref else None
        if resolved:
            project.sheet = TileSheet.open(resolved, tuple(data.get("sheet_cell") or "auto"))
        return project

    def _resolve_sheet(self, ref: str) -> Path | None:
        base = self.path.parent if self.path else Path(".")
        candidates = [base / ref, Path(ref), base / Path(ref).name, Path(ref).name]
        for cand in candidates:
            if cand.is_file():
                return cand
        return None

    # ---------------------------------------------------------------- output

    def render(self, scale: int = 1, transparent: bool = False) -> Image.Image:
        """Rasterise the map with PIL — the headless counterpart of the UI painter."""
        if not self.sheet:
            raise RuntimeError("no tilesheet attached")
        w, h = self.map.pixel_size
        out = Image.new("RGBA", (w * scale, h * scale),
                        self.background if not transparent else (0, 0, 0, 0))
        cache: dict[int, Image.Image] = {}
        for layer in self.map.layers:
            if not layer.visible or layer.opacity <= 0.001:
                continue
            sheet = Image.new("RGBA", out.size, (0, 0, 0, 0))
            for x, y, tile in layer.tile_positions():
                if not self.sheet.is_solid(tile):
                    continue
                img = cache.get(tile)
                if img is None:
                    img = self.sheet.crop(tile)
                    if scale != 1:
                        img = img.resize((img.width * scale, img.height * scale), Image.NEAREST)
                    cache[tile] = img
                sheet.alpha_composite(img, (x * self.map.tile_w * scale,
                                            y * self.map.tile_h * scale))
            if layer.opacity < 1.0:
                alpha = sheet.getchannel("A").point(lambda v: int(v * layer.opacity))
                sheet.putalpha(alpha)
            out.alpha_composite(sheet)
        return out

    def export_png(self, path: str | Path, scale: int = 1,
                   transparent: bool = False) -> Path:
        target = Path(path)
        self.render(scale, transparent).convert("RGBA").save(target)
        return target

    # ---------------------------------------------------------------- info

    def stats(self) -> dict:
        placed = sum(l.used for l in self.map.layers)
        used = self.map.used_tiles()
        return {
            "map": f"{self.map.width}x{self.map.height}",
            "pixels": "{}x{}".format(*self.map.pixel_size),
            "tile_size": f"{self.map.tile_w}x{self.map.tile_h}",
            "layers": len(self.map.layers),
            "placed": placed,
            "distinct_tiles": len(used),
            "sheet_tiles": self.sheet.count if self.sheet else 0,
            "sheet_solid": len(self.sheet.solid) if self.sheet else 0,
        }
