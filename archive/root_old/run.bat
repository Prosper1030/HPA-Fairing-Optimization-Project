@echo off
REM Quick launcher for VSP Python scripts
REM Usage: run.bat script_name.py [arguments]

set PYTHON_EXE=%~dp0vsp_env\Scripts\python.exe

if not exist "%PYTHON_EXE%" (
    echo Error: Python environment not found at %PYTHON_EXE%
    exit /b 1
)

if "%1"=="" (
    echo Usage: run.bat script_name.py [arguments]
    exit /b 1
)

"%PYTHON_EXE%" %*
