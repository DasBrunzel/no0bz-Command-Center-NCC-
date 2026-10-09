[CmdletBinding()]
param()

# Read-only companion for the dashboard's duplicate-telemetry warning.  It
# intentionally exposes neither the pairing secret nor the agent token.
$ErrorActionPreference = 'Stop'
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = [Security.Principal.WindowsPrincipal]::new($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'Dieses Diagnose-Skript bitte in einer als Administrator gestarteten PowerShell ausfuehren.'
}

$serviceNames = @('NccAgent', 'NccCore')
$services = foreach ($name in $serviceNames) {
    $service = Get-Service -Name $name -ErrorAction SilentlyContinue
    if ($null -eq $service) {
        [pscustomobject]@{ Name = $name; Exists = $false; Status = 'NotInstalled'; StartType = $null }
        continue
    }
    $startMode = (Get-CimInstance Win32_Service -Filter "Name='$name'").StartMode
    [pscustomobject]@{ Name = $name; Exists = $true; Status = $service.Status.ToString(); StartType = $startMode }
}

$nccProcesses = Get-CimInstance Win32_Process |
    Where-Object {
        $_.CommandLine -and $_.CommandLine -match '(?i)(ncc_payload|ncc_agent|ncccore|ncc-core|no0bz\\NCC)'
    } |
    Select-Object ProcessId, ParentProcessId, Name, CommandLine, CreationDate

$legacyTasks = Get-ScheduledTask -ErrorAction SilentlyContinue |
    Where-Object { $_.TaskName -match '(?i)ncc' } |
    ForEach-Object {
        [pscustomobject]@{
            TaskName = $_.TaskName
            TaskPath = $_.TaskPath
            State = $_.State.ToString()
        }
    }

[pscustomobject]@{
    CheckedAt = (Get-Date).ToString('o')
    Services = @($services)
    NccProcesses = @($nccProcesses)
    NccScheduledTasks = @($legacyTasks)
    Interpretation = 'Bei NccCore=Running und NccAgent=Stopped/Disabled darf genau ein NCC-Payload-Prozess vorhanden sein. Mehrere aktive Payload- oder Agent-Prozesse erklaeren die Warnung.'
} | ConvertTo-Json -Depth 5
