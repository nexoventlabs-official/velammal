const { app, BrowserWindow, ipcMain } = require('electron')
const path = require('path')
const fs = require('fs')
const http = require('http')
const { execSync } = require('child_process')

// Scanner module (Windows WIA)
let scannerModule = null
let server = null

// Check if running in development
const isDev = !app.isPackaged && process.env.NODE_ENV !== 'production'

// MIME types
const mimeTypes = {
  '.html': 'text/html',
  '.js': 'application/javascript',
  '.css': 'text/css',
  '.json': 'application/json',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.svg': 'image/svg+xml',
  '.ico': 'image/x-icon',
  '.woff': 'font/woff',
  '.woff2': 'font/woff2'
}

// Start local server for production
function startServer() {
  return new Promise((resolve, reject) => {
    const appPath = app.getAppPath()
    const distPath = path.join(appPath, 'dist')

    server = http.createServer((req, res) => {
      let filePath = req.url === '/' ? '/index.html' : req.url
      filePath = path.join(distPath, filePath)

      const ext = path.extname(filePath)
      const contentType = mimeTypes[ext] || 'application/octet-stream'

      fs.readFile(filePath, (err, data) => {
        if (err) {
          // Try index.html for SPA routing
          fs.readFile(path.join(distPath, 'index.html'), (err2, data2) => {
            if (err2) {
              res.writeHead(404)
              res.end('Not found')
            } else {
              res.writeHead(200, { 'Content-Type': 'text/html' })
              res.end(data2)
            }
          })
        } else {
          res.writeHead(200, { 'Content-Type': contentType })
          res.end(data)
        }
      })
    })

    server.listen(0, '127.0.0.1', () => {
      const port = server.address().port
      console.log('Server running on port:', port)
      resolve(port)
    })

    server.on('error', reject)
  })
}

function createWindow(port) {
  const mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 1200,
    minHeight: 700,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, 'preload.cjs')
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
    // In production, use local HTTP server
    mainWindow.loadURL(`http://127.0.0.1:${port}`)
  }

  mainWindow.webContents.on('did-fail-load', (event, errorCode, errorDescription) => {
    console.error('Failed to load:', errorCode, errorDescription)
  })
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
    // Write PowerShell script to temp file to avoid escaping issues
    const tempDir = app.getPath('temp')
    const scriptPath = path.join(tempDir, 'detect_scanner.ps1')
    
    const scriptContent = `
try {
    $deviceManager = New-Object -ComObject WIA.DeviceManager
    $scanners = @()
    foreach ($deviceInfo in $deviceManager.DeviceInfos) {
        if ($deviceInfo.Type -eq 1) {
            $scanners += @{
                id = $deviceInfo.DeviceID
                name = $deviceInfo.Properties.Item("Name").Value
            }
        }
    }
    if ($scanners.Count -eq 0) {
        Write-Output "[]"
    } elseif ($scanners.Count -eq 1) {
        Write-Output ("[" + ($scanners | ConvertTo-Json -Compress) + "]")
    } else {
        Write-Output ($scanners | ConvertTo-Json -Compress)
    }
} catch {
    Write-Output "[]"
}
`
    fs.writeFileSync(scriptPath, scriptContent, 'utf8')
    
    const result = execSync(`powershell -NoProfile -ExecutionPolicy Bypass -File "${scriptPath}"`, {
      encoding: 'utf8',
      timeout: 15000,
      windowsHide: true
    })
    
    // Clean up temp file
    try { fs.unlinkSync(scriptPath) } catch (e) {}
    
    const trimmed = result.trim()
    console.log('Scanner detection result:', trimmed)
    
    if (!trimmed || trimmed === '') {
      return []
    }
    
    const parsed = JSON.parse(trimmed)
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
    const outputPath = path.join(outputDir, fileName)
    
    // Write PowerShell script to temp file
    const scriptPath = path.join(outputDir, 'scan_document.ps1')
    const scriptContent = `
try {
    $deviceManager = New-Object -ComObject WIA.DeviceManager
    $scanner = $null
    foreach ($deviceInfo in $deviceManager.DeviceInfos) {
        if ($deviceInfo.Type -eq 1) {
            $scanner = $deviceInfo.Connect()
            break
        }
    }
    if ($scanner -eq $null) {
        throw "No scanner found"
    }
    $item = $scanner.Items(1)
    $image = $item.Transfer("{B96B3CAF-0728-11D3-9D7B-0000F81EF32E}")
    $image.SaveFile("${outputPath.replace(/\\/g, '\\')}")
    Write-Output "${outputPath.replace(/\\/g, '\\')}"
} catch {
    Write-Error $_.Exception.Message
    exit 1
}
`
    fs.writeFileSync(scriptPath, scriptContent, 'utf8')
    
    const result = execSync(`powershell -NoProfile -ExecutionPolicy Bypass -File "${scriptPath}"`, {
      encoding: 'utf8',
      timeout: 60000,
      windowsHide: true
    })
    
    // Clean up script file
    try { fs.unlinkSync(scriptPath) } catch (e) {}
    
    console.log('Scan result:', result.trim())
    
    return {
      success: true,
      filePath: result.trim(),
      error: null
    }
  } catch (err) {
    let errorMsg = err.message || 'Unknown error'
    console.error('Scan error:', errorMsg)
    
    if (errorMsg.includes('0x80210006')) {
      errorMsg = 'Scanner is busy or paper not loaded'
    } else if (errorMsg.includes('0x80210001')) {
      errorMsg = 'Scanner not ready'
    } else if (errorMsg.includes('No scanner found')) {
      errorMsg = 'No scanner found. Please connect a scanner.'
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
app.whenReady().then(async () => {
  let port = null
  if (!isDev) {
    port = await startServer()
  }
  initScanner()
  createWindow(port)

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow(port)
    }
  })
})

app.on('window-all-closed', () => {
  if (server) {
    server.close()
  }
  if (process.platform !== 'darwin') {
    app.quit()
  }
})
