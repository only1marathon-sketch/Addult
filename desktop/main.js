// Velvet AI desktop app: a secure, branded window around your hosted platform.
// All accounts, age verification and safety checks stay on your server.

const { app, BrowserWindow, Menu, ipcMain, shell, net } = require("electron");
const fs = require("fs");
const path = require("path");

const BG = "#0a0607";
const CONFIG_PATH = () => path.join(app.getPath("userData"), "config.json");
// Set this to your live site before building so users skip the setup screen.
const DEFAULT_SERVER = process.env.VELVET_SERVER_URL || "";

let win = null;

function readConfig() {
  try { return JSON.parse(fs.readFileSync(CONFIG_PATH(), "utf8")); } catch { return {}; }
}
function writeConfig(cfg) {
  fs.mkdirSync(path.dirname(CONFIG_PATH()), { recursive: true });
  fs.writeFileSync(CONFIG_PATH(), JSON.stringify(cfg, null, 2));
}
function serverUrl() { return readConfig().serverUrl || DEFAULT_SERVER; }

function normalizeUrl(raw) {
  let s = String(raw || "").trim().replace(/\/+$/, "");
  if (!/^https?:\/\//i.test(s)) s = "https://" + s;
  const u = new URL(s);
  const local = ["localhost", "127.0.0.1"].includes(u.hostname);
  if (u.protocol !== "https:" && !local) throw new Error("Use an https:// address (http is only allowed for localhost).");
  return u.origin;
}

async function checkServer(origin) {
  const res = await net.fetch(`${origin}/api/health`, { cache: "no-store" });
  if (!res.ok) throw new Error(`Server answered with status ${res.status}.`);
  const data = await res.json().catch(() => ({}));
  if (!data.ok) throw new Error("That address isn't a Velvet AI server.");
}

function showSetup() {
  win.loadFile(path.join(__dirname, "setup.html"));
}

function showApp() {
  const url = serverUrl();
  if (!url) return showSetup();
  win.loadURL(url).catch(() => showSetup());
}

function createWindow() {
  win = new BrowserWindow({
    width: 1360,
    height: 880,
    minWidth: 900,
    minHeight: 620,
    backgroundColor: BG,
    title: "Velvet AI",
    icon: path.join(__dirname, "icon.png"),
    show: false,
    autoHideMenuBar: true,
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
      spellcheck: true,
    },
  });
  win.once("ready-to-show", () => win.show());

  // Keep the window on your server; open every other link in the user's browser.
  const isInternal = (target) => {
    try {
      const t = new URL(target);
      if (t.protocol === "file:") return true;
      return serverUrl() && t.origin === new URL(serverUrl()).origin;
    } catch { return false; }
  };
  win.webContents.on("will-navigate", (e, target) => {
    if (!isInternal(target)) { e.preventDefault(); if (/^https?:/.test(target)) shell.openExternal(target); }
  });
  win.webContents.setWindowOpenHandler(({ url }) => {
    if (/^https?:/.test(url)) shell.openExternal(url);
    return { action: "deny" };
  });

  // If the server can't be reached, go back to the setup screen with a message.
  win.webContents.on("did-fail-load", (_e, code, desc, failedUrl, isMainFrame) => {
    if (isMainFrame && !failedUrl.startsWith("file:")) {
      win.loadFile(path.join(__dirname, "setup.html"), { query: { error: `Couldn't reach ${failedUrl} (${desc}).` } });
    }
  });

  showApp();
}

function buildMenu() {
  const isMac = process.platform === "darwin";
  const template = [
    ...(isMac ? [{ role: "appMenu" }] : []),
    {
      label: "Velvet AI",
      submenu: [
        { label: "Home", accelerator: "CmdOrCtrl+H", click: () => showApp() },
        { label: "Change server…", click: () => showSetup() },
        { type: "separator" },
        isMac ? { role: "close" } : { role: "quit" },
      ],
    },
    { role: "editMenu" },
    {
      label: "View",
      submenu: [
        { role: "reload" },
        { role: "resetZoom" }, { role: "zoomIn" }, { role: "zoomOut" },
        { type: "separator" },
        { role: "togglefullscreen" },
        ...(app.isPackaged ? [] : [{ role: "toggleDevTools" }]),
      ],
    },
  ];
  Menu.setApplicationMenu(Menu.buildFromTemplate(template));
}

ipcMain.handle("get-server", () => serverUrl());
ipcMain.handle("set-server", async (_e, raw) => {
  try {
    const origin = normalizeUrl(raw);
    await checkServer(origin);
    writeConfig({ ...readConfig(), serverUrl: origin });
    showApp();
    return { ok: true };
  } catch (err) {
    return { ok: false, error: err.message || "Couldn't connect to that server." };
  }
});

// Only one copy of the app at a time.
if (!app.requestSingleInstanceLock()) {
  app.quit();
} else {
  app.on("second-instance", () => { if (win) { if (win.isMinimized()) win.restore(); win.focus(); } });
  app.whenReady().then(() => {
    buildMenu();
    createWindow();
    app.on("activate", () => { if (BrowserWindow.getAllWindows().length === 0) createWindow(); });
  });
  app.on("window-all-closed", () => { if (process.platform !== "darwin") app.quit(); });
}
