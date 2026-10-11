#!/usr/bin/env bash
# Adds a Sentinel launcher to the app menu and the desktop, and pins it to the dock. Safe to run again.
set -euo pipefail
HERE="$(cd "$(dirname "$(readlink -f "$0")")/.." && pwd)"
ICON="$HERE/build-resources/icon.png"
FILE="$HOME/.local/share/applications/sentinel.desktop"
mkdir -p "$(dirname "$FILE")"
cat > "$FILE" <<DESK
[Desktop Entry]
Type=Application
Name=Sentinel
Comment=Incident response council (live local models)
Exec=$HERE/scripts/sentinel-live.sh
Icon=$ICON
Terminal=false
Categories=Security;Utility;
StartupWMClass=Sentinel
DESK
chmod +x "$FILE"
DESKTOP_DIR="$(xdg-user-dir DESKTOP 2>/dev/null || echo "$HOME/Desktop")"
if [ -d "$DESKTOP_DIR" ]; then
  cp "$FILE" "$DESKTOP_DIR/Sentinel.desktop"
  chmod +x "$DESKTOP_DIR/Sentinel.desktop"
  gio set "$DESKTOP_DIR/Sentinel.desktop" metadata::trusted true 2>/dev/null || true
fi
update-desktop-database "$HOME/.local/share/applications" 2>/dev/null || true
if command -v gsettings >/dev/null 2>&1; then
  CURRENT="$(gsettings get org.gnome.shell favorite-apps 2>/dev/null || echo '')"
  case "$CURRENT" in
    *sentinel.desktop*|'') ;;
    *) gsettings set org.gnome.shell favorite-apps "$(echo "$CURRENT" | sed "s/\]$/, 'sentinel.desktop']/")" 2>/dev/null || true ;;
  esac
fi
echo "Installed: $FILE"
[ -f "$DESKTOP_DIR/Sentinel.desktop" ] && echo "Desktop icon: $DESKTOP_DIR/Sentinel.desktop"
