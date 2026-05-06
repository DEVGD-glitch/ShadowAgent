@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul 2>&1
title GenericAgent — One-Click Installer
color 0B

echo.
echo ╔══════════════════════════════════════════════════════════╗
echo ║        GenericAgent — One-Click Installer               ║
echo ║        Agent autonome auto-evolutif                     ║
echo ╚══════════════════════════════════════════════════════════╝
echo.

:: ── Check for existing installation ──────────────────────────────────────
set "INSTALL_DIR=%LOCALAPPDATA%\GenericAgent"
if exist "%INSTALL_DIR%\GenericAgent.exe" (
    echo  [!] GenericAgent is already installed at:
    echo      %INSTALL_DIR%
    echo.
    choice /C YN /M "  Do you want to reinstall/update? (Y=Yes / N=Exit)"
    if errorlevel 2 goto :end
    echo.
    echo  Stopping GenericAgent...
    taskkill /F /IM GenericAgent.exe >nul 2>&1
    timeout /t 3 /nobreak >nul
)

:: ── Step 1: Check Python ─────────────────────────────────────────────────
echo [1/5] Checking Python installation...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo  [!] Python is not installed or not in PATH.
    echo.
    echo  Installing Python 3.12 automatically...
    echo.

    set "PYTHON_URL=https://www.python.org/ftp/python/3.12.9/python-3.12.9-amd64.exe"
    set "PYTHON_INSTALLER=%TEMP%\python_installer.exe"

    echo  Downloading Python 3.12...
    powershell -NoProfile -Command "[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; $ProgressPreference='SilentlyContinue'; Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.12.9/python-3.12.9-amd64.exe' -OutFile '%PYTHON_INSTALLER%' -UseBasicParsing"

    if not exist "%PYTHON_INSTALLER%" (
        echo  [x] Failed to download Python. Please install manually from https://www.python.org/downloads/
        pause
        exit /b 1
    )

    echo  Installing Python 3.12 (this may take 2-3 minutes)...
    start /wait "" "%PYTHON_INSTALLER%" /passive InstallAllUsers=0 PrependPath=1 Include_test=0 Include_pip=1 Include_launcher=1
    del /f /q "%PYTHON_INSTALLER%" >nul 2>&1

    :: Refresh PATH
    set "PATH=%LOCALAPPDATA%\Programs\Python\Python312;%LOCALAPPDATA%\Programs\Python\Python312\Scripts;%PATH%"

    python --version >nul 2>&1
    if %errorlevel% neq 0 (
        echo  [x] Python installation failed. Please install manually.
        pause
        exit /b 1
    )
    echo  [OK] Python installed successfully
)
for /f "tokens=2 delims= " %%v in ('python --version 2^>^&1') do echo  [OK] Python %%v detected
echo.

:: ── Step 2: Create virtual environment ────────────────────────────────────
echo [2/5] Setting up virtual environment...
if exist "%INSTALL_DIR%\.venv\Scripts\activate.bat" (
    echo  [OK] Virtual environment already exists
) else (
    if not exist "%INSTALL_DIR%" mkdir "%INSTALL_DIR%"
    python -m venv "%INSTALL_DIR%\.venv"
    if %errorlevel% neq 0 (
        echo  [!] Failed to create virtual environment
        pause
        exit /b 1
    )
    echo  [OK] Virtual environment created
)
call "%INSTALL_DIR%\.venv\Scripts\activate.bat"
echo.

:: ── Step 3: Install GenericAgent ─────────────────────────────────────────
echo [3/5] Installing GenericAgent and dependencies...
echo  This may take a few minutes on first install...
echo.

python -m pip install --upgrade pip --quiet 2>nul

:: Install core dependencies
pip install requests beautifulsoup4 websockets markdown2 python-dotenv bottle --quiet 2>nul

