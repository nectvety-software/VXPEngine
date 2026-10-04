# VXPEngine v3.3.0

## TitleSet Library
- Khu vực dưới Inspector được chuyển thành **TitleSet / Component Library**.
- Hiển thị thumbnail từ `assets/map/tileset`, `assets/map/texture`, `assets/map/skill` và `assets/scenes`.
- Có các tab TitleSet, Controls, Skills, Tiles và Terrains.
- Kéo mẫu vào Frame Preview để tạo thành phần mới.
- Kéo mẫu lên nút/joystick đang có để thay hình nhưng giữ nguyên `id`, `code_name`, `ui_role` và `input_binding`.
- Chuột phải mẫu: thêm vào màn, thay hình thành phần đang chọn hoặc mở Editor Assets.
- Nút thêm bộ mẫu gồm nhân vật, hiệu ứng, joystick trái/phải, RUN và JUMP.

## Editor Assets -> TitleSet
- Khi Auto Slice tạo frame, **Áp dụng & lưu** xuất từng frame PNG vào `assets/map/tileset/<tên_asset>/`.
- Sinh catalog `<tên_asset>.tileset.dtfe`.
- Tự phân loại control, skill, character, terrain, UI hoặc tile.
- TitleSet panel tự làm mới sau khi lưu.

## Scene/code automation
- Sprite mẫu tự gán `ui_role`, `input_binding` và `component_category`.
- Scene bindings sinh thêm các hằng UI/input/motion.
- Sinh nested class `Controls` để ánh xạ action như `JUMP`, `RUN`, `MOVE_LEFT` tới node ID.
- Runtime hỗ trợ `findByInput()` và `requireInput()`.
- Motion preset trong scene được chạy tự động ở runtime: move, float, scale, rotate và opacity.

## Aspect ratio
- Modal tạo project có preset 16:9, 9:16, 1:1, 4:3, 3:2, 21:9 và Custom.
- Kích thước được lưu vào project descriptor, scene viewport, cửa sổ LWJGL3 và custom desktop chrome.

## Build/package
- Desktop JAR.
- Desktop JAR + companion JAD.
- Android APK Debug.
- Android APK Release.
- Android AAB Release.
- Artifact được sao chép vào thư mục `dist/` của project.

> JAD được tạo như tệp mô tả đi kèm JAR desktop. JAR libGDX/LWJGL3 không tự trở thành ứng dụng Java ME/MIDlet chỉ nhờ có JAD.
