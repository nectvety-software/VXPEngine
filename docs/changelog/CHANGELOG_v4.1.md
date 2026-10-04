# VXPEngine v4.1.0 — Photoshop Layers, Events & Stability

## Home
- Xóa menu và khu vực “Dự án gần đây”. Home chỉ giữ Trang chủ, Dự án, tạo mới và mở project.

## Scene / Layers
- Scene Tree chuyển thành bảng layer kiểu Photoshop.
- Kéo thả layer và group để thay đổi thứ tự z-index trong Frame Preview.
- Hiển thị thumbnail asset ở từng layer.
- Mỗi layer có nút mắt, khóa và menu ba chấm.
- Thêm nhân đôi dưới dạng Clipping Mask.

## Events & Maps
- Thêm hộp cấu hình sự kiện node/group: click, touch, overlap, enter, exit, animation complete.
- Hành động: đổi màn, toggle visibility, phát animation, đặt thuộc tính, phát signal gameplay.
- Tạo/nhân đôi map có tùy chọn nối map nguồn và map đích.
- Screen registry lưu transitions và Java bindings sinh lớp Transitions.

## Inspector
- Opacity sử dụng slider 0–100% kèm giá trị phần trăm, thay cho ô nhập khó thao tác.

## Windows stability
- Bật Qt software rendering mặc định để giảm lỗi Access Violation 0xC0000005 / -1073741819.
- Dừng QProcess, đóng cửa sổ Editor Assets/Keyframe, dừng timer và giải phóng QGraphicsScene theo thứ tự khi thoát.
- Ghi native trace vào %LOCALAPPDATA%/VXPEngine/logs/native_crash.log.
