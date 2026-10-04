# Nova2D Engine 1.5.0

## Bố cục editor

- Xóa hoàn toàn panel **Nodes** khỏi hàng dưới.
- Console chiếm toàn bộ vùng bên trái và giữa; TileMap giữ ở cột phải.
- Tăng tỷ lệ chiều cao cho Scene/Code tabs, giảm chiều cao mặc định của console.
- Thu nhỏ font icon và chiều cao các nút công cụ trên toolbar.

## Dự án mới trống

- `scenes/main.nova` chỉ chứa `Camera2D` kiểu `OrthographicCamera`.
- Viewport chỉ hiển thị lưới, trục X/Y, gốc tọa độ và khung camera 1280×720.
- `NovaGame.java` chỉ khởi tạo camera/viewport và xóa màn hình; không sinh player, nền đất hoặc map mẫu.
- Scene Tree và Inspector mặc định tập trung vào Camera2D.
- TileMap hiển thị trạng thái chưa có TileSet.

## Code editor

- Thêm số thứ tự dòng tự động.
- Tô màu cú pháp Java, C và C++.
- Hỗ trợ chuỗi, số, từ khóa, kiểu dữ liệu, class, hàm, annotation, toán tử, comment và preprocessor.
- Làm nổi dòng hiện tại và giữ `Ctrl+S` để lưu.
