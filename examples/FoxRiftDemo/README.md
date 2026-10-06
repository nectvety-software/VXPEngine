# Vaelora Duel — 240×320

Dự án solo offline 1vs1 trong thư mục `FoxRiftDemo`, nay dùng tên game
**Vaelora Duel**, logo lăng kính và ba hero thiết kế mới. Asset hồ ly cũ đã
được thay bằng Velin, Torvan và Nimara. Nền đấu trường băng là artwork riêng.

Luồng game: splash → chọn hero và hero của bot → đấu 1vs1 → kết quả → đấu lại
hoặc đổi tướng. Hạ đối thủ để thắng. Giới hạn 120 giây; hết giờ so phần trăm
HP còn lại, bằng nhau là hòa. Không có lính, trụ hay mục tiêu hạ 12 lính của
bản cũ trong chế độ này.

## Menu và điều khiển

| Phím | Menu chọn tướng | Trong trận |
|---|---|---|
| 4 / 6 | Chọn hero người chơi | Trái / phải |
| 2 / 8 | Chọn hero bot | Lên / xuống |
| 5 / OK | Bắt đầu | Kỹ năng 1 |
| 7 / 9 / 0 | — | Kỹ năng 2 / 3 / 4 |
| 1 | Hướng dẫn | Hồi 300 HP + 120 mana, hồi chiêu 15 giây |
| * | — | Pause / tiếp tục |
| 3 | — | Đấu lại |
| Back | Thoát | Về menu chọn tướng |

Đánh thường tự động trong tầm. Kỹ năng hướng về vị trí đối thủ khi kích
hoạt; projectile có thời gian bay và có thể né bằng di chuyển. Kỹ năng vùng
chỉ gây sát thương trong phạm vi. Stun khóa di chuyển, đánh và dùng kỹ năng;
slow giảm bước di chuyển về 1. Khiên hấp thụ sát thương trước HP.

## Hero

| Hero | Vai trò | HP / mana | Nội tại |
|---|---|---|---|
| Velin | Pháp sư lăng kính | 1100 / 600 | Mỗi ba lần cast nhận 50 khiên |
| Torvan | Đỡ đòn cận chiến | 1600 / 400 | Giảm 15% sát thương nhận |
| Nimara | Xạ thủ cơ động | 1000 / 650 | Hồi thêm 2 mana mỗi nhịp hồi nếu đang di chuyển |

Mana hồi 4 mỗi 300 ms. Hero không tự hồi HP ngoài kỹ năng hồi phục chung.
[Chi tiết kỹ năng, phạm vi và bot](docs/HERO_GAMEPLAY.md).

## Bot solo

Bot điều khiển một hero thực, dùng cùng HP/mana, kỹ năng, hồi chiêu, stun và
shield với người chơi. Bot suy nghĩ mỗi 350 ms: Torvan áp sát, Velin giữ
khoảng cách trung bình, Nimara đánh xa và lùi khi bị áp sát. Bot yếu máu
rút lui và dùng hồi phục nếu sẵn sàng. Bot dùng kỹ năng theo khoảng cách và
trạng thái; projectile không tự bám theo mục tiêu. AI là heuristic cho demo,
chưa có pathfinding qua vật cản hoặc hệ chiến thuật đội.

## Build / Run

Mở `project.vxp.json` trong VXPEngine rồi Build / Run hoặc:

```bat
scripts\build_arm.bat
scripts\run_vxpemu.bat
```

Bản ARM: `build-arm/main/vaelora_duel.vxp`, App ID 1053070, RAM 1500 KiB.
Build xác minh gói coremre đã ký. Script xuất VXP development chưa ký ứng dụng.
Demo đã chạy qua VXPEmu; chưa thử trên điện thoại vật lý.

## Asset và chỉnh gameplay

- `assets/source/heroes.png`, `logo.png`, `arena.png`: nguồn tạo bằng ImageGen.
- `assets/sprites/`: 12 frame, portrait, atlas và animation DTFE của ba tướng.
- `assets/ui/logo.png`: logo splash native.
- `assets/scenes/`: splash, heroes, main, result; có thể mở trong Editor Assets.
- `assets/gameplay/heroes.json`: thông số/nội tại mô tả/tên kỹ năng của roster.
- `src/scene.cpp`: cơ chế kỹ năng và AI; JSON không tự thay loại chiêu.

```powershell
.venv/Scripts/python.exe examples/FoxRiftDemo/tools/generate_assets.py
.venv/Scripts/python.exe examples/FoxRiftDemo/tools/generate_roster.py
.venv/Scripts/python.exe examples/FoxRiftDemo/tools/prepare_scene.py
```

Build ARM tự cập nhật roster khi JSON thay đổi; có thể chạy generate_roster riêng để kiểm tra. Bộ sinh kiểm tra phạm vi
stats, ASCII và thứ tự ba archetype. Người chơi và bot đọc chung header sinh.
DTFE là composition chỉnh được; bố cục UI runtime vẫn nằm trong scene.cpp.
[Prompt và nguồn thiết kế hero/logo](docs/ORIGINAL_ARTWORK.md).

## Kiểm thử

Host test kiểm tra luồng màn hình, chọn hero/bot, di chuyển, mana/hồi chiêu,
projectile trúng/né, stun, khiên và giáp, nội tại, kỹ năng của ba tướng, bot
cast/rút lui/hồi phục, pause, thắng/thua/hòa, đấu lại/Back và framebuffer guards.
`tests/run_vxpemu_smoke.py` chạy VXP ARM bằng VXPEmu tại 240×320, gửi phím thực
để đi qua splash/menu/trận/chiêu/pause/đấu lại, chụp ảnh và kiểm tra pixel nền.
Ảnh ở `tests/runtime_screenshots/`, report ở `reports/vaelora-duel/`.

## Font riêng / Font Styles

Vaelora Duel dùng ba font bitmap nguyên bản: **Vale UI** cho menu, **Prism
Display** cho tiêu đề/kết quả, **Duel Digits** cho số liệu. Chữ có shadow,
outline và highlight để đọc được trên nền đấu trường.

Trong **Editor Assets → Font Styles**, chọn vai trò title/body/numbers/hero/
accent, thử Royal Gold, Frost Cyan, Rune Violet hoặc Clean Ivory, chỉnh font,
khoảng cách và màu rồi Save. Build để áp dụng. Cấu hình nằm ở
`assets/ui/font_styles.json`; header dùng ở `src/font_styles_generated.h`.
Khi sửa JSON trực tiếp, chạy `tools/generate_font_styles.py` trước Build.

[API và source glyph](../../docs/PIXEL_FONT_STYLES.md).
