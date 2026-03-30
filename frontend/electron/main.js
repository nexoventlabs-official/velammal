const { app, BrowserWindow, ipcMain } = require('electron')
const path = require('path')
const { execSync } = require('child_process')

// Scanner module (Windows WIA)
let scannerModule = null

// Check if running in development
const isDev = process.env.NODE_ENV === 'development' || !app.isPackaged

function createWindow() {
  const mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 1200,
    minHeight: 700,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, 'preload.js')
    },
    icon: path.join(__dirname, '../public/favicon.ico'),
    title: 'ExamScan AI',
    autoHideMenuBar: true
  })

  // Load the app
  if (isDev) {
    mainWindow.loadURL('http://localhost:5173')
    mainWindow.webContents.openDevTools()
  } else {
    mainWindow.loadFile(path.join(__dirname, '../dist/index.html'))
  }
}

// Initialize scanner module
function initScanner() {
  try {
    // Use PowerShell to interact with WIA on Windows
    return true
  } catch (err) {
    console.error('Scanner init error:', err)
    return false
  }
}

// Get list of scanners using PowerShell WIA
function getScanners() {
  try {
    const script = `
      $deviceManager = New-Object -ComObject WIA.DeviceManager
      $scanners = @()
      foreach ($deviceInfo in $deviceManager.DeviceInfos) {
        if ($deviceInfo.Type -eq 1) {
          $scanners += @{
            id = $deviceInfo.DeviceID
            name = $deviceInfo.Properties("Name").Value
          }
        }
      }
      $scanners | ConvertTo-Json
    `
    const result = execSync(`powershell -Command "${script.replace(/"/g, '\\"').replace(/\n/g, ' ')}"`, {
      encoding: 'utf8',
      timeout: 10000
    })
    
    const parsed = JSON.parse(result || '[]')
    return Array.isArray(parsed) ? parsed : [parsed]
  } catch (err) {
    console.error('Get scanners error:', err.message)
    return []
  }
}

// Scan document using PowerShell WIA
function scanDocument(scannerId = null) {
  try {
    const outputDir = app.getPath('temp')
    const fileName = `scan_${Date.now()}.png`
    const filePath = path.join(outputDir, fileName)
    
    const script = `
      $deviceManager = New-Object -ComObject WIA.DeviceManager
      $scanner = $null
      foreach ($deviceInfo in $deviceManager.DeviceInfos) {
        if ($deviceInfo.Type -eq 1) {
          $scanner = $deviceInfo.Connect()
          break
        }
      }
      if ($scanner -eq $null) {
        Write-Error "No scanner found"
        exit 1
      }
      $item = $scanner.Items(1)
      $image = $item.Transfer("{B96B3CAF-0728-11D3-9D7B-0000F81EF32E}")
      $image.SaveFile("${filePath.replace(/\\/g, '\\\\')}")
      Write-Output "${filePath.replace(/\\/g, '\\\\')}"
    `
    
    const result = execSync(`powershell -Command "${script.replace(/"/g, '\\"').replace(/\n/g, ' ')}"`, {
      encoding: 'utf8',
      timeout: 60000 // 60 seconds for scanning
    })
    
    return {
      success: true,
      filePath: result.trim(),
      error: null
    }
  } catch (err) {
    let errorMsg = err.message
    if (errorMsg.includes('0x80210006')) {
      errorMsg = 'Scanner is busy or paper not loaded'
    } else if (errorMsg.includes('0x80210001')) {
      errorMsg = 'Scanner not ready'
    }
    
    return {
      success: false,
      filePath: null,
      error: errorMsg
    }
  }
}

// IPC Handlers
ipcMain.handle('scanner:check', async () => {
  const scanners = getScanners()
  return {
    available: scanners.length > 0,
    scanners: scanners
  }
})

ipcMain.handle('scanner:list', async () => {
  return getScanners()
})

ipcMain.handle('scanner:scan', async (event, options = {}) => {
  return scanDocument(options.scannerId)
})

ipcMain.handle('scanner:getFile', async (event, filePath) => {
  const fs = require('fs')
  try {
    const data = fs.readFileSync(filePath)
    return {
      success: true,
      data: data.toString('base64'),
      mimeType: 'image/png'
    }
  } catch (err) {
    return {
      success: false,
      error: err.message
    }
  }
})

// App lifecycle
app.whenReady().then(() => {
  initScanner()
  createWindow()

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow()
    }
  })
})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit()
  }
})
