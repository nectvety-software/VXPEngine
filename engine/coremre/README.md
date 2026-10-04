# coremre 2.0 — lõi MRE VXP của VXPEngine

`coremre` là target C++17 duy nhất dùng chung cho ứng dụng VXPEngine. Target
chuẩn là `VXPEngine::coremre` (tên tương thích: `coremre`). CMake dùng danh sách
source tường minh, không quét glob và không kéo backend Arduino/ESP32/SDL2 vào
bản MRE.

SDK nằm tại `sdk/`; backend ký re3 nằm tại `tools/vxp_signer.py`. Build tạo VXP
chưa ký trước, sau đó signer chuẩn hóa App ID/certid/IMSI, ký RSA-SHA1 PKCS#1
v1.5 và tự verify. Runtime thử nghiệm duy nhất là VXPEmu.
