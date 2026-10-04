# Build và ký VXP

VXPEngine 2.0 dùng pipeline riêng:

1. w64devkit chạy CMake/GNU Make.
2. \`arm-none-eabi-gcc\` tạo ELF32 ARMv5TE.
3. \`vxp_resource.py\` tạo resource archive.
4. \`vxp_pack.py\` chèn \`.vm_res\`, App ID, Vendor và các tags MRE.
5. Build ARM Signed dùng \`vxp_signer.py\` tạo/đọc khóa riêng, chuẩn hóa cert ID
   100 và IMSI \`*\`, ký RSA-512/SHA-1 PKCS#1 v1.5 và tự verify.

\`\`\`bat
run_windows.bat check
<project>\scripts\build_arm.bat
<project>\scripts\run_vxpemu.bat
\`\`\`

Private key nằm tại \`signing/apps/<appid>-<vendor>/private.pem\`, không nằm trong
project. Firmware đích phải tin cậy public key tương ứng.
