# VXPEngine v4.6.0

## App ID riêng cho từng project

- Mỗi project nhận **một App ID riêng** (6–7 chữ số do engine phát sinh, bảo
  đảm không trùng với project khác).
- App ID được lưu trong `project.vxp.json` (trường `app_id`) và tự điền vào
  `CMakeLists.txt` (`set(APPID ...)`).
- Project tạo bởi bản cũ chưa có App ID sẽ được **cấp tự động** khi mở lại,
  không trùng ID của các project đã có.
- Hiển thị **App ID** trên thanh trạng thái của editor (báo đỏ nếu chưa có ID).

