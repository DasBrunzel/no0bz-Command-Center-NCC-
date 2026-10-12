[CmdletBinding()]
param()

# Read-only foreground diagnostic for Windows OpenSSH.  The temporary debug
# process is stopped after four seconds; the installed sshd service is not
# changed by this script.
$ErrorActionPreference = 'Continue'
$sshd = Join-Path $env:WINDIR 'System32\OpenSSH\sshd.exe'
if (-not (Test-Path -LiteralPath $sshd)) { throw "OpenSSH sshd.exe fehlt: $sshd" }

$job = Start-Job -ScriptBlock {
    param($exe)
    & $exe -ddd -e 2>&1
} -ArgumentList $sshd

Start-Sleep -Seconds 4
Write-Output '--- sshd foreground debug ---'
Receive-Job -Job $job -Keep
Stop-Job -Job $job -ErrorAction SilentlyContinue
Remove-Job -Job $job -Force -ErrorAction SilentlyContinue

Write-Output '--- TCP port 22 ---'
Get-NetTCPConnection -LocalPort 22 -ErrorAction SilentlyContinue |
    Select-Object LocalAddress, LocalPort, State, OwningProcess
