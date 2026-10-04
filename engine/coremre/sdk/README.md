# VXPEngine SDK

SDK này là nguồn cấu hình duy nhất cho pipeline `coremre`.

## Bố cục portable

```text
sdk/
  w64devkit/      CMake, Ninja, GNU Make và GCC host
  arm-toolchain/  arm-none-eabi-gcc (ARMv5TE)
  mre/            include/ và lib/ của MRE API
  vxpemu/         VXPEmu.exe cùng các DLL runtime
```

Nếu chưa chép tool vào SDK, runner tự dò các bản đang có trên máy. Có thể ghi đè
bằng `VXPE_W64DEVKIT`, `VXPE_ARM_TOOLCHAIN`, `MRE_SDK`, `VXPE_SDK_TOOLS` và
`VXPE_VXPEMU`. `w64devkit` cung cấp công cụ host; ARM GCC và thư viện MRE vẫn là
hai thành phần riêng vì w64devkit x64 không chứa compiler ARM.
