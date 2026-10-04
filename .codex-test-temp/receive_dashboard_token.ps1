[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"

function Test-IsAdministrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = [Security.Principal.WindowsPrincipal]::new($identity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

if (-not (Test-IsAdministrator)) {
    Start-Process powershell.exe -Verb RunAs -ArgumentList @(
        "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", ('"' + $PSCommandPath + '"')
    )
    exit
}

$tailscale = "C:\Program Files\Tailscale\tailscale.exe"
$incoming = "C:\ProgramData\no0bz\NCC\incoming"
$downloads = Join-Path $env:USERPROFILE "Downloads"
$tokenFile = $null
$token = $null

try {
    if (-not (Test-Path -LiteralPath $tailscale)) { throw "Tailscale wurde nicht gefunden." }
    New-Item -ItemType Directory -Force -Path $incoming | Out-Null
    & icacls.exe $incoming /inheritance:r /grant:r '*S-1-5-18:F' '*S-1-5-32-544:F' | Out-Null

    $matches = @(Get-ChildItem -LiteralPath $downloads -File -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -like "ncc-dashboard-HORSTPC*.token" } |
        Sort-Object LastWriteTimeUtc -Descending)
    if ($matches.Count -eq 0) {
        Write-Host "[NCC] Warte auf den Dashboard-Token von HorstServer ..."
        & $tailscale file get --wait --conflict=rename $incoming
        if ($LASTEXITCODE -ne 0) { throw "Die Tailscale-Dateiübertragung ist fehlgeschlagen." }
        $matches = @(Get-ChildItem -LiteralPath $incoming -File |
            Where-Object { $_.Name -like "ncc-dashboard-HORSTPC*.token" } |
            Sort-Object LastWriteTimeUtc -Descending)
    }
    if ($matches.Count -ne 1) { throw "Es wurde nicht genau eine Dashboard-Token-Datei empfangen." }

    $tokenFile = $matches[0].FullName
    $token = (Get-Content -Raw -LiteralPath $tokenFile).Trim()
    if ($token -notmatch '^[A-Za-z0-9_-]{32,}$') { throw "Die empfangene Datei enthält keinen gültigen Dashboard-Token." }

    Set-Clipboard -Value $token
    Write-Host ""
    Write-Host "[NCC] Der Dashboard-Token liegt jetzt in der Zwischenablage."
    Write-Host "[NCC] Im Browser in das Token-Feld klicken, Strg+V drücken und verbinden."
    Read-Host "Danach hier Enter drücken; die Zwischenablage wird dann geleert"
    Set-Clipboard -Value ""
    Remove-Item -LiteralPath $tokenFile -Force
    $tokenFile = $null
    Write-Host "[NCC] Token-Übergabe sicher abgeschlossen."
} catch {
    Write-Error $_
    if ($tokenFile -and (Test-Path -LiteralPath $tokenFile)) {
        Write-Host "[NCC] Die geschützte Datei wurde zur Fehlerbehebung beibehalten."
    }
    Read-Host "Enter zum Schließen"
    exit 1
} finally {
    $token = $null
}
