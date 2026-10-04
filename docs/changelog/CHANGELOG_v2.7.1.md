# VXPEngine v2.7.1

## Sửa lỗi cửa sổ giả lập LWJGL3

- Sửa các nút Minimize, Maximize/Restore và Close bị nhận sai hoặc kích hoạt loạn trên Windows.
- Hit-test dùng tọa độ cửa sổ GLFW; phần vẽ dùng kích thước framebuffer, tương thích Display Scaling/HiDPI.
- Nút chỉ thực thi một lần khi thả chuột trên đúng nút đã nhấn.
- Tách trạng thái nhấn nút khỏi kéo title bar và double-click.
- Lưu normal geometry trước khi maximize; restore-drag dùng lại kích thước bình thường.
- Project cũ có `VXPEngineDesktopChrome.java` do VXPEngine sinh sẽ tự nâng cấp khi mở lại.
- Không ghi đè custom chrome do người dùng tự viết.
