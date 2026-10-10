# Sprite nhân vật bốn hướng

`graphics/VxpActorSprite2D.h` thêm controller C/C++ cho atlas RGB565+A8.
Mỗi hàng theo thứ tự North, East, South, West. Mỗi cột là một frame.
Định nghĩa bốn clip: Idle, Walk, Cast, Reel; mỗi clip có cột đầu,
số frame, thời gian/frame và chế độ loop. Anchor xác định vị trí chân.

```c
VxpeActorState2D actor;
vxpe_actor_init(&actor);
vxpe_actor_set(&actor, VXPE_ACTOR_EAST, VXPE_ACTOR_WALK);
/* Atlas và buffer do ứng dụng sở hữu; không cấp phát heap. */
vxpe_actor_update(&actor, &atlas, dt_ms);
vxpe_actor_draw(framebuffer, 240, 320, &atlas, &actor, foot_x, foot_y);
```

Đổi hướng giữ pha hoạt ảnh; đổi action bắt đầu lại clip. Gọi lại cùng
action không reset. Clip không loop giữ frame cuối và đặt `finished`.
API trả 0 nếu atlas/clip/state không hợp lệ; hỗ trợ clipping qua renderer A8.
Nếu thay atlas có số frame khác, hãy init state trước khi phát.

Ví dụ `examples/Hopscorch` dùng 32 ô 20×30, atlas 160×120:
idle cột 0, walk cột 1–4, cast cột 5–6, reel cột 7.
Nguồn pixel nằm ở `src/hero.h` và generator `tools/prepare_actors.py`.
Generator tạo PNG, VXA8, JSON metadata và header dùng trong firmware.
Atlas có hai frame nghỉ giống nhau trong chu kỳ đi bộ bốn frame.
Fish và bobber dùng atlas props 32×16 riêng.

Kiểm thử lõi bao gồm đổi hướng/action, loop với dt lớn, clip không loop,
chỉ số frame, clipping, alpha trong suốt và dữ liệu atlas không hợp lệ.
