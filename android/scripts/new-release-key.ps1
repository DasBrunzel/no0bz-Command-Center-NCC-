<#
.SYNOPSIS
  Erzeugt einmalig den Release-Schlüssel der NCC-Android-App.

.DESCRIPTION
  keytool fragt das Passwort selbst ab; es wird nirgends gespeichert.
  WICHTIG: Sichere die erzeugte Datei und das Passwort (z. B. im Passwort-Manager).
  Ohne beides lassen sich keine Updates mehr für installierte Apps bauen.
#>
param(
    [string]$Path = (Join-Path $env:USERPROFILE '.ncc\ncc-release.jks'),
    [string]$Alias = 'ncc'
)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot '_java.ps1')

if (Test-Path -LiteralPath $Path) {
    throw "Es gibt bereits einen Schlüssel unter $Path. Er wird nicht überschrieben."
}
New-Item -ItemType Directory -Force -Path (Split-Path $Path) | Out-Null
$keytool = Join-Path (Find-NccJavaHome) 'bin\keytool.exe'

Write-Host "Erzeuge den Release-Schlüssel unter $Path"
Write-Host 'keytool fragt gleich zweimal nach einem Passwort (mindestens 6 Zeichen).'
& $keytool -genkeypair -keystore $Path -storetype PKCS12 -alias $Alias -keyalg RSA -keysize 4096 -validity 36500 -dname 'CN=NCC Android, O=no0bz Command Center'
if ($LASTEXITCODE -ne 0) { throw 'keytool ist fehlgeschlagen.' }

Write-Host ''
Write-Host "Fertig. Sichere jetzt die Datei $Path und das Passwort an einem zweiten Ort."
Write-Host 'Danach baust du Releases mit: .\scripts\build-release.ps1'
