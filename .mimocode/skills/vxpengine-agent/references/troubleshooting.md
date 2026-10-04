# Troubleshooting VXPEngine

Thứ tự xử lý: **đọc log → đối chiếu bảng → sửa nguyên nhân → verify lại**.
Không disable `verify_core`, không xóa App ID, không “fix” bằng cách ghi đè `src/`.

---

## 0. Thu thập bằng chứng (luôn làm trước)

```powershell
# Crash / exception của frozen GUI
Get-Content "$env:LOCALAPPDATA\VXPEngine\logs\native_crash.log" -Tail 80

# Process đang treo
Get-Process VXPEngine, VXPEmu -ErrorAction SilentlyContinue

# Bản cài
Get-Item "C:\Program Files\VXPEngine\VXPEngine.exe" | Select-Object Length, LastWriteTime

# Sự kiện Application (crash 1000)
Get-WinEvent -FilterHashtable @{LogName='Application'; Id=1000} -MaxEvents 20 |
  Where-Object Message -match 'VXPEngine|PySide|Qt6'
```

Trong IDE: **Ctrl+J** mở Bottom Panel (Console / Problems / Output).
Dialog **Build/Run thất bại** / **Lỗi khi chạy tác vụ** (nếu app đã có fix UI).

---

## 1. Run/Build “không thấy gì”

### Nguyên nhân đã gặp (2026-09)

1. **Frozen build thiếu `verify_core`**  
   Traceback trong `native_crash.log`:

   ```text
   File "vxp_runner.py", line ..., in _core_defines
   ModuleNotFoundError: No module named 'verify_core'
   ```

   - GUI `console=False` → exception chỉ vào excepthook/log.
   - Console IDE mặc định ẩn → người dùng không thấy gì.

2. **Exception trong slot Qt** không hiện dialog (bản cũ).

### Sửa

| Việc | Where |
|------|--------|
| Bundle module | `packaging/windows/VXPEngine.spec` → `hiddenimports=[..., "verify_core"]`, `pathex` gồm `tools/` |
| Hiện lỗi UI | `app/vxp_runner.py` → `last_error` + `_fail_early`; `app/main.py` → `_build_target` catch + `NoticeDialog` |
| Rebuild release | `packaging\windows\build_release.ps1` |
| Cài lại | MSI elevated: `msiexec /i "...msi" /qn` **as Administrator** |

Verify sau fix:

```powershell
# verify_core phải có trong exe/PYZ
& ".\.venv\Scripts\pyi-archive_viewer.exe" -l "C:\Program Files\VXPEngine\VXPEngine.exe" | Select-String verify_core
```

---

## 2. Lỗi core / chữ ký

### `Thieu core coremre: chay qua VXPEngine hoac truyen -DCOREMRE_PACKAGE_DIR=...`

- Build chạy CMake **không** qua `VxpRunner`, hoặc `_core_defines()` trả `[]`
  sai (package dir không thấy).
- Sửa: build từ IDE / `VxpRunner`; kiểm tra `packaging/coremre/` tồn tại.

### `Chữ ký KHÔNG hợp lệ` / `Tệp bị sửa đổi`

- `verify_core.verify()` fail → build **phải** dừng (bảo mật).
- Sửa: khôi phục gói core từ nguồn sạch; **không** comment verify.
- Log IDE: dòng `[Core] ...`.

### `ModuleNotFoundError: verify_core` (source mode)

- `tools/` không trên `sys.path` hoặc file thiếu.
- `_core_defines` chỉ insert path nếu `tools.is_dir()`; frozen dùng hiddenimport.

---

## 3. Toolchain / CMake

| Thông điệp | Nguyên nhân | Sửa |
|------------|-------------|-----|
| `'C:/Program' is not recognized` | **MinGW Makefiles** + path có khoảng trắng (`Program Files`, `VXP Projects`) | Dùng generator **Ninja** (runner mặc định từ bản fix); xóa `build-arm/` cache cũ |
| `ld.exe: unrecognized option '--major-image-version'` | Cache cũ `CMAKE_SYSTEM_NAME=Windows` (toolchain Generic không áp) | Xóa `build-arm/`; configure lại với `-DCMAKE_TOOLCHAIN_FILE=...` |
| `You have changed variables that require your cache to be deleted` | Đổi compiler/toolchain giữa chừng | Xóa `build-arm/` rồi build lại |
| `Không tìm thấy lệnh: cmake` / `arm-none-eabi-gcc` | Sai `sdk_layout` / PATH | `run_windows.bat check`; env `VXPE_W64DEVKIT`, `VXPE_ARM_TOOLCHAIN` |
| `Thieu VXPEngine SDK tools` | `-DVXPE_SDK_TOOLS` trống | Dùng VxpRunner hoặc truyền `engine/coremre/tools` |
| Cache CMake thuộc project khác | Di chuyển folder | Runner tự `_reset_foreign_cmake_cache` + `_cmake_generator_mismatch` |
| Link `_close is not implemented` (newlib warning) | Bình thường trên MRE | Không phải lỗi build fail |

