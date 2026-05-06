#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════
# GenericAgent — Build Sidecar Backend (Shell Script)
#
# Packages the Python FastAPI backend as a standalone executable using
# PyInstaller, then copies it to src-tauri/binaries/ with the correct
# Tauri target-triple naming convention.
#
# Usage:
#   bash scripts/build-sidecar.sh                       # Auto-detect OS
#   bash scripts/build-sidecar.sh --target-windows      # For Windows
#   bash scripts/build-sidecar.sh --target-linux        # For Linux
#   bash scripts/build-sidecar.sh --target-macos        # For macOS
#   bash scripts/build-sidecar.sh --clean               # Clean build artifacts
#   bash scripts/build-sidecar.sh --skip-deps           # Skip pip install
#
# The output binary is placed at:
#   src-tauri/binaries/backend-x86_64-pc-windows-msvc.exe   (Windows)
#   src-tauri/binaries/backend-x86_64-unknown-linux-gnu     (Linux)
#   src-tauri/binaries/backend-x86_64-apple-darwin          (macOS Intel)
#   src-tauri/binaries/backend-aarch64-apple-darwin         (macOS ARM)
# ═══════════════════════════════════════════════════════════════════════

set -euo pipefail

# ─── Colors ────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m' # No Color

# ─── Defaults ──────────────────────────────────────────────────────────
TARGET=""
CLEAN=false
SKIP_DEPS=false

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
BACKEND_DIR="$PROJECT_DIR/upload/GenericAgent-Desktop-v1.2.0"
BINARIES_DIR="$PROJECT_DIR/src-tauri/binaries"
LAUNCHER_SCRIPT="$BINARIES_DIR/launch_backend.py"

# ─── Parse Arguments ──────────────────────────────────────────────────
for arg in "$@"; do
    case $arg in
        --target-windows) TARGET="windows" ;;
        --target-linux)   TARGET="linux" ;;
        --target-macos)   TARGET="macos" ;;
        --clean)          CLEAN=true ;;
        --skip-deps)      SKIP_DEPS=true ;;
        --help|-h)
            echo "Usage: bash scripts/build-sidecar.sh [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --target-windows   Build for Windows (x86_64-pc-windows-msvc)"
            echo "  --target-linux     Build for Linux (x86_64-unknown-linux-gnu)"
            echo "  --target-macos     Build for macOS (x86_64 + aarch64 apple-darwin)"
            echo "  --clean            Remove build artifacts before building"
            echo "  --skip-deps        Skip pip install of requirements"
            echo "  --help             Show this help message"
            exit 0
            ;;
        *) echo "Unknown argument: $arg (use --help for usage)"; exit 1 ;;
    esac
done

# ─── Banner ────────────────────────────────────────────────────────────
echo -e "${PURPLE}╔══════════════════════════════════════════════════════╗${NC}"
echo -e "${PURPLE}║     GenericAgent — Sidecar Backend Builder          ║${NC}"
echo -e "${PURPLE}╚══════════════════════════════════════════════════════╝${NC}"
echo ""

# ─── Auto-detect target if not specified ───────────────────────────────
if [ -z "$TARGET" ]; then
    case "$(uname -s)" in
        Linux*)  TARGET="linux" ;;
        Darwin*) TARGET="macos" ;;
        MINGW*|MSYS*|CYGWIN*|Windows_NT) TARGET="windows" ;;
        *) echo -e "${RED}ERROR: Unsupported OS: $(uname -s)${NC}"; exit 1 ;;
    esac
    echo -e "${BLUE}Auto-detected target: ${TARGET}${NC}"
fi

# ─── Validate prerequisites ───────────────────────────────────────────

echo -e "${GREEN}[1/6]${NC} Checking prerequisites..."

