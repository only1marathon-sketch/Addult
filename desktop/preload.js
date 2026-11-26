const { contextBridge, ipcRenderer } = require("electron");

// Only the local setup screen can change the server.
if (location.protocol === "file:") {
  contextBridge.exposeInMainWorld("desktop", {
    getServer: () => ipcRenderer.invoke("get-server"),
    setServer: (url) => ipcRenderer.invoke("set-server", url),
  });
}
