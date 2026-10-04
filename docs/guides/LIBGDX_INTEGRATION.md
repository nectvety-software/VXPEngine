# Kiến trúc tích hợp libGDX

## Một cơ sở mã dùng chung

- `core`: toàn bộ gameplay, rendering 2D, input, entity, physics và scene runtime.
- `lwjgl3`: launcher desktop; không chứa gameplay riêng.
- `android`: launcher Android tạo theo yêu cầu trước build APK đầu tiên; không chứa gameplay riêng.
- `assets`: tài nguyên dùng chung cho cả desktop và Android.

## Native bridge

- Java API: `NativePerformance`.
- C++ implementation: `native_performance.cpp`.
- Build system: CMake 3.22.1 trở lên.
- Android: Android Gradle Plugin gọi CMake/NDK.
- Windows: `native/build_native_windows.bat`.
- Fallback: Java tự động nếu native library chưa được nạp.

## Task Gradle dùng trong VXPEngine

| Chức năng | Task |
|---|---|
| Chạy desktop | `lwjgl3:run` |
| Build desktop JAR | `lwjgl3:dist` |
| Build Android APK debug | `android:assembleDebug` |
| Xóa output | `clean` |

## Đầu ra

- Desktop JAR: `lwjgl3/build/libs/<TênDựÁn>-desktop.jar`
- Android APK: `android/build/outputs/apk/debug/android-debug.apk`
- Native Windows: `native/build/windows/vxp_native.dll`


## Android tạo theo yêu cầu (v1.8)

Project mới không có thư mục `android`. Cả nút Build trong VXPEngine và `gradlew.bat android:assembleDebug` đều gọi `scripts/generate_android_module.py` trước khi Gradle cấu hình project. Script chỉ tạo tệp còn thiếu và không ghi đè mã Android đã chỉnh sửa.
