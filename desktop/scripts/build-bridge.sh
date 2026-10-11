#!/usr/bin/env bash
# Freezes the Python bridge for the CURRENT architecture (build on the GX10 for linux-arm64).
set -euo pipefail
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
VENV="${SENTINEL_BUILD_VENV:-$HOME/sentinel-build-venv}"
if [ ! -x "$VENV/bin/pyinstaller" ]; then
  python3 -m venv "$VENV"
  "$VENV/bin/pip" install --quiet pyinstaller
fi
cd "$REPO"
rm -rf desktop/build/py desktop/build/work
"$VENV/bin/pyinstaller" --noconfirm --distpath desktop/build/py --workpath desktop/build/work desktop/packaging/sentinel-server.spec
