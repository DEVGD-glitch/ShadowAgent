#!/usr/bin/env python3
# ══════════════════════════════════════════════════════════════════════════════
#  GenericAgent — Configuration interactive
#  Guide l'utilisateur pour configurer ses clés API et la langue
# ══════════════════════════════════════════════════════════════════════════════
"""
Lancez ce script pour configurer GenericAgent interactivement :
    python configure.py
"""
import getpass
import os
import sys

def header():
    print()
    print("╔════════════════════════════════════════════════════════════╗")
    print("║        Shadow Agent — Configuration interactive          ║")
    print("╚════════════════════════════════════════════════════════════╝")
    print()

def choose_language():
    """Choix de la langue de l'interface."""
    print("🌐  Choisissez la langue de l'application :")
    print("    1) Français")
    print("    2) English")
    print("    3) 中文")
    print()
    choice = input("  Votre choix (1-3) [1] : ").strip()
    lang_map = {"1": "fr", "2": "en", "3": "zh", "": "fr"}
    return lang_map.get(choice, "fr")

def choose_api_provider():
    """Choix du fournisseur d'API."""
    print()
    print("🤖  Quel fournisseur d'IA souhaitez-vous utiliser ?")
    print("    1) Anthropic Claude (recommandé)")
    print("    2) OpenAI GPT")
    print("    3) Les deux (avec basculement automatique)")
    print("    4) Aucun — je configurerai plus tard")
    print()
    choice = input("  Votre choix (1-4) [1] : ").strip()
    return choice or "1"

def get_api_key(provider_name):
    """Demande la clé API pour un fournisseur."""
    print()
    print(f"🔑  Entrez votre clé API {provider_name}")
    print(f"    (ou appuyez sur Entrée pour ignorer)")
    key = getpass.getpass("  Clé API (hidden) : ").strip()
    return key

def generate_mykey(lang, provider_choice, claude_key="", oai_key=""):
    """Génère le fichier mykey.py."""
    lines = [
        '# ═══════════════════════════════════════════════════════════',
        '#  GenericAgent — Configuration (générée automatiquement)',
        '# ═══════════════════════════════════════════════════════════',
        '',
        f'GA_LANG = "{lang}"',
        '',
    ]
    
    has_claude = provider_choice in ("1", "3")
    has_oai = provider_choice in ("2", "3")
    
    if has_claude:
        lines.extend([
            '# ── Connexion Anthropic Claude ──────────────────────────────',
            'native_claude_config = {',
            "    'name': 'claude',",
            f"    'apikey': '{claude_key or 'sk-ant-VOTRE-CLE-ICI'}',",
            "    'apibase': 'https://api.anthropic.com',",
            "    'model': 'claude-sonnet-4-6',",
            "    'thinking_type': 'adaptive',",
            '}',
            '',
        ])
    
    if has_oai:
        lines.extend([
            '# ── Connexion OpenAI GPT ─────────────────────────────────────',
            'native_oai_config = {',
            "    'name': 'gpt',",
            f"    'apikey': '{oai_key or 'sk-VOTRE-CLE-ICI'}',",
            "    'apibase': 'https://api.openai.com/v1',",
            "    'model': 'gpt-5.4',",
            "    'api_mode': 'chat_completions',",
            '}',
            '',
        ])
    
    if has_claude and has_oai:
        lines.extend([
            '# ── Basculement automatique ──────────────────────────────────',
            'mixin_config = {',
            "    'llm_nos': ['claude', 'gpt'],",
            "    'max_retries': 5,",
            "    'base_delay': 0.5,",
            '}',
            '',
        ])
    
    return '\n'.join(lines)

def main():
    header()
    
    # Vérifier si mykey.py existe déjà
    if os.path.exists("mykey.py"):
        print("⚠️  Un fichier mykey.py existe déjà.")
        choice = input("  Voulez-vous le remplacer ? (o/n) [n] : ").strip().lower()
        if choice not in ("o", "oui", "y", "yes"):
            print("\n  Configuration annulée. Votre fichier mykey.py est conservé.")
            return
    
    # Étape 1 : Langue
    lang = choose_language()
    
    # Messages dans la langue choisie
    if lang == "fr":
        _ask = "  Appuyez sur Entrée pour continuer..."
    elif lang == "zh":
        _ask = "  按回车继续..."
    else:
        _ask = "  Press Enter to continue..."
    
    # Étape 2 : Fournisseur API
    provider = choose_api_provider()
    
    # Étape 3 : Clés API
    claude_key = ""
    oai_key = ""
    if provider in ("1", "3"):
        claude_key = get_api_key("Anthropic")
    if provider in ("2", "3"):
        oai_key = get_api_key("OpenAI")
    
    # Étape 4 : Génération du fichier
    content = generate_mykey(lang, provider, claude_key, oai_key)
    
    with open("mykey.py", "w", encoding="utf-8") as f:
        f.write(content)
    
    print()
    print("✅  Fichier mykey.py créé avec succès !")
    
    if "VOTRE-CLE-ICI" in content:
        print()
        print("⚠️  ATTENTION : Vous n'avez pas entré de clé API.")
        print("   L'application ne fonctionnera pas sans clé API valide.")
        print("   Ouvrez le fichier mykey.py et remplacez VOTRE-CLE-ICI")
        print("   par votre vraie clé API.")
    
    print()
    print("🚀  Vous pouvez maintenant lancer GenericAgent avec start.bat")
    input(_ask)

if __name__ == "__main__":
    main()
