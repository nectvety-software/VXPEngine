# Prompt: create a memory-aware VXPEngine game

Create or update a game project for VXPEngine/MRE. First inspect its template, build flow, runtime APIs, existing game code, and asset pipeline. Preserve the requested resolution and controls.

## Persistence and public cache

Every newly generated game project should contain a small reusable cache scaffold. Use a unique folder under public storage (removable card when available, system storage otherwise), such as `\\@vxp_<app-id>\\`. Do not assume the app can discover the `.vxp` install directory. Store only progress/options/world seed or other data that must survive app exit. Use a versioned header and exact payload-size checks. Write to a temporary file, commit it, and rename it into place; recover a valid temporary file if the previous write was interrupted. Save at checkpoints, menu transitions, or a measured interval, never every frame. Display the chosen save location in a settings/help surface when appropriate. If writing is unavailable, the game must continue with in-memory state.

## Assets and memory

Keep high-quality editable source art separate from shipped runtime assets. Use compact runtime formats supported by the engine: RGB565 pixel atlases, packed transparency masks, shared spritesheets, cropped transparent margins, and reproducible conversions. Preserve palette detail and silhouettes; compare source and packaged output before adopting lossy reductions. Avoid loading unrelated large assets and avoid per-frame allocations. State the measured or estimated asset/RAM savings and any quality tradeoff.

## Graphics profile: retro 2.5D / low-poly 3D

When the reference calls for PS1/N64-era low-poly spaces, mallwave/liminal interiors, aquariums, or a moving 3D camera, preserve that visual goal with the lightest suitable renderer. Use `VxpScene25D` with billboards and perspective planes when draw order is predictable; use `VxpToon3D` for camera yaw/pitch and depth-tested occlusion. Prefer few-face geometry, small tileable RGB565 textures, nearest-neighbour sampling, per-face baked/static lighting, and depth fog. Use original signage and symbols.

For 240x320 targets, evaluate a 120x160 world render with caller-owned RGB565 color and 16-bit depth buffers (76.8 KB combined), then upscale the world and draw text/UI at native resolution. Keep texture conversion deterministic and outside the frame loop. Animate water with a small UV phase, fish with a few billboard states/LUT motion, and camera drift from elapsed time. Keep all render-frame state bounded and preallocated.

On 32-bit ARM, retain scanline edge stepping and exact quotient/remainder stepping for reciprocal depth and perspective UV weights. Do not replace perspective-correct UVs with affine mapping just to save divisions. Treat affine depth as an opt-in approximation only for untextured, unfogged, uniformly lit faces with separated depths. Validate with host regressions, a forced `VXPE_TOON3D_STEPPED_RECIPROCAL` image comparison, and ARMv5TE compilation; report device FPS only after testing on the actual device. See `docs/CORE_25D_3D_RENDERING.md`, `reports/graphics-benchmark/README.md`, and `ai/skills/vxpengine-agent/SKILLS.md` Skill 32.

If a sky/gradient pass fully covers the target color buffer, initialize depth with `vxpe_toon3d_clear_depth` instead of clearing color only to overwrite it immediately. Keep the regular full clear for flat-color backgrounds. The rasterizer coarse-rejects triangles whose projected bounds miss the target; still cull world chunks before submitting very large meshes.

For portrait arcade racing that references Super Hang-On/OutRun-era Super Scaler visuals, use the fixed-point scanline road in `graphics/VxpSuperScaler.h`: narrow road at the horizon, expanding width, Q8 bends, alternating curbs, lane dashes, distant terrain and sprites sorted far-to-near. Prefer integer LUTs and horizontal spans over per-pixel ray math. Add a playable test scene with steering, acceleration, braking/boost, traffic and pause; use original bike silhouettes and signage. Run `docs/SUPERSCALER_ROAD.md` regressions and cross-compile ARMv5TE. Never claim target FPS based on a host screenshot or benchmark.

## Gameplay

Implement requested systems with bounded state: fixed-size pools, explicit cooldowns/ranges, collision bounds, and finite-duration effects. Give attacks and status effects readable, distinct colors/shapes, safe hit feedback, and predictable counters. For enemies, test approach/attack/recovery, player damage, status expiry, and memory bounds. Persist these states only if required for continue/replay.

## Completion checks

Build the host version and target ARM/VXP package; run relevant gameplay tests and emulator checks for new controls, cache write/load, and packaged visuals. Confirm source art and cache files are not accidentally bundled into the VXP. Document changed files, cache path/format, test results, package size, and limitations.
