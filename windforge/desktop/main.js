const { app, BrowserWindow, protocol } = require('electron');
const { spawn } = require('child_process');
const path = require('path');
const http = require('http');
const portfinder = require('portfinder');

let mainWindow = null;
let backendProcess = null;
let backendPort = null;

// Determine resource paths based on packaged vs development
function getResourcesPath() {
  if (app.isPackaged) {
    return process.resourcesPath;
  }
  return path.join(__dirname, 'resources');
}

// Find a free port for the backend
async function findFreePort() {
  portfinder.basePort = 18080;
  portfinder.highestPort = 18999;
  return portfinder.getPortPromise();
}

// Poll the backend health endpoint until it responds
function waitForBackend(port, maxWaitMs = 30000) {
  const startTime = Date.now();
  return new Promise((resolve, reject) => {
    const check = () => {
      if (Date.now() - startTime > maxWaitMs) {
        reject(new Error('Backend did not start within timeout'));
        return;
      }

      const req = http.get(`http://127.0.0.1:${port}/`, (res) => {
        if (res.statusCode === 200) {
          resolve();
        } else {
          setTimeout(check, 500);
        }
      });

      req.on('error', () => {
        setTimeout(check, 500);
      });

      req.setTimeout(2000, () => {
        req.destroy();
        setTimeout(check, 500);
      });
    };

    check();
  });
}

// Start the Python backend
async function startBackend() {
  const resourcesPath = getResourcesPath();
  const port = await findFreePort();
  backendPort = port;

  const userData = app.getPath('userData');
  const dbPath = path.join(userData, 'windforge.db');

  const env = {
    ...process.env,
    PORT: String(port),
    HOST: '127.0.0.1',
    DATABASE_URL: `sqlite+aiosqlite:///${dbPath}`,
    DESKTOP_MODE: 'true',
    RESOURCES_PATH: resourcesPath,
    OPENFAST_EXE: path.join(resourcesPath, 'bin', 'openfast'),
    TURBSIM_EXE: path.join(resourcesPath, 'bin', 'turbsim'),
    ROSCO_LIB_PATH: path.join(resourcesPath, 'bin', 'libdiscon.dylib'),
    SECRET_KEY: 'windforge-desktop-local-key',
  };

  let backendExe;
  if (app.isPackaged) {
    backendExe = path.join(resourcesPath, 'python', 'windforge-api');
  } else {
    // Dev mode: run via Python directly
    backendExe = 'python';
  }

  const args = app.isPackaged
    ? []
    : ['-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', String(port)];

  const cwd = app.isPackaged
    ? resourcesPath
    : path.join(__dirname, '..', 'apps', 'api');

  console.log(`Starting backend: ${backendExe} ${args.join(' ')}`);
  console.log(`Working directory: ${cwd}`);
  console.log(`Port: ${port}`);

  backendProcess = spawn(backendExe, args, {
    cwd,
    env,
    stdio: ['ignore', 'pipe', 'pipe'],
  });

  backendProcess.stdout.on('data', (data) => {
    console.log(`[backend] ${data.toString().trim()}`);
  });

  backendProcess.stderr.on('data', (data) => {
    console.error(`[backend] ${data.toString().trim()}`);
  });

  backendProcess.on('error', (err) => {
    console.error('Failed to start backend:', err);
  });

  backendProcess.on('exit', (code) => {
    console.log(`Backend exited with code ${code}`);
    backendProcess = null;
  });

  // Wait for backend to be ready
  console.log('Waiting for backend to be ready...');
  await waitForBackend(port);
  console.log('Backend is ready!');

  return port;
}

// Create the main application window
function createWindow(port) {
  mainWindow = new BrowserWindow({
    width: 1440,
    height: 900,
    minWidth: 1024,
    minHeight: 700,
    title: 'WindForge',
    titleBarStyle: 'hiddenInset',
    backgroundColor: '#0f172a',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  const apiUrl = `http://127.0.0.1:${port}`;

  if (app.isPackaged) {
    // Load the built frontend from resources
    const indexPath = path.join(getResourcesPath(), 'app', 'dist', 'index.html');
    mainWindow.loadFile(indexPath);
  } else {
    // Dev mode: load from Vite dev server
    mainWindow.loadURL('http://localhost:3000');
    mainWindow.webContents.openDevTools();
  }

  // Inject the API URL after the page loads
  mainWindow.webContents.on('did-finish-load', () => {
    mainWindow.webContents.executeJavaScript(
      `window.__WINDFORGE_API_URL__ = '${apiUrl}';`
    );
  });

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

// Gracefully shut down the backend
function shutdownBackend() {
  if (backendProcess) {
    console.log('Shutting down backend...');
    backendProcess.kill('SIGTERM');

    // Force kill after 5 seconds if not exited
    const forceKillTimeout = setTimeout(() => {
      if (backendProcess) {
        console.log('Force-killing backend...');
        backendProcess.kill('SIGKILL');
      }
    }, 5000);

    backendProcess.on('exit', () => {
      clearTimeout(forceKillTimeout);
    });
  }
}

// App lifecycle
app.whenReady().then(async () => {
  try {
    const port = await startBackend();
    createWindow(port);
  } catch (err) {
    console.error('Failed to start application:', err);
    app.quit();
  }
});

app.on('window-all-closed', () => {
  shutdownBackend();
  app.quit();
});

app.on('before-quit', () => {
  shutdownBackend();
});

app.on('activate', () => {
  if (mainWindow === null && backendPort) {
    createWindow(backendPort);
  }
});
