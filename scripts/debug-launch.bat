@echo off
REM ═══════════════════════════════════════════════════════════════
REM GenericAgent — Debug Launch Script
REM
REM This script launches GenericAgent with full console output
REM visible, making it easy to diagnose startup issues.
REM
REM Usage:  scripts\debug-launch.bat
REM ═══════════════════════════════════════════════════════════════

echo.
echo ================================================================
echo   GenericAgent - Debug Launch
echo ================================================================
echo.

REM ─── Find the project root ───────────────────────────────────
set "SCRIPT_DIR=%~dp0"
set "PROJECT_DIR="

if exist "package.json" if exist "src-tauri" (
    set "PROJECT_DIR=%cd%"
    goto :found
)
if exist "%SCRIPT_DIR%..\package.json" if exist "%SCRIPT_DIR%..\src-tauri" (
    set "PROJECT_DIR=%SCRIPT_DIR%.."
    goto :found
)

echo ERROR: Cannot find GenericAgent project root!
echo Please run this script from the project directory.
pause
exit /b 1

:found
pushd "%PROJECT_DIR%"
set "PROJECT_DIR=%cd%"
popd

cd /d "%PROJECT_DIR%"

echo   Project: %PROJECT_DIR%
echo.

REM ─── Check if the exe exists ────────────────────────────────
set "EXE_PATH="

if exist "%PROJECT_DIR%\GenericAgent.exe" (
    set "EXE_PATH=%PROJECT_DIR%\GenericAgent.exe"
    echo   [OK] Found: GenericAgent.exe ^(project root^)
) else if exist "%PROJECT_DIR%\dist\GenericAgent.exe" (
    set "EXE_PATH=%PROJECT_DIR%\dist\GenericAgent.exe"
    echo   [OK] Found: dist\GenericAgent.exe
) else if exist "%PROJECT_DIR%\src-tauri\target\release\GenericAgent.exe" (
    set "EXE_PATH=%PROJECT_DIR%\src-tauri\target\release\GenericAgent.exe"
    echo   [OK] Found: src-tauri\target\release\GenericAgent.exe
) else (
    echo   [ERROR] GenericAgent.exe not found!
    echo.
    echo   Have you built the app yet? Run: scripts\build-exe.bat
    echo.
    pause
    exit /b 1
)

REM ─── Check WebView2 ─────────────────────────────────────────
echo.
echo   Checking WebView2...
where /r "C:\Program Files (x86)\Microsoft\EdgeWebView" WebView2Loader.dll >nul 2>&1
if %errorlevel% equ 0 (
    echo   [OK] WebView2 runtime found
) else (
    where /r "C:\Program Files\Microsoft\EdgeWebView" WebView2Loader.dll >nul 2>&1
    if %errorlevel% equ 0 (
        echo   [OK] WebView2 runtime found
    ) else (
        echo   [WARNING] WebView2 may not be installed!
        echo   If the app doesn't open, install WebView2 from:
        echo   https://developer.microsoft.com/microsoft-edge/webview2/
        echo.
    )
)

REM ─── Check sidecar ──────────────────────────────────────────
echo   Checking sidecar...
if exist "%PROJECT_DIR%\src-tauri\binaries\backend-x86_64-pc-windows-msvc.exe" (
    for %%f in ("%PROJECT_DIR%\src-tauri\binaries\backend-x86_64-pc-windows-msvc.exe") do (
        echo   [OK] Sidecar found ^(%%~zf bytes^)
    )
) else (
    echo   [WARNING] Sidecar not found - backend features won't work
    echo   To build sidecar: Run scripts\build-exe.bat ^(without --skip-sidecar^)
)

echo.
echo ────────────────────────────────────────────────────────────────
echo   Launching GenericAgent in DEBUG mode...
echo   Console output will appear below.
echo   If the app doesn't open, the error message will show here.
echo.
echo   Log files: %%APPDATA%%\com.genericagent.desktop\logs\
echo ────────────────────────────────────────────────────────────────
echo.

REM ─── Launch the app ─────────────────────────────────────────
"%EXE_PATH%"

set "EXIT_CODE=%errorlevel%"

echo.
echo ────────────────────────────────────────────────────────────────
if %EXIT_CODE% equ 0 (
    echo   App exited normally.
) else (
    echo   App exited with error code: %EXIT_CODE%
    echo.
    echo   Check the log files at:
    echo   %%APPDATA%%\com.genericagent.desktop\logs\
)
echo ────────────────────────────────────────────────────────────────
echo.
pause
