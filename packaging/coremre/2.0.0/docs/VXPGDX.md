# VXPGDX

VXPGDX is VXPEngine's lightweight, LibGDX-inspired C++17 facade for MRE/VXP.
It keeps the familiar game-framework structure while using VXPEngine's RGB565,
VXA8, fixed-memory VFX and MRE-friendly runtime underneath.

## API mapping

| LibGDX concept | VXPGDX |
| --- | --- |
| ApplicationAdapter | `vxpe::gdx::ApplicationAdapter` |
| Game | `vxpe::gdx::Game` |
| Screen | `vxpe::gdx::Screen` |
| Gdx.graphics | `vxpe::gdx::Gdx::graphics()` |
| Gdx.input | `vxpe::gdx::Gdx::input()` |
| Texture | `vxpe::gdx::Texture` (VXA8) |
| TextureRegion | `vxpe::gdx::TextureRegion` |
| SpriteBatch | `vxpe::gdx::SpriteBatch` |
| Animation | `vxpe::gdx::Animation` |
| OrthographicCamera | `vxpe::gdx::OrthographicCamera` |
| AssetManager | `vxpe::gdx::AssetManager<N>` |
| ShapeRenderer | `vxpe::gdx::ShapeRenderer` |
| ParticleEffect-like runtime | `VxpParticlePool` |
| shader/bloom substitute | `VxpLight2D` + `VxpVfx2D` |
| camera shake / hit stop | `VxpCinematic2D` |

## Minimal game

```cpp
#include "vxpgdx/VxpGdx.h"
using namespace vxpe::gdx;

class PlayScreen : public Screen {
public:
    SpriteBatch batch;
    Texture* hero = nullptr;
    uint16_t* framebuffer = nullptr;

    void render(float delta) override {
        (void)delta;
        batch.begin(framebuffer, 240, 320);
        if (hero) batch.draw(*hero, 80, 120);
        batch.end();
    }
};

class MyGame : public Game {
public:
    PlayScreen play;
    void create() override {
        setScreen(&play);
    }
};
```

## MRE design differences

VXPGDX intentionally does not emulate OpenGL. Rendering is software RGB565 with
VXA8 per-pixel alpha. Runtime effects use fixed-capacity buffers and integer or
fixed-point hot paths. AssetManager is synchronous and fixed-capacity instead of
threaded/asynchronous. SpriteBatch is depth-sorted and backed by the VXPEngine
fixed command buffer.

The goal is the LibGDX programming model, not binary/API compatibility with
LibGDX itself.

## TiledMap + TextureAtlas

VXPGDX now includes:

- `vxpgdx/TextureAtlas.h`
  - `TextureAtlas<MaxRegions>`
  - `AtlasRegion`
  - named region lookup
  - fixed-capacity metadata, no heap
  - one VXA8 page per atlas
  - optional binary `VXAT v1` descriptor parser

- `vxpgdx/TiledMap.h`
  - `TiledMap<MaxLayers>`
  - `TiledMapTileLayer`
  - `TiledMapCell`
  - `TiledMapRenderer<AtlasRegions>`
  - orthogonal and isometric layouts
  - camera culling
  - per-layer opacity, offset, visibility and z
  - horizontal/vertical tile flip bits
  - fixed per-frame tile safety cap
  - optional zero-copy `VXTM v1` parser

### Atlas example

```cpp
Texture tiles;
tiles.loadVxa8(vxa8Data, vxa8Size);

TextureAtlas<64> atlas;
atlas.setTexture(tiles);
atlas.addRegion("grass", 0, 0, 16, 16);
atlas.addRegion("stone", 16, 0, 16, 16);
```

Tile IDs are atlas region indices. `0xFFFF` is empty. Bit `0x8000`
flips X, bit `0x4000` flips Y, leaving 14 bits for the region index.

### Tiled map example

```cpp
static uint16_t ground[20 * 20];

TiledMapTileLayer layer;
layer.cells = ground;
layer.width = 20;
layer.height = 20;
layer.tileWidth = 16;
layer.tileHeight = 16;

TiledMap<4> map;
map.addLayer(layer);

OrthographicCamera camera(240, 320);
TiledMapRenderer<64> renderer;
renderer.setView(camera);

batch.begin(framebuffer, 240, 320);
renderer.render(map, atlas, batch);
batch.end();
```

`SpriteBatch` now auto-flushes its fixed 48-command buffer, so a visible
tilemap can exceed 48 tiles without dropping draw commands.

## Scene2D

`vxpgdx/Scene2D.h` adds a fixed-memory scene graph inspired by LibGDX Scene2D:

