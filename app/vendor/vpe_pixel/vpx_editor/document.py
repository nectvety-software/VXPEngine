"""Document model: RGB565 canvas buffer + undo/redo transaction history."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, List, Optional, Sequence, Tuple

from .vpe import MAX_DIM, decode_vpe, encode_vpe, VpeError
from .vpea import MAX_FRAMES, decode_vpea, encode_vpea

Pixel = int  # RGB565
Change = Tuple[int, int, Pixel, Pixel]  # x, y, old, new


@dataclass
class HistoryEntry:
    changes: List[Change]
    label: str = ""
    frame: int = 0

    def apply_reverse(self, set_pixel: Callable[[int, int, Pixel], None]) -> None:
        for x, y, old, _ in self.changes:
            set_pixel(x, y, old)

    def apply_forward(self, set_pixel: Callable[[int, int, Pixel], None]) -> None:
        for x, y, _, new in self.changes:
            set_pixel(x, y, new)


@dataclass
class Document:
    width: int
    height: int
    pixels: List[Pixel]
    name: str = "Untitled"
    path: Optional[str] = None
    dirty: bool = False
    undo_stack: List[HistoryEntry] = field(default_factory=list)
    redo_stack: List[HistoryEntry] = field(default_factory=list)
    max_history: int = 80
    # Animation: `pixels` always aliases frames[frame]; painting edits in place.
    frames: List[List[Pixel]] = field(default_factory=list)
    frame: int = 0
    delay_ms: int = 120
    loop: bool = True
    _stroke: Optional[dict] = field(default_factory=dict, repr=False)

    def __post_init__(self) -> None:
        if not self.frames:
            self.frames = [self.pixels]
        self.frame = max(0, min(self.frame, len(self.frames) - 1))
        self.pixels = self.frames[self.frame]

    # --- construction -------------------------------------------------
    @classmethod
    def blank(cls, width: int, height: int, fill: Pixel = 0xFFFF, name: str = "Untitled",
              frames: int = 1) -> "Document":
        w = max(1, min(int(width), MAX_DIM))
        h = max(1, min(int(height), MAX_DIM))
        n = max(1, min(int(frames), MAX_FRAMES))
        return cls(width=w, height=h,
                   frames=[[fill & 0xFFFF] * (w * h) for _ in range(n)],
                   pixels=[], name=name)

    @classmethod
    def from_pixels(cls, width: int, height: int, pixels: Sequence[Pixel], name: str = "Untitled",
                    path: Optional[str] = None) -> "Document":
        if len(pixels) != width * height:
            raise VpeError("pixel-count")
        return cls(width=width, height=height, pixels=list(pixels), name=name, path=path)

    @classmethod
    def from_vpe_bytes(cls, blob: bytes, name: str = "Untitled", path: Optional[str] = None) -> "Document":
        w, h, pixels = decode_vpe(blob)
        return cls.from_pixels(w, h, pixels, name=name, path=path)

    @classmethod
    def from_frames(cls, width: int, height: int, frames: Sequence[Sequence[Pixel]],
                    name: str = "Untitled", path: Optional[str] = None,
                    delay_ms: int = 120, loop: bool = True) -> "Document":
        if not frames or len(frames) > MAX_FRAMES:
            raise VpeError("vpea-frames")
        for px in frames:
            if len(px) != width * height:
                raise VpeError("pixel-count")
        return cls(width=width, height=height, pixels=[], name=name, path=path,
                   frames=[list(px) for px in frames], delay_ms=delay_ms, loop=loop)

    @classmethod
    def from_vpea_bytes(cls, blob: bytes, name: str = "Untitled",
                        path: Optional[str] = None) -> "Document":
        w, h, frames, delay, loop = decode_vpea(blob)
        return cls.from_frames(w, h, frames, name=name, path=path,
                               delay_ms=delay, loop=loop)

    # --- frames --------------------------------------------------------
    def frame_count(self) -> int:
        return len(self.frames)

    def is_animated(self) -> bool:
        return len(self.frames) > 1

    def goto_frame(self, index: int) -> bool:
        index = max(0, min(int(index), len(self.frames) - 1))
        if index == self.frame and self.pixels is self.frames[index]:
            return False
        self.frame = index
        self.pixels = self.frames[index]
        return True

    def add_frame(self, index: Optional[int] = None, fill: Pixel = 0xFFFF,
                  copy_from: Optional[int] = None) -> int:
        """Insert a frame after `index` (default: after the current one)."""
        if len(self.frames) >= MAX_FRAMES:
            raise VpeError("vpea-frames")
        blank = list(self.frames[copy_from]) if copy_from is not None \
            else [fill & 0xFFFF] * (self.width * self.height)
        at = len(self.frames) if index is None else min(index + 1, len(self.frames))
        self.frames.insert(at, blank)
        self.goto_frame(at)
        self.dirty = True
        return at

    def duplicate_frame(self, index: Optional[int] = None) -> int:
        return self.add_frame(index if index is not None else self.frame,
                              copy_from=self.frame if index is None else index)

    def delete_frame(self, index: Optional[int] = None) -> bool:
        """Remove a frame; the last remaining frame cannot be deleted."""
        index = self.frame if index is None else int(index)
        if len(self.frames) <= 1 or not 0 <= index < len(self.frames):
            return False
        self.frames.pop(index)
        self.goto_frame(min(index, len(self.frames) - 1))
        self.dirty = True
        return True

    def move_frame(self, src: int, dst: int) -> bool:
        n = len(self.frames)
        if not 0 <= src < n:
            return False
        dst = max(0, min(int(dst), n - 1))
        if src == dst:
            return False
        current = self.frames[self.frame]
        frame = self.frames.pop(src)
        self.frames.insert(dst, frame)
        # Identity, not equality: duplicated frames compare equal.
        self.frame = next(i for i, f in enumerate(self.frames) if f is current)
        self.pixels = current
        self.dirty = True
        return True

    def clear_frame(self, index: Optional[int] = None, fill: Pixel = 0xFFFF) -> None:
        index = self.frame if index is None else int(index)
        self.goto_frame(max(0, min(index, len(self.frames) - 1)))
        self.begin_stroke("Clear")
        for y in range(self.height):
            for x in range(self.width):
                self.stroke_set(x, y, fill)
        self.end_stroke()

    def onion_frames(self, back: int = 1, forward: int = 1) -> List[Tuple[int, List[Pixel]]]:
        """Neighbouring frames as (offset, pixels), oldest first — for onion skin."""
        out: List[Tuple[int, List[Pixel]]] = []
        for delta in range(-max(0, back), max(0, forward) + 1):
            if delta == 0:
                continue
            i = self.frame + delta
            if 0 <= i < len(self.frames):
                out.append((delta, self.frames[i]))
        return out


    # --- pixel access ------------------------------------------------
    def get_pixel(self, x: int, y: int) -> Optional[Pixel]:
        if x < 0 or y < 0 or x >= self.width or y >= self.height:
            return None
        return self.pixels[y * self.width + x]

    def set_pixel(self, x: int, y: int, color: Pixel) -> bool:
        if x < 0 or y < 0 or x >= self.width or y >= self.height:
            return False
        idx = y * self.width + x
        color &= 0xFFFF
        if self.pixels[idx] == color:
            return False
        self.pixels[idx] = color
        self.dirty = True
        return True

    def set_pixel_raw(self, x: int, y: int, color: Pixel) -> None:
        """Set without dirty/history (used by undo engine)."""
        if 0 <= x < self.width and 0 <= y < self.height:
            self.pixels[y * self.width + x] = color & 0xFFFF

    # --- stroke / transaction ----------------------------------------
    def begin_stroke(self, label: str = "Stroke") -> None:
        self._stroke = {"label": label, "changes": {}, "active": True,
                        "frame": self.frame}

    def stroke_set(self, x: int, y: int, color: Pixel) -> bool:
        if not self._stroke or not self._stroke.get("active"):
            return self.set_pixel(x, y, color)
        old = self.get_pixel(x, y)
        if old is None or old == (color & 0xFFFF):
            return False
        key = (x, y)
        changes = self._stroke["changes"]
        if key not in changes:
            changes[key] = (x, y, old, color & 0xFFFF)
        else:
            x0, y0, old0, _ = changes[key]
            changes[key] = (x0, y0, old0, color & 0xFFFF)
        return self.set_pixel(x, y, color)

    def stroke_set_many(self, points: Sequence[Tuple[int, int, Pixel]]) -> int:
        n = 0
        for x, y, c in points:
            if self.stroke_set(x, y, c):
                n += 1
        return n

    def end_stroke(self) -> Optional[HistoryEntry]:
        if not self._stroke or not self._stroke.get("active"):
            self._stroke = None
            return None
        changes = list(self._stroke["changes"].values())
        label = self._stroke.get("label", "Stroke")
        frame = self._stroke.get("frame", self.frame)
        self._stroke = None
        if not changes:
            return None
        entry = HistoryEntry(changes=changes, label=label, frame=frame)
        self._push_history(entry)
        return entry

    def commit_changes(self, changes: Sequence[Change], label: str = "Edit") -> Optional[HistoryEntry]:
        """Apply a list of (x,y,old,new) and push one history entry."""
        real = []
        for x, y, old, new in changes:
            cur = self.get_pixel(x, y)
            if cur is None:
                continue
            real.append((x, y, old if old is not None else cur, new & 0xFFFF))
            self.set_pixel(x, y, new)
        if not real:
            return None
        entry = HistoryEntry(changes=real, label=label, frame=self.frame)
        self._push_history(entry)
        return entry

    def _push_history(self, entry: HistoryEntry) -> None:
        self.redo_stack.clear()
        self.undo_stack.append(entry)
        if len(self.undo_stack) > self.max_history:
            self.undo_stack.pop(0)

    # --- undo / redo -------------------------------------------------
    def can_undo(self) -> bool:
        return bool(self.undo_stack)

    def can_redo(self) -> bool:
        return bool(self.redo_stack)

    def undo(self) -> Optional[str]:
        if not self.undo_stack:
            return None
        entry = self.undo_stack.pop()
        self._jump_to(entry.frame)
        entry.apply_reverse(self.set_pixel_raw)
        self.redo_stack.append(entry)
        self.dirty = True
        return entry.label

    def redo(self) -> Optional[str]:
        if not self.redo_stack:
            return None
        entry = self.redo_stack.pop()
        self._jump_to(entry.frame)
        entry.apply_forward(self.set_pixel_raw)
        self.undo_stack.append(entry)
        self.dirty = True
        return entry.label

    def _jump_to(self, index: int) -> None:
        """Undo entries belong to the frame they were made on."""
        self.goto_frame(max(0, min(index, len(self.frames) - 1)))

    def clear_history(self) -> None:
        self.undo_stack.clear()
        self.redo_stack.clear()

    # --- tools -------------------------------------------------------
    def paint_brush(self, cx: int, cy: int, size: int, color: Pixel) -> int:
        size = max(1, min(int(size), 16))
        half = size // 2
        # Even sizes: anchor top-left like the Lua editor (cursor = top-left).
        if size % 2 == 0:
            x0, y0 = cx, cy
        else:
            x0, y0 = cx - half, cy - half
        n = 0
        for dy in range(size):
            for dx in range(size):
                if self.stroke_set(x0 + dx, y0 + dy, color):
                    n += 1
        return n

    def paint_line(self, x0: int, y0: int, x1: int, y1: int, size: int, color: Pixel) -> int:
        points = _bresenham(x0, y0, x1, y1)
        n = 0
        for x, y in points:
            n += self.paint_brush(x, y, size, color)
        return n

    def paint_rect(self, x0: int, y0: int, x1: int, y1: int, size: int, color: Pixel,
                   filled: bool = False) -> int:
        xa, xb = sorted((x0, x1))
        ya, yb = sorted((y0, y1))
        n = 0
        if filled:
            for y in range(ya, yb + 1):
                for x in range(xa, xb + 1):
                    if self.stroke_set(x, y, color):
                        n += 1
        else:
            for x in range(xa, xb + 1):
                n += self.paint_brush(x, ya, size, color)
                n += self.paint_brush(x, yb, size, color)
            for y in range(ya + 1, yb):
                n += self.paint_brush(xa, y, size, color)
                n += self.paint_brush(xb, y, size, color)
        return n

    def flood_fill(self, x: int, y: int, color: Pixel) -> int:
        target = self.get_pixel(x, y)
        color &= 0xFFFF
        if target is None or target == color:
            return 0
        w, h = self.width, self.height
        # Span-based flood fill (no recursion).
        stack = [(x, x, y, 1), (x, x, y - 1, -1)]
        n = 0
        while stack:
            x_l, x_r, yy, dy = stack.pop()
            if yy < 0 or yy >= h:
                continue
            row = yy * w
            xl = x_l
            while xl > 0 and self.pixels[row + xl - 1] == target:
                xl -= 1
            xr = x_r
            while xr < w - 1 and self.pixels[row + xr + 1] == target:
                xr += 1
            for xx in range(xl, xr + 1):
                if self.pixels[row + xx] == target:
                    if self.stroke_set(xx, yy, color):
                        n += 1
            for ny in (yy + dy, yy - dy):
                if ny < 0 or ny >= h:
                    continue
                nrow = ny * w
                xx = xl
                while xx <= xr:
                    span = False
                    while xx <= xr and self.pixels[nrow + xx] == target:
                        if not span:
                            x_start = xx
                            span = True
                        xx += 1
                    if span:
                        stack.append((x_start, xx - 1, ny, dy))
                    xx += 1
        return n

    def pick(self, x: int, y: int) -> Optional[Pixel]:
        return self.get_pixel(x, y)

    # --- serialize ---------------------------------------------------
    def to_vpe_bytes(self) -> bytes:
        return encode_vpe(self.width, self.height, self.pixels)

    def to_vpea_bytes(self) -> bytes:
        return encode_vpea(self.width, self.height, self.frames,
                           self.delay_ms, self.loop)

    def resize(self, width: int, height: int, fill: Pixel = 0xFFFF) -> None:
        w = max(1, min(int(width), MAX_DIM))
        h = max(1, min(int(height), MAX_DIM))
        if w == self.width and h == self.height:
            return
        resized: List[List[Pixel]] = []
        for frame in self.frames:
            new_pixels = [fill & 0xFFFF] * (w * h)
            for y in range(min(h, self.height)):
                for x in range(min(w, self.width)):
                    new_pixels[y * w + x] = frame[y * self.width + x]
            resized.append(new_pixels)
        self.width, self.height = w, h
        self.frames = resized
        self.pixels = self.frames[self.frame]
        self.dirty = True
        self.clear_history()


def _bresenham(x0: int, y0: int, x1: int, y1: int) -> List[Tuple[int, int]]:
    points: List[Tuple[int, int]] = []
    dx = abs(x1 - x0)
    dy = -abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx + dy
    x, y = x0, y0
    while True:
        points.append((x, y))
        if x == x1 and y == y1:
            break
        e2 = 2 * err
        if e2 >= dy:
            err += dy
            x += sx
        if e2 <= dx:
            err += dx
            y += sy
    return points
