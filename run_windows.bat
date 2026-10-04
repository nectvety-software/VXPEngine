@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul 2>&1

REM VXPEngine Windows launcher.
REM Double-click (or run without arguments) to start the application.

set "ROOT_DIR=%~dp0"
set "VENV_DIR=%ROOT_DIR%.venv"
set "VENV_PY=%VENV_DIR%\Scripts\python.exe"
set "APP_MAIN=%ROOT_DIR%app\main.py"
set "SIM_MAIN=%ROOT_DIR%simulator\standalone_simulator.py"
set "COMMAND=%~1"
set "SIM_PORT=%~2"
set "FROM_MENU=0"
set "RC=0"

if not defined SIM_PORT set "SIM_PORT=8765"

pushd "%ROOT_DIR%" >nul 2>&1
if errorlevel 1 (
    echo [VXPEngine] Khong the truy cap thu muc "%ROOT_DIR%".
    pause
    exit /b 1
)

if not defined COMMAND goto :run_ide
if /i "%COMMAND%"=="ide"    goto :run_ide
if /i "%COMMAND%"=="sim"    goto :run_sim
if /i "%COMMAND%"=="deps"   goto :run_deps
if /i "%COMMAND%"=="check"  goto :run_check
if /i "%COMMAND%"=="test"   goto :run_test
if /i "%COMMAND%"=="update" goto :run_update
if /i "%COMMAND%"=="menu"   goto :menu
if /i "%COMMAND%"=="help"   goto :help
if /i "%COMMAND%"=="--help" goto :help
if /i "%COMMAND%"=="-h"     goto :help

echo [VXPEngine] Lenh khong hop le: %COMMAND%
echo.
goto :help_error

:run_ide
call :ensure_runtime
if errorlevel 1 goto :failed
if not exist "%APP_MAIN%" (
    echo [VXPEngine] Khong tim thay "%APP_MAIN%".
    goto :failed
)
echo.
echo [VXPEngine] Dang khoi dong VXPEngine...
echo.
"%VENV_PY%" "%APP_MAIN%"
set "RC=%ERRORLEVEL%"
if not "%RC%"=="0" (
    echo.
    echo [VXPEngine] Phan mem da thoat voi ma loi %RC%.
    echo Thu chay: run_windows.bat deps
    if "%FROM_MENU%"=="0" pause
)
goto :task_done

:run_sim
call :ensure_runtime
if errorlevel 1 goto :failed
if not exist "%SIM_MAIN%" (
    echo [VXPEngine] Khong tim thay "%SIM_MAIN%".
    goto :failed
)
echo.
echo [VXPEngine] Dang chay Frame Simulator tai http://127.0.0.1:%SIM_PORT%
echo Nhan Ctrl+C de dung.
echo.
"%VENV_PY%" "%SIM_MAIN%" --port "%SIM_PORT%"
set "RC=%ERRORLEVEL%"
goto :task_done

:run_deps
call :ensure_venv
if errorlevel 1 goto :failed
call :install_deps
if errorlevel 1 goto :failed
echo.
echo [VXPEngine] Da cai dat xong thu vien Python.
set "RC=0"
goto :task_done

:run_check
call :ensure_venv
if errorlevel 1 goto :failed
if not exist "%SIM_MAIN%" (
    echo [VXPEngine] Khong tim thay "%SIM_MAIN%".
    goto :failed
)
"%VENV_PY%" "%SIM_MAIN%" --check
set "RC=%ERRORLEVEL%"
goto :task_done

:run_update
call :ensure_venv
if errorlevel 1 goto :failed
if not exist "%SIM_MAIN%" (
    echo [VXPEngine] Khong tim thay "%SIM_MAIN%".
    goto :failed
)
"%VENV_PY%" "%SIM_MAIN%" --update
set "RC=%ERRORLEVEL%"
goto :task_done

:run_test
call :ensure_runtime
if errorlevel 1 goto :failed
echo [VXPEngine] Dang chay bo tu kiem tra editor, SDK va VXPEmu...
"%VENV_PY%" -m compileall -q "%ROOT_DIR%app" "%ROOT_DIR%simulator"
if errorlevel 1 goto :failed
for %%T in (harness_native_project_picker.py harness_cmake_cache_relocation.py harness_inspector_engine.py harness_inspector_styles.py harness_background_bitmap.py harness_asset_editor_apply.py harness_smart_guides.py harness_camera_layout_bounds.py harness_editor_layout.py harness_hidden_scrollbars.py harness_language_tips.py harness_multi_alignment.py harness_component_library_flow.py harness_design_pipeline.py harness_sim_tools.py harness_demo_build.py) do (
    echo [TEST] %%T
    "%VENV_PY%" "%ROOT_DIR%reports\%%T"
    if errorlevel 1 goto :failed
)
call :run_check
goto :task_done

:menu
set "FROM_MENU=1"
cls
echo.
echo ============================================================
echo   VXPEngine - Launcher
echo ============================================================
echo.
echo   [1] Chay VXPEngine
echo   [2] Chay Frame Simulator
echo   [3] Cai dat lai thu vien Python
echo   [4] Kiem tra moi truong
echo   [5] Kiem tra cap nhat SDK
echo   [6] Tu kiem tra toan bo Engine + build demo
echo   [0] Thoat
echo.
set "CHOICE="
set /p "CHOICE=Chon [1]: "
if not defined CHOICE set "CHOICE=1"
if "%CHOICE%"=="1" goto :run_ide
if "%CHOICE%"=="2" goto :run_sim
if "%CHOICE%"=="3" goto :run_deps
if "%CHOICE%"=="4" goto :run_check
if "%CHOICE%"=="5" goto :run_update
if "%CHOICE%"=="6" goto :run_test
if "%CHOICE%"=="0" goto :success
echo Lua chon khong hop le: %CHOICE%
pause
goto :menu

