# VXPEngine 2.5.1 — Windows Batch Runner Hotfix

## Sửa lỗi Run/Build/Debug trên đường dẫn có khoảng trắng

Phiên bản 2.5.0 truyền một chuỗi lệnh đã được thêm dấu nháy vào `cmd.exe /s /c`.
Khi `QProcess` tiếp tục escape chuỗi đó, CMD nhận tên tệp dạng ký tự thô
`\"C:\\...\\gradlew.bat\"` và báo `is not recognized as an internal or external command`.

2.5.1 thay cơ chế này bằng:

```text
cmd.exe /d /c call .\gradlew.bat <task> <arguments>
```

Mỗi đối số được truyền riêng cho `QProcess`. Batch file được gọi bằng đường dẫn tương
đối từ working directory, nên project có dấu cách, dấu ngoặc hoặc tên người dùng dài
không còn làm hỏng câu lệnh.

## Phạm vi đã sửa

- Check Java / Gradle.
- Compile Java.
- Run Desktop LWJGL3.
- Debug Desktop JDWP/JDB.
- Build Desktop JAR.
- Build Android APK.
- Clean Gradle.
- Build C/C++ bằng batch file trong thư mục `native`.

## Tương thích

Project đã tạo bằng 2.5.0 không cần tạo lại. Chỉ cần mở project cũ bằng Engine 2.5.1
và chạy lại tác vụ.
