#!/bin/sh
# Chromium's setuid sandbox helper must be root-owned with mode 4755 for the process sandbox to work.
chmod 4755 /opt/Sentinel/chrome-sandbox 2>/dev/null || true
exit 0
