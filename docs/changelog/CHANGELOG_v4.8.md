# VXPEngine v4.8 — Menu Settings, tự động cài môi trường và tự làm mới Assets

Bản này giải quyết bốn việc: gom các cài đặt vào một menu **Settings** ở topbar,
biến nút "Kiểm tra cập nhật" thành một quy trình **kiểm tra + tự cài nốt thư viện/SDK
còn thiếu bằng shell**, thêm **hộp thoại thiết lập lần đầu** tự chạy ngay sau khi cài
VXPEngine, và làm cho cây **Assets tự nhận tài nguyên thêm ngoài IDE**.

## 1. Menu Settings (mới)

Thanh menu hiện có: `File · Edit · View · Project · Scene · Run · Tools · Settings · Help`.

| Mục trong Settings | Phím tắt | Chức năng |
| --- | --- | --- |
| Kiểm tra cập nhật… | — | Dò bản phát hành mới, **sau đó** tự chạy bước cập nhật môi trường |
| Cập nhật môi trường / thư viện… | — | Quét thành phần còn thiếu và chạy trình cài bằng shell |
| Đường dẫn VXPEmu… | — | Chọn `VXPEmu.exe`, lưu vào QSettings |
| Làm mới tài nguyên Assets | `F5` | Quét lại `assets/` ngay lập tức |
| Chạy lại thiết lập lần đầu… | — | Mở lại hộp thoại thiết lập (dùng khi đổi máy/bổ sung SDK) |

**"Kiểm tra cập nhật…" đã rời khỏi menu Help.** Menu Help giờ chỉ còn *Tài liệu* (F1) và
*Giới thiệu*.

### Thứ tự chạy khi bấm "Kiểm tra cập nhật…"

```
Kiểm tra bản phát hành  ─┬─ có bản mới  → toast + mở link
                         ├─ đã mới nhất → toast
                         └─ lỗi mạng    → ghi console (im lặng nếu tự động)
                                  │
                                  ▼  (luôn chạy, bất kể kết quả trên)
                         Quét môi trường → thiếu gì?
                                  │
                                  ▼
                         Xác nhận → chạy trình cài bằng shell
```

Cờ `_environment_setup_after_update` đảm bảo bước môi trường **không bị nuốt** khi
máy mất mạng — kiểm tra cập nhật thất bại vẫn dẫn tới cài thư viện.

## 2. Tự động chạy shell cài thư viện / SDK còn thiếu (mới)

Module mới `app/environment_setup.py` mô tả 9 thành phần môi trường bằng một
`Requirement` gồm `detect()` (đã có chưa) và `command()` (lệnh shell để cài).

| Key | Thành phần | Cách cài |
| --- | --- | --- |
| `cmake` | CMake | `winget install -e --id Kitware.CMake` |
| `vs2022` | Visual Studio 2022 BuildTools | `winget … --id Microsoft.VisualStudio.2022.BuildTools --override "--wait --quiet --add Microsoft.VisualStudio.Workload.VCTools --includeRecommended"` |
| `bash` | Git for Windows | `winget … --id Git.Git` |
| `arm_gcc` | arm-none-eabi-gcc | `C:/msys64/usr/bin/bash -lc "pacman -S --noconfirm --needed mingw-w64-x86_64-arm-none-eabi-toolchain"`, thiếu MSYS2 thì dùng `winget` |
| `python_deps` | PySide6, QtAwesome… | `python -m pip install -r requirements.txt` |
| `mre_sdk` | MRE SDK | thủ công |
| `vxpemu` | VXPEmu | thủ công |

**Vì sao cần `winget_path()` riêng:** `winget.exe` là App Execution Alias nằm trong
`%LOCALAPPDATA%\Microsoft\WindowsApps\winget.exe`. Thư mục này thường **không có trong
PATH của tiến trình con** do IDE sinh ra, nên `shutil.which("winget")` trả về `None`
và mọi lệnh cài sẽ âm thầm biến mất. Hàm này dò thêm vị trí chuẩn.

