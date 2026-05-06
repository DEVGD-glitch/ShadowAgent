# GenericAgent Desktop — Guide de Build Windows

## Vue d'ensemble de l'architecture

```
┌─────────────────────────────────────────────┐
│            GenericAgent.exe                  │
│  ┌─────────────┐  ┌──────────────────────┐  │
│  │  Tauri v2    │  │  Next.js Frontend    │  │
│  │  (Rust)      │──│  (HTML/CSS/JS/TS)    │  │
│  │  main.rs     │  │  86+ fichiers        │  │
│  └──────┬───────┘  └──────────────────────┘  │
│         │ lance comme sidecar               │
│  ┌──────▼───────┐                           │
│  │ backend.exe   │  (Python FastAPI)        │
│  │ (PyInstaller) │  port 8765              │
│  │  server.py    │  SSE + REST + WebSocket  │
│  └───────────────┘                           │
└─────────────────────────────────────────────┘
```

L'app desktop est composée de 3 couches :
1. **Tauri v2 (Rust)** — Fenêtre native, gestion du sidecar, dialogs
2. **Next.js (TypeScript)** — Interface utilisateur (export statique → `/out`)
3. **Python FastAPI (sidecar)** — Backend IA, LLM, STT, TTS, mémoire

---

## ⚡ Quick Start (TL;DR)

```powershell
# 1. Vérifier les prérequis
scripts\check-prerequisites.bat

# 2. Installer les prérequis manquants
winget install Rustlang.Rustup OpenJS.NodeJS.LTS Python.Python.3.12
pip install pyinstaller

# 3. Builder !
scripts\build-exe.bat

# 4. Récupérer l'installateur
dir dist\GenericAgent_1.2.0_x64-setup.exe
```

---

## Prérequis Windows

### 1. Installer Rust (obligatoire)

```powershell
# Via winget
winget install Rustlang.Rustup

# OU télécharger https://win.rustup.rs/x86_64

# Après installation, redémarrer le terminal et vérifier :
rustc --version    # ex: rustc 1.82.0
cargo --version    # ex: cargo 1.82.0
```

### 2. Installer Node.js + Bun (obligatoire)

```powershell
# Node.js 20+
winget install OpenJS.NodeJS.LTS

# Bun (gestionnaire de paquets rapide)
powershell -c "irm bun.sh/install.ps1 | iex"

# Vérifier :
node --version     # v20+ ou v22+
bun --version      # 1.0+
```

### 3. Installer Python 3.10+ (obligatoire pour le sidecar)

```powershell
winget install Python.Python.3.12
# OU télécharger https://python.org/downloads/

# ⚠️ IMPORTANT : Cocher "Add Python to PATH" lors de l'installation !

# Vérifier :
python --version   # Python 3.10+
pip --version      # pip 24+
pip install pyinstaller
```

### 4. Installer Visual Studio Build Tools (obligatoire pour Rust)

```powershell
winget install Microsoft.VisualStudio.2022.BuildTools

# OU télécharger https://visualstudio.microsoft.com/visual-cpp-build-tools/
# ⚠️ IMPORTANT : Cocher "Desktop development with C++" dans l'installateur !
```

### 5. Vérification automatique

```powershell
scripts\check-prerequisites.bat
```

Ce script vérifie tous les prérequis et les fichiers du projet.

---

## Build complet — Étape par étape

### Étape 0 : Se placer dans le bon dossier

```powershell
cd C:\Users\vous\Downloads\GenericAgent-Desktop-v1.2.0
# OU le dossier où vous avez extrait le projet
```

> **IMPORTANT** : Toujours exécuter les scripts depuis la racine du projet !

### Étape 1 : Installer les dépendances frontend

```powershell
bun install
```

### Étape 2 : Builder le frontend Next.js

```powershell
bun run build
# Cela crée le dossier /out avec les fichiers statiques
# Vérifier :
dir out\index.html
```

### Étape 3 : Installer les dépendances Python du backend

```powershell
pip install fastapi uvicorn pydantic httpx edge-tts
pip install -r upload\GenericAgent-v1.2.0\requirements.txt
```

### Étape 4 : Tester le backend manuellement (recommandé)

```powershell
cd upload\GenericAgent-v1.2.0
python server.py

# Dans un autre terminal, tester :
curl http://localhost:8765/status
# → Devrait retourner du JSON

# Arrêter avec Ctrl+C, puis :
cd ..\..
```

