[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)] [string]$PrivateKey,
    [Parameter(Mandatory = $true)] [string]$KeyId,
    [Parameter(Mandatory = $true)] [string]$Version,
    [Parameter(Mandatory = $true)] [ValidateSet('windows', 'linux')] [string]$Platform,
    [Parameter(Mandatory = $true)] [string]$ArtifactPath,
    [Parameter(Mandatory = $true)] [string]$ArtifactUrl,
    [ValidateSet('beta', 'stable')] [string]$Channel = 'beta',
    [string]$OutputPath = ''
)

$ErrorActionPreference = 'Stop'
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = [Security.Principal.WindowsPrincipal]::new($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'Dieses Skript muss in einer als Administrator gestarteten PowerShell laufen. Der private Release-Schluessel bleibt nur fuer Administratoren und SYSTEM lesbar.'
}
if ($KeyId -notmatch '^[A-Za-z0-9._-]{1,64}$') { throw 'Invalid key ID.' }
if ($Version -notmatch '^\d+\.\d+\.\d+(-[A-Za-z0-9.-]+)?$') { throw 'Invalid semantic version.' }
if ($ArtifactUrl -notmatch '^https://') { throw 'ArtifactUrl must use HTTPS.' }
if (!(Test-Path -LiteralPath $PrivateKey -PathType Leaf)) { throw "Private signing key is missing: $PrivateKey" }
if (!(Test-Path -LiteralPath $ArtifactPath -PathType Leaf)) { throw "Artifact is missing: $ArtifactPath" }
try {
    $handle = [IO.File]::Open($PrivateKey, [IO.FileMode]::Open, [IO.FileAccess]::Read, [IO.FileShare]::Read)
    $handle.Dispose()
} catch { throw "Der private Release-Schluessel ist nicht lesbar: $PrivateKey" }

$artifact = Get-Item -LiteralPath $ArtifactPath
$hash = (Get-FileHash -LiteralPath $artifact.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
$size = $artifact.Length
$work = Join-Path $env:TEMP ('ncc-sign-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Force -Path $work | Out-Null
try {
    $statement = Join-Path $work 'release-statement.txt'
    $signatureFile = Join-Path $work 'signature.bin'
    [IO.File]::WriteAllText($statement, "NCC-AGENT-RELEASE-V1`n$Version`n$hash`n$size`n", [Text.UTF8Encoding]::new($false))
    & openssl pkeyutl -sign -rawin -inkey $PrivateKey -in $statement -out $signatureFile
    if ($LASTEXITCODE -ne 0) { throw 'OpenSSL konnte das Linux-Artefakt nicht signieren.' }
    $manifest = @{
        schema_version = 1; channel = $Channel; released_at = [DateTime]::UtcNow.ToString('o')
        minimum_core_version = '0.6.0-beta.1'
        artifacts = @(@{ payload_version = $Version; platform = $Platform; architecture = 'x86_64'; url = $ArtifactUrl; sha256 = $hash; size_bytes = $size })
        signature = @{ algorithm = 'ed25519'; key_id = $KeyId; value = [Convert]::ToBase64String([IO.File]::ReadAllBytes($signatureFile)) }
    }
    $OutputPath = if ($OutputPath) { $OutputPath } else { "$($artifact.FullName).manifest.json" }
    [IO.File]::WriteAllText($OutputPath, ($manifest | ConvertTo-Json -Depth 8), [Text.UTF8Encoding]::new($false))
    [PSCustomObject]@{ Result = 'NCC payload artifact signed'; Artifact = $artifact.FullName; Manifest = $OutputPath; Platform = $Platform; Version = $Version; Sha256 = $hash; SizeBytes = $size } | ConvertTo-Json
} finally { Remove-Item -LiteralPath $work -Recurse -Force -ErrorAction SilentlyContinue }
