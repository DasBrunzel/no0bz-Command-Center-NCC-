[CmdletBinding()]
param(
    [string]$PayloadPath = '',
    [string]$OutputDirectory = ''
)

$ErrorActionPreference = 'Stop'
$root = Join-Path $env:ProgramData 'no0bz\NCC\core-state'
if (!$PayloadPath) {
    $PayloadPath = Get-ChildItem (Join-Path $root 'payloads') -Directory |
        Sort-Object LastWriteTime -Descending |
        ForEach-Object { Join-Path $_.FullName 'files\ncc-payload.exe' } |
        Where-Object { Test-Path -LiteralPath $_ } |
        Select-Object -First 1
}
if (!$OutputDirectory) { $OutputDirectory = Join-Path $root 'diagnostics\system-payload' }
if (!(Test-Path -LiteralPath $PayloadPath -PathType Leaf)) { throw "Payload fehlt: $PayloadPath" }
New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null
$state = Join-Path $OutputDirectory 'state'
$data = Join-Path $OutputDirectory 'data'
$stdout = Join-Path $OutputDirectory 'stdout.log'
$stderr = Join-Path $OutputDirectory 'stderr.log'
New-Item -ItemType Directory -Force -Path $state, $data | Out-Null

# The endpoint is deliberately unreachable. This proves process startup under
# LocalSystem without sending telemetry or enrolling a diagnostic node.
$start = [Diagnostics.ProcessStartInfo]::new()
$start.FileName = $PayloadPath
$start.UseShellExecute = $false
$start.RedirectStandardOutput = $true
$start.RedirectStandardError = $true
$start.Environment['NCC_CORE_STATE_DIR'] = $state
$start.Environment['NCC_PAYLOAD_VERSION'] = 'system-diagnostic'
$start.Environment['NCC_AGENT_SERVER_URL'] = 'http://127.0.0.1:1'
$start.Environment['NCC_AGENT_ALLOW_INSECURE_HTTP'] = '1'
$start.Environment['NCC_AGENT_TOKEN'] = 'system-diagnostic-no-network'
$start.Environment['NCC_AGENT_DATA_DIR'] = $data
$process = [Diagnostics.Process]::new()
$process.StartInfo = $start
if (!$process.Start()) { throw 'Payload konnte nicht gestartet werden.' }

try {
    $deadline = (Get-Date).AddSeconds(15)
    $healthFile = Join-Path $state 'payload-health.json'
    do { Start-Sleep -Milliseconds 250 } while (!(Test-Path $healthFile) -and !$process.HasExited -and (Get-Date) -lt $deadline)
} finally {
    if (!$process.HasExited) { $process.Kill(); $process.WaitForExit() }
    [IO.File]::WriteAllText($stdout, $process.StandardOutput.ReadToEnd(), [Text.UTF8Encoding]::new($false))
    [IO.File]::WriteAllText($stderr, $process.StandardError.ReadToEnd(), [Text.UTF8Encoding]::new($false))
}

[pscustomobject]@{
    Health = if (Test-Path (Join-Path $state 'payload-health.json')) { Get-Content (Join-Path $state 'payload-health.json') -Raw } else { 'MISSING' }
    ExitCode = $process.ExitCode
    StandardError = $stderr
} | ConvertTo-Json
