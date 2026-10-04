# Tạo game / app VXPEngine mới

Mục tiêu: có project build được ARM `.vxp` và chạy VXPEmu trong vài phút,
không mất App ID, không copy sai template.

## Quyết định bắt buộc

| Câu hỏi | Lựa chọn hợp lệ |
|----------|------------------|
| Hướng màn | **240×320 portrait** hoặc **320×240 landscape** — không có lựa chọn khác |
| Template | `blank` (khuyến nghị) hoặc template có sẵn trong `PROJECT_TEMPLATES` |
| App name | ASCII, dùng cho `<app_name>.vxp` |
| Developer | mặc định `VXPstore` — đổi chỉ khi người dùng yêu cầu |

## Cách 1 — IDE (khuyến nghị)

1. Mở VXPEngine (`run_windows.bat` hoặc `C:\Program Files\VXPEngine\VXPEngine.exe`).
2. Home → **Tạo dự án VXP mới**.
3. Chọn **240×320 — Dọc** hoặc **320×240 — Ngang**.
4. Nhập tên project / App name → **Tạo và mở 2D Engine**.

IDE sẽ:

- cấp `app_id` riêng (`generate_app_id`)
- seed từ `template_blank/` theo `template.manifest.json`
- patch `CMakeLists.txt` (`APP_NAME`, `APPID`, …)
- ghi `project.vxp.json` + `assets/scenes/*.dtfe` + `src/main.c`
- purge mọi artifact signing khỏi project

## Cách 2 — Gọi `ProjectStore` (agent / script)

```python
from pathlib import Path
from project_store import ProjectStore

store = ProjectStore()  # cùng store với IDE đang dùng
p = store.create_project(
    name="ArrowDemo",
    base_directory=str(Path.home() / "VXPProjects"),
    app_name="arrowdemo",
    developer="VXPstore",
    template_key="blank",
    viewport_width=240,   # sẽ bị ép về 240×320 hoặc 320×240
    viewport_height=320,
)
print(p.path, p.app_id, p.viewport_width, p.viewport_height)
```

**Không** `robocopy template_blank` rồi sửa tay — sẽ thiếu App ID/patch/manifest state.

## Cách 3 — Mở project có sẵn

```python
store.register_existing(r"D:\path\to\existing")
```

- Có `project.vxp.json` → giữ App ID/metadata, migrate core nếu cần.
- Chỉ có `src/main.c` hoặc `CMakeLists.txt` → coi là legacy, cấp App ID mới nếu thiếu.

## Sau khi tạo — checklist 5 phút

```text
[ ] project.vxp.json có app_id ≠ "0" (máy retail yêu cầu id khác 0)
[ ] screen.width/height đúng cặp QVGA
[ ] CMakeLists.txt có set(APPID "...") và include(.vxpe/cmake/...)
[ ] .vxpe/template-state.json tồn tại
[ ] Không có *.pem / signing/ trong project
[ ] scripts\build_arm.bat chạy được
[ ] scripts\run_vxpemu.bat mở VXPEmu
```

## Viết game logic

### Design mode (khuyên dùng khi đã vẽ scene)

`src/main.c` đã có nhánh `VXP_DESIGN_ACTIVE_HAS_DESIGN`:

- IDE export sprite `.raw` → `resources/gen/`
- `scene_bindings.h` sinh macro vị trí/kích thước
- Build vẽ đúng Camera2D = giả lập

Chỉ cần thêm input, timer, scoring ở ngoài vòng design draw.

### Code mode (scene trống)

Khi `VXP_DESIGN_ACTIVE_COUNT == 0`, dùng code mặc định trong template
(backdrop + frame) làm điểm bắt đầu, rồi viết:

```c
#include "vmsys.h"
#include "vmtimer.h"
#include "vmgraph.h"

/* timer ~50ms như engine MRE — xem docs/ARCHITECTURE.md */
static void tick(VMINT tid) {
    /* update + draw vào layer_fb */
}
```

Tham chiếu:

- `template_blank/src/main.c` — pattern đầy đủ
- `examples/MedievalArcheryDemo`, `PocketToolkitDemo`, `IsometricOutpostDemo`
- `docs/ARCHITECTURE.md` — Engine/Scene/Renderer/Input
- `docs/guides/DTFE_FORMAT.md` — scene, screens, animation

## Thêm asset

1. Đặt ảnh/audio vào `assets/` (sprites, audio, maps, fonts, imported).
2. Kéo vào Camera2D **hoặc** dùng Editor Assets → Áp dụng & lưu.
3. Ảnh ngoài project: copy vào `assets/imported/` (tránh path tuyệt đối).
4. Build lại để pack resource (`.raw` / `.res` / `.vxp`).

## Build & Run

```bat
cd /d <project>
scripts\build_arm.bat
scripts\run_vxpemu.bat
```

Hoặc IDE toolbar: **Build · ARM** → **Run**.

Output: `build-arm/main/<app_name>.vxp`.

## Ký bản retail

Chỉ qua IDE **Build ARM Signed** (hoặc pipeline `VxpRunner`):

- inject `-DCOREMRE_PACKAGE_DIR` (gói core đã verify)
- inject App ID / cert path từ `signing/apps/`
- `vxp_signer.py` ký + self-verify

Không tạo cert mới mỗi build. Không copy `private.pem` vào project.

## Lỗi thường gặp khi tạo mới

| Triệu chứng | Sửa |
|-------------|-----|
| `Thư mục ... đã tồn tại` | Chọn tên/thư mục khác hoặc xóa folder rỗng |
| `Thiếu thư mục template_blank/` | Chạy từ engine root có đủ source; cài MSI đầy đủ |
| Viewport bị đổi khi reopen | Descriptor đã bị sửa tay — khôi phục cặp QVGA |
| Build thiếu coremre | Dùng IDE/VxpRunner để truyền `COREMRE_PACKAGE_DIR` |
| Run không thấy gì | Xem `troubleshooting.md` — crash log + dialog |

Chi tiết lỗi: `references/troubleshooting.md`.
