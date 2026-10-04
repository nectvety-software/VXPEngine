# VXPEngine v4.5.0

## Scene panel
- Thu nhỏ icon thêm màn, menu ba chấm, mắt, khóa và tùy chọn lớp.
- Thumbnail layer giảm từ 34 px xuống 26 px để Scene Tree gọn hơn.

## Group layout dragging
- Khi dùng Select và nhấn vào một thành phần thuộc group, toàn bộ group được chọn.
- Kéo một thành phần sẽ di chuyển tất cả layout trong group, giữ nguyên khoảng cách tương đối.
- Ctrl + click cho phép chọn riêng một member để chỉnh chi tiết.
- Vị trí toàn bộ member được lưu lại vào scene và Java bindings sau khi thả chuột.

## Runtime automation V6
- Joystick ảo, nút hướng và bàn phím được gom vào cùng hệ input.
- Runtime tự xử lý MOVE_AXIS, MOVE_LEFT/RIGHT/UP/DOWN, JUMP và RUN.
- Player mapping có hai chế độ Platformer và Top-down.
- Platformer có gravity, jump, ground/static collider và one-way platform cơ bản.
- Trigger, hazard, collectible và portal được thực thi tự động khi bật auto_execute.
- Portal có thể chuyển map dựa trên screens.dtfe.
- Thêm inputJustPressed(), signalActive() và switchScreen().
- Project cũ dùng runtime V3/V4/V5 được nâng cấp an toàn lên V6 khi mở lại.