# Check Python 3.10+
PYTHON_CMD=""
for cmd in python3 python; do
    if command -v "$cmd" &>/dev/null; then
        PY_VERSION=$("$cmd" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
        PY_MAJOR=$("$cmd" -c "import sys; print(sys.version_info.major)")
        PY_MINOR=$("$cmd" -c "import sys; print(sys.version_info.minor)")
        if [ "$PY_MAJOR" -ge 3 ] && [ "$PY_MINOR" -ge 10 ]; then
            PYTHON_CMD="$cmd"
            echo -e "${GREEN}  ✓${NC} Python $PY_VERSION found ($cmd)"
            break
        else
            echo -e "${YELLOW}  ⚠${NC} $cmd is Python $PY_VERSION (need 3.10+)"
        fi
    fi
done

if [ -z "$PYTHON_CMD" ]; then
    echo -e "${RED}ERROR: Python 3.10+ not found. Install it from https://python.org${NC}"
    exit 1
fi

# Check pip
PIP_CMD=""
for cmd in pip3 pip "$PYTHON_CMD -m pip"; do
    if command -v "$cmd" &>/dev/null; then
        PIP_CMD="$cmd"
        echo -e "${GREEN}  ✓${NC} pip found ($cmd)"
        break
    fi
done

if [ -z "$PIP_CMD" ]; then
    echo -e "${RED}ERROR: pip not found. Install it: $PYTHON_CMD -m ensurepip${NC}"
    exit 1
fi

# Check backend directory
if [ ! -d "$BACKEND_DIR" ]; then
    echo -e "${RED}ERROR: Backend directory not found: $BACKEND_DIR${NC}"
    exit 1
fi
echo -e "${GREEN}  ✓${NC} Backend directory: $BACKEND_DIR"

# Check launcher script
if [ ! -f "$LAUNCHER_SCRIPT" ]; then
    echo -e "${RED}ERROR: Launcher script not found: $LAUNCHER_SCRIPT${NC}"
    exit 1
fi
echo -e "${GREEN}  ✓${NC} Launcher script: $LAUNCHER_SCRIPT"

# ─── Clean if requested ────────────────────────────────────────────────
if [ "$CLEAN" = true ]; then
    echo -e "${YELLOW}[2/6]${NC} Cleaning build artifacts..."
    rm -rf "$BACKEND_DIR/build" "$BACKEND_DIR/dist" "$BACKEND_DIR/*.spec"
    echo -e "${GREEN}  ✓${NC} Cleaned"
else
    echo -e "${BLUE}[2/6]${NC} Skipping clean (use --clean to remove artifacts)"
fi

# ─── Install dependencies ──────────────────────────────────────────────
if [ "$SKIP_DEPS" = false ]; then
    echo -e "${GREEN}[3/6]${NC} Installing dependencies..."
    $PIP_CMD install --quiet --upgrade pip
    $PIP_CMD install --quiet pyinstaller
    $PIP_CMD install --quiet -r "$BACKEND_DIR/requirements.txt"
    echo -e "${GREEN}  ✓${NC} Dependencies installed"
else
    echo -e "${YELLOW}[3/6]${NC} Skipping dependency install (--skip-deps)"
fi

# ─── Build with PyInstaller ────────────────────────────────────────────
echo -e "${GREEN}[4/6]${NC} Building sidecar with PyInstaller..."
echo -e "  Entry point: ${LAUNCHER_SCRIPT}"

cd "$BACKEND_DIR"

# Build the PyInstaller command
PYINSTALLER_CMD=(
    pyinstaller
    --onefile
    --name "backend"
    --noconfirm
    --clean
    --console
    # ── Include data directories ──
    --add-data "assets:assets"
    --add-data "i18n:i18n"
    --add-data "mcp_config.json:."
    # ── Uvicorn hidden imports (required for PyInstaller) ──
    --hidden-import=uvicorn.logging
    --hidden-import=uvicorn.loops
    --hidden-import=uvicorn.loops.auto
    --hidden-import=uvicorn.protocols
    --hidden-import=uvicorn.protocols.http
    --hidden-import=uvicorn.protocols.http.auto
    --hidden-import=uvicorn.protocols.websockets
    --hidden-import=uvicorn.protocols.websockets.auto
    --hidden-import=uvicorn.lifespan
    --hidden-import=uvicorn.lifespan.on
    # ── Agent core hidden imports ──
    --hidden-import=agentmain
    --hidden-import=agentmain.core
    --hidden-import=agentmain.voice.voice_avatar
    --hidden-import=llmcore
    --hidden-import=llmcore.clients
    --hidden-import=llmcore.sessions
    # ── Collect all data for these packages ──
    --collect-all edge_tts
    --collect-all httpx
    # ── The launcher script ──
    "$LAUNCHER_SCRIPT"
)

echo -e "  Running: ${PYINSTALLER_CMD[*]}"
echo ""

if "${PYINSTALLER_CMD[@]}"; then
    echo ""
    echo -e "${GREEN}  ✓${NC} PyInstaller build succeeded"
else
    echo ""
    echo -e "${RED}ERROR: PyInstaller build failed${NC}"
    exit 1
fi

# ─── Copy to binaries directory ────────────────────────────────────────
echo -e "${GREEN}[5/6]${NC} Copying binary to Tauri binaries directory..."

mkdir -p "$BINARIES_DIR"

case "$TARGET" in
    windows)
        if [ -f "$BACKEND_DIR/dist/backend.exe" ]; then
            cp "$BACKEND_DIR/dist/backend.exe" "$BINARIES_DIR/backend-x86_64-pc-windows-msvc.exe"
            echo -e "${GREEN}  ✓${NC} Copied: backend-x86_64-pc-windows-msvc.exe"
        else
            echo -e "${RED}ERROR: backend.exe not found in dist/${NC}"
            exit 1
        fi
        ;;
    linux)
        if [ -f "$BACKEND_DIR/dist/backend" ]; then
            cp "$BACKEND_DIR/dist/backend" "$BINARIES_DIR/backend-x86_64-unknown-linux-gnu"
            chmod +x "$BINARIES_DIR/backend-x86_64-unknown-linux-gnu"
            echo -e "${GREEN}  ✓${NC} Copied: backend-x86_64-unknown-linux-gnu"
        else
            echo -e "${RED}ERROR: backend not found in dist/${NC}"
            exit 1
        fi
        ;;
    macos)
        if [ -f "$BACKEND_DIR/dist/backend" ]; then
            # Copy for both Intel and ARM (same binary on Apple Silicon with Rosetta)
            cp "$BACKEND_DIR/dist/backend" "$BINARIES_DIR/backend-x86_64-apple-darwin"
            cp "$BACKEND_DIR/dist/backend" "$BINARIES_DIR/backend-aarch64-apple-darwin"
            chmod +x "$BINARIES_DIR/backend-x86_64-apple-darwin"
            chmod +x "$BINARIES_DIR/backend-aarch64-apple-darwin"
            echo -e "${GREEN}  ✓${NC} Copied: backend-x86_64-apple-darwin"
            echo -e "${GREEN}  ✓${NC} Copied: backend-aarch64-apple-darwin"
        else
            echo -e "${RED}ERROR: backend not found in dist/${NC}"
            exit 1
        fi
        ;;
    *)
        echo -e "${RED}ERROR: Unknown target: $TARGET${NC}"
        exit 1
        ;;
