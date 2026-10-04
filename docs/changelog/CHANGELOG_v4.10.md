# VXPEngine v4.10 — Chrome giả lập bám sát VXPEmu (icon MDL2, lưới phím, multi-tap động)

Phase 5 dựng được kiến trúc lai (chrome Python + QSS theo VXPEmu, lõi chạy là
`MREmu.exe`), nhưng phần "vỏ" lúc đó mới chỉ **giống ý** chứ chưa **giống hình**:
icon lấy từ QtAwesome (FontAwesome), bàn phím xếp theo thứ tự tự nhiên, nhãn
phím điều hướng còn là chữ tiếng Việt, và dòng nhắc multi-tan nằm dưới màn hình.

Bản này chỉnh lại cho khít với ảnh tham chiếu VXPEmu (sau khi bổ sung đọc
được `8687567.PNG` thay vì chỉ suy luận từ mã nguồn), bằng cách **đọc thẳng mã
nguồn của VXPEmu** (`src/ui/MainWindow.cpp`, `src/ui/VirtualKeypadWidget.cpp`,
`src/ui/IconProvider.h`):

* **Toàn bộ icon vẽ bằng font `Segoe MDL2 Assets`** — đúng font VXPEmu dùng.
  Mã glyph nằm trong vùng Private Use Area (`U+E7xx`) nên không bao giờ bị hệ
  thống thay bằng color emoji; font này không có chữ Latin nên Qt tự ghép
  `Segoe UI` cho các ký tự còn lại (font merging).
* **Bàn phím 6×4 sao chép đúng toạ độ** của `VirtualKeypadWidget`: ô `(0,3)`
  để trống, `↑` ở `(0,4)`, phím mềm `—` ở `(0,5)`, hàng 3 của cụm điều hướng
  trống. Nhãn phím số gộp một dòng kiểu Nokia (`2 abc`), `1` và `0` để trần.
* **Glyph điều hướng** dùng icon MDL2: `↑`=ArrowUp, `⌫`=Delete (thùng rác),
  `↵`=Enter. VXPEmu gán Delete cho `MRE_KEY_BACK` và Enter cho `MRE_KEY_CLEAR`
  — ta giữ nguyên cả glyph lẫn hành vi để mặt phím khớp bản gốc.
* **Dòng nhắc multi-tap** nằm **dưới màn hình** trong cột screen
  (`EmulatorScreenColumn`), cao cố định 20 px. Ở trạng thái nghỉ hiện gợi ý
  tĩnh `Multi-tan: 2=a·b·c 3=d·e·f 7=p·q·r·s 0=space`; khi đang gõ thì hiện
  chữ cái hiện tại kiểu `2 → b   letter 2/3`, tự reset sau 1200 ms. (Bố cục
  cũ đặt dòng nhắc phía trên phone book — sai so với ảnh tham chiếu.)
* **Thứ tự 7 nút toolbar** đúng với ảnh `8687567.PNG`:
  **khung ảnh** (`U+E8B7` ContactPicture, mở thư mục screenshot) · nạp ·
  ảnh · thư mục · ghi (hồng) · xoay · tách cửa sổ. Trước đây nút đầu lầm
  là ▶ Run; Run vẫn còn ở menu **Run → Run MREmu** và phím tắt **F6**, không
  nằm trên thanh công cụ của chrome.

> **VXPEmu vẫn chỉ là nguồn tham khảo giao diện.** VXPEngine không nhúng cũng
> không sửa `VXPEmu.exe`. Lõi chạy game thật vẫn là
> `D:/MRE/XimikBoda/MREmu-master/bin/Release/MREmu.exe`, và log của nó vẫn đổ về
> console VXPEngine.

## 1. Icon font `Segoe MDL2 Assets`

Font nằm sẵn tại `C:\Windows\Fonts\SegMDL2.ttf` trên Windows 10/11, nên không
cần đóng gói thêm tài nguyên. Module `app/widgets/emulator_panel.py` định nghĩa:

| Hằng số | Mã | Ý nghĩa |
| --- | --- | --- |
| `MDL2_RUN` | `U+E768` | ▶ chạy |
| `MDL2_IMPORT` | `U+E896` | ⬇ nạp `.vxp` |
| `MDL2_SCREENSHOT` | `U+E722` | camera |
| `MDL2_FOLDER` | `U+ED25` | mở thư mục build |
| `MDL2_RECORD` | `U+E714` | ● ghi (màu hồng `#FB7185`) |
| `MDL2_ROTATE` | `U+E72C` | ⟳ xoay |
| `MDL2_EXPAND` | `U+E740` | ⤢ tách ra cửa sổ riêng |
| `MDL2_STOP` | `U+E71A` | ■ dừng |
| `MDL2_ARROW_UP/DOWN/LEFT/RIGHT` | `U+E74A/E74B/E72B/E72A` | D-pad |
| `MDL2_DELETE` | `U+E74D` | ⌫ back (thùng rác) |
| `MDL2_ENTER` | `U+E751` | ↵ clear (return) |

