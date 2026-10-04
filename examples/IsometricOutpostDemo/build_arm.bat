@echo off
rem Build <APP_NAME>.vxp bang VXPEngine SDK: w64devkit + ARM GCC + MRE API.
setlocal

set "PROJECT_DIR=%~dp0"
if not defined VXPE_W64DEVKIT set "VXPE_W64DEVKIT=D:\MRE\lib\w64devkit"
if not defined VXPE_ARM_TOOLCHAIN set "VXPE_ARM_TOOLCHAIN=C:\msys64\mingw64"
if not exist "%MRE_SDK%\include\vmsys.h" set "MRE_SDK=D:\MRE\VXPEngine\engine\coremre\sdk\mre"
if not defined VXPE_SDK_TOOLS set "VXPE_SDK_TOOLS=D:\MRE\VXPEngine\engine\coremre\tools"
if not defined VXPE_PYTHON set "VXPE_PYTHON=D:\MRE\VXPEngine\.venv\Scripts\python.exe"
set "CMAKE=%VXPE_W64DEVKIT%\bin\cmake.exe"
set "NINJA=%VXPE_W64DEVKIT%\bin\ninja.exe"
set "PATH=%VXPE_W64DEVKIT%\bin;%VXPE_ARM_TOOLCHAIN%\bin;%PATH%"

if not exist "%CMAKE%" (
    echo Khong tim thay w64devkit tai %VXPE_W64DEVKIT%
    exit /b 1
)
if not exist "%VXPE_ARM_TOOLCHAIN%\bin\arm-none-eabi-gcc.exe" (
    echo Khong tim thay ARM GCC tai %VXPE_ARM_TOOLCHAIN%
    exit /b 1
)
if not exist "%VXPE_SDK_TOOLS%\vxp_pack.py" (
    echo Khong tim thay VXPEngine SDK tools tai %VXPE_SDK_TOOLS%
    exit /b 1
)
if not exist "%VXPE_PYTHON%" (
    echo Khong tim thay Python tai %VXPE_PYTHON%
    exit /b 1
)

"%CMAKE%" -S "%PROJECT_DIR%." -B "%PROJECT_DIR%build-arm" -G "Ninja" ^
  -DCMAKE_TOOLCHAIN_FILE="%PROJECT_DIR%cmake\toolchain-arm-none-eabi.cmake" ^
  -DCMAKE_BUILD_TYPE=Release ^
  -DTOOLCHAIN_PREFIX="%VXPE_ARM_TOOLCHAIN%" ^
  -DCMAKE_MAKE_PROGRAM="%NINJA%" ^
  -DMRE_SDK="%MRE_SDK%" ^
  -DVXPE_PYTHON="%VXPE_PYTHON%" ^
  -DVXPE_SDK_TOOLS="%VXPE_SDK_TOOLS%"
if errorlevel 1 exit /b 1

"%CMAKE%" --build "%PROJECT_DIR%build-arm" --target main_vxp
if errorlevel 1 exit /b 1

echo.
echo Output: %PROJECT_DIR%build-arm\main\iso_outpost.vxp
echo Copy file .vxp vao the nho (vd E:\Others\) va mo tu menu ung dung MRE.
echo Ban nay CHUA KY. Ban signed dung khoa rieng theo App ID/Vendor do VXPEngine tao.
endlocal
