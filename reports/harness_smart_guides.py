"""Regression for smooth soft-grid snapping and blue/yellow smart guides."""
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

from PySide6.QtCore import QPointF
from PySide6.QtWidgets import QApplication
from widgets.viewport import Viewport2D

app = QApplication.instance() or QApplication([])
viewport = Viewport2D("")
viewport._zoom = 1.0
viewport.grid_size = 32

# Grid no longer quantizes every mouse position; it engages only near a line.
free = viewport._soft_grid_snap_point(QPointF(12.0, 19.0))
near = viewport._soft_grid_snap_point(QPointF(31.0, 33.0))
assert (free.x(), free.y()) == (12.0, 19.0), free
assert (near.x(), near.y()) == (32.0, 32.0), near

node = {
    "id":"moving", "name":"Moving", "type":"Rectangle2D", "position":[30, 40],
    "shape":{"width":20,"height":20,"fill":"#FFFFFF","stroke":"#00000000","stroke_width":0},
    "scale":[1,1], "pixel_snap":True,
}
item = viewport._create_vector_item(node, persist=True)
assert item is not None

# Enter at four screen pixels, remain stable briefly, release after seven.
snapped = viewport._smart_snap_position(item, QPointF(3.0, 40.0))
assert snapped.x() == 0.0 and viewport._active_guide_x == 0.0, snapped
held = viewport._smart_snap_position(item, QPointF(6.0, 40.0))
assert held.x() == 0.0, held
released = viewport._smart_snap_position(item, QPointF(9.0, 40.0))
assert released.x() == 9.0 and viewport._active_guide_x is None, released

print("PASS: soft grid + hysteresis smart guides + smooth release")
