# VXPEngine 2.0

IDE và SDK C/C++17 để phát triển game, ứng dụng MRE VXP cho điện thoại S30+.
Frame Camera2D được khóa theo đúng hai hướng 240×320 và 320×240. Runtime giả
lập duy nhất là **VXPEmu**.

## Chuỗi công cụ

- `run_windows.bat`: mở IDE, tự sửa/tạo `.venv` và cài dependency còn thiếu.
- w64devkit: CMake, GNU Make/Ninja và compiler host.
- ARM GCC `arm-none-eabi`: tạo ELF32 ARMv5TE cho MRE.
- `engine/coremre/sdk/mre`: headers và import libraries MRE tích hợp.
- VXPEmu: chạy file ARM `.vxp` thật trong cửa sổ Nokia 225 riêng, có màn hình
  240×320/320×240, phím MRE và thanh công cụ chạy/dừng, nạp VXP, chụp ảnh,
  mở thư mục, quay MP4, xoay và toàn màn hình. Tab `VXPEmu`
  của Bottom Panel là bảng chẩn đoán trực tiếp gồm thanh ghi ARM, CPSR, byte mã
  quanh PC, heap MRE, FPS đo thực, TestAPI và runtime log.

Pipeline không phụ thuộc trình giả lập cũ. Mỗi project có App ID riêng.

## Chạy

```bat
run_windows.bat
```

Các lệnh hữu ích:

```bat
run_windows.bat check
run_windows.bat deps
<project>\scripts\build_arm.bat
<project>\scripts\run_vxpemu.bat
```

## Bố cục chính

```text
app/                         IDE PySide6
engine/coremre/              core C++17 cho MRE
engine/coremre/sdk/          SDK headers/libs và cấu hình toolchain
packaging/coremre/2.0.0/     core dùng chung đã ký và kiểm tra toàn vẹn
template_blank/              mẫu project S30+ MRE VXP
ai/skills/vxpengine-agent/   SKILL.md, PROMPT.md và tài liệu cho AI Agents
.mimocode/skills/            skill nạp bởi MiMo Desktop (bản sao định tuyến)
```

Dự án mới dùng layout v2: `src/` và `assets/` thuộc người dùng, pipeline nội bộ
nằm trong `.vxpe/`, còn `template_blank/template.manifest.json` điều khiển tạo và
cập nhật động. VXPEngine chỉ cập nhật tệp managed chưa bị sửa cục bộ; code/asset
người dùng không bị ghi đè.

Build ARM trong IDE thực hiện compile, đóng gói `.vxp` rồi ghi checksum.

Hộp **Tạo dự án VXP mới** cho chọn trực tiếp `240×320 — Dọc` hoặc
`320×240 — Ngang`; descriptor, scene, Camera2D và cửa sổ Nokia dùng đồng bộ lựa chọn.

## UI Design và Pixel Paint

Editor Assets có tab **Terra · Tilemap** để cắt atlas, vẽ map theo layer,
lưu `.terra.json` và chuyển map PNG sang Assets. Xem [hướng dẫn Terra](docs/TERRA_INTEGRATION.md).

Editor Assets tích hợp **VPE Pixel** trong cùng cửa sổ, dùng chung thư viện
`Documents/VPE Pixel`, mở `.vpe/.vpea` và chuyển ảnh/animation hai chiều
để lưu vào project. Xem [hướng dẫn tích hợp](docs/VPE_PIXEL_INTEGRATION.md).

Asset Editor có năm palette game mới: Cozy Farm, Dark Fantasy, Neon Action,
Pastel Platformer và Retro Handheld. Runtime có `VxpColorGrade.h` để chỉnh màu
RGB565 theo vùng trước khi vẽ HUD, dùng LUT 256 byte không cấp phát heap.
Xem [hướng dẫn Game Art Styles](docs/GAME_ART_STYLES.md).
Lõi có thêm controller sprite bốn hướng `VxpActorSprite2D`; Hopscorch minh họa
atlas RGB565+A8 với idle/walk/cast/reel. Xem [Actor Sprites](docs/ACTOR_SPRITES.md).

- `TitleSet / Component Library` có tab UI với Canvas, Button, Label, Checkbox,
  TextBox, Image, ProgressBar, Slider và Switch. Kéo hoặc nhấp đúp để đặt vào
  Camera2D; node và C bindings được cập nhật tự động từ scene `.dtfe`.
- Tab UI có thêm hai background pixel dựng sẵn cho 240×320 và 320×240. Khi kéo
  vào Camera2D, nền tự căn giữa, khớp framebuffer, khóa transform và nằm sau các
  thành phần khác.
- Tab **Frame Perspective** có bốn guide editor-only: Side-Scroller, Top-Down,
  góc 3/4 và Isometric 2:1. Kéo preset vào Camera2D sẽ tự khít 240×320/320×240,
  lưu projection, góc camera và trục di chuyển vào `.dtfe`, đồng thời sinh macro C.
- Mọi ảnh bên trong `assets/` đều xuất hiện trong tab Assets. Vì vậy ảnh pixel vừa
  **Áp dụng & lưu** trong Editor Assets có thể được kéo vào Camera2D ngay, không tự
  chèn vào scene khi người dùng chưa yêu cầu.
