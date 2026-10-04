# VXPEngine 2.0 — hướng dẫn nhanh

VXPEngine là IDE + SDK C/C++17 cho game/app S30+ MRE VXP. Frame Camera2D chỉ
nhận 240×320 (dọc) hoặc 320×240 (ngang), không kéo tự do.

- Mở IDE: \`run_windows.bat\`
- Kiểm tra SDK: \`run_windows.bat check\`
- Build thiết bị: Build → Build ARM
- Chạy: F6; IDE build ARM rồi mở VXPEmu thật trong cửa sổ Nokia 225 riêng
- Xoay: nút xoay trên cửa sổ Nokia đổi đồng bộ 240×320 ↔ 320×240
- Toolbar Nokia: chạy/dừng, nạp `.vxp`, chụp PNG, mở thư mục capture, quay MP4,
  xoay và toàn màn hình
- Dự án mới: chọn sẵn `240×320 — Dọc` hoặc `320×240 — Ngang`; project ngang
  tự mở VXPEmu ở hướng 320×240
- Chẩn đoán: tab VXPEmu hiển thị CPU Registers, Hex, Memory, FPS, TestAPI và
  Runtime Log; dữ liệu register/hex/heap lấy trực tiếp từ Unicorn và app MRE
- Core: \`coremre\` 2.0 static library, kiểm tra chữ ký/toàn vẹn trước build
- Tool host: w64devkit; compiler thiết bị: ARM GCC

## Thiết kế UI 2D

- Chọn tab **UI** trong **TitleSet / Component Library**, rồi kéo Canvas, Button,
  Label, Checkbox, TextBox, Image, ProgressBar, Slider hoặc Switch vào Camera2D.
- Hai mẫu nền pixel 240×320 và 320×240 cũng nằm trong tab **UI**; kéo vào frame
  để tự căn đúng kích thước và đưa xuống lớp nền.
- Tab **Frame Perspective** cung cấp Side-Scroller, Top-Down 90°, 3/4 View và
  Isometric 2:1. Guide chỉ xuất hiện trong editor, tự khít khi đổi hướng frame;
  cấu hình perspective vẫn được lưu vào `.dtfe` và `scene_bindings.h`.
- Bảng Scene dùng thứ tự lớp kiểu Photoshop: lớp trên che lớp dưới. Camera2D được
  ghim riêng; `Vùng_vẽ` là guide trong suốt, vì vậy background ở dưới cùng vẫn
  hiển thị qua các lớp thiết kế.
- Kéo ảnh trong tab **Assets**, **Nhân vật** hoặc **Tiles** vào frame để tạo
  Sprite2D. Scene `.dtfe` và `src/scene_bindings.h` tự cập nhật sau thay đổi.
- Trong **Editor Assets**, nút **Áp dụng & lưu** đưa PNG mới vào Component Library.
  Ảnh chỉ được chèn vào màn khi người dùng kéo hoặc nhấp đúp.
- Chọn một texture rồi bật **Paint Tile** để quét lưới 16 px trong Camera2D;
  chuột phải xóa tile. Tọa độ lưới bám theo frame và không vẽ tràn ra ngoài.

### Nhập thông số trong Inspector

Khi chọn một component, nhập trực tiếp W/H theo pixel trong dòng **Size**.
Bật **Aspect** để thay một chiều và tự giữ tỉ lệ; **Pixel snap** giữ tọa độ
nguyên, còn **Anchor** xác định điểm neo layout. Nhóm Automation/GamePlay cho
phép bật va chạm, chọn bounds/circle và none/static/kinematic/dynamic/trigger.
Mọi thay đổi được ghi vào scene `.dtfe` và C bindings.

Asset Editor có preset background 240×320/320×240, unit/building isometric và
style **Pixel Art · Isometric RTS**. Dùng `run_windows.bat test` để chạy trọn
bộ tự kiểm tra, bao gồm build ARM hai project mẫu trong `examples/`.
