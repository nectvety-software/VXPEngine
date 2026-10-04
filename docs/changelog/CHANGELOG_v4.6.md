# VXPEngine v4.6.0

## Ký ứng dụng tách khỏi project (bảo mật cốt lõi)

- Project mới **không còn sinh thư mục `signing/`**. Khóa ký `certid=100`
  (`VXPEngine/signing/cert100-key.pem`) là tài sản của engine và không bao giờ
  được copy vào thư mục dự án.
- `CMakeLists.txt` của project luôn bị ép về trạng thái chưa ký
  (`CERTID=1`, `CERT=none`). Giá trị retail chỉ tồn tại trong lệnh build do
  engine phát ra.
- Project cũ còn sót khóa ký sẽ được **dọn tự động** khi mở, kèm thông báo
  `[Bảo mật] Đã xóa khóa ký lọt vào project: ...` trong console.
- `build_arm_signed.sh` không tự tìm khóa trong project: thiếu tham số sẽ thoát
  ngay với mã lỗi `2` và thông báo rõ lý do.

## App ID riêng cho từng project

- Mỗi project nhận **một App ID riêng** (6–7 chữ số do engine phát sinh, bảo
  đảm không trùng với project khác).
- App ID được lưu trong `project.vxp.json` (trường `app_id`) và tự điền vào
  `CMakeLists.txt` (`set(APPID ...)`).
- Project tạo bởi bản cũ chưa có App ID sẽ được **cấp tự động** khi mở lại,
  không trùng ID của các project đã có.
- Hiển thị **App ID** trên thanh trạng thái của editor (báo đỏ nếu chưa có ID).

## Build ARM Signed

- Nút **Build ARM Signed** lấy App ID của project, ghép với khóa ký của engine
  rồi truyền xuống `build_arm_signed.sh` qua ba biến môi trường
  `VXP_APPID`, `VXP_CERTID`, `VXP_CERT`.
- Kiểm tra môi trường bổ sung mục **Khóa ký VXPEngine (certid 100)**.
- Console in rõ `App ID … · certid 100 (khóa do engine giữ)` trước khi build.

## Tài liệu

- `docs/BUILD_VA_KY_VXP.md`, `docs/index.html` và tài liệu trong IDE cập nhật
  theo mô hình ký mới: phần sở hữu khóa, bảng biến môi trường và hai lỗi mới
  trong mục xử lý sự cố.
