const { contextBridge, ipcRenderer } = require('electron');

// The API URL is injected by main.js after page load via executeJavaScript.
// This preload script provides a minimal bridge if needed in the future.

contextBridge.exposeInMainWorld('windforge', {
  isDesktop: true,
  platform: process.platform,
});
