[CmdletBinding()]
param(
    [string]$Branch = 'codex/ncc-v0.6-agent-foundation'
)

# One-purpose production server update for the NCC 0.6 release distribution.
# It intentionally never reads or changes agent.env, agent services, pairings,
# dashboard tokens, Unraid settings, or PostgreSQL server configuration.
$ErrorActionPreference = 'Stop'
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = [Security.Principal.WindowsPrincipal]::new($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'Run this script from an elevated PowerShell window.'
}

$projectRoot = Split-Path -Parent $PSScriptRoot
$installRoot = Join-Path $env:ProgramData 'no0bz\NCC'
$configPath = Join-Path $installRoot 'config\server.env'
$venvPython = Join-Path $installRoot 'venv\Scripts\python.exe'
$migrationRoot = Join-Path $installRoot 'migrations'
$backupRoot = Join-Path $installRoot 'server-update-backups'
foreach ($path in @($configPath, $venvPython, (Join-Path $projectRoot '.git'))) {
    if (-not (Test-Path -LiteralPath $path)) { throw "Required NCC path is missing: $path" }
}

$dirty = @(& git -C $projectRoot status --porcelain --untracked-files=no)
if ($LASTEXITCODE -ne 0) { throw 'Could not read the repository status.' }
if ($dirty.Count -gt 0) {
    throw 'Repository has tracked local changes. Stop without overwriting them and resolve them first.'
}

$timestamp = Get-Date -Format 'yyyyMMdd-HHmmss'
New-Item -ItemType Directory -Force -Path $backupRoot | Out-Null
& icacls.exe $backupRoot /inheritance:r /grant:r '*S-1-5-18:(OI)(CI)F' '*S-1-5-32-544:(OI)(CI)F' | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'Could not protect the NCC server-update backup directory.' }
$configBackup = Join-Path $backupRoot "server.env.$timestamp.bak"
Copy-Item -LiteralPath $configPath -Destination $configBackup -ErrorAction Stop

# Reuse the established backup routine before migration. It obtains the database
# password locally from the protected server.env and never prints it.
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $projectRoot 'scripts\backup_ncc_postgres.ps1')
if ($LASTEXITCODE -ne 0) { throw 'PostgreSQL backup failed; server update was not started.' }

# A targeted fetch otherwise updates only FETCH_HEAD on some Git-for-Windows
# versions. Store the remote-tracking ref explicitly so a first-time branch
# switch is deterministic.
$remoteRef = "refs/heads/$Branch:refs/remotes/origin/$Branch"
& git -C $projectRoot fetch origin $remoteRef
if ($LASTEXITCODE -ne 0) { throw 'Git fetch failed.' }
& git -C $projectRoot show-ref --verify --quiet "refs/heads/$Branch"
if ($LASTEXITCODE -eq 0) {
    & git -C $projectRoot switch $Branch
} else {
    & git -C $projectRoot switch --track -c $Branch "origin/$Branch"
}
if ($LASTEXITCODE -ne 0) { throw "Could not switch to branch $Branch." }
& git -C $projectRoot pull --ff-only origin $Branch
if ($LASTEXITCODE -ne 0) { throw 'Git fast-forward update failed.' }

Push-Location (Join-Path $projectRoot 'frontend')
try {
    & npm.cmd run build
    if ($LASTEXITCODE -ne 0) { throw 'Frontend production build failed.' }
} finally { Pop-Location }

# Install only the Python package and server migration assets. Existing server
# configuration stays in place; neither -ReplaceConfig nor Agent is used.
& $venvPython -m pip install --upgrade $projectRoot
if ($LASTEXITCODE -ne 0) { throw 'NCC server package update failed.' }
if (Test-Path -LiteralPath $migrationRoot) { Remove-Item -LiteralPath $migrationRoot -Recurse -Force }
Copy-Item -LiteralPath (Join-Path $projectRoot 'migrations') -Destination $migrationRoot -Recurse
Copy-Item -LiteralPath (Join-Path $projectRoot 'alembic.ini') -Destination (Join-Path $installRoot 'alembic.ini') -Force
& $venvPython -m ncc_service.migrate --config $configPath --alembic (Join-Path $installRoot 'alembic.ini')
if ($LASTEXITCODE -ne 0) { throw 'NCC database migration failed.' }

& $venvPython -m ncc_service.windows server --startup auto update
if ($LASTEXITCODE -ne 0) { throw 'NccServer service registration update failed.' }
Restart-Service -Name NccServer -ErrorAction Stop
Start-Sleep -Seconds 4
if ((Get-Service -Name NccServer).Status -ne 'Running') { throw 'NccServer did not reach Running state.' }

$serverUrl = & $venvPython -c "from pathlib import Path; from ncc_service.environment import load_environment_file; env=load_environment_file(Path(r'$configPath')); print('http://' + env['NCC_SERVER_HOST'].strip(chr(34)) + ':' + env.get('NCC_SERVER_PORT', '8350').strip(chr(34)))"
if ($LASTEXITCODE -ne 0 -or -not $serverUrl) { throw 'Could not derive the local NCC server URL.' }
$ready = Invoke-WebRequest -Uri "$serverUrl/api/v1/status/ready" -UseBasicParsing -TimeoutSec 15
$version = Invoke-WebRequest -Uri "$serverUrl/api/v1/version" -UseBasicParsing -TimeoutSec 15
try {
    $releaseRoute = Invoke-WebRequest -Uri "$serverUrl/api/v1/releases" -UseBasicParsing -TimeoutSec 15
    $releaseStatus = [int]$releaseRoute.StatusCode
} catch {
    if (-not $_.Exception.Response) { throw }
    $releaseStatus = [int]$_.Exception.Response.StatusCode
}
if ($ready.StatusCode -ne 200 -or $version.StatusCode -ne 200 -or $releaseStatus -notin 401,403) {
    throw "Release-distribution verification failed: ready=$($ready.StatusCode), version=$($version.StatusCode), releases=$releaseStatus"
}

[pscustomobject]@{
    Result = 'NCC server release-distribution update completed'
    Branch = $Branch
    ConfigBackup = $configBackup
    NccServer = (Get-Service -Name NccServer).Status.ToString()
    ReadyStatus = [int]$ready.StatusCode
    VersionStatus = [int]$version.StatusCode
    ReleaseRouteStatus = $releaseStatus
} | ConvertTo-Json
