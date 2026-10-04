@echo off
setlocal

set "PROJECT_DIR=%~dp0"
set "BUILD_DIR=%PROJECT_DIR%build-win32"
set "VXP=%BUILD_DIR%\main\Release\CungThuBongDen.vc.vxp"
set "MREMU_ROOT=D:\MRE\XimikBoda\MREmu-master"
set "MREMU=%MREMU_ROOT%\bin\Release\MREmu.exe"
set "OPENAL=%MREMU_ROOT%\deps\SFML\extlibs\bin\x86\openal32.dll"
set "MREMU_DIR=%MREMU_ROOT%\bin\Release"

if not exist "%MREMU%" (
    echo MREmu.exe was not found:
    echo   %MREMU%
    exit /b 1
)

if not exist "%MREMU_DIR%\openal32.dll" if exist "%OPENAL%" copy /y "%OPENAL%" "%MREMU_DIR%\openal32.dll" >nul

if not exist "%BUILD_DIR%\CungThuBongDen.sln" (
    cmake -S "%PROJECT_DIR%" -B "%BUILD_DIR%" -G "Visual Studio 17 2022" -A Win32
    if errorlevel 1 exit /b 1
)

rem emulator test build: enable hidden debug cheats (NUM1 restore, NUM3 clear wave)
rem (%~dp0 keeps its trailing backslash, so append "." to avoid \" escaping)
cmake -S "%PROJECT_DIR%." -B "%BUILD_DIR%" -DTEST_CHEAT=ON >nul 2>&1
if errorlevel 1 exit /b 1

cmake --build "%BUILD_DIR%" --config Release --target main_vxp
if errorlevel 1 exit /b 1

if not exist "%VXP%" (
    echo VXP output was not found:
    echo   %VXP%
    exit /b 1
)

for /f "tokens=5" %%P in ('tasklist /fi "imagename eq MREmu.exe" ^| find /i "MREmu.exe"') do taskkill /pid %%P /f >nul 2>&1

start "MREmu - CungThuBongDen" /d "%MREMU_DIR%" "%MREMU%" "%VXP%" -l
endlocal
