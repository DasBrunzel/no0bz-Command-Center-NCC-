[CmdletBinding()]
param()

# Promotes an already healthy, Core-managed payload on this Windows host.  The
# legacy agent is only stopped after the Core health gate succeeds.  A matching
# rollback script restores NccAgent without recreating any pairing or token.
$ErrorActionPreference = 'Stop'
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = [Security.Principal.WindowsPrincipal]::new($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'Dieses Skript bitte in einer als Administrator gestarteten PowerShell ausfuehren.'
}

$root = Join-Path $env:ProgramData 'no0bz\NCC'
$configRoot = Join-Path $root 'config'
$agentEnv = Join-Path $configRoot 'agent.env'
$coreEnv = Join-Path $configRoot 'core.env'
$coreState = Join-Path $root 'core-state'
$core = Join-Path $root 'core\ncc-core.exe'
foreach ($path in @($agentEnv, $coreEnv, $core)) {
    if (-not (Test-Path -LiteralPath $path)) { throw "Benoetigte NCC-Datei fehlt: $path" }
}

$before = & $core --state-dir $coreState status
if ($LASTEXITCODE -ne 0 -or $before -notmatch '"active_payload"\s*:\s*"' -or $before -notmatch '"health"\s*:\s*"healthy"') {
    throw "NccCore-Payload ist noch nicht gesund. Abbruch ohne Aenderung: $before"
}

$timestamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$backup = Join-Path $configRoot "core.env.before-primary-switch-$timestamp.bak"
Copy-Item -LiteralPath $coreEnv -Destination $backup -ErrorAction Stop

# Reuse the proven 0.5 identity/token.  Thus the Core payload continues the
# same dashboard node instead of creating another machine entry.
$agentValues = Get-Content -LiteralPath $agentEnv | Where-Object { $_ -match '^NCC_AGENT_[A-Z0-9_]+=' }
if (-not $agentValues) { throw 'agent.env enthaelt keine NCC_AGENT-Werte.' }
@("NCC_CORE_STATE_DIR=$coreState") + $agentValues | Set-Content -LiteralPath $coreEnv -Encoding utf8
& icacls.exe $coreEnv /inheritance:r /grant:r '*S-1-5-18:F' '*S-1-5-32-544:F' | Out-Null

Stop-Service -Name NccCore -Force -ErrorAction SilentlyContinue
Stop-Service -Name NccAgent -Force -ErrorAction Stop
Set-Service -Name NccAgent -StartupType Disabled
Start-Service -Name NccCore
Start-Sleep -Seconds 5
$after = & $core --state-dir $coreState status
$coreService = Get-Service -Name NccCore
if ($coreService.Status -ne 'Running' -or $after -notmatch '"health"\s*:\s*"healthy"') {
    # The legacy service was intentionally only disabled after the health gate.
    # Restore it automatically if starting the promoted Core fails.
    Stop-Service -Name NccCore -Force -ErrorAction SilentlyContinue
    Set-Service -Name NccAgent -StartupType Automatic
    Start-Service -Name NccAgent
    throw "Core-Start fehlgeschlagen; NccAgent wurde automatisch wiederhergestellt. Zustand: $after"
}

[pscustomobject]@{
    Result = 'NccCore promoted; legacy NccAgent disabled as rollback fallback'
    CoreState = ($after | ConvertFrom-Json)
    LegacyConfigUntouched = $agentEnv
    CoreConfigBackup = $backup
    Rollback = (Join-Path $PSScriptRoot 'rollback_ncc_core_to_agent.ps1')
} | ConvertTo-Json -Depth 5
