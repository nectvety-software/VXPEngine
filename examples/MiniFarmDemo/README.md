# MiniFarmDemo

VXPGDX sample built from the optimized assets in `D:\MRE\Nokia2D\mini-farm`.

The selected source assets are copied into `assets_source/`, so the example is
self-contained after creation. Build-time tools use Python standard library only.

## VXPEngine features exercised

- AssetManager + VXA8
- TextureAtlas / VXAT
- TiledMap v3 / VXTM
- TiledMapRenderer + camera culling
- tile collision properties
- OrthographicCamera
- SpriteBatch z sorting
- Animation
- Scene2D Stage / Panel / Label
- ScrollPane + List inventory
- fixed particle pool
- mutable tile gameplay (hoe / seed / harvest / water)

## Controls

- Arrow keys or 2/4/6/8: move
- 5 / OK: use selected tool on tile in front
- 0: next tool
- 1: open inventory
- Inventory: Up/Down select, 5/OK activate, 1/Back close
- Back: exit

Gameplay tool cycle:
HOE -> SEED -> HARVEST -> WATER.

Build:
`build_arm.bat`

Run:
`run_vxpemu.bat`
