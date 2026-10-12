[CmdletBinding()]
param(
    [string]$MaintenanceUser = $env:USERNAME,
    [ValidatePattern('^100\.64\.0\.0/10$')]
    [string]$TailscaleCidr = '100.64.0.0/10'
)

# Last-resort repair for a Windows OpenSSH Server service that still exits 1067
# after configuration and ACL validation. Only the Server capability is
# reinstalled. Current SSH material is copied to a dated backup first; the
# replacement config permits just the local maintenance user and the firewall
# remains Tailscale-only.
$ErrorActionPreference = 'Stop'
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = [Security.Principal.WindowsPrincipal]::new($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'Bitte diese Datei in einer als Administrator gestarteten PowerShell ausfuehren.'
}
if (-not $MaintenanceUser -or $MaintenanceUser -match '\s') {
    throw 'MaintenanceUser muss ein einzelner lokaler Benutzername sein.'
}

$capabilityName = 'OpenSSH.Server~~~~0.0.1.0'
$sshRoot = Join-Path $env:ProgramData 'ssh'
$backupRoot = Join-Path $env:ProgramData ('no0bz\NCC\ssh-recovery\openssh-server-' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
New-Item -ItemType Directory -Path $backupRoot -Force | Out-Null
if (Test-Path -LiteralPath $sshRoot) {
    Copy-Item -LiteralPath $sshRoot -Destination (Join-Path $backupRoot 'ssh-before-reinstall') -Recurse -Force
}

Stop-Service -Name sshd -ErrorAction SilentlyContinue
$capability = Get-WindowsCapability -Online -Name $capabilityName
if ($capability.State -eq 'Installed') {
    Remove-WindowsCapability -Online -Name $capabilityName | Out-Null
}
Add-WindowsCapability -Online -Name $capabilityName | Out-Null

$sshdExe = Join-Path $env:WINDIR 'System32\OpenSSH\sshd.exe'
$defaultConfig = Join-Path $env:WINDIR 'System32\OpenSSH\sshd_config_default'
if (-not (Test-Path -LiteralPath $sshdExe)) { throw "sshd.exe fehlt nach Neuinstallation: $sshdExe" }
if (-not (Test-Path -LiteralPath $defaultConfig)) { throw "Standardkonfiguration fehlt nach Neuinstallation: $defaultConfig" }

New-Item -ItemType Directory -Path $sshRoot -Force | Out-Null
Copy-Item -LiteralPath $defaultConfig -Destination (Join-Path $sshRoot 'sshd_config') -Force

# Preserve the existing public-key access without restoring the faulty custom
# configuration. The default Windows configuration supports this protected
# administrators key file; the per-user key remains in the user profile.
$oldAdminKeys = Join-Path $backupRoot 'ssh-before-reinstall\administrators_authorized_keys'
$newAdminKeys = Join-Path $sshRoot 'administrators_authorized_keys'
if (Test-Path -LiteralPath $oldAdminKeys) {
    Copy-Item -LiteralPath $oldAdminKeys -Destination $newAdminKeys -Force
}

# Restrict login identities even inside Tailscale. The firewall below controls
# network reachability; AllowUsers controls SSH authentication scope.
Add-Content -LiteralPath (Join-Path $sshRoot 'sshd_config') -Value @('', '# NCC Windows maintenance access', "AllowUsers $MaintenanceUser") -Encoding ascii
& "$env:WINDIR\System32\OpenSSH\ssh-keygen.exe" -A
if ($LASTEXITCODE -ne 0) { throw 'OpenSSH-Hostschluessel konnten nicht erzeugt werden.' }

& icacls.exe $sshRoot /grant '*S-1-5-18:(OI)(CI)F' '*S-1-5-32-544:(OI)(CI)F' /T /C | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'Die OpenSSH-ACL konnte nicht gesetzt werden.' }
$rules = @(Get-NetFirewallRule -DisplayName 'OpenSSH-Server-In-TCP' -ErrorAction SilentlyContinue)
if (-not $rules.Count) {
    New-NetFirewallRule -DisplayName 'OpenSSH-Server-In-TCP' -Direction Inbound -Action Allow -Protocol TCP -LocalPort 22 -RemoteAddress $TailscaleCidr | Out-Null
} else {
    foreach ($rule in $rules) {
        Enable-NetFirewallRule -Name $rule.Name | Out-Null
        $rule | Get-NetFirewallAddressFilter | Set-NetFirewallAddressFilter -RemoteAddress $TailscaleCidr | Out-Null
    }
}

& $sshdExe -t
if ($LASTEXITCODE -ne 0) { throw 'Die neue sshd-Konfiguration ist ungueltig.' }
Set-Service -Name sshd -StartupType Automatic
Start-Service -Name sshd
Start-Sleep -Seconds 2
$listener = Get-NetTCPConnection -State Listen -LocalPort 22 -ErrorAction SilentlyContinue
if (-not $listener) { throw 'sshd wurde neu installiert, lauscht aber nicht auf TCP-Port 22.' }

[pscustomobject]@{
    Result = 'Windows OpenSSH Server reinstalled and running'
    Backup = $backupRoot
    Service = (Get-Service -Name sshd).Status.ToString()
    Port22 = 'Listening'
    AllowedUser = $MaintenanceUser
    AllowedRemoteRange = $TailscaleCidr
} | ConvertTo-Json
