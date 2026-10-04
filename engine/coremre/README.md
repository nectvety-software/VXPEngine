# coremre 2.0 — lõi MRE VXP của VXPEngine

`coremre` là target C++17 duy nhất dùng chung cho ứng dụng VXPEngine. Target
chuẩn là `VXPEngine::coremre` (tên tương thích: `coremre`). CMake dùng danh sách
source tường minh, không quét glob và không kéo backend Arduino/ESP32/SDL2 vào
bản MRE.

SDK nằm tại `sdk/`. Runtime thử nghiệm duy nhất là VXPEmu.
