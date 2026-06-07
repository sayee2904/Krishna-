// Preload: the only bridge between the (sandboxed, context-isolated) renderer
// and the main process. Exposes a tiny, explicit API on window.petAPI so the
// renderer never needs Node integration.

const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('petAPI', {
  // Click-through: true => mouse events fall through to the desktop.
  setIgnoreMouse: (ignore) => ipcRenderer.send('set-ignore-mouse', ignore),

  // Drag the window 1:1 with the cursor (screen coordinates).
  dragStart: (mouseX, mouseY) => ipcRenderer.send('drag-start', { mouseX, mouseY }),
  dragMove: (mouseX, mouseY) => ipcRenderer.send('drag-move', { mouseX, mouseY }),
  dragEnd: () => ipcRenderer.send('drag-end'),

  // Mood pushed from the tray submenu.
  onMood: (cb) => ipcRenderer.on('set-mood', (_event, mood) => cb(mood)),
});
