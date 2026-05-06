@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul 2>&1
title GenericAgent - Lanceur
color 0B

echo.
echo ╔══════════════════════════════════════════════════════════╗
echo ║              GenericAgent - Lanceur                      ║
echo ╚══════════════════════════════════════════════════════════╝
echo.

:: Vérifier que l'installation a été faite
if not exist ".venv\Scripts\activate.bat" (
    echo  [!] L'environnement virtuel n'existe pas.
    echo  Veuillez d'abord lancer setup_windows.bat
    echo.
    pause
    exit /b 1
)

:: Vérifier que mykey.py existe
if not exist "mykey.py" (
    echo  [!] Le fichier mykey.py n'existe pas.
    echo  Veuillez d'abord lancer setup_windows.bat
    echo.
    pause
    exit /b 1
)

:: Activer l'environnement virtuel
call .venv\Scripts\activate.bat

:: Menu
echo  Que voulez-vous faire ?
echo.
echo    1) Interface graphique (recommande)
echo    2) Ligne de commande
echo    3) Configurer mes cles API
echo    4) Reinstaller les dependances
echo    5) Quitter
echo.

set /p CHOICE="  Votre choix (1-5) : "

if "%CHOICE%"=="1" goto :gui
if "%CHOICE%"=="2" goto :cli
if "%CHOICE%"=="3" goto :config
if "%CHOICE%"=="4" goto :reinstall
if "%CHOICE%"=="5" exit /b 0
echo  Choix invalide.
pause
exit /b 1

:gui
echo.
echo  Lancement de l'interface graphique...
echo.
python launch.pyw
if %errorlevel% neq 0 (
    echo.
    echo  [!] Erreur au lancement de l'interface graphique.
    echo  Essayez le mode ligne de commande (choix 2).
    echo.
)
pause
exit /b 0

:cli
echo.
echo  Lancement en mode ligne de commande...
echo  Tapez votre question et appuyez sur Entree.
echo  Tapez /quit pour quitter.
echo.
python agentmain.py
pause
exit /b 0

:config
echo.
echo  Lancement de la configuration interactive...
echo.
python configure.py
pause
exit /b 0

:reinstall
echo.
echo  Reinstallation des dependances...
pip install requests beautifulsoup4 websockets markdown2 PySide6 bottle lxml --quiet
echo.
echo  [OK] Dependances reinstallees
pause
exit /b 0
