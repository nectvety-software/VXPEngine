# Slicing pipeline

## What runs

`~/.qoder/skills/tilesheet-slicer/scripts/slice_tilesheet.py` — Python 3, Pillow + NumPy.
It walks a fixed rectangular grid over the atlas, crops each cell, classifies blanks, writes
`manifest.json`, and renders the labelled overlay.

```bash
python ~/.qoder/skills/tilesheet-slicer/scripts/slice_tilesheet.py tilemaps.png -o out
```

Output for this repo:

```
OK  tilemaps.png 1152x192  cell 32x32 [auto (score 2.56)]  grid 36x6
    wrote 176 cell PNG + manifest.json + overlay.png (x2)  (skipped 40 blank)
    -> out
```

## Flags

| Flag | Default | Effect |
|---|---|---|
| `input` | required | Atlas PNG (RGB or RGBA; converted to RGBA internally) |
| `-o, --out` | `<stem>_sliced` | Output directory, created recursively |
| `--cell` | `auto` | `auto`, `N` (square), or `WxH` |
| `--prefix` | `tile` | Filename prefix: `cells/<prefix>_<index:03d>.png` |
| `--pad` | `0` | Shrink every cell inward by N px on all sides |
| `--scale` | `2` | Overlay upscale (NEAREST). `1` disables the overlay |
| `--no-skip-blank` | off | Still write PNGs for blank slots |
| `--no-overlay` | off | Skip overlay rendering |

## Cell-size auto-detection

For each candidate in `8, 16, 24, 32, 48, 64` that divides **both** axes:

```
seam(i)  = mean(|Δx| at column i, |Δx| at column i+1)      # the boundary straddles k-1|k
score(c) = ½ · [ mean(seam(c), seam(2c), …) / mean|Δx| overall
               + mean(seam(c), seam(2c), …) / mean|Δy| overall ]
```

`|Δx|[i]` is the difference between columns `i` and `i+1`, so the seam in front of grid line
`x = k` actually lives at index `k-1`. Sampling only `k` misses it by one pixel, which is
harmless on outlined atlases like `tilemaps.png` but fatal on **full-bleed** atlases whose
tiles run edge to edge — the old detector scored those highest at 48 px. Both sides of every
seam are averaged now.

The winner is the **finest** candidate scoring within 85 % of the best, not the raw maximum:
a 64 px grid samples a subset of the same seams as a 32 px one, so a coarse grid can only
ever look as good as the true cell size. If no candidate divides the image the fallback is 32.

Measured scores on `tilemaps.png`:

| Candidate | Score |
|---|---|
| **32** | **2.56** |
| 64 | 2.16 |
| 48 | 2.12 |
| 24 | 1.36 |
| 16 | 1.49 |
| 8 | 1.08 |

32 wins outright at 18 % above the runner-up, and 64/48 fall below the 85 % cut anyway.
Measured scores on the four generated atlases in `sheets/`: 32 wins at 2.65 (`terrain_pixel`),
3.45 (`biomes_natural`), 3.60 (`terrain_natural`) and 4.56 (`terrain_oil`).

Known limits: candidates stop at 64 px, so a 96 px or 128 px tile sheet needs explicit
`--cell`; soft/anti-aliased tile borders give flat scores; and an atlas whose group gaps are
wider than its cells can make the gap grid outrank the real cell grid.

## Verification workflow

1. Run with `-o out`.
2. Open `out/overlay.png` and look along every group boundary. Grid lines must sit on the black
   gaps, and the 1 px dark outlines of the tiles must not be cut in half.
3. Cross-check the summary against the documented numbers: cell 32, grid 36x6,
   `count 176`, `blank 40`. A different count means the atlas changed or the grid is wrong.
4. Run the manifest smoke test in [manifest.md](manifest.md#invariants).

The overlay labels each cell `col.row` in red at its top-left, and draws one line per grid
position, so a half-cell offset is visible immediately as doubled lines.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Lines cut through artwork | wrong auto-detected cell | `--cell 32` explicitly |
| `WARN: WxH is not divisible by cell` | atlas has a stray border row/column | set `--cell` to a divisor, or crop the source first |
| Tiles show a 1 px fringe of the neighbour | atlas packed without gutters | `--pad 1` |
| Blank cells you actually want | they are < 1 % visible | `--no-skip-blank`, and check the source really has art there |
| `ERROR: ModuleNotFoundError: PIL` | Pillow not installed | `python -m pip install pillow numpy` |
| Non-square tiles sliced as squares | `--cell` given as a single number | `--cell 48x32` |

## Determinism and safety

* The script never writes outside `--out` and never modifies the input.
* No randomness, no network. Same input plus same flags ⇒ byte-identical cells.
* Errors print one `ERROR: Type: message` line and exit 1; tracebacks are suppressed so the
  agent sees a short signal instead of a stack dump.

## Extending

* **Split by group** (one directory per biome group) — detect fully-blank column runs before
  slicing; the gap columns for this atlas are 4, 13, 22, 31.
* **Pack cells back into a new atlas** — see the rebuild recipe in
  [manifest.md](manifest.md#rebuilding-the-atlas-from-the-manifest), and slice with
  `--no-skip-blank` first if the round trip must be byte-exact.
* **Semantic tile naming** (`grass_tl`, `water_edge`, …) — add a lookup table keyed on
  `col`/`row`; do not change the numeric `index`, it is the stable identifier used by
  [tile-catalog.md](tile-catalog.md).
