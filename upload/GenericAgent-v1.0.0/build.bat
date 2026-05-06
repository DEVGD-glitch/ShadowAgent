@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul 2>&1
title GenericAgent — Build .exe
color 0B

echo.
echo ══════════════════════════════════════════════════════════════
echo   GenericAgent v1.0.0 — Windows Build
echo   One-click build to produce GenericAgent.exe
echo ══════════════════════════════════════════════════════════════
echo.

:: ── Step 1: Check Python ────────────────────────────────────────────────────
echo [1/5] Checking Python...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo  [!] Python is not installed or not in PATH.
    echo  Please install Python 3.10+ from https://www.python.org/downloads/
    echo  IMPORTANT: Check "Add Python to PATH" during installation.
    echo.
    pause
    exit /b 1
)

for /f "tokens=2 delims= " %%v in ('python --version 2^>^&1') do set PYVER=%%v
echo  [OK] Python %PYVER% detected

python -c "import sys; exit(0 if sys.version_info >= (3,10) else 1)" 2>nul
if %errorlevel% neq 0 (
    echo  [!] Python 3.10+ required. Your version: %PYVER%
    pause
    exit /b 1
)
echo  [OK] Version compatible (3.10+)
echo.

:: ── Step 2: Create virtual environment ───────────────────────────────────────
echo [2/5] Setting up virtual environment...
if exist ".venv\Scripts\activate.bat" (
    echo  [OK] Virtual environment already exists
) else (
    python -m venv .venv
    if %errorlevel% neq 0 (
        echo  [!] Failed to create virtual environment
        pause
        exit /b 1
    )
    echo  [OK] Virtual environment created
)
call .venv\Scripts\activate.bat
echo.

:: ── Step 3: Install dependencies ────────────────────────────────────────────
echo [3/5] Installing dependencies...
echo  This may take a few minutes on first build...
echo.

python -m pip install --upgrade pip --quiet 2>nul

echo  Installing core dependencies...
pip install requests beautifulsoup4 websockets markdown2 python-dotenv bottle numpy --quiet 2>nul

echo  Installing PySide6 (Qt UI)...
pip install PySide6 --quiet 2>nul
if %errorlevel% neq 0 (
    echo  [!] PySide6 failed. Retrying with --no-cache-dir...
    pip install PySide6 --no-cache-dir --quiet 2>nul
)

echo  Installing PyInstaller and build tools...
pip install pyinstaller Pillow certifi lxml pydantic --quiet 2>nul

echo  Installing optional dependencies...
pip install keyring cryptography --quiet 2>nul

echo  [OK] All dependencies installed
echo.

:: ── Step 4: Generate icon ──────────────────────────────────────────────────
echo [4/5] Generating application icon...
if exist "build\genericagent.ico" (
    echo  [OK] Icon already exists
) else (
    if exist "assets\images\logo.jpg" (
        python -c "from PIL import Image; img=Image.open('assets/images/logo.jpg'); sizes=[(16,16),(32,32),(48,48),(64,64),(128,128),(256,256)]; icons=[img.resize(s,Image.LANCZOS) for s in sizes]; icons[0].save('build/genericagent.ico',format='ICO',sizes=sizes,append_images=icons[1:]); print('  [OK] Icon generated')" 2>nul
        if %errorlevel% neq 0 (
            echo  [!] Could not generate icon (Pillow issue). Build will continue without icon.
        )
    ) else (
        echo  [!] No logo.jpg found. Build will continue without icon.
    )
)
echo.

:: ── Step 5: Build with PyInstaller ──────────────────────────────────────────
echo [5/5] Building GenericAgent.exe...
echo  This will take 2-5 minutes depending on your machine...
echo.

:: Clean previous build
if exist "dist\GenericAgent" (
    echo  Cleaning previous build...
    rmdir /s /q "dist\GenericAgent" 2>nul
)
if exist "build\dist" (
    rmdir /s /q "build\dist" 2>nul
)

:: Run PyInstaller with the spec file
pyinstaller --clean --noconfirm build\genericagent.spec

if %errorlevel% neq 0 (
    echo.
    echo  [!] Build FAILED. Check the error messages above.
    echo  Common fixes:
    echo    - Make sure PySide6 is installed: pip install PySide6
    echo    - Try cleaning: rmdir /s /q build dist
    echo    - Run again: build.bat
    echo.
    pause
    exit /b 1
)

:: ── Verify output ────────────────────────────────────────────────────────────
if exist "dist\GenericAgent\GenericAgent.exe" (
    for %%A in ("dist\GenericAgent\GenericAgent.exe") do set EXE_SIZE=%%~zA
    set /a EXE_MB=!EXE_SIZE! / 1048576

    echo.
    echo ══════════════════════════════════════════════════════════════
    echo   BUILD SUCCESSFUL!
    echo ══════════════════════════════════════════════════════════════
    echo.
    echo   Output: dist\GenericAgent\GenericAgent.exe
    echo   Size:   !EXE_MB! MB
    echo.
    echo   To run:  dist\GenericAgent\GenericAgent.exe
    echo.
    echo   To distribute the whole dist\GenericAgent\ folder:
    echo     - Zip it: powershell Compress-Archive -Path dist\GenericAgent -DestinationPath GenericAgent-v1.0.0-Portable.zip
    echo     - Or create an NSIS installer: python build\build_windows.py --skip-pyinstaller
    echo.

    :: Create a portable ZIP if PowerShell is available
    echo  Creating portable ZIP...
    if exist "GenericAgent-v1.0.0-Portable.zip" del /f /q "GenericAgent-v1.0.0-Portable.zip"
    powershell -NoProfile -Command "Compress-Archive -Path 'dist\GenericAgent\*' -DestinationPath 'GenericAgent-v1.0.0-Portable.zip' -Force" 2>nul
    if exist "GenericAgent-v1.0.0-Portable.zip" (
        echo  [OK] Portable ZIP created: GenericAgent-v1.0.0-Portable.zip
    ) else (
        echo  [!] Could not create ZIP. You can zip dist\GenericAgent manually.
    )
) else (
    echo.
    echo  [!] Build completed but GenericAgent.exe not found at expected location.
    echo  Check the dist\ folder for output files.
)

echo.
pause
