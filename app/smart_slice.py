"""Deterministic, content-aware slicing helpers for 2D image assets.

The detector deliberately has no Qt or network dependency.  It groups opaque
pixel runs into connected components, then optionally merges nearby pieces.
This makes it suitable as the local fallback for an AI segmentation provider.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True, slots=True)
class SliceRegion:
    x: int
    y: int
    width: int
    height: int
    opaque_pixels: int = 0

    @property
    def right(self) -> int:
        return self.x + self.width - 1

    @property
    def bottom(self) -> int:
        return self.y + self.height - 1


def detect_content_regions(
    width: int,
    height: int,
    alpha_at: Callable[[int, int], int],
    *,
    alpha_threshold: int = 8,
    min_pixels: int = 8,
    merge_distance: int = 1,
    padding: int = 0,
) -> list[SliceRegion]:
    """Return stable, reading-order regions containing visible pixels.

    A run-length connected-component pass avoids a large per-pixel visited
    matrix. Nearby fragments (for example a detached shadow beneath a sprite)
    are merged only when their expanded bounds overlap.
    """
    width = max(0, int(width))
    height = max(0, int(height))
    threshold = max(0, min(255, int(alpha_threshold)))
    min_pixels = max(1, int(min_pixels))
    merge_distance = max(0, int(merge_distance))
    padding = max(0, int(padding))
    if width == 0 or height == 0:
        return []

    parents: list[int] = []
    runs: list[tuple[int, int, int, int]] = []  # x0, x1, y, label
    pixel_counts: list[int] = []

    def new_label(count: int) -> int:
        label = len(parents)
        parents.append(label)
        pixel_counts.append(count)
        return label

    def find(label: int) -> int:
        while parents[label] != label:
            parents[label] = parents[parents[label]]
            label = parents[label]
        return label

    def union(left: int, right: int) -> int:
        left_root, right_root = find(left), find(right)
        if left_root == right_root:
            return left_root
        if left_root > right_root:
            left_root, right_root = right_root, left_root
        parents[right_root] = left_root
        pixel_counts[left_root] += pixel_counts[right_root]
        return left_root

    previous: list[tuple[int, int, int]] = []
    for y in range(height):
        current: list[tuple[int, int, int]] = []
        x = 0
        while x < width:
            while x < width and int(alpha_at(x, y)) < threshold:
                x += 1
            if x >= width:
                break
            x0 = x
            while x < width and int(alpha_at(x, y)) >= threshold:
                x += 1
            x1 = x - 1
            label = new_label(x1 - x0 + 1)
            for previous_x0, previous_x1, previous_label in previous:
                if previous_x1 + 1 < x0:
                    continue
                if previous_x0 - 1 > x1:
                    break
                label = union(label, previous_label)
            current.append((x0, x1, label))
            runs.append((x0, x1, y, label))
        previous = current

    bounds: dict[int, list[int]] = {}
    counts: dict[int, int] = {}
    for x0, x1, y, label in runs:
        root = find(label)
        rect = bounds.setdefault(root, [x0, y, x1, y])
        rect[0] = min(rect[0], x0)
        rect[1] = min(rect[1], y)
        rect[2] = max(rect[2], x1)
        rect[3] = max(rect[3], y)
        counts[root] = counts.get(root, 0) + (x1 - x0 + 1)

    regions = [
        SliceRegion(x0, y0, x1 - x0 + 1, y1 - y0 + 1, counts[root])
        for root, (x0, y0, x1, y1) in bounds.items()
        if counts.get(root, 0) >= min_pixels
    ]

    # Merge detached but visually related pieces. Repeating to convergence is
    # intentional: A touching B and B touching C should become one sprite.
    changed = True
    while changed:
        changed = False
        merged: list[SliceRegion] = []
        for region in regions:
            for index, other in enumerate(merged):
                if _regions_near(region, other, merge_distance):
                    merged[index] = _unite(region, other)
                    changed = True
                    break
            else:
                merged.append(region)
        regions = merged

    padded = [_pad(region, padding, width, height) for region in regions]
    return sorted(padded, key=lambda region: (region.y, region.x, region.height, region.width))


def _regions_near(left: SliceRegion, right: SliceRegion, distance: int) -> bool:
    return not (
        left.right + distance < right.x
        or right.right + distance < left.x
        or left.bottom + distance < right.y
        or right.bottom + distance < left.y
    )


def _unite(left: SliceRegion, right: SliceRegion) -> SliceRegion:
    x0, y0 = min(left.x, right.x), min(left.y, right.y)
    x1, y1 = max(left.right, right.right), max(left.bottom, right.bottom)
    return SliceRegion(x0, y0, x1 - x0 + 1, y1 - y0 + 1, left.opaque_pixels + right.opaque_pixels)


def _pad(region: SliceRegion, amount: int, width: int, height: int) -> SliceRegion:
    x0 = max(0, region.x - amount)
    y0 = max(0, region.y - amount)
    x1 = min(width - 1, region.right + amount)
    y1 = min(height - 1, region.bottom + amount)
    return SliceRegion(x0, y0, x1 - x0 + 1, y1 - y0 + 1, region.opaque_pixels)
