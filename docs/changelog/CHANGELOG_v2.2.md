# VXPEngine 2.2.0 — Assets theo thư mục

## Cấu trúc assets mới

Project mới tạo đúng cây cố định:

```text
assets/
├── audio/
├── fonts/
├── scenes/
│   └── main.dtfe
├── map/
│   ├── background/
│   ├── skill/
│   ├── texture/
│   └── tileset/
└── app-icon/
```

Các thư mục cũ `assets/textures`, `assets/data`, `assets/ui`, `assets/maps` và `scenes/` không còn được tạo cho project mới. Project cũ vẫn được mở và các đường dẫn cũ vẫn được đọc để tương thích.

## Menu ba chấm theo thư mục

- Xóa nút ba chấm khỏi tiêu đề panel Assets.
- Mỗi thư mục trong `assets` có nút ba chấm riêng.
- `audio` chỉ nhập tệp âm thanh.
- `fonts` chỉ nhập font.
- `scenes`, `map/*` và `app-icon` mở Editor Assets với đúng thư mục đích.
- Chuột phải trên thư mục dùng cùng menu.
- Không có lệnh tạo folder hoặc tạo file tùy ý.

## Editor Assets

- Ảnh tiếp tục lưu dưới dạng PNG.
- Metadata `<name>.asset.dtfe` được đặt cạnh PNG.
- Scene Timeline tạo spritesheet `assets/scenes/<name>_ani.png`.
- Descriptor animation dùng tên độc quyền `assets/scenes/<name>.ani..dtfe`.
- Vẫn đọc tên cũ `.ani.dtfe` và metadata trong `assets/data`.

## Scene mặc định

- Scene khởi tạo chuyển từ `scenes/main.dtfe` sang `assets/scenes/main.dtfe`.
- Viewport và Scene Tree có fallback đọc đường dẫn cũ.
- Module Android vẫn chỉ được tạo khi build Android lần đầu.

## Phiên bản

- `ENGINE_VERSION = 2.2.0`.
