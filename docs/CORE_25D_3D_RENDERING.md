# VXPEngine 2.5D and 3D rendering improvements

The shared core adds two optional rendering controls for scenes that need more depth and surface form while keeping the existing flat paths available.

## 2.5D camera orientation

`VxpeCamera25D` now accepts fixed-point yaw and pitch (`Q14`, where 16384 is 1.0). `vxpe25d_camera_init` sets the camera to face +Z with a level horizon. Rotate the view by setting the normalized sine/cosine pair; positive pitch follows the same convention as `VxpeToonCamera3D`.

```cpp
camera.sin_yaw_q14 = sinYawQ14;
camera.cos_yaw_q14 = cosYawQ14;
camera.sin_pitch_q14 = sinPitchQ14;
camera.cos_pitch_q14 = cosPitchQ14;
```

Call `vxpe25d_project` as before. It transforms world offsets into camera space before near/far clipping, perspective scale, and fog. Projection uses 64-bit intermediates so extreme world/camera offsets are rejected safely instead of overflowing 32-bit subtraction.

## 3D per-vertex cel lighting

`vxpe_toon3d_triangle_gouraud` interpolates three vertex illumination values in perspective-correct camera space, then applies the material’s cel bands at each covered pixel. It supports the same near/far clipping, depth, fog, cutout, and edge mask as flat triangles. Use it on curved surfaces or split a lit quad into two triangles with a shared material and no internal ink.

```cpp
const uint8_t cornerLight[3] = {72, 220, 150};
vxpe_toon3d_triangle_gouraud(&target, &camera, a, b, c,
                             &material, cornerLight, 0);
```

Uniform flat triangles keep the existing precomputed-shade fast path. Gouraud triangles add interpolation work only when their corner values differ. Both paths allocate no memory and keep the caller-owned RGB565 color and depth buffers.

## 3D per-vertex cel lighting on textured faces

`vxpe_toon3d_triangle_gouraud_textured` combines the perspective-correct UV path with the per-vertex illumination path above. Each covered pixel gets a perspective-correct illumination value, the material's cel bands are applied to the sampled texel, and the existing albedo tint, A8 alpha, depth test, fog, cutout and edge mask behave exactly as in `vxpe_toon3d_triangle_textured`.

The practical reason to use it: a broad light falloff that should cross cel bands used to require splitting the surface into more triangles, because a flat-lit textured face can only ever show one band. With one illumination value per corner, a large ground plane or a curved panel can carry a gradient without extra geometry. The lighting term is interpolation-plus-band per pixel; the texture lookup, perspective divide and fog are unchanged, so the added cost is the same `light_over_z` quotient already used by the untextured Gouraud path.

```cpp
const uint8_t cornerLight[3] = {48, 232, 132};
vxpe_toon3d_triangle_gouraud_textured(&target, &camera, vertices,
                                      &texture, &material, cornerLight, 0);
```

`vxpe_toon3d_quad_gouraud_textured` is the quad wrapper: it splits the convex, planar quad into the two triangles (0,1,2) and (0,2,3), forwards the corner illumination to each, and passes edge mask 3 then 6 so the shared diagonal carries no ink. Vertex order around the border matters, as with the flat quad entry points.

Reach for the flat-lit textured entries on small or already-flat faces; the Gouraud variants pay an extra interpolation channel per pixel and are meant for surfaces where a smooth falloff is actually visible.

## Low-power triangle rasterization

The 3D triangle rasterizer increments its three edge-function values across a scanline and increments the row starts between scanlines. This removes repeated wide-integer edge multiplications for every candidate pixel while preserving the same top-left coverage, clipping, depth test, shading, texture lookup, fog, and outline behavior.

On 32-bit ARM builds, exact-depth triangles step the barycentric reciprocal-depth quotient and remainder across each row. Perspective-textured triangles also step both normalized barycentric weight quotients and remainders. The integer values at covered pixels are identical to the former per-pixel divisions, so perspective-correct UV interpolation and depth remain unchanged. The x/y quotient and remainder gradients are prepared once per triangle, removing three software 64-bit divisions from each textured pixel (one reciprocal plus two UV weights); reciprocal-to-camera-Z conversion and UV perspective correction remain unchanged. This path is enabled only on 32-bit ARM, where 64-bit division is a software helper. Host builds keep the simpler path, and `VXPE_TOON3D_STEPPED_RECIPROCAL` can force the ARM path for image-equivalence tests.

Materials can additionally opt into `affine_depth` for flat, untextured faces without Gouraud lighting or fog. This path interpolates camera-space depth as a screen-space plane and avoids the per-pixel reciprocal-depth division. Keep the default (`0`) for perspective-sensitive overlap, textured, smoothly lit, or fogged geometry; use `1` only for small, low-resolution scenes whose faces are well separated. This is an approximation, so validate occlusion in the target view. The field is appended to the public material struct; rebuild projects against the updated header.

