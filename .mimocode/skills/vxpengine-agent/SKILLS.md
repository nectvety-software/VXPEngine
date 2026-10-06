# VXPEngine / VXPGDX — SKILLS

Tài liệu recipe cho AI agent làm việc với lõi mới. `PROMPT.md` là operating contract; file này là cookbook thực thi.

## Skill 1 — Khảo sát core trước khi sửa

```text
1. git status --short
2. đọc public header
3. tìm implementation
4. tìm sample đang dùng API
5. tìm regression test
6. xác định package/export path
```

Ưu tiên `engine/coremre/include/vxpgdx/`, `graphics/`, `physics/`, `engine/coremre/tests/`, `docs/VXPGDX.md`, `examples/MiniFarmDemo/`.

## Skill 2 — Tạo sample từ asset folder

1. Liệt kê asset + kích thước.
2. Xác định tile/frame/UI.
3. Giữ nguyên source asset.
4. Copy runtime subset nếu sample cần self-contained.
5. Viết `tools/generate_assets.py` deterministic.
6. Sinh VXA8 + atlas JSON.
7. Pack VXAT + VXTM v3.
8. Code gameplay bằng VXPGDX.
9. Build ARM.
10. Chạy VXPEmu và test interaction.

Reference: `examples/MiniFarmDemo/`.

## Skill 3 — TextureAtlas/VXA8

```cpp
AssetManager<2> assets;
assets.configure(loadFn, freeFn);
assets.loadTexture("game.vxa8");
Texture* texture = assets.getTexture("game.vxa8");

TextureAtlas<96> atlas;
atlas.loadVxat(*texture, vxatBytes, vxatSize);
const AtlasRegion* hero = atlas.findRegion("hero_idle");
```

Pack metadata:

```bat
python tools\vxpgdx_pack_atlas.py atlas.json game.vxat
```

Lookup tên ở setup; giữ pointer/index cho hot loop nếu cần.

## Skill 4 — TiledMap/VXTM v3

```cpp
TiledMap<4,4,2,64,16> map;
map.loadVxtm(data, size);

OrthographicCamera camera(240,320);
TiledMapRenderer<96> renderer;
renderer.setView(camera);
renderer.setMaxTilesPerFrame(360);

batch.begin(fb,240,320);
renderer.render(map,atlas,batch);
batch.end();
```

Collision query:

```cpp
if (map.cellHasFlags(0, tx, ty, TileFlagSolid)) {
    // blocked
}
```

Animation: `renderer.setAnimationTime(gameTimeMs);`.

VXTM v3 bits: H=`0x8000`, V=`0x4000`, D=`0x2000`, GID=`0x1FFF`, empty=`0xFFFF`.

## Skill 5 — Camera + culling

```cpp
int cx = clamp(playerX - 120, 0, worldW - 240);
int cy = clamp(playerY - 160, 0, worldH - 320);
camera.setPositionQ8(cx << 8, cy << 8);
renderer.setView(camera);
```

Không render toàn map; dùng TiledMapRenderer camera culling.

## Skill 6 — SpriteBatch

```cpp
batch.draw(region, x, y, w, h, tint, alpha, VXPE_BLEND_ALPHA,
           flipX, flipY, z, flipDiagonal);
```

Dùng atlas/source rect thay vì texture riêng từng frame. Batch tự auto-flush.

## Skill 7 — Animation

```cpp
VxpeRectI frames[5];
Animation walk(texture, frames, 5, 120, true, false);
walk.update(deltaMs);
TextureRegion frame = walk.getKeyFrame();
```

Time-based, không frame-count-based.

## Skill 8 — Scene2D HUD/UI

```cpp
using namespace vxpe::gdx::scene2d;
using namespace vxpe::gdx::scene2d::ui;

Stage stage(240,320);
Panel hud;
Label title("FARM");
hud.addActor(title);
stage.addActor(hud);
```

Frame:

```cpp
stage.act(deltaSeconds);
stage.draw(framebuffer,240,320);
```

Input:

```cpp
stage.touchDown(x,y,0,0);
stage.touchDragged(x,y,0);
stage.touchUp(x,y,0,0);
```

Actor lifetime phải ổn định vì Group/Stage giữ non-owning pointers.

