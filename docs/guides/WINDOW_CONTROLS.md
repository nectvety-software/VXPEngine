# VXPEngine — Windows Window Controls

## Tệp chính

- `app/window_state.py`: state machine cho Normal, Minimized, Maximized và Hidden.
- `app/widgets/title_bar.py`: phát tín hiệu từ các nút font icon và xử lý kéo/nhấp đúp.
- `app/main.py`: chuyển tiếp sự kiện Qt, lưu placement khi đóng và dừng tiến trình đang chạy.

## Luồng trạng thái

```text
Normal --Maximize--> Maximized --Restore--> Normal
   |                     |
Minimize              Minimize
   |                     |
Restore Normal        Restore Maximized
```

## Dữ liệu được lưu bằng QSettings

- `window/qt_geometry`
- `window/normal_geometry`
- `window/maximized`
- `window/last_state`

Ứng dụng luôn khởi động ở trạng thái hiển thị. Trạng thái Hidden chỉ được dùng trong phiên chạy hiện tại, tránh trường hợp mở ứng dụng nhưng không thấy cửa sổ.
