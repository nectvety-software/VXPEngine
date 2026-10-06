"""2D camera: world <-> screen mapping, zoom-to-cursor, visible tile range."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Camera2D:
    x: float = 0.0            # world position of the viewport centre
    y: float = 0.0
    zoom: float = 1.0
    viewport: tuple[int, int] = (0, 0)
    min_zoom: float = field(default=0.125)
    max_zoom: float = 12.0

    # ---------------------------------------------------------------- mapping

    def screen_to_world(self, sx: float, sy: float) -> tuple[float, float]:
        vw, vh = self.viewport
        return self.x + (sx - vw / 2) / self.zoom, self.y + (sy - vh / 2) / self.zoom

    def world_to_screen(self, wx: float, wy: float) -> tuple[float, float]:
        vw, vh = self.viewport
        return (wx - self.x) * self.zoom + vw / 2, (wy - self.y) * self.zoom + vh / 2

    def visible_rect(self) -> tuple[float, float, float, float]:
        vw, vh = self.viewport
        half_w, half_h = vw / 2 / self.zoom, vh / 2 / self.zoom
        return self.x - half_w, self.y - half_h, self.x + half_w, self.y + half_h

    def visible_tiles(self, width: int, height: int, tile_w: int, tile_h: int,
                      margin: int = 1) -> range | tuple[range, range]:
        x0, y0, x1, y1 = self.visible_rect()
        c0 = max(0, int(x0 // tile_w) - margin)
        c1 = min(width - 1, int(x1 // tile_w) + margin)
        r0 = max(0, int(y0 // tile_h) - margin)
        r1 = min(height - 1, int(y1 // tile_h) + margin)
        if c1 < c0 or r1 < r0:
            return range(0), range(0)
        return range(c0, c1 + 1), range(r0, r1 + 1)

    # ---------------------------------------------------------------- motion

    def pan_pixels(self, dx: float, dy: float) -> None:
        self.x -= dx / self.zoom
        self.y -= dy / self.zoom

    def zoom_at(self, factor: float, sx: float | None = None, sy: float | None = None) -> None:
        target = max(self.min_zoom, min(self.max_zoom, self.zoom * factor))
        if target == self.zoom:
            return
        vw, vh = self.viewport
        sx = vw / 2 if sx is None else sx
        sy = vh / 2 if sy is None else sy
        wx, wy = self.screen_to_world(sx, sy)
        self.zoom = target
        self.x = wx - (sx - vw / 2) / self.zoom
        self.y = wy - (sy - vh / 2) / self.zoom

    def fit(self, world_w: int, world_h: int, padding: int = 24) -> None:
        vw, vh = self.viewport
        if not (vw and vh and world_w and world_h):
            self.x, self.y = world_w / 2, world_h / 2
            return
        self.zoom = max(self.min_zoom, min((vw - padding) / world_w, (vh - padding) / world_h,
                                           self.max_zoom))
        self.x, self.y = world_w / 2, world_h / 2

    def center_on_tile(self, col: int, row: int, tile_w: int, tile_h: int) -> None:
        self.x, self.y = (col + 0.5) * tile_w, (row + 0.5) * tile_h

    def reset(self) -> None:
        self.zoom = 1.0