- `scene2d::Actor`
- `scene2d::Group`
- `scene2d::Image`
- `scene2d::Stage`
- `scene2d::InputListener`
- `scene2d::ClickListener`
- `scene2d::Touchable`

Stage and Group keep non-owning Actor pointers. Game code can therefore place
actors in static storage or a VXPEngine scene arena. No ownership heap is
required by Scene2D.

```cpp
using namespace vxpe::gdx::scene2d;

Image hero(heroRegion);
hero.setBounds(80, 120, 48, 64);

Stage stage(240, 320);
stage.addActor(hero);

stage.act(delta);
stage.draw(framebuffer, 240, 320);
```

Touch routing performs reverse-order hit testing and capture. An Actor that
accepts `touchDown` keeps touch focus until `touchUp`, allowing drag controls
without losing the pointer when it leaves the original bounds.

Groups support nested coordinate spaces, child ordering, `setZIndex` and
`toFront`. Stage also provides keyboard focus.

### MRE limits by design

Defaults are intentionally bounded for predictable RAM:

- SpriteBatch: 48 pending commands, auto-flushed
- Scene2D Group: 24 direct children per Group
- TextureAtlas: template-selected region capacity
- TiledMap: template-selected layer capacity
- TiledMapRenderer: 320 tiles/frame safety cap by default

These capacities are compile-time/runtime tunable and avoid dynamic containers
inside the frame loop.

## Scene2D UI

`vxpgdx/Scene2DUI.h` adds lightweight UI widgets on top of Stage/Actor:

- `ui::BitmapFont5x7` (standalone, no Renderer/Arduino dependency)
- `ui::Widget`
- `ui::Label`
- `ui::Panel`
- `ui::Button`
- `ui::TextButton`
- `ui::ImageButton`
- `ui::Table<MaxCells>`
- `ui::ScrollPane`
- `ui::List<MaxItems>`
- `ui::LabelStyle`, `ui::ButtonStyle`, `ui::ScrollPaneStyle`, `ui::ListStyle`
- left/center/right label alignment
- pressed/disabled button state
- fixed callback pointer + user data, no std::function
- fixed grid layout through Table
- nested software clipping for sprite + text + widget backgrounds
- ScrollPane tap delegation: tap reaches child, drag becomes scrolling
- List selection by touch or configurable keypad keys

Example:

```cpp
using namespace vxpe::gdx::scene2d;
using namespace vxpe::gdx::scene2d::ui;

Label title("Inventory");
TextButton useButton("USE");

Table<8> hud;
hud.setBounds(4, 250, 232, 64);
hud.setGrid(2, 1, 3);
hud.add(title, 0, 0);
hud.add(useButton, 1, 0);

Stage stage(240, 320);
stage.addActor(hud);
stage.act(delta);
stage.draw(framebuffer, 240, 320);
```

The UI font is copied into `vxpgdx/TinyFont5x7.h` as compact row data, so including
Scene2D UI no longer pulls the legacy Renderer/Arduino headers into host tools.

## TiledMap pipeline v3

Runtime `VXTM v3` carries the extended Tiled workflow while the loader remains compatible with VXTM v1/v2:

- tileset `firstGid` to atlas-region mapping
- tile flags: solid, trigger, damage, water, ladder
- animated tile frame metadata
- tile layers with opacity, visibility, z, offset, parallax and RGB565 tint
- object layers with object id, name, class/type, bounds and rotation
- runtime tile-property queries for collision/gameplay
- orthogonal and isometric rendering
- camera culling and per-layer parallax
- animation time supplied by `TiledMapRenderer::setAnimationTime()`
- all 8 orthogonal/isometric H/V/diagonal tile transform combinations
- VXTM v1/v2 backward compatibility

Build tools:

```text
tools/vxpgdx_pack_atlas.py
tools/vxpgdx_pack_tiled.py
```

Atlas metadata:

```bash
python tools/vxpgdx_pack_atlas.py atlas_regions.json game.vxat
```

Tiled JSON/TMJ map:

```bash
python tools/vxpgdx_pack_tiled.py level01.tmj level01.vxtm
```

External TSJ tilesets are resolved relative to the TMJ map. If several tilesets
share one packed VXA8 page, an optional JSON map can define each tileset's first
atlas region:

```bash
python tools/vxpgdx_pack_tiled.py level01.tmj level01.vxtm --atlas-map atlas_bases.json
```

Example `atlas_bases.json`:

```json
{
  "terrain": 0,
  "props": 128,
  "dungeon": 192
}
```

Recognized boolean tile properties are `solid`/`collision`/`blocked`,
`trigger`, `damage`/`hazard`, `water`, and `ladder`. A numeric
`vxpe_flags` property can supply the bitmask directly.

