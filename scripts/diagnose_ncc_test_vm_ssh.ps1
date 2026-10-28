[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$sshd = Join-Path $env:WINDIR 'System32\OpenSSH\sshd.exe'
$config = Join-Path $env:ProgramData 'ssh\sshd_config'
$sshDir = Join-Path $env:ProgramData 'ssh'
$debugLog = Join-Path $env:TEMP ('ncc-test-vm-sshd-' + [Guid]::NewGuid().ToString('N') + '.log')

if (-not (Test-Path -LiteralPath $sshd -PathType Leaf)) { throw 'OpenSSH Server binary is missing.' }
if (-not (Test-Path -LiteralPath $config -PathType Leaf)) { throw 'sshd_config is missing.' }

$syntaxOutput = @(& $sshd -t -f $config 2>&1 | ForEach-Object { "$_" })
$syntaxExitCode = $LASTEXITCODE
$port22 = @(Get-NetTCPConnection -LocalPort 22 -State Listen -ErrorAction SilentlyContinue |
    Select-Object LocalAddress, OwningProcess)

$debugOutput = @()
if ((Get-Service sshd).Status -eq 'Stopped') {
    $debugProcess = Start-Process -FilePath $sshd -ArgumentList @('-ddd', '-e', '-f', $config) `
        -PassThru -WindowStyle Hidden -RedirectStandardError $debugLog
    try {
        Start-Sleep -Seconds 4
        $debugProcess.Refresh()
    } finally {
        if (-not $debugProcess.HasExited) {
            Stop-Process -Id $debugProcess.Id -Force -ErrorAction SilentlyContinue
            $debugProcess.WaitForExit(5000) | Out-Null
        }
        if (Test-Path -LiteralPath $debugLog) {
            $debugOutput = @([IO.File]::ReadAllLines($debugLog) | Select-Object -Last 35)
            Remove-Item -LiteralPath $debugLog -Force -ErrorAction SilentlyContinue
        }
    }
}

$sshEvents = @(Get-WinEvent -LogName 'OpenSSH/Admin' -MaxEvents 8 -ErrorAction SilentlyContinue |
    Select-Object TimeCreated, Id, Message)
$serviceEvents = @(Get-WinEvent -FilterHashtable @{
    LogName = 'System'
    ProviderName = 'Service Control Manager'
    StartTime = (Get-Date).AddMinutes(-15)
} -ErrorAction SilentlyContinue | Where-Object { $_.Message -match 'ssh|OpenSSH' } |
    Select-Object -First 8 TimeCreated, Id, Message)
$keyAcls = @(Get-ChildItem -LiteralPath $sshDir -Filter 'ssh_host_*_key' -File -ErrorAction SilentlyContinue |
    ForEach-Object {
        $acl = Get-Acl -LiteralPath $_.FullName
        [pscustomobject]@{
            Name = $_.Name
            Owner = $acl.Owner
            Access = @($acl.Access | ForEach-Object { $_.IdentityReference.Value + ':' + $_.FileSystemRights + ':' + $_.AccessControlType })
        }
    })

[pscustomobject]@{
    ComputerName = $env:COMPUTERNAME
    SshService = (Get-Service sshd).Status.ToString()
    SyntaxExitCode = $syntaxExitCode
    SyntaxOutput = $syntaxOutput
    Port22Listeners = $port22
    DebugOutput = $debugOutput
    OpenSshAdminEvents = $sshEvents
    ServiceEvents = $serviceEvents
    HostKeyAcls = $keyAcls
} | ConvertTo-Json -Depth 6
