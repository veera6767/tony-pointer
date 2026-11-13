@echo off
setlocal

echo ========================================================
echo    POINTER V - INNO SETUP INSTALLER BUILDER (v2.0.4)
echo ========================================================
echo.

set SCRIPT_DIR=%~dp0
cd /d "%SCRIPT_DIR%.."

echo [GATE 1/5, 2/5, 3/5] Running PyInstaller build with quality gates...
cd pointer_v
call build_exe.bat
if errorlevel 1 (
    echo [ERROR] PyInstaller and Pre-Build Gates failed. Aborting installer build.
    cd /d "%SCRIPT_DIR%"
    exit /b 1
)
cd /d "%SCRIPT_DIR%"

echo.
echo [GATE 4/5] Locating Inno Setup Compiler and Compiling Windows Installer...
set "ISCC_CMD="
where iscc >nul 2>&1
if "%errorlevel%"=="0" (
    set "ISCC_CMD=iscc"
) else if exist "C:\Program Files (x86)\Inno Setup 6\iscc.exe" (
    set "ISCC_CMD=C:\Program Files (x86)\Inno Setup 6\iscc.exe"
) else if exist "C:\Program Files\Inno Setup 6\iscc.exe" (
    set "ISCC_CMD=C:\Program Files\Inno Setup 6\iscc.exe"
) else if exist "%LOCALAPPDATA%\Programs\Inno Setup 6\iscc.exe" (
    set "ISCC_CMD=%LOCALAPPDATA%\Programs\Inno Setup 6\iscc.exe"
)

if not defined ISCC_CMD (
    echo [ERROR] Inno Setup 6 ISCC.exe was not found on your system.
    exit /b 1
)

echo Found Inno Setup Compiler: "%ISCC_CMD%"
if not exist "Output" mkdir "Output"
"%ISCC_CMD%" "PointerV.iss"
if errorlevel 1 (
    echo [ERROR] Inno Setup compilation failed.
    exit /b 1
)
echo [GATE 4 PASSED] Output\PointerV-Setup-2.0.4.exe compiled successfully.

echo.
echo [GATE 5/5] Silent Installation and Installed Binary Self-Test Gate...
set "TEMP_INSTALL_DIR=%TEMP%\PointerV_TestInstall_%RANDOM%"
echo Installing temporarily to: %TEMP_INSTALL_DIR%...
"Output\PointerV-Setup-2.0.4.exe" /VERYSILENT /SUPPRESSMSGBOXES /NORESTART /DIR="%TEMP_INSTALL_DIR%"
if errorlevel 1 (
    echo [ERROR] Silent test installation failed.
    exit /b 1
)

echo Verifying installed binary at: %TEMP_INSTALL_DIR%\PointerV.exe...
"%TEMP_INSTALL_DIR%\PointerV.exe" --selftest
if errorlevel 1 (
    echo [ERROR] Installed PointerV.exe failed startup self-test.
    if exist "%TEMP_INSTALL_DIR%\unins000.exe" "%TEMP_INSTALL_DIR%\unins000.exe" /VERYSILENT /SUPPRESSMSGBOXES /NORESTART
    exit /b 1
)
echo Installed binary passed startup self-test.

echo Cleaning up test installation...
if exist "%TEMP_INSTALL_DIR%\unins000.exe" (
    "%TEMP_INSTALL_DIR%\unins000.exe" /VERYSILENT /SUPPRESSMSGBOXES /NORESTART
    timeout /t 2 /nobreak >nul
)
if exist "%TEMP_INSTALL_DIR%" rmdir /s /q "%TEMP_INSTALL_DIR%" 2>nul
echo [GATE 5 PASSED] Installed setup package verified functional and cleanly uninstalled.

echo.
echo ========================================================
echo Generating Checksums and Finalizing Share Package...
echo ========================================================
if exist "Output\PointerV-Setup-2.0.4.exe" (
    certutil -hashfile "Output\PointerV-Setup-2.0.4.exe" SHA256 | findstr /V ":" > "Output\PointerV-Setup-2.0.4.exe.sha256"
    echo Checksum saved to Output\PointerV-Setup-2.0.4.exe.sha256:
    type "Output\PointerV-Setup-2.0.4.exe.sha256"
    
    if not exist "..\share" mkdir "..\share"
    copy /y "Output\PointerV-Setup-2.0.4.exe" "..\share\PointerV-Setup-2.0.4.exe" >nul
    copy /y "Output\PointerV-Setup-2.0.4.exe.sha256" "..\share\PointerV-Setup-2.0.4.exe.sha256" >nul
    
    if exist "..\share\PointerV-Setup-2.0.3.exe" del /f /q "..\share\PointerV-Setup-2.0.3.exe"
    if exist "..\share\PointerV-Setup-2.0.3.exe.sha256" del /f /q "..\share\PointerV-Setup-2.0.3.exe.sha256"
    if exist "..\share\PointerV-Setup-2.0.2.exe" del /f /q "..\share\PointerV-Setup-2.0.2.exe"
    if exist "..\share\PointerV-Setup-2.0.2.exe.sha256" del /f /q "..\share\PointerV-Setup-2.0.2.exe.sha256"
    if exist "..\share\PointerV-Setup-2.0.1.exe" del /f /q "..\share\PointerV-Setup-2.0.1.exe"
    if exist "..\share\PointerV-Setup-2.0.1.exe.sha256" del /f /q "..\share\PointerV-Setup-2.0.1.exe.sha256"
    echo Copied verified installer and checksum to share\ folder.
)

echo.
echo ========================================================
echo All 5 Quality Gates Passed - v2.0.4 Package Ready!
echo ========================================================
endlocal
