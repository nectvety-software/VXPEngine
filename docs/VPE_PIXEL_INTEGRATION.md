# VPE Pixel trong Editor Assets

`D:\desktop-webapps\VPEPixel` là mã nguồn ứng dụng VPE Pixel;
`C:\Users\doxuanhop\Documents\VPE Pixel` là thư viện dữ liệu dùng chung,
không phải một ứng dụng thứ hai. Editor Assets tích hợp giao diện Qt của
VPE Pixel trong cùng cửa sổ qua tab **VPE Pixel**.

## Sử dụng

1. Mở Editor Assets, chọn tab **VPE Pixel**.
2. Dùng gallery (nút `Glr`) để duyệt thư viện Documents/VPE Pixel,
   hoặc File → Open để mở `.vpe` và `.vpea`.
3. Vẽ bằng pencil/eraser/fill/line/rectangle, chọn palette, chỉnh frame,
   xem onion skin và phát timeline như trong VPE Pixel.
4. Bấm **Nhận ảnh / animation vào Assets** để đưa vào canvas/timeline
   VXPEngine; **Áp dụng & lưu** ghi PNG và metadata/animation vào project.
   Bấm **Đưa canvas / timeline sang VPE Pixel** để chỉnh theo chiều ngược lại.

Nút **Áp dụng & lưu** khi đang ở tab VPE tự nhận document rồi lưu qua
pipeline Assets. File → Save trong VPE vẫn lưu `.vpe/.vpea` vào thư viện
gốc hoặc đường dẫn do người dùng chọn. Việc mở và chuyển dữ liệu không
tự ghi đè file gốc. Công cụ dùng trực tiếp thư viện chung, không chép toàn
bộ gallery vào project.

VPE565 không có alpha: khi gửi ảnh sang VPE, alpha được trộn trên nền trắng.
Khi nhận, mặc định giữ trắng là màu ảnh; chỉ bật **Trắng → trong suốt** nếu
trắng là nền cần xóa. `.vpea` dùng một duration chung; timeline có duration
khác nhau sẽ chuyển về FPS hiện tại. Uniform duration và loop được giữ nguyên.

## Mã nguồn và đóng gói

`app/vendor/vpe_pixel` là snapshot mã nguồn/QSS từ VPEPixel để bản cài
VXPEngine không phụ thuộc đường dẫn ổ D. `INTEGRATION.json` ghi nguồn và
checksum của snapshot; không tự đồng bộ thay đổi mã nguồn ngoài dự án.
`widgets/vpe_pixel_panel.py` nhúng UI và chuyển RGB565/animation. Theme và
shortcut chỉ áp dụng trong panel; không thay QSS/palette của VXPEngine.
PyInstaller kèm QSS trong `vendor/vpe_pixel/style`.

### Thư viện đi cùng EXE

Snapshot `app/vendor/vpe_pixel/library` chứa 1.367 tài nguyên (VPE, VPEA,
PNG, GIF, BMP và JSON); `tools` chứa 17 script tạo mẫu gốc.
PyInstaller đưa toàn bộ payload vào thư mục `app/vendor/vpe_pixel` cạnh EXE.
Phải phân phối nguyên thư mục bản build hoặc bộ cài MSI, không chỉ riêng EXE.
Công cụ vẽ và codec chạy bằng Qt/Python đã đóng gói; các script tạo mẫu
được kèm dưới dạng mã nguồn, chạy riêng cần Python/PySide6 và Pillow phù hợp.

Khi khởi tạo tab VPE Pixel, các tài nguyên còn thiếu được chép vào Documents/VPE Pixel.
File đã tồn tại luôn được giữ nguyên; chỉnh sửa và exports nằm trong thư viện
người dùng, không ghi vào Program Files. Nếu Documents không tạo được,
thư viện dùng thư mục APPDATA/VXP Pixel Editor/VPE Pixel.
Không cần hai thư mục nguồn trên máy phát triển để sử dụng bản đóng gói.

`library-manifest.json` và `tools-manifest.json` kiểm tra SHA256 trước khi
freeze và trước khi tạo MSI; thiếu hoặc sai payload sẽ dừng đóng gói.
Kiểm tra độc lập: `reports/harness_vpe_bundle.py`.

Kiểm tra: `reports/harness_vpe_integration.py` dùng file tạm để kiểm tra
codec, alpha, animation, Undo, save vào assets, shortcut và theme.
