@echo off
setlocal
set "PROJECT_DIR=%~dp0."
set "VXPEMU=%VXPE_VXPEMU%"
if not defined VXPEMU set "VXPEMU=D:\MRE\VXPEmu\deploy\VXPEmu.exe"
if not exist "%VXPEMU%" set "VXPEMU=D:\MRE\VXPEmu\build-new\VXPEmu.exe"
call "%PROJECT_DIR%\build_arm.bat"
if errorlevel 1 exit /b 1
if not exist "%PROJECT_DIR%\build-arm\main\ssh_bridge.vxp" exit /b 2
if not exist "%VXPEMU%" exit /b 3
start "SSH Web Bridge" /d "%PROJECT_DIR%" "%VXPEMU%" "%PROJECT_DIR%\build-arm\main\ssh_bridge.vxp" --autostart
endlocal
