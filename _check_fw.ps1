$port = $args[0]
$rules = Get-NetFirewallRule -Direction Inbound -Enabled True -ErrorAction SilentlyContinue |
    Get-NetFirewallPortFilter -ErrorAction SilentlyContinue |
    Where-Object { $_.Protocol -eq 'TCP' -and $_.LocalPort -eq $port }
if ($rules) { Write-Host "FOUND" } else { Write-Host "NONE" }
