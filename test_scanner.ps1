$deviceManager = New-Object -ComObject WIA.DeviceManager
Write-Host "Total devices: $($deviceManager.DeviceInfos.Count)"

foreach ($deviceInfo in $deviceManager.DeviceInfos) {
    Write-Host "---"
    Write-Host "Type: $($deviceInfo.Type)"
    Write-Host "DeviceID: $($deviceInfo.DeviceID)"
    try {
        $name = $deviceInfo.Properties.Item("Name").Value
        Write-Host "Name: $name"
    } catch {
        Write-Host "Name: (could not get)"
    }
}
