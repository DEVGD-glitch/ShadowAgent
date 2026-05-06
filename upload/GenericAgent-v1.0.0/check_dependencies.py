#!/usr/bin/env python3
# ══════════════════════════════════════════════════════════════════════════════
#  GenericAgent — Vérification des dépendances au démarrage
#  Remplace les ImportError cryptiques par des messages clairs
# ══════════════════════════════════════════════════════════════════════════════
"""
Ce module vérifie que toutes les dépendances nécessaires sont installées
avant de lancer l'application. Il propose de les installer automatiquement.

Utilisation :
    # Dans le code de démarrage (launch.pyw, agentmain.py, etc.) :
    from check_dependencies import check_and_install
    check_and_install()
"""
import sys
import importlib
import subprocess
import os

# Toutes les dépendances avec leur nom d'import et de package pip
REQUIRED_DEPS = {
    # Core — obligatoires
    "requests":         {"package": "requests",       "required": True,  "desc_fr": "Requêtes HTTP"},
    "bs4":              {"package": "beautifulsoup4",  "required": True,  "desc_fr": "Analyse HTML"},
    "bottle":           {"package": "bottle",          "required": True,  "desc_fr": "Serveur HTTP léger"},
    # Core — nouveau (remplace simple-websocket-server)
    "websockets":       {"package": "websockets",      "required": False, "desc_fr": "WebSocket robuste (recommandé)"},
    # UI Qt
    "PySide6":          {"package": "PySide6",         "required": False, "desc_fr": "Interface graphique Qt"},
    # Rendu Markdown
    "markdown2":        {"package": "markdown2",       "required": False, "desc_fr": "Rendu Markdown amélioré"},
    # Navigateur
    "lxml":             {"package": "lxml",            "required": False, "desc_fr": "Analyse XML/HTML rapide"},
}

# Dépendances optionnelles par fonctionnalité
OPTIONAL_GROUPS = {
    "Interface graphique": ["PySide6"],
    "Navigateur avancé": ["lxml"],
    "Rendu Markdown amélioré": ["markdown2"],
    "WebSocket robuste": ["websockets"],
}


def _is_installed(module_name):
    """Vérifie si un module Python est installé."""
    try:
        importlib.import_module(module_name)
        return True
    except ImportError:
        return False


def _install_package(package_name):
    """Installe un package pip."""
    try:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", package_name, "--quiet"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        return True
    except subprocess.CalledProcessError:
        return False


def check_dependencies(verbose=True):
    """
    Vérifie toutes les dépendances et retourne un rapport.
    
    Returns:
        dict: {"missing_required": [...], "missing_optional": [...], "installed": [...]}
    """
    report = {"missing_required": [], "missing_optional": [], "installed": []}
    
    for module_name, info in REQUIRED_DEPS.items():
        if _is_installed(module_name):
            report["installed"].append((module_name, info["desc_fr"]))
        elif info["required"]:
            report["missing_required"].append((module_name, info))
        else:
            report["missing_optional"].append((module_name, info))
    
    if verbose:
        _print_report(report)
    
    return report


def _print_report(report):
    """Affiche le rapport de vérification."""
    lang = os.environ.get("GA_LANG", "fr").strip().lower()
    if lang not in ("fr", "en", "zh"):
        try:
            import mykey
            lang = getattr(mykey, "GA_LANG", "fr").strip().lower()
        except ImportError:
            lang = "fr"
    
    if lang == "fr":
        print("\n=== Vérification des dépendances ===\n")
        if report["installed"]:
            print("✅ Installés :")
            for mod, desc in report["installed"]:
                print(f"   • {mod} ({desc})")
        if report["missing_required"]:
            print("\n❌ Manquants (obligatoires) :")
            for mod, info in report["missing_required"]:
                print(f"   • {mod} ({info['desc_fr']}) — pip install {info['package']}")
        if report["missing_optional"]:
            print("\n⚠️  Manquants (optionnels) :")
            for mod, info in report["missing_optional"]:
                print(f"   • {mod} ({info['desc_fr']}) — pip install {info['package']}")
        print()
    else:
        print("\n=== Dependency Check ===\n")
        if report["installed"]:
            print("✅ Installed:")
            for mod, desc in report["installed"]:
                print(f"   • {mod} ({desc})")
        if report["missing_required"]:
            print("\n❌ Missing (required):")
            for mod, info in report["missing_required"]:
                print(f"   • {mod} — pip install {info['package']}")
        if report["missing_optional"]:
            print("\n⚠️  Missing (optional):")
            for mod, info in report["missing_optional"]:
                print(f"   • {mod} — pip install {info['package']}")
        print()


def check_and_install():
    """
    Vérifie les dépendances et propose d'installer les manquantes.
    À appeler au démarrage de l'application.
    """
    report = check_dependencies(verbose=True)
    
    if not report["missing_required"] and not report["missing_optional"]:
        return True
    
    # Installer les obligatoires manquants
    if report["missing_required"]:
        for mod, info in report["missing_required"]:
            print(f"Installation de {info['package']} (obligatoire)...")
            if _install_package(info["package"]):
                print(f"  ✅ {mod} installé avec succès")
            else:
                print(f"  ❌ Échec de l'installation de {mod}")
                print(f"     Veuillez l'installer manuellement : pip install {info['package']}")
                return False
    
    # Proposer d'installer les optionnels manquants
    if report["missing_optional"]:
        try:
            answer = input("\nVoulez-vous installer les dépendances optionnelles manquantes ? (o/n) [o] : ").strip().lower()
            if answer in ("", "o", "oui", "y", "yes"):
                for mod, info in report["missing_optional"]:
                    print(f"Installation de {info['package']}...")
                    if _install_package(info["package"]):
                        print(f"  ✅ {mod} installé avec succès")
                    else:
                        print(f"  ⚠️  {mod} n'a pas pu être installé — fonctionnalité réduite")
        except (EOFError, KeyboardInterrupt):
            print("\nInstallation optionnelle ignorée.")
    
    return True


if __name__ == "__main__":
    if check_and_install():
        print("\n✅ Toutes les dépendances sont prêtes !")
    else:
        print("\n❌ Des dépendances obligatoires sont manquantes.")
        sys.exit(1)
