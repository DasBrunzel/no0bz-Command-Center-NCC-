function Start-NccInstallerAndWait {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string[]]$Arguments,
        [ValidateRange(30, 900)][int]$TimeoutSeconds = 300
    )

    # Start-Process -Wait includes descendants. The installer intentionally
    # starts a long-lived tray, so only wait for the Setup process itself.
    $process = Start-Process -FilePath $Path -ArgumentList $Arguments -PassThru
    if (-not $process.WaitForExit($TimeoutSeconds * 1000)) {
        Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
        throw "NCC installer timed out after $TimeoutSeconds seconds: $Path"
    }
    $process.Refresh()
    return $process
}

function Write-NccAgentDiagnostics {
    [CmdletBinding()]
    param([string]$SetupLog)

    # Prints only state and logs; config files hold pairing secrets.
    $root = Join-Path $env:ProgramData 'no0bz\NCC Agent'
    $files = @(
        (Join-Path $root 'core-state\state\core-state.json'),
        (Join-Path $root 'core-state\state\payload-health.json'),
        (Join-Path $env:ProgramData 'no0bz\NCC Agent Setup\install-error.log')
    )
    foreach ($file in $files) {
        if (Test-Path -LiteralPath $file) {
            Write-Host "--- $file ($((Get-Item -LiteralPath $file).LastWriteTimeUtc.ToString('o')))"
            Get-Content -LiteralPath $file -Tail 30 | ForEach-Object { Write-Host $_ }
        }
    }
    $attempt = Get-ChildItem -LiteralPath (Join-Path $env:ProgramData 'no0bz\NCC Agent Setup') -Directory -Filter 'failed-attempt-*' -ErrorAction SilentlyContinue |
        Sort-Object Name | Select-Object -Last 1
    if ($attempt) {
        Get-ChildItem -LiteralPath $attempt.FullName -File -Recurse | ForEach-Object {
            Write-Host "--- failed attempt: $($_.FullName) ($($_.LastWriteTimeUtc.ToString('o')))"
            Get-Content -LiteralPath $_.FullName -Tail 80 | ForEach-Object { Write-Host $_ }
        }
    }
    foreach ($log in @((Join-Path $root 'logs\service-host.log'), $SetupLog)) {
        if ($log -and (Test-Path -LiteralPath $log)) {
            Write-Host "--- $log"
            Get-Content -LiteralPath $log -Tail 80 | ForEach-Object { Write-Host $_ }
        }
    }
    Write-Host '--- NccAgentCore service and tray processes'
    Get-Service NccAgentCore -ErrorAction SilentlyContinue | Format-List Status, StartType | Out-String | Write-Host
    Get-CimInstance Win32_Process -Filter "Name='NccTray.exe' OR Name='NccServiceHost.exe' OR Name='ncc-core.exe'" -ErrorAction SilentlyContinue |
        ForEach-Object { Write-Host "$($_.Name) pid=$($_.ProcessId) parent=$($_.ParentProcessId) started=$($_.CreationDate.ToUniversalTime().ToString('o'))" }
}
