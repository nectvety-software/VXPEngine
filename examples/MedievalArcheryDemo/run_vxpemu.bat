@echo off
setlocal
set "PROJECT_DIR=%~dp0"
set "VXP=%PROJECT_DIR%build-archery\main\arrowfall_duel.vxp"
set "VXPEMU=%VXPE_VXPEMU%"
if not defined VXPEMU set "VXPEMU=D:\MRE\VXPEmu\deploy\VXPEmu.exe"
if not exist "%VXPEMU%" set "VXPEMU=D:\MRE\VXPEmu\build\Release\VXPEmu.exe"
call "%PROJECT_DIR%build_arm.bat"
if errorlevel 1 exit /b 1
if not exist "%VXPEMU%" exit /b 1
start "VXPEmu - Arrowfall Duel" /d "%PROJECT_DIR%" "%VXPEMU%" "%VXP%" --autostart
endlocal
