[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$AppDir,
    [string]$ServerUrl = '',
    [string]$ServerUrlFile = '',
    [ValidateRange(20, 180)][int]$HealthTimeoutSeconds = 90
)

$ErrorActionPreference = 'Stop'
if ($ServerUrlFile) { $ServerUrl = (Get-Content -LiteralPath $ServerUrlFile -Raw -Encoding UTF8).Trim() }
$admin = [Security.Principal.WindowsPrincipal]::new([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $admin.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'NCC Agent Setup requires administrator rights.'
}
$AppDir = [IO.Path]::GetFullPath($AppDir)
$root = Join-Path $env:ProgramData 'no0bz\NCC Agent'
$legacyRoot = Join-Path $env:ProgramData 'no0bz\NCC'
$configDir = Join-Path $root 'config'
$stateDir = Join-Path $root 'core-state'
$dataDir = Join-Path $root 'data'
$core = Join-Path $AppDir 'ncc-core.exe'
$serviceExe = Join-Path $AppDir 'NccServiceHost.exe'
$bundle = Join-Path $AppDir 'initial-payload.zip'
$manifestFile = Join-Path $AppDir 'initial-payload.manifest.json'
$trustedFile = Join-Path $AppDir 'trusted-keys.json'
$handoffFile = Join-Path $env:ProgramData 'no0bz\NCC Agent Setup\handoff.json'
$migrationCommitted = $false
trap {
    $cause = $_
    if ($migrationCommitted) { throw $cause }
    Stop-Service -Name NccAgentCore -Force -ErrorAction SilentlyContinue
    if (Test-Path -LiteralPath $handoffFile) {
        try {
            $handoff = Get-Content -LiteralPath $handoffFile -Raw | ConvertFrom-Json
            $backupApp = Join-Path $handoff.backup 'app'
            $backupData = Join-Path $handoff.backup 'agent-data'
            if (Test-Path -LiteralPath $backupApp -PathType Container) {
                Get-ChildItem -LiteralPath $backupApp -Force | ForEach-Object {
                    Copy-Item -LiteralPath $_.FullName -Destination $AppDir -Recurse -Force
                }
            }
            if (Test-Path -LiteralPath $backupData -PathType Container) {
                Get-ChildItem -LiteralPath $backupData -Force | ForEach-Object {
                    Copy-Item -LiteralPath $_.FullName -Destination $root -Recurse -Force
                }
            }
            foreach ($oldName in @($handoff.running_services)) {
                Start-Service -Name $oldName -ErrorAction SilentlyContinue
            }
            if ($handoff.legacy_task_running) {
                Start-ScheduledTask -TaskName NccAgent -ErrorAction SilentlyContinue
            }
        } catch { }
    }
    throw $cause
}
foreach ($path in @($core, $serviceExe, $bundle, $manifestFile, $trustedFile)) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw "Installer component missing: $path" }
}

function Read-EnvFile([string]$Path) {
    $values = @{}
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { return $values }
    foreach ($line in Get-Content -LiteralPath $Path -Encoding UTF8) {
        if ($line -match '^([A-Z][A-Z0-9_]*)=(.*)$') {
            $value = $Matches[2].Trim()
            if ($value.Length -ge 2 -and $value[0] -eq '"' -and $value[-1] -eq '"') {
                $value = $value.Substring(1, $value.Length - 2).Replace('\"', '"').Replace('\\', '\')
            }
            $values[$Matches[1]] = $value
        }
    }
    return $values
}

function New-Token([int]$Bytes) {
    $buffer = New-Object byte[] $Bytes
    $rng = [Security.Cryptography.RandomNumberGenerator]::Create()
    try { $rng.GetBytes($buffer) } finally { $rng.Dispose() }
    return [Convert]::ToBase64String($buffer).TrimEnd('=').Replace('+', '-').Replace('/', '_')
}

function Set-PrivateAcl([string]$Path) {
    $systemRight = if (Test-Path -LiteralPath $Path -PathType Container) { '*S-1-5-18:(OI)(CI)F' } else { '*S-1-5-18:F' }
    $adminRight = if (Test-Path -LiteralPath $Path -PathType Container) { '*S-1-5-32-544:(OI)(CI)F' } else { '*S-1-5-32-544:F' }
    & icacls.exe $Path /inheritance:r /grant:r $systemRight $adminRight | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "Could not protect NCC Agent data: $Path" }
}

