@echo off
setlocal enabledelayedexpansion
REM ═══════════════════════════════════════════════════════════════
REM Shadow Agent — Build Sidecar Backend (Windows Batch Script v2)
REM
REM Packages the Python FastAPI backend as a standalone .exe using
REM PyInstaller, then copies it to src-tauri/binaries/ with the
REM correct Tauri target-triple naming convention.
REM
REM IMPORTANT: Run from project root!
REM   cd C:\path\to\ShadowAgent
REM   scripts\build-sidecar.bat
REM
REM Usage:
REM   scripts\build-sidecar.bat                  # Build for Windows
REM   scripts\build-sidecar.bat --clean          # Clean build artifacts first
REM   scripts\build-sidecar.bat --skip-deps      # Skip pip install
REM ═══════════════════════════════════════════════════════════════

echo.
echo ================================================================
echo   Shadow Agent - Sidecar Backend Builder v2
echo ================================================================
echo.

REM ─── Parse Arguments ─────────────────────────────────────────
set "CLEAN=0"
set "SKIP_DEPS=0"

:parse_args
if "%~1"=="" goto :done_parsing
if /i "%~1"=="--clean" set "CLEAN=1"
if /i "%~1"=="--skip-deps" set "SKIP_DEPS=1"
if /i "%~1"=="--help" goto :show_help
if /i "%~1"=="-h" goto :show_help
shift
goto :parse_args
:done_parsing

REM ─── Detect Project Root ─────────────────────────────────────
set "SCRIPT_DIR=%~dp0"

if exist "package.json" (
    set "PROJECT_DIR=%cd%"
) else if exist "%SCRIPT_DIR%..\package.json" (
    set "PROJECT_DIR=%SCRIPT_DIR%.."
) else (
    echo   ERROR: Cannot find project root ^(package.json not found^)
    echo   Run this script from the project root directory.
    goto :error_exit
)

pushd "%PROJECT_DIR%"
set "PROJECT_DIR=%cd%"
popd

REM ─── Set Key Paths ──────────────────────────────────────────
set "BACKEND_DIR=%PROJECT_DIR%\upload\GenericAgent-v1.0.0"
set "BINARIES_DIR=%PROJECT_DIR%\src-tauri\binaries"
set "LAUNCHER=%BINARIES_DIR%\launch_backend.py"
set "OUTPUT_FILE=%BINARIES_DIR%\backend-x86_64-pc-windows-msvc.exe"

echo   Project root: %PROJECT_DIR%
echo   Backend dir:  %BACKEND_DIR%
echo   Launcher:     %LAUNCHER%
echo.

REM ─── [1/6] Check Prerequisites ─────────────────────────────
echo [1/6] Checking prerequisites...

where python >nul 2>&1
if %errorlevel% neq 0 (
    echo   ERROR: Python not found. Install Python 3.10+ from https://python.org
    goto :error_exit
)

python -c "import sys; exit(0 if sys.version_info >= (3, 10) else 1)"
if %errorlevel% neq 0 (
    echo   ERROR: Python 3.10+ required. Found:
    python --version
    goto :error_exit
)

for /f "tokens=*" %%v in ('python --version') do echo   OK: %%v

where pip >nul 2>&1
if %errorlevel% neq 0 (
    echo   ERROR: pip not found. Install it: python -m ensurepip
    goto :error_exit
)
echo   OK: pip found

where pyinstaller >nul 2>&1
if %errorlevel% neq 0 (
    echo   Installing PyInstaller...
    pip install pyinstaller
    if %errorlevel% neq 0 (
        echo   ERROR: Failed to install PyInstaller
        goto :error_exit
    )
)
for /f "tokens=*" %%v in ('pyinstaller --version 2^>nul') do echo   OK: PyInstaller %%v

REM Check backend directory
if not exist "%BACKEND_DIR%\server.py" (
    echo   ERROR: Backend not found at: %BACKEND_DIR%
    echo.
    echo   The Python backend must be in: upload\GenericAgent-Desktop-v1.2.0\
    echo   Make sure you have the complete project with the backend directory.
    echo.
    echo   If the backend is elsewhere, set the BACKEND_DIR variable:
    echo     set BACKEND_DIR=C:\path\to\backend
    echo     scripts\build-sidecar.bat
    goto :error_exit
)
echo   OK: Backend directory found

REM Check launcher script
if not exist "%LAUNCHER%" (
    echo   ERROR: Launcher script not found: %LAUNCHER%
    echo   Make sure src-tauri\binaries\launch_backend.py exists.
    goto :error_exit
)
echo   OK: Launcher script found

echo.

REM ─── [2/6] Clean if requested ──────────────────────────────
if "%CLEAN%"=="1" (
    echo [2/6] Cleaning build artifacts...
    if exist "%BACKEND_DIR%\build" rmdir /s /q "%BACKEND_DIR%\build"
    if exist "%BACKEND_DIR%\dist" rmdir /s /q "%BACKEND_DIR%\dist"
    if exist "%BACKEND_DIR%\backend.spec" del /q "%BACKEND_DIR%\backend.spec"
    echo   OK: Cleaned
) else (
    echo [2/6] Skipping clean ^(use --clean to remove artifacts^)
)
echo.

