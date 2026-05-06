@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul 2>&1
title GenericAgent - Installation Windows
color 0B

echo.
echo ╔══════════════════════════════════════════════════════════╗
echo ║        GenericAgent - Installateur Windows              ║
echo ║        Agent autonome auto-evolutif                     ║
echo ╚══════════════════════════════════════════════════════════╝
echo.

:: ── Vérification Python ────────────────────────────────────────────────────
echo [1/7] Verification de Python...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo  [!] Python n'est pas installe ou pas dans le PATH.
    echo.
    echo  Options :
    echo    1. Telecharger Python 3.12 depuis https://www.python.org/downloads/
    echo       IMPORTANT : Cochez "Add Python to PATH" pendant l'installation
    echo    2. Ou lancez : assets\install_python_windows.bat
    echo.
    echo  Apres installation de Python, relancez ce script.
    pause
    exit /b 1
)

for /f "tokens=2 delims= " %%v in ('python --version 2^>^&1') do set PYVER=%%v
echo  [OK] Python %PYVER% detecte
echo.

:: ── Vérification version Python (3.10+ requis) ─────────────────────────────
python -c "import sys; exit(0 if sys.version_info >= (3,10) else 1)" 2>nul
if %errorlevel% neq 0 (
    echo  [!] Python 3.10 ou superieur est requis. Votre version : %PYVER%
    echo  Veuillez mettre a jour Python depuis https://www.python.org/downloads/
    pause
    exit /b 1
)
echo  [OK] Version Python compatible (3.10+)
echo.

:: ── Création environnement virtuel ─────────────────────────────────────────
echo [2/7] Creation de l'environnement virtuel...
if exist ".venv\Scripts\activate.bat" (
    echo  [OK] Environnement virtuel deja existant
) else (
    python -m venv .venv
    if %errorlevel% neq 0 (
        echo  [!] Echec de la creation de l'environnement virtuel
        echo  Tentative avec --without-pip...
        python -m venv .venv --without-pip
        if %errorlevel% neq 0 (
            echo  [!] Echec critique. Verifiez votre installation Python.
            pause
            exit /b 1
        )
        echo  Installation de pip...
        .venv\Scripts\python.exe -m ensurepip --default-pip 2>nul
    )
    echo  [OK] Environnement virtuel cree
)
echo.

:: ── Activation environnement virtuel ───────────────────────────────────────
call .venv\Scripts\activate.bat

:: ── Mise à jour pip ────────────────────────────────────────────────────────
echo [3/7] Mise a jour de pip...
python -m pip install --upgrade pip --quiet 2>nul
echo  [OK] pip mis a jour
echo.

:: ── Installation des dépendances ────────────────────────────────────────────
echo [4/7] Installation des dependances (cela peut prendre quelques minutes)...
echo.

echo  Installation des dependances principales...
pip install requests beautifulsoup4 websockets markdown2 --quiet 2>nul
echo  [OK] Dependances principales installees

echo  Installation de PySide6 (interface graphique)...
pip install PySide6 --quiet 2>nul
if %errorlevel% neq 0 (
    echo  [!] PySide6 n'a pas pu etre installe. L'interface graphique ne sera pas disponible.
    echo  Vous pouvez toujours utiliser GenericAgent en ligne de commande.
) else (
    echo  [OK] PySide6 installe
)

echo  Installation des dependances optionnelles...
pip install bottle lxml --quiet 2>nul
echo  [OK] Dependances optionnelles installees
echo.

:: ── Configuration ──────────────────────────────────────────────────────────
echo [5/7] Configuration...
if exist "mykey.py" (
    echo  [OK] Fichier mykey.py deja existant - conserve
) else if exist "mykey_template_fr.py" (
    copy "mykey_template_fr.py" "mykey.py" >nul
    echo  [OK] Template francais copie vers mykey.py
) else if exist "mykey_template_en.py" (
    copy "mykey_template_en.py" "mykey.py" >nul
    echo  [OK] Template anglais copie vers mykey.py
) else (
    copy "mykey_template.py" "mykey.py" >nul
    echo  [OK] Template copie vers mykey.py
)

if not exist "temp" mkdir temp
if not exist "workspace" mkdir workspace
echo  [OK] Dossiers de travail crees
echo.

:: ── Vérification des dépendances ────────────────────────────────────────────
echo [6/7] Verification de l'installation...
python -c "import requests; import bs4; import bottle; print('  [OK] Modules principaux OK')" 2>nul
python -c "import websockets; print('  [OK] websockets OK')" 2>nul || echo  [!] websockets non installe - connexion navigateur degradee
python -c "import PySide6; print('  [OK] PySide6 OK')" 2>nul || echo  [!] PySide6 non installe - interface graphique non disponible
python -c "import markdown2; print('  [OK] markdown2 OK')" 2>nul || echo  [!] markdown2 non installe - rendu Markdown de base
echo.

:: ── Résumé ─────────────────────────────────────────────────────────────────
echo [7/7] Finalisation...
echo.
echo ╔══════════════════════════════════════════════════════════╗
echo ║                INSTALLATION TERMINEE !                  ║
echo ╠══════════════════════════════════════════════════════════╣
echo ║                                                          ║
echo ║  PROCHAINE ETAPE : Configurez votre cle API             ║
echo ║                                                          ║
echo ║  1. Ouvrez le fichier mykey.py dans un editeur          ║
echo ║     (Bloc-notes, Notepad++, VS Code...)                 ║
echo ║  2. Remplacez VOTRE-CLE-ICI par votre cle API           ║
echo ║     (OpenAI, Anthropic, ou autre)                        ║
echo ║  3. Sauvegardez le fichier                              ║
echo ║  4. Lancez GenericAgent avec start.bat                  ║
echo ║                                                          ║
echo ║  Ou vous pouvez lancer la configuration interactive :   ║
echo ║     python configure.py                                  ║
echo ║                                                          ║
echo ╚══════════════════════════════════════════════════════════╝
echo.
pause
