# VXPEngine v2.8.0

## Bottom Panel kiểu VS Code

- `Ctrl+J` hiện hoặc ẩn toàn bộ khu vực Console / Problems / Debugger / Output.
- Nút terminal ở Status Bar đồng bộ trạng thái với menu View.
- Nút thu gọn nằm ở góc phải thanh tab của Bottom Panel.
- Khi ẩn, Preview 2D và Code Editor tự dùng toàn bộ chiều cao cột giữa.
- Khi build có lỗi, Bottom Panel tự mở lại tại tab Problems.

## Run/Build dạng thanh tiến trình IDE

- Run Session không còn tự bật thành cửa sổ che editor.
- Tác vụ Run, Build, Debug, CMake và ADB xuất hiện dưới Status Bar dưới dạng task chip.
- Task chip hiển thị tên tác vụ, project, phase hiện tại và progress không xác định.
- Nút terminal mở cửa sổ log chi tiết dùng custom title bar.
- Nút `×` dừng toàn bộ cây tiến trình Gradle/Java/JDB/ADB.
- Khi hoàn tất, task chip đổi trạng thái rồi tự thu gọn.

## Ruler X/Y và Smart Guides

- Preview 2D có thước X ở cạnh trên và thước Y ở cạnh trái.
- Giá trị thước tự thay đổi theo pan và zoom.
- Khi kéo node bằng Select, engine tự bắt theo:
  - trục tọa độ 0;
  - cạnh và tâm Camera2D;
  - cạnh và tâm các node khác;
  - Grid khi Snap đang bật.
- Guide dọc màu xanh lá và guide ngang màu đỏ xuất hiện trong lúc căn chỉnh.
- Con trỏ hiện dấu vị trí trực tiếp trên hai thước.

## ADB / Android USB Type-C

- Thêm nút `ADB` trên toolbar và mục `Run on Android Device (ADB)` trong menu Run.
- Tự tìm `adb` từ PATH, `ANDROID_SDK_ROOT`, `ANDROID_HOME`, `local.properties` và vị trí Android SDK mặc định trên Windows.
- Quét thiết bị bằng `adb devices -l` và hiển thị model, serial, trạng thái.
- Chọn chính xác thiết bị khi có nhiều điện thoại hoặc giả lập.
- Pipeline chạy trực tiếp:
  1. sinh Android module theo yêu cầu;
  2. build `android:assembleDebug`;
  3. `adb -s <serial> install -r -t`;
  4. khởi chạy `AndroidLauncher` bằng Activity Manager.
- Nhận biết trạng thái `device`, `unauthorized`, `offline` và hướng dẫn bật USB debugging.
- Có lệnh làm mới thiết bị và khởi động lại ADB server.

## Phiên bản

- `ENGINE_VERSION = 2.8.0`.
