"""Live-drive animation playback through the real editor and export previews.

Opens each `.vpea` in MainWindow, starts the timeline's own playback timer,
records what the canvas paints on every tick, and writes one animated GIF per
scene plus a filmstrip PNG. Doubles as a playback smoke check: a scene whose
frames never all appear is reported as FAIL.

    python tools/play_animations.py                     # every .vpea in the library
    python tools/play_animations.py --dir "C:\\path\\to\\sprite" --zoom 6
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from vpx_editor.gallery import category_dir  # noqa: E402
from vpx_editor.main_window import MainWindow  # noqa: E402
from vpx_editor.vpea import header_of  # noqa: E402


def pump(app: QApplication, seconds: float) -> None:
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.001)


def sprite_grab(canvas, doc):
    """The canvas as painted, cropped to the sprite rect."""
    img = canvas.grab().toImage()
    ox, oy = int(canvas._offset.x()), int(canvas._offset.y())
    w, h = int(doc.width * canvas.zoom()), int(doc.height * canvas.zoom())
    return img.copy(ox, oy, w, h)


def play(win, app, path: str, zoom: float, cycles: float):
    """Returns (frame_count, delay_ms, loop, {frame index: QImage}, step ms)."""
    doc = win._load_doc(path)
    win._set_doc(doc, path)
    doc.dirty = False
    win.canvas.set_zoom(zoom)
    win.canvas._center_content()
    app.processEvents()

    n, delay = doc.frame_count(), doc.delay_ms
    if n < 2:
        return n, delay, doc.loop, {}, []
    seen = {0: sprite_grab(win.canvas, doc)}
    steps: list[int] = []
    last, prev_t = doc.frame, time.monotonic()
    win.timeline.start()
    deadline = time.monotonic() + (n * delay / 1000.0) * cycles + 0.5
    while time.monotonic() < deadline and win.timeline.playing():
        app.processEvents()
        time.sleep(0.001)
        if doc.frame != last:
            now = time.monotonic()
            steps.append(round((now - prev_t) * 1000))
            prev_t, last = now, doc.frame
            seen.setdefault(doc.frame, sprite_grab(win.canvas, doc))
    win.timeline.stop()
    return n, delay, doc.loop, seen, steps


def pil_frames(seen, tmp_dir: Path, tag: str):
    """QImage grabs -> PIL RGBA images (Qt writes the PNG, so no raw buffer math)."""
    from PIL import Image

    out = []
    for i in sorted(seen):
        raw = tmp_dir / f"_raw_{tag}_{i}.png"
        seen[i].save(str(raw))
        out.append(Image.open(raw).convert("RGBA"))
        raw.unlink()
    return out


def strip_of(seen, tmp_dir: Path, tag: str):
    from PIL import Image

    frames = pil_frames(seen, tmp_dir, tag)
    row = Image.new("RGBA", (sum(f.width + 8 for f in frames) + 8,
                             max(f.height for f in frames) + 8), (11, 14, 20, 255))
    x = 4
    for f in frames:
        row.paste(f, (x, 4))
        x += f.width + 8
    return row


def to_gifs(out_dir: Path, name: str, seen, delay: int, loop: bool) -> str:
    from PIL import Image

    pal = [f.convert("P", palette=Image.Palette.ADAPTIVE)
           for f in pil_frames(seen, out_dir, name)]
    gif = out_dir / f"play_{name}.gif"
    pal[0].save(gif, save_all=True, append_images=pal[1:],
                duration=delay, loop=0 if loop else 1)
    return str(gif)


def filmstrip(out_dir: Path, rows) -> str:
    from PIL import Image

    sheet = Image.new("RGBA", (max(r.width for _, r in rows),
                               sum(r.height + 8 for _, r in rows) + 8),
                      (11, 14, 20, 255))
    y = 4
    for _, r in rows:
        sheet.paste(r, (4, y))
        y += r.height + 8
    path = out_dir / "playback_filmstrip.png"
    sheet.save(path)
    return str(path)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dir", default=None,
                    help="folder to scan for .vpea (default: the sprite library)")
    ap.add_argument("--out", default=None, help="where to write previews")
    ap.add_argument("--zoom", type=float, default=8.0)
    ap.add_argument("--cycles", type=float, default=1.0,
                    help="loop passes to watch per scene (looping scenes only)")
    args = ap.parse_args()

    root = Path(args.dir) if args.dir else category_dir("sprite", create=False)
    scenes = sorted(root.rglob("*.vpea"))
    if not scenes:
        print(f"FAIL no .vpea under {root}")
        return 1
    out_dir = Path(args.out) if args.out else root.parent / "exports" / "playback"
    out_dir.mkdir(parents=True, exist_ok=True)

    try:
        import PIL  # noqa: F401
        gifs = True
    except ImportError:
        gifs = False
        print("[warn] PIL missing - playback is checked, no GIFs written")

    app = QApplication.instance() or QApplication(sys.argv)
    win = MainWindow()
    win.resize(900, 640)
    win.show()
    pump(app, 0.3)

    rows, failed = [], 0
    for path in scenes:
        loops = header_of(path)[4]
        n, delay, loop, seen, steps = play(
            win, app, str(path), args.zoom, args.cycles if loops else 1.0)
        got = len(seen)
        ok = got == n
        failed += 0 if ok else 1
        step = f"{min(steps)}-{max(steps)} ms" if steps else "n/a"
        print(f"  {'OK  ' if ok else 'FAIL'} {path.name:26} {n} frames "
              f"@{delay} ms loop={loop} painted={got} step={step}")
        if not ok:
            continue
        if gifs:
            print(f"       gif {to_gifs(out_dir, path.stem, seen, delay, loop)}")
            rows.append((path.stem, strip_of(seen, out_dir, path.stem)))
    win._doc.dirty = False
    win.close()
    if rows and gifs:
        print("sheet", filmstrip(out_dir, rows))
    print(f"{'FAIL' if failed else 'OK'} {len(scenes) - failed}/{len(scenes)} "
          f"scenes played every frame")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
