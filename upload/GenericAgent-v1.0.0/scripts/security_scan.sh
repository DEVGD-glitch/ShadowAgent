#!/usr/bin/env bash
# ══════════════════════════════════════════════════════════════════════════
#  GenericAgent — Security Scan Script
#  Runs SAST (Static Application Security Testing) analysis
# ══════════════════════════════════════════════════════════════════════════

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "╔════════════════════════════════════════════════════════════╗"
echo "║        GenericAgent — Security Scan                       ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

# ── Bandit (SAST) ──────────────────────────────────────────────────────────
echo "🔍 Running Bandit SAST scan..."
if command -v bandit &> /dev/null; then
    bandit -r "$PROJECT_DIR" -c "$PROJECT_DIR/.bandit.yml" -f txt 2>&1 || true
    echo "✅ Bandit scan complete"
else
    echo "⚠️  Bandit not installed. Install with: pip install bandit"
fi

echo ""

# ── pip-audit (Dependency Audit) ───────────────────────────────────────────
echo "🔍 Running pip-audit dependency scan..."
if command -v pip-audit &> /dev/null; then
    pip-audit --desc 2>&1 || true
    echo "✅ Dependency audit complete"
else
    echo "⚠️  pip-audit not installed. Install with: pip install pip-audit"
fi

echo ""

# ── Safety (Known Vulnerability Check) ─────────────────────────────────────
echo "🔍 Running safety vulnerability check..."
if command -v safety &> /dev/null; then
    safety check --json 2>&1 || true
    echo "✅ Safety check complete"
else
    echo "⚠️  safety not installed. Install with: pip install safety"
fi

echo ""
echo "╔════════════════════════════════════════════════════════════╗"
echo "║        Security scan complete                             ║"
echo "╚════════════════════════════════════════════════════════════╝"