## Skill 9 — ScrollPane + List

```cpp
List<16> list;
list.addItem("A");
list.addItem("B");

ScrollPane pane;
pane.setBounds(8,27,188,180);
pane.setWidget(list);
```

ARM-friendly:

```cpp
pane.setScrollPixels(0,y);
int maxY = pane.getMaxScrollYPixels();
```

Test đúng phải có content > viewport, tap callback, drag scroll, không click nhầm và thấy bottom items.
MRE pen path phải forward `TAP → touchDown`, `MOVE → touchDragged`, `RELEASE/ABORT → touchUp`.

## Skill 10 — Particle VFX

```cpp
VxpeParticlePool pool;
vxpe_particles_init(&pool, VXPE_PARTICLE_POOL_MAX);

VxpeParticleSpawn p{};
p.x=x; p.y=y;
p.vx_q8=vx; p.vy_q8=vy; p.ay_q8=gravity;
p.lifetime_ms=400;
p.color565=0xFFFF; p.tint565=tint;
p.alpha_start=220; p.alpha_end=0;
p.size_start=2; p.size_end=1;
p.blend=VXPE_BLEND_ALPHA;
vxpe_particles_spawn(&pool,&p);
```

Frame: `vxpe_particles_update` + `vxpe_particles_draw`.

## Skill 11 — Particle physics

```cpp
VxpeParticlePhysicsWorld world{};
world.bounds_enabled=1;
world.bounds_response=VXPE_PARTICLE_COLLISION_BOUNCE;
world.colliders=colliders;
world.collider_count=count;

VxpeParticleCollisionEvent events[8];
vxpe_particles_update_physics(&pool,deltaMs,&world,events,8);
```

Responses: NONE / BOUNCE / STOP / KILL.

## Skill 12 — Tile collision nhẹ

```cpp
int tx = worldX / tileW;
int ty = worldY / tileH;
bool blocked = map.cellHasFlags(layer,tx,ty,TileFlagSolid);
```

Với mutable map, copy cell layer vào caller-owned RAM rồi trỏ `layer.cells` sang buffer đó.

## Skill 13 — Full physics

Headers:

```cpp
#include "physics/CollisionSystem.h"
#include "physics/KinematicActor.h"
#include "physics/RigidActor.h"
#include "physics/PhysicsScheduler.h"
```

Character dùng `KinematicActor::moveAndSlide` / `moveAndCollide`.
Dynamic body dùng `RigidActor`.
World dùng `PhysicsScheduler` fixed timestep.
Dùng SpatialGrid/query cho area lookup và `TileCollisionBuilder` khi behavior layer cần body/sensor.

## Skill 14 — Rich 2D/2.5D

Lower-level modules khi facade chưa đủ:

```text
graphics/VxpRender2D.h
graphics/VxpSpriteFx.h
graphics/VxpLight2D.h
graphics/VxpCinematic2D.h
graphics/VxpVfx2D.h
```

Techniques: parallax, radial light, additive glow, multiply shade, camera shake, perspective floor, sprite-scale depth, particle trail.

## Skill 15 — Tối ưu ARM

Checklist:

```text
[ ] không allocation trong frame
[ ] fixed-capacity
[ ] camera culling
[ ] visible-row culling
[ ] cached layout/preferred size
[ ] integer UI hot path
[ ] atlas/batching
[ ] dense particle active list
[ ] 30 FPS khi phù hợp
```

Compile:

```bat
arm-none-eabi-g++ -std=c++17 -Os -fno-exceptions -fno-rtti ^
  -ffunction-sections -fdata-sections ...
```

Inspect: `arm-none-eabi-nm -u object.o`; chú ý `__aeabi_fmul` / `__aeabi_fdiv`.

## Skill 16 — Regression VXTM/UI

```bat
cmake -S engine\coremre\tests -B engine\coremre\build-vxpgdx-tests -G "MinGW Makefiles"
cmake --build engine\coremre\build-vxpgdx-tests
ctest --test-dir engine\coremre\build-vxpgdx-tests --output-on-failure
```

Tests cover v1/v2 compatibility, v3, H/V/D, flags, animation, objects, malformed input, packer, GID boundary và UI.

