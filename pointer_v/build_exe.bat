@echo off
setlocal

echo ========================================================
echo    POINTER V - STANDALONE EXECUTABLE BUILDER
echo ========================================================
echo.

set "PY_CMD="
where python >nul 2>&1
if %errorlevel% equ 0 (
    set "PY_CMD=python"
) else (
    where py >nul 2>&1
    if %errorlevel% equ 0 (
        set "PY_CMD=py -3.12"
    ) else if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" (
        set "PY_CMD=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
    )
)

if "%PY_CMD%" == "" (
    echo [ERROR] Python is not found in PATH!
    echo Please install Python 3.11 or 3.12 from python.org and check "Add Python to PATH".
    exit /b 1
)

echo Using Python: %PY_CMD%
echo.
echo [1/3] Verifying dependencies from requirements.txt...
"%PY_CMD%" -m pip install -r requirements.txt >nul 2>&1
if %errorlevel% neq 0 (
    echo [WARNING] Dependency check completed with warnings, continuing...
)

echo.
echo [2/3] Building standalone onedir bundle with PyInstaller...
"%PY_CMD%" -m PyInstaller --clean --noconfirm PointerV.spec
if %errorlevel% neq 0 (
    echo [ERROR] PyInstaller build failed.
    exit /b 1
)

echo.
echo [3/3] Build complete!
echo Output folder: dist\PointerV\
echo Executable: dist\PointerV\PointerV.exe
echo.
endlocal
