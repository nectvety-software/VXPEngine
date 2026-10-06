@echo off
rem ---------------------------------------------------------------------------
rem  Terra Editor launcher.  Double-click to open tilemaps.png, or pass args:
rem      run.bat                          -> editor with tilemaps.png (dark)
rem      run.bat --theme light            -> same sheet, light theme
rem      run.bat demo.terra.json          -> reopen a saved project
rem      run.bat other.png --cell 48      -> another sheet, fixed 48px cells
rem      run.bat --selftest               -> render UI offscreen into out\selftest
rem ---------------------------------------------------------------------------
setlocal
cd /d "%~dp0"

set "SHEET=tilemaps.png"
set "PY=python"
where py >nul 2>&1 && set "PY=py -3"

rem Pick an interpreter that actually has the GUI stack installed.
%PY% -c "import PySide6, PIL, numpy" >nul 2>&1
if errorlevel 1 (
    echo [run.bat] Missing dependencies. Installing PySide6 Pillow numpy ...
    %PY% -m pip install PySide6 Pillow numpy
    if errorlevel 1 (
        echo [run.bat] pip failed. Install manually:  %PY% -m pip install PySide6 Pillow numpy
        pause
        exit /b 1
    )
)

if "%~1"=="" (
    if not exist "%SHEET%" (
        echo [run.bat] No project given and "%SHEET%" was not found in %cd%
        pause
        exit /b 2
    )
    echo [run.bat] Opening %SHEET%
    %PY% main.py --sheet "%SHEET%"
) else (
    %PY% main.py %*
)

set "CODE=%ERRORLEVEL%"
if not "%CODE%"=="0" (
    echo [run.bat] Exited with code %CODE%
    pause
)
endlocal
exit /b %CODE%