## Skill 17 — Build ARM sample

```bat
examples\MiniFarmDemo\build_arm.bat
```

Artifact: `examples/MiniFarmDemo/build-arm/main/mini_farm_demo.vxp`.

Newlib `_read/_write/_close/_isatty` warnings có thể là syscall stubs đã biết; phân biệt warning với link failure thật.

## Skill 18 — Chạy VXPEmu

```bat
examples\MiniFarmDemo\run_vxpemu.bat
```

Test tối thiểu: launch, render, movement, collision, animation, VFX, UI open/close, list selection, scroll/touch nếu có, app remains responsive.

Nếu screenshot/input automation nhắm nhầm browser/Explorer thì test INVALID.

## Skill 19 — Package core

```bat
.venv\Scripts\python.exe tools\pack_core.py
.venv\Scripts\python.exe tools\verify_core.py packaging\coremre\2.0.0
```

Đảm bảo public headers/tools/tests mới được ship.

## Skill 20 — Thêm API kiểu LibGDX

1. Xác định LibGDX analog về ergonomics.
2. Rút gọn cho QVGA/MRE.
3. Fixed-capacity.
4. Ownership đơn giản.
5. Không yêu cầu exception/RTTI.
6. Host regression.
7. ARM compile.
8. Sample sử dụng thật.
9. Docs.
10. Package export.

Không copy nguyên API desktop nếu gây heap pressure hoặc giả định GPU hiện đại.

## Skill 21 — Debug runtime “không thấy gì”

```text
1. .vxp có được tạo?
2. resource pack có asset?
3. vm_load_resource size > 0?
4. framebuffer/layer tạo được?
5. screen size đúng?
6. timer/update chạy?
7. VXPEmu Responding?
8. screenshot đúng cửa sổ?
```

## Skill 22 — Backward compatibility

- Giữ VXTM v1/v2 loader.
- Zero-init public operation structs.
- Test old sample khi đổi renderer.
- Không đổi enum/bit layout tùy tiện.
- Breaking change phải có version mới.

## Skill 23 — MiniFarmDemo testbed

`examples/MiniFarmDemo` đang exercise AssetManager, TextureAtlas, VXTM v3, TiledMapRenderer, camera, SpriteBatch, Animation, tile flags, mutable cells, particle pool, Stage/Panel/Label và ScrollPane/List.

Tính năng mới nên có use case nhỏ tại đây nếu phù hợp: weather, day/night, NPC pathfinding, save/load, animated crops, triggers, camera shake hoặc dialog.

## Skill 24 — Completion checklist

```text
[ ] source-of-truth đúng
[ ] không đụng thay đổi không liên quan
[ ] host compile/regression
[ ] ARM build
[ ] sample .vxp
[ ] VXPEmu nếu runtime task
[ ] behavior đã quan sát
[ ] docs cập nhật
[ ] package verify nếu public core
[ ] chưa commit/push nếu chưa được yêu cầu
```

Báo cáo rõ phần nào PASS và phần nào chưa kiểm chứng.

## Skill 25 — Tái tạo đồ họa từ video bằng VxpScene25D

Dùng khi video tham chiếu có phối cảnh, vật thể scale theo khoảng cách, fog, light hoặc rope/beam mà tilemap 2D không đủ.

### Phân tích video

Tách keyframe ở đầu/giữa/cuối và ghi lại:

```text
camera horizon
perspective plane(s)
billboard objects
foreground occluders
lights / glow
fog / palette tint
rope / fishing line / cable
shadow
particles / splash
UI
```

Không cần true 3D nếu scene có thể biểu diễn bằng textured plane + billboard.

### Runtime recipe

```cpp
#include "graphics/VxpScene25D.h"

VxpeCamera25D cam{};
vxpe25d_camera_init(&cam, 240, 320, 80, 160);
cam.world_y = 64;

VxpePlane25D pool{};
pool.center_x = 120;
pool.top_y = 82;
pool.bottom_y = 248;
pool.top_width = 120;
pool.bottom_width = 330;
pool.ripple_amplitude = 1;
vxpe25d_draw_plane(fb, 240, 320, &waterSprite, &pool);

VxpeBillboard25D object{};
object.world_x = x;
object.world_y = y;
object.world_z = z;
object.world_w = 24;
object.world_h = 24;
object.pivot_x_q8 = 128;
object.pivot_y_q8 = 256;
vxpe25d_draw_billboard(fb, 240, 320, &sprite, &cam, &object);
```