The rasterizer now rejects a projected triangle whose screen-space bounding box misses the target before entering the pixel loops. This preserves clipping and coverage for intersecting triangles while avoiding edge/depth work for fully off-screen geometry.

`vxpe_toon3d_clear_depth(target)` clears only the caller-owned Z buffer to `65535`, using a contiguous fill. Use it when a sky gradient, panorama, or other pass overwrites every color pixel. For a 120×160 RGB565 target that skips one redundant 76,800-byte color write per frame; call `vxpe_toon3d_clear` when the caller needs a uniform color clear.

For portrait S30+ devices, a practical memory budget is a half-resolution RGB565 render target plus a half-resolution 16-bit depth buffer (76,800 bytes at 120×160), enlarged with the existing Scale2x helper. Draw text and controls at native resolution after scaling. This keeps the 3D camera perspective while reducing fill work and buffer RAM to one quarter of a full 240×320 color/depth pair. The mall sample demonstrates this path without dynamic allocations in its frame loop.

`tests/vxpe_graphics_benchmark.cpp` is an opt-in host profiler for 2.5D billboards and the exact/affine 3D triangle paths at 120×160 and 240×320. Build target `vxpe_graphics_benchmark` and run it with an iteration count; it writes reference PPMs under `reports/graphics-benchmark`. Host timings are comparative only and do not represent device FPS. For current measurements and the recommended path by scene type, see that report.

## Deterministic coverage and depth offset

The rasterizer applies a top-left fill rule. A pixel lying exactly on a triangle edge belongs to the triangle that owns that edge: an edge directed downwards, or a horizontal edge directed to the left (screen space, y down, interior on the right of every directed edge). Two triangles that share an edge traverse it in opposite directions, so exactly one of them keeps the boundary pixels. Previously both triangles of a quad covered their shared diagonal and the surviving pixel was whichever was submitted last, so seams and coincident faces changed with draw order instead of geometry. In the Promised Future sample, reordering the ring quads of one tower changed 82 of 19200 world pixels before the rule and 16 after it; the remainder are exact 16-bit depth ties between facets that graze the silhouette, which no coverage rule can separate.

Materials gained `depth_bias`, polygon offset expressed in whole camera-space z units and applied to the depth test and to the stored depth, but never to the fog term. Use it for coincident surfaces - a sign decal on a wall, a stripe on a curved shell, glass over an opening - instead of pushing the geometry outward, which leaves an overhang that can be seen through at the silhouette. Negative values pull the face towards the camera. The default is 0, so existing scenes keep their depth behaviour, and `vxpe_toon3d_billboard` honours the same field.

## Dithered 2D gradients

`vxpe2d_gradient_vertical_dithered` fills the same rectangle as `vxpe2d_gradient_vertical` but applies 4x4 ordered dithering against RGB565 quantization. A tall band steps through few 565 levels per channel, which reads as flat stripes: on the regression's synthetic 64x64 band the plain fill repeated the row above 32 times and the dithered fill leaves 0, because the interpolation happens in 8-bit channels and the bias spans one whole destination level. The Promised Future sky improves over the same effect but not to zero at every column: at one sampled column the count of rows matching the row above went from 51 of 80 to 24, since adjacent rows can still quantize to the same value. The dither bias only depends on the column modulo four, so each row precomputes four colours and the pixel loop is a masked store; a 120x160 pass measured 1.33x the plain fill on the host benchmark (0.010 ms versus 0.007 ms per frame, host timings are comparative only). Prefer the plain fill for short gradients that already cover many levels.

## Untextured Gouraud quads

`vxpe_toon3d_quad_gouraud` is the untextured counterpart of `vxpe_toon3d_quad_gouraud_textured`: it takes one illumination value per corner, splits the quad into (0,1,2) and (0,2,3), and forwards the corner values so the shared diagonal carries no ink. Use it where a surface direction turns across the face - cylinder shells, terrain skirts, leaning towers - so the cel bands read as light falling on a form instead of one flat tone per quad. Quads whose corners share a value take the same precomputed-shade path as `vxpe_toon3d_quad`.

## Camera-anchored perspective ground

