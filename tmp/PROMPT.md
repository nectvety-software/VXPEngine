# PROMPT — Tilesheet slicing pipeline

Paste the block below to an agent working in this folder. It is the task spec;
the `tilesheet-slicer` skill (`~/.qoder/skills/tilesheet-slicer/`) implements it.

---

## Task prompt

```
Slice the tile atlas into individual cells and produce a verifiable overlay.

INPUT
  ./tilemaps.png  — 1152x192 RGB atlas, pixel-art grass/water autotiles.
                    5 tile groups at x = 0, 160, 448, 736, 1024
                    (widths 128/256/256/256/128 px, separated by 32 px black gaps).
                    Cell size is 32x32 -> grid 36 cols x 6 rows = 216 slots.

DO
  1. Run:  python ~/.qoder/skills/tilesheet-slicer/scripts/slice_tilesheet.py \
              tilemaps.png -o out
  2. Open out/overlay.png and confirm every red grid line sits on a tile border.
     If lines cut through artwork, re-run with an explicit --cell N (or WxH).
  3. Report: detected cell size, grid dimensions, number of cells written,
     number of blank cells skipped, and the output path.

OUTPUT (out/)
  cells/tile_<index>.png   one PNG per non-blank cell, index = row*36 + col, zero-padded 3
  manifest.json            source size, cell size, grid, tiles[] with {index,col,row,x,y,w,h,file,blank}
  overlay.png              atlas upscaled x2 with red grid and "col.row" label per cell

RULES
  - Do not invent a new slicing script; use the bundled one.
  - Keep indices dense: blank slots stay in manifest.json with "file": null so a
    downstream renderer can rebuild the atlas from the manifest alone.
  - Never upscale or resample tile cells (NEAREST only, pixel art).
  - The 32 px black gaps between groups are padding, not tiles — do not treat them
    as cell borders.
  - Overwrite out/ freely; never modify tilemaps.png.

DONE WHEN
  out/manifest.json exists, count of files in out/cells equals manifest.count,
  and overlay.png visually aligns to the artwork.
```

---

## Background reading

Detailed specs live in [docs/](docs/README.md):

* `docs/atlas.md` — geometry, groups, gap columns, palette, uniqueness stats
* `docs/tile-catalog.md` — per-block inventory and index ranges
* `docs/manifest.md` — schema, invariants, rebuild recipe + its measured fidelity
* `docs/pipeline.md` — flags, auto-detect algorithm, verification, troubleshooting

## Variants

| Goal | Change |
|---|---|
| Trim 1 px bleed from neighbours | add `--pad 1` |
| Emit PNGs for blank slots too | add `--no-skip-blank` |
| Skip the overlay render | add `--no-overlay` |
| Non-square tiles | `--cell 48x32` |
| Known grid, skip detection | `--cell 32` |

## Notes for future edits

* Auto-detect scores edge energy along candidate grids (8/16/24/32/48/64) and only
  accepts a size dividing both axes. It misfires on anti-aliased tiles or atlases where
  group gaps dominate — pass `--cell` explicitly in that case.
* `D:/MRE/tilesheet/tilesheet_cells.png` is a hand-made reference overlay; the generated
  `out/overlay.png` is its reproducible equivalent.