### Étape 5 : Builder le sidecar Python avec PyInstaller

```powershell
scripts\build-sidecar.bat

# Vérifier le résultat :
dir src-tauri\binaries\backend-x86_64-pc-windows-msvc.exe
# → Devrait faire ~50-200 MB
```

### Étape 6 : Builder l'application Tauri

```powershell
bun tauri build
# Prend 5-15 min la première fois
```

> **Note** : Le `beforeBuildCommand` est vide dans `tauri.conf.json` car le frontend
> est déjà buildé à l'étape 2. Tauri package directement les fichiers de `/out`.

### Étape 7 : Récupérer les fichiers de sortie

```powershell
# Installateur NSIS (recommandé pour distribution) :
dir src-tauri\target\release\bundle\nsis\*.exe

# Installateur MSI (alternative) :
dir src-tauri\target\release\bundle\msi\*.msi

# Exécutable portable (sans installateur) :
dir src-tauri\target\release\GenericAgent.exe
```

---

## Build en une seule commande

```powershell
# Build complet automatique
scripts\build-exe.bat

# Options :
scripts\build-exe.bat --skip-sidecar     # Skip PyInstaller (si déjà buildé)
scripts\build-exe.bat --skip-frontend    # Skip Next.js build
scripts\build-exe.bat --dev              # Mode dev au lieu de build
scripts\build-exe.bat --clean            # Nettoyer avant de builder
```

---

## Mode développement (sans build complet)

### Option A : Navigateur uniquement (le plus simple pour tester)

```powershell
# Terminal 1 : Backend Python
cd upload\GenericAgent-v1.2.0
python server.py
# → Backend sur http://localhost:8765

# Terminal 2 : Frontend Next.js
bun run dev
# → Ouvrir http://localhost:3000 dans le navigateur
```

### Option B : Fenêtre native Tauri (mode dev)

```powershell
# Terminal 1 : Backend
cd upload\GenericAgent-v1.2.0
python server.py

# Terminal 2 : Tauri dev (avec Hot Reload)
bun tauri dev
# → Ouvre une fenêtre native
```

---

## Structure du projet

```
GenericAgent-Desktop/
├── src/                          # Frontend Next.js
│   ├── app/                      # Pages (Chat, Dashboard, History, Memory, Settings)
│   ├── components/               # 60+ composants UI
│   │   ├── avatar/               # VRM 3D avatar viewer
│   │   ├── pet/                  # Desktop pet animé
│   │   └── ui/                   # shadcn/ui components
│   ├── lib/                      # API, backend, tauri, db
│   ├── stores/                   # Zustand state management
│   └── hooks/                    # Custom React hooks
│
├── src-tauri/                    # Backend Tauri (Rust)
│   ├── src/main.rs               # Point d'entrée Rust (427 lignes)
│   ├── Cargo.toml                # Dépendances Rust
│   ├── tauri.conf.json           # Configuration Tauri v2
│   ├── build.rs                  # Script de build Tauri
│   ├── capabilities/default.json # Permissions
│   ├── binaries/                 # Sidecar Python
│   │   ├── launch_backend.py     # Lanceur Python
│   │   └── backend-x86_64-pc-windows-msvc.exe  # (généré par PyInstaller)
│   └── icons/                    # Icônes de l'app
│
├── upload/GenericAgent-v1.2.0/   # Backend Python FastAPI
│   ├── server.py                 # Serveur FastAPI (SSE, REST, WebSocket)
│   ├── agentmain/                # Core agent
│   ├── llmcore/                  # Clients LLM (10+ providers)
│   ├── memory/                   # Mémoire 5 couches
│   ├── mcp/                      # Model Context Protocol
│   └── requirements.txt          # Dépendances Python
│
├── public/                       # Assets statiques
│   └── models/                   # VRM 3D models
│       ├── avatar.vrm
│       └── waifu.vrm
│
├── scripts/                      # Scripts de build
│   ├── build-exe.bat             # Build complet Windows (v3)
│   ├── build-exe.sh              # Build complet Linux
│   ├── build-sidecar.bat         # Build sidecar seul (v2)
│   ├── build-sidecar.sh          # Build sidecar Linux
│   └── check-prerequisites.bat   # Vérification des prérequis
│
├── package.json                  # Dépendances Node.js
├── next.config.ts                # Config Next.js (static export)
├── BUILD_GUIDE.md                # Ce fichier
└── worklog.md                    # Journal de développement
```

