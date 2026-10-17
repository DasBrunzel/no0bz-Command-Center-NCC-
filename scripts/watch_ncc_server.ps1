[CmdletBinding()]
param(
    [string]$ServerUrl = 'http://127.0.0.1:8350',
    [int]$TimeoutSeconds = 12
)

# Local health guard for the Windows NCC server. It catches the otherwise hard
# to see state where the SCM wrapper is Running but its HTTP child has exited
# or stopped accepting requests. It never exposes a network port itself.
$ErrorActionPreference = 'Stop'
$root = Join-Path $env:ProgramData 'no0bz\NCC'
$logPath = Join-Path $root 'logs\server-watchdog.log'
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

    $service = Get-Service -Name NccServer -ErrorAction Stop
    $before = $service.Status.ToString()
    Write-WatchdogLog "readiness failed; service state=$before; restarting"
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
