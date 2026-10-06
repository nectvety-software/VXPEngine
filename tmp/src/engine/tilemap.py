"""Tilemap document model: layers of tile indices with paint operations."""

from __future__ import annotations

import json
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path

EMPTY = -1


@dataclass
class Layer:
    name: str
    tile_w: int
    tile_h: int
    width: int
    height: int
    cells: list[int] = field(default_factory=list)
    visible: bool = True
    opacity: float = 1.0
    locked: bool = False

    def __post_init__(self) -> None:
        if not self.cells:
            self.cells = [EMPTY] * (self.width * self.height)

    @property
    def used(self) -> int:
        return sum(1 for c in self.cells if c != EMPTY)

    def get(self, x: int, y: int) -> int:
        return self.cells[y * self.width + x] if self.inside(x, y) else EMPTY

    def set(self, x: int, y: int, tile: int) -> bool:
        if not self.inside(x, y) or self.cells[y * self.width + x] == tile:
            return False
        self.cells[y * self.width + x] = tile
        return True

    def inside(self, x: int, y: int) -> bool:
        return 0 <= x < self.width and 0 <= y < self.height

    def tile_positions(self) -> list[tuple[int, int, int]]:
        return [(i % self.width, i // self.width, t)
                for i, t in enumerate(self.cells) if t != EMPTY]

    def to_dict(self) -> dict:
        return {"name": self.name, "visible": self.visible, "opacity": self.opacity,
                "locked": self.locked, "cells": self.cells}


@dataclass
class TileMap:
    width: int = 40
    height: int = 24
    tile_w: int = 32
    tile_h: int = 32
    layers: list[Layer] = field(default_factory=list)
    active: int = 0

    def __post_init__(self) -> None:
        if not self.layers:
            self.layers = [Layer("Ground", self.tile_w, self.tile_h, self.width, self.height)]

    # ---------------------------------------------------------------- layers

    @property
    def pixel_size(self) -> tuple[int, int]:
        return self.width * self.tile_w, self.height * self.tile_h

    def layer(self, index: int) -> Layer:
        return self.layers[index]

    @property
    def active_layer(self) -> Layer:
        return self.layers[self.active]

    def add_layer(self, name: str | None = None, above: bool = True) -> int:
        i = len(self.layers) if above else 0
        name = name or f"Layer {len(self.layers) + 1}"
        self.layers.insert(i, Layer(name, self.tile_w, self.tile_h, self.width, self.height))
        self.active = i
        return i

    def remove_layer(self, index: int) -> bool:
        if len(self.layers) <= 1 or not 0 <= index < len(self.layers):
            return False
        del self.layers[index]
        self.active = max(0, min(self.active, len(self.layers) - 1))
        return True

    def rename_layer(self, index: int, name: str) -> None:
        self.layers[index].name = name

    def move_layer(self, index: int, delta: int) -> int:
        j = max(0, min(len(self.layers) - 1, index + delta))
        if j == index:
            return index
        self.layers.insert(j, self.layers.pop(index))
        self.active = j
        return j

    def clear_layer(self, index: int) -> list[tuple[int, int, int]]:
        layer = self.layers[index]
        return self._replace(layer, [(x, y) for x, y, _ in layer.tile_positions()], EMPTY)

    # ---------------------------------------------------------------- painting

    def _replace(self, layer: Layer, coords, tile: int) -> list[tuple[int, int, int]]:
        """Apply a write and return the edits made, as (layer_index, cell_index, old, new)."""
        li = self.layers.index(layer)
        edits = []
        for x, y in coords:
            old = layer.get(x, y)
            if old == tile or not layer.inside(x, y):
                continue
            layer.set(x, y, tile)
            edits.append((li, y * layer.width + x, old, tile))
        return edits

    def paint(self, x: int, y: int, tile: int, layer: Layer | None = None) -> list:
        layer = layer or self.active_layer
        return self._replace(layer, [(x, y)], tile)

    def paint_line(self, x0: int, y0: int, x1: int, y1: int, tile: int,
                   layer: Layer | None = None) -> list:
        layer = layer or self.active_layer
        dx, dy = abs(x1 - x0), -abs(y1 - y0)
        sx, sy = (1 if x0 < x1 else -1), (1 if y0 < y1 else -1)
        err = dx + dy
        coords, guard = [], 0
        while True:
            coords.append((x0, y0))
            if (x0, y0) == (x1, y1) or guard > 8192:
                break
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                x0 += sx
            if e2 <= dx:
                err += dx
                y0 += sy
            guard += 1
        return self._replace(layer, coords, tile)

    def paint_rect(self, x0: int, y0: int, x1: int, y1: int, tile: int, filled: bool = True,
                   layer: Layer | None = None) -> list:
        layer = layer or self.active_layer
        xa, xb = sorted((x0, x1))
        ya, yb = sorted((y0, y1))
        coords = []
        for y in range(ya, yb + 1):
            for x in range(xa, xb + 1):
                if filled or x in (xa, xb) or y in (ya, yb):
                    coords.append((x, y))
        return self._replace(layer, coords, tile)

    def flood_fill(self, x: int, y: int, tile: int, layer: Layer | None = None) -> list:
        layer = layer or self.active_layer
        target = layer.get(x, y)
        if target == tile:
            return []
        seen, queue, coords = {(x, y)}, deque([(x, y)]), []
        while queue:
            cx, cy = queue.popleft()
            coords.append((cx, cy))
            for nx, ny in ((cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)):
                if (nx, ny) in seen or not layer.inside(nx, ny):
                    continue
                if layer.get(nx, ny) == target:
                    seen.add((nx, ny))
                    queue.append((nx, ny))
        return self._replace(layer, coords, tile)

    def erase(self, x: int, y: int, layer: Layer | None = None) -> list:
        return self.paint(x, y, EMPTY, layer)

    # ---------------------------------------------------------------- stats

    def used_tiles(self) -> dict[int, int]:
        counts: dict[int, int] = {}
        for layer in self.layers:
            for t in layer.cells:
                if t != EMPTY:
                    counts[t] = counts.get(t, 0) + 1
        return counts

    # ---------------------------------------------------------------- io

    def to_dict(self) -> dict:
        return {"width": self.width, "height": self.height, "tile_w": self.tile_w,
                "tile_h": self.tile_h, "active": self.active,
                "layers": [l.to_dict() for l in self.layers]}

    @classmethod
    def from_dict(cls, data: dict) -> "TileMap":
        layers = [Layer(l["name"], data["tile_w"], data["tile_h"], data["width"],
                        data["height"], list(l["cells"]), l.get("visible", True),
                        float(l.get("opacity", 1.0)), l.get("locked", False))
                  for l in data["layers"]]
        return cls(data["width"], data["height"], data["tile_w"], data["tile_h"], layers,
                   min(data.get("active", 0), len(layers) - 1))

    def save(self, path: str | Path) -> Path:
        p = Path(path)
        p.write_text(json.dumps(self.to_dict(), indent=1), encoding="utf-8")
        return p

    @classmethod
    def load(cls, path: str | Path) -> "TileMap":
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))
