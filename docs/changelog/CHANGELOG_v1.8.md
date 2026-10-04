# Nova2D Engine v1.8

## Codebase cố định và Android tạo theo yêu cầu

- Xóa `Tạo thư mục…` và `Tạo tệp…` khỏi menu ba chấm của Assets.
- Assets chỉ còn nhập tài nguyên, làm mới và mở thư mục dự án.
- Dự án mới tạo cấu trúc chuẩn: `assets`, `configs`, `core`, `gradle`, `lwjgl3`, `scenes`, `scripts`, `tools` và `native` khi bật JNI.
- Không tạo `.gradle`, `.idea`, `build` hoặc `android` khi khởi tạo dự án.
- `.gradle`, `.idea` và `build` do Gradle/IDE sinh tự động.
- Khi chạy task `android:*`, Nova2D sinh module `android` trước rồi mới gọi Gradle.
- `settings.gradle` chỉ include Android khi `android/build.gradle` đã tồn tại.
- Các tệp Android đã chỉnh sửa không bị ghi đè ở lần build tiếp theo.
- Assets tự làm mới sau khi module Android được sinh.
