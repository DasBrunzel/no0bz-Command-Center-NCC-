[CmdletBinding()]
param(
    [string]$ServerUrl = "http://100.88.247.35/graphql",
    [string]$DisplayName = "horsttower"
)

$ErrorActionPreference = "Stop"
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = [Security.Principal.WindowsPrincipal]::new($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Start-Process powershell.exe -Verb RunAs -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`" -ServerUrl `"$ServerUrl`" -DisplayName `"$DisplayName`""
    exit
}

function Quote-DotEnv([string]$Value) {
    if ($Value.Contains("`r") -or $Value.Contains("`n")) { throw "Konfigurationswerte dürfen keine Zeilenumbrüche enthalten." }
    return '"' + $Value.Replace('\', '\\').Replace('"', '\"') + '"'
}

$configPath = Join-Path $env:ProgramData "no0bz\NCC\config\server.env"
if (-not (Test-Path $configPath)) { throw "NCC-Server-Konfiguration wurde nicht gefunden: $configPath" }
if ($ServerUrl -notmatch '^http://100\.(6[4-9]|[7-9][0-9]|1[01][0-9]|12[0-7])\.[0-9]{1,3}\.[0-9]{1,3}/graphql$') {
    throw "Für Unraid ist ausschließlich eine Tailscale-GraphQL-Adresse zulässig."
}

$secureKey = Read-Host "Unraid API-Key für $DisplayName" -AsSecureString
$pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureKey)
try {
    $apiKey = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)
    if (-not $apiKey) { throw "Ein API-Key ist erforderlich." }
    $body = @{ query = "query NccConnectionCheck { __typename }" } | ConvertTo-Json -Compress
    $response = Invoke-RestMethod -Method Post -Uri $ServerUrl -Headers @{ "x-api-key" = $apiKey } -ContentType "application/json" -Body $body -TimeoutSec 15
    if (-not $response.data) { throw "Unraid hat keine gültige GraphQL-Antwort geliefert." }

    $lines = [IO.File]::ReadAllLines($configPath) | Where-Object {
        $_ -notmatch '^NCC(_SERVER)?_UNRAID_(URL|API_KEY|DISPLAY_NAME)='
    }
    $lines += "NCC_SERVER_UNRAID_URL=$(Quote-DotEnv $ServerUrl)"
    $lines += "NCC_SERVER_UNRAID_API_KEY=$(Quote-DotEnv $apiKey)"
    $lines += "NCC_SERVER_UNRAID_DISPLAY_NAME=$(Quote-DotEnv $DisplayName)"
    [IO.File]::WriteAllLines($configPath, $lines, [Text.UTF8Encoding]::new($false))
    & icacls.exe $configPath /inheritance:r /grant:r '*S-1-5-18:F' '*S-1-5-32-544:F' | Out-Null
} finally {
    if ($pointer -ne [IntPtr]::Zero) { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer) }
}

Restart-Service -Name NccServer
Write-Host "[NCC] Unraid-Verbindung für $DisplayName wurde geprüft und geschützt gespeichert."
Write-Host "[NCC] Der API-Key wird nicht angezeigt und nicht in GitHub gespeichert."
