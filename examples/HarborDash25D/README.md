# Harbor Dash 2.5D — VXPEngine sample game

2.5D arcade sailor for MRE VXP (240x320, Nokia 225/220) built on
`VxpScene25D`: perspective sea plane with ripple, depth-sorted billboards
(boat, buoys, coins), distance fog and color grade. All sprites are
procedural — no external assets needed.

## Play

- `4/6` or arrows: steer left/right. `2/8`: speed down/up.
- Dodge red buoys (−1 life), collect gold coins (+10).
- `5`/OK restarts after game over. Right softkey exits.

## Build & run

```bat
build_arm.bat     :: -> build-arm\main\harbor_dash_25d.vxp (APPID 6052701, dev)
run_vxpemu.bat    :: build + launch VXPEmu
```

Retail: rebuild with the engine-signed flow (`certid 100`, per-app key —
see `docs/BUILD_VA_KY_VXP.md`); keys never live in the project.
