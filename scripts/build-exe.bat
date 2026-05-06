@echo off
setlocal enabledelayedexpansion
REM ═══════════════════════════════════════════════════════════════
REM GenericAgent — Windows Desktop Build Script (v6)
REM
REM Changes from v5:
REM   - Auto-detect backend dir (upload\GenericAgent-v1.2.0 OR backend\)
REM   - Copy final exe to project root for easy access
REM   - Show clear instructions after build
REM   - Add --skip-tauri flag for sidecar-only build
REM   - Better error messages for common issues
REM
REM Usage:
REM   scripts\build-exe.bat                    # Build complet
REM   scripts\build-exe.bat --skip-sidecar     # Skip PyInstaller
REM   scripts\build-exe.bat --skip-frontend    # Skip Next.js build
REM   scripts\build-exe.bat --skip-tauri       # Skip Tauri (sidecar only)
REM   scripts\build-exe.bat --dev              # Mode developpement
REM   scripts\build-exe.bat --clean            # Nettoyer avant build
REM ═══════════════════════════════════════════════════════════════

echo.
echo ================================================================
echo   GenericAgent - Windows Desktop Builder v6
echo ================================================================
echo.

REM ─── Parse Arguments ─────────────────────────────────────────
set "SKIP_SIDECAR=0"
set "SKIP_FRONTEND=0"
set "SKIP_TAURI=0"
set "DEV_MODE=0"
set "CLEAN=0"

:parse_args
if "%~1"=="" goto :done_parsing
if /i "%~1"=="--skip-sidecar" set "SKIP_SIDECAR=1"
if /i "%~1"=="--skip-frontend" set "SKIP_FRONTEND=1"
if /i "%~1"=="--skip-tauri" set "SKIP_TAURI=1"
if /i "%~1"=="--dev" set "DEV_MODE=1"
if /i "%~1"=="--clean" set "CLEAN=1"
if /i "%~1"=="--help" goto :show_help
if /i "%~1"=="-h" goto :show_help
shift
goto :parse_args
:done_parsing

REM ═══════════════════════════════════════════════════════════════
REM AUTO-DETECT PROJECT ROOT — works from any directory!
REM ═══════════════════════════════════════════════════════════════
set "SCRIPT_DIR=%~dp0"
set "PROJECT_DIR="

REM Method 1: Current directory has package.json + src-tauri
if exist "package.json" if exist "src-tauri" (
    set "PROJECT_DIR=%cd%"
    goto :found_root
)

REM Method 2: Script is inside project/scripts/
if exist "%SCRIPT_DIR%..\package.json" if exist "%SCRIPT_DIR%..\src-tauri" (
    set "PROJECT_DIR=%SCRIPT_DIR%.."
    goto :found_root
)

REM Method 3: Current directory has package.json + src/app
if exist "package.json" if exist "src\app" (
    set "PROJECT_DIR=%cd%"
    goto :found_root
)

REM Method 4: Script parent has package.json + src/app
if exist "%SCRIPT_DIR%..\package.json" if exist "%SCRIPT_DIR%..\src\app" (
    set "PROJECT_DIR=%SCRIPT_DIR%.."
    goto :found_root
)

echo   ERROR: Cannot find GenericAgent project root!
echo.
echo   Could not find package.json and src-tauri/ in:
echo     Current dir:  %cd%
echo     Script dir:   %SCRIPT_DIR%
echo.
echo   Please cd to the project folder first:
echo     cd /d "%USERPROFILE%\Downloads\GenericAgent-Desktop-v1.2.0"
echo     scripts\build-exe.bat
echo.
pause
exit /b 1

:found_root
REM Convert to absolute path and CD into it
pushd "%PROJECT_DIR%"
set "PROJECT_DIR=%cd%"
popd

echo   Project root: %PROJECT_DIR%
echo.

REM ─── Auto-Detect Backend Directory ───────────────────────────
set "BACKEND_DIR="

