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
        $java = Join-Path $candidate 'bin\java.exe'
        if (-not (Test-Path $java)) { continue }
        $version = (& $java -version 2>&1 | Select-Object -First 1) -replace '.*version "([0-9]+).*', '$1'
        if ([int]$version -ge 17) { return $candidate }
    }
    throw 'Kein JDK 17+ gefunden. Setze NCC_JAVA_HOME auf ein JDK (z. B. den Ordner "jbr" von Android Studio).'
}
