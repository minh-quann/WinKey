#!/bin/bash
# WinKey Uninstaller

echo "Removing WinKey..."

rm -f "$HOME/.local/share/applications/winkey.desktop"
rm -f "$HOME/.config/autostart/winkey.desktop"
rm -f "$HOME/.local/share/icons/hicolor/scalable/apps/winkey.svg"
gtk-update-icon-cache -f -t "$HOME/.local/share/icons/hicolor" 2>/dev/null || true

echo "✓ WinKey removed."
echo "  Note: Source files are still at $(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
