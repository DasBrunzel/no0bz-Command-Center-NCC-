[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$PublicKey
)

$ErrorActionPreference = 'Stop'
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = [Security.Principal.WindowsPrincipal]::new($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'Run this script in an elevated PowerShell window inside the disposable Windows test VM.'
}
if ($PublicKey -notmatch '^ssh-ed25519\s+[A-Za-z0-9+/=]+(?:\s+[^\r\n]+)?$') {
    throw 'Invalid SSH public key.'
}

$tailscale = @(
    (Join-Path $env:ProgramFiles 'Tailscale\tailscale.exe'),
    'C:\Program Files\Tailscale\tailscale.exe'
) | Where-Object { Test-Path -LiteralPath $_ -PathType Leaf } | Select-Object -First 1
if (-not $tailscale) { throw 'Install Tailscale in the VM and sign in to your tailnet first.' }
$tailscaleIp = @(& $tailscale ip -4 2>$null) | Where-Object {
    $_ -match '^100\.(?:6[4-9]|[7-9]\d|1[01]\d|12[0-7])\.\d{1,3}\.\d{1,3}$'
} | Select-Object -First 1
if (-not $tailscaleIp) { throw 'Tailscale is not connected to the tailnet yet.' }

$capability = Get-WindowsCapability -Online -Name 'OpenSSH.Server~~~~0.0.1.0'
if ($capability.State -ne 'Installed') {
    Add-WindowsCapability -Online -Name 'OpenSSH.Server~~~~0.0.1.0' | Out-Null
}
$sshDir = Join-Path $env:ProgramData 'ssh'
$config = Join-Path $sshDir 'sshd_config'
$authorizedKeys = Join-Path $sshDir 'administrators_authorized_keys'
$sshd = Join-Path $env:WINDIR 'System32\OpenSSH\sshd.exe'
$sshKeygen = Join-Path $env:WINDIR 'System32\OpenSSH\ssh-keygen.exe'
New-Item -ItemType Directory -Force -Path $sshDir | Out-Null
& $sshKeygen -A | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'Could not prepare SSH host keys.' }

$existingKeys = if (Test-Path -LiteralPath $authorizedKeys) {
    @(Get-Content -LiteralPath $authorizedKeys -ErrorAction Stop)
} else { @() }
if ($PublicKey -notin $existingKeys) {
    if (Test-Path -LiteralPath $authorizedKeys) {
        Copy-Item -LiteralPath $authorizedKeys -Destination ($authorizedKeys + '.before-ncc-test-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '.bak')
    }
    [IO.File]::AppendAllText($authorizedKeys, $PublicKey + [Environment]::NewLine,
        [Text.UTF8Encoding]::new($false))
}

$configuration = if (Test-Path -LiteralPath $config) {
    Get-Content -LiteralPath $config -Raw -ErrorAction Stop
} else { "Subsystem sftp sftp-server.exe`r`n" }
$newConfiguration = $configuration
if ($newConfiguration -notmatch '(?m)^# NCC test VM SSH \(managed\)$') {
    $newConfiguration = "# NCC test VM SSH (managed)`r`nPubkeyAuthentication yes`r`nPasswordAuthentication no`r`n" + $newConfiguration
}
if ($newConfiguration -notmatch '(?m)^\s*Match\s+Group\s+administrators\b') {
    $newConfiguration += "`r`nMatch Group administrators`r`n    AuthorizedKeysFile __PROGRAMDATA__/ssh/administrators_authorized_keys`r`n"
}
if ($newConfiguration -ne $configuration) {
    if (Test-Path -LiteralPath $config) {
        Copy-Item -LiteralPath $config -Destination ($config + '.before-ncc-test-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '.bak')
    }
    [IO.File]::WriteAllText($config, $newConfiguration, [Text.UTF8Encoding]::new($false))
}
foreach ($path in @($authorizedKeys, $config)) {
    & icacls.exe $path /inheritance:r /grant:r '*S-1-5-18:F' '*S-1-5-32-544:F' | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "Could not secure SSH file ACL: $path" }
}
& $sshd -t -f $config
if ($LASTEXITCODE -ne 0) { throw 'SSH configuration validation failed. The original config backup is still available.' }

$defaultRule = Get-NetFirewallRule -Name 'OpenSSH-Server-In-TCP' -ErrorAction SilentlyContinue
if ($defaultRule) { $defaultRule | Disable-NetFirewallRule }
$ruleName = 'NCC-Test-VM-SSH-Tailscale'
Get-NetFirewallRule -Name $ruleName -ErrorAction SilentlyContinue | Remove-NetFirewallRule -ErrorAction SilentlyContinue
New-NetFirewallRule -Name $ruleName -DisplayName 'NCC Test VM SSH via Tailscale' -Direction Inbound `
    -Action Allow -Protocol TCP -LocalPort 22 -LocalAddress $tailscaleIp -RemoteAddress '100.64.0.0/10' | Out-Null

Set-Service -Name sshd -StartupType Automatic
if ((Get-Service -Name sshd).Status -eq 'Running') { Restart-Service -Name sshd }
else { Start-Service -Name sshd }
$fingerprint = (& $sshKeygen -lf (Join-Path $sshDir 'ssh_host_ed25519_key.pub') 2>$null | Out-String).Trim()
[pscustomobject]@{
    Result = 'SSH ready for NCC test VM via Tailscale'
    TailscaleIP = $tailscaleIp
    WindowsUser = $identity.Name
    HostKeyFingerprint = $fingerprint
    SshService = (Get-Service sshd).Status.ToString()
} | ConvertTo-Json -Depth 3
