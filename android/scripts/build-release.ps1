<#
.SYNOPSIS
  Baut eine signierte Release-APK der NCC-Android-App.

.DESCRIPTION
  Fragt das Passwort des Release-Schlüssels ab, gibt es nur für diesen Build an Gradle weiter und
  legt die APK als dist\ncc-android-<Version>-<Build>.apk ab. Diese Datei lädst du im NCC-Dashboard
  unter „Releases → Android-App“ hoch; der Dateiname füllt Version und Build-Nummer automatisch aus.
#>
param(
    [string]$Keystore = (Join-Path $env:USERPROFILE '.ncc\ncc-release.jks'),
    [string]$Alias = 'ncc'
)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot '_java.ps1')
$project = Split-Path $PSScriptRoot

if (-not (Test-Path -LiteralPath $Keystore)) {
    throw "Kein Release-Schlüssel unter $Keystore. Erst .\scripts\new-release-key.ps1 ausführen."
}
$gradleFile = Get-Content (Join-Path $project 'app\build.gradle.kts') -Raw
$versionName = [regex]::Match($gradleFile, 'versionName\s*=\s*"([^"]+)"').Groups[1].Value
$versionCode = [regex]::Match($gradleFile, 'versionCode\s*=\s*(\d+)').Groups[1].Value

$secure = Read-Host "Passwort für $Keystore" -AsSecureString
$bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
$previousJava = $env:JAVA_HOME
try {
    $env:NCC_RELEASE_STORE_PASSWORD = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
    $env:NCC_RELEASE_KEYSTORE = $Keystore
    $env:NCC_RELEASE_KEY_ALIAS = $Alias
    $env:JAVA_HOME = Find-NccJavaHome
    Push-Location $project
    # Ohne Konfigurations-Cache, damit das Passwort nicht im Gradle-Cache landet.
    & .\gradlew.bat --no-configuration-cache testReleaseUnitTest assembleRelease
    if ($LASTEXITCODE -ne 0) { throw 'Der Release-Build ist fehlgeschlagen.' }
} finally {
    Pop-Location -ErrorAction SilentlyContinue
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
    Remove-Item Env:NCC_RELEASE_STORE_PASSWORD, Env:NCC_RELEASE_KEYSTORE, Env:NCC_RELEASE_KEY_ALIAS -ErrorAction SilentlyContinue
    $env:JAVA_HOME = $previousJava
}

$built = Join-Path $project 'app\build\outputs\apk\release\app-release.apk'
if (-not (Test-Path $built)) { throw 'Keine signierte APK gefunden – ist der Schlüssel richtig?' }
$dist = New-Item -ItemType Directory -Force -Path (Join-Path $project 'dist')
$target = Join-Path $dist "ncc-android-$versionName-$versionCode.apk"
Copy-Item $built $target -Force
$hash = (Get-FileHash $target -Algorithm SHA256).Hash.ToLower()

Write-Host ''
Write-Host "Fertig: $target"
Write-Host "Version $versionName (Build $versionCode) · SHA-256 $hash"
Write-Host 'Hochladen im NCC-Dashboard: Releases → Android-App → App-Version verteilen.'
