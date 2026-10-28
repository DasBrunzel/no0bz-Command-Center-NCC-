[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$FirstSetup,
    [Parameter(Mandatory = $true)][string]$NextSetup
)

$ErrorActionPreference = 'Stop'
$root = Join-Path $env:ProgramData 'no0bz\NCC Agent'
$appDir = Join-Path $env:ProgramFiles 'no0bz\NCC Agent'
$trayExe = Join-Path $appDir 'NccTray.exe'
$tray = $null
function Find-TrayProcesses {
    @(Get-Process -Name NccTray -ErrorAction SilentlyContinue)
}
try {
    $args = @('/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', '/SERVERURL=http://127.0.0.1:8350',
        '/CLOSEAPPLICATIONS', '/FORCECLOSEAPPLICATIONS', '/RESTARTAPPLICATIONS', '/LOGCLOSEAPPLICATIONS')
    $install = Start-Process -FilePath $FirstSetup -ArgumentList $args -Wait -PassThru
    if ($install.ExitCode -ne 0 -or (Get-Service NccAgentCore).Status -ne 'Running') {
        throw 'Tray smoke: version A did not install and start.'
    }
    $runEntry = (Get-ItemProperty -Path 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Run' -Name NccTray).NccTray
    if ($runEntry -notlike "*$trayExe*") { throw 'Machine-wide tray autostart is missing.' }

    Stop-Process -Id $tray.Id -Force
    $tray.WaitForExit(10000) | Out-Null
    Stop-Service NccAgentCore
    (Get-Service NccAgentCore).WaitForStatus('Stopped', [TimeSpan]::FromSeconds(30))
    $tray = Start-Process -FilePath $trayExe -PassThru
    $trayDeadline = (Get-Date).AddSeconds(20)
    do {
        Start-Sleep -Seconds 1
        $existingTray = @(Find-TrayProcesses)
    } while ($existingTray.Count -eq 0 -and (Get-Date) -lt $trayDeadline)
    if ($existingTray.Count -ne 1) {
        throw "Silent installation did not start exactly one tray: $($existingTray.Count)."
    }
    $tray = $existingTray[0]
    $deadline = (Get-Date).AddSeconds(30)
    do {
        Start-Sleep -Seconds 2
        $running = (Get-Service NccAgentCore).Status -eq 'Running'
    } while (-not $running -and (Get-Date) -lt $deadline)
    if (-not $running) { throw 'Tray did not restart a manually stopped service at sign-in.' }
    if ($tray.HasExited) { throw 'Tray exited instead of remaining in the user session.' }

    $second = Start-Process -FilePath $trayExe -PassThru
    Start-Sleep -Seconds 4
    $trayCount = (Find-TrayProcesses).Count
    if (-not $second.HasExited -or $tray.HasExited -or $trayCount -ne 1) {
        throw "Tray single-instance guard failed: firstExited=$($tray.HasExited), secondExited=$($second.HasExited), count=$trayCount."
    }

    $upgradeLog = Join-Path $env:TEMP 'ncc-agent-tray-upgrade.log'
    $upgrade = Start-Process -FilePath $NextSetup -ArgumentList ($args + "/LOG=$upgradeLog") -Wait -PassThru
    if ($upgrade.ExitCode -ne 0) {
        if (Test-Path -LiteralPath $upgradeLog) {
            Get-Content -LiteralPath $upgradeLog -Tail 100 | ForEach-Object { Write-Host $_ }
        }
        throw "Tray smoke: version B upgrade failed: $($upgrade.ExitCode)"
    }
    Start-Sleep -Seconds 10
    $state = Get-Content (Join-Path $root 'core-state\state\core-state.json') -Raw | ConvertFrom-Json
    if ($state.active_payload -ne '0.6.0-beta.8-ci.2' -or $state.health -ne 'healthy') {
        throw 'Tray smoke: version B payload is not healthy.'
    }
    if ((Find-TrayProcesses).Count -ne 1) { throw 'Tray did not return after silent upgrade.' }
} finally {
    Find-TrayProcesses | ForEach-Object {
        if ($null -ne $_ -and $null -ne $_.Id) {
            Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue
        }
    }
    $uninstaller = Join-Path $appDir 'unins000.exe'
    if (Test-Path $uninstaller) {
        Start-Process -FilePath $uninstaller -ArgumentList @('/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART') -Wait | Out-Null
    }
}
