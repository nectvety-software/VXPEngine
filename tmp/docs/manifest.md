# `manifest.json` schema

Written by `slice_tilesheet.py` next to `cells/` and `overlay.png`. It is the contract between
the slicer and anything that renders or rebuilds the atlas.

## Top level

| Field | Type | Meaning |
|---|---|---|
| `source` | string | Input filename only, not a path |
| `source_size` | `[w, h]` | Pixel size of the atlas as loaded |
| `cell` | `[cw, ch]` | Cell pitch in source pixels |
| `cell_mode` | string | `"auto (score N.NN)"` or `"manual"` — how `cell` was decided |
| `grid` | `[cols, rows]` | `source_size // cell`, truncated |
| `pad` | int | Inward shrink applied to every cell |
| `count` | int | Number of tiles with a written file |
| `blank` | int | Number of slots with no file |
| `tiles` | array | Every slot, `count + blank + skipped = cols*rows` |

## `tiles[]` entry

```json
{ "index": 149, "col": 5, "row": 4, "x": 160, "y": 128,
  "w": 32, "h": 32, "file": "cells/tile_149.png", "blank": false }
```

| Field | Notes |
|---|---|
| `index` | `row*cols + col`. Stable across runs as long as the grid is unchanged |
| `col`, `row` | Grid coordinates, origin top-left |
| `x`, `y` | Absolute top-left in **source pixels** (already includes `--pad`) |
| `w`, `h` | Crop size; `cell - 2*pad` in the normal case |
| `file` | Path relative to the manifest, or `null` when `blank` is true |
| `blank` | True when < 1 % of the cell is opaque and non-black |

## Invariants

1. `len(tiles) == grid[0] * grid[1]` minus any slot removed by an over-large `--pad`.
2. `count + blank == len(tiles)`.
3. `tiles` is sorted by `index`, and `index` values are dense `0..len-1`.
4. Every non-null `file` exists on disk and its PNG size equals `[w, h]`.
5. `x == col*cell[0] + pad` and `y == row*cell[1] + pad`.

Check 4 is the usual smoke test after a run:

```bash
python - <<'PY'
import json, os
from PIL import Image
m = json.load(open('out/manifest.json'))
bad = [t['file'] for t in m['tiles'] if t['file']
       and (not os.path.exists('out/'+t['file'])
            or Image.open('out/'+t['file']).size != (t['w'], t['h']))]
print('OK' if not bad else f'BROKEN: {bad[:5]}')
PY
```

## Rebuilding the atlas from the manifest

```python
import json
from PIL import Image

m = json.load(open('out/manifest.json'))
w, h = m['source_size']
atlas = Image.new('RGBA', (w, h), (0, 0, 0, 255))
for t in m['tiles']:
    if t['file']:
        atlas.paste(Image.open('out/' + t['file']).convert('RGBA'), (t['x'], t['y']))
atlas.convert('RGB').save('rebuilt.png')
```

Round-trip fidelity, measured on this atlas:

| Run flags | Files written | Max channel diff vs `tilemaps.png` |
|---|---|---|
| default (`out/`) | 176 | 27 — 1257 px lost, all inside blank slots |
| `--no-skip-blank` | 216 | 0 — byte-exact |

The default run is **not** a lossless container: blank slots still hold the 1 px outline of the
neighbouring tile and sub-threshold texture. Slice with `--no-skip-blank` whenever the atlas must
be reassembled exactly. With `--pad N` the stripped border is unrecoverable either way, so
compare against the source with the pad region masked.

## Consuming tiles in a renderer

Map a game grid cell to a tile with the same index formula, and treat `file: null` as "draw
nothing / keep the layer below":

```python
by_index = {t['index']: t for t in m['tiles'] if t['file']}
tile = by_index.get(row * m['grid'][0] + col)
```

Do not compact or renumber indices to drop blanks — every documented index range in
[tile-catalog.md](tile-catalog.md) assumes the dense layout.
