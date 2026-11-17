# Findet ein JDK 17+ für Gradle und keytool: NCC_JAVA_HOME, JAVA_HOME (wenn neu genug) oder das
# JDK aus Android Studio (über dessen Deinstallationseintrag in der Registry).
function Find-NccJavaHome {
    $candidates = @()
    if ($env:NCC_JAVA_HOME) { $candidates += $env:NCC_JAVA_HOME }
    if ($env:JAVA_HOME) { $candidates += $env:JAVA_HOME }
    $uninstall = Get-ItemProperty HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*, HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\* -ErrorAction SilentlyContinue |
        Where-Object DisplayName -eq 'Android Studio' | Select-Object -First 1
    if ($uninstall -and $uninstall.UninstallString) {
        $candidates += Join-Path (Split-Path ($uninstall.UninstallString.Trim('"'))) 'jbr'
    }
    $candidates += "$env:ProgramFiles\Android\Android Studio\jbr"
    foreach ($candidate in $candidates) {
        if (-not (Test-Path (Join-Path $candidate 'bin\keytool.exe'))) { continue }
        # Version aus der Datei "release" des JDK lesen – "java -version" schreibt nach stderr,
        # was PowerShell 5.1 mit ErrorActionPreference=Stop als Fehler wertet.
        $release = Join-Path $candidate 'release'
        if (-not (Test-Path $release)) { continue }
        $line = Select-String -Path $release -Pattern '^JAVA_VERSION="([0-9]+)(\.([0-9]+))?' | Select-Object -First 1
        if (-not $line) { continue }
        $major = [int]$line.Matches[0].Groups[1].Value
        if ($major -eq 1) { $major = [int]$line.Matches[0].Groups[3].Value }  # "1.8.0" = Java 8
        if ($major -ge 17) { return $candidate }
    }
    throw 'Kein JDK 17+ gefunden. Setze NCC_JAVA_HOME auf ein JDK (z. B. den Ordner "jbr" von Android Studio).'
}