REM Check 1: upload\GenericAgent-v1.0.0 (standard location)
if exist "%PROJECT_DIR%\upload\GenericAgent-v1.0.0\server.py" (
    set "BACKEND_DIR=%PROJECT_DIR%\upload\GenericAgent-v1.0.0"
    echo   Backend found: upload\GenericAgent-v1.0.0
    goto :backend_found
)

REM Check 2: backend\ (alternative location)
if exist "%PROJECT_DIR%\backend\server.py" (
    set "BACKEND_DIR=%PROJECT_DIR%\backend"
    echo   Backend found: backend\
    goto :backend_found
)

REM Check 3: GenericAgent-v1.2.0\ (in project root)
if exist "%PROJECT_DIR%\GenericAgent-v1.2.0\server.py" (
    set "BACKEND_DIR=%PROJECT_DIR%\GenericAgent-v1.2.0"
    echo   Backend found: GenericAgent-v1.2.0\
    goto :backend_found
)

REM Check 4: Same directory as project root
if exist "%PROJECT_DIR%\server.py" (
    set "BACKEND_DIR=%PROJECT_DIR%"
    echo   Backend found: project root
    goto :backend_found
)

echo   WARNING: Backend source not found!
echo   Searched in:
echo     %PROJECT_DIR%\upload\GenericAgent-v1.0.0\
echo     %PROJECT_DIR%\backend\
echo.
echo   The sidecar will NOT be built. Use --skip-sidecar to suppress.
echo   The app will still work but without the Python backend.
echo.

:backend_found

set "BINARIES_DIR=%PROJECT_DIR%\src-tauri\binaries"
set "SIDECAR_ENTRY=%BINARIES_DIR%\sidecar_entry.py"
set "DIST_DIR=%PROJECT_DIR%\dist"

REM ═══════════════════════════════════════════════════════════════
REM CD TO PROJECT ROOT — all subsequent commands run from here
REM ═══════════════════════════════════════════════════════════════
cd /d "%PROJECT_DIR%"

REM ─── [0/6] Prerequisite Check ────────────────────────────────
echo [0/6] Checking prerequisites...
set "HAS_ERRORS=0"

where bun >nul 2>&1
if %errorlevel% neq 0 (
    echo   [MISSING] bun - Install from https://bun.sh
    set "HAS_ERRORS=1"
) else (
    for /f "tokens=*" %%v in ('bun --version 2^>nul') do echo   [OK] bun %%v
)

where node >nul 2>&1
if %errorlevel% neq 0 (
    echo   [MISSING] node - Install from https://nodejs.org
    set "HAS_ERRORS=1"
) else (
    for /f "tokens=*" %%v in ('node --version 2^>nul') do echo   [OK] node %%v
)

where npx >nul 2>&1
if %errorlevel% neq 0 (
    echo   [MISSING] npm/npx - Install Node.js from https://nodejs.org
    set "HAS_ERRORS=1"
) else (
    for /f "tokens=*" %%v in ('npx --version 2^>nul') do echo   [OK] npx %%v
)

where cargo >nul 2>&1
if %errorlevel% neq 0 (
    echo   [MISSING] cargo/rust - Install from https://rustup.rs
    set "HAS_ERRORS=1"
) else (
    for /f "tokens=*" %%v in ('rustc --version 2^>nul') do echo   [OK] %%v
)

if not defined BACKEND_DIR (
    echo   [SKIP] Python/PyInstaller - no backend source found
) else (
    where python >nul 2>&1
    if %errorlevel% neq 0 (
        echo   [MISSING] python - Install from https://python.org
        set "HAS_ERRORS=1"
    ) else (
        for /f "tokens=*" %%v in ('python --version 2^>nul') do echo   [OK] %%v
    )

    if "%SKIP_SIDECAR%"=="0" (
        where pyinstaller >nul 2>&1
        if %errorlevel% neq 0 (
            echo   [MISSING] pyinstaller - Run: pip install pyinstaller
            set "HAS_ERRORS=1"
        ) else (
            for /f "tokens=*" %%v in ('pyinstaller --version 2^>nul') do echo   [OK] PyInstaller %%v
        )
    )
)

