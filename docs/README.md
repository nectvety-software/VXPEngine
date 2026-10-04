# Documentation — VXPEngine

Tài liệu VXPEngine được tổ chức như `D:\Tools\VXPEngine\docs` (cơ chế 100% giống):

- `VXPEngine_Manual.md` — hướng dẫn sử dụng chính (26 mục, như VXPEngine_Manual.md).
- `index.html` — phiên bản HTML cho `DocumentationPage` trong IDE (offline docs).
- `guides/` — ghi chú kỹ thuật theo chủ đề (DTFE, PixelRoot32, MRE build, runner…).
- `changelog/` — lịch sử thay đổi theo phiên bản (`CHANGELOG_v*.md`).

Tài liệu giới thiệu và khởi động nhanh vẫn nằm tại `README.md` ở thư mục gốc.
Cơ chế nạp docs trong IDE: `app/widgets/documentation_page.py` đọc `docs/index.html` và `docs/guides/*.md` như VXPEngine.
