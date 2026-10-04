# VXPEngine v4.9 — Kiến trúc giả lập lai: chrome VXPEmu + lõi MREmu

Phase 5 đổi mới hoàn toàn cách chạy giả lập trong VXPEngine: thay vì nhúng
`VXPEmu.exe` (gặp khó khăn vì VXPEmu là ứng dụng Qt/C++ độc lập, không có cơ
chế IPC), IDE giờ đây:

* **Dựng lại toàn bộ chrome** (frame thiết bị, màn hình 240×320, bàn phím
  MRE, dòng nhắc multi-tan) bằng **Python + QSS**, bám sát giao diện của
  `VXPEmu` (xem ảnh tham chiếu). Không chỉnh sửa `VXPEmu.exe` ở
  `D:/MRE/VXPEmu` — mọi thứ đồng bộ với dark theme của IDE.
* **Chạy lõi thật** là `MREmu.exe` từ
  `D:/MRE/XimikBoda/MREmu-master`. Đây là MREmu thật (SFML + ImGui +
  Unicorn); VXPEngine khởi chạy nó như tiến trình con, tìm HWND của cửa sổ
  1100×720 rồi `SetParent` vào host 240×320 bên trong panel. MREmu HWND
  được `SetWindowPos` với tọa độ âm (−650, −20) để vùng game canvas lọt
  đúng vào host; các panel debug bên trái/phải của MREmu tự bị clip ra ngoài.
* **Log** từ MREmu (spdlog ra stdout) được merge channel trong `QProcess`
  rồi emit từng dòng qua tín hiệu `message`; `MainWindow` nối thẳng vào
  console VXPEngine. Không còn cửa sổ log riêng.
* **Phím** ảo (đã có từ trước) giờ `PostMessage` mã Win32 VK tới HWND của
  MREmu, mapping y hệt SFML KeyboardControl của MREmu.

## Thay đổi kỹ thuật

### `app/widgets/emulator_panel.py`

* Viết lại hoàn toàn: trước đây nhúng `VXPEmu.exe`, giờ dựng chrome theo
  VXPEmu và nhúng `MREmu.exe`.
* Thêm hằng số: `MREMU_GAME_OFFSET_X = 650`, `MREMU_GAME_OFFSET_Y = 20`,
  `MREMU_GAME_W = 240`, `MREMU_GAME_H = 320`, `MREMU_WIN_W = 1100`,
  `MREMU_WIN_H = 720` — bám sát `MREmu.cpp:167` (kích thước cửa sổ) và
  `MREmu.cpp:235` (vị trí game canvas).
* Host nhúng (`_EmbedHost`) cố định 240×320, native window với
  `WA_NativeWindow`. MREmu HWND reparent vào host, `SetWindowPos` với
  offset âm để cắt đúng vùng game.
* Toolbar 7 nút icon-only kiểu VXPEmu: viền đỏ (ghi/dừng), nạp, chụp ảnh,
  mở thư mục, điện thoại đỏ (chạy), khởi động lại, tách cửa sổ.
* Bàn phím đổi sang bố cục 6 cột × 4 hàng y hệt VXPEmu phone-book: 3 cột
  số (`1..9, *, 0, #`) + 3 cột nav (`↑ ─`, `← OK →`, `⌫ ↓ ↵`).
* Thêm `screenshot()` (chụp vùng host thành PNG cạnh artifact) và
  `_open_output_folder()` (mở `build-win32/main/Release` trong Explorer).
* Multi-tan hint dùng rich text y hệt VXPEmu:
  `Multi-tan: 2=a·b·c 3=d·e·f 7=p·q·r·s 0=space`.
* `start()` gọi `MREmu.exe <vxp> -l` (MREmu không có cờ `--autostart`; `-l`
  là `--path_is_local`); cwd đặt về thư mục chứa exe vì MREmu cần
  `libcharset.dll`, `libiconv.dll`, `openal32.dll` cạnh bên.
* `set_emulator_path()` lưu vào `QSettings["emulator/mremuPath"]`;
  mặc định dò `D:/MRE/XimikBoda/MREmu-master/bin/Release/MREmu.exe` rồi
  `.../bin/Debug/MREmu.exe`.
* `refresh_path_label()` (công khai) cập nhật nhãn đường dẫn sau khi đổi
  MREmu.exe qua Settings.

### `app/vxp_runner.py`

* Module docstring viết lại cho kiến trúc hybrid.
* Thêm `MREMU_EXE = D:/MRE/XimikBoda/MREmu-master/bin/Release/MREmu.exe`.
* Thêm `run_mremu(project_path)`: build `.vc.vxp` (CMake + target
  `main_vxp`) rồi đặt `_post_action = "mremu"`; pipeline hiện tại chỉ có
  2 bước (configure + build) — bước thứ ba "chạy MREmu" do
  `EmulatorPanel.start()` xử lý.
