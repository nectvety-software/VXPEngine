# Automation Runtime v4.5

Ánh xạ không thay thế code Java của người dùng. Trường `auto_execute` quyết định runtime có tự chạy gameplay cơ bản hay chỉ cung cấp input/helper cho code riêng.

## Player platformer

```json
{
  "enabled": true,
  "role": "player",
  "physics": "kinematic",
  "auto_execute": true,
  "movement_mode": "platformer",
  "move_speed": 260,
  "jump_speed": 560,
  "gravity": 1450
}
```

## Player top-down

Đổi `movement_mode` thành `top_down`. Runtime đọc joystick hoặc nút hướng để di chuyển bốn hướng.

## Input helper

```java
Vector2 axis = scene.inputAxis("MOVE_AXIS", new Vector2());
boolean jump = scene.inputPressed("JUMP");
boolean jumpStarted = scene.inputJustPressed("JUMP");
```

## Tắt tự động hóa

Đặt `auto_execute=false` để giữ metadata/Java bindings nhưng tự viết toàn bộ gameplay trong `VxpGame.java`.
