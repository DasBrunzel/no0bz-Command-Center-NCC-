[CmdletBinding()]
param(
    [string]$CoreExecutable = (Join-Path $PSScriptRoot "..\core\ncc-core\target\release\ncc-core.exe")
)

$ErrorActionPreference = "Stop"
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = [Security.Principal.WindowsPrincipal]::new($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw "Dieses Skript muss erhöht in PowerShell ausgeführt werden."
}
if (-not (Test-Path -LiteralPath $CoreExecutable)) { throw "NccCore executable nicht gefunden: $CoreExecutable" }
$root = Join-Path $env:ProgramData "no0bz\NCC"
$coreRoot = Join-Path $root "core"
$configRoot = Join-Path $root "config"
New-Item -ItemType Directory -Force -Path $coreRoot, $configRoot, (Join-Path $root "core-state"), (Join-Path $root "logs") | Out-Null
Copy-Item -LiteralPath $CoreExecutable -Destination (Join-Path $coreRoot "ncc-core.exe") -Force
$config = Join-Path $configRoot "core.env"
@(
  "NCC_CORE_STATE_DIR=$root\core-state"
) | Set-Content -LiteralPath $config -Encoding utf8
& icacls.exe $config /inheritance:r /grant:r '*S-1-5-18:F' '*S-1-5-32-544:F' | Out-Null
$python = Join-Path $root "venv\Scripts\python.exe"
if (-not (Test-Path $python)) { throw "NCC Dienst-Python fehlt: $python" }
$existing = Get-Service NccCore -ErrorAction SilentlyContinue
& $python -m ncc_service.windows core --startup auto $(if ($existing) { "update" } else { "install" })
if ($LASTEXITCODE -ne 0) { throw "NccCore konnte nicht registriert werden." }
$stateFile = Join-Path $root "core-state\state\core-state.json"
$active = $false
if (Test-Path -LiteralPath $stateFile) {
    try { $active = !!((Get-Content -LiteralPath $stateFile -Raw | ConvertFrom-Json).active_payload) } catch { $active = $false }
}
if ($active) {
    if ($existing -and $existing.Status -eq 'Running') { Restart-Service NccCore -Force } else { Start-Service NccCore }
    Write-Host "[NCC] NccCore läuft. Log: $(Join-Path $root 'logs\core.log')"
} else {
    Write-Host "[NCC] NccCore ist installiert, aber bewusst noch nicht gestartet: zuerst signierten Payload stagen und aktivieren."
}
