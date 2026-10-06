"""Terra engine core: tile atlas handling, tilemaps, camera, draw batching.

Deliberately free of any Qt import so the same model can run in a headless
build pipeline, a test, or this editor's UI layer.
"""

from .camera import Camera2D
from .history import History, PaintCommand
from .project import Project
from .renderer import DrawBatch, build_batches
from .tilemap import Layer, TileMap
from .tilesheet import TileSheet, TileRef

__version__ = "0.1.0"

__all__ = [
    "Camera2D", "History", "PaintCommand", "Project", "DrawBatch", "build_batches",
    "Layer", "TileMap", "TileSheet", "TileRef", "__version__",
]