`EnvironmentInstaller` chạy các lệnh **nối tiếp** qua `QProcess`, gộp stdout/stderr và
phát log từng dòng ra console lẫn hộp thoại. Nút Stop của IDE cũng dừng được trình cài.

Thành phần không có trình cài tự động sẽ bị bỏ qua kèm gợi ý thủ công, thay vì làm
cả đợt cài thất bại.

## 3. Hộp thoại thiết lập lần đầu (mới)

`app/widgets/first_run_dialog.py` — hiện **tự động ~0.8 giây sau khi IDE mở**, nhưng
chỉ khi `QSettings` chưa ghi nhận hoàn tất:

* `is_first_run(version)` → `True` khi chưa từng thiết lập, **hoặc** khi phiên bản
  VXPEngine đổi (bản mới có thể cần công cụ mới).
* `mark_setup_done(version)` ghi `setup/firstRunCompleted` + `setup/firstRunVersion`.
* `reset_setup_flag()` để chạy lại từ đầu.

Hộp thoại tự quét ngay khi hiện, dựng một dòng cho mỗi thành phần với ba trạng thái:
**Đã có** · **Có thể cài tự động** (tick sẵn) · **Cần làm thủ công** (kèm gợi ý).
Nút *Tự động cài đặt* chỉ bật khi có mục được chọn; nhật ký chảy ra theo thời gian thực.

Nút X cũng gọi `request_close()` để đánh dấu hoàn tất — nếu không, hộp thoại sẽ hiện
lại mỗi lần mở IDE.

Mọi lỗi trong bước này đều bị nuốt và ghi console (`[Setup] Không thể chạy thiết lập
lần đầu: …`) — **thiết lập không bao giờ được chặn việc mở IDE**.

Menu Settings → *Chạy lại thiết lập lần đầu…* mở lại hộp thoại này bất cứ lúc nào.

## 4. Tự làm mới thư mục Assets (mới)

Thêm tệp vào `assets/` bằng Explorer, git hoặc trình biên dịch ảnh thì trước đây cây
Assets đứng im cho tới khi mở lại project. Giờ:

* `QFileSystemWatcher` theo dõi **đệ quy** `assets/` (và `maps/`, `resources/`, `src/`
  nếu có), tối đa 200 thư mục, sâu 6 cấp.
* Thay đổi được **debounce 500 ms** (`WATCH_DEBOUNCE_MS`) để một đợt copy nhiều tệp
  chỉ gây đúng một lần làm mới.
* Sau mỗi lần làm mới, thư mục mới xuất hiện được đăng ký theo dõi lại.
* `AssetsPanel.set_auto_refresh(bool)` bật/tắt; `refresh_now()` làm mới ngay (bỏ qua
  debounce) cho action thủ công.
* `F5` / Settings → *Làm mới tài nguyên Assets* gọi `_sync_project_assets()`, làm mới
  cả cây Assets lẫn bảng tileset.

## Tệp liên quan

- Mới: `app/environment_setup.py`, `app/widgets/first_run_dialog.py`
- Đổi: `app/main.py` (menu Settings, `_check_updates_and_environment`,
  `_update_environment`, `_refresh_project_assets`, `_run_first_run_setup`,
  `_maybe_run_first_run_setup`),
  `app/widgets/asset_manager.py` (watcher + debounce),
  `app/vxp_runner.py` (`install_environment` từ stub thành thật),
  `app/resources/resources/dark_theme.qss` (style hộp thoại thiết lập),
  `app/documentation_content.py`, `docs/index.html`, `README.md`

## Kiểm thử

115 kiểm tra (95 đơn vị + 20 end-to-end) chạy offscreen, tất cả đạt: cấu trúc menu
Settings và việc "Kiểm tra cập nhật…" đã rời khỏi Help, chuỗi
cập nhật → môi trường (kể cả khi lỗi mạng), `detect_missing` / `installable` /
`winget_path`, vòng đời `is_first_run` / `mark_setup_done`, dựng `FirstRunDialog`,
và việc cây Assets tự nhận tệp thêm ngoài IDE sau debounce.
