# Tilesheet documentation

Project: `D:/MRE/tilesheet` — pixel-art terrain atlas and the tooling that slices it.

| Doc | Read it when |
|---|---|
| [atlas.md](atlas.md) | You need the geometry of `tilemaps.png`: grid, coordinate system, groups, gaps, palette |
| [tile-catalog.md](tile-catalog.md) | You need to know what each cell/row contains and which slots are empty |
| [manifest.md](manifest.md) | You consume or produce `manifest.json`, or rebuild the atlas from cells |
| [pipeline.md](pipeline.md) | You run, extend or debug the slicer script |

## Source files

| File | Role |
|---|---|
| `tilemaps.png` | 1152x192 RGB atlas — the input. Never edited in place |
| `tilesheet_cells.png` | Hand-made reference overlay (grid + `col.row` labels). Superseded by the generated `out/overlay.png` |
| `PROMPT.md` | Copy-paste task prompt for an agent running the pipeline |
| `out/` | Generated output: `cells/`, `manifest.json`, `overlay.png` |
| `check_cpu.py`, `test_avx.py`, `test_load.py` | Unrelated leftover host-probing scripts, not part of this pipeline |

## Tooling location

The slicer is a user-scope skill, not a repo file:

```
~/.qoder/skills/tilesheet-slicer/
├── SKILL.md
└── scripts/slice_tilesheet.py
```

## Conventions

* Pixel art: nearest-neighbour scaling only, never bilinear or Lanczos.
* `tilemaps.png` is read-only; all derived data goes under `out/`.
* Cell indices are dense (`row * 36 + col`) and never renumbered when a cell is blank —
  blank slots keep their manifest entry with `"file": null`.
