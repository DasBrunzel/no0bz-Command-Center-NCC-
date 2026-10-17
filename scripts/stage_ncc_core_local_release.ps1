[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)] [string]$ArtifactPath,
    [Parameter(Mandatory = $true)] [string]$ManifestPath,
    [ValidateRange(10, 120)] [int]$TimeoutSeconds = 60
)

# Controlled emergency/local rollout path. The artifact is never trusted merely
# because it is local: NccCore validates its SHA-256 and Ed25519 signature against
# the already installed public key before it is staged.
$ErrorActionPreference = 'Stop'
$principal = [Security.Principal.WindowsPrincipal]::new([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'Dieses Skript bitte in einer als Administrator gestarteten PowerShell ausfuehren.'
}
if (!(Test-Path -LiteralPath $ArtifactPath -PathType Leaf)) { throw "Payload fehlt: $ArtifactPath" }
if (!(Test-Path -LiteralPath $ManifestPath -PathType Leaf)) { throw "Manifest fehlt: $ManifestPath" }

$manifest = Get-Content -LiteralPath $ManifestPath -Raw | ConvertFrom-Json
$artifact = @($manifest.artifacts)[0]
if (-not $artifact -or $manifest.schema_version -ne 1) { throw 'Ungültiges Release-Manifest.' }
$version = [string]$artifact.payload_version
$hash = [string]$artifact.sha256
$size = [string]$artifact.size_bytes
$keyId = [string]$manifest.signature.key_id
$signature = [string]$manifest.signature.value
if (!$version -or !$hash -or !$size -or !$keyId -or !$signature) { throw 'Manifest enthält keine vollständigen Signaturdaten.' }

$root = Join-Path $env:ProgramData 'no0bz\NCC'
$core = Join-Path $root 'core\ncc-core.exe'
$stateDir = Join-Path $root 'core-state'
if (!(Test-Path -LiteralPath $core)) { throw "NccCore fehlt: $core" }
$service = Get-Service -Name NccCore -ErrorAction Stop
$wasRunning = $service.Status -eq 'Running'
if ($wasRunning) {
    Stop-Service -Name NccCore -Force
    (Get-Service -Name NccCore).WaitForStatus('Stopped', [TimeSpan]::FromSeconds(20))
}

try {
    $stageOutput = & $core --state-dir $stateDir stage --source $ArtifactPath --version $version --sha256 $hash --size $size --key-id $keyId --signature $signature 2>&1 | Out-String
    if ($LASTEXITCODE -ne 0) { throw "Signiertes Staging abgelehnt: $stageOutput" }
    $activateOutput = & $core --state-dir $stateDir activate --version $version 2>&1 | Out-String
    if ($LASTEXITCODE -ne 0) { throw "Aktivierung abgelehnt: $activateOutput" }
} finally {
    Start-Service -Name NccCore
}

$deadline = (Get-Date).AddSeconds($TimeoutSeconds)
do {
    Start-Sleep -Seconds 2
    $stateOutput = & $core --state-dir $stateDir status 2>&1 | Out-String
    try { $state = $stateOutput | ConvertFrom-Json } catch { $state = $null }
    if ($state -and $state.active_payload -eq $version -and $state.health -eq 'healthy' -and (Get-Service NccCore).Status -eq 'Running') {
        [pscustomobject]@{
            Result = 'Local signed NCC release staged and healthy'
            ActivePayload = $state.active_payload
            PreviousPayload = $state.previous_payload
            Health = $state.health
        } | ConvertTo-Json
        exit 0
    }
} while ((Get-Date) -lt $deadline)

throw "NccCore wurde wieder gestartet, aber $version wurde nicht rechtzeitig gesund. Letzter Zustand: $stateOutput"
