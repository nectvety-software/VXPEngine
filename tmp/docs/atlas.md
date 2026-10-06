# Atlas structure — `tilemaps.png`

All numbers below were measured from the file, not assumed.

## Geometry

| Property | Value |
|---|---|
| Size | 1152 x 192 px |
| Colour mode | RGB, no alpha channel |
| Cell size | 32 x 32 px (uniform) |
| Grid | 36 columns x 6 rows = 216 slots |
| Non-blank slots | 176 |
| Blank slots | 40 |
| Visible pixels | 166 002 of 221 184 (75.1 %) |
| Background | pure black `#000000`, used as padding between groups, not as a tile colour |

## Coordinate system

* Origin is the top-left pixel; `y` grows downward.
* Column `c` occupies `x = c*32 … c*32+31`; row `r` occupies `y = r*32 … r*32+31`.
* Linear index: `index = r*36 + c`, filename `tile_<index:03d>.png`.
* `manifest.json` stores absolute source pixels (`x`, `y`) plus `w`/`h`, so a cell rect is
  always `[x, y, x+w, y+h]` regardless of `--pad`.

## Tile groups

Content is not one continuous strip. It is 5 groups separated by 32 px black gaps, so the
gaps must never be treated as cell borders.

| Group | Columns | x range (px) | Width | Composition |
|---|---|---|---|---|
| A | 0–3 | 0–128 | 128 px | 1 corner block |
| B | 5–12 | 160–416 | 256 px | full block (5–8) + corner block (9–12) |
| C | 14–21 | 448–704 | 256 px | full block (14–17) + corner block (18–21) |
| D | 23–30 | 736–992 | 256 px | full block (23–26) + corner block (27–30) |
| E | 32–35 | 1024–1151 | 128 px | 1 full block |

Gap columns: **4, 13, 22, 31** (x = 128–159, 416–447, 704–735, 992–1023). Each gap column is
detected as blank; its leftmost pixel is the 1 px border of the neighbouring tile.

A "block" is a 4-column x 6-row unit. There are 8 blocks: 4 full-band and 4 corner, in
strict alternation `corner | full, corner | full, corner | full | full`.

## Row semantics

| Rows | y range | Content | Water/rock share* |
|---|---|---|---|
| 0–3 | 0–127 | Terrain body — solid grass/teal fill, no shoreline | 0.06–0.16 |
| 4 | 128–159 | Shoreline band — rock faces and water edge | 0.51 |
| 5 | 160–191 | Underwater band — rock pillars and water | 0.56 |

\* Heuristic share of visible pixels where `blue >= green − 4`; useful for spotting the band
boundary, not a semantic label. Per-row medians and dark-pixel shares are in
[tile-catalog.md](tile-catalog.md#what-each-band-depicts).

Full blocks fill all 8 cells of rows 4–5. Corner blocks only carry the outer columns
(`L . . R`), leaving 4 empty cells per corner block — that accounts for 16 of the 40 blanks.

## Blank-slot accounting

```
gap columns   4 cols x 6 rows           = 24
corner blocks 4 blocks x 2 inner cols x 2 rows = 16
                                        ---- total 40 blank / 176 filled
```

## Palette

10-means median-cut over visible pixels:

| Hex | rgb | Share | Reads as |
|---|---|---|---|
| `#599a89` | 89,154,137 | 27.8 % | teal water |
| `#799b73` | 121,155,115 | 19.2 % | shaded grass |
| `#69a46c` | 105,164,108 | 15.8 % | mid grass |
| `#7eb46d` | 126,180,109 | 14.5 % | lit grass |
| `#3b504f` | 59,80,79 | 11.1 % | rock outline |
| `#5f8972` | 95,137,114 | 10.1 % | transition |
| `#080a0c` | 8,10,12 | 1.6 % | dark outline / shadow pixels |

Shares are measured over visible pixels only (`lum > 90`), so the black padding is excluded;
the last bucket is the near-black artwork outline, not background.

Groups B–E are a palette progression, not different geometry: median body colour moves from
yellow-green `rgb(130,172,87)` (A) through `rgb(105,169,95)` (B), `rgb(104,155,98)` (C),
`rgb(94,151,100)` (D) to teal `rgb(85,151,138)` (E). Treat them as biome/tint variants of the
same block layout.

## Uniqueness

Hashing every non-blank cell's raw bytes: **176 cells, 172 unique, only 4 exact duplicates.**

Consequence: this atlas is hand-painted terrain, **not** a reusable autotile set. Do not
dedupe cells or assume a 47-blob / 8x8 autotile layout — the grid here is 36x6 and nearly
every tile is distinct art.