if "%HAS_ERRORS%"=="1" (
    echo.
    echo   ERROR: Missing prerequisites. Install them first.
    echo.
    pause
    exit /b 1
)

echo   [OK] Project files found in %PROJECT_DIR%
echo.

REM ─── Clean if requested ──────────────────────────────────────
if "%CLEAN%"=="1" (
    echo [CLEAN] Removing build artifacts...
    if exist ".next" rmdir /s /q ".next" 2>nul
    if exist "out" rmdir /s /q "out" 2>nul
    if defined BACKEND_DIR (
        if exist "%BACKEND_DIR%\build" rmdir /s /q "%BACKEND_DIR%\build" 2>nul
        if exist "%BACKEND_DIR%\dist" rmdir /s /q "%BACKEND_DIR%\dist" 2>nul
        if exist "%BACKEND_DIR%\backend.spec" del /q "%BACKEND_DIR%\backend.spec" 2>nul
    )
    if exist "src-tauri\target" rmdir /s /q "src-tauri\target" 2>nul
    echo   Cleaned.
    echo.
)

REM ═══════════════════════════════════════════════════════════════
REM [1/5] Install Node.js dependencies
REM ═══════════════════════════════════════════════════════════════
echo [1/5] Installing Node.js dependencies...
call bun install
if %errorlevel% neq 0 (
    echo   ERROR: bun install failed
    pause
    exit /b 1
)
echo   OK: Dependencies installed
echo.

REM ═══════════════════════════════════════════════════════════════
REM [2/5] Build Next.js frontend (static export → /out)
REM ═══════════════════════════════════════════════════════════════
if "%SKIP_FRONTEND%"=="1" (
    echo [2/5] Skipping frontend build ^(--skip-frontend^)
    echo.
) else (
    echo [2/5] Building Next.js frontend...
    call bun run build
    if %errorlevel% neq 0 (
        echo   ERROR: Next.js build failed
        pause
        exit /b 1
    )

    REM Verify static export
    if not exist "out\index.html" (
        echo   ERROR: Static export not found at out\index.html
        echo   Check that next.config.ts has: output: "export"
        pause
        exit /b 1
    )
    echo   OK: Frontend built ^(out\index.html created^)
    echo.
)

