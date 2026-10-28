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
