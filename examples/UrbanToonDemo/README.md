# Urban Toon Demo

Showcase 240×320: nhân vật patin 3D có pose tay/chân, áo vàng và tai nghe,
viền inverted hull và bóng đổ; phố có cửa hàng, ban công, biển hiệu, mái hiên,
vỉa hè lát gạch, cây đa giác, xe bus, xe đỗ, cầu bộ hành và vạch qua đường.
Camera yaw/pitch tự hướng về nhân vật khi vị trí bị giới hạn tại lề phố.

4/6 steer; 2/8 speed; 5 jump; 7 rail; 0 camera; 9 pause; Back exit.
Mẫu minh họa hình ảnh/chuyển động; chưa có collision hay hệ mission hoàn chỉnh.

Mở project trong VXPEngine để Build/Run ARM. Atlas `assets/skater_atlas.png`
và animation `assets/skater_roll.ani..dtfe` có 6 frame 96×144, được render từ
chính mesh nhân vật live và mở được trong Editor Assets.

Tạo lại tài nguyên bằng Python/Pillow:
- `tools/make_city.py`: 7 texture phố gốc và header RGB565 nhúng.
- `tools/bake_actor.py`: atlas mesh 3D và descriptor (cần native g++ trên PATH).
- `tools/make_skater.py`: artwork 2D legacy riêng và header facade/graffiti.

Mesh nhân vật dùng 384 vertex / 640 face trong buffer cố định. Texture và mesh
được nhúng vào VXP, không cần Python/Pillow khi chạy.
`tests/preview.cpp` kiểm tra jump/grind, ba góc camera, pause và framebuffer guards;
`tests/bake_actor.cpp` kiểm tra kích thước mesh và coverage của atlas.

© VXPstore. All rights reserved. Website: https://qeafivels.com/

Chế độ tiết kiệm RAM: cảnh 3D render 120×160, upscale Scale2x 2× ra 240×320; HUD/nhân vật full resolution. Buffer màu + depth chỉ 76.800 byte, bỏ buffer xoay 153.600 byte. RAM khai báo MRE 1024KB. Chi tiết cảnh nhỏ sẽ có pixel lớn hơn; mesh/texture không đổi.

Đo ARM bằng `arm-none-eabi-size`: BSS giảm từ 328.900 xuống 92.104 byte (giảm 236.796 byte, khoảng 72%). Con số này không bao gồm layer framebuffer, heap và stack của MRE.

Nâng cấp đồ họa: upscale Scale2x giữ palette và cải thiện đường chéo; nhân vật mesh vẽ ở độ phân giải đầy đủ trong tile 80×120, dùng lại buffer màu 120×160 sau khi upscale. Depth của phố được giữ để clip nhân vật. Thêm bóng nhà trên đường, ban công, skyline/mây, nghiêng người khi rẽ và sparks khi grind. Không cấp thêm buffer thường trú cho nhân vật.


PS1 street gameplay update (Erman Malak video reference): muted blue/grey palette with warm lamps, bevelled car bodies and sloped windscreens, shop interiors behind dithered glass, sloping canopies, octagonal light pools and 8-sided street bins. Actor uses directional face lighting without inverted-hull outlines. In-place RGB555 rounding and nearest upscale preserve polygon edges. No extra buffers or physics/hitbox changes.

Startup opens the playable street: 4/6 steer, 2/8 speed, 5 jump, 7 grind, 0 camera, 9 pause, Back exit. The martini prop study is no longer linked into the game. Video is a style reference only; no copied video pixels or audio.

Rebuild 7 textures with `tools/make_city.py`, character atlas and Editor Assets descriptors with `tools/bake_actor.py`. Asset provenance/contracts: `assets/ps1_street.manifest.json`. Viewport 240x320; world 120x160; actor tile 80x120; MRE RAM cap 1024KB.

Validated PS1 street build: native gameplay/camera/buffer guards and 17/17 core checks pass; ARM signed VXP verifies OK. ARM BSS 92,136 bytes (+32 from original city), excluding MRE framebuffer/heap/stack. Native previews: `preview.png`, `preview_ps1_street.png`. Emulator screen capture is unavailable (timeout); no emulator visual verification claimed.
