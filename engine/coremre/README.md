# coremre 2.0 — lõi vxpstore/corevxp của VXPEngine (MRE VXP + Arduino)

`coremre` là target C++17 duy nhất dùng chung cho ứng dụng VXPEngine. Tên gọi
riêng của core là **vxpstore** (alias ngắn: **corevxp**) — dựa trên
PixelRoot32-Game-Engine nhưng đã tách độc lập, chỉ hỗ trợ **MRE VXP và
Arduino**, không dùng cho Java, không còn tên PixelRoot32 ở tầng người dùng.

- Target chuẩn: `VXPEngine::coremre` (tên tương thích: `coremre`, `vxpstore`).
- Header umbrella cho game: `vxpstore/Core.h` (`vxpstore::Engine`, `Scene`, …).
- CMake dùng danh sách source tường minh, không quét glob và không kéo
  backend ESP32/SDL2/Java vào bản MRE.

SDK nằm tại `sdk/`. Runtime thử nghiệm duy nhất là VXPEmu.
