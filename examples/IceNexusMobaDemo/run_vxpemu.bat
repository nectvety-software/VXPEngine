@echo off
setlocal
set "PROJECT_DIR=%~dp0"
set "VXP=%PROJECT_DIR%build-arm\main\ice_nexus_moba.vxp"
set "VXPEMU=%VXPE_VXPEMU%"
if not defined VXPEMU set "VXPEMU=D:\MRE\VXPEmu\build\Release\VXPEmu.exe"
if not exist "%VXPEMU%" set "VXPEMU=D:\MRE\VXPEmu\deploy\VXPEmu.exe"
call "%PROJECT_DIR%build_arm.bat"
if errorlevel 1 exit /b 1
start "VXPEmu - Ice Nexus MOBA" /d "%PROJECT_DIR%" "%VXPEMU%" "%VXP%" --autostart
endlocal
