# VXPEngine 2.5D / 3D graphics checks

The opt-in test renderer is `engine/coremre/tests/vxpe_graphics_benchmark.cpp`. It measures a drifting 48-billboard 2.5D scene, a textured retro-mall walkthrough, and a low-poly 3D plaza with depth-tested faces. The textured mall uses generated 8×8 RGB565 floor, glass, roof, and water maps; per-face fixed illumination stands in for baked lighting, while the fountain surface, fish and camera animate from lookup tables. Its arcade/pizza signage is abstract and original. The plaza runs with exact perspective depth and opt-in affine depth. Each mode is measured at 120×160 and 240×320; buffer sizes are reported alongside median frame times.

## Host run

Configure the host test directory, build `vxpe_graphics_benchmark`, then run it with a sample count:

```powershell
cmake -S engine/coremre/tests -B tmp/graphics-benchmark -G Ninja
cmake --build tmp/graphics-benchmark --target vxpe_graphics_benchmark
tmp/graphics-benchmark/vxpe_graphics_benchmark.exe 16
```

The host clock is affected by CPU scheduling and power management, so use these values to compare code paths on the same machine. They are not S30+ FPS claims.

One 16-frame run on the VXPEngine development PC:

| Path | Resolution | Median time | Pixel storage |
|---|---:|---:|---:|
| 2.5D billboards | 120×160 | 0.162 ms/frame | 38,400 B color |
| 2.5D billboards | 240×320 | 0.559 ms/frame | 153,600 B color |
| 3D textured mall | 120×160 | 2.285 ms/frame | 76,800 B color + depth |
| 3D textured mall | 240×320 | 8.434 ms/frame | 307,200 B color + depth |
| 3D exact depth, flat plaza | 120×160 | 1.287 ms/frame | 76,800 B color + depth |
| 3D affine depth, flat plaza | 120×160 | 0.782 ms/frame | 76,800 B color + depth |
| 3D exact depth, flat plaza | 240×320 | 4.217 ms/frame | 307,200 B color + depth |
| 3D affine depth, flat plaza | 240×320 | 2.240 ms/frame | 307,200 B color + depth |

In this run, affine depth was 1.6× faster at 120×160 and 1.9× at 240×320. It changed 156/19,200 pixels at 120×160 and 787/76,800 pixels at 240×320 in this overlapping plaza scene. The changes cluster around depth intersections, so affine depth remains opt-in and should be used only for separated flat faces. Textured, fogged, smooth-lit, and overlap-sensitive faces should use exact depth. The textured mall costs more than flat faces, which is the expected quality/performance tradeoff; render it at half resolution for S30+.

## Rendering choice

Use 2.5D billboards and projected planes when the scene is built from sprites and painter order is predictable. It has no depth buffer and uses half the color RAM of the 120×160 3D target. Use the 3D renderer when objects need arbitrary camera orientation and per-pixel occlusion; 120×160 color plus depth costs 76.8 KB and retains full 3D perspective. On 32-bit ARM, stepped quotient/remainder interpolation now covers exact reciprocal depth and perspective UV weights. A regular and forced-path host benchmark produced identical image checksums for the textured mall at both sizes (`1A09E13438A6E3FB` at 120×160; `E98427829E3CDD87` at 240×320) and for the exact-depth plaza (`4EF4962D9063D95B`; `75114656622C3161`). ARMv5TE compilation and regular/forced regression suites passed. Forced-host timings are not useful for ARM speed estimates; device-side frame timings still need measurement on the target handset.

The playable `examples/LostLatencyMallDemo` uses the same 120×160 software 3D target. Since its sky gradient replaces every color pixel, depth-only clearing removes 38,400 redundant RGB565 writes (76,800 bytes written) from each world frame, without changing the captured PPM image (pre/post SHA-256 matched). Core rasterization also skips triangles whose projected bounds are fully offscreen. The mall gameplay regression and ARM VXP build pass with these paths enabled.

## Reference images

![2.5D billboard path, 240×320](2.5d_240x320.png)

![Textured retro mall walkthrough, 240×320](retro_mall_3d_240x320.png)

![Camera drift with animated fountain water and fish](retro_mall_motion.gif)

![3D exact depth, 240×320](3d_exact_240x320.png)

![3D affine depth, 240×320](3d_affine_240x320.png)
