# Android Aspect Ratio Synchronization

Nguồn dữ liệu build được ưu tiên theo thứ tự:

1. `assets/scenes/<start_scene>.dtfe > viewport.width/height`
2. `project.dtfe > display.width/height`
3. dự phòng `1280×720`

Quy tắc orientation:

- `height > width` → `portrait`
- `width > height` → `landscape`
- `width == height` → `unspecified`; FitViewport tạo letterbox/pillarbox phù hợp

Trước mỗi task Android, engine đồng bộ:

- `AndroidManifest.xml`
- `project.dtfe > display`
- `.vxpe-generated.dtfe`

Engine chỉ sửa các thuộc tính hiển thị cần thiết trong manifest, không thay toàn bộ tệp Android đã chỉnh sửa.
