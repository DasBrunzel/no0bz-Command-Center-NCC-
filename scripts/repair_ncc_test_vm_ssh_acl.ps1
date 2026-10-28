[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = [Security.Principal.WindowsPrincipal]::new($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'Run this script in an elevated PowerShell window inside the disposable Windows test VM.'
}

$sshDir = Join-Path $env:ProgramData 'ssh'
$sshd = Join-Path $env:WINDIR 'System32\OpenSSH\sshd.exe'
$config = Join-Path $sshDir 'sshd_config'
$adminKey = Join-Path $sshDir 'administrators_authorized_keys'
$logDir = Join-Path $sshDir 'logs'
foreach ($required in @($sshDir, $sshd, $config, $adminKey)) {
    if (-not (Test-Path -LiteralPath $required)) { throw "OpenSSH path is missing: $required" }
}

$systemSid = [Security.Principal.SecurityIdentifier]::new('S-1-5-18')
$adminsSid = [Security.Principal.SecurityIdentifier]::new('S-1-5-32-544')
$full = [Security.AccessControl.FileSystemRights]::FullControl
$allow = [Security.AccessControl.AccessControlType]::Allow
$inherit = [Security.AccessControl.InheritanceFlags]::ContainerInherit -bor
    [Security.AccessControl.InheritanceFlags]::ObjectInherit
$noInherit = [Security.AccessControl.InheritanceFlags]::None
$propagation = [Security.AccessControl.PropagationFlags]::None

function Set-NccSshAcl([string]$Path, [bool]$Directory) {
    $acl = Get-Acl -LiteralPath $Path
    $acl.SetAccessRuleProtection($true, $false)
    foreach ($rule in @($acl.Access)) { [void]$acl.RemoveAccessRuleSpecific($rule) }
    $flags = if ($Directory) { $inherit } else { $noInherit }
    foreach ($sid in @($systemSid, $adminsSid)) {
        $rule = [Security.AccessControl.FileSystemAccessRule]::new(
            $sid, $full, $flags, $propagation, $allow)
        $acl.AddAccessRule($rule)
    }
    $acl.SetOwner($adminsSid)
    Set-Acl -LiteralPath $Path -AclObject $acl
    $current = Get-Acl -LiteralPath $Path
    $unexpected = @($current.Access | Where-Object {
        $_.AccessControlType -eq 'Allow' -and
            $_.IdentityReference.Translate([Security.Principal.SecurityIdentifier]).Value -notin
                @('S-1-5-18', 'S-1-5-32-544')
    })
    if ($unexpected.Count) { throw "OpenSSH ACL still permits another writer: $Path" }
}

$privateKeys = @(Get-ChildItem -LiteralPath $sshDir -Filter 'ssh_host_*_key' -File)
if ($privateKeys.Count -eq 0) { throw 'No private SSH host keys were found.' }
if (-not (Test-Path -LiteralPath $logDir -PathType Container)) {
    New-Item -ItemType Directory -Path $logDir | Out-Null
}
$paths = @($sshDir, $logDir, $config, $adminKey) + @($privateKeys.FullName)
$backup = Join-Path $env:TEMP ('ncc-test-vm-ssh-acl-before-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '.json')
$snapshot = @($paths | ForEach-Object {
    [pscustomobject]@{ Path = $_; Sddl = (Get-Acl -LiteralPath $_).Sddl }
})
[IO.File]::WriteAllText($backup, ($snapshot | ConvertTo-Json -Depth 3), [Text.UTF8Encoding]::new($false))

Set-NccSshAcl $sshDir $true
Set-NccSshAcl $logDir $true
Set-NccSshAcl $config $false
Set-NccSshAcl $adminKey $false
foreach ($key in $privateKeys) { Set-NccSshAcl $key.FullName $false }

& $sshd -t -f $config
if ($LASTEXITCODE -ne 0) { throw 'SSH configuration or host keys failed validation after ACL repair.' }
try {
    Start-Service -Name sshd -ErrorAction Stop
} catch {
    $recent = @(Get-WinEvent -FilterHashtable @{
        LogName = 'System'
        ProviderName = 'Service Control Manager'
        StartTime = (Get-Date).AddMinutes(-5)
    } -ErrorAction SilentlyContinue | Where-Object { $_.Message -match 'ssh|OpenSSH' } |
        Select-Object -First 3 -ExpandProperty Message)
    throw "OpenSSH still does not start. Recent service events: $($recent -join ' | ')"
}

[pscustomobject]@{
    Result = 'OpenSSH ACL repaired and service started'
    ComputerName = $env:COMPUTERNAME
    SshService = (Get-Service sshd).Status.ToString()
    TailscaleIP = @(& (Join-Path $env:ProgramFiles 'Tailscale\tailscale.exe') ip -4 2>$null | Select-Object -First 1)
    WindowsUser = $identity.Name
    HostKeyFingerprint = @(& (Join-Path $env:WINDIR 'System32\OpenSSH\ssh-keygen.exe') -lf
        (Join-Path $sshDir 'ssh_host_ed25519_key.pub') 2>$null | Select-Object -First 1)
    AclBackup = $backup
} | ConvertTo-Json -Depth 3
