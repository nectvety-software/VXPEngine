# VXPEngine v4.7 — Gộp core thành `coremre` + tích hợp VXPEmu

## 1. Gộp hai core thành một: `coremre`

Trước đây repo mang hai thư mục core là **bản sao của nhau** (`engine/vxpstore` và
`engine/corevxp`, 208 tệp trùng nội dung, chỉ khác tên target trong `CMakeLists.txt`).
Chúng đã được gộp thành một thư mục duy nhất:

| Vị trí | Trước | Sau |
| --- | --- | --- |
| Bản tham chiếu của IDE | `engine/vxpstore`, `engine/corevxp` | `engine/coremre` |
| Bản mang vào project | `template/engine/vxpstore`, `template/engine/corevxp` | `template/engine/coremre` |
| Template trống | `template_blank/engine/vxpstore`, `template_blank/engine/corevxp` | `template_blank/engine/coremre` |
| Target CMake | `add_library(vxpstore INTERFACE)` | `add_library(coremre INTERFACE)` |

`coremre` vẫn là INTERFACE library (header + src), yêu cầu C++17, dùng chung cho
MRE VXP lẫn Arduino.

**Lưu ý:** tên nhà phát triển mặc định vẫn là `VXPstore` và owner GitHub vẫn là
`vxpstore` — hai cái đó **không** đổi theo core.

## 2. Di trú project cũ (mới)

Project tạo ra trước khi gộp core vẫn trỏ `add_subdirectory(engine/vxpstore)` và sẽ
hỏng ngay khi configure CMake, vì `template/` không còn bản sao nào để bù vào.

Module mới `app/core_migration.py` chạy tự động khi mở project (và khi đăng ký project
có sẵn), thực hiện:

1. Đổi tên `engine/<core cũ>` → `engine/coremre`.
2. Quét và cập nhật mọi tham chiếu trong `CMakeLists.txt`, `main/CMakeLists.txt`,
   scripts (`.sh`, `.bat`), `src/`, `docs/`… từ `vxpstore`/`corevxp` sang `coremre`.
3. In thông báo `[Core] …` ra console của IDE.

**Nguyên tắc an toàn — không bao giờ xóa dữ liệu:**

| Tình trạng project | Hành động |
| --- | --- |
| Chỉ có một core cũ | Đổi tên thành `coremre`, cập nhật tham chiếu |
| Có cả hai core, **giống nhau** | Lấy `vxpstore` làm `coremre`; giữ lại `corevxp` và nhắc xóa thủ công |
| Có cả hai core, **khác nhau** | Không tự gộp — cảnh báo và yêu cầu chọn tay |
| Đã có `coremre`, còn core cũ sót lại | Không đổi gì; chỉ nhắc có thể xóa thủ công |
| Đã đúng layout | Không làm gì (chỉ tốn vài lệnh `stat`) |

So sánh "giống nhau" bỏ qua `CMakeLists.txt`, vì hai core cũ khác biệt duy nhất ở tên
target bên trong tệp đó — khác biệt do tên thư mục sinh ra, không phải nội dung core.

Chữ ký nhà phát triển (`DEVELOPER_NAME "VXPstore"`, viết hoa chữ V) và App ID trong
`project.vxp.json` **không** bị đụng tới.

## 3. Giả lập: bỏ frame MREmu, nhúng VXPEmu

- Không còn dùng frame giả lập của MREmu.
- Tích hợp `D:\MRE\VXPEmu` bằng cách **nhúng cửa sổ native** (không sửa mã C++ của
  VXPEmu): IDE khởi chạy `VXPEmu.exe` như tiến trình con, lấy HWND, tước viền cửa sổ
  rồi đưa vào một `QWidget` bằng `QWindow.fromWinId`.
- Toàn bộ chrome xung quanh (thanh công cụ, màn hình 240x320, bàn phím MRE ảo, thanh
  trạng thái) viết bằng **Python + QSS**, đồng bộ dark theme của IDE.

## Tệp liên quan

- Mới: `app/core_migration.py`
- Đổi: `app/project_store.py` (thêm `ProjectStore.migrate_core`), `app/main.py`
  (thông báo `[Core]` khi mở project), `engine/coremre/CMakeLists.txt`,
  `template/CMakeLists.txt`, `template/main/CMakeLists.txt`, `README.md`,
  `docs/VXPEngine_Manual.md`, `docs/index.html`, `app/documentation_content.py`
