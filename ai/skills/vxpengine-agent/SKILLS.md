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

## Skill 32 — Retro 2.5D / 3D tối ưu MRE

Dùng cho game 240x320 phong cách low-poly cuối 1990s, mall liminal, aquarium, phiêu lưu góc nhìn phối cảnh.

### Chọn renderer

- Billboard + perspective plane (`VxpScene25D`) nếu camera chủ yếu cuộn và thứ tự vẽ biết trước.
- `VxpToon3D` khi cần yaw/pitch, depth occlusion theo pixel, hoặc mesh góc cạnh có ánh sáng mặt.
- Bắt đầu ở 120x160: RGB565 color + depth tốn 76.8 KB; upscale world, sau đó vẽ HUD/text ở 240x320.

### Asset và chuyển động

- Dùng mesh ít polygon, texture RGB565 nhỏ (ví dụ 8x8/16x16), nearest-neighbour và UV wrap.
- Bake ánh sáng vào màu/material theo mặt; dùng depth fog để phân tách lớp.
- Tạo texture từ source qua script deterministic; source chất lượng cao không bắt buộc đóng gói vào VXP.
- Nước/đài phun dùng phase UV hoặc vài sprite frame; cá dùng billboard với LUT. Camera drift tính từ elapsed milliseconds.
- Không decode texture, tạo heap hoặc dựng geometry trong frame loop.

### Tối ưu và kiểm chứng

- Giữ edge stepping và quotient/remainder barycentric stepping trong rasterizer ARM.
- Nếu pass sky/gradient sẽ phủ cả màn hình, dùng `vxpe_toon3d_clear_depth` để tránh ghi màu thừa; geometry ngoài viewport được coarse-reject theo bounding box.
- Texture perspective-correct vẫn là mặc định; affine depth chỉ dùng cho mặt phẳng phẳng, không texture/fog/Gouraud và không gần nhau theo depth.
- Regression: `vxpe_toon3d_runtime`, `vxpe_toon3d_c_api`, `vxpe_scene25d_runtime`.
- So sánh ảnh exact-depth trước/sau bằng host build với `VXPE_TOON3D_STEPPED_RECIPROCAL`, rồi cross-compile `VxpToon3D.cpp` ARMv5TE.
- Xem `docs/CORE_25D_3D_RENDERING.md` và `reports/graphics-benchmark/README.md`; host timings chỉ là so sánh tương đối, không phải FPS máy.

## Skill 33 — Super Scaler pseudo-3D racing

Dùng cho game đua xe arcade góc nhìn sau xe trên màn hình dọc 240×320.

- Ưu tiên `graphics/VxpSuperScaler.h` cho road scanline RGB565: road hẹp ở chân trời, mở rộng về camera, bend Q8, curb luân phiên và lane marker đứt đoạn.
- Renderer không cấp phát heap; dùng LUT depth và span fill. Giữ state actor cố định, cập nhật phase theo tốc độ, không tính float hoặc chia trong vòng lặp pixel.
- Vẽ background/horizon trước, road tiếp theo, rồi roadside objects và traffic từ xa đến gần; scale sprite theo depth và cull ngoài viewport.
- Cho người chơi điều khiển rõ ràng: steer, accelerate, brake/boost, pause. Dùng hình gốc, không tái sử dụng logo/xe/asset có bản quyền.
- Build host regression và ARMv5TE; chỉ công bố FPS sau khi đo trên thiết bị thật. Xem `docs/SUPERSCALER_ROAD.md` và `examples/SuperScalerRacingDemo`.

## Skill 34 — VxpSoft3D (raster 3D mềm cho MRE)

Header: `graphics/VxpSoft3D.h`. C API, caller owns buffers, integer-only.

```c
VxpeSoft3DTarget tgt = {fb, depth, 240, 320};
VxpeSoft3DCamera cam;  vxpe_soft3d_camera_init(&cam, 240, 320);
VxpeSoft3DMaterial mat; vxpe_soft3d_material_init(&mat, albedo565);
VxpeSoft3DLight light; vxpe_soft3d_light_init(&light);
/* bake object-space 1 lần lúc init, không tính lại mỗi frame */
vxpe_soft3d_bake_vertex_light(pos, nrm, NULL, illum, n, &light);
vxpe_soft3d_clear(&tgt, bg);
vxpe_soft3d_mesh16(&tgt, &cam, &mesh, &tex, &mat, NULL);
```

Quy tắc rút từ bug thật:

1. UV phối cảnh: `tu = iu/iz` trực tiếp (`iu = u_q8*S/z`, `iz = 256*S/z`).
   Thừa một hệ số `S/256` sẽ collapse UV 16× → mặt phẳng lì mà test đếm
   pixel không phát hiện. Regression bắt buộc: texture 2 texel khác màu +
   assert cả hai màu đều xuất hiện (`vxpe_soft3d_runtime`).
