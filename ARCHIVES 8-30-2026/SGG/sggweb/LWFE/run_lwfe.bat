@echo off
setlocal
set "LWFE_DIR=%~dp0"
cd /d "%LWFE_DIR%"
where py >nul 2>nul
if errorlevel 1 (
    echo ERROR: The Windows Python launcher ^(py^) was not found.
    echo Install Python with the Windows Python launcher and Tk support,
    echo or launch LWFE from a CMD window using your configured Python.
    pause
    exit /b 1
)
py -3 "%LWFE_DIR%lwfe_app.py"
if errorlevel 1 (
    echo.
    echo LWFE did not start successfully. See the message above.
    pause
)
endlocal
