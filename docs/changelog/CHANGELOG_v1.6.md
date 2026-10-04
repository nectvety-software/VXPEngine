# Nova2D Engine 1.6.0

## Bố cục workspace ba cột

- Thay cấu trúc `top_split + bottom_split` bằng một `workspace_split` nằm ngang.
- Cột trái: Scene và Assets chạy suốt chiều cao.
- Cột giữa: Preview/Code ở trên, Console ở dưới. Console luôn đúng bằng chiều rộng Preview.
- Cột phải: Inspector ở trên, TileMap ở dưới.
- Preview nhận stretch chính theo chiều dọc; Console giữ chiều cao ban đầu gọn nhưng vẫn kéo thay đổi được.
- Các splitter không cho panel bị thu gọn hoàn toàn ngoài ý muốn.

## Tương thích

- Không thay đổi cấu trúc project libGDX, Java 17, Android hay JNI/C++.
- Không thay đổi logic chạy Gradle và nhận log Console.
