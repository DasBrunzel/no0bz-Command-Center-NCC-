[CmdletBinding()]
param(
    [string]$Version = '',
    [string]$InitialManifest = '',
    [string]$InitialPayload = '',
    [string]$TrustedKeys = '',
    [string]$UpdateFeedUrl = 'https://raw.githubusercontent.com/DasBrunzel/no0bz-Command-Center-NCC-/codex/ncc-v0.6-agent-foundation/windows/installer/update-feed.json',
    [string]$ArtifactUrl = '',
    [string]$PrivateKey = '',
    [string]$KeyId = 'ncc-release-2026',
    [string]$OutputDirectory = ''
)

$ErrorActionPreference = 'Stop'
$project = Split-Path -Parent $PSScriptRoot
$installer = Join-Path $project 'windows\installer'
$Version = if ($Version) { $Version } else { [string]((Get-Content -LiteralPath (Join-Path $project 'frontend\package.json') -Raw | ConvertFrom-Json).version) }
if ($Version -notmatch '^\d+\.\d+\.\d+-(?:beta|rc|alpha)\.\d+(?:-dev\.\d+)?$') { throw 'Invalid NCC Agent setup version.' }
if ($UpdateFeedUrl -notmatch '^https://') { throw 'Installer update feed must use HTTPS.' }
if ($ArtifactUrl -and $ArtifactUrl -notmatch '^https://') { throw 'Installer artifact URL must use HTTPS.' }
if (($ArtifactUrl -and -not $PrivateKey) -or ($PrivateKey -and -not $ArtifactUrl)) {
    throw 'A signed release requires both ArtifactUrl and PrivateKey.'
}
$InitialManifest = if ($InitialManifest) { $InitialManifest } else { Join-Path $installer 'initial-release.manifest.json' }
$TrustedKeys = if ($TrustedKeys) { $TrustedKeys } else { Join-Path $installer 'trusted-keys.json' }
$OutputDirectory = if ($OutputDirectory) { $OutputDirectory } else { Join-Path $project 'dist\installer' }
$manifest = Get-Content -LiteralPath $InitialManifest -Raw | ConvertFrom-Json
$artifact = @($manifest.artifacts | Where-Object { $_.platform -eq 'windows' -and $_.architecture -eq 'x86_64' }) | Select-Object -First 1
if (-not $artifact -or $manifest.signature.algorithm -ne 'ed25519') { throw 'Initial release manifest is invalid.' }
if (-not $InitialPayload) {
    $InitialPayload = Join-Path $project ('dist\payloads\ncc-payload-' + $artifact.payload_version + '-windows-x86_64.zip')
}
if (-not (Test-Path -LiteralPath $InitialPayload -PathType Leaf)) {
    if ($artifact.url -notmatch '^https://') { throw 'Initial release URL must use HTTPS.' }
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $InitialPayload) | Out-Null
    Invoke-WebRequest -UseBasicParsing -Uri $artifact.url -OutFile $InitialPayload
}
if ((Get-Item -LiteralPath $InitialPayload).Length -ne [long]$artifact.size_bytes) { throw 'Initial payload size does not match its signed manifest.' }
if ((Get-FileHash -LiteralPath $InitialPayload -Algorithm SHA256).Hash.ToLowerInvariant() -ne $artifact.sha256.ToLowerInvariant()) {
    throw 'Initial payload SHA-256 does not match its signed manifest.'
}
$keys = Get-Content -LiteralPath $TrustedKeys -Raw | ConvertFrom-Json
$key = $keys.keys.PSObject.Properties[$manifest.signature.key_id]
if (-not $key -or [Convert]::FromBase64String([string]$key.Value).Length -ne 32) { throw 'The initial release key is not trusted.' }

