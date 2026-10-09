[CmdletBinding()]
param(
    [ValidatePattern('^\d+\.\d+\.\d+(?:-[A-Za-z0-9.-]+)?$')]
    [string]$ExpectedVersion = '0.6.0-beta.2',
    [ValidateRange(10, 120)]
    [int]$TimeoutSeconds = 45
)

# Activates a release already approved by a Commander in NCC. The Core checks
# the server only on a controlled service start, and it verifies HTTPS, size,
# SHA-256, and Ed25519 before staging anything. This script deliberately does
# not recreate credentials, alter the legacy 0.5 config, or auto-run rollback.
$ErrorActionPreference = 'Stop'
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = [Security.Principal.WindowsPrincipal]::new($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'Dieses Skript bitte in einer als Administrator gestarteten PowerShell ausfuehren.'
}

$root = Join-Path $env:ProgramData 'no0bz\NCC'
$core = Join-Path $root 'core\ncc-core.exe'
$stateDir = Join-Path $root 'core-state'
$coreEnv = Join-Path $root 'config\core.env'
if (!(Test-Path -LiteralPath $core)) { throw "NccCore executable fehlt: $core" }
if (!(Test-Path -LiteralPath $coreEnv)) { throw "NccCore-Konfiguration fehlt: $coreEnv" }
if (!(Get-Service -Name NccCore -ErrorAction SilentlyContinue)) { throw 'Der Dienst NccCore ist nicht installiert.' }

$serviceBefore = Get-Service -Name NccCore
$wasRunning = $serviceBefore.Status -eq 'Running'
if ($wasRunning) {
    Stop-Service -Name NccCore -Force
    (Get-Service -Name NccCore).WaitForStatus('Stopped', [TimeSpan]::FromSeconds(20))
}

# The Windows service loads core.env before starting ncc-core. Load the same
# values into this elevated process so `check-update` performs the exact same
# authenticated HTTPS/hash/signature gate, but can return its useful error to
# the operator instead of hiding it in the Windows service wrapper.
$updateOutput = ''
$updateFailure = $null
try {
    foreach ($line in Get-Content -LiteralPath $coreEnv) {
        if ($line -match '^([A-Z0-9_]+)=(.*)$') {
            [Environment]::SetEnvironmentVariable($Matches[1], $Matches[2].Trim('"'), 'Process')
        }
    }
    $updateOutput = & $core --state-dir $stateDir check-update 2>&1 | Out-String
    if ($LASTEXITCODE -ne 0) { throw "NccCore check-update failed: $updateOutput" }
} catch {
    $updateFailure = $_
} finally {
    # Keep monitoring available even if download, hash, or signature checking
    # rejected the candidate. The active known-good payload stays untouched.
    Start-Service -Name NccCore
}

if ($updateFailure) { throw $updateFailure }
$deadline = (Get-Date).AddSeconds($TimeoutSeconds)
$lastState = ''
do {
    Start-Sleep -Seconds 2
    $service = Get-Service -Name NccCore
    $lastState = & $core --state-dir $stateDir status 2>&1 | Out-String
    if ($LASTEXITCODE -eq 0 -and $service.Status -eq 'Running') {
        try {
            $state = $lastState | ConvertFrom-Json
            if ($state.active_payload -eq $ExpectedVersion -and $state.health -eq 'healthy') {
                [pscustomobject]@{
                    Result = 'Approved NCC release activated and healthy'
                    Service = $service.Status.ToString()
                    ActivePayload = $state.active_payload
                    PreviousPayload = $state.previous_payload
                    Health = $state.health
                    UpdateCheck = $updateOutput.Trim()
                    Rollback = (Join-Path $PSScriptRoot 'rollback_ncc_core_to_agent.ps1')
                } | ConvertTo-Json
                exit 0
            }
        } catch { }
    }
} while ((Get-Date) -lt $deadline)

throw "NccCore did not become healthy with expected payload $ExpectedVersion within $TimeoutSeconds seconds. No automatic rollback was performed. Last state: $lastState"
