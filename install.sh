#!/usr/bin/env bash
# install.sh — ssPrayerTime / PrayerSheetProcess installer
# Run this once after cloning to set up dependencies and the API key.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== PrayerSheetProcess Installer ==="
echo

# ── System packages ────────────────────────────────────────────────────────────

echo "Checking system packages..."

MISSING=()
for pkg in python3 pandoc aspell; do
    if ! command -v "$pkg" &>/dev/null; then
        MISSING+=("$pkg")
    fi
done

# python3-tk check (import, not command)
if ! python3 -c "import tkinter" &>/dev/null 2>&1; then
    MISSING+=("python3-tk")
fi

# aspell-en check
if ! aspell dump master 2>/dev/null | head -1 &>/dev/null; then
    MISSING+=("aspell-en")
fi

if [ ${#MISSING[@]} -gt 0 ]; then
    echo "  Missing: ${MISSING[*]}"
    echo "  Installing via apt..."
    sudo apt-get install -y "${MISSING[@]}"
else
    echo "  python3, pandoc, aspell, python3-tk — OK"
fi

# ── External tools (must be installed separately) ─────────────────────────────

echo
echo "Checking external tools..."

WARN=0
if ! command -v convertmd &>/dev/null; then
    echo "  WARNING: 'convertmd' not found. Install it before using Prepare Document."
    WARN=1
else
    echo "  convertmd — OK"
fi

if ! command -v rapumamd &>/dev/null; then
    echo "  WARNING: 'rapumamd' not found. Install it before using Open in rapumamd."
    WARN=1
else
    echo "  rapumamd — OK"
fi

if [ $WARN -eq 1 ]; then
    echo
    echo "  These tools are not available via apt. See their respective project"
    echo "  pages for installation instructions."
fi

# ── Python virtual environment ─────────────────────────────────────────────────

echo
echo "Setting up Python virtual environment..."

if [ ! -d ".venv" ]; then
    python3 -m venv .venv
    echo "  Created .venv"
else
    echo "  .venv already exists — skipping create"
fi

echo "  Installing Python packages..."
.venv/bin/pip install --quiet --upgrade pip
.venv/bin/pip install --quiet anthropic
echo "  anthropic — OK"

# ── Anthropic API key ──────────────────────────────────────────────────────────

echo
if [ -f ".env" ] && grep -q "ANTHROPIC_API_KEY=" .env 2>/dev/null; then
    echo "API key: .env already exists — skipping."
else
    echo "An Anthropic API key is required for the Prepare Document step."
    echo "Get one at https://console.anthropic.com"
    echo
    read -rp "Enter your Anthropic API key (or press Enter to skip): " API_KEY
    if [ -n "$API_KEY" ]; then
        echo "ANTHROPIC_API_KEY=$API_KEY" > .env
        chmod 600 .env
        echo "  Saved to .env"
    else
        echo "  Skipped. Create .env manually:  echo 'ANTHROPIC_API_KEY=your-key' > .env"
    fi
fi

# ── Folder structure ───────────────────────────────────────────────────────────

echo
echo "Ensuring required directories exist..."
mkdir -p input archive
echo "  input/, archive/ — OK"

# ── Done ───────────────────────────────────────────────────────────────────────

echo
echo "=== Installation complete ==="
echo
echo "To launch the app:"
echo "  python3 prayer_sheet.py"
echo
