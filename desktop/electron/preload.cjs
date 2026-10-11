const { contextBridge, ipcRenderer } = require('electron');
contextBridge.exposeInMainWorld('sentinel', {
  request: (path, body) => ipcRenderer.invoke('bridge:request', path, body),
  connection: () => ipcRenderer.invoke('bridge:connection'),
  configure: url => ipcRenderer.invoke('bridge:configure', url),
  login: () => ipcRenderer.invoke('bridge:login'),
  notify: () => ipcRenderer.invoke('app:notify'),
  exportReport: data => ipcRenderer.invoke('app:export', data)
});
