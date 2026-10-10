# Tactics Kingdom — VXPEngine sample game

Turn-based tactics for MRE VXP (240x320) in the style of classic handheld
strategy RPGs: a 15x20 tile kingdom (grass, forest, mountains, lake, roads,
castle, tower), 4 blue knights vs 3 red soldiers.

## Play

- Arrows/`2468`: move cursor. `5`/OK: select unit → blue move-range overlay →
  confirm tile to move (auto-attacks adjacent foe). OK on selected unit: cancel.
- Enemies act greedily on their phase; castles heal +2 each turn and halve damage.
- Win by routing all foes; lose if your squad falls. OK restarts. Right softkey exits.

## Build & run

```bat
build_arm.bat     :: -> build-arm\main\tactics_kingdom.vxp (APPID 6052703, dev)
run_vxpemu.bat    :: build + launch VXPEmu
```

Retail: rebuild with the engine-signed flow (`certid 100`, per-app key —
see `docs/BUILD_VA_KY_VXP.md`); keys never live in the project.
