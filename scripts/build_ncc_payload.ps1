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
$hardwareProject = Join-Path $project 'hardware\ncc-hardware-provider\NccHardwareProvider.csproj'
$openssl = (Get-Command openssl -ErrorAction SilentlyContinue).Source
if (-not $openssl) {
    $opensslCandidates = @(
        'C:\Program Files\Git\usr\bin\openssl.exe',
        'C:\Program Files\Git\mingw64\bin\openssl.exe',
        'C:\Program Files\OpenSSL-Win64\bin\openssl.exe'
    )
    $openssl = $opensslCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
}
if (!(Test-Path $python)) { throw "Build-Python fehlt: $python" }
if (!(Test-Path $PrivateKey)) { throw "Private signing key is missing: $PrivateKey" }
if (-not $openssl) { throw 'OpenSSL fehlt. Installiere Git for Windows oder OpenSSL, um NCC-Release-Payloads zu signieren.' }
try {
    $privateKeyHandle = [IO.File]::Open($PrivateKey, [IO.FileMode]::Open, [IO.FileAccess]::Read, [IO.FileShare]::Read)
    $privateKeyHandle.Dispose()
} catch {
    throw "Der private Release-Schluessel ist in diesem erhöhten Fenster nicht lesbar: $PrivateKey. Die Signer-Berechtigungen muessen einmal repariert werden; der Schluesselinhalt wird dabei nicht gelesen oder angezeigt."
}
if ($KeyId -notmatch '^[A-Za-z0-9._-]{1,64}$') { throw 'Invalid key ID.' }
$work = Join-Path $env:TEMP ('ncc-payload-build-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Force -Path $work, $OutputDirectory | Out-Null
try {
    $dist = Join-Path $work 'dist'; $build = Join-Path $work 'build'
    # Conda-backed virtual environments keep SQLite outside the venv.  PyInstaller
    # cannot always discover those runtime DLLs, so add them explicitly.  Without
    # them a payload exits before its ready health record is written.
    $pythonBase = (& $python -c 'import sys; print(sys.base_prefix)').Trim()
    $requiredRuntimes = @(
        (Join-Path $pythonBase 'DLLs\_sqlite3.pyd'),
        (Join-Path $pythonBase 'Library\bin\sqlite3.dll'),
        (Join-Path $pythonBase 'Library\bin\libssl-3-x64.dll'),
        (Join-Path $pythonBase 'Library\bin\libcrypto-3-x64.dll')
    )
    $missingRuntimes = @($requiredRuntimes | Where-Object { !(Test-Path $_) })
    if ($missingRuntimes.Count -gt 0) {
        throw "Die Python-Laufzeit fuer den Windows-Payload ist unvollstaendig: $($missingRuntimes -join ', ')"
    }
    $pyInstallerArguments = @(
        '--noconfirm', '--clean', '--onefile', '--name', 'ncc-payload',
        '--paths', (Join-Path $project 'backend'),
        '--collect-submodules', 'ncc',
        '--collect-submodules', 'ncc_agent',
        '--collect-submodules', 'ncc_payload'
    )
    foreach ($runtime in $requiredRuntimes) {
        $pyInstallerArguments += @('--add-binary', "$runtime;.")
    }
    $pyInstallerArguments += @(
        '--distpath', $dist,
        '--workpath', $build,
        '--specpath', $work,
        (Join-Path $project 'backend\ncc_payload\__main__.py')
    )
    & $python -m PyInstaller @pyInstallerArguments
    if ($LASTEXITCODE -ne 0) { throw 'PyInstaller konnte den NCC-Payload nicht bauen.' }
    $payloadExecutable = Join-Path $dist 'ncc-payload.exe'
    $smokeRoot = Join-Path $work 'payload-startup-smoke'
    $smokeState = Join-Path $smokeRoot 'state'
    $smokeData = Join-Path $smokeRoot 'data'
    New-Item -ItemType Directory -Force -Path $smokeState, $smokeData | Out-Null
    $processInfo = [Diagnostics.ProcessStartInfo]::new()
    $processInfo.FileName = $payloadExecutable
    $processInfo.UseShellExecute = $false
    $processInfo.RedirectStandardError = $true
    $processInfo.RedirectStandardOutput = $true
    $processInfo.Environment['NCC_CORE_STATE_DIR'] = $smokeState
    $processInfo.Environment['NCC_PAYLOAD_VERSION'] = 'build-smoke'
    $processInfo.Environment['NCC_AGENT_SERVER_URL'] = 'http://127.0.0.1:1'
    $processInfo.Environment['NCC_AGENT_ALLOW_INSECURE_HTTP'] = '1'
    $processInfo.Environment['NCC_AGENT_TOKEN'] = 'build-smoke-no-network'
    $processInfo.Environment['NCC_AGENT_DATA_DIR'] = $smokeData
    $payloadProcess = [Diagnostics.Process]::new()
    $payloadProcess.StartInfo = $processInfo
    if (!$payloadProcess.Start()) { throw 'Windows-Payload konnte fuer den Start-Selbsttest nicht ausgefuehrt werden.' }
    $ready = $false
    try {
        $deadline = (Get-Date).AddSeconds(20)
        $healthFile = Join-Path $smokeState 'payload-health.json'
        do {
            Start-Sleep -Milliseconds 250
            if (Test-Path $healthFile) {
                try {
                    $health = Get-Content -LiteralPath $healthFile -Raw | ConvertFrom-Json
                    $ready = $health.payload_version -eq 'build-smoke' -and $health.status -eq 'ready'
                } catch { $ready = $false }
            }
        } while (!$ready -and !$payloadProcess.HasExited -and (Get-Date) -lt $deadline)
        if (!$ready) {
            $stderr = $payloadProcess.StandardError.ReadToEnd().Trim()
            throw "Windows-Payload besteht den Start-Selbsttest nicht: $stderr"
        }
    } finally {
        if (!$payloadProcess.HasExited) { $payloadProcess.Kill($true); $payloadProcess.WaitForExit() }
    }
    $content = Join-Path $work 'content'; New-Item -ItemType Directory -Force -Path $content | Out-Null
    Copy-Item (Join-Path $dist 'ncc-payload.exe') (Join-Path $content 'ncc-payload.exe')
    if ($Platform -eq 'windows') {
        if (!(Test-Path $hardwareProject)) { throw "LibreHardwareMonitor helper project fehlt: $hardwareProject" }
        $hardwareOutput = Join-Path $content 'hardware'
        & dotnet publish $hardwareProject --configuration Release --runtime win-x64 --self-contained true --output $hardwareOutput --nologo
        if ($LASTEXITCODE -ne 0) { throw 'LibreHardwareMonitor helper konnte nicht gebaut werden.' }
        if (!(Test-Path (Join-Path $hardwareOutput 'ncc-hardware-provider.exe'))) { throw 'LibreHardwareMonitor helper executable fehlt nach dem Build.' }
        Copy-Item (Join-Path (Split-Path $hardwareProject -Parent) 'THIRD-PARTY-NOTICES.txt') (Join-Path $hardwareOutput 'THIRD-PARTY-NOTICES.txt') -Force
    }
    [IO.File]::WriteAllText((Join-Path $content 'payload.json'), (@{ executable = 'ncc-payload.exe'; arguments = @() } | ConvertTo-Json -Compress), [Text.UTF8Encoding]::new($false))
    $archive = Join-Path $OutputDirectory "ncc-payload-$Version-$Platform-x86_64.zip"
    if (Test-Path $archive) { Remove-Item -LiteralPath $archive -Force }
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    [IO.Compression.ZipFile]::CreateFromDirectory($content, $archive)
    $hash = (Get-FileHash $archive -Algorithm SHA256).Hash.ToLowerInvariant(); $size = (Get-Item $archive).Length
    $statement = Join-Path $work 'release-statement.txt'
    [IO.File]::WriteAllText($statement, "NCC-AGENT-RELEASE-V1`n$Version`n$hash`n$size`n", [Text.UTF8Encoding]::new($false))
    $signatureFile = Join-Path $work 'signature.bin'
    $signOutput = & $openssl pkeyutl -sign -rawin -inkey $PrivateKey -in $statement -out $signatureFile 2>&1 | Out-String
    if ($LASTEXITCODE -ne 0) {
        throw "OpenSSL konnte den Payload nicht signieren: $($signOutput.Trim())"
    }
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
