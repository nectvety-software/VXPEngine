# Terra Tilemap trong Editor Assets

Mở **Editor Assets → Terra · Tilemap**. Terra chạy trong cùng cửa sổ IDE,
với theme riêng và phím tắt vẽ map. Atlas mẫu được cắt theo ô 32×32;
map ban đầu là 10×7 ô (320×224 px).

- Dự án mới / Mở tilesheet: chọn PNG, JPG, WEBP hoặc BMP.
- Dùng brush, eraser, fill, line và rectangle; quản lý layer, undo/redo.
- Menu lệnh hỗ trợ mở dự án `.terra.json`; Ctrl+S lưu map và tham chiếu atlas.
- Ctrl+E xuất PNG. Giữ atlas cùng thư mục dự án để dễ chuyển sang máy khác.
- **Đưa tilemap vào Assets** chuyển hình render của các layer đang hiển thị
  sang canvas Assets với nền trong suốt. Dùng **Áp dụng & lưu** để lưu vào
  project VXPEngine; sau đó kéo ảnh từ Assets vào Camera2D.

JSON Terra giữ dữ liệu tile/layer; PNG chuyển sang Assets là ảnh đã render.
Việc chuyển PNG không thay thế thao tác lưu JSON. Khi đóng Editor Assets,
Terra hỏi lưu nếu map còn thay đổi.

Nguồn được tích hợp từ `tmp/src` vào `app/vendor/terra`; hoạt động không cần
thư mục `tmp`. Pillow và NumPy nằm trong `requirements.txt`, QSS và atlas mẫu
nằm trong cấu hình PyInstaller.

Kiểm tra tích hợp:

```powershell
.venv/Scripts/python.exe packaging/windows/test_terra_integration.py
```
