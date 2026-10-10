# Tower shell: measured findings

Follow-up to the earlier probe scratch files in this folder. Everything below is a
measurement from a host build of the real scene at 120x160 (`src/scene.cpp`), not a
reading of the source.

## What was actually wrong

The old claim in the source comment was that hidden back-facing ring quads win the
depth test and leave sky-coloured holes. Two measurements do not support it:

- Rebuilding the pre-fix scene (`docs/scene_ab.cpp`, all 16 ring quads per level
  submitted, exact depth) and the culled scene gives the same 10 detected interior
  background pixels at the same coordinates. App-level culling changed coverage by
  21 pixels out of 19200 and no hole. The holes that the detector does find are
  background between the near tower and a distant one, not gaps in the shell.
- Because the sky is painted before geometry and writes no depth, a pixel that any
  quad covers is never sky. Depth rejection alone cannot produce a sky pixel.

What the same geometry *is* sensitive to is submission order:

```
same geometry, only the ring loop s = 0..15 rewritten as s = 15..0
before the core fix : 82 of 19200 world pixels changed
after  the core fix : 16 of 19200 world pixels changed
```

The 82 pixels are the shared edges of the shell. The core used an inclusive
`w >= 0` test on all three triangle edges, so both triangles of every quad covered
their shared diagonal and the winner was the triangle submitted last; adjacent ring
quads did the same along their shared vertical edge. `affine_depth` plays no part
here: the material sets `fog_alpha = 100`, which makes the core disable the affine
path, so the demo was never actually using it.

The 16 remaining pixels are exact 16-bit depth ties between facets that graze the
tower silhouette (`(23,42) (24,44) (25,46) (26,48) (27,50)` is the leaning left
silhouette of the near tower). Removing the crown rings leaves 17, removing the
glass stripe leaves 13, so they are not attributable to either detail; they are
inherent to a 16-bit depth buffer at a grazing angle and are sub-pixel.

## Changes

Core (`engine/coremre`, shipped in package `2.0.0`):

- top-left fill rule in the triangle rasterizer, so a pixel on a shared edge belongs
  to exactly one triangle and coverage no longer depends on draw order;
- `VxpeToonMaterial3D.depth_bias`, polygon offset in camera-space z units applied to
  the depth test and the stored depth but not to fog, for coincident surfaces;
- regression coverage for both in `vxpe_toon3d_regression.cpp`.

Sample (`src/scene.cpp`):

- `ring_faces_viewer()` and its two call sites are removed. The fill rule makes the
  shared-edge ambiguity deterministic, so the hand-rolled back-face test is no longer
  carrying correctness, and the tower is back to its full ring of quads;
- the tower shell is now continuous. Each level used to build its bottom ring at `x`
  and its top ring at `x + level*level*2`, so the ring at every joint was used at two
  different centre offsets and two different radii, leaving a step in the silhouette.
  A single `RING_OX[5]` table is now shared by the level below and the level above;
- the cyan glass stripe is a decal at the shell radius with `depth_bias = -3` instead
  of a ring pushed 2 units outside the shell. It no longer protrudes, so the ledge
  that could be seen through at the silhouette is gone;
- `affine_depth` is left at 0 with the rest of the material defaults: the flag was set
  to 1 while `fog_alpha = 100` silently disabled the affine path, which made the
  material look cheaper on ARM than it was.

## VXPEmu check

The ARM build links the repackaged core (`packaging/coremre/2.0.0/src/graphics/VxpToon3D.cpp`
is the object the ARM target compiles), signs with `CERT ID 100` and reports `VERIFY : OK`.
The emulator was captured with the harness in `tmp/vxpemu_capture.ps1` (PrintWindow; the
device framebuffer sits at `(504,140)` of the 1280x800 window, shown at 125% zoom):

```
title frame, device vs host promised_future_title.ppm   mean |diff| 5.33   6.64% of pixels > 24
world frame, device vs host promised_future_island.ppm  mean |diff| 5.17   6.70% of pixels > 24
  of which rows 32..287 (the 3D view)  mean |diff| 0.79
  and rows 0..31 / 288..319 (HUD bars) mean |diff| 59.1 / 57.5
```

The residual is the HUD text only: one-pixel glyphs are resampled by the emulator's 125%
zoom, while the 3D view matches the host reference to within about one channel step. The
world frame was captured by building a throwaway variant that starts in the world state,
because injected keyboard and pen events did not reach the emulator window from this
session (`SendKeys` and a synthetic click both left the frame unchanged). The shipped
artifact was rebuilt from the unmodified source afterwards and its SHA-256 matches the
unmodified source afterwards; the emitted artifact is `promised_future_signed.vxp`, 382241
bytes, `CERT ID 100`, SHA-256 `A90C96A3D44C109029D15B30968CBE4C8B7F9393B5CAABB141D18517D4C1D503`.

Artifacts: `docs/vxpemu_screen_world.png` (device world frame), `promised_future_title.png`
and `promised_future_island.png` (host references regenerated from the regression run).

## Reproduce

```
g++ -std=c++17 -O2 -I ../src -I ../../../engine/coremre/include \
    hole_probe.cpp ../src/scene.cpp ../../../engine/coremre/src/graphics/VxpRender2D.cpp \
    ../../../engine/coremre/src/graphics/VxpSpriteFx.cpp \
    ../../../engine/coremre/src/graphics/VxpToon3D.cpp -o hole_probe
./hole_probe label out.ppm     # prints covered pixels and interior-background count
```

`world_dump.cpp` writes the deterministic 120x160 world frame so two build variants
can be diffed pixel by pixel. Both are host diagnostics and are not part of the `.vxp`.