function Assert-ServerUrl([string]$Value) {
    $uri = $null
    if (-not [Uri]::TryCreate($Value, [UriKind]::Absolute, [ref]$uri)) { throw 'Invalid NCC server URL.' }
    if ($uri.UserInfo -or $uri.Query -or $uri.Fragment -or $uri.AbsolutePath -ne '/') { throw 'NCC server URL must be a base URL without credentials or path.' }
    if ($uri.Scheme -eq 'https') { return }
    if ($uri.Scheme -ne 'http') { throw 'NCC server URL must use HTTPS or trusted Tailscale HTTP.' }
    if ($uri.Host -in @('localhost', '127.0.0.1', '::1')) { return }
    $ip = $null
    if (-not [Net.IPAddress]::TryParse($uri.Host, [ref]$ip)) { throw 'HTTP is only allowed for loopback or a Tailscale IP.' }
    $bytes = $ip.GetAddressBytes()
    if ($bytes.Length -ne 4 -or $bytes[0] -ne 100 -or $bytes[1] -lt 64 -or $bytes[1] -gt 127) {
        throw 'HTTP is only allowed for loopback or a Tailscale IP.'
    }
}

$newConfigFile = Join-Path $configDir 'core.env'
$existing = Read-EnvFile $newConfigFile
$migrating = $existing.Count -eq 0
if ($migrating) {
    $existing = Read-EnvFile (Join-Path $legacyRoot 'config\core.env')
    if ($existing.Count -eq 0) { $existing = Read-EnvFile (Join-Path $legacyRoot 'config\agent.env') }
}
if (-not $ServerUrl) { $ServerUrl = [string]$existing['NCC_AGENT_SERVER_URL'] }
if (-not $ServerUrl) { throw 'NCC server URL is required for a new installation.' }
Assert-ServerUrl $ServerUrl
$ServerUrl = $ServerUrl.TrimEnd('/')

New-Item -ItemType Directory -Force -Path $root, $configDir, $stateDir, $dataDir, (Join-Path $root 'logs') | Out-Null
foreach ($privateDir in @($root, $configDir, $stateDir, $dataDir, (Join-Path $root 'logs'))) {
    Set-PrivateAcl $privateDir
}
if ($migrating) {
    $oldData = [string]$existing['NCC_AGENT_DATA_DIR']
    if (-not $oldData) { $oldData = Join-Path $legacyRoot 'agent-data' }
    if ((Test-Path -LiteralPath $oldData -PathType Container) -and -not (Get-ChildItem -LiteralPath $dataDir -Force | Select-Object -First 1)) {
        Get-ChildItem -LiteralPath $oldData -Force | ForEach-Object {
            Copy-Item -LiteralPath $_.FullName -Destination $dataDir -Recurse -Force -ErrorAction Stop
        }
    }
    $oldState = Join-Path $legacyRoot 'core-state'
    if ((Test-Path -LiteralPath $oldState -PathType Container) -and -not (Test-Path -LiteralPath (Join-Path $stateDir 'state\core-state.json'))) {
        Get-ChildItem -LiteralPath $oldState -Force | ForEach-Object {
            Copy-Item -LiteralPath $_.FullName -Destination $stateDir -Recurse -Force -ErrorAction Stop
        }
    }
}
$existing['NCC_AGENT_SERVER_URL'] = $ServerUrl
$existing['NCC_AGENT_DATA_DIR'] = $dataDir
$existing['NCC_AGENT_ALLOW_INSECURE_HTTP'] = if ($ServerUrl.StartsWith('http://', [StringComparison]::OrdinalIgnoreCase)) { '1' } else { '0' }
$existing['NCC_CORE_STATE_DIR'] = $stateDir
$feedFile = Join-Path $AppDir 'installer-feed-url.txt'
if (-not $existing['NCC_AGENT_INSTALLER_FEED_URL'] -and (Test-Path -LiteralPath $feedFile)) {
    $existing['NCC_AGENT_INSTALLER_FEED_URL'] = (Get-Content -LiteralPath $feedFile -Raw -Encoding UTF8).Trim()
}
if (-not $existing['NCC_AGENT_PAIRING_ID']) { $existing['NCC_AGENT_PAIRING_ID'] = New-Token 18 }
if (-not $existing['NCC_AGENT_PAIRING_SECRET']) { $existing['NCC_AGENT_PAIRING_SECRET'] = New-Token 32 }
$lines = @($existing.Keys | Sort-Object | Where-Object { $_ -match '^NCC_(CORE|AGENT)_[A-Z0-9_]+$' } | ForEach-Object {
    $value = [string]$existing[$_]
    if ($value.Contains("`r") -or $value.Contains("`n")) { throw 'NCC configuration contains a newline.' }
    "$_=$value"
})
[IO.File]::WriteAllLines($newConfigFile, $lines, [Text.UTF8Encoding]::new($false))
Set-PrivateAcl $newConfigFile

