"""Backend-agnostic draw batching: turn a tilemap + camera into screen-space quads."""

from __future__ import annotations

from dataclasses import dataclass, field

from .tilemap import EMPTY, TileMap
from .camera import Camera2D


@dataclass
class Placement:
    tile: int
    x: float
    y: float
    w: float
    h: float


@dataclass
class DrawBatch:
    layer_index: int
    name: str
    opacity: float
    placements: list[Placement] = field(default_factory=list)


def build_batches(tilemap: TileMap, camera: Camera2D, cull: bool = True) -> list[DrawBatch]:
    """Bottom layer first. Coordinates are in screen pixels, ready for QPainter."""
    vw, vh = camera.viewport
    if cull and (vw <= 0 or vh <= 0):
        return []
    cols, rows = camera.visible_tiles(tilemap.width, tilemap.height,
                                       tilemap.tile_w, tilemap.tile_h) if cull else (
        range(tilemap.width), range(tilemap.height))
    tw, th = tilemap.tile_w * camera.zoom, tilemap.tile_h * camera.zoom
    batches: list[DrawBatch] = []
    for li, layer in enumerate(tilemap.layers):
        batch = DrawBatch(li, layer.name, layer.opacity)
        if layer.visible and layer.opacity > 0.001:
            for y in rows:
                for x in cols:
                    tile = layer.get(x, y)
                    if tile == EMPTY:
                        continue
                    sx, sy = camera.world_to_screen(x * tilemap.tile_w, y * tilemap.tile_h)
                    batch.placements.append(Placement(tile, sx, sy, tw, th))
        batches.append(batch)
    return batches


def draw_stats(batches: list[DrawBatch]) -> dict:
    return {
        "layers": sum(1 for b in batches if b.placements),
        "quads": sum(len(b.placements) for b in batches),
    }
