# Meadow Rush 2.5D — VXPEngine sample game

First-person 2.5D meadow racer for MRE VXP (240x320, Nokia 225/220) built on
the camera-anchored `VxpScene25D` paths: `vxpe25d_draw_ground` renders the
tiled grass plane with row fog and a seamless horizon, and
`vxpe25d_batch_*` depth-sorts the trees, rocks and bobbing coins (each with a
projected ground shadow) far-to-near every frame. All sprites are procedural —
no external assets needed. A bottom-left frame-time probe bar (1 px/ms,
green/amber/red) shows the cost of one `draw()` pass.

## Play

- `4/6` or LEFT/RIGHT: steer. `2/8` or UP/DOWN: throttle/brake.
- Hold the pen (or a key) for continuous input; pen taps on the left/right
  thirds steer, the middle third brakes.
- Collect gold coins (+10), dodge rocks (-1 life, 3 lives).
- `5`/OK restarts after game over. Right softkey/CLEAR exits.

## Build & run

```bat
build_arm.bat     :: -> build-arm\main\meadow_rush_25d.vxp (APPID 6052901, dev)
run_vxpemu.bat    :: build + launch VXPEmu
```

Retail: rebuild with the engine-signed flow (`certid 100`, per-app key —
see `docs/BUILD_VA_KY_VXP.md`); keys never live in the project.

## Notes from the VXPEmu run (2026-10-11)

- The probe bar saturates at 64 ms under VXPEmu because the emulator is not a
  speed reference; the same frame measures 0.76 ms in the host benchmark
  (`reports/graphics-benchmark/README.md`).
- Driving this sample in the emulator exposed the horizon-seam bug fixed in
  `vxpe25d_draw_ground`: stale rows between the sky and the first textured row
  showed as a black band plus a 1 px tear at `horizon_y`.
