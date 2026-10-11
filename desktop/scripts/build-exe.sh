#!/usr/bin/env bash
# One-step build of the Sentinel Linux executable: frontend, frozen Python bridge, then Electron packages.
# Usage: desktop/scripts/build-exe.sh [dir|dist]   (dir = unpacked app only; dist = AppImage + .deb)
set -euo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"
cd "$HERE"
npm ci
node node_modules/electron/install.js
npm run build
"$HERE/scripts/build-bridge.sh"
if [ "${1:-dist}" = dir ]; then npm run pack; else npm run dist; fi
ls -lh release
