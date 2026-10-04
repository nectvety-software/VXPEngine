# Nova2D Engine 1.9.0 — Editor Assets

## Tích hợp mới

- Thêm hộp thoại modal **Editor Assets** toàn màn hình làm việc, giao diện tối và dùng QtAwesome font icon.
- Mở từ:
  - `Edit > Editor Assets…` (`Ctrl+Shift+A`).
  - Nút ba chấm của panel Assets.
  - Chuột phải vào ảnh trong Assets > `Editor Assets…`.
  - Nhấp đúp ảnh trong cây Assets.
  - `Nhập tài nguyên…`: ảnh được đưa vào Editor trước khi ghi vào codebase.
- Canvas trống để tạo sprite, tileset/map texture, UI/HUD và material 2D.
- Công cụ pixel: Pencil, Eraser, Fill, Eyedropper, Select, Pan và Collision.
- Undo/Redo tối đa 40 snapshot.
- Ghép ảnh vào canvas, crop vùng chọn, crop alpha, flip, rotate và resize nearest-neighbor.
- Xóa nền theo màu với sai số tùy chỉnh.
- Phong cách 2D: pixel hóa 2×/4×, Retro 4-bit, posterize, grayscale, tương phản cao và viền pixel.
- Lưới tile tùy chỉnh, margin/spacing và chia texture atlas tự động; có thể bỏ frame hoàn toàn trong suốt.
- Danh sách frame/animation kèm tên, FPS, loop và duration.
- Vẽ collision rectangle theo loại Solid, Trigger, Hurtbox, Hitbox.
- Lưu PNG chỉ vào các nhánh codebase có sẵn:
  - `assets/textures`
  - `assets/ui`
  - `assets/maps`
- Sinh metadata `assets/data/*.novaasset.json` chứa grid, frames, animation, texture settings và collision.
- Sau khi áp dụng, cây Assets tự làm mới và chọn tệp vừa lưu.

## Giới hạn có chủ đích

- Editor hiện xử lý ảnh raster; SVG được raster hóa khi plugin Qt hỗ trợ.
- Collision v1.9 là hình chữ nhật. Polygon/ellipse và bone animation dành cho bản tiếp theo.
- Đây là editor tài nguyên 2D, không thay thế Scene/World editor của map runtime.
