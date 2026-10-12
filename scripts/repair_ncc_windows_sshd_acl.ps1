[CmdletBinding()]
param()

# Windows OpenSSH runs as LocalSystem. Repair only the standard local service
# ACLs on its ProgramData directory; this grants nothing to network users.
$ErrorActionPreference = 'Stop'
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = [Security.Principal.WindowsPrincipal]::new($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'Bitte diese Datei in einer als Administrator gestarteten PowerShell ausfuehren.'
}

$sshRoot = Join-Path $env:ProgramData 'ssh'
$sshdExe = Join-Path $env:WINDIR 'System32\OpenSSH\sshd.exe'
if (-not (Test-Path -LiteralPath $sshRoot)) { throw "OpenSSH-Verzeichnis fehlt: $sshRoot" }
if (-not (Test-Path -LiteralPath $sshdExe)) { throw "sshd.exe fehlt: $sshdExe" }

$beforePath = Join-Path $sshRoot ("ncc-sshd-acl-before-{0}.txt" -f (Get-Date -Format 'yyyyMMdd-HHmmss'))
& icacls.exe $sshRoot /T /C | Set-Content -LiteralPath $beforePath -Encoding ascii

# Remove only direct DENY rules for the two service-management identities, then
# grant their expected full local access recursively. SID notation avoids any
# localized Windows account-name lookup.
& icacls.exe $sshRoot /remove:d '*S-1-5-18' '*S-1-5-32-544' /T /C | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'Direkte DENY-Regeln fuer SYSTEM/Administratoren konnten nicht bereinigt werden.' }
& icacls.exe $sshRoot /grant '*S-1-5-18:(OI)(CI)F' '*S-1-5-32-544:(OI)(CI)F' /T /C | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'Die OpenSSH-ACL fuer SYSTEM/Administratoren konnte nicht gesetzt werden.' }

& $sshdExe -t
if ($LASTEXITCODE -ne 0) { throw 'Die sshd-Konfiguration ist ungueltig; keine Dienststart-Aktion ausgefuehrt.' }
Start-Service -Name sshd
Start-Sleep -Seconds 2
$listener = Get-NetTCPConnection -State Listen -LocalPort 22 -ErrorAction SilentlyContinue
if (-not $listener) { throw 'sshd wurde gestartet, lauscht aber nicht auf TCP-Port 22.' }

[pscustomobject]@{
    Result = 'OpenSSH LocalSystem ACL repaired'
    AclBackup = $beforePath
    Service = (Get-Service -Name sshd).Status.ToString()
    Port22 = 'Listening'
    Granted = 'SYSTEM and local Administrators only'
} | ConvertTo-Json
