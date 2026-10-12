[CmdletBinding()]
param()

# Runs a short foreground sshd diagnostic as LocalSystem, the same identity as
# the Windows service. It never changes sshd configuration or firewall rules.
$ErrorActionPreference = 'Stop'
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = [Security.Principal.WindowsPrincipal]::new($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'Bitte diese Datei in einer als Administrator gestarteten PowerShell ausfuehren.'
}

$sshRoot = Join-Path $env:ProgramData 'ssh'
$sshdExe = Join-Path $env:WINDIR 'System32\OpenSSH\sshd.exe'
$logPath = Join-Path $sshRoot 'ncc-sshd-system-debug.log'
# LocalSystem cannot reliably traverse a user's %TEMP% profile directory.
# Keep both diagnostic artefacts in ProgramData so the task uses exactly the
# same filesystem visibility as the sshd service.
$cmdPath = Join-Path $sshRoot 'ncc-sshd-system-debug.cmd'
$taskName = 'NccSshdSystemDiagnostic'
if (-not (Test-Path -LiteralPath $sshdExe)) { throw "sshd.exe fehlt: $sshdExe" }

Stop-Service -Name sshd -ErrorAction SilentlyContinue
Remove-Item -LiteralPath $logPath -Force -ErrorAction SilentlyContinue
@(
    '@echo off',
    'echo NCC_SYSTEM_TASK_STARTED > "' + $logPath + '"',
    'whoami >> "' + $logPath + '" 2>&1',
    '"' + $sshdExe + '" -ddd -e >> "' + $logPath + '" 2>&1'
) | Set-Content -LiteralPath $cmdPath -Encoding ascii

Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue
$action = New-ScheduledTaskAction -Execute $env:ComSpec -Argument ('/d /c "' + $cmdPath + '"')
$principalSystem = New-ScheduledTaskPrincipal -UserId 'SYSTEM' -LogonType ServiceAccount -RunLevel Highest
Register-ScheduledTask -TaskName $taskName -Action $action -Principal $principalSystem -Force | Out-Null
try {
    Start-ScheduledTask -TaskName $taskName
    Start-Sleep -Seconds 6
    Stop-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 1

    Write-Output '--- sshd LocalSystem debug output ---'
    if (Test-Path -LiteralPath $logPath) {
        Get-Content -LiteralPath $logPath -Tail 160
    } else {
        Write-Output 'NO_SYSTEM_DEBUG_LOG'
    }
    Write-Output '--- diagnostic task state ---'
    Get-ScheduledTaskInfo -TaskName $taskName | Select-Object LastRunTime, LastTaskResult, NextRunTime
} finally {
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $cmdPath -Force -ErrorAction SilentlyContinue
}
