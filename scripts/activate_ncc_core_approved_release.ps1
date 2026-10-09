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
if (!(Test-Path -LiteralPath $core)) { throw "NccCore executable fehlt: $core" }
if (!(Get-Service -Name NccCore -ErrorAction SilentlyContinue)) { throw 'Der Dienst NccCore ist nicht installiert.' }

Restart-Service -Name NccCore -Force
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
                    Rollback = (Join-Path $PSScriptRoot 'rollback_ncc_core_to_agent.ps1')
                } | ConvertTo-Json
                exit 0
            }
        } catch { }
    }
} while ((Get-Date) -lt $deadline)

throw "NccCore did not become healthy with expected payload $ExpectedVersion within $TimeoutSeconds seconds. No automatic rollback was performed. Last state: $lastState"
