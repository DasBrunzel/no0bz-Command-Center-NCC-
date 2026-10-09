[CmdletBinding()]
param(
    [ValidatePattern('^[A-Za-z0-9._-]{1,64}$')]
    [string]$KeyId = 'ncc-release-2026',
    [string]$SignerRoot = (Join-Path $env:ProgramData 'no0bz\NCC\release-signer')
)

# Repairs ACL inheritance only. It never prints, copies, exports, or changes
# the encrypted private key or its passphrase.
$ErrorActionPreference = 'Stop'
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = [Security.Principal.WindowsPrincipal]::new($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'Dieses Skript bitte in einer als Administrator gestarteten PowerShell ausfuehren.'
}

$privateKey = Join-Path $SignerRoot "$KeyId-private.pem"
if (!(Test-Path -LiteralPath $privateKey)) { throw "Privater Release-Schluessel fehlt: $privateKey" }

& icacls.exe $SignerRoot /inheritance:r /grant:r '*S-1-5-18:(OI)(CI)F' '*S-1-5-32-544:(OI)(CI)F' | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'Die Signer-Ordnerberechtigungen konnten nicht repariert werden.' }
Get-ChildItem -LiteralPath $SignerRoot -Force -File | ForEach-Object {
    & icacls.exe $_.FullName /inheritance:r /grant:r '*S-1-5-18:F' '*S-1-5-32-544:F' | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "Die Signer-Berechtigungen konnten nicht repariert werden: $($_.Name)" }
}

try {
    $handle = [IO.File]::Open($privateKey, [IO.FileMode]::Open, [IO.FileAccess]::Read, [IO.FileShare]::Read)
    $handle.Dispose()
} catch {
    throw 'Der private Schluessel ist trotz Reparatur nicht lesbar. Es wurden keine Schluesseldateien veraendert.'
}

[pscustomobject]@{
    Result = 'Release signer ACL repaired and private key read access verified'
    KeyId = $KeyId
    Access = 'SYSTEM and local Administrators only'
} | ConvertTo-Json
