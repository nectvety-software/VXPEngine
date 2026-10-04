# Custom Dialog System

Tệp chính: `app/widgets/custom_dialog.py`.

## Quy tắc

1. Không sử dụng static native dialog (`QFileDialog.get...`, `QInputDialog.get...`, `QMessageBox...`).
2. Mọi cửa sổ phải dùng `Qt.FramelessWindowHint` và title bar do ứng dụng vẽ.
3. Modal nhỏ chỉ có nút Close; cửa sổ lớn có Minimize, Maximize/Restore và resize grip.
4. Nội dung dài đặt trong `QScrollArea` và co giãn theo available geometry của màn hình.
5. Tác vụ Run/Build/Debug dùng `RunSessionDialog`; không dùng console popup native.

## API ví dụ

```python
NoticeDialog("Thông báo", "Đã lưu project.", parent).exec()

path = FilePickerDialog.get_open_file_name(
    parent,
    "Chọn ảnh",
    start_directory,
    "Ảnh (*.png *.jpg);;Tất cả tệp (*.*)",
)

text, accepted = TextInputDialog.get_text(parent, "Tên node", "Nhập tên:")
```

## Desktop game chrome

Project generator tạo `VXPEngineDesktopChrome.java`. Lớp này là `ApplicationListener` wrapper, gọi lifecycle của game và vẽ chrome sau `game.render()`. Launcher phải giữ `config.setDecorated(false)` để Windows không tạo native title bar.
