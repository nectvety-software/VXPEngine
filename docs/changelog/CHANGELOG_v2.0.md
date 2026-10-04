# VXPEngine 2.0.0 — Branding và định dạng .dtfe

- Đổi tên toàn bộ ứng dụng từ Nova2D Engine thành **VXPEngine**.
- Thêm app icon Windows tại `app/resources/app-icon.ico` và PNG 1024 px.
- Định dạng độc quyền thuần chữ UTF-8 JSON: `.dtfe`.
- Project descriptor mới: `project.dtfe`.
- Scene mặc định mới: `scenes/main.dtfe`.
- Metadata Asset Editor mới: `assets/data/<name>.asset.dtfe`.
- Vẫn đọc được project cũ có `project.nova.json` và scene `main.nova`.
- Package mặc định hợp lệ cho Java/Android: `com.vxp.ten_project`.
- `com.vxpe.ten_project` không được dùng trực tiếp vì một nhánh package Java/Android không thể bắt đầu bằng chữ số. Trường package vẫn có thể chỉnh sửa trong form.
- Lớp gameplay mẫu đổi từ `NovaGame` thành `VxpGame`.
- Native library đổi từ `nova_native` thành `vxp_native`.
