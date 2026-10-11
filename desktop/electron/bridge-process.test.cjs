const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');
const fs = require('node:fs');
const os = require('node:os');
const { parsePort, resolveCommand, startBridge, waitForHealth } = require('./bridge-process.cjs');
test('parses only the loopback port the bridge announces', () => {
  assert.equal(parsePort('Sentinel bridge listening at http://127.0.0.1:45907\n'), 45907);
  for (const text of ['', 'listening at http://0.0.0.0:80', 'listening at http://127.0.0.1:0', 'listening at http://127.0.0.1:99999']) assert.equal(parsePort(text), null);
});
test('packaged builds use the bundled executable and fail loudly when it is missing', () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'sentinel-'));
  assert.throws(() => resolveCommand({ packaged: true, resourcesPath: dir, repoRoot: dir }), /missing/);
  fs.mkdirSync(path.join(dir, 'sentinel-server'));
  fs.writeFileSync(path.join(dir, 'sentinel-server', 'sentinel-server'), '');
  assert.equal(resolveCommand({ packaged: true, resourcesPath: dir, repoRoot: dir }).command, path.join(dir, 'sentinel-server', 'sentinel-server'));
});
test('development runs the Python entry point from the repository root', () => {
  const result = resolveCommand({ packaged: false, repoRoot: '/repo', platform: 'linux', python: '' });
  assert.deepEqual([result.command, result.args, result.cwd], ['python3', ['-m', 'desktop.sentinel_server'], '/repo']);
});
test('startBridge resolves with the announced port and reports early exits', async () => {
  const ok = await startBridge({ command: process.execPath, cwd: os.tmpdir(), dataDir: os.tmpdir(),
    args: ['-e', "console.log('Sentinel bridge listening at http://127.0.0.1:4321'); setTimeout(()=>{},3000)", '--'] });
  assert.equal(ok.port, 4321); ok.child.kill();
  await assert.rejects(startBridge({ command: process.execPath, cwd: os.tmpdir(), dataDir: os.tmpdir(), args: ['-e', 'process.exit(3)', '--'] }), /exit 3/);
});
test('waitForHealth retries then gives up', async () => {
  let calls = 0;
  assert.equal(await waitForHealth('http://x', async () => ({ ok: ++calls > 2 }), 5, 1), true);
  assert.equal(await waitForHealth('http://x', async () => ({ ok: false }), 2, 1), false);
});
