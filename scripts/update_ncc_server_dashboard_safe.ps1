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

$stashMessage = $null
if ($modifiedPaths.Count -gt 0) {
    $stashMessage = 'NCC dashboard assets before update ' + (Get-Date -Format 'yyyyMMdd-HHmmss')
    & git -C $ProjectRoot stash push -m $stashMessage -- backend/ncc_server/static
    if ($LASTEXITCODE -ne 0) { throw 'Could not preserve local dashboard assets in Git stash.' }
    $remaining = @(& git -C $ProjectRoot status --porcelain --untracked-files=no)
    if ($LASTEXITCODE -ne 0 -or $remaining.Count -gt 0) { throw 'Repository still has tracked changes after preserving dashboard assets.' }
}

& git -C $ProjectRoot pull --ff-only origin $Branch
if ($LASTEXITCODE -ne 0) { throw 'Could not fast-forward NCC repository; saved dashboard assets remain in Git stash.' }

$updater = Join-Path $ProjectRoot 'scripts\update_ncc_server_release_distribution.ps1'
if (-not (Test-Path -LiteralPath $updater)) { throw "Updated server installer is missing: $updater" }
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File $updater -Branch $Branch
if ($LASTEXITCODE -ne 0) { throw 'NCC server update failed. Inspect the preceding error; saved dashboard assets remain in Git stash.' }

if ($stashMessage) { Write-Output "Preserved former dashboard assets in Git stash: $stashMessage" }
