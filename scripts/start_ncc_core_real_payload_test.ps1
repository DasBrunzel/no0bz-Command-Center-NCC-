[CmdletBinding()]
param(
    [string]$DisplayName = 'HorstPC 0.6 Test'
)

# Installs only a parallel Core-managed test node. The 0.5 NccAgent and its
# config/data directory remain untouched and continue to be the fallback.
$ErrorActionPreference = 'Stop'
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = [Security.Principal.WindowsPrincipal]::new($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) { throw 'Bitte erhöht in PowerShell ausführen.' }
$project = Split-Path -Parent $PSScriptRoot
$root = Join-Path $env:ProgramData 'no0bz\NCC'
$configRoot = Join-Path $root 'config'; $agentEnv = Join-Path $configRoot 'agent.env'; $coreEnv = Join-Path $configRoot 'core.env'
$python = Join-Path $root 'venv\Scripts\python.exe'; $core = Join-Path $project 'core\ncc-core\target\release\ncc-core.exe'
if (!(Test-Path $agentEnv) -or !(Test-Path $python) -or !(Test-Path $core)) { throw 'Agent-Konfiguration, Dienst-Python oder Core-Binary fehlt.' }

# Refresh the Core service first. It may preserve/start the prior harmless test
# payload; stopping the service immediately afterwards removes that process tree.
& (Join-Path $PSScriptRoot 'install_ncc_core_service.ps1') -CoreExecutable $core
Stop-Service NccCore -Force -ErrorAction SilentlyContinue

$work = Join-Path $env:TEMP ('ncc-real-payload-test-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Force -Path $work | Out-Null
try {
    $key = Join-Path $work 'test-release-key.pem'
    & openssl genpkey -algorithm ED25519 -out $key | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'OpenSSL konnte keinen temporären Testschlüssel erstellen.' }
    $payloadOut = Join-Path $work 'payload'
    & (Join-Path $PSScriptRoot 'build_ncc_payload.ps1') -PrivateKey $key -KeyId 'temporary-real-payload-test' -Version '0.6.0-beta.1' -ArtifactUrl 'https://ncc.invalid/parallel-test' -OutputDirectory $payloadOut
    $archive = Get-ChildItem $payloadOut -Filter '*.zip' | Select-Object -First 1
    $manifest = Get-ChildItem $payloadOut -Filter '*.manifest.json' | Select-Object -First 1
    if (!$archive -or !$manifest) { throw 'Payload-Build lieferte kein Archiv oder Manifest.' }
    $release = Get-Content $manifest.FullName -Raw | ConvertFrom-Json

    # Copy only non-secret-safe formatting from agent.env, then give the Core
    # payload an isolated data root.  A rerun refreshes the test payload but
    # deliberately keeps its pairing identity so it cannot create duplicate
    # test nodes or invalidate an already approved browser pairing.
    $dataDir = Join-Path $root 'core-test-agent-data'; New-Item -ItemType Directory -Force -Path $dataDir | Out-Null
    $existingCoreValues = @{}
    if (Test-Path $coreEnv) {
        foreach ($line in Get-Content $coreEnv) {
            if ($line -match '^([A-Z0-9_]+)=(.*)$') { $existingCoreValues[$Matches[1]] = $Matches[2] }
        }
    }
    $pairingId = [string]$existingCoreValues['NCC_AGENT_PAIRING_ID']
    $pairingSecret = [string]$existingCoreValues['NCC_AGENT_PAIRING_SECRET']
    if ([string]::IsNullOrWhiteSpace($pairingId) -or [string]::IsNullOrWhiteSpace($pairingSecret)) {
        $pairingId = & $python -c "import secrets; print(secrets.token_urlsafe(18))"
        $pairingSecret = & $python -c "import secrets; print(secrets.token_urlsafe(32))"
    }
    $values = Get-Content $agentEnv | Where-Object { $_ -match '^NCC_AGENT_[A-Z0-9_]+=' -and $_ -notmatch '^NCC_AGENT_(PAIRING_ID|PAIRING_SECRET|DATA_DIR|DISPLAY_NAME)=' }
    @("NCC_CORE_STATE_DIR=$root\core-state", "NCC_AGENT_PAIRING_ID=$pairingId", "NCC_AGENT_PAIRING_SECRET=$pairingSecret", "NCC_AGENT_DATA_DIR=$dataDir", "NCC_AGENT_DISPLAY_NAME=$DisplayName") + $values | Set-Content $coreEnv -Encoding utf8
    & icacls.exe $coreEnv /inheritance:r /grant:r '*S-1-5-18:F' '*S-1-5-32-544:F' | Out-Null

    # Trust only the ephemeral public key required for this one local test.
    $publicDer = Join-Path $work 'test-public.der'; & openssl pkey -in $key -pubout -outform DER -out $publicDer | Out-Null
    $public = [Convert]::ToBase64String([IO.File]::ReadAllBytes($publicDer)[12..43])
    $stateRoot = Join-Path $root 'core-state'; New-Item -ItemType Directory -Force -Path (Join-Path $stateRoot 'config') | Out-Null
    [IO.File]::WriteAllText((Join-Path $stateRoot 'config\trusted-keys.json'), (@{ keys = @{ 'temporary-real-payload-test' = $public } } | ConvertTo-Json -Compress), [Text.UTF8Encoding]::new($false))

    $coreInstalled = Join-Path $root 'core\ncc-core.exe'
    $item = $release.artifacts[0]
    & $coreInstalled --state-dir $stateRoot stage --source $archive.FullName --version $item.payload_version --sha256 $item.sha256 --size $item.size_bytes --key-id $release.signature.key_id --signature $release.signature.value
    if ($LASTEXITCODE -ne 0) { throw 'Core hat den echten Test-Payload abgewiesen.' }
    & $coreInstalled --state-dir $stateRoot activate --version $item.payload_version
    if ($LASTEXITCODE -ne 0) { throw 'Core konnte den echten Test-Payload nicht aktivieren.' }
    Start-Service NccCore; Start-Sleep -Seconds 3
    $state = & $coreInstalled --state-dir $stateRoot status
    if ($state -notmatch '"healthy"') { throw "Core-Payload ist nicht gesund: $state" }
    $serverUrl = (($values | Where-Object { $_ -match '^NCC_AGENT_SERVER_URL=' } | Select-Object -First 1) -replace '^NCC_AGENT_SERVER_URL=', '').Trim('"')
    Write-Host "[NCC] Echter 0.6-Payload ist gesund. 0.5-NccAgent läuft unverändert weiter."
    Write-Host "[NCC] Browser-Pairing für den separaten Test-Node: $serverUrl/?pair=$pairingId"
} finally { Remove-Item -LiteralPath $work -Recurse -Force -ErrorAction SilentlyContinue }