$dotnet = (Get-Command dotnet -ErrorAction Stop).Source
$cargo = (Get-Command cargo -ErrorAction Stop).Source
$iscc = (Get-Command ISCC.exe -ErrorAction SilentlyContinue).Source
if (-not $iscc) {
    $iscc = @(
        (Join-Path $env:LOCALAPPDATA 'Programs\Inno Setup 7\ISCC.exe'),
        'C:\Program Files (x86)\Inno Setup 7\ISCC.exe',
        'C:\Program Files (x86)\Inno Setup 6\ISCC.exe',
        'C:\Program Files\Inno Setup 7\ISCC.exe',
        'C:\Program Files\Inno Setup 6\ISCC.exe'
    ) | Where-Object { Test-Path -LiteralPath $_ -PathType Leaf } | Select-Object -First 1
}
if (-not $iscc -or -not (Test-Path -LiteralPath $iscc)) { throw 'Inno Setup compiler (ISCC.exe) is required to build setup.exe.' }

$stage = Join-Path $project ('dist\installer-stage\' + $Version)
New-Item -ItemType Directory -Force -Path $stage, $OutputDirectory | Out-Null
& $dotnet publish (Join-Path $project 'windows\NccTray\NccTray.csproj') -c Release -r win-x64 --self-contained true '-p:PublishSingleFile=true' '-p:PublishTrimmed=false' -o (Join-Path $stage 'tray')
if ($LASTEXITCODE -ne 0) { throw 'NCC Tray build failed.' }
& $dotnet publish (Join-Path $project 'windows\NccServiceHost\NccServiceHost.csproj') -c Release -r win-x64 --self-contained true '-p:PublishSingleFile=true' '-p:PublishTrimmed=false' -o (Join-Path $stage 'service')
if ($LASTEXITCODE -ne 0) { throw 'NCC Service Host build failed.' }
& $cargo build --release --manifest-path (Join-Path $project 'core\ncc-core\Cargo.toml')
if ($LASTEXITCODE -ne 0) { throw 'NCC Core build failed.' }

Copy-Item -LiteralPath (Join-Path $stage 'tray\NccTray.exe') -Destination (Join-Path $stage 'NccTray.exe') -Force
Copy-Item -LiteralPath (Join-Path $stage 'service\NccServiceHost.exe') -Destination (Join-Path $stage 'NccServiceHost.exe') -Force
Copy-Item -LiteralPath (Join-Path $project 'core\ncc-core\target\release\ncc-core.exe') -Destination (Join-Path $stage 'ncc-core.exe') -Force
Copy-Item -LiteralPath $InitialPayload -Destination (Join-Path $stage 'initial-payload.zip') -Force
Copy-Item -LiteralPath $InitialManifest -Destination (Join-Path $stage 'initial-payload.manifest.json') -Force
Copy-Item -LiteralPath $TrustedKeys -Destination (Join-Path $stage 'trusted-keys.json') -Force
foreach ($name in @('install-agent.ps1', 'preinstall-agent.ps1', 'uninstall-agent.ps1')) {
    Copy-Item -LiteralPath (Join-Path $installer $name) -Destination (Join-Path $stage $name) -Force
}
[IO.File]::WriteAllText((Join-Path $stage 'installer-version.txt'), $Version, [Text.UTF8Encoding]::new($false))
[IO.File]::WriteAllText((Join-Path $stage 'installer-feed-url.txt'), $UpdateFeedUrl, [Text.UTF8Encoding]::new($false))

# Exercise the actual Core signature verifier against a disposable state dir.
# A matching hash alone does not prove that the release was signed by NCC.
$verification = Join-Path $stage 'signature-check'
$verifyKeys = Join-Path $verification 'config\trusted-keys.json'
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $verifyKeys) | Out-Null
Copy-Item -LiteralPath $TrustedKeys -Destination $verifyKeys -Force
& (Join-Path $stage 'ncc-core.exe') --state-dir $verification stage --source (Join-Path $stage 'initial-payload.zip') --version $artifact.payload_version --sha256 $artifact.sha256 --size $artifact.size_bytes --key-id $manifest.signature.key_id --signature $manifest.signature.value
if ($LASTEXITCODE -ne 0) { throw 'NCC Core rejected the initial payload signature.' }