:: Install Qt UI (PySide6)
echo  Installing PySide6 (desktop UI)...
pip install PySide6 --quiet 2>nul
if %errorlevel% neq 0 (
    echo  [!] PySide6 installation failed. Trying with --no-cache-dir...
    pip install PySide6 --no-cache-dir --quiet 2>nul
)

:: Install optional dependencies
pip install lxml Pillow --quiet 2>nul

echo  [OK] Dependencies installed
echo.

:: ── Step 4: Copy application files ───────────────────────────────────────
echo [4/5] Setting up application files...

:: Copy the GenericAgent source to the install directory
:: (We use xcopy to copy everything except .venv)
if not "%~dp0" == "%INSTALL_DIR%\" (
    echo  Copying application files...
    if not exist "%INSTALL_DIR%\agentmain" mkdir "%INSTALL_DIR%\agentmain"
    if not exist "%INSTALL_DIR%\llmcore" mkdir "%INSTALL_DIR%\llmcore"
    if not exist "%INSTALL_DIR%\frontends" mkdir "%INSTALL_DIR%\frontends"
    if not exist "%INSTALL_DIR%\memory" mkdir "%INSTALL_DIR%\memory"
    if not exist "%INSTALL_DIR%\tools" mkdir "%INSTALL_DIR%\tools"
    if not exist "%INSTALL_DIR%\plugins" mkdir "%INSTALL_DIR%\plugins"
    if not exist "%INSTALL_DIR%\i18n" mkdir "%INSTALL_DIR%\i18n"
    if not exist "%INSTALL_DIR%\assets" mkdir "%INSTALL_DIR%\assets"
    if not exist "%INSTALL_DIR%\mcp" mkdir "%INSTALL_DIR%\mcp"

    xcopy /E /Y /Q "%~dp0agentmain\*" "%INSTALL_DIR%\agentmain\" >nul 2>&1
    xcopy /E /Y /Q "%~dp0llmcore\*" "%INSTALL_DIR%\llmcore\" >nul 2>&1
    xcopy /E /Y /Q "%~dp0frontends\*" "%INSTALL_DIR%\frontends\" >nul 2>&1
    xcopy /E /Y /Q "%~dp0memory\*" "%INSTALL_DIR%\memory\" >nul 2>&1
    xcopy /E /Y /Q "%~dp0tools\*" "%INSTALL_DIR%\tools\" >nul 2>&1
    xcopy /E /Y /Q "%~dp0plugins\*" "%INSTALL_DIR%\plugins\" >nul 2>&1
    xcopy /E /Y /Q "%~dp0i18n\*" "%INSTALL_DIR%\i18n\" >nul 2>&1
    xcopy /E /Y /Q "%~dp0assets\*" "%INSTALL_DIR%\assets\" >nul 2>&1
    xcopy /E /Y /Q "%~dp0mcp\*" "%INSTALL_DIR%\mcp\" >nul 2>&1

    :: Copy root Python files
    for %%f in (ga.py agent_loop.py config.py env_loader.py logging_config.py protocols.py exceptions.py circuit_breaker.py metrics.py simphtml.py server.py configure.py mykey_template.py mykey_template_en.py mykey_template_fr.py pyproject.toml mcp_config.json) do (
        if exist "%~dp0%%f" copy /Y "%~dp0%%f" "%INSTALL_DIR%\" >nul 2>&1
    )

    echo  [OK] Application files copied
) else (
    echo  [OK] Already in install directory
)

:: Configure mykey.py if not exists
if not exist "%INSTALL_DIR%\mykey.py" (
    if exist "%INSTALL_DIR%\mykey_template_fr.py" (
        copy "%INSTALL_DIR%\mykey_template_fr.py" "%INSTALL_DIR%\mykey.py" >nul
    ) else if exist "%INSTALL_DIR%\mykey_template_en.py" (
        copy "%INSTALL_DIR%\mykey_template_en.py" "%INSTALL_DIR%\mykey.py" >nul
    ) else if exist "%INSTALL_DIR%\mykey_template.py" (
        copy "%INSTALL_DIR%\mykey_template.py" "%INSTALL_DIR%\mykey.py" >nul
    )
)