esac

# ─── Verify output ─────────────────────────────────────────────────────
echo -e "${GREEN}[6/6]${NC} Verifying output..."

case "$TARGET" in
    windows) OUTPUT_FILE="$BINARIES_DIR/backend-x86_64-pc-windows-msvc.exe" ;;
    linux)   OUTPUT_FILE="$BINARIES_DIR/backend-x86_64-unknown-linux-gnu" ;;
    macos)   OUTPUT_FILE="$BINARIES_DIR/backend-x86_64-apple-darwin" ;;
esac

if [ -f "$OUTPUT_FILE" ]; then
    FILE_SIZE=$(du -h "$OUTPUT_FILE" | cut -f1)
    echo -e "${GREEN}  ✓${NC} Output: $OUTPUT_FILE ($FILE_SIZE)"
else
    echo -e "${RED}ERROR: Output file not found: $OUTPUT_FILE${NC}"
    exit 1
fi

# ─── Done ──────────────────────────────────────────────────────────────
echo ""
echo -e "${PURPLE}════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  Sidecar build complete!${NC}"
echo ""
echo -e "  Target:     ${YELLOW}$TARGET${NC}"
echo -e "  Output:     ${YELLOW}$OUTPUT_FILE${NC}"
echo -e "  Size:       ${YELLOW}$FILE_SIZE${NC}"
echo ""
echo -e "  Next: Run ${BLUE}bun tauri build${NC} to build the desktop app"
echo -e "${PURPLE}════════════════════════════════════════════════════════${NC}"