`app/sdk_layout.py` thứ tự tìm:

1. `engine/coremre/sdk/...` (cài MSI / repo)
2. env override
3. fallback `D:/MRE/...`, `C:/msys64/mingw64`

---

## 4. MSI / cài đặt

| Mã | Ý nghĩa | Sửa |
|----|---------|-----|
| 0 | Thành công | — |
| 1603 | Fatal | Xem log ` /l*v ` |
| 1730 | *You must be an Administrator to remove this application* | Cài elevated (per-machine Program Files); `/qn` tắt UAC → phải chạy msiexec as admin |
| ICE61 warning (LGHT1076) | Same-version upgrade | Cảnh báo; `AllowSameVersionUpgrades=yes` đã có |

Log mẫu:

```powershell
msiexec /i "D:\MRE\VXPEngine\dist-installer\VXPEngine-2.0.0-x64.msi" /l*v "$env:TEMP\vxpe.msi.log"
Select-String "$env:TEMP\vxpe.msi.log" -Pattern 'Return value 3|Error 1730|being used'
```

App đang mở → đóng `VXPEngine.exe` trước khi cài lại.

---

## 5. Qt / frozen GUI

| Triệu chứng | Sửa |
|-------------|-----|
| `DLL load failed ... procedure not found` | MSVC runtime mismatch — `build_release.ps1` copy từ PySide6 |
| WinError 127 `ucnv_open` | ICU của bên thứ 3 — xóa `icu*.dll`; hook nạp `System32\icuuc.dll` |
| Crash `Qt6Gui`/`Qt6Core` | Xem WER 1000; thử `QT_OPENGL=software` (đã set trong `configure_crash_diagnostics`) |
| PATH bị VXPEmu Qt 6.7 làm hỏng IDE Qt 6.11 | `qt_runtime_hook.py` pin DLL; probe trong `verify_release.py` |

---

## 6. Viewport / design ≠ run

- Chỉ 240×320 / 320×240. Nếu `.dtfe` viewport lệch → Camera2D và VXPEmu lệch.
- Design mode không vẽ: kiểm tra `VXP_DESIGN_ACTIVE_COUNT` trong `scene_bindings.h`
  (regenerate từ scene, **không** sửa tay lâu dài).
- Sprite không hiện: ảnh phải trong `assets/`, export `.raw` vào `resources/gen/`.

---

## 7. Template sync ghi đè code

- File **user** phải policy `seed` trong `template_blank/template.manifest.json`.
- File **engine** là `managed` — chỉ update khi hash local == hash base.
- Nếu code bị overwrite: policy sai → sửa manifest, bump `version`, thêm harness
  `reports/harness_project_layout_v2.py`.

---

---

## 9. Checklist trước khi nói “đã sửa”

```text
[ ] Đã đọc native_crash.log / console / dialog thật
[ ] Nguyên nhân gốc đã chỉ ra (file:line hoặc missing module)
[ ] py_compile / harness phù hợp đã chạy
[ ] Nếu đụng build/SDK: có ARM .vxp artifact thật
[ ] Nếu đụng frozen: verify_core (và import động khác) có trong archive
[ ] Không có secret trong output/log/project
[ ] Báo cáo: symptom → cause → fix → test → residual risk
```

## 10. Harness nhanh liên quan lỗi

```powershell
.\.venv\Scripts\python.exe -m py_compile app\vxp_runner.py app\main.py app\project_store.py
.\.venv\Scripts\python.exe reports\harness_project_layout_v2.py
.\.venv\Scripts\python.exe reports\harness_design_pipeline.py
.\.venv\Scripts\python.exe reports\harness_demo_build.py
run_windows.bat check
```
