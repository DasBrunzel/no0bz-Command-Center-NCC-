# Plattform-Setup

## Windows 10/11

Starte `scripts\start_ncc.bat`. Für den Autostart öffne die Aufgabenplanung, erstelle
eine Aufgabe „NCC“, wähle „Bei Anmeldung“ und verwende das Startskript als Programm.
Setze „Starten in“ auf das Repository. Verwende kein Administratorkonto, außer ein
Hardware-Provider benötigt es ausdrücklich.

LibreHardwareMonitor: als Administrator starten und unter **Options → Remote Web
Server → Run** den lokalen Server auf Port 8085 aktivieren. NCC greift standardmäßig
nur auf `http://127.0.0.1:8085/data.json` zu.

## Linux / Raspberry Pi OS

Starte `scripts/start_ncc.sh`. Für systemd kopiere `docs/ncc.service`, passe Benutzer
und Pfad an, führe `systemctl daemon-reload` aus und aktiviere den Dienst. SMART-Zugriff
und einige hwmon-Dateien benötigen passende Gruppen-/udev-Rechte.

## macOS

Die psutil-Basiswerte funktionieren best effort. Hardwaretemperaturen und GPU-Sensoren
werden deaktiviert, wenn kein sicherer Provider verfügbar ist.

## Container

`docker compose up --build` startet NCC. `pid: host`, `/sys` und GPU-Durchreichung sind
optional, erhöhen aber die Sichtbarkeit des Containers auf den Host erheblich.

