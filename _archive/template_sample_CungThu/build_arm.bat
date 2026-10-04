@echo off
rem Build <APP_NAME>.vxp cho máy thật (MRE ARM) — chạy thuần cmd, KHÔNG cần Git Bash.
rem Dùng CMake + MinGW Makefiles + arm-none-eabi-gcc từ MSYS2.
setlocal

set "PROJECT_DIR=%~dp0"
set "MSYS_MINGW=C:\msys64\mingw64"
set "PATH=%MSYS_MINGW%\bin;%PATH%"

if not exist "%MSYS_MINGW%\bin\mingw32-make.exe" (
    echo Khong tim thay MSYS2 MinGW tai %MSYS_MINGW%
    echo Cai MSYS2 va goi arm-none-eabi-gcc, hoac sua duong dan trong script nay.
    exit /b 1
)

cmake -S "%PROJECT_DIR%." -B "%PROJECT_DIR%build-arm" -G "MinGW Makefiles" ^
  -DCMAKE_TOOLCHAIN_FILE="%PROJECT_DIR%cmake\toolchain-arm-none-eabi.cmake" ^
  -DCMAKE_BUILD_TYPE=Release ^
  -DTOOLCHAIN_PREFIX="%MSYS_MINGW%" ^
  -DCMAKE_MAKE_PROGRAM="%MSYS_MINGW%\bin\mingw32-make.exe" ^
  -DMRE_SDK="D:/MRE/XimikBoda/third_party/mre-sdk/app" ^
  -DTinyMRESDK="D:/MRE/XimikBoda/TinyMRESDK-main"
if errorlevel 1 exit /b 1

cmake --build "%PROJECT_DIR%build-arm" --target main_vxp
if errorlevel 1 exit /b 1

echo.
echo Output: %PROJECT_DIR%build-arm\main\CungThuBongDen.vxp
echo Copy file .vxp vao the nho (vd E:\Others\) va mo tu menu ung dung MRE.
echo Ban nay CHUA KY - chi chay tren may dev. Ban ky retail do VXPEngine build (khoa thuoc engine).
endlocal
