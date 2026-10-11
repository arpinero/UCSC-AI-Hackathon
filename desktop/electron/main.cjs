const { app, BrowserWindow, ipcMain, session, dialog, Notification } = require('electron');
const path = require('node:path');
const fs = require('node:fs');
const { validateBase, validatePath } = require('./security.cjs');
const { resolveCommand, startBridge, waitForHealth } = require('./bridge-process.cjs');
let main, base = 'http://127.0.0.1:8787', connectionFile, csrf='', bridge = null;
app.setName('Sentinel');
app.setAppUserModelId('org.ucsc.sentinel');
function trusted(event) {
  if (!main || event.sender !== main.webContents || event.senderFrame !== main.webContents.mainFrame) throw new Error('Untrusted renderer');
}
function fail(message) {
  dialog.showErrorBox('Sentinel could not start', message);
  app.exit(1);
}
// Starts the bundled bridge on a free loopback port. SENTINEL_USE_SAVED_CONNECTION=1 instead reuses the
// last bridge URL saved in Connection settings (a bridge you started yourself, or a private tunnel).
async function connectBridge() {
  connectionFile = path.join(app.getPath('userData'), 'connection.json');
  if (process.env.SENTINEL_USE_SAVED_CONNECTION === '1') {
    try { base = validateBase(JSON.parse(fs.readFileSync(connectionFile, 'utf8')).url); return; } catch {}
  }
  const command = resolveCommand({ packaged: app.isPackaged, resourcesPath: process.resourcesPath, repoRoot: path.join(__dirname, '..', '..') });
  const started = await startBridge({ ...command, dataDir: path.join(app.getPath('userData'), 'reports') });
  bridge = started.child;
  base = 'http://127.0.0.1:' + started.port;
  if (!(await waitForHealth(base))) throw new Error('The Sentinel bridge started but did not answer health checks.');
}
function stopBridge() {
  if (bridge && bridge.exitCode === null) bridge.kill();
  bridge = null;
}
app.on('before-quit', stopBridge);
app.on('quit', stopBridge);
const gotLock = app.requestSingleInstanceLock();
if (!gotLock) app.quit();
app.whenReady().then(async () => {
  if (!gotLock) return;
  try { await connectBridge(); } catch (error) { return fail(error.message); }
  if (bridge) bridge.on('exit', code => { if (main && !main.isDestroyed()) fail('The Sentinel bridge stopped unexpectedly (exit ' + code + ').'); });
  const transport = session.fromPartition('persist:sentinel-connection');
  main = new BrowserWindow({ width: 1460, height: 980, minWidth: 980, minHeight: 680,
    title: 'Sentinel — Incident workspace', backgroundColor: '#f8f7f4',
    webPreferences: { preload: path.join(__dirname, 'preload.cjs'), contextIsolation: true, nodeIntegration: false, sandbox: true } });
  main.setMenuBarVisibility(false);
  main.webContents.setWindowOpenHandler(() => ({ action: 'deny' }));
  main.webContents.on('will-navigate', event => event.preventDefault());
  main.webContents.session.setPermissionRequestHandler((_web, _permission, callback) => callback(false));
  ipcMain.handle('bridge:connection', event => { trusted(event); return base; });
  ipcMain.handle('bridge:configure', (event, url) => {
    trusted(event); base = validateBase(url); csrf='';
    fs.writeFileSync(connectionFile, JSON.stringify({url: base})); return base;
  });
  ipcMain.handle('bridge:request', async (event, endpoint, body) => {
    trusted(event); validatePath(endpoint);
    const encoded = body === undefined ? undefined : JSON.stringify(body);
    if (encoded && Buffer.byteLength(encoded) > 64000) throw new Error('Request too large');
    const response = await transport.fetch(base + endpoint, { method: encoded ? 'POST' : 'GET',
      headers: { 'Content-Type': 'application/json', 'X-Sentinel-CSRF': csrf }, body: encoded,
      redirect: 'error', signal: AbortSignal.timeout(endpoint.endsWith('/chat') ? 250000 : 15000) });
    if (!(response.headers.get('content-type') || '').includes('application/json')) throw new Error('Sign in to the private tunnel in Connection settings.');
    const result = await response.json();
    if(endpoint==='/api/health')csrf=result.csrf_token||'';
    if (!response.ok) throw new Error(result.error || 'Bridge request failed');
    return result;
  });
  ipcMain.handle('bridge:login', event => {
    trusted(event);
    if (!base.startsWith('https://')) throw new Error('Local connections do not require tunnel sign-in.');
    const login = new BrowserWindow({ width: 950, height: 760, parent: main,
      webPreferences: { partition: 'persist:sentinel-connection', contextIsolation: true, nodeIntegration: false, sandbox: true } });
    login.webContents.setWindowOpenHandler(() => ({action:'deny'}));
    login.loadURL(base + '/api/health');
  });
  ipcMain.handle('app:notify', event => {
    trusted(event);
    if (!main.isFocused()) {
      const notice = new Notification({title:'Sentinel · review required',body:'An incident plan is waiting for your decision.'});
      notice.on('click', () => { main.show(); main.focus(); }); notice.show();
    }
  });
  ipcMain.handle('app:export', async (event, data) => {
    trusted(event); const raw = JSON.stringify(data, null, 2);
    if (raw.length > 10000000) throw new Error('Report too large');
    const result = await dialog.showSaveDialog(main, { defaultPath: 'sentinel-incident.json', filters:[{name:'Incident report',extensions:['json']}] });
    if (result.canceled) return false;
    await fs.promises.writeFile(result.filePath, raw); return true;
  });
  main.loadFile(path.join(__dirname, '../web-build/index.html'));
});
app.on('window-all-closed', () => app.quit());
