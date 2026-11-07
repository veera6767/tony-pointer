@echo off
setlocal enabledelayedexpansion

echo ========================================================
echo    POINTER V - INNO SETUP INSTALLER BUILDER
echo ========================================================
echo.

set SCRIPT_DIR=%~dp0
cd /d "%SCRIPT_DIR%.."

if "%1"=="--rebuild" goto do_build
if exist "pointer_v\dist\PointerV\PointerV.exe" (
    echo [1/4] Found existing PyInstaller bundle at pointer_v\dist\PointerV\PointerV.exe.
    goto check_iscc
)

:do_build
echo [1/4] Running PyInstaller build for Pointer V...
cd pointer_v
call build_exe.bat
if %errorlevel% neq 0 (
    echo [ERROR] PyInstaller build failed! Aborting installer build.
    cd /d "%SCRIPT_DIR%"
    exit /b 1
)
cd /d "%SCRIPT_DIR%"

:check_iscc
cd /d "%SCRIPT_DIR%"
echo.
echo [2/4] Locating Inno Setup Compiler ISCC.exe...
set "ISCC_CMD="

where iscc >nul 2>&1
if %errorlevel% equ 0 (
    set "ISCC_CMD=iscc"
) else if exist "C:\Program Files (x86)\Inno Setup 6\iscc.exe" (
    set "ISCC_CMD=C:\Program Files (x86)\Inno Setup 6\iscc.exe"
) else if exist "C:\Program Files\Inno Setup 6\iscc.exe" (
    set "ISCC_CMD=C:\Program Files\Inno Setup 6\iscc.exe"
) else if exist "%LOCALAPPDATA%\Programs\Inno Setup 6\iscc.exe" (
    set "ISCC_CMD=%LOCALAPPDATA%\Programs\Inno Setup 6\iscc.exe"
)

if not defined ISCC_CMD (
    echo.
    echo ======================================================================
    echo [ERROR] Inno Setup 6 ISCC.exe was not found on your system!
    echo.
    echo To build the Windows installer package:
    echo   1. Download Inno Setup from: https://jrsoftware.org/isdl.php
    echo   2. Run the installer and ensure ISCC is installed.
    echo   3. Either add Inno Setup to your PATH or install to default location.
    echo ======================================================================
    echo.
    exit /b 1
)

echo Found Inno Setup Compiler: "!ISCC_CMD!"
echo.
echo [3/4] Compiling Windows Installer with Inno Setup...
if not exist "Output" mkdir "Output"
"!ISCC_CMD!" "PointerV.iss"
if %errorlevel% neq 0 (
    echo [ERROR] Inno Setup compilation failed!
    exit /b 1
)

echo.
echo [4/4] Generating SHA-256 Checksums...
if exist "Output\PointerV-Setup-2.0.0.exe" (
    echo Computing SHA256 for Output\PointerV-Setup-2.0.0.exe...
    certutil -hashfile "Output\PointerV-Setup-2.0.0.exe" SHA256 | findstr /V ":" > "Output\PointerV-Setup-2.0.0.exe.sha256"
    echo Checksum saved to Output\PointerV-Setup-2.0.0.exe.sha256
    type "Output\PointerV-Setup-2.0.0.exe.sha256"
)

echo.
echo ========================================================
echo Build Succeeded! Installer generated in:
echo   installers\Output\PointerV-Setup-2.0.0.exe
echo ========================================================
endlocal
