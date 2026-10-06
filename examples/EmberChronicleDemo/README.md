# Ember Chronicle Demo

Mẫu fantasy 2.5D 240×320 theo tinh thần các ảnh tham khảo: nhân vật sprite trên
nền dựng sẵn nhiều chi tiết, thư viện cổ, sân đá phủ rêu, làng lúc hoàng hôn,
hội thoại và phép lửa. Artwork mới được tạo riêng; PNG và alpha nguồn được
lưu trong project để chỉnh sửa bằng Editor Assets.

Lyra và tiên Syl nhận lời bảo vệ làng. Hãy nói chuyện ở thư viện, tập dùng
phép với Rowan trên sân đá rồi thanh tẩy ba phong ấn trong quảng trường.

| Phím | Hành động |
|---|---|
| 2/4/6/8 hoặc mũi tên | Di chuyển trên mặt phẳng sân |
| 5 / OK | Nói chuyện; hiện hết chữ; chuyển trang; đóng hội thoại |
| 7 | Phóng phép; gần phong ấn sẽ thanh tẩy nó |
| 0 | Đổi cảnh thư viện → sân đá → làng |
| 9 | Pause / tiếp tục |
| 1 | Chơi lại |
| Back | Đóng hội thoại; nếu không có hội thoại thì thoát |

Đấu tập: quay phải và bắn ba lần vào Rowan. Ở làng, đến gần ba vạch vàng và
nhấn 7; khi cả ba phong ấn tắt, làng được cứu. Phím 0 cho phép xem trực tiếp
mọi cảnh để thuận tiện thử lõi. Đây là demo ngắn; chưa có lưu tiến trình,
bản đồ thế giới, âm thanh hoặc hệ chiến đấu RPG đầy đủ.

## Build và chạy

Mở `project.vxp.json` trong VXPEngine rồi Build / Run. Hoặc:

```bat
scripts\build_arm.bat
scripts\run_vxpemu.bat
```

Bản ARM: `build-arm/main/ember_chronicle.vxp` (App ID 1668016).
Build kiểm tra chữ ký core trước khi dùng gói `packaging/coremre/2.0.0`.
Bản script là VXP development chưa ký ứng dụng; Build từ IDE dùng signer
của VXPEngine. Project không chứa khóa riêng.

Khung hình dọc 240×320 native; nền, nhân vật, HUD và hộp thoại được bố trí trực tiếp cho màn hình này.

## Lõi được dùng

- `VxpStory2D`: source foot anchor, depth theo ground Y, scale theo chiều sâu,
  thoại phân trang/word wrap/typewriter với buffer cố định và API C/C++.
- `VxpSpriteFx`: RGB565+A8, atlas crop/flip, batch có giới hạn và đường vẽ nhanh.
- `VxpParticlePool`: sparks phép thuật, lửa và ánh tiên; tối đa 64 particle.
- `VxpRender2D`: HUD, bóng tiếp xúc, glow và overlay.

Tài nguyên đã bake được nhúng trong VXP; không decode PNG trong vòng vẽ.
BSS không chứa framebuffer trung gian; bộ nhớ còn gồm framebuffer layer/heap/stack
của MRE. RAM khai báo 1500 KiB. Nền giữ độ phân giải 240×320, atlas gồm
16 ô 80×96 với RGB565 và alpha 8-bit.

## Asset và scene chỉnh được

- `assets/source/`: hai ảnh gốc tạo bằng ImageGen.
- `assets/backgrounds/`: library, terrace, village 240×320.
- `assets/sprites/`: atlas, frame JSON, sprite riêng, `.ani..dtfe`.
- `assets/runtime/`: VXA8; `src/assets_generated.h`: dữ liệu nhúng tương ứng.
- `assets/scenes/`: main/library/terrace/village DTFE và registry IDE.

DTFE là bố cục chỉnh được trong Camera2D. Gameplay hiện đọc `scene.cpp`;
đổi DTFE không tự sửa logic runtime. Thay PNG rồi bake để cập nhật hình:

```powershell
.venv/Scripts/python.exe examples/EmberChronicleDemo/tools/generate_assets.py
.venv/Scripts/python.exe examples/EmberChronicleDemo/tools/prepare_scenes.py
```

[Prompt artwork và nguồn](docs/ARTWORK_PROMPTS.md).
[Lõi Story2D](../../docs/STORY_STAGES_2D.md).

## Kiểm tra

Host CMake trong `tests/` kiểm tra hội thoại, movement, pause, ba lần đánh
trúng trong duel, mưa lửa, ba phong ấn, kết thúc, restart/exit và framebuffer
canaries. Ảnh render nằm trong `tests/screenshots/`.

`tests/run_vxpemu_smoke.py` chạy VXP ARM thật bằng EmulatorCore của bản
VXPEmu đang build tại `D:/MRE/VXPEmu/build-new`, không sửa source emulator.
Harness đặt display 240×320, gửi phím đổi cảnh/cast/pause/restart và lưu
ảnh/report vào `reports/ember-portrait/`. Nó cần môi trường MSVC/Qt cục bộ.
Kiểm thử tiến trình đầy đủ nằm ở host test; runtime smoke xác nhận load,
framebuffer portrait và thay đổi hình khi nhận phím.

## Story HUD authoring

Editor Assets > Story HUD edits the title, RGB565 colors, opacity and keypad labels. Save writes `assets/ui/story_hud.json` and `src/story_hud_generated.h`; rebuild to apply. The demo calls the shared `vxpe_story_hud_draw` core API.