2. Tọa độ world của billboard/mesh là tuyệt đối theo camera
   (`dz = world_z - camera->world_z`); vật bám camera phải cộng offset
   camera mỗi frame (bug thuyền HarborDash25D).
3. Xoay dùng LUT sin Q14 tự build lúc init; depth buffer `static`
   (240×320×2 = 150KB), không để stack.
4. Verify on-device bằng PrintWindow đúng HWND + so sánh 2 frame;
   `ImageGrab` toàn màn hình dễ chụp nhầm cửa sổ IDE.

Bake offline: `engine/coremre/tools/vxp_bake_light.py mesh.json -o baked.json`.
Sample: `examples/SpinCube3D` (3D), `examples/HarborDash25D` (2.5D).

## Skill 35 — action2d (lõi game 2D hành động / platformer)

Sáu header trong `engine/coremre/include/action2d/`: `VxpTilemap2D`,
`VxpCamera2D`, `VxpBody2D`, `VxpCombat2D`, `VxpHud2D`, `VxpInputMap2D`.
Hướng dẫn đầy đủ: `docs/CORE_ACTION2D.md`; dự án tham chiếu:
`examples/VampireVeilDemo` (map 128×24 tile = 2048×384 px, 35 sprite, 14 slot
combatant, `MS 07–09` đo trên máy thật).

- Game chỉ sở hữu dữ liệu và thứ tự vẽ. Nếu `main.c` bắt đầu chứa code vật lý
  hoặc self-implement hitbox nghĩa là lõi thiếu primitive — sửa lõi, không
  viết glue.
- Hai `VxpeTilemap2D` view dùng chung một mảng `flags`: atlas nền opaque đi fast
  path `copy_tile`, atlas ledge có mask 1-bit để slab "rắn với mover, trong với
  blitter". `VxpBody2D` va chạm chỉ đọc `flags`, không đọc cell.
- Q8.8, không float, không chia. Một tuning `VxpeBody2DTuning` cho một
  archetype; flier = bảng tuning memset 0 (`gravity_q8 = 0`), không phải
  nhánh code riêng. `vxpe_combat_body_step/_control` là đường đi thật của mọi
  move; `vxpe_body_*` trực tiếp chỉ còn init/tuning/settle/touching.
- Hitbox luôn mirror theo facing: `out->x = facing ? bx + off_x
  : bx + body->w - off_x - w`. `off_x` âm là đòn đánh phủ cả hai phía.
- `map->pressed` chỉ tồn tại một frame sau `vxpe_input_update`; mỗi press đúng
  một edge. Pen không có key code nên virtual pad bơm mã giả
  (`PEN_LEFT 200`..`PEN_BURST 206`) vào `vxpe_input_press` — game không bao giờ
  thấy toạ độ, chỉ có một đường input để test.
- Bẫy chơi được chỉ thiết bị thật bắt được: cửa sổ verdict phải khoá input vài
  trăm ms (`g_title_ms > 400`, death `g_dead_ms > 1200`), nếu không nút nhảy
  làm chết nhân vật cũng bị đọc là "đóng panel". Menu UP wrap từ row 0 xuống
  row cuối — nếu row cuối là EXIT thì driver tự kill app và PrintWindow vẫn
  phát lại frame cuối: capture giống nhau từng byte = app đã chết, không phải
  treo (kiểm tra `Get-Process .CPU` flat + `EnumWindows` không có dialog).
- Cost vẽ phải đọc được từ screenshot: `g_frame_ms = vm_get_tick_count()` bọc
  `draw()` rồi in `MS n` ở góc thế giới không bao giờ vẽ gì. Host shim trả tick
  không chạy trong `draw()` nên host luôn `MS 00` — con số này chỉ có ý nghĩa
  trên máy thật.
