# VXPEngine 2.0 — Tài liệu chuẩn MRE VXP

VXPEngine là IDE + SDK C/C++17 cho game/app S30+ MRE VXP (Nokia 225/220, QVGA
240x320). Tài liệu này là **một trang duy nhất, chuẩn xác**, thay thế mọi ghi
chú rời rạc trước đây.

## 1. Chạy IDE

- Chạy `run_windows.bat` (double-click, không cần tham số).
- Kiểm tra môi trường: `run_windows.bat check`. Cài lại lib: `run_windows.bat deps`.
- IDE là PySide6, **chỉ dark mode**, không có light mode. Cửa sổ frameless, ẩn
  thanh tiêu đề hệ điều hành, dùng custom Title Bar (giống 2Dutiful Engine).

## 2. Tạo dự án mới (mặc định blank chuẩn)

- Home → Dự án mới. Mặc định là **dự án trống MRE VXP**, không dùng dự án mẫu.
- Chọn sẵn `240x320 — Dọc` hoặc `320x240 — Ngang`. Frame Camera2D chỉ nhận đúng
  một trong hai kích thước vật lý này.
- Dự án mới sinh đúng cấu trúc `D:\MRE\VXPstore\CungThuBongDen`:
  `CMakeLists.txt`, `src/main.c`, `assets/`, `resources/`, `maps/`, `cmake/`,
  `common/`, `main/`, `mreapi/`, `run/`, `scripts/`.
- Mỗi dự án được engine cấp một **App ID riêng** (không trùng). App ID nằm trong
  `project.vxp.json` và `CMakeLists.txt` (`set(APPID ...)`).

## 3. Quy tắc App ID: debug và release đã ký

Theo `BUILD_VA_KY_VXP.md` (đóng gói MRE `.vxp` cho Nokia 225):

- `.vxp` = ELF ARM + `resources.res` + khối tag (tên, appid, certid, API, RAM)
  + chữ ký RSA. `.vc.vxp` chỉ dùng cho giả lập, không chạy máy thật.
- Máy retail chỉ mở app có **appid không âm** và ký bằng **certid = 100**.
- `PackApp` chỉ tạo chữ ký khi `appid != -1` **và** `certid != 1`.
- Trong dự án: bản **debug** để `APPID 0 / CERTID 1` (chưa ký, chạy máy dev).
  Bản **release** do engine ký bằng khóa của engine (`certid 100`, App ID riêng
  của dự án). Khóa ký **không bao giờ** nằm trong thư mục dự án.
- Kiểm chứng: đọc tag cuối file — bản ký đúng có `appid > 0`, `certid 100`,
  64 byte chữ ký khác 0.

## 4. Core riêng: vxpstore / corevxp (MRE VXP + Arduino)

- Core duy nhất tên **vxpstore** (alias ngắn **corevxp**, target `coremre`).
- Dựa trên PixelRoot32-Game-Engine nhưng đã tách độc lập: chỉ hỗ trợ
  **MRE VXP và Arduino**, không dùng cho Java, không còn tên PixelRoot32 ở tầng
  người dùng. Header umbrella: `vxpstore/Core.h`.
- Game include `vxpstore/Core.h` và dùng `vxpstore::Engine`, `Scene`, `Renderer`.

## 5. Thiết kế màn hình

- Tab **UI** trong TitleSet/Component Library: kéo Canvas, Button, Label,
  Checkbox, Image, ProgressBar, Slider, Switch vào Camera2D.
- Hai mẫu nền pixel 240x320 và 320x240 nằm trong tab UI; kéo vào frame để có
  đúng kích thước, đưa xuống lớp nền.
- Bảng Scene xếp lớp kiểu Photoshop: lớp trên che lớp dưới. Camera2D ghim riêng.
- Kéo ảnh từ Assets/Nhân vật/Tiles vào frame để tạo Sprite2D. Scene `.dtfe` và
  `src/scene_bindings.h` tự cập nhật. Nút **Áp dụng & lưu** trong Editor Assets
  đưa PNG mới vào Component Library.
