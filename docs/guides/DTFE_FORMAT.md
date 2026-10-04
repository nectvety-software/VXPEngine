# Định dạng VXPEngine `.dtfe`

`.dtfe` là định dạng văn bản UTF-8 độc quyền của VXPEngine. Nội dung hiện dùng JSON để dễ đọc, quản lý phiên bản và theo dõi thay đổi bằng Git. Ảnh trong Editor Assets vẫn được lưu ở dạng `.png`; `.dtfe` chỉ chứa dữ liệu mô tả project, scene, texture, frame, collision và animation.

## Vị trí chuẩn

- `project.dtfe`: descriptor nhận dạng project và target build.
- `assets/scenes/main.dtfe`: scene 2D mặc định, camera và viewport.
- `<ảnh>.asset.dtfe`: metadata đặt cạnh PNG tương ứng.
- `assets/scenes/<tên_assets>.ani..dtfe`: animation, hành động hoặc cảnh chuyển động.

## Tương thích

VXPEngine 2.2 vẫn đọc các đường dẫn cũ `scenes/main.dtfe`, `scenes/main.nova`, `assets/data/*.asset.dtfe` và tên animation `.ani.dtfe`. Tệp mới luôn dùng cấu trúc `assets/*` và hậu tố độc quyền `.ani..dtfe`.

## Animation descriptor `.ani..dtfe`

Ví dụ `assets/scenes/hero.ani..dtfe`:

```json
{
  "format": "VXPEngine Animation",
  "format_version": 1,
  "extension": ".ani..dtfe",
  "asset": "assets/scenes/hero.png",
  "texture": "assets/scenes/hero_ani.png",
  "source_mode": "scene_timeline",
  "pixel_mode_bits": 16,
  "animation": {
    "name": "run",
    "fps": 12,
    "loop": true,
    "frame_count": 6
  },
  "frames": [
    {
      "name": "scene_001",
      "x": 0,
      "y": 0,
      "width": 64,
      "height": 64,
      "duration_ms": 83
    }
  ]
}
```

`source_mode` có hai giá trị:

- `scene_timeline`: các Scene được đóng gói thành PNG `assets/scenes/<tên_assets>_ani.png`.
- `atlas_frames`: frame tham chiếu trực tiếp vùng chữ nhật trong PNG tài nguyên chính.

## Screen Registry và Group metadata — v2.9

Danh sách màn chơi được lưu dưới dạng văn bản JSON tại:

```text
assets/scenes/screens.dtfe
```

```json
{
  "format": "VXPEngine Screen Registry",
  "format_version": 1,
  "active_screen": "main",
  "screens": [
    {
      "id": "main",
      "name": "Main",
      "file": "assets/scenes/main.dtfe",
      "java_name": "Main"
    }
  ]
}
```

Một scene v2.9 có `screen_id`, `groups` và node IDs ổn định:

```json
{
  "name": "Level Forest",
  "screen_id": "level_forest",
  "type": "LibGDXScene",
  "groups": [
    {
      "id": "group_enemies",
      "name": "Enemies",
      "opacity": 0.8,
      "visible": true,
      "locked": false
    }
  ],
  "children": [
    {
      "id": "enemy_slime_01",
      "code_name": "EnemySlime",
      "name": "Slime",
      "type": "Sprite2D",
      "group_id": "group_enemies",
      "asset": "assets/map/texture/slime.png",
      "position": [320, 180],
      "rotation": 0,
      "scale": [1, 1],
      "opacity": 1,
      "visible": true,
      "locked": false,
      "blend_mode": "Normal",
      "tint": "#FFFFFFFF",
      "z_index": 4
    }
  ]
}
```

`id` được runtime dùng để ánh xạ gameplay. `name` là tên hiển thị trong Scene Tree. `code_name` sinh hằng Java thân thiện trong `VXPEngineSceneBindings.java`. Đổi `name` không làm mất liên kết code nếu `id` không đổi.
