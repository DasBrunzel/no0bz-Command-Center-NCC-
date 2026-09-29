# Plattform-Setup

## Windows 10/11

Starte je nach Rolle `scripts\start_ncc_local.bat`, `start_ncc_server.bat` oder
`start_ncc_client.bat`. Für den Autostart öffne die Aufgabenplanung, erstelle
eine Aufgabe „NCC“, wähle „Bei Anmeldung“ und verwende das Startskript als Programm.
Setze „Starten in“ auf das Repository. Verwende kein Administratorkonto, außer ein
Hardware-Provider benötigt es ausdrücklich.

LibreHardwareMonitor ist optional. Für zusätzliche Board-, Lüfter-, Spannungs- und
Power-Sensoren kann sein Remote Web Server auf Port 8085 aktiviert werden. Die
Grundfunktionen und GPU-Erkennung benötigen LHM nicht.

## Linux / Raspberry Pi OS

Starte je nach Rolle `scripts/start_ncc_local.sh`, `start_ncc_server.sh` oder
`start_ncc_client.sh`. Für systemd kopiere `docs/ncc.service`, passe Benutzer
und Pfad an, führe `systemctl daemon-reload` aus und aktiviere den Dienst. SMART-Zugriff
und einige hwmon-Dateien benötigen passende Gruppen-/udev-Rechte.

## macOS

Die psutil-Basiswerte funktionieren best effort. Hardwaretemperaturen und GPU-Sensoren
werden deaktiviert, wenn kein sicherer Provider verfügbar ist.

## Tailscale

Verwende die dedizierten `start_ncc_tailscale_server`- und
`start_ncc_tailscale_client`-Skripte. Der Server-Starter akzeptiert ausschließlich
eine aktive IPv4-Adresse aus `100.64.0.0/10` und bindet NCC nur an diese Schnittstelle.
Damit wird Port 8350 nicht automatisch im normalen LAN angeboten. Server und Clients
verwenden denselben NCC-Token; die Übergabedatei kann mit `manage_ncc_token` erzeugt,
exportiert und importiert werden.

## Container

`docker compose up --build` startet NCC. `pid: host`, `/sys` und GPU-Durchreichung sind
optional, erhöhen aber die Sichtbarkeit des Containers auf den Host erheblich.

