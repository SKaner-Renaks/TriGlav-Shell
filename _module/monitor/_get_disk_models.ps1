$physDisks = Get-PhysicalDisk
$results = @()
Get-CimInstance Win32_DiskDrive | ForEach-Object {
    $phys = $_
    $parts = $phys | Get-CimAssociatedInstance -ResultClassName Win32_DiskPartition -ErrorAction SilentlyContinue
    foreach ($p in $parts) {
        $logs = $p | Get-CimAssociatedInstance -ResultClassName Win32_LogicalDisk -ErrorAction SilentlyContinue
        foreach ($ld in $logs) {
            if ($ld.DriveType -eq 3) {
                $driveNum = $phys.DeviceID -replace '\\\\.\\PHYSICALDRIVE',''
                $pd = $physDisks | Where-Object { $_.DeviceId -eq $driveNum }
                $mt = if ($pd) { $pd.MediaType } else { 'Unknown' }
                $model = if ($phys.Model) { $phys.Model } else { 'Unknown' }
                $label = if ($ld.VolumeName) { $ld.VolumeName } else { '' }
                $results += [PSCustomObject]@{ Letter = $ld.DeviceID; Model = $model; MediaType = $mt; Label = $label }
            }
        }
    }
}
$results | ConvertTo-Json -Compress