- Paint Tile quét lưới 16px trong Camera2D; chuột phải xóa tile.

## 6. Build và chạy giả lập

- Build thiết bị: nút Build → Build ARM (bản debug `APPID 0`, chưa ký).
- Build release: Build ARM Signed (engine ký `certid 100` bằng khóa của engine).
- Chạy: F6. IDE build ARM rồi mở VXPEmu thật trong cửa sổ Nokia 225 riêng
  (CPU Registers, Hex, Memory, FPS, TestAPI, Runtime Log lấy trực tiếp từ
  Unicorn và app MRE). Nút xoay đổi hướng 240x320 ↔ 320x240.
- Toolbar Nokia: chạy/dừng, nạp `.vxp`, chụp PNG, mở thư mục capture, quay MP4,
  xoay, toàn màn hình.
- Tool host: w64devkit; compiler thiết bị: ARM GCC.

## 7. Thư mục dự án chuẩn

```
MyGame/
  CMakeLists.txt        # APP_NAME, APPID riêng, CERTID 1, CERT none
  project.vxp.json      # app_id riêng, screen 240x320/320x240
  src/main.c            # vm_main + handle_keyevt/handle_penevt
  src/scene_bindings.h  # sinh từ .dtfe
  assets/scenes/        # main.dtfe, screens.dtfe
  assets/sprites|maps|audio|fonts
  resources/gen|pack
  maps/  docs/  scripts/build_arm.bat|run_vxpemu.bat
  .vxpe/ (cmake, common, main, mreapi, resources, run)
```

## 8. Đồ họa 3D mềm (clean-room, RGB565, fixed-point)

- Module `graphics/VxpSoft3D.h` (C API, caller owns buffers, không cấp phát):
  raster tam giác hàm-cạnh (edge-function) số nguyên, kiểm tra chiều mặt,
  depth buffer 16-bit, UV phối cảnh đúng qua nội suy `1/z`, sampling RGB565
  nearest, sáng Lambert phẳng + fog theo khoảng cách, hỗ trợ index 16-bit
  (`mesh16`) và 32-bit (`mesh32`).
- Tổ chức pipeline (transform → loại near → raster → depth → sample → light)
  học theo ý tưởng đã công bố của YMGRE (engine C99 CPU ~200KB, raster +
  depth + texture + lighting + bake offline); toàn bộ mã là viết lại độc lập,
  không bundling mã YMGRE (YMGRE dùng giấy phép noncommercial riêng).
- Bake offline: `tools/vxp_bake_light.py` nướng sáng từng đỉnh trên máy host,
  kèm `vxpe_soft3d_ray_triangle` / `vxpe_soft3d_bake_vertex_light` cho truy vấn
  bóng; chỉ dữ liệu đã bake lên thiết bị — thiết bị không ray-trace realtime.
- Kiểm thử: `vxpe_soft3d_runtime` (phẳng, texture, mesh16/32, ray, bake).

## 9. Phím tắt

F5 Debug, F6 Run/Build ARM + VXPEmu, Ctrl+N dự án mới, Ctrl+O mở, Ctrl+S lưu,
Ctrl+Z/Y undo/redo, F1 tài liệu, Ctrl+J console.

## 10. Khắc phục sự cố

- Máy retail không mở app → đang dùng bản debug chưa ký; build Signed.
- `PackApp` không in `Creating signature` → kiểm tra `APPID`/`CERTID`.
- CMake báo không biên dịch được → PATH phải dạng `/c/...`, không `C:/...`.
- Phím cứng không phản hồi → xử lý trong `handle_keyevt`, không chỉ pen event.
- Giả lập screen-only dừng sau vài giây (crash Qt6Widgets): dùng VXPEmu build
  đã vá `setScreenOnlyMode` (detach layout trước khi reparent view); kiểm tra
  bằng `tools/screen_only_smoke.py <VXPEmu.exe> <app.vxp> 15` phải PASS.