REM ═══════════════════════════════════════════════════════════════
REM [3/5] Build Python sidecar with PyInstaller
REM ═══════════════════════════════════════════════════════════════
if "%SKIP_SIDECAR%"=="1" (
    echo [3/5] Skipping sidecar build ^(--skip-sidecar^)
    echo.
) else if not defined BACKEND_DIR (
    echo [3/5] No backend source found - skipping sidecar build
    echo   The app will work but without the Python backend.
    echo.
) else if not exist "%SIDECAR_ENTRY%" (
    echo [3/5] Sidecar entry point not found at %SIDECAR_ENTRY%
    echo   ERROR: Missing src-tauri\binaries\sidecar_entry.py
    pause
    exit /b 1
) else (
    echo [3/5] Building Python sidecar with PyInstaller...
    echo   Backend dir:  %BACKEND_DIR%
    echo   Entry point:  %SIDECAR_ENTRY%
    echo.

    REM Install core Python dependencies (skip heavy ones)
    echo   Installing core Python dependencies...
    pip install --quiet fastapi uvicorn pydantic httpx edge-tts websockets anyio certifi 2>nul

    REM Build with PyInstaller from the backend directory
    pushd "%BACKEND_DIR%"

    REM ── Build the --add-data list ──────────────────────────────
    echo   Collecting backend source files...

    set "ADD_DATA="

    REM Core Python packages (directories with __init__.py)
    for %%d in (agentmain llmcore engine memory plugins tools reflect mcp protocols) do (
        if exist "%%d" (
            set "ADD_DATA=!ADD_DATA! --add-data %%d;%%d"
        )
    )

    REM Core .py files in the backend root
    for %%f in (server.py config.py agent_loop.py circuit_breaker.py env_loader.py exceptions.py logging_config.py metrics.py protocols.py) do (
        if exist "%%f" (
            set "ADD_DATA=!ADD_DATA! --add-data %%f;."
        )
    )

    REM Assets and i18n directories
    if exist "assets" set "ADD_DATA=!ADD_DATA! --add-data assets;assets"
    if exist "i18n" set "ADD_DATA=!ADD_DATA! --add-data i18n;i18n"
    if exist "mcp_config.json" set "ADD_DATA=!ADD_DATA! --add-data mcp_config.json;."

    echo   Files to bundle: !ADD_DATA!
    echo.

    REM ── Run PyInstaller ───────────────────────────────────────
    pyinstaller --onefile ^
        --name "backend" ^
        --noconfirm ^
        --clean ^
        --console ^
        !ADD_DATA! ^
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
        --hidden-import=anyio ^
        --hidden-import=anyio._backends ^
        --hidden-import=anyio._backends._asyncio ^
        --hidden-import=httpx ^
        --hidden-import=pydantic ^
        --hidden-import=edge_tts ^
        --hidden-import=websockets ^
        --collect-all edge_tts ^
        --collect-all httpx ^
        "%SIDECAR_ENTRY%"

    if %errorlevel% neq 0 (
        popd
        echo   ERROR: PyInstaller build failed
        echo.
        echo   Common fixes:
        echo     1. pip install fastapi uvicorn pydantic httpx edge-tts
        echo     2. Check %BACKEND_DIR% has server.py, agentmain/, llmcore/
        echo     3. Try: --skip-sidecar to build without backend
        pause
        exit /b 1
    )

    REM Copy sidecar to Tauri binaries directory
    if not exist "%BINARIES_DIR%" mkdir "%BINARIES_DIR%"
    copy /y "dist\backend.exe" "%BINARIES_DIR%\backend-x86_64-pc-windows-msvc.exe" >nul
    if %errorlevel% neq 0 (
        popd
        echo   ERROR: Failed to copy backend.exe to binaries dir
        pause
        exit /b 1
    )

    popd

    REM Verify
    if exist "%BINARIES_DIR%\backend-x86_64-pc-windows-msvc.exe" (
        for %%f in ("%BINARIES_DIR%\backend-x86_64-pc-windows-msvc.exe") do echo   OK: Sidecar built ^(%%~zf bytes^)
    ) else (
        echo   ERROR: Sidecar binary not found after build
        pause
        exit /b 1
    )
    echo.
)

REM ═══════════════════════════════════════════════════════════════
REM [4/5] Build Tauri desktop app
REM ═══════════════════════════════════════════════════════════════
if "%SKIP_TAURI%"=="1" (
    echo [4/5] Skipping Tauri build ^(--skip-tauri^)
    echo.
    goto :collect_output
)

if "%DEV_MODE%"=="1" (
    echo [4/5] Starting Tauri in DEV mode...
    call npx tauri dev
    goto :eof
)

echo [4/5] Building Tauri desktop app...
echo   This may take 5-15 minutes on first build...
echo.

REM Ensure Rust target is installed
rustup target add x86_64-pc-windows-msvc >nul 2>&1

REM IMPORTANT: beforeBuildCommand is empty in tauri.conf.json
REM Frontend is already built in step [2/5].
call npx tauri build
if %errorlevel% neq 0 (
    echo.
    echo   ERROR: Tauri build failed
    echo.
    echo   Common fixes:
    echo     1. Install Rust: https://rustup.rs
    echo     2. Install VS Build Tools with "Desktop C++"
    echo     3. Make sure out\ directory exists
    echo     4. Check src-tauri\tauri.conf.json
    echo.
    pause
    exit /b 1
)
echo   OK: Tauri app built
echo.

