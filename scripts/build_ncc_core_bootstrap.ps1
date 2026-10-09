[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[A-Za-z0-9._-]{1,64}$')]
    [string]$KeyId,
    [Parameter(Mandatory = $true)]
    [string]$PublicKey,
    [ValidatePattern('^\d+\.\d+\.\d+(?:-[A-Za-z0-9.-]+)?$')]
    [string]$Version = '0.6.0-beta.3',
    [string]$OutputDirectory = ''
)

# Produces the small, source-checkout-free Windows bootstrap ZIP. The embedded
# key is public verification material only; a signing private key is neither
# read nor included in this artifact.
$ErrorActionPreference = 'Stop'
try { $keyBytes = [Convert]::FromBase64String($PublicKey) } catch { throw 'PublicKey ist kein gueltiges Base64.' }
if ($keyBytes.Length -ne 32) { throw 'PublicKey muss ein 32-Byte Ed25519-Public-Key sein.' }

$project = Split-Path -Parent $PSScriptRoot
$OutputDirectory = if ($OutputDirectory) { $OutputDirectory } else { Join-Path $project 'dist\bootstrap' }
$core = Join-Path $project 'core\ncc-core\target\release\ncc-core.exe'
$installer = Join-Path $PSScriptRoot 'install_ncc_core_bootstrap.ps1'
$serviceSource = Join-Path $project 'backend\ncc_service'
foreach ($path in @($core, $installer, $serviceSource)) {
    if (-not (Test-Path -LiteralPath $path)) { throw "Bootstrap-Quelle fehlt: $path" }
}

$work = Join-Path $env:TEMP ('ncc-core-bootstrap-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Force -Path $work, $OutputDirectory | Out-Null
try {
    Copy-Item -LiteralPath $core -Destination (Join-Path $work 'ncc-core.exe')
    Copy-Item -LiteralPath $installer -Destination (Join-Path $work 'install_ncc_core_bootstrap.ps1')
    New-Item -ItemType Directory -Force -Path (Join-Path $work 'service-package\backend') | Out-Null
    Copy-Item -LiteralPath $serviceSource -Destination (Join-Path $work 'service-package\backend\ncc_service') -Recurse
    Get-ChildItem -LiteralPath (Join-Path $work 'service-package') -Directory -Recurse -Filter '__pycache__' |
        Remove-Item -Recurse -Force
    @"
[build-system]
requires = ["setuptools>=70"]
build-backend = "setuptools.build_meta"

[project]
name = "ncc-core-service-bootstrap"
version = "$Version"
requires-python = ">=3.10"

[tool.setuptools.packages.find]
where = ["backend"]
"@ | Set-Content -LiteralPath (Join-Path $work 'service-package\pyproject.toml') -Encoding utf8
    @{ keys = @{ $KeyId = $PublicKey } } | ConvertTo-Json -Compress | Set-Content -LiteralPath (Join-Path $work 'trusted-keys.json') -Encoding utf8
    $readme = @"
# NCC Core Bootstrap $Version

1. Im NCC-Dashboard zuerst diesem bestehenden Geraet einen freigegebenen 0.6-Release zuweisen.
2. ZIP vollstaendig entpacken.
3. `install_ncc_core_bootstrap.ps1` als Administrator ausfuehren.

Der Bootstrap uebernimmt die vorhandene NCC-Identitaet, prueft den signierten
Payload und entfernt den alten NccAgent erst nach erfolgreicher Core-Gesundheit.
"@
    Set-Content -LiteralPath (Join-Path $work 'README.md') -Value $readme -Encoding utf8
    $zip = Join-Path $OutputDirectory "ncc-core-bootstrap-$Version-windows-x86_64.zip"
    if (Test-Path -LiteralPath $zip) { Remove-Item -LiteralPath $zip -Force }
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    [IO.Compression.ZipFile]::CreateFromDirectory($work, $zip)
    [pscustomobject]@{
        Result = 'NCC Core bootstrap package built'
        Package = $zip
        Sha256 = (Get-FileHash -LiteralPath $zip -Algorithm SHA256).Hash.ToLowerInvariant()
        Included = @('ncc-core.exe', 'install_ncc_core_bootstrap.ps1', 'ncc_service service wrapper', 'trusted public release key')
    } | ConvertTo-Json -Depth 4
} finally {
    Remove-Item -LiteralPath $work -Recurse -Force -ErrorAction SilentlyContinue
}
