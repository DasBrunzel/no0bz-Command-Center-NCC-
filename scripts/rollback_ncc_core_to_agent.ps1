[CmdletBinding()]
param()

# Immediate local fallback for switch_ncc_core_to_primary.ps1. It does not
# delete Core payloads, data, pairings, or the original agent configuration.
$ErrorActionPreference = 'Stop'
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = [Security.Principal.WindowsPrincipal]::new($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'Dieses Skript bitte in einer als Administrator gestarteten PowerShell ausfuehren.'
}

Stop-Service -Name NccCore -Force -ErrorAction SilentlyContinue
$root = Join-Path $env:ProgramData 'no0bz\NCC'
$configRoot = Join-Path $root 'config'
$agentEnv = Join-Path $configRoot 'agent.env'
$retirementRecord = Join-Path $configRoot 'legacy-agent-retirement.json'
if (-not (Test-Path -LiteralPath $agentEnv)) {
    $backup = Get-ChildItem -LiteralPath $configRoot -Filter 'agent.env.retired-*.bak' -File |
        Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if (-not $backup) { throw 'Keine archivierte agent.env fuer den Rollback gefunden.' }
    Copy-Item -LiteralPath $backup.FullName -Destination $agentEnv -Force
}

$mode = 'service'
if (Test-Path -LiteralPath $retirementRecord) {
    try { $mode = [string]((Get-Content -LiteralPath $retirementRecord -Raw | ConvertFrom-Json).mode) } catch { $mode = 'service' }
}

if ($mode -eq 'task') {
    $python = Join-Path $root 'venv\Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $python)) { throw "NCC Python fehlt: $python" }
    $taskCommand = "`"$python`" -m ncc_service.task_runner agent"
    & schtasks.exe /Create /TN NccAgent /SC ONSTART /RU SYSTEM /RL HIGHEST /TR $taskCommand /F | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'NccAgent-Systemaufgabe konnte beim Rollback nicht erstellt werden.' }
    Start-ScheduledTask -TaskName NccAgent
    $state = (Get-ScheduledTask -TaskName NccAgent).State.ToString()
    if ($state -ne 'Running') { throw 'NccAgent-Systemaufgabe konnte beim Rollback nicht gestartet werden.' }
} else {
    Set-Service -Name NccAgent -StartupType Automatic
    Start-Service -Name NccAgent
    $state = (Get-Service -Name NccAgent).Status.ToString()
    if ($state -ne 'Running') { throw 'NccAgent konnte beim Rollback nicht gestartet werden.' }
}
[pscustomobject]@{
    Result = 'Legacy NccAgent restored; NccCore stopped'
    LegacyAgentMode = $mode
    NccAgent = $state
} | ConvertTo-Json
