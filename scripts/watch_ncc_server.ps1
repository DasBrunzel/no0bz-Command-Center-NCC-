[CmdletBinding()]
param(
    [string]$ServerUrl,
    [int]$TimeoutSeconds = 12,
    [string]$ConfigPath = (Join-Path $env:ProgramData 'no0bz\NCC\config\server.env'),
    [switch]$ResolveOnly
)

# Local health guard for the Windows NCC server. It catches the otherwise hard
# to see state where the SCM wrapper is Running but its HTTP child has exited
# or stopped accepting requests. It never exposes a network port itself.
$ErrorActionPreference = 'Stop'
$root = Join-Path $env:ProgramData 'no0bz\NCC'
$logPath = Join-Path $root 'logs\server-watchdog.log'

# The production server commonly binds to its Tailscale address only. A probe
# against 127.0.0.1 would fail and restart a healthy server every five minutes.
if (-not $ServerUrl) {
    if (-not (Test-Path -LiteralPath $ConfigPath)) {
        throw "NCC server configuration not found: $ConfigPath"
    }
    $values = @{}
    foreach ($line in Get-Content -LiteralPath $ConfigPath -Encoding UTF8) {
        if ($line -match '^\s*(NCC_SERVER_HOST|NCC_SERVER_PORT)\s*=\s*(.*?)\s*$') {
            $value = $Matches[2].Trim()
            if ($value.Length -ge 2 -and $value[0] -eq $value[-1] -and $value[0] -in @('"', "'")) {
                $value = $value.Substring(1, $value.Length - 2)
            }
            $values[$Matches[1]] = $value
        }
    }
    $bindHost = $values['NCC_SERVER_HOST']
    $port = $values['NCC_SERVER_PORT']
    if (-not $port) { $port = '8350' }
    if (-not $bindHost -or $bindHost -notmatch '^[a-zA-Z0-9.:-]+$' -or $port -notmatch '^\d{1,5}$' -or [int]$port -lt 1 -or [int]$port -gt 65535) {
        throw 'NCC_SERVER_HOST or NCC_SERVER_PORT is invalid; refusing to restart the service.'
    }
    if ($bindHost -eq '0.0.0.0') { $bindHost = '127.0.0.1' }
    if ($bindHost -eq '::') { $bindHost = '::1' }
    if ($bindHost.Contains(':')) { $bindHost = "[$bindHost]" }
    $ServerUrl = "http://${bindHost}:$port"
}
if ($ResolveOnly) { Write-Output $ServerUrl; exit 0 }

New-Item -ItemType Directory -Path (Split-Path -Parent $logPath) -Force | Out-Null

$createdMutex = $false
$mutex = [Threading.Mutex]::new($true, 'Global\NccServerWatchdog', [ref]$createdMutex)
if (-not $createdMutex) { exit 0 }

function Write-WatchdogLog([string]$Message) {
    Add-Content -LiteralPath $logPath -Value "$(Get-Date -Format o) $Message"
}

function Test-NccReady {
    try {
        $response = Invoke-WebRequest -UseBasicParsing -Uri "$ServerUrl/api/v1/status/ready" -TimeoutSec $TimeoutSeconds
        return $response.StatusCode -eq 200
    } catch {
        return $false
    }
}

try {
    if (Test-NccReady) {
        exit 0
    }

    # One transient timeout must not interrupt the API and every connected agent.
    Start-Sleep -Seconds 3
    if (Test-NccReady) {
        Write-WatchdogLog "readiness recovered on second probe; url=$ServerUrl"
        exit 0
    }

    $service = Get-Service -Name NccServer -ErrorAction Stop
    $before = $service.Status.ToString()
    Write-WatchdogLog "readiness failed twice; url=$ServerUrl; service state=$before; restarting"
    if ($service.Status -eq 'Stopped') { Start-Service -Name NccServer }
    else { Restart-Service -Name NccServer -Force }

    $ready = $false
    foreach ($attempt in 1..3) {
        Start-Sleep -Seconds 8
        if (Test-NccReady) {
            $ready = $true
            break
        }
    }
    if (-not $ready) {
        Write-WatchdogLog 'restart completed but readiness is still failing'
        throw 'NccServer is still not ready after watchdog restart.'
    }
    Write-WatchdogLog 'recovered after restart'
} finally {
    if ($createdMutex) { $mutex.ReleaseMutex() | Out-Null }
    $mutex.Dispose()
}
