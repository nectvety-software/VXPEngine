# Super Scaler pseudo-3D road renderer

`graphics/VxpSuperScaler.h` provides a caller-owned RGB565 raster path for 240×320 arcade racing scenes. The pass draws the sky, flat terrain, perspective-width road, alternating shoulders, segmented road bands and broken lane markers. A quadratic depth profile makes the road narrow near the horizon and wide at the camera; a Q8 bend offset moves its center smoothly with depth.

The implementation uses a 257-entry compile-time depth LUT, a single Q16 reciprocal for scanline normalization, integer arithmetic, clipped horizontal spans, and optional power-of-two RGB565 road/terrain texture tiles. The texture sampler uses bit masks for nearest sampling without per-pixel division. A frame needs the framebuffer (153,600 bytes at 240×320 RGB565), two 8×8 RGB565 detail tiles (256 bytes total in the sample), plus the caller's small fixed game state. Keep sprite art pre-scaled or derive a small number of sizes outside the inner scanline loop; draw traffic far-to-near after the road and cull it when its projected rectangle leaves the viewport.

The `examples/SuperScalerRacingDemo` project is the reference integration. It draws three fixed traffic actors, simple original motorcycle silhouettes, roadside markers and a compact HUD. It is intended as a rendering/gameplay test for low-power MRE devices, not a claim of measured device frame rate. Build the ARM target and measure sustained FPS/RAM on the actual S30+ handset.

Run `engine/coremre/tests/vxpe_superscaler_regression.cpp` and `examples/SuperScalerRacingDemo/tests` to verify clipping, curve placement, road expansion, controls, pause and deterministic traffic updates.