$keyTarget = Join-Path $stateDir 'config\trusted-keys.json'
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $keyTarget) | Out-Null
if (-not (Test-Path -LiteralPath $keyTarget)) { Copy-Item -LiteralPath $trustedFile -Destination $keyTarget }
Set-PrivateAcl $stateDir

$manifest = Get-Content -LiteralPath $manifestFile -Raw | ConvertFrom-Json
$artifact = @($manifest.artifacts | Where-Object { $_.platform -eq 'windows' -and $_.architecture -eq 'x86_64' }) | Select-Object -First 1
if (-not $artifact -or $manifest.signature.algorithm -ne 'ed25519') { throw 'Initial payload manifest is invalid.' }
if ((Get-Item -LiteralPath $bundle).Length -ne [long]$artifact.size_bytes) { throw 'Initial payload size mismatch.' }
if ((Get-FileHash -LiteralPath $bundle -Algorithm SHA256).Hash.ToLowerInvariant() -ne $artifact.sha256.ToLowerInvariant()) { throw 'Initial payload checksum mismatch.' }

$stateFile = Join-Path $stateDir 'state\core-state.json'
$hasActive = $false
if (Test-Path -LiteralPath $stateFile) {
    try { $hasActive = !!((Get-Content -LiteralPath $stateFile -Raw | ConvertFrom-Json).active_payload) } catch { $hasActive = $false }
}
if (-not $hasActive) {
    & $core --state-dir $stateDir stage --source $bundle --version $artifact.payload_version --sha256 $artifact.sha256 --size $artifact.size_bytes --key-id $manifest.signature.key_id --signature $manifest.signature.value
    if ($LASTEXITCODE -ne 0) { throw 'Signed initial NCC payload was rejected.' }
    & $core --state-dir $stateDir activate --version $artifact.payload_version
    if ($LASTEXITCODE -ne 0) { throw 'Initial NCC payload could not be activated.' }
}

$settings = @{ serverUrl = $ServerUrl; version = (Get-Item -LiteralPath $AppDir).Name }
$settings.version = (Get-Content -LiteralPath (Join-Path $AppDir 'installer-version.txt') -Raw).Trim()
[IO.File]::WriteAllText((Join-Path $AppDir 'tray-settings.json'), ($settings | ConvertTo-Json -Compress), [Text.UTF8Encoding]::new($false))
$pairingUrl = "$ServerUrl/?pair=$($existing['NCC_AGENT_PAIRING_ID'])"
[IO.File]::WriteAllText((Join-Path $AppDir 'pairing-url.txt'), $pairingUrl, [Text.UTF8Encoding]::new($false))

