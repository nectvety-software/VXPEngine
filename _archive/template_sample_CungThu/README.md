# CungThuBongDen — Cung Thủ Bóng Đêm (.vxp / MRE)

Game arcade bắn cung 2D pixel-art cho điện thoại MRE (Nokia 225/220...), màn hình dọc **240x320**.
Người chơi hóa thân cung thủ trong lâu đài tối, chống lại các đợt tấn công của ogre và rồng lửa,
có trùm ogre đỏ mỗi 5 đợt, cửa hàng nâng cấp giữa các đợt.

![Thể loại] Wave-arena side-scroller · 20 fps · RGB565 · 1 file `.vxp` chạy trực tiếp từ thẻ nhớ

## Cấu trúc thư mục
```
assets/            Ảnh gốc (title, tileset, spritesheet, audio) + tools/
  tools/           sprite_manifest.txt (bảng kê kích thước sprite)
maps/              arena1.txt — bản đồ đấu trường 10x13 ô (24px/ô)
data/              (trống, dành cho dữ liệu mở rộng)
src/               Mã nguồn C của game (game, draw, gfx, res, main)
docs/              keyboard_mapping.txt, asset_sheet.md, asset_sheet_preview.png
resources/gen/     73 sprite .raw (RGB565 + mask 1-bit) cắt sẵn theo sprite_manifest.txt
resources/pack/    Bản sao phẳng dùng khi đóng gói resources.res (sinh khi build)
cmake/ common/ mreapi/ run/             Khung build .vxp (toolchain ARM)
project.vxp.json   Descriptor: App ID riêng của project (do VXPEngine cấp)
build-arm/         Output .vxp chưa ký (máy thật)
build-arm-signed/  Output .vxp ĐÃ KÝ cert100 (chạy trên máy retail)
build-win32/       Output .vc.vxp cho giả lập MREmu
```

> **Không có thư mục `signing/` ở đây.** Khóa ký `certid=100` là tài sản của
> VXPEngine (`VXPEngine/signing/`). Project luôn ở mặc định `CERTID=1` /
> `CERT=none`; khi build bản ký, VXPEngine truyền khóa và `certid` từ bên ngoài.

## Build
Yêu cầu: CMake + Visual Studio 2022 (Win32/MREmu), MSYS2 MinGW
(`C:\msys64\mingw64`, có `arm-none-eabi-gcc`) cho ARM, TinyMRESDK + MRE SDK
(đường dẫn đã ghi sẵn trong script, đổi nếu cần).

```bat
run_mremu.bat               :: build win32 + chạy giả lập MREmu (test trên PC)
build_arm.bat               :: .vxp chưa ký -> build-arm\main\<app>.vxp (chạy cmd thuần, không cần Git Bash)
```

Bản **signed (certid 100)** do chính VXPEngine build bằng nút **Build ARM Signed**:
engine truyền `-DAPPID=<App ID riêng của project> -DCERTID=100 -DCERT=<khóa engine>`
thẳng vào CMake — khóa ký không bao giờ nằm trong project, và trong project
không còn script ký nào để chạy tay.

Máy thật: chép `.vxp` vào thẻ nhớ (vd `E:\Others\`) và mở từ menu ứng dụng MRE.
**Phải dùng bản signed** (Build ARM Signed) — bản chưa ký/appid 0 sẽ không mở trên máy retail.
App ID của project xem trong `project.vxp.json` hoặc trên thanh trạng thái VXPEngine.

## Điều khiển (bàn phím điện thoại)
| Phím | Trong game | Màn hình khác |
|------|-----------|----------------|
| 2 / Lên | Nhảy (giữ 8 để leo xuống khi trên thang) | — |
| 4 / 6 | Đi trái / phải (qua phải thang = bước ra) | — |
| 5 | **Bắn tên** | Xác nhận / Bắt đầu |
| 7 | Power Shot — tên xuyên, x3 sát thương (30 MP) | — |
| 9 | Multi Shot — 3 tên quạt (40 MP) | — |
| 0 | Dash lướt nhanh + miễn sát thương (20 MP) | — |
| * | Uống thuốc hồi 50 HP | — |
| 1-4 | — | Mua vật phẩm trong SHOP |
| Phím trái (LSK) | Tạm dừng | — |
| Phím phải (C) | Tạm dừng | Thoát / lưu điểm |

Chi tiết đầy đủ: `docs/keyboard_mapping.txt`. Bản phím PC khi chạy MREmu: Numpad đảo ngược
theo layout điện thoại (Numpad5=5, Numpad6=phải, Numpad8=phím 2/nhảy), Enter=OK, `/`=phím trái,
RShift=phím phải.

## Luật chơi
- Mỗi đợt (wave) sinh ogre bộ hành + rồng lửa bay phun cầu lửa; **đợt 5, 10, 15... có trùm ogre**
  ném đá và gây sát thương tiếp xúc.
- Hạ hết địch: +5 tên, +điểm, mở **SHOP** — mua Damage +2, Max HP +20, +10 tên, Max MP +10 bằng vàng.
- Vàng/ngọc rơi từ địch: đi qua để nhặt. Ngọc +15 MP. Tên hồi chậm theo thời gian.
- Bãi gai (`H` trên bản đồ) gây 10 sát thương khi đứng lên. Thang `L` leo lên các tầng.
- HP/MP hiển thị góc trái; MP tự hồi 1/1.5s. Chết → GAME OVER, lưu điểm cao vào
  `@CungThuBongDen\save.dat` trên thẻ nhớ.

## Đồ họa & tài nguyên
- Toàn bộ sprite lấy từ bộ asset gốc của dự án (`assets/`), đã cắt sẵn
  theo `assets/tools/sprite_manifest.txt` (73 sprite).
- Định dạng `.raw` tự mô tả: header 8 byte (w, h, opaque, reserved) + pixel RGB565 LE
  + mask trong suốt 1-bit. Load bằng `vm_load_resource` từ `resources.res` đóng gói sẵn.
- Âm thanh: 4 hiệu ứng mp3 đóng gói trong .vxp, tự extract ra thẻ nhớ lần đầu chạy
  (`@CungThuBongDen\` trên ổ removable).

## Kiểm thử
Đã chạy trên giả lập MREmu: khởi động, vẽ đủ lớp parallax + HUD, di chuyển/nhảy/bắn,
3 kỹ năng + cooldown, ogre đuổi và cận chiến, dọn wave → shop → wave mới, chết → GAME OVER
→ chơi lại, lưu/đọc save.dat, extract sfx. `tools/sendkeys_test.ps1` = script gửi phím giả lập.

## Bản quyền / ghi nhận
Asset âm thanh từ các gói SFX miễn phí thu thập trong `Audio Assets/` và `assets/audio/`.
Mã nguồn theo mẫu CmakeMreTemplate + TinyMRESDK (build/ký .vxp).
