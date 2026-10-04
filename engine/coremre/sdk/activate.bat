@echo off
set "VXPE_SDK=%~dp0"
if exist "%VXPE_SDK%w64devkit\bin\cmake.exe" set "VXPE_W64DEVKIT=%VXPE_SDK%w64devkit"
if exist "%VXPE_SDK%arm-toolchain\bin\arm-none-eabi-gcc.exe" set "VXPE_ARM_TOOLCHAIN=%VXPE_SDK%arm-toolchain"
if exist "%VXPE_SDK%mre\include" set "MRE_SDK=%VXPE_SDK%mre"
set "VXPE_SDK_TOOLS=%~dp0..\tools"
if exist "%VXPE_SDK%vxpemu\VXPEmu.exe" set "VXPE_VXPEMU=%VXPE_SDK%vxpemu\VXPEmu.exe"
if defined VXPE_W64DEVKIT set "PATH=%VXPE_W64DEVKIT%\bin;%PATH%"
if defined VXPE_ARM_TOOLCHAIN set "PATH=%VXPE_ARM_TOOLCHAIN%\bin;%PATH%"
echo VXPEngine SDK environment activated.