* Thêm `last_post_action` (read-only) — lưu lại `_post_action` trước khi
  xóa, để `MainWindow._on_runner_finished` biết cần nạp artifact vào
  MREmu (cờ `_pending_emulator_load` vẫn dùng song song cho menu/toolbar).
* `build_win32` đổi nhãn: "Build Win32 (.vc.vxp cho MREmu)".

### `app/main.py`

* `BUILD_TARGETS`: thay `"Run VXPEmu"` bằng `"Run MREmu"`, thay
  `"Build Win32 (VXPEmu)"` bằng `"Build Win32 (.vc.vxp cho MREmu)"`.
* Menu Run: "Run MREmu" (F6) thay cho "Run VXPEmu"; nhãn "Build Win32
  (.vc.vxp cho MREmu)".
* Menu Settings: "Đường dẫn MREmu…" thay cho "Đường dẫn VXPEmu…", gọi
  `_configure_mremu_path()` (đổi tên từ `_configure_vxpemu_path()`).
* Toolbar Run button tooltip: "Lưu mã, build .vc.vxp và nạp vào giả lập
  MREmu (F6)"; Check button: "Kiểm tra CMake, Visual Studio, bash,
  arm-none-eabi-gcc và MREmu".
* `_build_target("run_mremu")` set `_pending_emulator_load = True` rồi
  gọi `self.runner.run_mremu(path)`.
* `_on_runner_finished()` consume `self.runner.last_post_action == "mremu"`
  để dẫn tới `_load_artifact_into_emulator()`.
* Đóng MREmu khi đổi project / tắt IDE (trước đây comment nói "đóng
  VXPEmu"; giờ sửa thành MREmu).
* Tab trung tâm: tiêu đề "MREmu" (trước: "VXPEmu").

### `app/native_window.py`

* Module docstring đổi từ "Win32 helpers cho VXPEmu" sang "Win32 helpers
  cho MREmu". Bố cục cũ vẫn dùng được vì MREmu cũng là cửa sổ native SFML
  với HWND riêng.

### `app/environment_setup.py`

* Thêm `mremu` requirement: phát hiện
  `D:/MRE/XimikBoda/MREmu-master/bin/Release/MREmu.exe` (hoặc Debug).
  Optional, gợi ý build MREmu-master.
* `vxpemu` requirement đổi mô tả thành "VXPEmu (tham khảo giao diện)" —
  không còn bắt buộc để chạy giả lập.

### `app/resources/resources/dark_theme.qss`

* Viết lại toàn bộ block Emulator: 7 nút toolbar vuông icon-only
  (34×30), nút "Ghi" viền đỏ trong suốt, nút "Chạy" nền xanh dương đậm,
  màn hình host có viền 2px bo góc, multi-tan hint màu cyan (#5BD1D7) y
  hệt VXPEmu.
* Bỏ block `EmulatorNavPad` / `EmulatorDigitPad` (keypad giờ dùng một
  `QFrame#EmulatorPhoneBook` duy nhất chứa cả số và nav trong grid 6×4).
* Thêm `QLabel#EmulatorMultiTanHint`, `QWidget#EmulatorRecordButton`,
  `QWidget#EmulatorStartButton`.

## Kiểm thử

* `smoke_mremu_hybrid.py` (mới, 22 kiểm tra):
  * `VXPRunner.run_mremu` set `_post_action = "mremu"`, build 2 bước trả
    về thành công, `last_post_action` được giữ lại sau khi pipeline kết
    thúc.
  * `EmulatorPanel` có đủ 7 nút toolbar VXPEmu (record/load/screenshot/
    folder/start/restart/detach) với objectName đúng, multi-tan hint
    đúng rich text, phone-book 6×4 với đúng 20 phím (12 số + 8 nav/soft).
  * `panel.start(<vxp>)` gọi `QProcess.start` với `program = MREmu.exe`,
    `arguments = [vxp, "-l"]`, `cwd = thư mục chứa MREmu.exe`.
  * `MainWindow` mở project mới: tab trung tâm "MREmu" (không còn
    "VXPEmu"), `BUILD_TARGETS` có "Run MREmu", menu Settings có "Đường
    dẫn MREmu…" (không còn "VXPEmu"), action "Run MREmu" có shortcut F6.
  * `_on_runner_finished(exit_code=0, success=True)` với
    `last_post_action="mremu"` dẫn tới `_load_artifact_into_emulator`.
* 38 kiểm tra cũ (`_tmp_boot_mremu.py` ban đầu, sau đó sáp nhập vào
  `smoke_mremu_hybrid.py`): menu/menu-bar layout, toolbar tooltip, v.v.
* Tổng cộng: **60/60** kiểm tra thuộc Phase 5 pass headless.

## Tệp liên quan

* Đổi: `app/main.py`, `app/vxp_runner.py`, `app/widgets/emulator_panel.py`,
  `app/native_window.py`, `app/environment_setup.py`,
  `app/resources/resources/dark_theme.qss`, `app/documentation_content.py`,
  `docs/index.html`, `README.md`.
* Mới: `smoke_mremu_hybrid.py`.
