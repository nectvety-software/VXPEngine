@echo off
setlocal

set "PROJECT_DIR=%~dp0"
set "VXP=%PROJECT_DIR%build-arm\main\pocket_tools.vxp"
set "VXPEMU=%VXPE_VXPEMU%"
if not defined VXPEMU set "VXPEMU=D:\MRE\VXPEmu\deploy\VXPEmu.exe"
if not exist "%VXPEMU%" set "VXPEMU=D:\MRE\VXPEmu\build\Release\VXPEmu.exe"

call "%PROJECT_DIR%build_arm.bat"
if errorlevel 1 exit /b 1
if not exist "%VXP%" (
    echo VXP output was not found: %VXP%
    exit /b 1
)
if not exist "%VXPEMU%" (
    echo VXPEmu.exe was not found: %VXPEMU%
    exit /b 1
)

start "VXPEmu - pocket_tools" /d "%~dp0" "%VXPEMU%" "%VXP%" --autostart
endlocal
