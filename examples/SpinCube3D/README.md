# Spin Cube 3D — VXPEngine sample game

3D sample for MRE VXP (240x320) built on the clean-room `VxpSoft3D` module:
a textured cube spins with perspective-correct UV interpolation, 16-bit
depth testing, baked per-face illumination and distance fog — all integer
math, no FPU, ~300KB static buffers.

## Play

- `4/6`: orbit yaw. `2/8`: pitch. `5`/OK toggles auto-spin.
- HUD: FPS bar + spin indicator. Right softkey exits.

## How it works

- `graphics/VxpSoft3D.h`: `mesh16` textured path, `bake_vertex_light` at init
  (object-space light fixed at +Z), `camera_init`/`clear` per frame.
- Rotation uses a 256-entry integer sine LUT (Taylor-built at startup).
- Offline bake companion: `engine/coremre/tools/vxp_bake_light.py`.

## Build & run

```bat
build_arm.bat     :: -> build-arm\main\spin_cube_3d.vxp (APPID 6052702, dev)
run_vxpemu.bat    :: build + launch VXPEmu
```

Retail: rebuild with the engine-signed flow (`certid 100`, per-app key —
see `docs/BUILD_VA_KY_VXP.md`); keys never live in the project.
