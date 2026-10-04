# VXPEngine 2.6.0 — Unified Custom Modals & Frameless Simulator

## Cửa sổ và hộp thoại

- Thêm nền tảng `CustomDialog` frameless, responsive, có custom title bar 32 px.
- Thêm `NoticeDialog`, `ConfirmDialog`, `TextInputDialog`, `IntInputDialog`, `ColorPickerDialog` và `FilePickerDialog`.
- Xóa toàn bộ lời gọi trực tiếp tới `QFileDialog`, `QInputDialog`, `QMessageBox` và `QProgressDialog` trong ứng dụng.
- QColorDialog chỉ còn được dùng ở chế độ `DontUseNativeDialog`, nhúng dưới dạng widget trong custom frame.
- File Picker nội bộ hỗ trợ chọn một tệp, nhiều tệp, thư mục, bộ lọc, điều hướng, Home, Up, Refresh và tạo thư mục.

## Run / Build / Debug

- Thêm `RunSessionDialog` dạng window-modal với custom title bar.
- Log Gradle, Java, CMake và JDB hiển thị trực tiếp trong monitor.
- Có trạng thái tiến trình, progress indicator, nút Ẩn và Dừng.
- Nút X chỉ ẩn monitor để tránh dừng game ngoài ý muốn.

## Cửa sổ giả lập desktop

- Project mới sinh `VXPEngineDesktopChrome.java` trong module `lwjgl3`.
- `Lwjgl3Launcher` dùng `config.setDecorated(false)` và bọc gameplay bằng desktop chrome.
- Thanh tiêu đề OpenGL 31 px có kéo cửa sổ, nhấp đúp maximize/restore, minimize, maximize/restore và close.
- Khi mở project cũ, engine tự thêm chrome và chỉ nâng cấp launcher cũ khi nhận diện đúng template do engine tạo.

## Tương thích

- Giữ nguyên Java 17, libGDX 1.14.2, Gradle 8.11.1 và cấu trúc `.dtfe`.
- Project gameplay do người dùng chỉnh sửa không bị ghi đè.
- Windows batch runner 2.5.1 tiếp tục được giữ nguyên.
