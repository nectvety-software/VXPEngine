# VXPEngine v3.1.0

- Sửa Apply trong Editor Assets không cập nhật Frame Preview.
- Khi chỉnh tài nguyên hiện có, Editor ghi đè đúng tệp thay vì tạo `*_1.png`.
- Frame Preview tự reload pixmap sau khi lưu.
- Nhóm/vector/text mở trong Editor Assets được áp dụng lại thành sprite tổng hợp tại đúng tọa độ và Z-index.
- Mỗi lần kéo, đổi opacity, blend, tint, scale hoặc rotation, `main.dtfe` và `VXPEngineSceneBindings.java` tự cập nhật.
- Java bindings sinh thêm X/Y/rotation/scale/opacity/Z-index/visible/type/asset/blend/tint.
