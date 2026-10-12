[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^ssh-ed25519\s+[A-Za-z0-9+/=]+(?:\s+[^\r\n]+)?$')]
    [string]$PublicKey,
    [ValidatePattern('^100\.64\.0\.0/10$')]
    [string]$TailscaleCidr = '100.64.0.0/10'
)

# One-time bootstrap for a Windows Server that should be administered through
# Tailscale only. It deliberately installs no NCC component and grants access
# only to the supplied public key; private keys and passwords are never read.
$ErrorActionPreference = 'Stop'
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = [Security.Principal.WindowsPrincipal]::new($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'Bitte diese Datei in einer als Administrator gestarteten PowerShell ausfuehren.'
}

$capabilityName = 'OpenSSH.Server~~~~0.0.1.0'
$capability = Get-WindowsCapability -Online -Name $capabilityName
if ($capability.State -ne 'Installed') {
    Add-WindowsCapability -Online -Name $capabilityName | Out-Null
}

$sshd = Get-Service -Name sshd -ErrorAction Stop
Set-Service -Name sshd -StartupType Automatic

$sshRoot = Join-Path $env:ProgramData 'ssh'
$authorizedKeys = Join-Path $sshRoot 'administrators_authorized_keys'
$userSshRoot = Join-Path $env:USERPROFILE '.ssh'
$userAuthorizedKeys = Join-Path $userSshRoot 'authorized_keys'
New-Item -ItemType Directory -Path $sshRoot -Force | Out-Null
if (Test-Path -LiteralPath $authorizedKeys) {
    $backup = "$authorizedKeys.before-ncc-maintenance-$(Get-Date -Format 'yyyyMMdd-HHmmss').bak"
    Copy-Item -LiteralPath $authorizedKeys -Destination $backup -Force
}

$keyMaterial = ($PublicKey -split '\s+')[1]
$hasKey = (Test-Path -LiteralPath $authorizedKeys) -and (
    Select-String -LiteralPath $authorizedKeys -SimpleMatch -Quiet -Pattern $keyMaterial
)
if (-not $hasKey) {
    Add-Content -LiteralPath $authorizedKeys -Value $PublicKey -Encoding ascii
}

# Keep a standard per-user authorized_keys copy as well. Some pre-existing
# Windows sshd_config files do not contain the Microsoft administrators match
# block, but they do use the default .ssh/authorized_keys path.
New-Item -ItemType Directory -Path $userSshRoot -Force | Out-Null
$hasUserKey = (Test-Path -LiteralPath $userAuthorizedKeys) -and (
    Select-String -LiteralPath $userAuthorizedKeys -SimpleMatch -Quiet -Pattern $keyMaterial
)
if (-not $hasUserKey) {
    Add-Content -LiteralPath $userAuthorizedKeys -Value $PublicKey -Encoding ascii
}

# Windows OpenSSH requires a protected administrators_authorized_keys file for
# members of the local Administrators group.
& icacls.exe $authorizedKeys /inheritance:r /grant:r '*S-1-5-18:F' '*S-1-5-32-544:F' | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'Die ACL fuer administrators_authorized_keys konnte nicht gesetzt werden.' }
& icacls.exe $userSshRoot /inheritance:r /grant:r "*$($identity.User.Value):F" '*S-1-5-18:F' | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'Die ACL fuer das Benutzer-.ssh-Verzeichnis konnte nicht gesetzt werden.' }
& icacls.exe $userAuthorizedKeys /inheritance:r /grant:r "*$($identity.User.Value):F" '*S-1-5-18:F' | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'Die ACL fuer die Benutzer-Schluesseldatei konnte nicht gesetzt werden.' }

# The offsite receiver intentionally locks SSH to nccbackup. Extend only its
# managed AllowUsers line so the invoker can perform server maintenance while
# the constrained backup account and its ForceCommand remain unchanged.
$sshdConfig = Join-Path $sshRoot 'sshd_config'
$configLines = @(Get-Content -LiteralPath $sshdConfig)
$markerIndex = [Array]::IndexOf($configLines, '# NCC offsite backup receiver (managed)')
if ($markerIndex -ge 0 -and $markerIndex + 1 -lt $configLines.Count) {
    $allowIndex = $markerIndex + 1
    if ($configLines[$allowIndex] -match '^AllowUsers\s+(.+)$') {
        $allowedUsers = @($Matches[1] -split '\s+' | Where-Object { $_ })
        if ($allowedUsers -notcontains $env:USERNAME) {
            Copy-Item -LiteralPath $sshdConfig -Destination "$sshdConfig.before-ncc-maintenance-$(Get-Date -Format 'yyyyMMdd-HHmmss').bak" -Force
            $configLines[$allowIndex] = 'AllowUsers ' + (($allowedUsers + $env:USERNAME) -join ' ')
            Set-Content -LiteralPath $sshdConfig -Value $configLines -Encoding ascii
        }
    }
}

# The capability normally creates this rule with an unrestricted source range.
# Keep maintenance SSH private to the Tailscale CGNAT range instead.
$firewallRules = @(Get-NetFirewallRule -DisplayName 'OpenSSH-Server-In-TCP' -ErrorAction SilentlyContinue)
if (-not $firewallRules.Count) {
    New-NetFirewallRule -DisplayName 'OpenSSH-Server-In-TCP' -Direction Inbound -Action Allow `
        -Protocol TCP -LocalPort 22 -RemoteAddress $TailscaleCidr | Out-Null
} else {
    foreach ($rule in $firewallRules) {
        Enable-NetFirewallRule -Name $rule.Name | Out-Null
        # Windows Server's older NetSecurity module has no
        # -AssociatedNetFirewallRule parameter. Resolve the address filter
        # through the pipeline for compatibility with both module versions.
        $rule | Get-NetFirewallAddressFilter | Set-NetFirewallAddressFilter -RemoteAddress $TailscaleCidr | Out-Null
    }
}

& "$env:WINDIR\System32\OpenSSH\sshd.exe" -t
if ($LASTEXITCODE -ne 0) { throw 'Die Windows-OpenSSH-Konfiguration ist ungueltig.' }

# Add-WindowsCapability does not create these host keys reliably on every
# Windows Server image. ssh-keygen -A is idempotent and creates only missing
# keys, so the first service start has a valid server identity.
& "$env:WINDIR\System32\OpenSSH\ssh-keygen.exe" -A
if ($LASTEXITCODE -ne 0) { throw 'Die OpenSSH-Server-Hostschluessel konnten nicht erzeugt werden.' }
Restart-Service -Name sshd
$listener = Get-NetTCPConnection -State Listen -LocalPort 22 -ErrorAction SilentlyContinue
if (-not $listener) { throw 'sshd laeuft, lauscht aber nicht auf TCP Port 22.' }
$fingerprint = $PublicKey | & "$env:WINDIR\System32\OpenSSH\ssh-keygen.exe" -lf - 2>$null

[pscustomobject]@{
    Result = 'Windows OpenSSH maintenance access configured'
    Service = (Get-Service -Name sshd).Status.ToString()
    Port22 = 'Listening'
    AllowedRemoteRange = $TailscaleCidr
    AuthorizedKeys = @($authorizedKeys, $userAuthorizedKeys)
    ExistingKeysBackup = $backup
    PublicKeyFingerprint = $fingerprint
} | ConvertTo-Json -Depth 3
