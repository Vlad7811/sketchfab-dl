const { app, BrowserWindow, ipcMain, session, dialog } = require('electron');
const path = require('path');
const fs = require('fs');
const os = require('os');

let mainWin;

function createWindow() {
  mainWin = new BrowserWindow({
    width: 1200,
    height: 860,
    minWidth: 900,
    minHeight: 600,
    backgroundColor: '#0a0a0f',
    titleBarStyle: 'hidden',
    webPreferences: {
      nodeIntegration: true,
      contextIsolation: false,
      webviewTag: true,
    },
  });

  session.defaultSession.webRequest.onHeadersReceived((details, callback) => {
    const h = { ...details.responseHeaders };
    delete h['content-security-policy'];
    delete h['Content-Security-Policy'];
    delete h['x-frame-options'];
    delete h['X-Frame-Options'];
    callback({ responseHeaders: h });
  });

  mainWin.loadFile('index.html');
}

// Save zip file to Downloads folder
ipcMain.on('save-zip', (event, { buffer, name }) => {
  const downloadsDir = app.getPath('downloads');
  const filePath = path.join(downloadsDir, name);
  try {
    fs.writeFileSync(filePath, Buffer.from(buffer));
    mainWin.webContents.send('save-done', filePath);
  } catch (err) {
    mainWin.webContents.send('save-done', 'Ошибка: ' + err.message);
  }
});

ipcMain.on('minimize', () => mainWin.minimize());
ipcMain.on('maximize', () => mainWin.isMaximized() ? mainWin.unmaximize() : mainWin.maximize());
ipcMain.on('close', () => mainWin.close());

app.whenReady().then(createWindow);
app.on('window-all-closed', () => { if (process.platform !== 'darwin') app.quit(); });
