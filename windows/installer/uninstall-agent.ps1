[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$admin = [Security.Principal.WindowsPrincipal]::new([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $admin.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) { throw 'Administrator rights required.' }

$name = 'NccAgentCore'
$service = Get-Service -Name $name -ErrorAction SilentlyContinue
if ($service) {
    if ($service.Status -ne 'Stopped') {
        Stop-Service -Name $name -Force
        $service.WaitForStatus('Stopped', [TimeSpan]::FromSeconds(30))
    }
    & sc.exe delete $name | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'Could not remove NCC Agent service.' }
}

$appDir = Split-Path -Parent $PSCommandPath
Get-CimInstance Win32_Process -Filter "Name='NccTray.exe'" -ErrorAction SilentlyContinue | ForEach-Object {
    if ($_.ExecutablePath -and [IO.Path]::GetFullPath($_.ExecutablePath).StartsWith([IO.Path]::GetFullPath($appDir), [StringComparison]::OrdinalIgnoreCase)) {
        Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
    }
}
$task = Get-ScheduledTask -TaskName 'NccAgentCore' -ErrorAction SilentlyContinue
if ($task) { Unregister-ScheduledTask -TaskName 'NccAgentCore' -Confirm:$false }
$rule = Get-NetFirewallRule -DisplayName 'NCC Agent Core' -ErrorAction SilentlyContinue
if ($rule) { $rule | Remove-NetFirewallRule }

# Never remove the sibling NCC Server data under ProgramData\no0bz\NCC.
$programData = [IO.Path]::GetFullPath($env:ProgramData).TrimEnd('\')
foreach ($path in @(
    (Join-Path $env:ProgramData 'no0bz\NCC Agent'),
    (Join-Path $env:ProgramData 'no0bz\NCC Agent Setup')
)) {
    $resolved = [IO.Path]::GetFullPath($path)
    if (-not $resolved.StartsWith($programData + '\', [StringComparison]::OrdinalIgnoreCase)) {
        throw "Unexpected NCC Agent data path: $resolved"
    }
    if (Test-Path -LiteralPath $resolved) {
        Remove-Item -LiteralPath $resolved -Recurse -Force -ErrorAction Stop
    }
}