& $iscc "/DVersion=$Version" "/DStage=$stage" "/DOutput=$OutputDirectory" (Join-Path $installer 'NccAgent.iss')
if ($LASTEXITCODE -ne 0) { throw 'Inno Setup could not create NCC Agent setup.exe.' }
$setup = Join-Path $OutputDirectory "ncc-agent-setup-$Version-windows-x86_64.exe"
if (-not (Test-Path -LiteralPath $setup -PathType Leaf)) { throw 'NCC Agent setup.exe is missing after compilation.' }
$hash = (Get-FileHash -LiteralPath $setup -Algorithm SHA256).Hash.ToLowerInvariant()
[IO.File]::WriteAllText("$setup.sha256", "$hash  $(Split-Path -Leaf $setup)`n", [Text.UTF8Encoding]::new($false))
$signedManifest = $null
if ($PrivateKey) {
    if (-not (Test-Path -LiteralPath $PrivateKey -PathType Leaf)) { throw 'Private signing key is missing.' }
    if (-not $keys.keys.PSObject.Properties[$KeyId]) { throw 'Signer key ID is absent from trusted keys.' }
    $openssl = (Get-Command openssl -ErrorAction SilentlyContinue).Source
    if (-not $openssl) {
        $openssl = @('C:\Program Files\Git\usr\bin\openssl.exe', 'C:\Program Files\Git\mingw64\bin\openssl.exe', 'C:\Program Files\OpenSSL-Win64\bin\openssl.exe') |
            Where-Object { Test-Path -LiteralPath $_ -PathType Leaf } | Select-Object -First 1
    }
    if (-not $openssl) { throw 'OpenSSL is required to sign the installer release.' }
    $statement = Join-Path $OutputDirectory 'installer-signing-statement.tmp'
    $signatureFile = Join-Path $OutputDirectory 'installer-signature.tmp'
    $signedManifest = "$setup.manifest.json"
    try {
        $size = (Get-Item -LiteralPath $setup).Length
        $bytes = "NCC-AGENT-INSTALLER-V1`n$Version`n$hash`n$size`n$ArtifactUrl`n"
        [IO.File]::WriteAllText($statement, $bytes, [Text.UTF8Encoding]::new($false))
        & $openssl pkeyutl -sign -rawin -inkey $PrivateKey -in $statement -out $signatureFile
        if ($LASTEXITCODE -ne 0) { throw 'OpenSSL could not sign the installer release.' }
        $signature = [Convert]::ToBase64String([IO.File]::ReadAllBytes($signatureFile))
        $release = [ordered]@{
            SchemaVersion = 1
            Version = $Version
            ArtifactUrl = $ArtifactUrl
            Sha256 = $hash
            SizeBytes = $size
            SignatureKeyId = $KeyId
            SignatureValue = $signature
        }
        [IO.File]::WriteAllText($signedManifest, ($release | ConvertTo-Json -Compress), [Text.UTF8Encoding]::new($false))
        & (Join-Path $stage 'ncc-core.exe') --state-dir $verification verify-installer --source $setup --version $Version --sha256 $hash --size $size --url $ArtifactUrl --key-id $KeyId --signature $signature
        if ($LASTEXITCODE -ne 0) { throw 'NCC Core rejected the signed installer release.' }
    } finally {
        Remove-Item -LiteralPath $statement, $signatureFile -Force -ErrorAction SilentlyContinue
    }
}
[pscustomobject]@{
    Result = if ($signedManifest) { 'Signed NCC Agent setup built and verified' } else { 'NCC Agent setup built; signed initial payload verified' }
    Setup = $setup
    Version = $Version
    InitialPayloadVersion = $artifact.payload_version
    Sha256 = $hash
    SignedReleaseManifest = $signedManifest
} | ConvertTo-Json -Compress
