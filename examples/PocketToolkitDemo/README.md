# pocket_tools — project MRE VXP trống

Mẫu project 240×320 dành cho ứng dụng/game S30+ MRE VXP.

- Build host dùng w64devkit; build thiết bị dùng ARM GCC.
- MRE headers/libs lấy từ SDK tích hợp của VXPEngine.
- Resource và VXP được đóng gói bằng công cụ Python của `coremre`.
- `run_vxpemu.bat` build ARM rồi mở file `.vxp` bằng VXPEmu.
- Build ARM Signed trong IDE tạo khóa riêng theo App ID/Vendor; private key chỉ nằm
  trong kho `VXPEngine/signing/apps`, không nằm trong project.

```text
assets/                  tài nguyên nguồn
src/main.c               entry point MRE
resources/gen/           resource đã chuyển đổi
cmake/, common/, mreapi/ pipeline build VXP
build-arm/               output ARM .vxp
```

```bat
build_arm.bat
run_vxpemu.bat
```