REM ═══════════════════════════════════════════════════════════════
REM [5/5] Collect output files
REM ═══════════════════════════════════════════════════════════════
:collect_output
echo [5/5] Collecting output files...

if not exist "%DIST_DIR%" mkdir "%DIST_DIR%"

set "FOUND_OUTPUT=0"

REM Copy NSIS installer
for %%f in ("src-tauri\target\release\bundle\nsis\*.exe") do (
    copy /y "%%f" "%DIST_DIR%\" >nul
    echo   OK: %%~nxf
    set "FOUND_OUTPUT=1"
)

REM Copy MSI installer
for %%f in ("src-tauri\target\release\bundle\msi\*.msi") do (
    copy /y "%%f" "%DIST_DIR%\" >nul
    echo   OK: %%~nxf
    set "FOUND_OUTPUT=1"
)

REM Copy portable exe
if exist "src-tauri\target\release\GenericAgent.exe" (
    copy /y "src-tauri\target\release\GenericAgent.exe" "%DIST_DIR%\" >nul
    echo   OK: GenericAgent.exe ^(portable^)
    set "FOUND_OUTPUT=1"
)

REM ALSO copy to project root for easy access
if exist "src-tauri\target\release\GenericAgent.exe" (
    copy /y "src-tauri\target\release\GenericAgent.exe" "%PROJECT_DIR%\GenericAgent.exe" >nul
    echo   OK: GenericAgent.exe copied to project root
)

if "%FOUND_OUTPUT%"=="0" (
    echo   WARNING: No output files found!
    echo   Check src-tauri\target\release\bundle\ for build results
)

echo.

REM ─── Summary ─────────────────────────────────────────────────
echo ================================================================
echo   BUILD COMPLETE!
echo.
echo   Output: %DIST_DIR%\
echo.

for %%f in ("%DIST_DIR%\*.exe") do echo   %%~nxf  ^(%%~zf bytes^)
for %%f in ("%DIST_DIR%\*.msi") do echo   %%~nxf  ^(%%~zf bytes^)

echo.
echo   HOW TO RUN THE APP:
echo.
echo   Option 1 - NSIS Installer ^(recommended^):
echo     1. Double-click: %DIST_DIR%\GenericAgent_xxx_x64-setup.exe
echo     2. Follow the installation wizard
echo     3. Find "GenericAgent" in your Start Menu or Desktop
echo.
echo   Option 2 - Portable EXE:
echo     1. Double-click: %PROJECT_DIR%\GenericAgent.exe
echo     2. Or run in PowerShell: .\GenericAgent.exe
echo        (NOTE: PowerShell requires .\ prefix!)
echo.
echo   Option 3 - Debug mode:
echo     1. Run: scripts\debug-launch.bat
echo     2. This shows console output for troubleshooting
echo.
echo   NOTE: The backend sidecar starts automatically when the
echo         app launches. Wait 3-5 seconds for it to initialize.
echo.
echo   TROUBLESHOOTING:
echo     - App doesn't open? Run: scripts\debug-launch.bat
echo     - Check logs at: %%APPDATA%%\com.genericagent.desktop\logs\
echo     - Missing WebView2? Install from: https://developer.microsoft.com/microsoft-edge/webview2/
echo ================================================================
echo.
pause
goto :eof

REM ─── Help ────────────────────────────────────────────────────
:show_help
echo Usage: scripts\build-exe.bat [OPTIONS]
echo.
echo Options:
echo   --skip-sidecar    Skip PyInstaller sidecar build
echo   --skip-frontend   Skip Next.js frontend build
echo   --skip-tauri      Skip Tauri build (sidecar only)
echo   --dev             Start Tauri in dev mode instead of building
echo   --clean           Remove build artifacts before building
echo   --help            Show this help message
echo.
echo Note: Script auto-detects the project root directory.
echo.
goto :eof
