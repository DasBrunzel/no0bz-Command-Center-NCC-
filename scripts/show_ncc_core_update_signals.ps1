[CmdletBinding()]
param()

# Compact, read-only helper for sharing only the useful Core update signals.
# It never prints environment files, tokens, or full telemetry logs.
$root = Join-Path $env:ProgramData 'no0bz\NCC'
$logPath = Join-Path $root 'logs\core.log'
if (!(Test-Path -LiteralPath $logPath)) {
    'NCC_CORE_LOG_MISSING'
    exit 0
}

$pattern = '(?i)ncc-core:|update check|release (request|response|download)|download(ed)?|stage|activat|signature|sha-?256|hash|error|failed|skipped|denied|untrusted|invalid'
$signals = @(Get-Content -LiteralPath $logPath -Tail 300 | Where-Object { $_ -match $pattern } | Select-Object -Last 30)
if ($signals.Count -eq 0) {
    'NCC_CORE_UPDATE_SIGNALS_EMPTY'
} else {
    $signals
}
