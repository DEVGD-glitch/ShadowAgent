@echo off
setlocal enabledelayedexpansion
REM ═══════════════════════════════════════════════════════════════
REM Shadow Agent — Prerequisite Checker for Windows
REM
REM Works from ANY directory — auto-finds the project root.
REM ═══════════════════════════════════════════════════════════════

echo.
echo ================================================================
echo   Shadow Agent - Windows Prerequisites Check
echo ================================================================
echo.

REM ─── Auto-detect project root ─────────────────────────────────
set "SCRIPT_DIR=%~dp0"
set "PROJECT_DIR="

REM Method 1: Check current directory
if exist "package.json" if exist "src\app" (
    set "PROJECT_DIR=%cd%"
    goto :found_root
)

REM Method 2: Check relative to script (scripts/ subdirectory)
if exist "%SCRIPT_DIR%..\package.json" if exist "%SCRIPT_DIR%..\src\app" (
    set "PROJECT_DIR=%SCRIPT_DIR%.."
    goto :found_root
)

REM Method 3: Look for package.json with src-tauri
if exist "package.json" if exist "src-tauri" (
    set "PROJECT_DIR=%cd%"
    goto :found_root
)

REM Method 4: Parent of script dir
if exist "%SCRIPT_DIR%..\package.json" if exist "%SCRIPT_DIR%..\src-tauri" (
    set "PROJECT_DIR=%SCRIPT_DIR%.."
    goto :found_root
)

echo   ERROR: Cannot find Shadow Agent project root!
echo.
echo   Make sure you are in the project folder that contains:
echo     - package.json
echo     - src\app\
echo     - src-tauri\
echo.
echo   Try:
echo     cd /d "%USERPROFILE%\Downloads\ShadowAgent"
echo     scripts\check-prerequisites.bat
echo.
pause
exit /b 1

:found_root
REM Convert to absolute path
pushd "%PROJECT_DIR%"
set "PROJECT_DIR=%cd%"
popd

echo   Project found: %PROJECT_DIR%
echo.

set "ALL_OK=1"

REM ─── Rust ───────────────────────────────────────────────────
echo [Checking Rust...]
where rustc >nul 2>&1
if %errorlevel% neq 0 (
    echo   [MISSING] Rust not found
    echo   Install: https://rustup.rs
    echo   Command: winget install Rustlang.Rustup
    set "ALL_OK=0"
) else (
    for /f "tokens=*" %%v in ('rustc --version 2^>nul') do echo   [OK] %%v
)

where cargo >nul 2>&1
if %errorlevel% neq 0 (
    echo   [MISSING] Cargo not found
    echo   Install Rust from https://rustup.rs
    set "ALL_OK=0"
) else (
    for /f "tokens=*" %%v in ('cargo --version 2^>nul') do echo   [OK] %%v
)

echo.

REM ─── Node.js & Bun ──────────────────────────────────────────
echo [Checking Node.js & Bun...]
where node >nul 2>&1
if %errorlevel% neq 0 (
    echo   [MISSING] Node.js not found
    echo   Install: https://nodejs.org
    echo   Command: winget install OpenJS.NodeJS.LTS
    set "ALL_OK=0"
) else (
    for /f "tokens=*" %%v in ('node --version 2^>nul') do echo   [OK] node %%v
)

where bun >nul 2>&1
if %errorlevel% neq 0 (
    echo   [MISSING] Bun not found
    echo   Install: https://bun.sh
    echo   Command: powershell -c "irm bun.sh/install.ps1 ^| iex"
    set "ALL_OK=0"
) else (
    for /f "tokens=*" %%v in ('bun --version 2^>nul') do echo   [OK] bun %%v
)

echo.

REM ─── Python ──────────────────────────────────────────────────
echo [Checking Python...]
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo   [MISSING] Python not found
    echo   Install: https://python.org
    echo   Command: winget install Python.Python.3.12
    echo   IMPORTANT: Check "Add Python to PATH" during install!
    set "ALL_OK=0"
) else (
    for /f "tokens=*" %%v in ('python --version 2^>nul') do echo   [OK] %%v
    python -c "import sys; exit(0 if sys.version_info >= (3, 10) else 1)" 2>nul
    if %errorlevel% neq 0 (
        echo   [WARN] Python 3.10+ required, found older version
        set "ALL_OK=0"
    )
)