For predictable MRE memory, the current packer intentionally targets finite
Tiled JSON/TMJ maps with uncompressed gid arrays. VXTM v3 stores horizontal,
vertical and diagonal transform bits and applies the Tiled operation order:
diagonal axis swap first, then horizontal and vertical flips. Because the fixed
16-bit cell reserves three transform bits plus the empty sentinel, packed GIDs
must be in the usable range 1..8190. The runtime still reads older VXTM v1/v2
cells using their legacy 14-bit GID layout.

## VXTM v3 regression suite

The repository and packaged SDK now include standalone CTest coverage under
`engine/coremre/tests` / `tests`. It does not require the MRE SDK or
`vmsys.h`; the test target links only the renderer pieces needed by VXPGDX.

```bash
cmake -S engine/coremre/tests -B engine/coremre/build-vxpgdx-tests -G "MinGW Makefiles"
cmake --build engine/coremre/build-vxpgdx-tests
ctest --test-dir engine/coremre/build-vxpgdx-tests --output-on-failure
```

Coverage includes VXTM v1/v2 compatibility, VXTM v3 H/V/diagonal cell decoding,
all eight rendered transform combinations, tileset flags, animated tiles,
object layers, malformed/truncated input, the TMJ packer, and the v3 GID
sentinel boundary.

## ARM UI hot-path notes

`ScrollPane` keeps scroll positions, content sizes, max ranges and scrollbar
math in integer pixels. Layout is cached and only refreshed when the viewport,
content preferred size, or widget layout revision changes. Float coordinates
remain at the Scene2D Actor boundary for API compatibility.

`List` caches its preferred width/height, updates width incrementally when
items are appended, and renders only the row range intersecting the current
clip rectangle. `BitmapFont5x7::drawScreen()` caches framebuffer and clipping
once per string and writes clipped glyph pixels directly instead of performing
a clip lookup/fill call for every lit font pixel.

The ARM regression is compiled with `-Os -fno-exceptions -fno-rtti`. Its
current ScrollPane/List object has no unresolved `__aeabi_fmul` or
`__aeabi_fdiv` symbols; remaining soft-float helpers come from the existing
float-based Scene2D Actor coordinate API.

## VxpScene25D

VxpScene25D is the fixed-memory 2.5D compositor for perspective video-inspired scenes. It provides fixed-point camera projection, depth-scaled billboards, textured trapezoid planes with optional ripple, projected ellipse shadows, world-space rope/line drawing, fog tint and low-cost colour grading/dither. Use it with VxpLight2D/VxpVfx2D/ParticlePool rather than a heavy true-3D pipeline on MRE.
\n## VxpStage2D\n\nVxpStage2D is the fixed-memory compositor for classic horizontal fighting/arcade stages. It provides a dead-zone horizontal camera, repeated parallax bands, scanline raster-wave water/haze, scrolling/tint controls and a low-cost RGB565 colour cycle helper. Use it for Saturn/PS1/Neo Geo-style backgrounds; use VxpScene25D when the reference depends on depth projection.\n\n## Legacy MRE asset import\n\nEditor Assets can import flat legacy `res/` trees and reorganize them into VXPEngine categories while preserving binary ANI/VPEA/JMP/JOP descriptors byte-for-byte. The importer writes `assets/legacy/legacy_assets.catalog.json` with category, target path, SHA-256 and basename pairing metadata. Unknown numeric/project-specific resources stay under `assets/legacy/misc` until their runtime role is known.\n\n## Legacy Asset Browser\n\nThe Editor Assets **Legacy** tab reads `assets/legacy/legacy_assets.catalog.json`, displays cached image/paired-asset thumbnails, filters by category/search text, and edits catalog-only metadata (`category`, `display_name`, `role`, `tags`, `notes`). Binary animation descriptors remain byte-identical; paired image previews can be opened on the canvas.\n
## StrategyRPG

`vxpgdx/StrategyRPG.h` adds fixed-memory building blocks for QVGA kingdom/tactics RPGs: nine-patch skins, a screen stack, multilingual string tables, tactical grid overlays, world-map nodes, softkey bars, dialogue panels and victory/result panels. It is header-only and designed to compose with `Scene2DUI`, `TextureAtlas` and `TiledMap`.

## Multi-style ArtStyle pipeline

VxpArtStyle provides fixed-memory runtime visual profiles that compose with SpriteFx, Scene25D, Light2D and Vfx2D. Editor Assets stores the matching art_style block in .asset.dtfe. Profiles cover pixel, cozy, dark fantasy, neon, pastel, handheld, cel-shaded, saturated adventure, strategy RPG, painterly and low-poly 2.5D looks.
