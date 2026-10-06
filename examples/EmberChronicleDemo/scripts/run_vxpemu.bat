@echo off
setlocal

set "PROJECT_DIR=%~dp0.."
set "VXP=%PROJECT_DIR%\build-arm\main\ember_chronicle.vxp"
set "VXPEMU=%VXPE_VXPEMU%"
if not defined VXPEMU set "VXPEMU=D:\MRE\VXPEmu\deploy\VXPEmu.exe"
if not exist "%VXPEMU%" set "VXPEMU=D:\MRE\VXPEmu\build\Release\VXPEmu.exe"

call "%~dp0build_arm.bat"
if errorlevel 1 exit /b 1
if not exist "%VXP%" (
    echo VXP output was not found: %VXP%
    exit /b 1
)
if not exist "%VXPEMU%" (
    echo VXPEmu.exe was not found: %VXPEMU%
    exit /b 1
)

start "VXPEmu - ember_chronicle" /d "%PROJECT_DIR%" "%VXPEMU%" "%VXP%" --autostart
endlocal
