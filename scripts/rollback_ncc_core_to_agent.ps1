[CmdletBinding()]
param()

# Immediate local fallback for switch_ncc_core_to_primary.ps1. It does not
# delete Core payloads, data, pairings, or the original agent configuration.
$ErrorActionPreference = 'Stop'
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = [Security.Principal.WindowsPrincipal]::new($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'Dieses Skript bitte in einer als Administrator gestarteten PowerShell ausfuehren.'
}

Stop-Service -Name NccCore -Force -ErrorAction SilentlyContinue
Set-Service -Name NccAgent -StartupType Automatic
Start-Service -Name NccAgent
$service = Get-Service -Name NccAgent
if ($service.Status -ne 'Running') { throw 'NccAgent konnte beim Rollback nicht gestartet werden.' }
[pscustomobject]@{
    Result = 'Legacy NccAgent restored; NccCore stopped'
    NccAgent = $service.Status.ToString()
} | ConvertTo-Json
