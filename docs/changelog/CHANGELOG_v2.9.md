# VXPEngine v2.9.0

## Preview 2D và Scene Tree

- Thêm gộp nhóm/tách nhóm trực tiếp trong Preview 2D.
- Tên nhóm tự tăng `Group_1`, `Group_2` và hỗ trợ đổi tên.
- Hiển thị nhóm lồng các thành phần trong Scene Tree.
- Layer order kiểu Photoshop: Front, Forward, Backward, Back.
- Align Left/Center/Right, Top/Middle/Bottom và Distribute H/V.
- Flip Horizontal/Vertical, Lock/Unlock, Copy/Paste, Duplicate và Delete.
- Chuột phải Preview và Scene Tree dùng cùng pipeline thao tác.

## Inspector

- Opacity cho một node, nhiều node hoặc cả nhóm.
- Code ID, Group, Members, Visible, Locked, Blend Mode, Tint và Z Index.
- Cụm nút Layers & Arrange.
- Cuộn dọc ẩn để bảng thuộc tính không chiếm chiều ngang.

## Nhiều màn chơi

- Screen Registry độc quyền: `assets/scenes/screens.dtfe`.
- Thêm, đổi tên, nhân đôi, xóa và chuyển màn từ Scene Panel.
- Mỗi màn mở trong một Preview tab riêng.
- `Main` là màn khởi động và được bảo vệ khỏi xóa.

## Java/libGDX bindings

- Sinh `src/scene_bindings.h` từ toàn bộ màn, node và nhóm.
- `DtfeSceneRuntime.find/require` truy cập thành phần theo ID, tên hoặc Code ID.
- `SceneNode` cho phép cập nhật position, rotation, scale, opacity, visibility, z-index, tint, text và camera zoom từ gameplay.
- `SceneGroup` cho phép điều khiển opacity, visibility và lock của cả nhóm.
- Runtime áp dụng group opacity/visibility và tint khi render.

## Nâng cấp dự án

- Scene cũ tự bổ sung `screen_id`, `groups`, node ID, `code_name`, lock, blend và tint.
- Runtime do VXPEngine sinh được nâng cấp lên marker `VXPE_GENERATED_DTFE_RUNTIME_V3`.
- Gameplay Java do người dùng chỉnh sửa không bị ghi đè.
