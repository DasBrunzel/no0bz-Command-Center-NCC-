[CmdletBinding()]
param(
    [string]$ProjectRoot = 'C:\Users\BigHorst\Desktop\ncc',
    [string]$Branch = 'codex/ncc-v0.6-agent-foundation'
)

$ErrorActionPreference = 'Stop'
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = [Security.Principal.WindowsPrincipal]::new($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'Run this script from an elevated PowerShell window.'
}
if (-not (Test-Path -LiteralPath (Join-Path $ProjectRoot '.git'))) {
    throw "NCC Git repository not found: $ProjectRoot"
}

$dirty = @(& git -C $ProjectRoot status --porcelain --untracked-files=no)
if ($LASTEXITCODE -ne 0) { throw 'Could not read NCC Git status.' }
$modifiedPaths = @($dirty | Where-Object { $_ } | ForEach-Object { $_.Substring(3).Trim('"') })
$unexpected = @($modifiedPaths | Where-Object { -not $_.StartsWith('backend/ncc_server/static/', [StringComparison]::Ordinal) })
if ($unexpected.Count -gt 0) {
    throw "Tracked changes outside generated dashboard assets need review: $($unexpected -join ', ')"
}

$backupPath = $null
if ($modifiedPaths.Count -gt 0) {
    $backupRoot = Join-Path $env:ProgramData 'no0bz\NCC\server-update-backups'
    New-Item -ItemType Directory -Path $backupRoot -Force | Out-Null
    & icacls.exe $backupRoot /inheritance:r /grant:r '*S-1-5-18:(OI)(CI)F' '*S-1-5-32-544:(OI)(CI)F' | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'Could not protect the dashboard backup directory.' }
    $backupPath = Join-Path $backupRoot ('dashboard-static.' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
    $staticRoot = Join-Path $ProjectRoot 'backend\ncc_server\static'
    Copy-Item -LiteralPath $staticRoot -Destination $backupPath -Recurse -Force -ErrorAction Stop
    if (-not (Test-Path -LiteralPath (Join-Path $backupPath 'index.html'))) {
        throw 'Dashboard asset backup could not be verified; repository was not changed.'
    }
    & git -C $ProjectRoot restore --source=HEAD --worktree -- backend/ncc_server/static
    if ($LASTEXITCODE -ne 0) { throw "Could not reset generated dashboard assets. Backup: $backupPath" }
    $remaining = @(& git -C $ProjectRoot status --porcelain --untracked-files=no)
    if ($LASTEXITCODE -ne 0 -or $remaining.Count -gt 0) { throw "Repository still has tracked changes after preserving dashboard assets. Backup: $backupPath" }
}

& git -C $ProjectRoot pull --ff-only origin $Branch
if ($LASTEXITCODE -ne 0) { throw "Could not fast-forward NCC repository. Dashboard backup: $backupPath" }

$updater = Join-Path $ProjectRoot 'scripts\update_ncc_server_release_distribution.ps1'
if (-not (Test-Path -LiteralPath $updater)) { throw "Updated server installer is missing: $updater" }
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File $updater -Branch $Branch
if ($LASTEXITCODE -ne 0) { throw "NCC server update failed. Inspect the preceding error. Dashboard backup: $backupPath" }

if ($backupPath) { Write-Output "Preserved former dashboard assets at: $backupPath" }