- VXPEmu map `vm_get_removable_driver()` = `'e'` (`MreIO.cpp:562`) và
  `path_from_emu` trả về `%LOCALAPPDATA%\MREmu\fs\e\`, nên save của template
  (`vxp_public_cache.h`) nằm ở `fs\e\@vxp_<app_id_hex>\save.bin`. Muốn xác nhận
  persistence phải relaunch process rồi đọc lại menu — con số trên menu trong
  cùng một phiên không phải bằng chứng, vì `save_write` chỉ chạy khi chết, khi
  gặp NPC lưu, và khi destroy ngoài màn menu.
- Regression: `vxpe_action2d_runtime/_c_api`, `vxpe_combat2d_*`, `vxpe_input2d_*`,
  `vxpe_hud2d_*` (toàn bộ suite 31/31, 3.63 s — `tmp/sforge_full_ctest.log`).
  Twin `_c_api` compile header bằng C để game C không bị break khai báo chỉ-C++.
  VXPEmu single-instance: driver phải `taskkill` và
  chờ cửa sổ biến mất, nếu không sẽ test nhầm module cũ đã load.

## Skill 36 — sprite-forge bridge (art từ spec → header RGB565)

Route art thứ hai của engine: tác giả sprite bằng skill đã vendor
(`third_party/agent-sprite-forge/skills`: chỉ `codeart2d` + `generate2dsprite`,
MIT, commit `5324342f…`, digest 91 file / 3.304.730 byte = `44d74282…` ghi trong
`third_party/VENDOR-agent-sprite-forge.json`, tính trên byte đã commit và loại
`__pycache__`; `.gitattributes` pin tree này bằng `-text` nên `core.autocrlf`
không được phép làm lệch digest sau clone), rồi bake sang header C bằng
`tools/vxp_import_sprite_forge.py`. Engine không phụ thuộc gì tree vendored:
`.vxp` phát hành chỉ chứa header sinh ra. **Tree vendored chỉ đọc** — cần sửa gì
thì sửa bridge tool hoặc spec của project, không vá file upstream.

- Chạy mọi script bằng `D:/Program/Python/python.exe` với `PYTHONUTF8=1`.
  `python` trên PATH (msys) không có Pillow → ImportError trông như tool hỏng.
- Upstream từ chối `--output-dir` đã tồn tại và `--strict-qc` không publish gì
  khi fail: mỗi lần thử phải dùng thư mục mới, đừng "sửa tại chỗ".
- Input của importer có hai dạng: `*/frames/*.png` (loose, kèm `--variant`) hoặc
  `animation-clips.json` / `bundle/animation-clips.json` (tên frame, thứ tự,
  `duration_ms` từng frame, `loop`, `anchor_px` lấy từ manifest, và **mọi PNG
  được sha256 đối chiếu với manifest trước khi đọc pixel**).
- Output hai dạng: `--mode sprites` → bảng `VxpeSprite565` + enum chỉ số;
  `--mode atlas` → một atlas ô đều + `VxpeRectI[]` + `uint16_t[]` +
  `VxpeAnimClip` cho mỗi clip, tức `VxpTilemap2D` và `vxpe2d_anim_*` dùng trực tiếp.
- Hợp đồng byte (bắt buộc từ `VxpRender2D.cpp`): mask là bit `y*width+x`, MSB
  trước, **không pad theo row**; `pixels` = 0 tại pixel trong suốt; frame không có
  pixel trong suốt nào phải phát `mask=0, opaque=1` để ăn nhánh memcpy; atlas bắt
  buộc `stride == width` vì `mask_visible()` index bằng `width`, pad row là lệch
  mọi bit từ ô thứ hai trở đi.
- Gate fail-closed, override luôn tường minh: frame rỗng, sha256 manifest lệch,
  **RGB565 collapse** (hai màu nguồn về cùng một giá trị 565 — art mất nét mà
  screenshot không nói), size lệch manifest, atlas lẫn kích thước,
  `--max-dimension 255`, `--max-colors 32`, `--max-atlas-pixels 16384`. Alpha
  chỉ 1 bit: pixel alpha < 128 bị loại và phải báo số lượng.
- Header **không chứa đường dẫn máy**, chỉ digest manifest + digest từng frame.
  Nhờ vậy fixture golden diff được trên mọi máy; đổi tool có chủ đích thì phải
  regen `engine/coremre/tests/data/sprite_forge/fixture_*.h` trong cùng commit.
- Test: `vxpe_sprite_forge_c_api` đọc lại từng pixel qua `vxpe2d_blit`/`vxpe2d_anim_*`
  thật và compile bằng C99; `vxpe_sprite_forge_importer` chạy 14 check có tên cộng
  các exit-code gate. Debug không define NDEBUG — đã chứng minh bằng mutation
  (đổi một kỳ vọng → `Assertion failed`, rc=3), nên hai test này không rỗng.
- `anchor_px` là gốc canvas chung của cả bộ frame, không phải đáy khả kiến từng
  frame; importer chỉ ghi chú chứ không dịch chuyển gì. Muốn chân nhân vật chạm
  đất thì phải tác giả canvas như ô 16x26 của `VampireVeilDemo`.
- Giá đo được: import 12 frame 16x24 (4 clip) = 0.16 s, header 45.773 byte,
  9.792 byte `.rodata`; 3 frame slime 32x32 = 0.15 s, 6.528 byte `.rodata`.
  Round-trip header → PNG (`tmp/sf_preview.py`) đã xem bằng mắt: silhouette và
  palette giữ nguyên, nền xám đúng chỗ mask trống.
