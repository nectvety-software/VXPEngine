# Hopscorch

Dự án mẫu VXPEngine/MRE VXP 240×320 dọc, phong cách pixel art câu cá
bên biển lấy cảm hứng từ video Hopscorch do người dùng cung cấp.
Nền được tạo mới bằng imagegen, cắt bố cục dọc và giữ tỉ lệ hình vẽ.
Nhân vật được vẽ lại thành sprite pixel 20×30 theo ảnh phóng lớn từ video:
tóc trắng, khăn/mũ xanh xám, áo da nâu đỏ, quần và giày tối.
Sprite có hướng quay, chuyển động chân khi đi và tay cầm cần câu.
Runtime dùng `VxpActorSprite2D`: atlas 32 ô 20×30 cho bốn hướng và các
action idle/walk/cast/reel. Đã thêm sprite cá, phao câu và gợn nước quanh phao.

## Các màn hình

- Splash tự chuyển sau khoảng 2 giây, hoặc bấm phím để bỏ qua.
- Menu: Play, Language, Guide, Abouts, Settings, Exit.
- Play: di chuyển trên bãi cát, thả câu, chờ phao vàng rồi kéo để bắt cá.
- Language: English / Tiếng Việt, áp dụng ngay cho menu và hướng dẫn.
- Abouts: **© VXPstore. All rights reserved.**
  Website: [qeafivels.com](https://qeafivels.com/?utm_source=chatgpt.com).
- Settings: bật/tắt hiệu ứng nước, tốc độ đi nhanh/chậm.
- Exit: xác nhận trước khi đóng ứng dụng.

## Điều khiển

Phím hướng hoặc 2/4/6/8 để đi/chọn; 5, OK hoặc softkey trái để xác nhận.
Trong game, bấm 5 để thả câu, chờ thông báo CÁ CẮN rồi bấm 5 lần nữa.
Back hoặc softkey phải trở về menu. Cài đặt và ngôn ngữ giữ trong phiên chạy;
demo chưa lưu chúng qua lần khởi động lại. Website hiển thị trong Abouts;
URL đầy đủ nằm trong `assets/localization.json`.
VXPEmu dùng màn hình dọc 240×320. Nếu emulator đang ở chế độ ngang,
demo xoay framebuffer để giữ đủ cảnh; chuyển emulator về dọc để xem đúng.

## Build và chạy

Từ thư mục dự án, chạy `scripts/build_arm.bat`, rồi `scripts/run_vxpemu.bat`.
Output để chạy: `build-arm/main/hopscorch_signed.vxp` (ký theo App ID riêng).
SDK/core dùng chung của VXPEngine.
Mã chính: `src/main.cpp` (MRE lifecycle), `src/game.cpp` (state machine/render).
`tools/prepare_actors.py` tái tạo atlas nhân vật/props thành PNG, VXA8,
JSON và header nhúng; `assets/sprites/hero_atlas.png` xem được trong Asset Editor.
`src/art.h` và `src/labels.h` là asset đã biên dịch, được kèm sẵn.
`tools/prepare_assets.py` tái tạo chúng từ ảnh/localization, cần PySide6 và
font Segoe UI trên Windows; build game bình thường không cần tái tạo asset.

Các scene trong `assets/scenes` dùng để xem từng màn trong editor;
runtime vẽ theo code và bitmap, không tự đọc các scene này.
Ảnh xem trước: `docs/preview.png`. `tests/host_preview.cpp` kiểm tra luồng
menu, đổi ngôn ngữ, câu cá, cài đặt và xác nhận thoát bằng renderer thật.
