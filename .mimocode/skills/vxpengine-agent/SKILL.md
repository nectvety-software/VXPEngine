---
name: vxpengine-agent
description: Develop, inspect, optimize, build and test VXPEngine/VXPGDX MRE games and core. Use for VXA8/VXAT, VXTM v3/TiledMap, Scene2D UI, ScrollPane/List, particle pool, physics/collision, ARM optimization, sample projects, packaging and VXPEmu runtime verification.
---

# VXPEngine Agent

Work from `D:\MRE\VXPEngine`.

Read `PROMPT.md` for the full operating contract and `SKILLS.md` for task recipes.

## Default route

For new games, prefer:

`AssetManager → TextureAtlas → TiledMap/TiledMapRenderer → OrthographicCamera → SpriteBatch → Scene2D → ParticlePool`

Use PixelRoot32 physics only when tile flags or particle collision are insufficient.

## Required rules

1. Target QVGA MRE: 240×320 or 320×240.
2. Use VXPEmu for runtime verification.
3. Keep hot paths fixed-capacity and allocation-free where practical.
4. Preserve VXTM v1/v2 compatibility when changing VXTM v3.
5. Run host regression and ARM build for public core changes.
6. Use `examples/MiniFarmDemo` as the primary new-core integration reference.
7. Do not reset unrelated working-tree changes.
8. Do not bypass core signature verification.
9. Do not commit/push unless requested.
10. Never call a runtime/UI test PASS if input or screenshot targeted the wrong window.

## Key references

- `PROMPT.md` — full system prompt
- `SKILLS.md` — implementation recipes
- `docs/VXPGDX.md` — public documentation
- `engine/coremre/tests/` — regression suite
- `examples/MiniFarmDemo/` — integration sample