Sau world draw:

```cpp
vxpe25d_draw_ground_shadow(...);
vxpe25d_draw_rope_world(...);
vxpe2d_lightmap_composite_add(...);
vxpe25d_apply_grade(...);
```

### Editor Assets recipe

Chọn một loại:

```text
2.5D / Billboard
2.5D / Perspective Plane
2.5D / Water Surface
```

Mở tab **2.5D**. Với scene kiểu The Water Museum, chọn preset **Water Museum / Green Pool** rồi tinh chỉnh:

- pivot;
- world width/height;
- fog near/far/strength/color;
- plane top/bottom width;
- plane top/bottom Y;
- ripple amplitude;
- shadow radius/alpha;
- grade tint/vignette/dither.

Khi lưu, kiểm tra `*.asset.dtfe` có block `scene25d`; mở lại asset phải restore đúng các giá trị.

### Performance

- perspective plane render scanline, không polygon mesh;
- 1–2 plane lớn mỗi frame là mục tiêu;
- billboard dùng fixed-point projection;
- không heap allocation trong render;
- grade là full-frame pass: chỉ bật khi visual gain đáng giá;
- fog/light có thể render quarter-resolution bằng `VxpLight2D`;
- ưu tiên 30 FPS trên QVGA.

### Regression gate

Chạy `vxpe_scene25d_runtime` trong `engine/coremre/tests`, ARM cross-compile module và test Editor Assets bằng `py_compile` + save/reload metadata.

## Skill 26 — Ký VXP an toàn, không commit khóa

Luồng chuẩn:

```text
project (CERTID=1, CERT=none)
       ↓
Build ARM base VXP
       ↓
%LOCALAPPDATA%/VXPEngine/signing/apps/<appid>-<vendor>/private.pem
       ↓
vxp_signer.py
       ↓
<app>-signed.vxp (certid 100)
```

Quy tắc:

1. Dùng `signing_service.ensure_signing_identity(project)`; không tự copy key vào project.
2. Nếu gặp identity legacy trong source tree, giữ identity canonical cũ hơn/đã dùng và di chuyển bản legacy ra AppData. Nếu hai key khác nhau, không xóa bừa; lưu conflict ngoài Git.
3. `Build ARM` là unsigned cho dev/VXPEmu; dùng `Build ARM Signed` cho artifact ký.
4. Signer phải in `VERIFY : OK`, đúng App ID/vendor và `CERT ID : 100`.
5. Project `.gitignore` và repo `.gitignore` phải chặn private-key formats.
6. Trước commit/push: kiểm tra `git status --short`, xác nhận không có `signing/` hay private-key file được stage/tracked; không commit `.vxp`, `.sha256` build output nếu không phải release workflow riêng.
7. Không log hoặc trả về nội dung private key; fingerprint/public key metadata thì được.

## Skill 27 — Stage2D kiểu Saturn/Neo Geo từ video

Dùng khi video có camera ngang và background nhiều lớp nhưng không cần perspective 2.5D.

Pipeline:
```text
video keyframes
  -> sky
  -> slow parallax cliff/background
  -> raster water/cloud band
  -> ground/foreground
  -> fighter sprites
  -> splash/impact particles
  -> HUD
```

Core recipe:
```cpp
#include "graphics/VxpStage2D.h"
VxpeStageCamera2D cam{};
vxpe_stage_camera_init(&cam, 240, 480);
vxpe_stage_camera_follow(&cam, fighter_world_x, 64);

VxpeStageBand2D water{};
water.dst_y = 92;
water.dst_h = 126;
water.parallax_q8 = 90;
water.repeat_x = 1;
water.raster_wave = 1;
water.wave_amplitude = 3;
water.wave_shift = 2;
water.wave_phase = frame & 15;
vxpe_stage_draw_band565(fb, 240, 320, &waterTexture, &cam, &water);
```

Editor Assets:
- `Stage2D / Parallax Layer`
- `Stage2D / Water Band`
- `Stage2D / Ground`
- `Stage2D / Foreground`

