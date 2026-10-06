# Dungeon Synth 3D

VxpDungeonFx bổ sung API C không cấp phát heap:
- `vxpe_dungeon_light565`: ánh sáng màu theo khoảng cách bình phương, tối đa 16 đèn, ambient 0..255. Radius bằng 0 tắt đèn. Kết quả dùng làm material albedo/tint trước render texture.
- `vxpe_dungeon_mana_sky`: bầu trời mana chuyển động vào framebuffer RGB565 do caller sở hữu, kích thước tối đa 2048×2048.
- `VXPE_ARTSTYLE_DUNGEON_SYNTH`: preset ánh đuốc vàng, đá cũ và fog tím. Enum mới nối cuối để giữ giá trị cũ.

GnarlyDungeonDemo dùng VxpToon3D cho tường/sàn/cột/tháp perspective có depth, texture RGB565, bộ xương A8, kiếm foreground và các đèn màu. Lighting lấy mẫu tại tâm mặt quad, phù hợp mesh chia nhỏ, không phải per-pixel PBR hay shadow map. Skeleton là billboard; không có VR tracking hoặc tương tác vật lý tay.

Mẫu chạy 240×320 dọc, ghi trực tiếp vào layer MRE, bỏ buffer xoay, cần framebuffer/depth khoảng 300KB và texture nhúng. Chưa đo FPS trên thiết bị MRE thật.

Trang tham chiếu: https://gnarlycrawl.bobunderforest.me/ . Tài nguyên mẫu do generator trong project tự dựng, không lấy asset của trò chơi gốc.
