# Tile catalog

Per-block inventory derived from `out/manifest.json` (authoritative — regenerate with the
slicer and diff if in doubt). Index = `row*36 + col`.

## Occupancy map

`#` filled cell, `.` blank slot, `|` gap column (never a tile).

```
        cols 0-3 | 5-12 | 14-21 | 23-30 | 32-35
row 0    ####|########|########|########|####
row 1    ####|########|########|########|####
row 2    ####|########|########|########|####
row 3    ####|########|########|########|####
row 4    #..#|#####..#|#####..#|#####..#|####
row 5    #..#|#####..#|#####..#|#####..#|####
```

Rows 0–3 are completely filled inside every group. Only rows 4–5 carry blank slots, and only
in the inner two columns of corner blocks.

## Blocks

| # | Cols | Group | Type | Rows 0–3 | Rows 4–5 | Cells |
|---|---|---|---|---|---|---|
| 1 | 0–3 | A | corner | 4/4 filled | outer 2 only | 20 |
| 2 | 5–8 | B | full | 4/4 filled | 4/4 filled | 24 |
| 3 | 9–12 | B | corner | 4/4 filled | outer 2 only | 20 |
| 4 | 14–17 | C | full | 4/4 filled | 4/4 filled | 24 |
| 5 | 18–21 | C | corner | 4/4 filled | outer 2 only | 20 |
| 6 | 23–26 | D | full | 4/4 filled | 4/4 filled | 24 |
| 7 | 27–30 | D | corner | 4/4 filled | outer 2 only | 20 |
| 8 | 32–35 | E | full | 4/4 filled | 4/4 filled | 24 |

Total `4*24 + 4*20 = 176` filled cells, matching `manifest.count`.

## Index ranges per block

Rows are listed in order 0,1,2,3,4,5.

| Block | Indices |
|---|---|
| 1 (cols 0–3) | `0-3` `36-39` `72-75` `108-111` `144,147` `180,183` |
| 2 (cols 5–8) | `5-8` `41-44` `77-80` `113-116` `149-152` `185-188` |
| 3 (cols 9–12) | `9-12` `45-48` `81-84` `117-120` `153,156` `189,192` |
| 4 (cols 14–17) | `14-17` `50-53` `86-89` `122-125` `158-161` `194-197` |
| 5 (cols 18–21) | `18-21` `54-57` `90-93` `126-129` `162,165` `198,201` |
| 6 (cols 23–26) | `23-26` `59-62` `95-98` `131-134` `167-170` `203-206` |
| 7 (cols 27–30) | `27-30` `63-66` `99-102` `135-138` `171,174` `207,210` |
| 8 (cols 32–35) | `32-35` `68-71` `104-107` `140-143` `176-179` `212-215` |

Unused indices (gap columns) are `4, 13, 22, 31` and their row offsets
(`+36, +72, +108, +144, +180`), plus the inner corner slots listed above.

## What each band depicts

Median colour of visible pixels and dark-outline share (`lum < 240`) per row:

| Row | Median rgb | Dark share | Content |
|---|---|---|---|
| 0 | 100,155,98 | 5.8 % | terrain body — grass/teal fill, speckled noise |
| 1 | 101,156,98 | 3.2 % | terrain body, least textured row |
| 2 | 100,155,98 | 6.6 % | terrain body |
| 3 | 96,154,97 | 10.4 % | terrain body, starts picking up outline pixels |
| 4 | 101,154,134 | 14.7 % | shoreline — top of the rock band, water surface between rock faces |
| 5 | 101,154,137 | 10.8 % | underwater — rock pillars/reef against water |

Rows 4–5 shift the median blue channel up by ~36 while green stays flat: that jump, not the
dark share, is the reliable signal for "this row is the shoreline band". In corner blocks only
the two outer columns of rows 4–5 exist, which is what makes them read as map edges.

## Group identity

The 5 groups share block geometry and differ in tint only (green → teal, see
[atlas.md](atlas.md#palette)). When mapping to a game, treat group index as the biome/tint
selector and column/row as the shape selector — do not assume group B's tiles are byte-identical
to group C's, they are repainted per group (172 of 176 cells are unique).
