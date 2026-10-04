# VXPEngine v2.7.0

## Scene Preview trực quan kiểu Canva

- Công cụ **Select** chọn và kéo trực tiếp Sprite2D, Effect2D, Text2D, Tile2D và các hình vector.
- Giữ `Ctrl` để chọn nhiều thành phần bằng cơ chế QGraphicsScene; kéo vùng trống để chọn theo khung.
- Phím mũi tên dịch chuyển 1 px; `Shift + phím mũi tên` dịch chuyển 10 px.
- Snap to Grid tiếp tục áp dụng khi kéo thành phần bằng Select.

## Move/Pan Frame

- Công cụ **Move** nay dùng để kéo toàn bộ frame/canvas Camera2D, không làm thay đổi tọa độ node.
- Con trỏ đổi sang bàn tay mở/đóng trong lúc kéo.
- Chuột giữa vẫn có thể pan ở mọi công cụ.

## Toolbar Scene

Bổ sung các nút icon:

- **Hoàn tác** (`Ctrl+Z`).
- **Làm lại** (`Ctrl+Y`).
- **Đặt lại frame** (`Ctrl+0`) — tự fit vùng Camera2D vào Preview.

Trạng thái Undo/Redo được đồng bộ với lịch sử Scene.

## Menu chuột phải thành phần

Trong Preview 2D và Scene Tree:

- Mở Editor Assets.
- Đặt tên thành phần (`F2`).
- Nhân đôi (`Ctrl+D`).
- Xóa (`Delete`).

Sprite mở đúng ảnh nguồn trong Editor Assets. Thành phần vector/text mở Editor Assets trống tại `assets/map/texture` để tạo tài nguyên mới.
