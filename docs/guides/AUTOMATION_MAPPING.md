# VXPEngine v4.2 — Automation Mapping

## Mục tiêu

Mọi Sprite, Tile, Shape hoặc Group trong Frame Preview đều có thể được gán vai trò gameplay. Ánh xạ chỉ bổ sung metadata và runtime helper; mã Java của người dùng vẫn là nguồn điều khiển gameplay chính.

## Mở công cụ

- Chuột phải thành phần trong Frame Preview → **Ánh xạ vai trò / tự động hóa…**
- Chuột phải layer trong Scene Tree → **Ánh xạ vai trò / tự động hóa…**
- Inspector → **Automation / Gameplay** → **Cấu hình ánh xạ…**

## Vai trò có sẵn

- Player
- Virtual Joystick
- Direction Button
- Action Button
- Skill Button
- Ground
- One-way Platform
- Static Obstacle
- Hazard
- Trigger Zone
- Portal
- Collectible
- Enemy
- Spawn Point
- Camera Target
- Decoration
- Custom / code-only

## Dữ liệu lưu trong scene

```json
{
  "automation": {
    "enabled": true,
    "role": "virtual_joystick",
    "input_action": "MOVE_AXIS",
    "axis": "both",
    "physics": "none",
    "collision_shape": "circle",
    "dead_zone": 0.18,
    "sensitivity": 1.0,
    "tags": ["mobile", "control"],
    "event_channel": "",
    "target_screen": ""
  }
}
```

## Java runtime helper

```java
scene.update(delta);

Vector2 move = scene.inputAxis("MOVE_AXIS", new Vector2());
boolean jumpHeld = scene.inputPressed("JUMP");

DtfeSceneRuntime.SceneNode player = scene.findByRole("player");
Array<DtfeSceneRuntime.SceneNode> grounds = scene.findByTag("ground");
Array<DtfeSceneRuntime.SceneNode> colliders = scene.getColliders();
```

`Virtual Joystick` tự tính trục X/Y từ vị trí touch bên trong bounds của component. Nút thường trả `1` khi đang chạm và `0` khi thả.

## Ground và collider

- `static`: nền/vật cản cố định
- `dynamic`: vật thể động
- `kinematic`: điều khiển bằng code
- `sensor`: vùng kích hoạt, không chặn chuyển động
- `one_way`: platform một chiều

Runtime cung cấp bounds, contains và overlap helper. Polygon được lưu đầy đủ để code tùy chỉnh sử dụng; helper mặc định dùng bounds fallback.

## Portal và tín hiệu

Khi gán `Portal` kèm map đích, engine tự thêm sự kiện `on_overlap → change_screen` nếu chưa tồn tại. Hazard, Collectible và Trigger Zone có thể phát `event_channel` để gameplay code xử lý.
