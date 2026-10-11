// Starts and supervises the bundled Sentinel bridge (a PyInstaller build, or Python from source in development).
const path = require('node:path');
const fs = require('node:fs');
const { spawn } = require('node:child_process');

function parsePort(text) {
  const match = /listening at http:\/\/127\.0\.0\.1:(\d{1,5})/.exec(String(text));
  const port = match ? Number(match[1]) : 0;
  return port > 0 && port < 65536 ? port : null;
}

function resolveCommand({ packaged, resourcesPath, repoRoot, platform = process.platform, python = process.env.PYTHON }) {
  if (packaged) {
    const exe = path.join(resourcesPath, 'sentinel-server', platform === 'win32' ? 'sentinel-server.exe' : 'sentinel-server');
    if (!fs.existsSync(exe)) throw new Error('The bundled Sentinel bridge is missing from this installation: ' + exe);
    return { command: exe, args: [], cwd: path.dirname(exe) };
  }
  return { command: python || (platform === 'win32' ? 'python' : 'python3'), args: ['-m', 'desktop.sentinel_server'], cwd: repoRoot };
}

// Resolves { child, port } once the bridge reports its loopback port. Rejects if it exits or stays silent.
function startBridge({ command, args, cwd, dataDir, env = process.env, timeoutMs = 20000 }) {
  return new Promise((resolve, reject) => {
    const child = spawn(command, [...args, '--port', '0', '--data', dataDir], {
      cwd, env: { ...env, PYTHONUNBUFFERED: '1', PYTHONPATH: cwd }, stdio: ['ignore', 'pipe', 'pipe'] });
    let output = '', done = false;
    const finish = (fn, value) => { if (done) return; done = true; clearTimeout(timer); fn(value); };
    const timer = setTimeout(() => { child.kill(); finish(reject, new Error('The Sentinel bridge did not start within ' + timeoutMs / 1000 + ' seconds.\n' + output.slice(-800))); }, timeoutMs);
    child.stdout.on('data', chunk => {
      output += chunk;
      const port = parsePort(output);
      if (port) finish(resolve, { child, port });
    });
    child.stderr.on('data', chunk => { output += chunk; });
    child.on('error', error => finish(reject, error));
    child.on('exit', code => finish(reject, new Error('The Sentinel bridge stopped (exit ' + code + ').\n' + output.slice(-800))));
  });
}

async function waitForHealth(base, fetchImpl = fetch, attempts = 40, delayMs = 250) {
  for (let i = 0; i < attempts; i++) {
    try {
      const response = await fetchImpl(base + '/api/health', { signal: AbortSignal.timeout(2000) });
      if (response.ok) return true;
    } catch {}
    await new Promise(resolve => setTimeout(resolve, delayMs));
  }
  return false;
}

module.exports = { parsePort, resolveCommand, startBridge, waitForHealth };
