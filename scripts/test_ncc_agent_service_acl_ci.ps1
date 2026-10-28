[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$name = 'ncc-ci-standard-user'
$password = 'A1!' + [Guid]::NewGuid().ToString('N')
$secure = ConvertTo-SecureString $password -AsPlainText -Force
$child = Join-Path $env:PUBLIC ('ncc-service-control-' + [Guid]::NewGuid().ToString('N') + '.ps1')
$log = $child + '.log'
try {
    New-LocalUser -Name $name -Password $secure -PasswordNeverExpires | Out-Null
    @'
$ErrorActionPreference = 'Stop'
$service = Get-Service NccAgentCore
Stop-Service NccAgentCore
$service.WaitForStatus('Stopped', [TimeSpan]::FromSeconds(30))
Start-Sleep -Seconds 7
$service.Refresh()
if ($service.Status -ne 'Stopped') { throw 'Manual stop triggered service recovery.' }
Start-Service NccAgentCore
$service.WaitForStatus('Running', [TimeSpan]::FromSeconds(30))
'@ | Set-Content -LiteralPath $child -Encoding ASCII
    $credential = [pscredential]::new("$env:COMPUTERNAME\$name", $secure)
    $process = Start-Process -FilePath 'powershell.exe' -Credential $credential -LoadUserProfile `
        -ArgumentList @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', ('"' + $child + '"')) `
        -RedirectStandardOutput $log -RedirectStandardError ($log + '.err') -Wait -PassThru
    if ($process.ExitCode -ne 0) {
        if (Test-Path $log) { Get-Content $log -Tail 30 }
        if (Test-Path ($log + '.err')) { Get-Content ($log + '.err') -Tail 30 }
        throw "Standard-user service control failed: $($process.ExitCode)"
    }
    if ((Get-Service NccAgentCore).Status -ne 'Running') { throw 'Service was not restarted by standard user.' }
} finally {
    Get-LocalUser -Name $name -ErrorAction SilentlyContinue | Remove-LocalUser -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $child, $log, ($log + '.err') -Force -ErrorAction SilentlyContinue
}
