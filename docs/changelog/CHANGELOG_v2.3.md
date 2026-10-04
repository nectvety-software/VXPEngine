# VXPEngine 2.3.0 — Responsive Project Flow & Scene Drag/Drop

## Tạo dự án

- Sửa package mặc định: nhập tên dự án sẽ tự sinh `com.vxp.<ten_du_an>`.
- Chuẩn hóa tên tiếng Việt/Unicode sang package ASCII hợp lệ.
- Cho phép người dùng sửa Package ID thủ công; thay đổi tên không ghi đè package đã sửa.
- Gộp hai nút tạo thành một nút **Tạo dự án và mở 2D Engine**.

## Responsive desktop

- Modal dùng vùng nội dung cuộn và tự giới hạn theo vùng màn hình khả dụng.
- Home tự đổi số cột project card và thu gọn sidebar.
- Toolbar chuyển chữ thành icon và dùng menu tràn ở cửa sổ hẹp.
- Workspace giảm minimum width để không che Scene, Preview và Inspector.
- Editor Assets tự co giãn splitter, toolbar và timeline.
- Custom Title Bar giảm còn 31 px với nút Windows 46 × 30 px.

## Assets → Preview 2D

- Cây Assets phát MIME/URL khi kéo tệp.
- Preview nhận ảnh từ codebase, tạo Sprite2D tại tọa độ thả và hiển thị ngay.
- Sprite có thể chọn, kéo, xóa và được lưu vào `assets/scenes/main.dtfe`.
- Scene tree tự làm mới sau khi scene được lưu.

## Inspector

- Inspector thay đổi theo Camera2D hoặc Sprite2D đang chọn.
- Thuộc tính sprite: Name, Asset, Size, Position, Rotation, Scale, Opacity, Z Index, Visible.
- Thuộc tính camera: Position, Rotation, Zoom, Viewport, Projection và Preview.
- Cuộn bằng chuột/touchpad nhưng ẩn scrollbar.

## Phiên bản

- `ENGINE_VERSION = 2.3.0`.
