[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$project = Split-Path -Parent $PSScriptRoot
$temporary = Join-Path $env:TEMP ('ncc-setup-ci-' + [Guid]::NewGuid().ToString('N'))
$output = Join-Path $project 'dist\installer-ci'
$version = '0.6.0-beta.8-ci.1'
$keyId = 'ncc-ci-ephemeral'
$openssl = @('C:\Program Files\Git\usr\bin\openssl.exe', 'C:\Program Files\Git\mingw64\bin\openssl.exe') |
    Where-Object { Test-Path -LiteralPath $_ -PathType Leaf } | Select-Object -First 1
if (-not $openssl) { throw 'Git for Windows OpenSSL is required for the CI installer test.' }
New-Item -ItemType Directory -Force -Path $temporary | Out-Null
try {
    $privateKey = Join-Path $temporary 'test-private.pem'
    $publicDer = Join-Path $temporary 'test-public.der'
    & $openssl genpkey -algorithm ED25519 -out $privateKey
    if ($LASTEXITCODE -ne 0) { throw 'Could not generate test signer.' }
    & $openssl pkey -in $privateKey -pubout -outform DER -out $publicDer
    if ($LASTEXITCODE -ne 0) { throw 'Could not export test public key.' }
    $public = [Convert]::ToBase64String([IO.File]::ReadAllBytes($publicDer)[-32..-1])
    $keysFile = Join-Path $temporary 'trusted-keys.json'
    [IO.File]::WriteAllText($keysFile, (@{ keys = @{ $keyId = $public } } | ConvertTo-Json -Depth 4), [Text.UTF8Encoding]::new($false))

    $source = Join-Path $temporary 'test-payload.rs'
    $rust = @'
use std::{env, fs, path::Path, thread, time::Duration};
fn main() {
    let root = env::var("NCC_CORE_STATE_DIR").unwrap();
    let version = env::var("NCC_PAYLOAD_VERSION").unwrap();
    fs::write(Path::new(&root).join("payload-health.json"),
        format!(r#"{{"payload_version":"{}","status":"ready"}}"#, version)).unwrap();
    loop { thread::sleep(Duration::from_secs(1)); }
}
'@
    [IO.File]::WriteAllText($source, $rust, [Text.UTF8Encoding]::new($false))
    $contents = Join-Path $temporary 'contents'
    New-Item -ItemType Directory -Path $contents | Out-Null
    & rustc --edition 2021 -o (Join-Path $contents 'test-payload.exe') $source
    if ($LASTEXITCODE -ne 0) { throw 'Could not compile test payload.' }
    [IO.File]::WriteAllText((Join-Path $contents 'payload.json'), '{"executable":"test-payload.exe","arguments":[]}', [Text.UTF8Encoding]::new($false))
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $archive = Join-Path $temporary 'initial-payload.zip'
    [IO.Compression.ZipFile]::CreateFromDirectory($contents, $archive)
    $hash = (Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash.ToLowerInvariant()
    $size = (Get-Item -LiteralPath $archive).Length
    $statement = Join-Path $temporary 'statement.txt'
    $signatureFile = Join-Path $temporary 'signature.bin'
    [IO.File]::WriteAllText($statement, "NCC-AGENT-RELEASE-V1`n$version`n$hash`n$size`n", [Text.UTF8Encoding]::new($false))
    & $openssl pkeyutl -sign -rawin -inkey $privateKey -in $statement -out $signatureFile
    if ($LASTEXITCODE -ne 0) { throw 'Could not sign test payload.' }
    $signature = [Convert]::ToBase64String([IO.File]::ReadAllBytes($signatureFile))
    $manifest = @{
        schema_version = 1
        channel = 'beta'
        minimum_core_version = '0.6.0-beta.1'
        released_at = [DateTime]::UtcNow.ToString('o')
        signature = @{ algorithm = 'ed25519'; key_id = $keyId; value = $signature }
        artifacts = @(@{ platform = 'windows'; architecture = 'x86_64'; payload_version = $version;
            url = 'https://example.invalid/ncc-ci-payload.zip'; sha256 = $hash; size_bytes = $size })
    }
    $manifestFile = Join-Path $temporary 'initial-release.manifest.json'
    [IO.File]::WriteAllText($manifestFile, ($manifest | ConvertTo-Json -Depth 8), [Text.UTF8Encoding]::new($false))
    & (Join-Path $project 'scripts\build_ncc_agent_setup.ps1') -InitialManifest $manifestFile -InitialPayload $archive -TrustedKeys $keysFile -OutputDirectory $output
    if ($LASTEXITCODE -ne 0) { throw 'CI setup build failed.' }
} finally {
    Remove-Item -LiteralPath $temporary -Recurse -Force -ErrorAction SilentlyContinue
}
