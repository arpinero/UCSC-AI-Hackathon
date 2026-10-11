// electron-builder afterPack hook (Linux): install a launcher in place of the Electron binary.
// Chromium checks its setuid sandbox before any JavaScript runs, so the choice must be made by a launcher.
// The real binary is kept as `<name>.bin`. The sandbox stays on whenever chrome-sandbox is root-owned and setuid.
const fs = require('node:fs');
const path = require('node:path');

exports.default = async function afterPack(context) {
  if (context.electronPlatformName !== 'linux') return;
  const name = context.packager.executableName;
  const real = path.join(context.appOutDir, name);
  fs.renameSync(real, real + '.bin');
  fs.writeFileSync(real, `#!/bin/sh
HERE="$(dirname "$(readlink -f "$0")")"
SANDBOX="$HERE/chrome-sandbox"
if [ -u "$SANDBOX" ] && [ "$(stat -c %u "$SANDBOX" 2>/dev/null)" = "0" ]; then
  exec "$HERE/${name}.bin" "$@"
fi
# Not installed setuid root (AppImage, unpacked build): run without Chromium's process sandbox.
# Renderer isolation, the CSP and the IPC route allowlist remain in force.
exec "$HERE/${name}.bin" --no-sandbox "$@"
`, { mode: 0o755 });
};
