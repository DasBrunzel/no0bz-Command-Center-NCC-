[CmdletBinding()]
param()

# Read-only diagnostic for the per-node release gate. Secrets are used only in
# memory for the authenticated request and are never emitted.
$ErrorActionPreference = 'Stop'
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = [Security.Principal.WindowsPrincipal]::new($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'Dieses Skript bitte in einer als Administrator gestarteten PowerShell ausfuehren.'
}

function Read-EnvValue([string]$Path, [string]$Name) {
    $line = Get-Content -LiteralPath $Path | Where-Object { $_ -match "^$([regex]::Escape($Name))=" } | Select-Object -First 1
    if (!$line) { return '' }
    return (($line -split '=', 2)[1]).Trim().Trim('"')
}

$root = Join-Path $env:ProgramData 'no0bz\NCC'
$core = Join-Path $root 'core\ncc-core.exe'
$stateDir = Join-Path $root 'core-state'
$coreEnv = Join-Path $root 'config\core.env'
$trustedKeys = Join-Path $stateDir 'config\trusted-keys.json'
foreach ($path in @($core, $coreEnv)) {
    if (!(Test-Path -LiteralPath $path)) { throw "Benoetigte NCC-Datei fehlt: $path" }
}

$serverUrl = Read-EnvValue $coreEnv 'NCC_AGENT_SERVER_URL'
$token = Read-EnvValue $coreEnv 'NCC_AGENT_TOKEN'
if (!$serverUrl -or !$token) { throw 'core.env enthaelt keine vollstaendige NCC-Agent-Verbindung.' }
$state = & $core --state-dir $stateDir status 2>&1 | Out-String
$service = Get-Service -Name NccCore -ErrorAction Stop
$keyInstalled = $false
if (Test-Path -LiteralPath $trustedKeys) {
    try { $keyInstalled = [bool]((Get-Content -Raw $trustedKeys | ConvertFrom-Json).keys.'ncc-release-2026') } catch { $keyInstalled = $false }
}

$pendingUrl = "$($serverUrl.TrimEnd('/'))/api/v1/releases/pending"
$pendingStatus = $null
$pendingBody = ''
try {
    $params = @{ Uri = $pendingUrl; Headers = @{ Authorization = "Bearer $token" }; Method = 'Get'; ErrorAction = 'Stop' }
    if ((Get-Command Invoke-WebRequest).Parameters.ContainsKey('UseBasicParsing')) { $params.UseBasicParsing = $true }
    $response = Invoke-WebRequest @params
    $pendingStatus = [int]$response.StatusCode
    $pendingBody = [string]$response.Content
} catch {
    $response = $_.Exception.Response
    if ($response) {
        $pendingStatus = [int]$response.StatusCode
        try {
            $reader = [IO.StreamReader]::new($response.GetResponseStream())
            $pendingBody = $reader.ReadToEnd()
            $reader.Dispose()
        } catch { $pendingBody = $_.Exception.Message }
    } else {
        $pendingBody = $_.Exception.Message
    }
}

[pscustomobject]@{
    NccCoreService = $service.Status.ToString()
    CoreState = ($state.Trim() | ConvertFrom-Json)
    ServerUrl = $serverUrl
    TrustedReleaseKeyInstalled = $keyInstalled
    PendingReleaseHttpStatus = $pendingStatus
    PendingReleaseResponse = $pendingBody
    LogPath = (Join-Path $root 'logs\core.log')
} | ConvertTo-Json -Depth 6
