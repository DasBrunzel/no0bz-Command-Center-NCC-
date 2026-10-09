[CmdletBinding()]
param(
    [switch]$KeepLegacyAgent,
    [ValidateRange(20, 180)]
    [int]$HealthTimeoutSeconds = 75
)

# This script is shipped inside a small bootstrap ZIP alongside ncc-core.exe.
# It intentionally reuses the already installed NCC Python/pywin32 runtime;
# therefore it needs neither Rust nor a source checkout on the target machine.
# The legacy agent is retired only after the signed payload has become healthy.
$ErrorActionPreference = 'Stop'
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = [Security.Principal.WindowsPrincipal]::new($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'Bitte diese Datei in einer als Administrator gestarteten PowerShell ausfuehren.'
}

$packageRoot = $PSScriptRoot
$root = Join-Path $env:ProgramData 'no0bz\NCC'
$configRoot = Join-Path $root 'config'
$agentEnv = Join-Path $configRoot 'agent.env'
$coreEnv = Join-Path $configRoot 'core.env'
$stateRoot = Join-Path $root 'core-state'
$coreSource = Join-Path $packageRoot 'ncc-core.exe'
$trustedKeysSource = Join-Path $packageRoot 'trusted-keys.json'
$servicePackage = Join-Path $packageRoot 'service-package'
$python = Join-Path $root 'venv\Scripts\python.exe'

foreach ($path in @($coreSource, $trustedKeysSource, $servicePackage, $agentEnv, $python)) {
    if (-not (Test-Path -LiteralPath $path)) { throw "Benoetigte Bootstrap-Datei fehlt: $path" }
}

function Set-NccAcl([string]$Path) {
    & icacls.exe $Path /inheritance:r /grant:r '*S-1-5-18:F' '*S-1-5-32-544:F' | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "NCC-Dateiberechtigungen konnten nicht gesetzt werden: $Path" }
}

function Import-NccEnvironment([string]$Path) {
    foreach ($line in Get-Content -LiteralPath $Path) {
        if ($line -match '^([A-Z0-9_]+)=(.*)$') {
            [Environment]::SetEnvironmentVariable($Matches[1], $Matches[2].Trim('"'), 'Process')
        }
    }
}

New-Item -ItemType Directory -Force -Path (Join-Path $root 'core'), $configRoot, $stateRoot, (Join-Path $stateRoot 'config'), (Join-Path $root 'logs') | Out-Null

# Install only the service wrapper. --no-deps prevents a bootstrap from
# changing the proven telemetry dependencies in the existing NCC venv.
& $python -m pip install --no-deps --upgrade --force-reinstall $servicePackage
if ($LASTEXITCODE -ne 0) { throw 'Die NCC-Core-Dienstlogik konnte nicht installiert werden.' }

$coreTarget = Join-Path $root 'core\ncc-core.exe'
$wasCoreRunning = (Get-Service -Name NccCore -ErrorAction SilentlyContinue).Status -eq 'Running'
if ($wasCoreRunning) { Stop-Service -Name NccCore -Force }
Copy-Item -LiteralPath $coreSource -Destination $coreTarget -Force

# Copy every existing agent setting exactly once. Pairing identity and token
# remain unchanged, so the Core continues the existing dashboard node.
$agentValues = Get-Content -LiteralPath $agentEnv | Where-Object { $_ -match '^NCC_AGENT_[A-Z0-9_]+=' }
if (-not $agentValues) { throw 'agent.env enthaelt keine NCC_AGENT-Werte.' }
@("NCC_CORE_STATE_DIR=$stateRoot") + $agentValues | Set-Content -LiteralPath $coreEnv -Encoding utf8
Copy-Item -LiteralPath $trustedKeysSource -Destination (Join-Path $stateRoot 'config\trusted-keys.json') -Force
Set-NccAcl $coreTarget
Set-NccAcl $coreEnv
Set-NccAcl (Join-Path $stateRoot 'config\trusted-keys.json')

$existingCoreService = Get-Service -Name NccCore -ErrorAction SilentlyContinue
if ($existingCoreService) {
    & $python -m ncc_service.windows core update
    if ($LASTEXITCODE -ne 0) { throw 'Der bestehende NccCore-Dienst konnte nicht aktualisiert werden.' }
} else {
    & $python -m ncc_service.windows core --startup auto install
    if ($LASTEXITCODE -ne 0) { throw 'Der NccCore-Dienst konnte nicht registriert werden.' }
}
Set-Service -Name NccCore -StartupType Automatic

# Download/stage/activate happens before the service starts. The update route
# returns only a Commander-approved, node-assigned, signed release.
Import-NccEnvironment $coreEnv
$updateOutput = & $coreTarget --state-dir $stateRoot check-update 2>&1 | Out-String
if ($LASTEXITCODE -ne 0) { throw "Der freigegebene NCC-Release konnte nicht geprueft werden: $updateOutput" }
$stateBefore = & $coreTarget --state-dir $stateRoot status | ConvertFrom-Json
if (-not $stateBefore.active_payload) {
    throw 'Fuer dieses Geraet ist noch kein freigegebener NCC-Release zugeteilt. NccAgent blieb unveraendert aktiv; Release im Dashboard zuweisen und Bootstrap erneut starten.'
}

Start-Service -Name NccCore
$deadline = (Get-Date).AddSeconds($HealthTimeoutSeconds)
$state = $null
do {
    Start-Sleep -Seconds 2
    try { $state = & $coreTarget --state-dir $stateRoot status | ConvertFrom-Json } catch { $state = $null }
    $coreService = Get-Service -Name NccCore
    if ($coreService.Status -eq 'Running' -and $state -and $state.health -eq 'healthy') { break }
} while ((Get-Date) -lt $deadline)

if (-not $state -or $state.health -ne 'healthy' -or (Get-Service NccCore).Status -ne 'Running') {
    Stop-Service -Name NccCore -Force -ErrorAction SilentlyContinue
    if ((Get-Service -Name NccAgent -ErrorAction SilentlyContinue).Status -ne 'Running') {
        Set-Service -Name NccAgent -StartupType Automatic -ErrorAction SilentlyContinue
        Start-Service -Name NccAgent -ErrorAction SilentlyContinue
    }
    throw "NccCore wurde nicht gesund. Der bisherige NccAgent wurde wiederhergestellt. Letzter Core-Zustand: $($state | ConvertTo-Json -Compress)"
}

if (-not $KeepLegacyAgent) {
    $backup = Join-Path $configRoot ('agent.env.retired-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '.bak')
    Stop-Service -Name NccAgent -Force -ErrorAction SilentlyContinue
    & $python -m ncc_service.windows agent remove 2>$null
    if ($LASTEXITCODE -ne 0 -and (Get-Service -Name NccAgent -ErrorAction SilentlyContinue)) {
        throw 'NccCore ist gesund, aber der alte NccAgent-Dienst konnte nicht entfernt werden. Keine Agent-Dateien wurden geloescht.'
    }
    Move-Item -LiteralPath $agentEnv -Destination $backup -Force
    [pscustomobject]@{
        Result = 'NccCore installed, healthy, and legacy NccAgent removed'
        ActivePayload = $state.active_payload
        LegacyAgentConfigBackup = $backup
        NccCore = (Get-Service NccCore).Status.ToString()
    } | ConvertTo-Json
} else {
    [pscustomobject]@{
        Result = 'NccCore installed and healthy; legacy NccAgent retained by request'
        ActivePayload = $state.active_payload
        NccCore = (Get-Service NccCore).Status.ToString()
    } | ConvertTo-Json
}
