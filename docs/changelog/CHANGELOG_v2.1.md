# VXPEngine 2.1.0 — Pixel modes và Scene Animation

## Editor Assets

- Bút pixel có submenu Pixel Art 8-bit, 16-bit và 32-bit.
- 8-bit dùng lượng tử màu RGB332; 16-bit dùng RGB565; 32-bit giữ ARGB8888.
- Mỗi chế độ tự đặt preset lưới 8×8, 16×16 hoặc 32×32 và dùng render nearest.
- Thêm tab Scene Timeline để chụp canvas/vùng chọn thành cel/frame.
- Hỗ trợ cập nhật, nhân đôi, xóa, đổi thứ tự và duration riêng cho từng Scene.
- Có phát, tạm dừng và loop xem trước trên canvas.
- Nút Áp dụng đóng gói timeline thành `<asset>_ani.png` và `assets/data/<asset>.ani.dtfe`.
- Nếu chỉ có atlas frames, descriptor `.ani.dtfe` tham chiếu PNG chính mà không tạo spritesheet phụ.
- Metadata `.asset.dtfe` nâng lên format version 2 và ghi `pixel_mode_bits`, `scene_timeline`, đường dẫn descriptor animation.

## Phiên bản

- `ENGINE_VERSION` nâng lên `2.1.0`.
