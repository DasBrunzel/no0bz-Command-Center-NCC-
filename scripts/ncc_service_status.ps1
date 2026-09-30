[CmdletBinding()]
param(
    [ValidateSet("Agent", "Server", "All")]
    [string]$Component = "All",
    [int]$LogLines = 40
)

$root = Join-Path $env:ProgramData "no0bz\NCC"
$items = if ($Component -eq "All") { @("Agent", "Server") } else { @($Component) }
foreach ($item in $items) {
    $serviceName = "Ncc$item"
    $service = Get-Service -Name $serviceName -ErrorAction SilentlyContinue
    if (-not $service) { Write-Host "[$item] Nicht installiert."; continue }
    Write-Host "[$item] Status: $($service.Status), Starttyp: $($service.StartType)"
    $log = Join-Path $root "logs\$($item.ToLowerInvariant()).log"
    if (Test-Path $log) {
        Write-Host "[$item] Letzte Logzeilen aus $log"
        Get-Content -LiteralPath $log -Tail $LogLines
    }
}
