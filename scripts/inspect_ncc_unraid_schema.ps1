[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = [Security.Principal.WindowsPrincipal]::new($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Start-Process powershell.exe -Verb RunAs -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`""
    exit
}

$configPath = Join-Path $env:ProgramData "no0bz\NCC\config\server.env"
if (-not (Test-Path $configPath)) { throw "NCC-Server-Konfiguration wurde nicht gefunden." }
$values = @{}
foreach ($line in [IO.File]::ReadAllLines($configPath)) {
    $parts = $line.Trim().Split("=", 2)
    if ($parts.Count -eq 2 -and $parts[0] -in "NCC_SERVER_UNRAID_URL", "NCC_UNRAID_URL", "NCC_SERVER_UNRAID_API_KEY", "NCC_UNRAID_API_KEY") {
        $values[$parts[0]] = $parts[1].Trim().Trim('"').Replace('\"', '"').Replace('\\', '\')
    }
}
$url = $values["NCC_SERVER_UNRAID_URL"]
if (-not $url) { $url = $values["NCC_UNRAID_URL"] }
$apiKey = $values["NCC_SERVER_UNRAID_API_KEY"]
if (-not $apiKey) { $apiKey = $values["NCC_UNRAID_API_KEY"] }
if (-not $url -or -not $apiKey) { throw "Die Unraid-Verbindung ist nicht vollständig eingerichtet." }

$query = @'
query NccSchema {
  __schema {
    queryType { name }
    types {
      kind name
      fields {
        name
        args { name }
        type { kind name ofType { kind name ofType { kind name } } }
      }
    }
  }
}
'@
$response = Invoke-RestMethod -Method Post -Uri $url -Headers @{ "x-api-key" = $apiKey } -ContentType "application/json" -Body (@{ query = $query } | ConvertTo-Json -Compress) -TimeoutSec 30
if (-not $response.data.__schema) { throw "Unraid hat keine Schema-Antwort geliefert." }
$target = Join-Path $env:USERPROFILE "Desktop\ncc-unraid-schema.json"
$response.data.__schema | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $target -Encoding utf8
Write-Host "[NCC] Unraid-Schema wurde ohne API-Key gespeichert: $target"
