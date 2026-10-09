[CmdletBinding()]
param(
    [ValidatePattern('^[A-Za-z0-9._-]{1,64}$')]
    [string]$KeyId = 'ncc-release-2026',
    [string]$SignerRoot = (Join-Path $env:ProgramData 'no0bz\NCC\release-signer')
)

# Safe diagnostic: reports identity, ACL, and an empty file-open check only.
# It never reads, prints, copies, or changes private-key bytes.
$ErrorActionPreference = 'Continue'
$key = Join-Path $SignerRoot "$KeyId-private.pem"

[pscustomobject]@{
    CurrentUser = [Security.Principal.WindowsIdentity]::GetCurrent().Name
    Elevated = ([Security.Principal.WindowsPrincipal]::new([Security.Principal.WindowsIdentity]::GetCurrent())).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
    KeyPath = $key
    KeyExists = Test-Path -LiteralPath $key
} | ConvertTo-Json

Write-Host '--- ACL ---'
& icacls.exe $key

Write-Host '--- READ TEST ---'
try {
    $handle = [IO.File]::Open($key, [IO.FileMode]::Open, [IO.FileAccess]::Read, [IO.FileShare]::Read)
    $handle.Dispose()
    'READ_TEST=OK'
} catch {
    "READ_TEST_TYPE=$($_.Exception.GetType().FullName)"
    "READ_TEST_MESSAGE=$($_.Exception.Message)"
}
