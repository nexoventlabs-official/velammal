// Free scanner utility - uses native scanner apps + file upload
// No paid SDK required!

// Convert PDF to images (for scanned PDFs)
export const convertPdfToImages = async (pdfFile) => {
  // For PDF files, we'll pass them through as-is since the backend can handle them
  // Or convert first page to image preview
  return [pdfFile]
}

// Process uploaded scan files (images or PDFs)
export const processScannedFiles = async (files) => {
  const processedFiles = []
  
  for (const file of files) {
    if (file.type === 'application/pdf') {
      // Keep PDF as-is, backend will handle it
      processedFiles.push(file)
    } else if (file.type.startsWith('image/')) {
      processedFiles.push(file)
    }
  }
  
  return processedFiles
}

// Get scanner instructions based on OS
export const getScannerInstructions = () => {
  const isWindows = navigator.platform.includes('Win')
  const isMac = navigator.platform.includes('Mac')
  
  if (isWindows) {
    return {
      title: 'Windows Scan',
      steps: [
        'Open "Windows Scan" app (search in Start menu)',
        'Or use your scanner\'s app (HP Scan, Canon IJ Scan, etc.)',
        'Select your scanner and scan the document',
        'Save as PNG, JPG, or PDF',
        'Upload the saved file here'
      ],
      tip: 'Tip: Press Win + S and search "Scan" to find Windows Scan app'
    }
  } else if (isMac) {
    return {
      title: 'macOS Preview',
      steps: [
        'Open "Preview" app',
        'Go to File → Import from Scanner',
        'Select your scanner and scan',
        'Save as PNG, JPG, or PDF',
        'Upload the saved file here'
      ],
      tip: 'Tip: You can also use Image Capture app'
    }
  } else {
    return {
      title: 'Scanner App',
      steps: [
        'Open your scanner\'s companion app',
        'Scan the document',
        'Save as PNG, JPG, or PDF',
        'Upload the saved file here'
      ],
      tip: 'Most scanners come with a free scanning app'
    }
  }
}

// Supported file types for scanned documents
export const SUPPORTED_SCAN_TYPES = {
  accept: 'image/png,image/jpeg,image/jpg,image/tiff,application/pdf',
  extensions: ['.png', '.jpg', '.jpeg', '.tiff', '.pdf']
}

// Validate scanned file
export const validateScannedFile = (file) => {
  const validTypes = ['image/png', 'image/jpeg', 'image/jpg', 'image/tiff', 'application/pdf']
  const maxSize = 50 * 1024 * 1024 // 50MB
  
  if (!validTypes.includes(file.type)) {
    return { valid: false, error: 'Invalid file type. Please upload PNG, JPG, TIFF, or PDF.' }
  }
  
  if (file.size > maxSize) {
    return { valid: false, error: 'File too large. Maximum size is 50MB.' }
  }
  
  return { valid: true }
}