`vxpe25d_draw_ground` renders the world y=0 plane through the same `VxpeCamera25D` that billboards use, so tiled floors stay glued to the world while the camera drives forward and yaws. The older `vxpe25d_draw_plane` is a screen-space trapezoid whose texture ramp is linear in screen rows - acceptable for a static road strip, but its texture visibly slides when the camera moves. Every screen row below `horizon_y` maps to one world depth `z = focal_px * camera.world_y / (y - horizon_y)`; rows nearer than `near_z` are skipped, and the horizon row itself plus rows beyond `far_z` are painted `camera->fog_color565` when `use_fog` is set - without fog they are left untouched. The fog fill keeps the horizon seamless: the emulator run of `examples/MeadowRush25D` showed that leaving the horizon row and the far-culled rows stale draws a 1 px tear plus a black band between sky and ground whenever `far_z` is smaller than the depth at `horizon_y + 1`. Screen columns then step the world point linearly along that row: the per-pixel world step is `z/focal` in Q16 (`(z_q8<<16)/focal_q8`) and the row-start phase is kept in Q16 texels rather than truncated to whole world units. An earlier revision shifted by only 8, making the horizontal step 256x too small: with a level camera every row collapsed to a single texel and tiled floors degenerated into horizontal bands - the emulator run of `examples/StormArena25D` caught it because the arena's vertical grid lines never appeared, and only a yawed camera (as in `examples/MeadowRush25D`) had masked the error with row-to-row variation. The inner loop is 32-bit adds, shifts and two wrap branches, while division and modulo happen once per row. Texture coordinates accumulate in Q16 texels and wrap per row, which keeps sampling correct for negative world coordinates; rows so shallow that one pixel spans a whole texture repeat fall back to a per-pixel modulo (only far, fog-blurred rows take that branch). `use_fog` blends each row with the same distance ramp `vxpe25d_project` applies to billboards, so ground and sprites fog consistently. Pitch is intentionally ignored - bake it by moving `horizon_y`. The sampler honours the sprite's A8 channel, tint, and all four `VxpeBlendMode`s.

```cpp
VxpeGround25D ground{};
ground.src={0,0,8,8}; ground.tile_w=32; ground.tile_h=32;
ground.blend=VXPE_BLEND_COPY; ground.use_fog=1;
vxpe25d_draw_ground(fb,240,320,&camera,&floor_tiles,&ground);
```

## Depth-sorted 2.5D billboard batch

`VxpeBillboardBatch25D` (fixed array, `VXPE_BATCH25D_MAX`=64, zero heap) lifts the painter-order bookkeeping out of game code. Entries are a `VxpeBillboard25D`, its sprite, and an optional projected ground shadow. `vxpe25d_batch_flush` projects every entry with the camera, silently culls what `vxpe25d_draw_billboard` would reject, stable-insertion-sorts by projected depth, then draws far-to-near; each entry's shadow is drawn immediately before its billboard, so shadows never bleed over nearer objects. Push order is irrelevant, matching the 2D `VxpeSpriteBatch` contract: full pushes bump `dropped`, flush clears `count` but preserves `dropped`.

```cpp
vxpe25d_batch_init(&batch);
vxpe25d_batch_push(&batch,&tree_entry);   /* any order */
int drawn = vxpe25d_batch_flush(&batch,fb,240,320,&camera);
```

In the host benchmark the combined scene - one full-screen ground pass plus 48 unsorted trees with shadows - measures 0.735 ms/frame at 240×320 versus 0.583 ms for the hand-ordered billboard scene (see `reports/graphics-benchmark/README.md`); correct per-frame sorting and a perspective-correct floor cost about 0.15 ms at QVGA.

## Compatibility and tests

The new 2.5D camera fields are appended to `VxpeCamera25D`; callers that zero-initialize the struct retain the legacy +Z, level camera. Rebuild projects against the updated header because the public struct has grown. Existing renderer entry points and their flat-light behavior are unchanged. Regression coverage checks yaw/pitch projection, extreme-coordinate rejection, per-vertex band transitions, textured per-vertex lighting (proving the Gouraud path yields several cel bands where flat lighting yields one), quad-wrapper byte-equivalence, clipping, and the C API.

`tests/vxpe_toon3d_regression.cpp` and `tests/vxpe_toon3d_c_api.c` are the entry points for these paths; both are built and run by `ctest`. The suite pins the fill rule (a quad split into two triangles must report drawn counts that add up to the covered pixel count, and swapping their submission order must not change one pixel) and `depth_bias` (a coincident face pulled towards the camera must win whichever is submitted first).

`tests/vxpe_scene25d_regression.cpp` covers the 2.5D scene on top of the existing camera/plane/shadow checks: sliding the ground exactly one tile must reproduce the previous frame pixel-for-pixel (both with and without a quarter-turn yaw), half a tile must change it, an unreachable near/far band must write nothing without fog, the horizon seam test pins that the horizon row and the far-culled band are painted the fog colour when `use_fog` is on while nearer rows still texture, a step-scale test pins that a level camera's bottom row alternates the 2-texel checker ~48 times (a 256x step error collapses it to one texel) and repeats pixel-exactly one full tile in X, and invalid tile sizes must no-op. The batch checks pin painter order (near pushed first must still end up drawn last where sprites overlap), silent culling of unprojectable entries, the `dropped`/`count` flush contract at capacity, and that a batched shadow darkens the ground beside a narrow billboard without covering the billboard itself. `tests/vxpe_scene25d_c_api.c` keeps the new entry points compiling and running under plain C99.
