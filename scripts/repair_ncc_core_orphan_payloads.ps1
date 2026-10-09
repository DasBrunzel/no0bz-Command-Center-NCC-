[CmdletBinding()]
param()

# Recover a host after an interrupted foreground Core update test.  Only
# payload executables below the NCC Core state directory are targeted; it
# never touches arbitrary Python processes, pairings, or agent.env.
$ErrorActionPreference = 'Stop'
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = [Security.Principal.WindowsPrincipal]::new($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'Dieses Reparatur-Skript bitte in einer als Administrator gestarteten PowerShell ausfuehren.'
}

$root = Join-Path $env:ProgramData 'no0bz\NCC'
$coreState = Join-Path $root 'core-state'
$core = Join-Path $root 'core\ncc-core.exe'
if (-not (Test-Path -LiteralPath $core)) { throw "NccCore fehlt: $core" }

# Stop the service first so it cannot start a new payload while stale children
# are being removed. NccAgent deliberately remains disabled as rollback fallback.
Stop-Service -Name NccCore -Force -ErrorAction SilentlyContinue

$escapedRoot = [regex]::Escape((Join-Path $coreState 'payloads'))
$payloadPattern = '(?i)^"?' + $escapedRoot + '.*\\files\\.*\.(exe|py)("|\s|$)'
$orphans = @(Get-CimInstance Win32_Process | Where-Object {
    $_.CommandLine -and $_.CommandLine -match $payloadPattern
})
foreach ($process in $orphans) {
    Stop-Process -Id $process.ProcessId -Force -ErrorAction Stop
}

$deadline = (Get-Date).AddSeconds(10)
do {
    Start-Sleep -Milliseconds 250
    $remaining = @(Get-CimInstance Win32_Process | Where-Object {
        $_.CommandLine -and $_.CommandLine -match $payloadPattern
    })
} while ($remaining.Count -gt 0 -and (Get-Date) -lt $deadline)
if ($remaining.Count -gt 0) {
    throw "Mindestens ein NCC-Payload-Prozess konnte nicht beendet werden: $($remaining.ProcessId -join ', ')"
}

Start-Service -Name NccCore
$healthy = $false
$state = $null
for ($attempt = 0; $attempt -lt 30; $attempt++) {
    Start-Sleep -Seconds 1
    $raw = & $core --state-dir $coreState status 2>$null
    try { $state = $raw | ConvertFrom-Json } catch { continue }
    if ($state.health -eq 'healthy' -and $state.active_payload) {
        $healthy = $true
        break
    }
}
if (-not $healthy) {
    throw "NccCore wurde gestartet, meldet aber noch keinen gesunden Payload: $raw"
}

[pscustomobject]@{
    Result = 'Stale NCC Core payloads removed; NccCore restarted'
    RemovedPayloadProcesses = @($orphans | Select-Object ProcessId, Name, CommandLine)
    CoreState = $state
    NccCore = (Get-Service NccCore).Status.ToString()
    NccAgent = (Get-Service NccAgent).Status.ToString()
} | ConvertTo-Json -Depth 5
