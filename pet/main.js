// Electron main process for the Krish desktop pet.
//
// A small frameless, transparent, always-on-top, skip-taskbar window pinned to
// the bottom-right corner. The window ignores mouse events by default (clicks
// fall through to the desktop); the renderer raycasts the 3D figure and toggles
// that off while the cursor is over the character so it can be dragged/clicked.
//
// Target: Ubuntu X11, where transparent + always-on-top + click-through work.

const path = require('path');
const { app, BrowserWindow, Tray, Menu, ipcMain, screen, nativeImage } = require('electron');

const WIN_W = 240;
const WIN_H = 300;
const MARGIN = 24; // gap from the screen edge

let win = null;
let tray = null;

// Drag state: where the window and cursor were when a drag started, in screen
// coordinates, so we can move the window 1:1 with the cursor.
let dragOrigin = null; // { winX, winY, mouseX, mouseY }

function bottomRightPosition() {
  // workAreaSize excludes panels/docks, so we sit above the taskbar.
  const { workArea } = screen.getPrimaryDisplay();
  return {
    x: workArea.x + workArea.width - WIN_W - MARGIN,
    y: workArea.y + workArea.height - WIN_H - MARGIN,
  };
}

function createWindow() {
  const { x, y } = bottomRightPosition();

  win = new BrowserWindow({
    width: WIN_W,
    height: WIN_H,
    x,
    y,
    frame: false,
    transparent: true,
    backgroundColor: '#00000000',
    alwaysOnTop: true,
    skipTaskbar: true,
    resizable: false,
    movable: true,
    hasShadow: false,
    focusable: true,
    fullscreenable: false,
    webPreferences: {
      nodeIntegration: true,
      contextIsolation: false,
    },
  });

  // Sit above normal windows (incl. fullscreen-ish) without stealing focus.
  win.setAlwaysOnTop(true, 'screen-saver');
  win.setVisibleOnAllWorkspaces(true, { visibleOnFullScreen: true });

  // Default: let clicks pass through to whatever is behind us. {forward:true}
  // keeps delivering mousemove to the renderer so it can detect hover.
  win.setIgnoreMouseEvents(true, { forward: true });

  win.loadFile(path.join(__dirname, 'renderer', 'index.html'));
}

function createTray() {
  const iconPath = path.join(__dirname, 'assets', 'icon.png');
  let image = nativeImage.createFromPath(iconPath);
  if (image.isEmpty()) {
    // Fallback so the app still runs if the icon asset is missing.
    image = nativeImage.createEmpty();
  }
  tray = new Tray(image);
  tray.setToolTip('Krish — desktop pet');

  const menu = Menu.buildFromTemplate([
    {
      label: 'Show / Hide',
      click: () => {
        if (!win) return;
        if (win.isVisible()) win.hide();
        else win.show();
      },
    },
    { type: 'separator' },
    { label: 'Quit', click: () => app.quit() },
  ]);
  tray.setContextMenu(menu);

  // Left-click the tray icon also toggles visibility.
  tray.on('click', () => {
    if (!win) return;
    if (win.isVisible()) win.hide();
    else win.show();
  });
}

// --- IPC from renderer --------------------------------------------------------

// Toggle click-through. ignore=true -> events fall through to the desktop.
ipcMain.on('set-ignore-mouse', (_event, ignore) => {
  if (!win) return;
  if (ignore) win.setIgnoreMouseEvents(true, { forward: true });
  else win.setIgnoreMouseEvents(false);
});

ipcMain.on('drag-start', (_event, { mouseX, mouseY }) => {
  if (!win) return;
  const [winX, winY] = win.getPosition();
  dragOrigin = { winX, winY, mouseX, mouseY };
});

ipcMain.on('drag-move', (_event, { mouseX, mouseY }) => {
  if (!win || !dragOrigin) return;
  const dx = mouseX - dragOrigin.mouseX;
  const dy = mouseY - dragOrigin.mouseY;
  win.setPosition(dragOrigin.winX + dx, dragOrigin.winY + dy);
});

ipcMain.on('drag-end', () => {
  dragOrigin = null;
});

// --- app lifecycle ------------------------------------------------------------

app.whenReady().then(() => {
  createWindow();
  createTray();
});

// Tray-driven app: don't quit just because the window is hidden/closed.
app.on('window-all-closed', () => {});
