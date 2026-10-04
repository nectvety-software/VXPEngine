# VXPEngine 2.4.0 — Asset Folder Actions & Center Tab Workflow

## Assets

- Ghim nút ba chấm của từng thư mục Assets sát mép phải của cây thư mục.
- Dùng cột thao tác cố định để nút không bị lệch theo mức thụt lề thư mục.
- Nhấp đúp tệp ảnh mở tab xem trước nội bộ trong vùng trung tâm.
- Nhấp đúp tệp văn bản, Java, C/C++, Gradle hoặc `.dtfe` mở code tab.
- Tệp nhị phân khác mở trang thông tin tài nguyên trong tab, kèm nút mở bằng ứng dụng Windows mặc định.
- Editor Assets vẫn được mở từ submenu ba chấm hoặc menu chuột phải của ảnh.

## Scene Tree

- Nhấp đúp `Main` hoặc `Camera2D` sẽ mở/kích hoạt lại tab `main.dtfe`.
- Nhấp đúp Sprite2D chọn đúng thành phần trong Preview 2D và đồng bộ Inspector.
- Camera2D được focus về vị trí camera và gửi dữ liệu thuộc tính sang Inspector.

## Center tabs

- Thêm nút đóng tab tùy chỉnh kích thước 23 px, icon rõ hơn.
- Chuột phải thanh tab có:
  - Đóng tab.
  - Đóng các tab khác.
  - Đóng tất cả tab.
- Cho phép đóng toàn bộ tab; Scene có thể mở lại từ Scene Tree.
- Tự lưu code đã chỉnh sửa trước khi đóng tab nguồn.
- Tab có thể kéo đổi thứ tự.

## Technical

- `ENGINE_VERSION = 2.4.0`.
- Bổ sung API `Viewport2D.select_node()`.
- Bổ sung signal `ScenePanel.node_open_requested`.
- Bổ sung quản lý tab trung tâm và preview tài nguyên trong `app/main.py`.