:ensure_runtime
call :ensure_venv
if errorlevel 1 exit /b 1
"%VENV_PY%" -c "import PySide6, qtawesome" >nul 2>&1
if errorlevel 1 (
    echo [VXPEngine] Dang cai cac thu vien Python con thieu...
    call :install_deps
    if errorlevel 1 exit /b 1
)
exit /b 0

:ensure_venv
if exist "%VENV_PY%" (
    "%VENV_PY%" -c "import sys; raise SystemExit(not (sys.version_info.major == 3 and sys.version_info.minor in range(11, 100)))" >nul 2>&1
    if not errorlevel 1 exit /b 0
    echo [VXPEngine] .venv bi hong hoac dang tro toi ban Python khong con ton tai.
    echo [VXPEngine] Dang tu dong sua moi truong Python...
    call :find_python
    if errorlevel 1 exit /b 1
    "!BASE_PY!" !BASE_PY_ARGS! -m venv --upgrade "%VENV_DIR%"
    if errorlevel 1 (
        echo [VXPEngine] Khong the tu dong sua .venv.
        echo Hay doi ten/xoa "%VENV_DIR%" roi chay lai launcher.
        exit /b 1
    )
    "%VENV_PY%" -c "import sys; raise SystemExit(not (sys.version_info.major == 3 and sys.version_info.minor in range(11, 100)))" >nul 2>&1
    if errorlevel 1 (
        echo [VXPEngine] .venv sau khi sua van khong hop le.
        exit /b 1
    )
    exit /b 0
)

call :find_python
if errorlevel 1 exit /b 1
echo [VXPEngine] Dang tao moi truong Python tai "%VENV_DIR%"...
"%BASE_PY%" %BASE_PY_ARGS% -m venv "%VENV_DIR%"
if errorlevel 1 (
    echo [VXPEngine] Khong tao duoc .venv.
    exit /b 1
)
exit /b 0

:find_python
set "BASE_PY="
set "BASE_PY_ARGS="
for %%V in (3.12 3.11 3.13) do (
    py -%%V -c "import sys" >nul 2>&1
    if not errorlevel 1 if not defined BASE_PY (
        set "BASE_PY=py"
        set "BASE_PY_ARGS=-%%V"
    )
)
if not defined BASE_PY if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" set "BASE_PY=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
if not defined BASE_PY if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" set "BASE_PY=%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
if not defined BASE_PY if exist "%LOCALAPPDATA%\Programs\Python\Python313\python.exe" set "BASE_PY=%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
if not defined BASE_PY if exist "C:\Python312\python.exe" set "BASE_PY=C:\Python312\python.exe"
if not defined BASE_PY if exist "C:\Python311\python.exe" set "BASE_PY=C:\Python311\python.exe"
if not defined BASE_PY if exist "C:\Python313\python.exe" set "BASE_PY=C:\Python313\python.exe"
if not defined BASE_PY (
    where python >nul 2>&1
    if not errorlevel 1 set "BASE_PY=python"
)
if not defined BASE_PY (
    echo [VXPEngine] Khong tim thay Python 3.11 tro len.
    echo Hay cai Python, bat tuy chon Add Python to PATH, roi chay lai.
    exit /b 1
)
echo [VXPEngine] Su dung Python: !BASE_PY! !BASE_PY_ARGS!
"!BASE_PY!" !BASE_PY_ARGS! -c "import sys; raise SystemExit(not (sys.version_info.major == 3 and sys.version_info.minor in range(11, 100)))" >nul 2>&1
if errorlevel 1 (
    echo [VXPEngine] Can Python 3.11 tro len.
    exit /b 1
)
exit /b 0

:install_deps
if not exist "%ROOT_DIR%requirements.txt" (
    echo [VXPEngine] Khong tim thay requirements.txt.
    exit /b 1
)
"%VENV_PY%" -m pip install -r "%ROOT_DIR%requirements.txt"
if errorlevel 1 (
    echo [VXPEngine] Cai dat thu vien that bai.
    exit /b 1
)
exit /b 0

:task_done
if "%FROM_MENU%"=="1" (
    echo.
    pause
    goto :menu
)
goto :finish

:help
echo.
echo Cach dung:
echo   run_windows.bat              Chay VXPEngine
echo   run_windows.bat ide          Chay VXPEngine
echo   run_windows.bat sim [port]   Chay Frame Simulator
echo   run_windows.bat deps         Cai dat thu vien Python
echo   run_windows.bat check        Kiem tra moi truong
echo   run_windows.bat test         Tu kiem tra Editor, SDK, VXPEmu
echo   run_windows.bat update       Kiem tra cap nhat SDK
echo   run_windows.bat menu         Mo menu tac vu
set "RC=0"
goto :finish

:help_error
echo Cach dung: run_windows.bat [ide^|sim^|deps^|check^|test^|update^|menu]
set "RC=2"
goto :finish

:failed
set "RC=1"
if "%FROM_MENU%"=="0" pause
goto :task_done

:success
set "RC=0"

:finish
popd
endlocal & exit /b %RC%
