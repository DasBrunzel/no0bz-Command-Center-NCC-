[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)] [string]$PrivateKey,
    [Parameter(Mandatory = $true)] [string]$KeyId,
    [string]$Version = "0.6.0-beta.1",
    [ValidateSet('windows')] [string]$Platform = 'windows',
    [string]$ArtifactUrl = '',
    [string]$OutputDirectory = ''
)

$ErrorActionPreference = 'Stop'
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = [Security.Principal.WindowsPrincipal]::new($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'Dieses Skript bitte in einer als Administrator gestarteten PowerShell ausfuehren. Der private Release-Schluessel ist absichtlich nur fuer Administratoren und SYSTEM lesbar.'
}
$project = Split-Path -Parent $PSScriptRoot
$OutputDirectory = if ($OutputDirectory) { $OutputDirectory } else { Join-Path $project 'dist\payloads' }
$python = Join-Path $project '.venv\Scripts\python.exe'
if (!(Test-Path $python)) { throw "Build-Python fehlt: $python" }
if (!(Test-Path $PrivateKey)) { throw "Private signing key is missing: $PrivateKey" }
if ($KeyId -notmatch '^[A-Za-z0-9._-]{1,64}$') { throw 'Invalid key ID.' }
$work = Join-Path $env:TEMP ('ncc-payload-build-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Force -Path $work, $OutputDirectory | Out-Null
try {
    $dist = Join-Path $work 'dist'; $build = Join-Path $work 'build'
    & $python -m PyInstaller --noconfirm --clean --onefile --name ncc-payload --paths (Join-Path $project 'backend') --collect-submodules ncc --collect-submodules ncc_agent --collect-submodules ncc_payload --distpath $dist --workpath $build --specpath $work (Join-Path $project 'backend\ncc_payload\__main__.py')
    if ($LASTEXITCODE -ne 0) { throw 'PyInstaller konnte den NCC-Payload nicht bauen.' }
    $content = Join-Path $work 'content'; New-Item -ItemType Directory -Force -Path $content | Out-Null
    Copy-Item (Join-Path $dist 'ncc-payload.exe') (Join-Path $content 'ncc-payload.exe')
    [IO.File]::WriteAllText((Join-Path $content 'payload.json'), (@{ executable = 'ncc-payload.exe'; arguments = @() } | ConvertTo-Json -Compress), [Text.UTF8Encoding]::new($false))
    $archive = Join-Path $OutputDirectory "ncc-payload-$Version-$Platform-x86_64.zip"
    if (Test-Path $archive) { Remove-Item -LiteralPath $archive -Force }
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    [IO.Compression.ZipFile]::CreateFromDirectory($content, $archive)
    $hash = (Get-FileHash $archive -Algorithm SHA256).Hash.ToLowerInvariant(); $size = (Get-Item $archive).Length
    $statement = Join-Path $work 'release-statement.txt'
    [IO.File]::WriteAllText($statement, "NCC-AGENT-RELEASE-V1`n$Version`n$hash`n$size`n", [Text.UTF8Encoding]::new($false))
    $signatureFile = Join-Path $work 'signature.bin'
    & openssl pkeyutl -sign -rawin -inkey $PrivateKey -in $statement -out $signatureFile
    if ($LASTEXITCODE -ne 0) { throw 'OpenSSL konnte den Payload nicht signieren.' }
    $signature = [Convert]::ToBase64String([IO.File]::ReadAllBytes($signatureFile))
    Write-Host "[NCC] Payload gebaut: $archive"
    if ($ArtifactUrl) {
        if ($ArtifactUrl -notmatch '^https://') { throw 'ArtifactUrl muss HTTPS verwenden.' }
        $manifest = @{ schema_version = 1; channel = 'beta'; released_at = [DateTime]::UtcNow.ToString('o'); minimum_core_version = '0.6.0-beta.1'; artifacts = @(@{ payload_version = $Version; platform = $Platform; architecture = 'x86_64'; url = $ArtifactUrl; sha256 = $hash; size_bytes = $size }); signature = @{ algorithm = 'ed25519'; key_id = $KeyId; value = $signature } }
        $manifestPath = "$archive.manifest.json"
        [IO.File]::WriteAllText($manifestPath, ($manifest | ConvertTo-Json -Depth 8), [Text.UTF8Encoding]::new($false))
        Write-Host "[NCC] Manifest: $manifestPath"
    }
} finally { Remove-Item -LiteralPath $work -Recurse -Force -ErrorAction SilentlyContinue }