where pip >nul 2>&1
if %errorlevel% neq 0 (
    echo   [MISSING] pip not found
    echo   Install: python -m ensurepip
    set "ALL_OK=0"
) else (
    for /f "tokens=*" %%v in ('pip --version 2^>nul') do echo   [OK] %%v
)

where pyinstaller >nul 2>&1
if %errorlevel% neq 0 (
    echo   [MISSING] PyInstaller not found
    echo   Install: pip install pyinstaller
    set "ALL_OK=0"
) else (
    for /f "tokens=*" %%v in ('pyinstaller --version 2^>nul') do echo   [OK] PyInstaller %%v
)

echo.

REM ─── Visual Studio Build Tools ───────────────────────────────
echo [Checking Visual Studio Build Tools...]
set "VS_FOUND=0"
if exist "C:\Program Files\Microsoft Visual Studio\2022\BuildTools" set "VS_FOUND=1"
if exist "C:\Program Files\Microsoft Visual Studio\2022\Community" set "VS_FOUND=1"
if exist "C:\Program Files\Microsoft Visual Studio\2022\Professional" set "VS_FOUND=1"
if exist "C:\Program Files\Microsoft Visual Studio\2022\Enterprise" set "VS_FOUND=1"
if exist "C:\Program Files (x86)\Microsoft Visual Studio\2019\BuildTools" set "VS_FOUND=1"
if exist "C:\Program Files (x86)\Microsoft Visual Studio\2019\Community" set "VS_FOUND=1"

if "%VS_FOUND%"=="1" (
    echo   [OK] Visual Studio Build Tools found
) else (
    echo   [MISSING] Visual Studio Build Tools not found
    echo   Install: https://visualstudio.microsoft.com/visual-cpp-build-tools/
    echo   Command: winget install Microsoft.VisualStudio.2022.BuildTools
    echo   IMPORTANT: Select "Desktop development with C++" workload!
    set "ALL_OK=0"
)

echo.

REM ─── Project Files ──────────────────────────────────────────
echo [Checking Project Files...]

if exist "%PROJECT_DIR%\package.json" (
    echo   [OK] package.json found
) else (
    echo   [MISSING] package.json
    set "ALL_OK=0"
)

if exist "%PROJECT_DIR%\src-tauri\tauri.conf.json" (
    echo   [OK] Tauri config found
) else (
    echo   [MISSING] src-tauri\tauri.conf.json
    set "ALL_OK=0"
)

if exist "%PROJECT_DIR%\src\app" (
    echo   [OK] Next.js source found
) else (
    echo   [MISSING] src\app - Next.js source not found
    set "ALL_OK=0"
)

if exist "%PROJECT_DIR%\upload\GenericAgent-v1.2.0\server.py" (
    echo   [OK] Python backend found
) else (
    echo   [WARN] Python backend not found at upload\GenericAgent-v1.2.0\
    echo          Sidecar build will be skipped. That's OK if you only want the frontend.
)

if exist "%PROJECT_DIR%\src-tauri\binaries\launch_backend.py" (
    echo   [OK] Sidecar launcher found
) else (
    echo   [MISSING] src-tauri\binaries\launch_backend.py
)

echo.

REM ─── Result ──────────────────────────────────────────────────
if "%ALL_OK%"=="1" (
    echo ================================================================
    echo   ALL PREREQUISITES MET!
    echo.
    echo   Project: %PROJECT_DIR%
    echo.
    echo   You can now build the app:
    echo     cd /d "%PROJECT_DIR%"
    echo     scripts\build-exe.bat
    echo ================================================================
) else (
    echo ================================================================
    echo   SOME PREREQUISITES ARE MISSING
    echo.
    echo   Project: %PROJECT_DIR%
    echo.
    echo   Install the items marked [MISSING] above, then re-run this script.
    echo   See BUILD_GUIDE.md for detailed installation instructions.
    echo ================================================================
)

echo.
pause