foreach ($oldName in @('NccCore', 'NccAgent')) {
    $old = Get-Service -Name $oldName -ErrorAction SilentlyContinue
    if ($old -and $old.Status -ne 'Stopped') {
        Stop-Service -Name $oldName -Force -ErrorAction Stop
        $old.WaitForStatus('Stopped', [TimeSpan]::FromSeconds(30))
    }
}
$name = 'NccAgentCore'
$registered = Get-Service -Name $name -ErrorAction SilentlyContinue
if (-not $registered) {
    New-Service -Name $name -BinaryPathName ('"' + $serviceExe + '"') -DisplayName 'no0bz Command Center Agent' -Description 'Runs signed NCC Core telemetry payloads.' -StartupType Automatic | Out-Null
} else {
    & sc.exe config $name "binPath= `"$serviceExe`"" 'start= auto' | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'Could not update NCC Agent service path.' }
}
& sc.exe config $name 'start= delayed-auto' | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'Could not enable automatic NCC Agent startup.' }
& sc.exe failure $name 'reset= 86400' 'actions= restart/5000/restart/15000/restart/60000' | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'Could not configure NCC Agent crash recovery.' }

# The BUILTIN Users SID receives exactly query status, start and stop. It
# cannot change the service binary, configuration, ACL, or delete the service.
$descriptor = @(& sc.exe sdshow $name | Where-Object { $_ -match '^(?:O:|D:)' }) | Select-Object -First 1
if (-not $descriptor) { throw 'Could not read NCC Agent service security.' }
$descriptor = $descriptor.Trim()
if ($descriptor -notmatch '\(A;;LCRPWP;;;BU\)') {
    $ace = '(A;;LCRPWP;;;BU)'
    $sacl = $descriptor.IndexOf('S:', [StringComparison]::Ordinal)
    if ($sacl -ge 0) { $descriptor = $descriptor.Insert($sacl, $ace) } else { $descriptor += $ace }
    & sc.exe sdset $name $descriptor | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'Could not grant start/stop rights for the NCC tray.' }
}

$serviceStartedAt = (Get-Date).ToUniversalTime()
Start-Service -Name $name
$deadline = (Get-Date).AddSeconds($HealthTimeoutSeconds)
$health = $null
$freshReady = $false
do {
    Start-Sleep -Seconds 2
    try { $health = & $core --state-dir $stateDir status | ConvertFrom-Json } catch { $health = $null }
    $running = (Get-Service -Name $name).Status -eq 'Running'
    $record = Join-Path $stateDir 'state\payload-health.json'
    if ($running -and $health -and $health.health -eq 'healthy' -and (Test-Path -LiteralPath $record)) {
        try {
            $ready = Get-Content -LiteralPath $record -Raw | ConvertFrom-Json
            $freshReady = $ready.status -eq 'ready' -and
                $ready.payload_version -eq $health.active_payload -and
                (Get-Item -LiteralPath $record).LastWriteTimeUtc -ge $serviceStartedAt.AddSeconds(-1)
        } catch { $freshReady = $false }
        if ($freshReady) { Start-Sleep -Seconds 5; $running = (Get-Service -Name $name).Status -eq 'Running'; if ($running) { break } }
    }
} while ((Get-Date) -lt $deadline)
if (-not $running -or -not $health -or $health.health -ne 'healthy' -or -not $freshReady) {
    Stop-Service -Name $name -Force -ErrorAction SilentlyContinue
    foreach ($oldName in @('NccCore', 'NccAgent')) {
        $old = Get-Service -Name $oldName -ErrorAction SilentlyContinue
        if ($old) { Start-Service -Name $oldName -ErrorAction SilentlyContinue }
    }
    throw 'NCC Agent did not become healthy; previous agent services were restarted.'
}
$migrationCommitted = $true

foreach ($oldName in @('NccCore', 'NccAgent')) {
    if (Get-Service -Name $oldName -ErrorAction SilentlyContinue) {
        & sc.exe delete $oldName | Out-Null
        if ($LASTEXITCODE -ne 0) { throw "Old NCC agent service could not be removed: $oldName" }
    }
    $oldTask = Get-ScheduledTask -TaskName $oldName -ErrorAction SilentlyContinue
    if ($oldTask) { Unregister-ScheduledTask -TaskName $oldName -Confirm:$false }
}

# Remove only agent-owned legacy paths. NccServer may share this ProgramData
# tree and its Python runtime, database configuration, and logs must survive.
foreach ($relative in @('config\agent.env', 'config\core.env', 'agent-data', 'core-state', 'core\ncc-core.exe', 'logs\agent.log', 'logs\core.log')) {
    $oldPath = Join-Path $legacyRoot $relative
    if (Test-Path -LiteralPath $oldPath) {
        Remove-Item -LiteralPath $oldPath -Recurse -Force -ErrorAction Stop
    }
}
if (-not (Get-Service -Name NccServer -ErrorAction SilentlyContinue)) {
    $oldVenv = Join-Path $legacyRoot 'venv'
    if (Test-Path -LiteralPath $oldVenv -PathType Container) {
        Remove-Item -LiteralPath $oldVenv -Recurse -Force -ErrorAction Stop
    }
}
foreach ($nameToRemove in @('NccAgent', 'NccCore')) {
    Remove-ItemProperty -Path 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Run' -Name $nameToRemove -ErrorAction SilentlyContinue
    Get-NetFirewallRule -DisplayName $nameToRemove -ErrorAction SilentlyContinue | Remove-NetFirewallRule -ErrorAction SilentlyContinue
}

[pscustomobject]@{ Result = 'NCC Agent installed'; Service = $name; Health = $health.health; Payload = $health.active_payload; PairingUrl = $pairingUrl } | ConvertTo-Json -Compress
