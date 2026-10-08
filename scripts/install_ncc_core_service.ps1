[CmdletBinding()]
param(
    [string]$CoreExecutable = (Join-Path $PSScriptRoot "..\core\ncc-core\target\release\ncc-core.exe"),
    [string]$PayloadExecutable = "",
    [string]$PayloadVersion = "0.6.0-beta.1"
)

$ErrorActionPreference = "Stop"
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = [Security.Principal.WindowsPrincipal]::new($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw "Dieses Skript muss erhöht in PowerShell ausgeführt werden."
}
if (-not (Test-Path -LiteralPath $CoreExecutable)) { throw "NccCore executable nicht gefunden: $CoreExecutable" }
if (-not $PayloadExecutable -or -not (Test-Path -LiteralPath $PayloadExecutable)) { throw "Payload executable ist erforderlich und muss existieren." }
$root = Join-Path $env:ProgramData "no0bz\NCC"
$coreRoot = Join-Path $root "core"
$configRoot = Join-Path $root "config"
New-Item -ItemType Directory -Force -Path $coreRoot, $configRoot, (Join-Path $root "core-state"), (Join-Path $root "logs") | Out-Null
Copy-Item -LiteralPath $CoreExecutable -Destination (Join-Path $coreRoot "ncc-core.exe") -Force
$config = Join-Path $configRoot "core.env"
@(
  "NCC_CORE_STATE_DIR=$root\core-state",
  "NCC_CORE_PAYLOAD_EXECUTABLE=$PayloadExecutable",
  "NCC_CORE_PAYLOAD_VERSION=$PayloadVersion"
) | Set-Content -LiteralPath $config -Encoding utf8
& icacls.exe $config /inheritance:r /grant:r '*S-1-5-18:F' '*S-1-5-32-544:F' | Out-Null
$python = Join-Path $root "venv\Scripts\python.exe"
if (-not (Test-Path $python)) { throw "NCC Dienst-Python fehlt: $python" }
$existing = Get-Service NccCore -ErrorAction SilentlyContinue
& $python -m ncc_service.windows core --startup auto $(if ($existing) { "update" } else { "install" })
if ($LASTEXITCODE -ne 0) { throw "NccCore konnte nicht registriert werden." }
if ($existing -and $existing.Status -eq 'Running') { Restart-Service NccCore -Force } else { Start-Service NccCore }
Write-Host "[NCC] NccCore läuft. Log: $(Join-Path $root 'logs\core.log')"
