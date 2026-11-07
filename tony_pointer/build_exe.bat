@echo off
echo ========================================================
echo    TONY POINTER - STANDALONE EXECUTABLE BUILDER
echo ========================================================
echo.

python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not found in PATH!
    echo Please install Python 3.11 from python.org and check "Add Python to PATH".
    pause
    exit /b 1
)

echo [1/3] Installing dependencies from requirements.txt...
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo [ERROR] Dependency installation failed.
    pause
    exit /b 1
)

echo.
echo [2/3] Building standalone single-file TonyPointer.exe with PyInstaller...
pyinstaller --clean tony_pointer.spec
if %errorlevel% neq 0 (
    echo [ERROR] PyInstaller build failed.
    pause
    exit /b 1
)

echo.
echo [3/3] Build complete!
echo Executable generated in: dist\TonyPointer.exe
echo.
echo You can now copy dist\TonyPointer.exe anywhere and run it without Python installed!
pause
