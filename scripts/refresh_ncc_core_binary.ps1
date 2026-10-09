[CmdletBinding()]
param()

# Rebuilds and replaces only the durable NccCore executable. It does not stage
# a payload, rotate pairing credentials, or modify the legacy NccAgent config.
$ErrorActionPreference = 'Stop'
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = [Security.Principal.WindowsPrincipal]::new($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'Dieses Skript bitte in einer als Administrator gestarteten PowerShell ausfuehren.'
}

$project = Split-Path -Parent $PSScriptRoot
$coreProject = Join-Path $project 'core\ncc-core'
$installer = Join-Path $PSScriptRoot 'install_ncc_core_service.ps1'
if (!(Test-Path -LiteralPath $coreProject)) { throw "NccCore-Quellen fehlen: $coreProject" }
if (!(Test-Path -LiteralPath $installer)) { throw "NccCore-Installer fehlt: $installer" }
$cargo = Get-Command cargo.exe -ErrorAction SilentlyContinue
if (!$cargo) { $cargo = Get-Command cargo -ErrorAction SilentlyContinue }
if (!$cargo) { throw 'Rust Cargo wurde nicht gefunden. Installiere oder repariere Rust zuerst; es wird nichts an NCC geaendert.' }

Push-Location $coreProject
try {
    & $cargo.Source build --release
    if ($LASTEXITCODE -ne 0) { throw 'NccCore konnte nicht kompiliert werden.' }
} finally {
    Pop-Location
}

$binary = Join-Path $coreProject 'target\release\ncc-core.exe'
if (!(Test-Path -LiteralPath $binary)) { throw "Kompilierter NccCore fehlt: $binary" }
& $installer -CoreExecutable $binary
if ($LASTEXITCODE -ne 0) { throw 'NccCore-Dienst konnte nach dem Build nicht aktualisiert werden.' }

[pscustomobject]@{
    Result = 'NccCore binary rebuilt and service refreshed'
    Binary = $binary
    Service = (Get-Service -Name NccCore).Status.ToString()
    NextStep = 'Run activate_ncc_core_approved_release.ps1 to apply the already approved release.'
} | ConvertTo-Json
