@echo off
setlocal

echo ========================================================
echo    POINTER V - STANDALONE EXECUTABLE BUILDER (v2.0.5)
echo ========================================================
echo.

set "PY_CMD="
if exist "%~dp0..\.venv\Scripts\python.exe" (
    set "PY_CMD=%~dp0..\.venv\Scripts\python.exe"
) else (
    where py >nul 2>&1
    if %errorlevel% equ 0 (
        set "PY_CMD=py -3.12"
    ) else (
        where python >nul 2>&1
        if %errorlevel% equ 0 (
            set "PY_CMD=python"
        ) else if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" (
            set "PY_CMD=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
        )
    )
)

if "%PY_CMD%" == "" (
    echo [ERROR] Python 3.12 is not found in PATH.
    exit /b 1
)

echo [GATE 1/3] Running Static Analysis and Automated Tests...
echo --- 1a. Compiling Python bytecode...
"%PY_CMD%" -m compileall .
if %errorlevel% neq 0 (
    echo [ERROR] python -m compileall failed. Aborting build.
    exit /b 1
)

echo --- 1b. Checking static analysis (ruff)...
"%PY_CMD%" -m ruff check . --config ..\ruff.toml
if %errorlevel% neq 0 (
    echo [ERROR] Ruff lint checks failed. Aborting build.
    exit /b 1
)

echo --- 1c. Running full automated test suite (pytest)...
pushd ..
"%PY_CMD%" -m pytest tests -q
if errorlevel 1 (
    popd
    echo [ERROR] Pytest test suite failed. Aborting build.
    exit /b 1
)
popd
echo [GATE 1 PASSED] Static checks and unit/smoke tests all passed cleanly.

echo.
echo [GATE 2/3] Building standalone onedir bundle with PyInstaller...
"%PY_CMD%" -m PyInstaller --clean --noconfirm PointerV.spec
if %errorlevel% neq 0 (
    echo [ERROR] PyInstaller compilation failed.
    exit /b 1
)
echo [GATE 2 PASSED] PyInstaller onedir bundle built in dist\PointerV\.

echo.
echo [GATE 3/3] Running Startup Self-Test Gate on built executable...
dist\PointerV\PointerV.exe --selftest
if %errorlevel% neq 0 (
    echo [ERROR] Built dist\PointerV\PointerV.exe failed startup self-test.
    exit /b 1
)
echo [GATE 3 PASSED] dist\PointerV\PointerV.exe verified alive and functional.

echo.
echo ========================================================
echo Build Succeeded and Passed All Quality Gates
echo Output: dist\PointerV\PointerV.exe
echo ========================================================
endlocal
