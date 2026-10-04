# Windows Run/Build/Debug runner

VXPEngine dùng `QProcess` và `cmd.exe` để chạy `.bat`/`.cmd` trên Windows.
Câu lệnh chuẩn từ 2.5.1:

```text
cmd.exe /d /c call .\gradlew.bat lwjgl3:run --console=plain --stacktrace
```

Không tự ghép một command string có dấu nháy kép. Mỗi token phải được truyền riêng
qua `QProcess.setArguments()` để Qt xử lý quoting theo Windows CreateProcess.

Nếu cần kiểm tra thủ công trong thư mục project:

```bat
call gradlew.bat --version
call gradlew.bat lwjgl3:classes --console=plain --stacktrace
call gradlew.bat lwjgl3:run --console=plain --stacktrace
```