Hàm `_mdl2_font(pixel_size)` trả về `QFont("Segoe MDL2 Assets")` để gán cho mọi
nút glyph. `_tool_button(glyph, tooltip, slot)` thay thế hàm cũ nhận tên icon
QtAwesome — toolbar giờ không còn phụ thuộc `qtAwesome`.

**Lưu ý kỹ thuật:** vì font MDL2 không có mặt chữ Latin, nút `OK` ở giữa D-pad
vẫn hiển thị bình thường nhờ cơ chế font merging của Qt. Nếu sau này thêm nút
glyph nào có lẫn chữ, cần tách riêng `QLabel` để tránh ô vuông rỗng.

## 2. Bàn phím 6×4 — toạ độ lấy từ `VirtualKeypadWidget.cpp`

```
cột:      0      1        2     │  3     4     5
hàng 0  [ 1 ][ 2 abc ][ 3 def ] │      [ ↑ ][ — ]
hàng 1  [ 4 ][ 5 jkl ][ 6 mno ] │ [ ← ][ OK ][ → ]
hàng 2  [ 7 ][ 8 tuv ][ 9 wxyz] │ [ ⌫ ][ ↓ ][ ↵ ]
hàng 3  [ * ][   0   ][   #   ] │      (trống)
```

Cụm điều hướng khai báo trong hằng số `_NAV_LAYOUT`, mỗi phần tử là
`(row, col, tên NAV_KEYS, kind, glyph)`. Tổng cộng **20 phím** = 12 phím số +
7 D-pad + 1 phím mềm (VXPEmu chỉ vẽ phím mềm trái).

Hai hàm phụ trung gian:

* `_nav_spec(name, glyph)` — trả bản sao `NAV_KEYS[name]` chỉ **đè `label`**,
  giữ nguyên `vk` / `char` / `object_name`. Nhờ vậy glyph đẹp hơn nhưng mã phím
  gửi xuống MREmu qua `PostMessage` **không hề đổi**.
* `_phone_label(spec)` — gộp `2 abc`; chỉ phím `2..9` có chữ T9, `1` và `0` để
  trần (VXPEmu cũng làm vậy, vì `1` là dấu câu và `0` là space).

Tooltip tiếng Việt (`_NAV_TOOLTIPS`) vẫn giữ để người dùng không phải đoán
glyph.

## 3. Dòng nhắc multi-tap động

Trước đây dòng nhắc là text tĩnh và nằm **dưới** màn hình. Theo VXPEmu nó nằm
**phía trên** khung phím, cao cố định 20 px, và thay đổi theo thao tác gõ:

| Trạng thái | Nội dung |
| --- | --- |
| Nghỉ | `Multi-tan: 2=a·b·c  3=d·e·f  7=p·q·r·s  0=space` |
| Đang gõ | `2 → b   letter 2/3` (số · chữ cái · vị trí trên chuỗi) |

* `_TAP_LETTERS` — bảng chữ T9 sao chép `VirtualKeypadWidget::lettersFor`
  (`1`→`.,?!1`, `2`→`abc`, …, `7`→`pqrs`, `0`→space).
* `_note_multi_tap(spec)` — mỗi lần bấm phím: cùng phím trong 1200 ms thì chạy
  tiếp chuỗi chữ (`2 → a → b → c` và quay vòng), khác phím thì bắt đầu ký tự mới.
* `_reset_tap()` — xoá trạng thái, hiện lại gợi ý tĩnh.
* `_TAP_RESET_MS = 1200` — thời gian chờ trước khi reset.
* `_update_tap_hint()` — render rich text; chữ cái hiện tại tô tím `#8B5CF6`,
  số đếm xám `#475569`.

Dòng nhắc viết entity `&rarr;` / `&nbsp;` dưới dạng ký tự thật (không phải
chuỗi escape) để Qt rich-text không phải đoán.

## 4. QSS

`app/resources/resources/dark_theme.qss` cập nhật phần `Emulator`:

* `QPushButton#EmulatorToolButton` — nền trong suốt, viền mảnh, cỡ 34×30 bám
  theo padding `6x10` + font 14 px của `TOOLBAR_STYLE` bên VXPEmu.
* `QPushButton#EmulatorRecordButton` — viền hồng `#FB7185` (VXPEmu dùng màu này
  cho nút ghi).
* `QPushButton#EmulatorStartButton` — xanh `#2d6cdf` cho nút chạy.
* `QFrame#EmulatorPhoneBook` — border `1px #263247`, radius `8px`, margin `12`
  (đúng thông số của VXPEmu).