Preset `Retro Beach Fighter / Saturn` starts at ~35% water parallax, scanline wave amplitude 3, Y around 92 and a full-width repeat. Save/reload must preserve the `stage2d` metadata block.

Performance rules:
- 3-5 stage bands maximum on QVGA;
- raster-wave only where it creates visible motion;
- use RGB565 nearest-neighbour;
- reuse ParticlePool for splash/impact;
- camera and scrolling remain integer/fixed-point;
- target 30 FPS on ARM/VXPEmu.

## Skill 28 — Nhập resource từ các project MRE cũ

Dùng cho project có cấu trúc kiểu:
```text
game/
  res/
    bg1.png
    hero1.gif
    hero1.ani
    boss1.gif
    boss1.ani
    fire.gif
    coin0.png
    menu_bg.gif
    stage.map
    theme.mid
```

Trong Editor Assets chọn **Nhập res cũ** (`Ctrl+Alt+R`) và chọn thư mục `res/`.

Importer:
1. quét recursive;
2. phân loại background/character/enemy/boss/effect/item/ui/audio/map;
3. giữ unknown trong `assets/legacy/misc`;
4. giữ binary descriptor nguyên byte;
5. nếu `.ani/.vpea/.jmp/.jop` cùng basename với image thì đặt descriptor cạnh image và ghi `paired_asset` trong catalog;
6. xử lý collision bằng tên suffix thay vì ghi đè file khác nội dung;
7. không ghi absolute source path vào catalog.

Regression bắt buộc:
```text
python reports/harness_legacy_asset_import.py
```

Với corpus thực `Transform Robots`, smoke target hiện tại là 138 files và pairing `boss1_1.ani -> assets/scenes/bosses/boss1_1.gif` phải giữ nguyên byte.

## Skill 29 — Legacy Asset Browser / metadata editor

Trong Editor Assets mở tab **Legacy** sau khi dùng `Nhập res cũ`.

Browser hỗ trợ:
- thumbnail grid;
- filter category;
- search theo filename/role/tag/note;
- large preview;
- paired preview cho descriptor binary;
- chỉnh `category`, `display_name`, `role`, `tags`, `notes`;
- double-click để mở ảnh/paired asset lên canvas.

Metadata được ghi vào `assets/legacy/legacy_assets.catalog.json`; không sửa bytes của `.ani/.vpea/.jmp/.jop`.

Regression:
```text
python reports/harness_legacy_asset_editor.py
```

Real-corpus smoke với Transform Robots phải giữ:
```text
138 assets total
boss category = 8
boss1_1.ani preview -> boss1_1.gif
```

## Skill 30 — Strategy RPG UI 240x320

Header:
```cpp
#include "vxpgdx/StrategyRPG.h"
```

Core primitives:
- `NinePatch` — scalable ornate frames/buttons from one atlas region;
- `ScreenStack` — fixed-capacity screen/navigation stack with simple transitions;
- `LocalizationTable` — fixed multilingual lookup with English fallback;
- `StrategyGrid` — battle-grid cursor plus move/attack/skill overlays;
- `WorldMap` — stage nodes with Locked/Open/Cleared state and up to 3 stars;
- `drawSoftkeyBar`, `drawDialogueBox`, `drawResultPanel` — QVGA UI helpers.

Recommended composition:
```text
TextureAtlas -> medieval skin/portraits/icons/units
TiledMap     -> town/battle/world backgrounds
Scene2DUI    -> menus, lists, settings, build/army panels
StrategyRPG  -> skin, navigation, localization, battle/world/dialog/result
```

Regression:
```text
vxpgdx_strategy_rpg_regression
```

## Skill 31 ? Multi-style game graphics

Use graphics/VxpArtStyle.h. Profiles include Pixel Classic/Modern, Cozy Farm, Dark Fantasy, Neon Action, Pastel Platformer, Retro Handheld, Cel-Shaded Cartoon, Saturated Adventure, Strategy RPG, Painterly Fantasy and Low-Poly 2.5D. For jungle/cartoon traversal references prefer VXPE_ARTSTYLE_SATURATED_ADVENTURE with teal depth fog, warm light and cyan movement trails.
