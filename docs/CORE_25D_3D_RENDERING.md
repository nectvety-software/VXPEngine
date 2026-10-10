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

## Compatibility and tests

The new 2.5D camera fields are appended to `VxpeCamera25D`; callers that zero-initialize the struct retain the legacy +Z, level camera. Rebuild projects against the updated header because the public struct has grown. Existing renderer entry points and their flat-light behavior are unchanged. Regression coverage checks yaw/pitch projection, extreme-coordinate rejection, per-vertex band transitions, textured per-vertex lighting (proving the Gouraud path yields several cel bands where flat lighting yields one), quad-wrapper byte-equivalence, clipping, and the C API.

`tests/vxpe_toon3d_regression.cpp` and `tests/vxpe_toon3d_c_api.c` are the entry points for these paths; both are built and run by `ctest`. The suite pins the fill rule (a quad split into two triangles must report drawn counts that add up to the covered pixel count, and swapping their submission order must not change one pixel) and `depth_bias` (a coincident face pulled towards the camera must win whichever is submitted first).
