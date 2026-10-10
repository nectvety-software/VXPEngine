# Pixel art source and integration

The road and terrain tiles are original, hand-authored 8×8 pixel patterns, generated deterministically by `tools/generate_pixel_assets.py`.

- `pixel_art/road_tile.png`: opaque asphalt swatch for Editor Assets; the runtime uses zero-transparent RGB565 detail texels over the scanline road colors.
- `pixel_art/sand_tile.png`: opaque sandstone swatch; the runtime uses its sparse stone/shadow texels over RGB565 terrain.
- `src/pixel_art_tiles.h`: generated runtime arrays; 256 bytes total for both RGB565 overlays.
- Palette: asphalt `#7B7B`, shadow `#4A4A`, glint `#8C8C`; sandstone `#B58C`, pebble `#9C6D`, sunlit stone `#C58C`, dry shadow `#8C60` (RGB565 approximations).

The moving motorcycles, mesas, cactus and HUD are authored as compact native pixel primitives in `src/scene.cpp`. No image-generation tool was available for this run, so no generated image, third-party game sprite, logo or video frame is claimed as source art. There is no AI prompt file for these hand-authored assets.
