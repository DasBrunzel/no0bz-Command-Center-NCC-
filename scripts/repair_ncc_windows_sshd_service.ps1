[CmdletBinding()]
param(
    [string]$MaintenanceUser = $env:USERNAME
)

# Repairs a legacy, sshd-only nccbackup Match stanza that can make the Windows
# OpenSSH service exit with 1067 / lookup_sid 1332. NCC offsite recovery uses
# Taildrop and its Scheduled Task; it does not use this inbound SSH stanza.
$ErrorActionPreference = 'Stop'
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = [Security.Principal.WindowsPrincipal]::new($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'Bitte diese Datei in einer als Administrator gestarteten PowerShell ausfuehren.'
}
if (-not $MaintenanceUser -or $MaintenanceUser -match '\s') {
    throw 'MaintenanceUser muss ein einzelner lokaler Benutzername sein.'
}

$sshRoot = Join-Path $env:ProgramData 'ssh'
$configPath = Join-Path $sshRoot 'sshd_config'
if (-not (Test-Path -LiteralPath $configPath)) { throw "sshd_config fehlt: $configPath" }

$lines = @(Get-Content -LiteralPath $configPath)
$marker = [Array]::IndexOf($lines, '# NCC offsite backup receiver (managed)')
if ($marker -lt 0) { throw 'Die verwaltete NCC-nccbackup-Regel wurde nicht gefunden; keine Aenderung vorgenommen.' }

$matchIndex = $marker + 1
while ($matchIndex -lt $lines.Count -and $lines[$matchIndex] -notmatch '^Match\s+User\s+nccbackup\s*$') { $matchIndex++ }
if ($matchIndex -ge $lines.Count) { throw 'Die verwaltete Match User nccbackup-Regel wurde nicht gefunden; keine Aenderung vorgenommen.' }

$endIndex = $matchIndex + 1
while ($endIndex -lt $lines.Count -and $lines[$endIndex] -notmatch '^\s*$') { $endIndex++ }
$prefix = if ($marker -gt 0) { @($lines[0..($marker - 1)]) } else { @() }
$suffix = if ($endIndex -lt $lines.Count) { @($lines[$endIndex..($lines.Count - 1)]) } else { @() }
$backupPath = "$configPath.before-nccbackup-sshd-repair-$(Get-Date -Format 'yyyyMMdd-HHmmss').bak"
Copy-Item -LiteralPath $configPath -Destination $backupPath -Force

$replacement = @(
    '# NCC offsite backup receiver (managed; legacy sshd stanza retired)',
    '# Taildrop recovery delivery is handled by NccOffsiteTaildropReceiver and does not use sshd.',
    "AllowUsers $MaintenanceUser"
)
Set-Content -LiteralPath $configPath -Value @($prefix + $replacement + $suffix) -Encoding ascii

$sshdExe = Join-Path $env:WINDIR 'System32\OpenSSH\sshd.exe'
& $sshdExe -t
if ($LASTEXITCODE -ne 0) {
    Copy-Item -LiteralPath $backupPath -Destination $configPath -Force
    throw 'Die reparierte sshd_config ist ungueltig; die vorherige Konfiguration wurde wiederhergestellt.'
}

Restart-Service -Name sshd
$listener = Get-NetTCPConnection -State Listen -LocalPort 22 -ErrorAction SilentlyContinue
if (-not $listener) { throw 'sshd wurde gestartet, lauscht aber nicht auf TCP-Port 22.' }

[pscustomobject]@{
    Result = 'Legacy nccbackup sshd stanza retired; maintenance SSH is active'
    ConfigBackup = $backupPath
    Service = (Get-Service sshd).Status.ToString()
    Port22 = 'Listening'
    AllowedUser = $MaintenanceUser
    OffsiteBackup = 'Unchanged: Taildrop receiver task'
} | ConvertTo-Json
