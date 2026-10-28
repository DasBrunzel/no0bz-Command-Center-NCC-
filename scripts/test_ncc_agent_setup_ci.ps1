[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$project = Split-Path -Parent $PSScriptRoot
$temporary = Join-Path $env:TEMP ('ncc-setup-ci-' + [Guid]::NewGuid().ToString('N'))
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

    Add-Type -AssemblyName System.IO.Compression.FileSystem
    function Build-TestVariant([string]$Label, [string]$PayloadVersion, [string]$SetupVersion, [bool]$Healthy) {
        $work = Join-Path $temporary $Label
        $contents = Join-Path $work 'contents'
        New-Item -ItemType Directory -Force -Path $contents | Out-Null
        $source = Join-Path $work 'test-payload.rs'
        $rust = if ($Healthy) { @'
use std::{env, fs, path::Path, thread, time::Duration};
fn main() {
    let root = env::var("NCC_CORE_STATE_DIR").unwrap();
    let version = env::var("NCC_PAYLOAD_VERSION").unwrap();
    fs::write(Path::new(&root).join("payload-health.json"),
        format!(r#"{{"payload_version":"{}","status":"ready"}}"#, version)).unwrap();
    loop { thread::sleep(Duration::from_secs(1)); }
}
'@
        } else { @'
use std::{thread, time::Duration};
fn main() { loop { thread::sleep(Duration::from_secs(1)); } }
'@
        }
        [IO.File]::WriteAllText($source, $rust, [Text.UTF8Encoding]::new($false))
        & rustc --edition 2021 -o (Join-Path $contents 'test-payload.exe') $source
        if ($LASTEXITCODE -ne 0) { throw 'Could not compile test payload.' }
        [IO.File]::WriteAllText((Join-Path $contents 'payload.json'), '{"executable":"test-payload.exe","arguments":[]}', [Text.UTF8Encoding]::new($false))
        $archive = Join-Path $work 'initial-payload.zip'
        [IO.Compression.ZipFile]::CreateFromDirectory($contents, $archive)
        $hash = (Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash.ToLowerInvariant()
        $size = (Get-Item -LiteralPath $archive).Length
        $statement = Join-Path $work 'statement.txt'
        $signatureFile = Join-Path $work 'signature.bin'
        [IO.File]::WriteAllText($statement, "NCC-AGENT-RELEASE-V1`n$PayloadVersion`n$hash`n$size`n", [Text.UTF8Encoding]::new($false))
        & $openssl pkeyutl -sign -rawin -inkey $privateKey -in $statement -out $signatureFile
        if ($LASTEXITCODE -ne 0) { throw 'Could not sign test payload.' }
        $signature = [Convert]::ToBase64String([IO.File]::ReadAllBytes($signatureFile))
        $manifest = @{
            schema_version = 1
            channel = 'beta'
            minimum_core_version = '0.6.0-beta.1'
            released_at = [DateTime]::UtcNow.ToString('o')
            signature = @{ algorithm = 'ed25519'; key_id = $keyId; value = $signature }
            artifacts = @(@{ platform = 'windows'; architecture = 'x86_64'; payload_version = $PayloadVersion;
                url = 'https://example.invalid/ncc-ci-payload.zip'; sha256 = $hash; size_bytes = $size })
        }
        $manifestFile = Join-Path $work 'initial-release.manifest.json'
        [IO.File]::WriteAllText($manifestFile, ($manifest | ConvertTo-Json -Depth 8), [Text.UTF8Encoding]::new($false))
        $output = Join-Path $project ('dist\installer-ci-' + $Label)
        $builder = @{
            Version = $SetupVersion
            InitialManifest = $manifestFile
            InitialPayload = $archive
            TrustedKeys = $keysFile
            OutputDirectory = $output
            UpdateFeedUrl = 'https://localhost:18443/update-feed.json'
        }
        if ($Label -eq 'next') {
            $builder.PrivateKey = $privateKey
            $builder.KeyId = $keyId
            $builder.ArtifactUrl = "https://localhost:18443/ncc-agent-setup-$SetupVersion-windows-x86_64.exe"
        }
        & (Join-Path $project 'scripts\build_ncc_agent_setup.ps1') @builder
        if ($LASTEXITCODE -ne 0) { throw "CI setup build failed: $Label" }
    }
    Build-TestVariant 'first' '0.6.0-beta.8-ci.1' '0.6.0-beta.8-dev.1' $true
    Build-TestVariant 'next' '0.6.0-beta.8-ci.2' '0.6.0-beta.8-dev.2' $true
    Build-TestVariant 'bad' '0.6.0-beta.8-ci.3' '0.6.0-beta.8-dev.3' $false
} finally {
    Remove-Item -LiteralPath $temporary -Recurse -Force -ErrorAction SilentlyContinue
}
