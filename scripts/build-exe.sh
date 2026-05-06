#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════
# GenericAgent — Build Windows Desktop App (.exe + Installer)
#
# This script builds the complete GenericAgent desktop application:
#   1. Builds the Next.js frontend
#   2. Packages the Python backend as a standalone .exe (PyInstaller)
#   3. Builds the Tauri desktop app (Rust + WebView2)
#   4. Creates a one-click NSIS installer for Windows
#
# Prerequisites (Windows):
#   - Node.js 18+ & bun
#   - Python 3.10+ & pip
#   - Rust & Cargo (rustup.rs)
#   - Visual Studio Build Tools (C++ workload)
#   - WebView2 (installed by default on Windows 11)
#
# Usage:
#   bash scripts/build-exe.sh          # Full build
#   bash scripts/build-exe.sh --skip-py  # Skip Python backend build
#   bash scripts/build-exe.sh --dev     # Development mode
# ═══════════════════════════════════════════════════════════════════════

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
PURPLE='\033[0;35m'
NC='\033[0m' # No Color

echo -e "${PURPLE}╔══════════════════════════════════════════════════╗${NC}"
echo -e "${PURPLE}║     GenericAgent — Windows Desktop Builder      ║${NC}"
echo -e "${PURPLE}╚══════════════════════════════════════════════════╝${NC}"
echo ""

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
BACKEND_DIR="$PROJECT_DIR/upload/GenericAgent-Desktop-v1.2.0"
TAURI_DIR="$PROJECT_DIR/src-tauri"
DIST_DIR="$PROJECT_DIR/dist"

SKIP_PY=false
DEV_MODE=false

for arg in "$@"; do
    case $arg in
        --skip-py) SKIP_PY=true ;;
        --dev) DEV_MODE=true ;;
        *) echo "Unknown argument: $arg"; exit 1 ;;
    esac
done

# ──────────────────────────────────────────────────────────────
# Step 1: Build Next.js Frontend
# ──────────────────────────────────────────────────────────────
echo -e "${GREEN}[1/4]${NC} Building Next.js frontend..."
cd "$PROJECT_DIR"

if [ "$DEV_MODE" = false ]; then
    bun install
    bun run build
    echo -e "${GREEN}  ✓${NC} Frontend built successfully"
else
    echo -e "${YELLOW}  ⚠${NC} Skipping frontend build (dev mode)"
fi

# ──────────────────────────────────────────────────────────────
# Step 2: Package Python Backend with PyInstaller
# ──────────────────────────────────────────────────────────────
if [ "$SKIP_PY" = false ]; then
    echo -e "${GREEN}[2/4]${NC} Packaging Python backend..."
    cd "$BACKEND_DIR"

    # Install PyInstaller if not present
    pip install pyinstaller 2>/dev/null || pip3 install pyinstaller 2>/dev/null

    # Install backend dependencies
    pip install -r requirements.txt 2>/dev/null || pip3 install -r requirements.txt 2>/dev/null

    # Build with PyInstaller
    # --onefile: Single executable
    # --noconsole: No console window (use --console for debugging)
    # --add-data: Include necessary data files
    pyinstaller --onefile \
        --name "backend" \
        --noconfirm \
        --clean \
        --add-data "assets:assets" \
        --add-data "i18n:i18n" \
        --add-data "mcp_config.json:." \
        --hidden-import=uvicorn.logging \
        --hidden-import=uvicorn.loops \
        --hidden-import=uvicorn.loops.auto \
        --hidden-import=uvicorn.protocols \
        --hidden-import=uvicorn.protocols.http \
        --hidden-import=uvicorn.protocols.http.auto \
        --hidden-import=uvicorn.protocols.websockets \
        --hidden-import=uvicorn.protocols.websockets.auto \
        --hidden-import=uvicorn.lifespan \
        --hidden-import=uvicorn.lifespan.on \
        --hidden-import=agentmain \
        --hidden-import=agentmain.core \
        --hidden-import=agentmain.voice.voice_avatar \
        --hidden-import=llmcore \
        --hidden-import=llmcore.clients \
        --hidden-import=llmcore.sessions \
        --collect-all edge_tts \
        --collect-all httpx \
        server.py

    # Copy the built binary to Tauri's binaries directory
    mkdir -p "$TAURI_DIR/binaries"

    # Determine the target triple based on the OS
    if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "win32" || "$OSTYPE" == "cygwin" ]]; then
        cp dist/backend.exe "$TAURI_DIR/binaries/backend-x86_64-pc-windows-msvc.exe"
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        cp dist/backend "$TAURI_DIR/binaries/backend-x86_64-apple-darwin"
        cp dist/backend "$TAURI_DIR/binaries/backend-aarch64-apple-darwin"
    else
        cp dist/backend "$TAURI_DIR/binaries/backend-x86_64-unknown-linux-gnu"
    fi

    echo -e "${GREEN}  ✓${NC} Python backend packaged"
else
    echo -e "${YELLOW}  ⚠${NC} Skipping Python backend build (--skip-py)"
fi

# ──────────────────────────────────────────────────────────────
# Step 3: Build Tauri Desktop App
# ──────────────────────────────────────────────────────────────
echo -e "${GREEN}[3/4]${NC} Building Tauri desktop app..."
cd "$PROJECT_DIR"

if [ "$DEV_MODE" = false ]; then
    # Ensure Rust target is installed
    rustup target add x86_64-pc-windows-msvc 2>/dev/null || true

    # Build with Tauri
    bun tauri build

    echo -e "${GREEN}  ✓${NC} Tauri app built"
else
    echo -e "${YELLOW}  ⚠${NC} Skipping Tauri build (dev mode)"
fi

# ──────────────────────────────────────────────────────────────
# Step 4: Collect Output
# ──────────────────────────────────────────────────────────────
echo -e "${GREEN}[4/4]${NC} Collecting output..."

mkdir -p "$DIST_DIR"

if [ -d "$TAURI_DIR/target/release/bundle" ]; then
    # Copy NSIS installer
    cp "$TAURI_DIR/target/release/bundle/nsis/"*.exe "$DIST_DIR/" 2>/dev/null || true

    # Copy MSI installer
    cp "$TAURI_DIR/target/release/bundle/msi/"*.msi "$DIST_DIR/" 2>/dev/null || true

    # Copy standalone exe
    cp "$TAURI_DIR/target/release/GenericAgent.exe" "$DIST_DIR/" 2>/dev/null || true

    echo -e "${GREEN}  ✓${NC} Output collected in $DIST_DIR/"
    echo ""
    echo -e "${PURPLE}════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}  Build complete!${NC}"
    echo ""
    echo -e "  Installer: ${YELLOW}$DIST_DIR/GenericAgent_1.2.0_x64-setup.exe${NC}"
    echo -e "  Portable:  ${YELLOW}$DIST_DIR/GenericAgent.exe${NC}"
    echo -e "${PURPLE}════════════════════════════════════════════════════${NC}"
else
    echo -e "${YELLOW}  ⚠${NC} No bundle found. Build may have failed or was skipped."
fi

echo ""
echo -e "${GREEN}Done!${NC}"
