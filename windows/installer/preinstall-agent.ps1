[CmdletBinding()]
param([Parameter(Mandatory = $true)][string]$AppDir)

$ErrorActionPreference = 'Stop'
$admin = [Security.Principal.WindowsPrincipal]::new([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $admin.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) { throw 'Administrator rights required.' }

$root = Join-Path $env:ProgramData 'no0bz\NCC Agent'
$legacyRoot = Join-Path $env:ProgramData 'no0bz\NCC'
$handoffRoot = Join-Path $env:ProgramData 'no0bz\NCC Agent Setup'
$trayMarker = Join-Path $AppDir 'tray-upgrade.marker'
$backup = Join-Path $handoffRoot ('backup-' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
New-Item -ItemType Directory -Force -Path $handoffRoot, $backup | Out-Null
& icacls.exe $handoffRoot /inheritance:r /grant:r '*S-1-5-18:(OI)(CI)F' '*S-1-5-32-544:(OI)(CI)F' | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'Could not protect NCC installer backup.' }

$runningServices = @()
$legacyTaskRunning = $false
trap {
    Remove-Item -LiteralPath $trayMarker -Force -ErrorAction SilentlyContinue
    foreach ($name in $runningServices) { Start-Service -Name $name -ErrorAction SilentlyContinue }
    if ($legacyTaskRunning) { Start-ScheduledTask -TaskName NccAgent -ErrorAction SilentlyContinue }
    throw
}
$trayProcesses = @(Get-CimInstance Win32_Process -Filter "Name='NccTray.exe'" -ErrorAction SilentlyContinue | Where-Object {
    $_.ExecutablePath -and [IO.Path]::GetFullPath($_.ExecutablePath).Equals(
        [IO.Path]::GetFullPath((Join-Path $AppDir 'NccTray.exe')), [StringComparison]::OrdinalIgnoreCase)
})
if ($trayProcesses.Count -gt 0) {
    [IO.File]::WriteAllText($trayMarker, 'upgrade', [Text.UTF8Encoding]::new($false))
    $trayDeadline = (Get-Date).AddSeconds(25)
    do {
        Start-Sleep -Seconds 1
        $remaining = @($trayProcesses | Where-Object { Get-Process -Id $_.ProcessId -ErrorAction SilentlyContinue })
    } while ($remaining.Count -gt 0 -and (Get-Date) -lt $trayDeadline)
    foreach ($process in $remaining) { Stop-Process -Id $process.ProcessId -Force -ErrorAction Stop }
}
foreach ($name in @('NccAgentCore', 'NccCore', 'NccAgent')) {
    $service = Get-Service -Name $name -ErrorAction SilentlyContinue
    if ($service -and $service.Status -eq 'Running') {
        $runningServices += $name
        Stop-Service -Name $name -Force -ErrorAction Stop
        $service.WaitForStatus('Stopped', [TimeSpan]::FromSeconds(30))
    }
}
$legacyTask = Get-ScheduledTask -TaskName NccAgent -ErrorAction SilentlyContinue
if ($legacyTask -and $legacyTask.State -eq 'Running') {
    $legacyTaskRunning = $true
    Stop-ScheduledTask -TaskName NccAgent -ErrorAction Stop
}

if (Test-Path -LiteralPath $root -PathType Container) {
    Copy-Item -LiteralPath $root -Destination (Join-Path $backup 'agent-data') -Recurse -Force -ErrorAction Stop
}
if (Test-Path -LiteralPath $AppDir -PathType Container) {
    Copy-Item -LiteralPath $AppDir -Destination (Join-Path $backup 'app') -Recurse -Force -ErrorAction Stop
}
$legacyBackup = Join-Path $backup 'legacy-agent'
foreach ($relative in @('config\agent.env', 'config\core.env', 'agent-data', 'core-state', 'core\ncc-core.exe')) {
    $source = Join-Path $legacyRoot $relative
    if (-not (Test-Path -LiteralPath $source)) { continue }
    $destination = Join-Path $legacyBackup $relative
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $destination) | Out-Null
    Copy-Item -LiteralPath $source -Destination $destination -Recurse -Force -ErrorAction Stop
}
@{
    backup = $backup
    agent_root = $root
    app_dir = [IO.Path]::GetFullPath($AppDir)
    legacy_agent_backup = $legacyBackup
    running_services = $runningServices
    legacy_task_running = $legacyTaskRunning
    created_at = (Get-Date).ToString('o')
} | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $handoffRoot 'handoff.json') -Encoding UTF8

# The tray starts a same-session relaunch helper before it exits. The forced
# stop only handles older tray builds that do not yet understand the marker.
