[CmdletBinding()]
param()

# This opt-in migration test is intentionally isolated from NccAgent.  It only
# installs NccCore plus a local executable that writes a health record.
$ErrorActionPreference = 'Stop'
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = [Security.Principal.WindowsPrincipal]::new($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'Dieses Skript bitte in einer als Administrator gestarteten PowerShell ausführen.'
}
$project = Split-Path -Parent $PSScriptRoot
$core = Join-Path $project 'core\ncc-core\target\release\ncc-core.exe'
$payload = Join-Path $project 'core\ncc-core\target\release\examples\test-payload.exe'
if (!(Test-Path $core) -or !(Test-Path $payload)) { throw 'Core/Test-Payload fehlen. Zuerst: cargo build --release --examples --manifest-path core\ncc-core\Cargo.toml' }

& (Join-Path $PSScriptRoot 'install_ncc_core_service.ps1') -CoreExecutable $core
$root = Join-Path $env:ProgramData 'no0bz\NCC\core-state'
$coreInstalled = Join-Path $env:ProgramData 'no0bz\NCC\core\ncc-core.exe'
$work = Join-Path $env:TEMP ('ncc-core-test-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Force -Path $work | Out-Null
try {
    $version = '0.6.0-beta.test'
    $archive = Join-Path $work 'payload.zip'
    $content = Join-Path $work 'content'
    New-Item -ItemType Directory -Force -Path $content | Out-Null
    Copy-Item $payload (Join-Path $content 'test-payload.exe')
    @{ executable = 'test-payload.exe'; arguments = @() } | ConvertTo-Json -Compress | Set-Content (Join-Path $content 'payload.json') -NoNewline -Encoding utf8
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    [IO.Compression.ZipFile]::CreateFromDirectory($content, $archive)
    $hash = (Get-FileHash $archive -Algorithm SHA256).Hash.ToLowerInvariant()
    $size = (Get-Item $archive).Length
    $message = "NCC-AGENT-RELEASE-V1`n$version`n$hash`n$size`n"
    $messageFile = Join-Path $work 'statement.txt'; [IO.File]::WriteAllText($messageFile, $message, [Text.UTF8Encoding]::new($false))
    $private = Join-Path $work 'test-private.pem'; $publicDer = Join-Path $work 'test-public.der'; $signatureFile = Join-Path $work 'signature.bin'
    & openssl genpkey -algorithm ED25519 -out $private | Out-Null
    & openssl pkey -in $private -pubout -outform DER -out $publicDer | Out-Null
    & openssl pkeyutl -sign -rawin -inkey $private -in $messageFile -out $signatureFile | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'OpenSSL konnte das Testartefakt nicht signieren.' }
    $public = [Convert]::ToBase64String([IO.File]::ReadAllBytes($publicDer)[12..43])
    $signature = [Convert]::ToBase64String([IO.File]::ReadAllBytes($signatureFile))
    New-Item -ItemType Directory -Force -Path (Join-Path $root 'config') | Out-Null
    @{ keys = @{ 'temporary-migration-test' = $public } } | ConvertTo-Json -Compress | Set-Content (Join-Path $root 'config\trusted-keys.json') -NoNewline -Encoding utf8
    & $coreInstalled --state-dir $root stage --source $archive --version $version --sha256 $hash --size $size --key-id temporary-migration-test --signature $signature
    if ($LASTEXITCODE -ne 0) { throw 'Core hat den signierten Test-Payload abgewiesen.' }
    & $coreInstalled --state-dir $root activate --version $version
    if ($LASTEXITCODE -ne 0) { throw 'Core konnte den Test-Payload nicht aktivieren.' }
    Start-Service NccCore
    Start-Sleep -Seconds 3
    $state = & $coreInstalled --state-dir $root status
    $service = Get-Service NccCore
    if ($service.Status -ne 'Running' -or $state -notmatch '"healthy"') { throw "Testmigration nicht gesund. Dienst: $($service.Status); Zustand: $state" }
    Write-Host '[NCC] Testmigration erfolgreich: NccCore läuft mit einem rein lokalen Test-Payload. NccAgent blieb unverändert aktiv.'
    Write-Host '[NCC] Nächster kontrollierter Schritt: Test-Payload beenden/entfernen oder echten 0.6-Payload separat bereitstellen.'
} finally {
    Remove-Item -LiteralPath $work -Recurse -Force -ErrorAction SilentlyContinue
}
