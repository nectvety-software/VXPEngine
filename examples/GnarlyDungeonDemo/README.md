# GnarlyDungeonDemo

Mẫu góc nhìn thứ nhất lấy cảm hứng hình ảnh từ [Gnarly Crawl](https://gnarlycrawl.bobunderforest.me/): ngục đá, gỗ cũ, ánh đuốc vàng đỏ, bộ xương, sân thành dưới trời mana tím xanh và kiếm cận chiến. Tài nguyên gốc được vẽ bằng generator trong project; không dùng asset của game tham chiếu.

Menu Play / Guide; khám phá, đánh bộ xương, tìm chìa khóa trên bệ đá phía xa bên phải sân và dùng ở cửa song sắt gần điểm xuất phát. Hết HP sẽ có màn thua và restart; mở cửa sẽ có màn hoàn thành.

- 2/8 hoặc Up/Down: tiến/lùi.
- 4/6 hoặc Left/Right: xoay camera.
- 5 / OK: chém kiếm / chọn menu.
- 7: nhặt chìa khóa / mở cửa khi ở gần.
- 9: pause; 0: restart; Back: về menu, rồi thoát.

240×320 portrait, render trực tiếp trên thiết bị MRE 240×320. Mở `project.vxp.json` bằng VXPEngine để build ARM. Tài nguyên RGB565/A8 nhúng cùng VXP, không cần thư viện Python khi chạy. `tools/make_assets.py` tái tạo PNG, metadata Editor Assets và header nhúng (Python + Pillow).

Lõi mới: `VxpDungeonFx`, ánh sáng màu theo khoảng cách và trời mana chuyển động. Editor Assets: preset `Game · Dungeon Synth`. Xem tài liệu `docs/DUNGEON_SYNTH_3D.md` của engine. Mẫu chưa hỗ trợ VR tracking, vật lý tay, âm thanh dungeon synth hoặc PBR; ảnh preview là framebuffer renderer thật. Chưa đo tốc độ trên điện thoại MRE thật.

© VXPstore. All rights reserved. Website: https://qeafivels.com/