---

## Dépannage

### ❌ `cp: illegal option -- r`

**Cause** : Les commandes `cp -r` sont Linux-only.

**Solution** : Déjà corrigé dans la v3. Le `package.json` build script est maintenant juste `next build`.
Si vous avez encore cette erreur, mettez à jour `package.json` :

```json
"build": "next build"
```

### ❌ `tsc && vite build` au lieu de `next build`

**Cause** : Le `beforeBuildCommand` dans `tauri.conf.json` lançait `bun run build` qui
pouvait être intercepté par un template Vite.

**Solution** : Déjà corrigé. Le `beforeBuildCommand` est maintenant vide `""`.
Le frontend est pré-buildé à l'étape 2, et Tauri package directement `/out`.

### ❌ `Le chemin d'accès spécifié est introuvable`

**Cause** : Le dossier `upload\GenericAgent-v1.2.0` n'existe pas dans votre extraction.

**Solution** :
1. Vérifiez que vous avez extrait le ZIP complet
2. Le dossier `upload\GenericAgent-v1.2.0` doit contenir `server.py`
3. Si le backend est ailleurs, utilisez `--skip-sidecar` :
   ```powershell
   scripts\build-exe.bat --skip-sidecar
   ```

### ❌ `cargo not found`

**Solution** : Redémarrer le terminal après installation de Rust.
```powershell
$env:Path += ";$env:USERPROFILE\.cargo\bin"
```

### ❌ `link.exe not found` / C++ build tools

```
error: linker `link.exe` not found
```

**Solution** : Installer VS Build Tools avec "Desktop development with C++"
```powershell
winget install Microsoft.VisualStudio.2022.BuildTools
# Puis dans VS Installer, cocher "Desktop development with C++"
```

### ❌ `sidecar "binaries/backend" not found`

**Solution** : Le sidecar n'a pas été buildé. Exécuter :
```powershell
scripts\build-sidecar.bat
```

### ❌ PyInstaller `ModuleNotFoundError`

**Solution** : Installer le module manquant et ajouter `--hidden-import` :
```powershell
pip install nom_du_module
# Puis éditer build-sidecar.bat pour ajouter:
--hidden-import=nom_du_module
```

### ❌ Port 8765 déjà utilisé

```powershell
netstat -ano | findstr :8765
taskkill /PID <PID trouvé> /F
```

### ❌ Next.js build failed

```powershell
# Nettoyer et recommencer
rmdir /s /q .next out node_modules
bun install
bun run build
```

### ❌ Warning: Next.js inferred your workspace root

C'est un warning inoffensif. Pour le supprimer, ajouter dans `next.config.ts` :

```typescript
const nextConfig: NextConfig = {
  output: "export",
  images: { unoptimized: true },
  turbopack: {
    root: ".."
  }
};
```

### ❌ L'installateur NSIS est trop gros

L'installateur peut faire 200-500 MB car il inclut le runtime Python bundlé.
Pour réduire la taille :
- Retirer `sentence-transformers` des dépendances (~2 GB économisés)
- Utiliser `--exclude-module` dans PyInstaller
- Supprimer `__pycache__` avant le build

---

## Notes importantes

### 1. Le frontend fonctionne SANS le backend

L'app Next.js a un mode hors-ligne avec données de fallback. Vous pouvez :
- Utiliser l'app en navigateur sans le backend
- Le chat utilisera Pollinations (gratuit, sans clé API) si pas de backend

### 2. Le sidecar est optionnel

Si vous n'avez pas le backend Python, vous pouvez quand même builder :
```powershell
scripts\build-exe.bat --skip-sidecar
```
L'app fonctionnera en mode frontend-only.

### 3. L'identifier Tauri a changé

L'ancien identifiant `com.genericagent.app` finissait par `.app` ce qui
conflit avec l'extension macOS. Il est maintenant `com.genericagent.desktop`.

---

## Commandes rapides

| Action | Commande |
|--------|----------|
| Vérifier prérequis | `scripts\check-prerequisites.bat` |
| Build complet | `scripts\build-exe.bat` |
| Build sans sidecar | `scripts\build-exe.bat --skip-sidecar` |
| Build sidecar seul | `scripts\build-sidecar.bat` |
| Mode dev (navigateur) | `bun run dev` |
| Mode dev (Tauri) | `bun tauri dev` |
| Nettoyer + build | `scripts\build-exe.bat --clean` |
