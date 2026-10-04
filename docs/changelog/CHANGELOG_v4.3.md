# VXPEngine v4.3.0 — Android Aspect Ratio Fix

- AndroidManifest không còn khóa cứng `landscape`.
- Tự chọn `portrait`, `landscape` hoặc `unspecified` từ kích thước Frame Preview.
- Build Android lấy viewport trực tiếp từ scene `.dtfe` đang dùng, sau đó đồng bộ lại `project.dtfe`.
- FitViewport tiếp tục giữ đúng tỉ lệ khi màn hình thiết bị có tỉ lệ khác.
- Module Android cũ do engine sinh được sửa riêng thuộc tính orientation mà không ghi đè mã Android khác.
- Script `generate_android_module.py` tự đồng bộ orientation mỗi lần build trực tiếp bằng Gradle.
- Màn chơi mới kế thừa kích thước viewport của màn đang hoạt động thay vì trở về 1280×720.
