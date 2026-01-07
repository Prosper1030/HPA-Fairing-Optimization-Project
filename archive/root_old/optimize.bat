@echo off
REM Quick launcher for main optimization
REM Just run: optimize.bat

echo ================================================================================
echo   Birdman Fairing Optimizer
echo ================================================================================
echo.

"%~dp0vsp_env\Scripts\python.exe" "%~dp0scripts\main_optimization.py" %*

if errorlevel 1 (
    echo.
    echo [ERROR] Optimization failed. Check error messages above.
    pause
) else (
    echo.
    echo [SUCCESS] Optimization completed. Check output/ folder for results.
)
