#!/usr/bin/env bash
# dependency_audit.sh — Audit Python dependencies for known vulnerabilities.
#
# Runs pip-audit and safety check against the project's requirements.
#
# Usage:
#   ./scripts/dependency_audit.sh
#
# Requires: pip install pip-audit safety
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "=== GenericAgent Dependency Audit ==="
echo "Project root: $PROJECT_ROOT"

cd "$PROJECT_ROOT"

# --- pip-audit ---
echo ""
echo "--- pip-audit ---"
if command -v pip-audit &>/dev/null; then
    pip-audit -r requirements.txt --desc 2>/dev/null || pip-audit --desc 2>/dev/null || {
        echo "WARNING: pip-audit encountered issues. Install requirements first."
    }
else
    echo "SKIP: pip-audit not installed. Run: pip install pip-audit"
fi

# --- safety ---
echo ""
echo "--- safety ---"
if command -v safety &>/dev/null; then
    safety check -r requirements.txt 2>/dev/null || safety check 2>/dev/null || {
        echo "WARNING: safety check encountered issues."
    }
else
    echo "SKIP: safety not installed. Run: pip install safety"
fi

echo ""
echo "=== Audit complete ==="