:: Create workspace directories
mkdir "%USERPROFILE%\GenericAgent\workspace" >nul 2>&1
mkdir "%USERPROFILE%\GenericAgent\config" >nul 2>&1
mkdir "%USERPROFILE%\GenericAgent\data" >nul 2>&1
mkdir "%USERPROFILE%\GenericAgent\memory" >nul 2>&1
echo  [OK] Workspace directories created
echo.

:: ── Step 5: Create shortcuts and launcher ─────────────────────────────────
echo [5/5] Creating shortcuts and launcher...

:: Create a launcher batch file
set "LAUNCHER=%INSTALL_DIR%\GenericAgent.bat"
(
echo @echo off
echo start "" /B "%INSTALL_DIR%\.venv\Scripts\pythonw.exe" "%INSTALL_DIR%\launch_desktop.py"
) > "%LAUNCHER%"

:: Create desktop shortcut
powershell -NoProfile -Command "$ws = New-Object -ComObject WScript.Shell; $sc = $ws.CreateShortcut('%USERPROFILE%\Desktop\GenericAgent.lnk'); $sc.TargetPath = '%LAUNCHER%'; $sc.WorkingDirectory = '%INSTALL_DIR%'; $sc.Description = 'GenericAgent - Agent autonome auto-evolutif'; $sc.Save()"

:: Create Start Menu shortcut
mkdir "%APPDATA%\Microsoft\Windows\Start Menu\Programs\GenericAgent" >nul 2>&1
powershell -NoProfile -Command "$ws = New-Object -ComObject WScript.Shell; $sc = $ws.CreateShortcut('%APPDATA%\Microsoft\Windows\Start Menu\Programs\GenericAgent\GenericAgent.lnk'); $sc.TargetPath = '%LAUNCHER%'; $sc.WorkingDirectory = '%INSTALL_DIR%'; $sc.Description = 'GenericAgent - Agent autonome auto-evolutif'; $sc.Save()"

:: Add to Windows Defender exclusion (speeds up launch)
powershell -NoProfile -Command "Add-MpPreference -ExclusionPath '%INSTALL_DIR%' -ErrorAction SilentlyContinue"

:: Enable long paths
powershell -NoProfile -Command "try { Set-ItemProperty -Path 'HKLM:\SYSTEM\CurrentControlSet\Control\FileSystem' -Name 'LongPathsEnabled' -Value 1 -ErrorAction Stop } catch {}"

echo  [OK] Shortcuts created
echo.

:: ── Summary ───────────────────────────────────────────────────────────────
echo.
echo ╔══════════════════════════════════════════════════════════╗
echo ║                INSTALLATION COMPLETE!                    ║
echo ╠══════════════════════════════════════════════════════════╣
echo ║                                                          ║
echo ║  GenericAgent is installed at:                           ║
echo ║    %INSTALL_DIR%                    ║
echo ║                                                          ║
echo ║  NEXT STEP: Configure your API key                      ║
echo ║                                                          ║
echo ║  1. Open: %INSTALL_DIR%\mykey.py          ║
echo ║  2. Replace VOTRE-CLE-ICI with your API key             ║
echo ║  3. Save the file                                       ║
echo ║  4. Launch GenericAgent from the desktop shortcut       ║
echo ║                                                          ║
echo ║  Or run the interactive configuration:                  ║
echo ║    %INSTALL_DIR%\.venv\Scripts\python.exe configure.py   ║
echo ║                                                          ║
echo ╚══════════════════════════════════════════════════════════╝
echo.

choice /C YN /M "  Launch GenericAgent now? (Y=Yes / N=Exit)"
if errorlevel 2 goto :end
start "" /B "%LAUNCHER%"

:end
