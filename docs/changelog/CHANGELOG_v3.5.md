# VXPEngine v3.5.0

- Các thao tác Import ảnh/tài nguyên dùng hộp thoại tệp mặc định của Windows.
- TitleSet có nút Import riêng; ảnh nhập được tự phân loại vào Controls, Skills, Tiles/Terrain hoặc Characters.
- Preview 2D có menu chuột phải **Mở Keyframe / Điểm neo** cho một thành phần đang chọn.
- Keyframe Editor mở thành cửa sổ frameless riêng, hiển thị asset, điểm neo kéo trực tiếp và danh sách keyframe theo thời gian.
- Keyframe lưu Position, Rotation, Scale, Opacity, Anchor X/Y và interpolation vào scene `.dtfe`.
- `VXPEngineSceneBindings.java` tự sinh `ANCHOR_X`, `ANCHOR_Y`, `KEYFRAME_COUNT` và `KEYFRAMES_JSON`.
