[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("Agent", "Server")]
    [string]$Component,
    [switch]$Purge
)

$ErrorActionPreference = "Stop"
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = [Security.Principal.WindowsPrincipal]::new($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    $arguments = "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`" -Component $Component"
    if ($Purge) { $arguments += " -Purge" }
    Start-Process powershell.exe -Verb RunAs -ArgumentList $arguments
    exit
}

$installRoot = Join-Path $env:ProgramData "no0bz\NCC"
$python = Join-Path $installRoot "venv\Scripts\python.exe"
$name = $Component.ToLowerInvariant()
$serviceName = if ($Component -eq "Agent") { "NccAgent" } else { "NccServer" }
$service = Get-Service -Name $serviceName -ErrorAction SilentlyContinue
if ($service) {
    if ($service.Status -ne "Stopped") { Stop-Service -Name $serviceName -Force }
    if (Test-Path $python) { & $python -m ncc_service.windows $name remove }
    else { & sc.exe delete $serviceName | Out-Null }
}
if ($Purge) {
    $config = Join-Path $installRoot "config\$name.env"
    if (Test-Path $config) { Remove-Item -LiteralPath $config -Force }
    if ($Component -eq "Agent") {
        $data = Join-Path $installRoot "agent-data"
        if (Test-Path $data) { Remove-Item -LiteralPath $data -Recurse -Force }
    }
    Write-Host "[NCC] Dienst und $Component-Daten wurden entfernt."
} else {
    Write-Host "[NCC] Dienst entfernt; Konfiguration und Daten bleiben erhalten."
}
