# VXPEngine 2.5.0 — Deep Tools, Programming, Run/Build/Debug

## Scene tools

- Nối thật `Select`, `Move`, `Rotate`, `Scale` vào `Viewport2D`.
- Nối thật `Rectangle`, `Circle`, `Line`, `Text`, `Tile`, `Brush` để tạo node `.dtfe`.
- Thêm snap grid, duplicate, delete, frame selection, pan/zoom và undo/redo scene.
- Inspector cập nhật transform, opacity, z-index, visibility, vector style và nội dung text.
- Scene được lưu atomic vào `assets/scenes/main.dtfe`.

## DTFE runtime

- Tự sinh `core/.../runtime/DtfeSceneRuntime.java`.
- Runtime đọc `main.dtfe` và dựng Sprite2D, Rectangle2D, Circle2D, Line2D, Brush2D, Tile2D và Text2D.
- `VxpGame.java` dùng runtime mới trong vòng đời create/render/resize/dispose.
- Dự án cũ có template trống được nâng cấp tự động; mã gameplay người dùng đã chỉnh sửa được giữ nguyên.

## Code editor

- Breakpoint bằng cách nhấp gutter.
- Diagnostic marker và highlight theo dòng cho Java/Gradle và C/C++ (GCC/Clang/MSVC).
- Auto-indent, bracket pairing, comment toggle, go-to-line, indent/unindent.
- Problems panel mở đúng tệp, dòng và cột lỗi.

## Run / Build / Debug

- Compile Java: `lwjgl3:classes` (kiểm tra cả `core` và launcher desktop).
- Run Desktop: `lwjgl3:run`.
- Debug Desktop: `lwjgl3:run --debug-jvm --no-daemon` + JDB attach.
- Continue, Pause, Step Over, Step Into, Step Out, Stack, Locals và Threads.
- Tự thử kết nối lại JDB trong lúc Gradle chuẩn bị JVM.
- Dừng cây tiến trình con trên Windows.
- Phát hiện artifact JAR, APK/AAB và DLL/SO/DYLIB sau build.
- Console, Problems, Debugger và Output nhận dữ liệu thật.

## Version

- `ENGINE_VERSION = 2.5.0`.
