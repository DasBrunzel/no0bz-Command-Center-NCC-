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
$action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$managedScript`""
$daily = New-ScheduledTaskTrigger -Daily -At '00:00'
$daily.Repetition.Interval = "PT$IntervalMinutes`M"
$daily.Repetition.Duration = 'P1D'
$startup = New-ScheduledTaskTrigger -AtStartup
$taskPrincipal = New-ScheduledTaskPrincipal -UserId 'SYSTEM' -LogonType ServiceAccount -RunLevel Highest
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger @($daily, $startup) -Principal $taskPrincipal -Force | Out-Null
Start-ScheduledTask -TaskName $taskName

[pscustomobject]@{
    Result = 'NCC Server watchdog installed'
    Task = $taskName
    IntervalMinutes = $IntervalMinutes
    ManagedScript = $managedScript
    Log = (Join-Path $root 'logs\server-watchdog.log')
} | ConvertTo-Json
