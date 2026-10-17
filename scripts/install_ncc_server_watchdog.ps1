[CmdletBinding()]
param(
    [ValidateRange(2, 60)]
    [int]$IntervalMinutes = 5
)

$ErrorActionPreference = 'Stop'
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = [Security.Principal.WindowsPrincipal]::new($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'Bitte diese Datei in einer als Administrator gestarteten PowerShell ausfuehren.'
}

$root = Join-Path $env:ProgramData 'no0bz\NCC'
$managedDirectory = Join-Path $root 'scripts'
$managedScript = Join-Path $managedDirectory 'watch_ncc_server.ps1'
New-Item -ItemType Directory -Path $managedDirectory -Force | Out-Null
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'watch_ncc_server.ps1') -Destination $managedScript -Force

$taskName = 'NCC Server Watchdog'
$startupTaskName = 'NCC Server Watchdog Startup'
$taskCommand = "powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$managedScript`""

# Older Windows Server ScheduledTasks modules expose no writable Repetition
# property. schtasks.exe has a stable minute schedule across those versions.
& schtasks.exe /Create /TN $taskName /SC MINUTE /MO $IntervalMinutes /RU SYSTEM /RL HIGHEST /TR $taskCommand /F | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'Die periodische NCC-Server-Watchdog-Aufgabe konnte nicht erstellt werden.' }
& schtasks.exe /Create /TN $startupTaskName /SC ONSTART /RU SYSTEM /RL HIGHEST /TR $taskCommand /F | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'Die NCC-Server-Watchdog-Startaufgabe konnte nicht erstellt werden.' }
& schtasks.exe /Run /TN $taskName | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'Der NCC-Server-Watchdog konnte nicht gestartet werden.' }

[pscustomobject]@{
    Result = 'NCC Server watchdog installed'
    Task = $taskName
    StartupTask = $startupTaskName
    IntervalMinutes = $IntervalMinutes
    ManagedScript = $managedScript
    Log = (Join-Path $root 'logs\server-watchdog.log')
} | ConvertTo-Json
