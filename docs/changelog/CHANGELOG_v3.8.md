# VXPEngine v3.8.0

## Animation Player

- Thêm cửa sổ Animation Player độc lập trong Editor Assets.
- Chọn/bỏ từng frame bằng thumbnail.
- Shift + click để chọn dải frame.
- Chọn tất cả, bỏ chọn và đảo vùng chọn.
- Điều chỉnh 1-60 FPS và phát loop.
- SPACE để phát/dừng; phím trái/phải để chuyển frame.
- Nền preview: checker, đen, green screen và trong suốt.
- Nhấp preview để chuyển Fit/x2; tùy chọn x1/x2/x4/x8.
- Hỗ trợ hai nguồn: Atlas Frames và Scene Timeline.
- Chỉ đóng gói các frame được chọn vào `.ani..dtfe`.
- Lưu `selected_indices`, `selection_mask_hex`, FPS, loop, background và zoom trong descriptor.
- Tương thích loader animation hiện tại của libGDX.
