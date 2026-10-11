#!/usr/bin/env bash
# Launches Sentinel configured for the local GX10 live services. Any variable already set wins.
# Find the app next to this repo's build (release/next first, then release), or at the .deb install path.
HERE="$(cd "$(dirname "$(readlink -f "$0")")/.." && pwd)"
APP=""
for candidate in "$HERE/release/next/linux-arm64-unpacked/sentinel" "$HERE/release/linux-arm64-unpacked/sentinel" /opt/Sentinel/sentinel; do
  if [ -x "$candidate" ]; then APP="$candidate"; break; fi
done
if [ -z "$APP" ]; then echo "Sentinel is not built. Run desktop/scripts/build-exe.sh first." >&2; exit 1; fi
export COUNCIL_MODEL="${COUNCIL_MODEL:-gemma4:26b}"
export COUNCIL_FORENSICS_URL="${COUNCIL_FORENSICS_URL:-http://127.0.0.1:8747}"
# The Forensics API does not report its model. This is the model its service is configured to use (llama.cpp on :8000).
export COUNCIL_FORENSICS_MODEL="${COUNCIL_FORENSICS_MODEL:-fdtn-ai/Foundation-Sec-8B-Instruct}"
exec "$APP" "$@"
