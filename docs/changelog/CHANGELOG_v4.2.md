# VXPEngine v4.2.0

- Thêm **Ánh xạ vai trò / tự động hóa** cho mọi thành phần hoặc nhóm trong Frame Preview.
- Một ảnh bất kỳ có thể trở thành joystick, nút hướng, nút hành động, nút kỹ năng, ground, platform, hazard, portal, collectible, player hoặc enemy.
- Scene Tree và Inspector đều mở được công cụ ánh xạ.
- Runtime tự đọc touch cho joystick/nút và xuất `inputValue`, `inputPressed`, `inputAxis`.
- Runtime thêm truy vấn `findByRole`, `findByTag`, `getColliders`, `overlaps`.
- Portal và vùng sự kiện có thể tự sinh event metadata không trùng lặp.
- Java bindings thêm role, physics, collision shape, tags, dead-zone, sensitivity, event channel và target screen.
- Ánh xạ là tùy chọn, không ghi đè mã gameplay Java của người dùng.
