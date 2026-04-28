#!/bin/bash
# WinKey Installer
# Sets up desktop entry and optional autostart

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DESKTOP_FILE="$HOME/.local/share/applications/winkey.desktop"
AUTOSTART_FILE="$HOME/.config/autostart/winkey.desktop"
ICON_DIR="$HOME/.local/share/icons/hicolor/scalable/apps"

echo "╔══════════════════════════════════════════════════╗"
echo "║         WinKey Installer                         ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""

# Make main script executable
chmod +x "$SCRIPT_DIR/winkey.py"

# Install icon
mkdir -p "$ICON_DIR"
cp "$SCRIPT_DIR/data/icons/winkey.svg" "$ICON_DIR/winkey.svg"
echo "✓ Icon installed"

# Create desktop entry
mkdir -p "$(dirname "$DESKTOP_FILE")"
cat > "$DESKTOP_FILE" << EOF
[Desktop Entry]
Type=Application
Name=WinKey
GenericName=Input Source Switcher
Comment=Hold Super key to temporarily switch to English input
Exec=python3 ${SCRIPT_DIR}/winkey.py
Icon=winkey
Terminal=false
Categories=Utility;Settings;
Keywords=keyboard;input;language;switch;super;
StartupNotify=true
EOF
echo "✓ Desktop entry installed"

# Ask about autostart
read -p "Enable auto-start on login? [y/N] " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    mkdir -p "$(dirname "$AUTOSTART_FILE")"
    cp "$DESKTOP_FILE" "$AUTOSTART_FILE"
    echo "X-GNOME-Autostart-enabled=true" >> "$AUTOSTART_FILE"
    echo "✓ Autostart enabled"
fi

# Update icon cache
gtk-update-icon-cache -f -t "$HOME/.local/share/icons/hicolor" 2>/dev/null || true

echo ""
echo "✓ Installation complete!"
echo "  You can now launch WinKey from your application menu."
echo "  Or run: python3 ${SCRIPT_DIR}/winkey.py"
