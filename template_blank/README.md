# BlankApp — project MRE VXP trống

Mẫu project 240×320 dành cho ứng dụng/game S30+ MRE VXP.

- Build host dùng w64devkit; build thiết bị dùng ARM GCC.
- MRE headers/libs lấy từ SDK tích hợp của VXPEngine.
- Resource và VXP được đóng gói bằng công cụ Python của `coremre`.
- `scripts/run_vxpemu.bat` build ARM rồi mở file `.vxp` bằng VXPEmu.
- Build ARM Signed trong IDE tạo khóa riêng theo App ID/Vendor; private key chỉ nằm
  trong kho `VXPEngine/signing/apps`, không nằm trong project.

```text
assets/                  ảnh, âm thanh, scene .dtfe do người dùng quản lý
src/                     mã C và binding scene do người dùng quản lý
resources/gen/           resource sinh tự động, không sửa tay
scripts/                 lệnh build/chạy thuận tiện
.vxpe/                   pipeline MRE được VXPEngine cập nhật an toàn
build-arm/               output ARM .vxp (không commit)
```

```bat
scripts\build_arm.bat
scripts\run_vxpemu.bat
```

VXPEngine chỉ cập nhật tệp do engine quản lý khi chúng chưa bị sửa cục bộ.
Trạng thái đồng bộ nằm trong `.vxpe/template-state.json`; code và asset của dự
án không bao giờ bị ghi đè khi template mới được phát hành.
