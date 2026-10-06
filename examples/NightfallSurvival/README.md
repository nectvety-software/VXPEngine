# Nightfall Survival

Mẫu FPS sinh tồn cho VXPEngine/MRE VXP, 240×320 landscape.
Lấy cảm hứng từ video Lockie: góc nhìn thứ nhất, zombie sprite, texture pixel tối,
tay cầm súng, căn nhà gỗ nối với sân nghĩa địa. Artwork, map và tên game là bản
vẽ riêng; không trích xuất tài nguyên Call of Duty hoặc video.

## Chơi

- 2/8 hoặc Up/Down: đi tới/lùi; 4/6 hoặc Left/Right: xoay góc nhìn.
- 1/3: strafe; 5/OK: bắn; 0: nạp đạn; 7: tương tác; 9: pause.
- Back: về menu. Menu có Play, How to play và Exit; chết có thể bấm 5 chơi lại.
- Điểm: trúng 10, hạ zombie tổng 100, qua wave thêm 100. Địch tăng máu/tốc độ.
- Gần cửa ra sân: 500 điểm mở cổng; gần điểm tiếp đạn tại (2.5,5.5):
  200 điểm mua reserve; sửa cửa sổ tại (3.5,6.4) nhận 10 điểm mỗi thanh.
- Medkit tại (10.5,10.5): 300 điểm hồi máu. Có khoảng nghỉ giữa các wave.
- Touch: chạm trái trên/dưới để tới/lùi, trái giữa/phải để xoay;
  chạm giữa để bắn, HUD dưới trái để tương tác, dưới phải nạp đạn,
  HUD trên để pause. Hướng portrait tự xoay khung game.

## Cấu trúc

`src/game.cpp`: raycaster, texture floor/ceiling, fog, wall depth clipping,
transparent billboards và luật chơi. `src/main.cpp`: vòng đời MRE, timer, input.
`assets/*.png`: artwork mở được bằng Editor Assets; `src/art.h`: RGB565 nhúng
để bản VXP chạy không cần thư viện Documents trên máy phát triển.
`tools/make_assets.py`: tạo lại artwork có seed cố định, cần Python/Pillow.
`tests/game_test.cpp`: kiểm tra collision, occlusion, ammo/reload, points,
interact, pause, zombie attacks, wave progression và xuất framebuffer thực.

Renderer 2.5D dùng DDA ở 160 cột nhân đôi, floor/ceiling 2×2, tối đa 18 zombie.
Đây là mẫu single-player, chưa có multiplayer hay audio; không dùng mesh 3D.

© VXPstore. All rights reserved.
Website: https://qeafivels.com/
