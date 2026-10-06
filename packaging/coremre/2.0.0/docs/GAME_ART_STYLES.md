# Game art styles cho VXPEngine

Các preset lấy cảm hứng từ các nhóm hình ảnh đã xem trong DLanatils:
Fourleaf Fields (farm), MagnaDev (fantasy), Absym (combat neon),
Kidbash/Celeste prototype (platformer), Pastry Pile Up (màu mềm).
Đây là công cụ chuyển bảng màu cho asset có sẵn; bố cục, sprite,
animation và chi tiết hình vẽ vẫn cần được tạo riêng.

## Asset Editor

Trong **PHONG CÁCH 2D**, chọn `Game · Cozy Farm`, `Dark Fantasy`,
`Neon Action`, `Pastel Platformer` hoặc `Retro Handheld`, rồi bấm
**Áp dụng phong cách**. Bốn preset đầu dùng 16 màu, handheld dùng 4 màu.
Kích thước và alpha được giữ nguyên; thao tác dùng Undo hiện có.
Chọn **Áp dụng & lưu** để lưu asset và dùng trong Camera2D.
Nên xử lý sprite/tileset theo cùng một palette trước khi dựng scene.

## Chỉnh màu RGB565 trong game

`graphics/VxpColorGrade.h` cung cấp API C/C++ không dùng heap.
Mỗi bộ chỉnh màu dùng 256 byte LUT, khởi tạo một lần:

```c
#include "graphics/VxpColorGrade.h"
static VxpeColorGrade565 scene_grade;

/* Khi khởi tạo scene */
vxpe_grade_init(&scene_grade, VXPE_GRADE_DARK_FANTASY);

/* Sau khi vẽ scene và trước khi vẽ HUD */
vxpe_grade_rect(&scene_grade, framebuffer, 320, 240, 320,
                0, 0, 320, 216);
```

Các preset runtime cùng nhóm phong cách với editor nhưng chỉnh từng kênh
RGB, không ép framebuffer về palette 16 màu. `VXPE_GRADE_NEUTRAL` giữ
nguyên toàn bộ 65.536 màu. Có thể chỉnh riêng vùng gameplay để HUD giữ
màu; API clip vùng ngoài màn hình và hỗ trợ stride có padding.
Không áp lại trên frame đã chỉnh màu: vẽ lại vùng scene trước mỗi lần gọi.
Chi phí tỷ lệ số pixel xử lý; FPS trên thiết bị thật chưa được đo.

Kết hợp với Stage2D cho parallax, Scene25D cho chiều sâu,
Light2D/Vfx2D cho ánh sáng/phép thuật và Cinematic2D cho camera impact.
Các bộ chỉnh màu không bổ sung renderer 3D hay tái tạo tự động game từ video.

## Kiểm tra

Preset **Game · Urban Toon / VXPE_ARTSTYLE_URBAN_TOON** bổ sung màu đô thị
vàng/cyan/magenta, viền mực 2px và fog xanh. Renderer mesh/UV mới nằm trong
[VxpToon3D](URBAN_TOON_3D.md), độc lập với thao tác chỉnh palette ảnh.

- `reports/harness_game_art_styles.py`: palette, alpha, kích thước và tích hợp editor.
- CMake/CTest trong `engine/coremre/tests`: identity RGB565 toàn miền,
  clipping, stride/padding và giá trị biên.
