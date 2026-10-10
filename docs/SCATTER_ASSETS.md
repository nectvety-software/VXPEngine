# Cọ địa hình và rải vật thể

Editor Assets → Terra · Tilemap: Mẫu địa hình giữ công cụ kéo cọ liên tục, tự nối 16 viền, xóa và Undo/Redo.
Mẫu đá mở atlas 4 biến thể gốc, 16×16 px và map 240×320. Chọn ô đầu, đặt số Biến thể rồi Gắn từ ô chọn.
Bật Cọ rải vật thể, đặt cỡ cọ, Mật độ %, Cách (ô), Seed và kéo chuột trái; chuột phải xóa. Để đá trên layer riêng nếu muốn rải trên nền đã vẽ; cọ không ghi đè ô có sẵn hoặc layer khóa.
Cách=2 giữ khoảng cách Chebyshev tối thiểu 2 ô. Seed cố định tái lập kết quả với cùng bản đồ trống và cùng thứ tự đường cọ. Kết quả đã đặt lưu trong .terra.json; thông số cọ là trạng thái phiên làm việc.
Đưa tilemap vào Assets xuất PNG và Save & Apply giữ tài liệu .terra.json cùng atlas di động.

## Lõi native
`graphics/VxpScatter2D.h`: coremre::VxpScatter2D::hash và paint. Không cấp phát động. paint nhận vùng ô đã cắt theo map, số biến thể, mật độ 0–100, khoảng cách, seed, callback occupied và emit. occupied trả false ngoài map; emit cập nhật ô ngay để những vị trí sau tránh chồng. Dùng vùng nhỏ khi sinh trong gameplay; xuất bản đồ sẵn để tiết kiệm CPU.

Hai video chỉ dùng tham khảo thao tác: rải đá theo nét cọ và dựng địa hình tự nối. Công cụ hiện là tilemap 2D cho VXP, không chỉnh mesh 3D, xoay/scale mesh hay mô phỏng physics 3D. PNG mẫu tự tạo, không trích hình hoặc âm thanh video.

Kiểm tra: tools/test_scatter_workflow.py; tools/test_terrain_workflow.py; engine/coremre/tests/vxpe_scatter_regression.cpp.