REM ─── [3/6] Install Dependencies ────────────────────────────
if "%SKIP_DEPS%"=="0" (
    echo [3/6] Installing Python dependencies...

    pip install --quiet --upgrade pip 2>nul
    pip install --quiet pyinstaller 2>nul

    REM Install core dependencies
    pip install --quiet fastapi uvicorn pydantic httpx edge-tts
    if %errorlevel% neq 0 (
        echo   WARNING: Some core deps failed, continuing...
    )

    REM Install from requirements.txt if available
    if exist "%BACKEND_DIR%\requirements.txt" (
        pip install --quiet -r "%BACKEND_DIR%\requirements.txt"
        if %errorlevel% neq 0 (
            echo   WARNING: Some requirements.txt deps failed, continuing...
        )
    )

    REM Install from pyproject.toml extras
    pip install --quiet -e "%BACKEND_DIR%[server]" 2>nul

    echo   OK: Dependencies installed
) else (
    echo [3/6] Skipping dependency install ^(--skip-deps^)
)
echo.

REM ─── [4/6] Build with PyInstaller ──────────────────────────
echo [4/6] Building sidecar with PyInstaller...
echo   Entry point: %LAUNCHER%
echo   Working dir: %BACKEND_DIR%
echo.

pushd "%BACKEND_DIR%"

REM Check for assets/i18n directories (they may not exist)
set "PYINSTALLER_ADD_DATA="
if exist "assets" set "PYINSTALLER_ADD_DATA=%PYINSTALLER_ADD_DATA% --add-data assets;assets"
if exist "i18n" set "PYINSTALLER_ADD_DATA=%PYINSTALLER_ADD_DATA% --add-data i18n;i18n"
if exist "mcp_config.json" set "PYINSTALLER_ADD_DATA=%PYINSTALLER_ADD_DATA% --add-data mcp_config.json;."

pyinstaller --onefile ^
    --name "backend" ^
    --noconfirm ^
    --clean ^
    --console ^
    %PYINSTALLER_ADD_DATA% ^
    --hidden-import=uvicorn.logging ^
    --hidden-import=uvicorn.loops ^
    --hidden-import=uvicorn.loops.auto ^
    --hidden-import=uvicorn.protocols ^
    --hidden-import=uvicorn.protocols.http ^
    --hidden-import=uvicorn.protocols.http.auto ^
    --hidden-import=uvicorn.protocols.websockets ^
    --hidden-import=uvicorn.protocols.websockets.auto ^
    --hidden-import=uvicorn.lifespan ^
    --hidden-import=uvicorn.lifespan.on ^
    --hidden-import=agentmain ^
    --hidden-import=agentmain.core ^
    --hidden-import=llmcore ^
    --hidden-import=llmcore.clients ^
    --hidden-import=llmcore.sessions ^
    --collect-all edge_tts ^
    --collect-all httpx ^
    "%LAUNCHER%"

if %errorlevel% neq 0 (
    popd
    echo.
    echo   ERROR: PyInstaller build failed
    echo.
    echo   Common fixes:
    echo     1. Install missing packages: pip install fastapi uvicorn pydantic
    echo     2. Check that agentmain/ and llmcore/ exist in %BACKEND_DIR%
    echo     3. Try with --hidden-import for any missing module
    goto :error_exit
)

popd
echo   OK: PyInstaller build succeeded
echo.

REM ─── [5/6] Copy to binaries directory ──────────────────────
echo [5/6] Copying binary to Tauri binaries directory...

if not exist "%BINARIES_DIR%" mkdir "%BINARIES_DIR%"

if not exist "%BACKEND_DIR%\dist\backend.exe" (
    echo   ERROR: backend.exe not found in %BACKEND_DIR%\dist\
    echo   PyInstaller may have failed silently. Check the output above.
    goto :error_exit
)

copy /y "%BACKEND_DIR%\dist\backend.exe" "%OUTPUT_FILE%"
if %errorlevel% neq 0 (
    echo   ERROR: Failed to copy backend.exe
    goto :error_exit
)

echo   OK: Copied: backend-x86_64-pc-windows-msvc.exe
echo.

REM ─── [6/6] Verify output ──────────────────────────────────
echo [6/6] Verifying output...

if exist "%OUTPUT_FILE%" (
    for %%f in ("%OUTPUT_FILE%") do (
        set "FILE_SIZE=%%~zf"
        echo   OK: Output: %OUTPUT_FILE%
        echo   OK: Size: !FILE_SIZE! bytes
    )
) else (
    echo   ERROR: Output file not found: %OUTPUT_FILE%
    goto :error_exit
)

REM ─── Done ───────────────────────────────────────────────────
echo.
echo ================================================================
echo   Sidecar build complete!
echo.
echo   Target:  Windows ^(x86_64-pc-windows-msvc^)
echo   Output:  %OUTPUT_FILE%
echo   Size:    !FILE_SIZE! bytes
echo.
echo   Next step: Run "scripts\build-exe.bat --skip-sidecar"
echo   Or full build: "scripts\build-exe.bat"
echo ================================================================
echo.
goto :eof

REM ─── Help ───────────────────────────────────────────────────
:show_help
echo Usage: scripts\build-sidecar.bat [OPTIONS]
echo.
echo Options:
echo   --clean       Remove build artifacts before building
echo   --skip-deps   Skip pip install of requirements
echo   --help        Show this help message
echo.
echo Note: Run from the project root directory!
echo.
goto :eof

REM ─── Error Exit ────────────────────────────────────────────
:error_exit
echo.
echo   Build FAILED. Check the errors above.
endlocal
exit /b 1
