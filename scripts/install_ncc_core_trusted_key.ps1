[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)] [ValidatePattern('^[A-Za-z0-9._-]{1,64}$')] [string]$KeyId,
    [Parameter(Mandatory = $true)] [string]$PublicKey
)

# Installs only an Ed25519 *public* verification key.  Private release signing
# keys must stay off the monitored hosts and are never accepted by this script.
$ErrorActionPreference = 'Stop'
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = [Security.Principal.WindowsPrincipal]::new($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'Dieses Skript bitte in einer als Administrator gestarteten PowerShell ausführen.'
}
try { $raw = [Convert]::FromBase64String($PublicKey) } catch { throw 'Der öffentliche Schlüssel ist kein gültiges Base64.' }
if ($raw.Length -ne 32) { throw 'Ein Ed25519-öffentlicher Schlüssel muss genau 32 Bytes haben.' }

$configRoot = Join-Path $env:ProgramData 'no0bz\NCC\core-state\config'
$path = Join-Path $configRoot 'trusted-keys.json'
New-Item -ItemType Directory -Force -Path $configRoot | Out-Null
$keys = @{}
if (Test-Path -LiteralPath $path) {
    try {
        $existing = Get-Content -LiteralPath $path -Raw | ConvertFrom-Json
        foreach ($property in $existing.keys.psobject.Properties) { $keys[$property.Name] = [string]$property.Value }
    } catch { throw "Bestehende Vertrauensdatei ist ungültig: $path" }
}
$keys[$KeyId] = $PublicKey
[IO.File]::WriteAllText($path, (@{ keys = $keys } | ConvertTo-Json -Compress), [Text.UTF8Encoding]::new($false))
& icacls.exe $path /inheritance:r /grant:r '*S-1-5-18:F' '*S-1-5-32-544:F' | Out-Null
[pscustomobject]@{ Result = 'Public release key installed'; KeyId = $KeyId; Path = $path } | ConvertTo-Json