- Ảnh từ thư viện mẫu hoặc ngoài project được chép một lần vào
  `assets/imported/` trước khi scene tham chiếu, tránh đường dẫn tuyệt đối và file
  trùng lặp.
- Kéo asset luôn tạo Sprite2D mới; thao tác thay ảnh chỉ chạy từ lệnh **Thay hình**
  riêng, nên một background phủ toàn frame không còn chặn việc thả asset khác.
- Layer được xếp như Photoshop: hàng trên vẽ phía trước, hàng dưới vẽ phía sau;
  Camera2D được ghim ngoài z-order. Các node `Vùng_vẽ`/Canvas cũ tự chuyển thành
  guide trong suốt nên không còn che background khi nền được đưa xuống dưới cùng.
- Smart Guides dùng snap mềm: kéo tự do giữa các điểm lưới, chỉ hít khi
  gần tâm/mép. Ngưỡng bám và ngưỡng nhả tách biệt chống rung; đường
  dóng gạch nét xanh/vàng hiển thị khi thẳng hàng với Camera2D hoặc node khác.
- `Paint Tile` vẽ theo lưới 16 px tương đối với góc Camera2D, giới hạn hoàn toàn
  trong frame 240×320 hoặc 320×240 và lưu dữ liệu terrain/rule tile vào `.dtfe`.

### Inspector chuyên dụng cho game/app 2D

- Nhập trực tiếp **Size W/H (px)** cho sprite, shape và text; kích thước logic
  không bị thay đổi khi xoay node.
- Có **khóa tỉ lệ**, **Pixel snap**, chín vị trí **Anchor**, layer/Z-index,
  opacity, blend, tint, collision shape và physics.
- Các thuộc tính được lưu vào `.dtfe` và sinh macro trong
  `src/scene_bindings.h`, không phải controls minh họa.

Asset Editor có thêm canvas preset QVGA, unit/building isometric và style
**Pixel Art · Isometric RTS**. Hai project kiểm thử UI hoàn chỉnh nằm trong
`examples/PocketToolkitDemo` (240×320) và `examples/IsometricOutpostDemo`
(320×240). Demo `examples/ParticleFireDemo` minh hoạ particle pool C cố định
64 slot với lifetime, alpha fade, tint RGB565 và blend ADD/ALPHA chạy ở 30 FPS.

Chạy `run_windows.bat test` để tự động kiểm tra Inspector, Asset Editor,
Component Library, DTFE/C bindings, simulator, SDK/VXPEmu và build ARM của cả hai project mẫu.

## Đóng gói Windows

[Ember Chronicle](examples/EmberChronicleDemo/README.md) là mẫu fantasy 2.5D
240×320: thư viện, sân đá, làng hoàng hôn, sprite hoạt ảnh, hội thoại phân trang
và phép lửa. Lõi [VxpStory2D](docs/STORY_STAGES_2D.md) dùng chung hỗ trợ foot depth,
scale theo chiều sâu và hộp hội thoại không cấp phát heap.

Mẫu [Nightfall Survival](examples/NightfallSurvival/README.md) minh họa FPS
zombie sinh tồn 320×240: raycasting 2.5D, texture pixel, zombie billboard,
wave, ammo/reload, cửa mở bằng điểm, rào chắn và vật phẩm. Artwork PNG và
animation descriptor đi kèm để mở trong Editor Assets.

[Urban Toon Demo](examples/UrbanToonDemo/README.md) minh họa lõi
[VxpToon3D](docs/URBAN_TOON_3D.md): mesh/texture phối cảnh, cel band, ink,
depth, clipping, A8 billboard và camera đô thị theo nhân vật patin.

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-build.txt
powershell -ExecutionPolicy Bypass -File packaging\windows\build_release.ps1
```

Kết quả là một file `dist-installer/VXPEngine-2.0.0-Setup.exe`. Bộ cài theo
tài khoản Windows, không yêu cầu quyền Administrator, chứa GUI không console,
w64devkit, ARM GCC, MRE SDK, VXPEmu và media runtime. Pipeline tự quét dependency,
Bandit, secret, chạy thử GUI/SDK và build game ARM trước khi tạo SHA-256.

Bottom Panel/Console mặc định ẩn và không tự chiếm chỗ khi Run/VXPEmu;
dùng `Ctrl+J`, menu View hoặc nút terminal trên status bar để mở. UI Design
có vỏ máy bao quanh Camera2D. Background mặc định được ghim đúng
240×320/320×240; mọi component được kẹp trong frame. Menu **Căn chỉnh**
trên toolbar và menu chuột phải hỗ trợ căn mép/tâm, phân bố và căn theo Camera2D.

Editor Assets also includes **Story HUD**: native QVGA title/location/progress and keypad previews, editable RGB565 colors and project JSON/C header export for the shared `VxpStory2D` HUD API.

`examples/FoxRiftDemo` now runs **Vaelora Duel**, a native 240×320 solo 1vs1 demo with an original logo, splash, hero selection, three original heroes, shared player/bot skills and match results.

Editor Assets → **Font Styles** adds three authored pixel font families (Vale UI, Prism Display, Duel Digits), five roles and four palette/effect presets. The shared core C renderer and editor preview use identical masks.
