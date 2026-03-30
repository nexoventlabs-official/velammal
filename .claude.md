# ExamScan AI - Electron Desktop App Build Guide

## Overview
This document explains how the Electron desktop app (.exe) is built and configured. The app allows direct USB scanner control on Windows machines while using the Render backend for OCR processing.

## Project Structure

```
frontend/
├── electron/
│   ├── main.cjs          # Electron main process
│   └── preload.cjs       # Preload script for IPC
├── dist/                 # Vite build output (React app)
├── release2/             # Electron build output
│   └── ExamScan AI 1.0.0.exe  # Portable executable
├── package.json          # Contains Electron build config
├── vite.config.js        # Vite config with base: './'
└── .env.production       # Production API URL
```

## Key Configuration Files

### 1. package.json - Electron Build Config
```json
{
  "main": "electron/main.cjs",
  "build": {
    "appId": "com.examscan.ai",
    "productName": "ExamScan AI",
    "directories": {
      "output": "release2"
    },
    "files": [
      "dist/**/*",
      "electron/**/*"
    ],
    "win": {
      "target": "portable",
      "signAndEditExecutable": false
    }
  }
}
```

### 2. vite.config.js - CRITICAL Setting
```javascript
export default defineConfig({
  plugins: [react()],
  base: './',  // REQUIRED for Electron - uses relative paths
  // ...
})
```

### 3. .env.production - Backend API URL
```
VITE_API_URL=https://velammal.onrender.com/api
```

## Electron Main Process (main.cjs)

### Why .cjs Extension?
- Electron requires CommonJS modules
- package.json has `"type": "module"` for Vite
- Using `.cjs` forces CommonJS regardless of package.json

### Local HTTP Server Approach
The app uses a local HTTP server to serve files in production because:
- `file://` protocol doesn't support ES modules (`type="module"`)
- Custom protocols are complex and unreliable
- HTTP server properly handles MIME types and module loading

```javascript
// Start local server for production
function startServer() {
  const appPath = app.getAppPath()
  const distPath = path.join(appPath, 'dist')
  
  server = http.createServer((req, res) => {
    // Serves files from dist folder
    // Falls back to index.html for SPA routing
  })
  
  server.listen(0, '127.0.0.1')  // Random available port
}
```

### App Lifecycle
```javascript
app.whenReady().then(() => {
  if (!isDev) {
    startServer()  // Start HTTP server in production
  }
  initScanner()
  createWindow()
})
```

## Build Commands

```bash
# Development mode (with hot reload)
npm run electron:dev

# Production build (creates .exe)
npm run electron:build
```

## Common Issues & Solutions

### 1. Blank Screen
**Cause**: ES modules not loading with `file://` protocol
**Solution**: Use local HTTP server (implemented in main.cjs)

### 2. Build Fails - File Locked
**Cause**: Previous .exe still running
**Solution**: 
```powershell
taskkill /f /im "ExamScan AI.exe"
Remove-Item -Path "release2" -Recurse -Force
npm run electron:build
```

### 3. Blank Screen with No Console Errors
**Cause**: Paths in index.html are absolute (`/assets/...`)
**Solution**: Set `base: './'` in vite.config.js

### 4. Module Loading Errors
**Cause**: Using `.js` extension with CommonJS
**Solution**: Rename to `.cjs` and update all references

## Scanner Integration (Windows WIA)

The app uses PowerShell to interact with Windows Image Acquisition (WIA):

```javascript
// Get available scanners
const script = `
  $deviceManager = New-Object -ComObject WIA.DeviceManager
  $devices = $deviceManager.DeviceInfos | Where-Object { $_.Type -eq 1 }
  # Returns scanner list as JSON
`
execSync(`powershell -Command "${script}"`)
```

### IPC Handlers
- `scanner:check` - Check if scanners available
- `scanner:list` - List all connected scanners
- `scanner:scan` - Perform document scan
- `scanner:getFile` - Get scanned file as base64

## API Configuration

The app connects to the Render backend:
- **Production URL**: `https://velammal.onrender.com/api`
- Set in `.env.production` as `VITE_API_URL`

## Rebuilding the App

1. Kill any running instances:
   ```powershell
   taskkill /f /im "ExamScan AI.exe"
   ```

2. Clean and rebuild:
   ```powershell
   Remove-Item -Path "release2" -Recurse -Force
   npm run electron:build
   ```

3. Output: `frontend/release2/ExamScan AI 1.0.0.exe`

## Dependencies

Key Electron-related packages in package.json:
- `electron`: ^41.1.0
- `electron-builder`: ^26.8.1
- `concurrently`: For running Vite + Electron together
- `wait-on`: Wait for Vite server before launching Electron

---

## Backend Setup (Render)

### Required Environment Variables on Render

For the "Results DB not connected" error, set these on Render:

| Variable | Description |
|----------|-------------|
| `MONGODB_URL` | MongoDB connection string |
| `MONGODB_DB_NAME` | Database name (default: `examscan`) |
| `RESULTS_CREDENTIALS_JSON` | Google Sheets service account JSON (full content) |
| `RESULTS_DB_SHEET_ID` | Google Sheet ID for results storage |
| `GROQ_API_KEY` | Groq API key for OCR |
| `CLOUDINARY_CLOUD_NAME` | Cloudinary cloud name |
| `CLOUDINARY_API_KEY` | Cloudinary API key |
| `CLOUDINARY_API_SECRET` | Cloudinary API secret |

### Google Sheets Setup

1. Create a Google Cloud service account
2. Enable Google Sheets API
3. Share your Google Sheet with the service account email
4. Copy the JSON credentials to `RESULTS_CREDENTIALS_JSON` env var
5. Set the Sheet ID in `RESULTS_DB_SHEET_ID`

### API Endpoints

The Electron app connects to: `https://velammal.onrender.com/api`

Key endpoints:
- `POST /exam/start-session` - Start exam scanning session
- `POST /exam/upload-pages/{session_id}` - Upload scanned pages
- `POST /students/upload-excel/{session_id}` - Upload student Excel
- `POST /students/worksheets/create` - Create result sheet
- `GET /results/dashboard` - Dashboard statistics

---

## Troubleshooting

### "Results DB not connected"
- Check `RESULTS_CREDENTIALS_JSON` is set on Render
- Check `RESULTS_DB_SHEET_ID` is set on Render
- Verify the Google Sheet is shared with the service account

### Student Upload Not Working
- Ensure backend is running and accessible
- Check network connectivity to Render backend
- Verify Excel file format (.xlsx, .xls, .csv)

### Dashboard Shows No Data
- Dashboard requires results in the Google Sheet
- Scan some exam sheets first to populate data