* `QLabel#EmulatorMultiTanHint` — cao cố định 20 px, `#64748B`, 11 px.
* Xoá `EmulatorNavPad` / `EmulatorDigitPad` (không còn dùng).

## 5. Độ bền font icon (tránh tofu)

Cách tiếp cận glyph phụ thuộc vào việc máy có đăng ký font
`Segoe MDL2 Assets` hay không. Kiểm tra registry cho thấy font được khai báo tại
`HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts`
→ `Segoe MDL2 Assets (TrueType) = segmdl2.ttf`, nên Windows 10/11 bình thường
dùng được ngay. Nhưng nếu thiếu (ví dụ Windows 11 22H2+ đã chuyển sang
`Segoe Fluent Icons` với bảng mã khác), **mọi icon sẽ thành ô vuông rỗng**.

Vì vậy `resolve_icon_font()` dò theo chuỗi:

1. Family đã có trong `QFontDatabase` (`Segoe MDL2 Assets`, rồi `Holo MDL2
   Assets` — cùng bảng mã `U+E7xx`).
2. Nạp thẳng `%SystemRoot%\Fonts\segmdl2.ttf` bằng `addApplicationFont`.
3. Không được nữa thì trả `""` — khi đó `_tool_button()` và `_build_keypad()`
   tự đổi sang ký tự hình học phổ thông (`▶ ↓ ◉ ▤ ■ ↻ ↗`, `↑ ↓ ← → ⌫ ↵`) qua
   hai bản đồ `_TOOLBAR_FALLBACK_TEXT` / `_NAV_FALLBACK_TEXT`.

Kết quả được nhớ trong biến module `_icon_font_family` để không phải dò lại mỗi
lần tạo nút. **Việc đổi glyph không ảnh hưởng mã phím**: `_nav_spec()` chỉ đè
`label`, còn `vk` / `char` / `object_name` giữ nguyên, nên `PostMessage` xuống
MREmu vẫn đúng.

> Lưu ý khi kiểm thử: trong môi trường `QT_QPA_PLATFORM=offscreen` Qt báo
> **0 family** (không enumerate được system font). Đó là hiện tượng của môi
> trường headless, **không phải** máy thiếu font — đừng kết luận sai.

## 6. Kiểm thử

`smoke_mremu_hybrid.py` mở rộng từ **22 lên 56 kiểm tra**, chạy headless
(`QT_QPA_PLATFORM=offscreen`). Nhóm mới kiểm tra trực tiếp từng chi tiết của ảnh
tham chiếu:

* Thứ tự 7 nút toolbar khớp `MainWindow.cpp`, nút chạy dùng glyph `U+E768` và
  font `Segoe MDL2 Assets`.
* Đúng 20 phím: 12 số + 7 D-pad + 1 phím mềm.
* Toạ độ lưới: `(0,3)` trống, `↑` tại `(0,4)` là `NavUp`, phím mềm tại `(0,5)`
  là `SoftLeft`, hàng 1 `NavLeft/NavOk/NavRight`, hàng 2
  `KeyBack/NavDown/KeyClear`, hàng 3 trống.
* Glyph MDL2: `↑`=`U+E74A`, back=`U+E74D`, clear=`U+E751`, phím mềm = em dash.
* Không còn nhãn tiếng Việt dài (`Chức năng` / `Tuỳ chọn` / `Xoá`) trên phím.
* **Hồi quy hành vi:** `NavOk` vẫn giữ `VK_RETURN` (0x0D), `SoftLeft` vẫn giữ
  `VK_OEM_2` (0xBF), `KeyBack` vẫn `VK_ESCAPE` (0x1B), `KeyClear` vẫn
  `VK_BACK` (0x08) — chứng minh việc đè glyph không làm hỏng việc gửi phím.
* Dòng nhắc multi-tap: bấm 2 lần hiện `>b<` và `letter 2/3`; reset về text nghỉ.
* **Độ bền font icon:** mọi glyph toolbar và D-pad đều có bản đồ dự phòng; mô
  phỏng máy thiếu font (`resolve_icon_font → ""`) thì panel hiện ký tự hình học
  thay vì mã vùng `U+E000+`, và `NavOk` vẫn `VK_RETURN` / `KeyBack` vẫn
  `VK_ESCAPE`.

Kết quả: **56/56 pass**.

## Tệp liên quan

* Đổi: `app/widgets/emulator_panel.py`, `app/resources/resources/dark_theme.qss`,
  `app/documentation_content.py`, `docs/index.html`, `README.md`.
* Mới: `docs/changelog/CHANGELOG_v4.10.md`.
* Cập nhật: `smoke_mremu_hybrid.py`.
