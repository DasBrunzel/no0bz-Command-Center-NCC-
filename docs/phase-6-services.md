# Phase 6 – Dienste, Installer und Tailscale-Diagnose

## Ergebnis

`0.5.0-beta.2` kann Server und Agent nach einem Neustart des Betriebssystems automatisch
starten. Die neue Dienstschicht verändert die Telemetrie- oder Fleet-API nicht. Sie
kapselt Start, Stopp, Neustart, Konfiguration, Migrationen und Logs reproduzierbar.

Vorausgesetzt werden Python 3.10 oder neuer und für den Server eine erreichbare
PostgreSQL-Datenbank. Die Tailscale-Installer setzen eine bereits angemeldete
Tailscale-Installation voraus; sie installieren oder konfigurieren kein VPN selbst.

## Windows

| Zweck | Starter |
|---|---|
| Agent installieren | `scripts\install_ncc_agent_service.bat` |
| Agent über Tailscale | `scripts\install_ncc_agent_tailscale_service.bat` |
| Server installieren | `scripts\install_ncc_server_service.bat` |
| Server über Tailscale | `scripts\install_ncc_server_tailscale_service.bat` |
| Status und Logs | `scripts\ncc_service_status.bat` |
| Agent deinstallieren | `scripts\uninstall_ncc_agent_service.bat` |
| Server deinstallieren | `scripts\uninstall_ncc_server_service.bat` |

Der Installer fordert selbst eine UAC-Freigabe an, erstellt eine eigene virtuelle
Python-Umgebung unter `%ProgramData%\no0bz\NCC`, installiert oder aktualisiert NCC und
registriert `NccAgent` beziehungsweise `NccServer` in der Windows-Dienstverwaltung.
Nach Fehlern erfolgen drei zeitlich gestaffelte Neustartversuche.

Konfiguration und Logs:

```text
%ProgramData%\no0bz\NCC\config\agent.env
%ProgramData%\no0bz\NCC\config\server.env
%ProgramData%\no0bz\NCC\logs\agent.log
%ProgramData%\no0bz\NCC\logs\server.log
```

## Linux

Normales Netzwerk:

```bash
sudo ./scripts/install_ncc_server_service.sh
sudo ./scripts/install_ncc_agent_service.sh https://ncc.example
```

Tailscale:

```bash
sudo ./scripts/install_ncc_server_tailscale_service.sh
sudo ./scripts/install_ncc_agent_tailscale_service.sh ncc-server.tailnet.ts.net
```

Die Units heißen `ncc-server.service` und `ncc-agent.service`. Der Server läuft als
eigener Systembenutzer `ncc`; der Agent läuft für vollständigen Hardwarezugriff als
root, jedoch ohne zusätzliche Capabilities und mit systemd-Härtung. Logs landen im
Journal und können mit `scripts/ncc_service_status.sh` gelesen werden.

## Updates und Deinstallation

Ein erneuter Installer-Aufruf aktualisiert Programmdateien und Units, übernimmt aber
vorhandene `.env`-Dateien unverändert. Datenbankmigrationen laufen vor dem Serverstart.

```bash
sudo ./scripts/uninstall_ncc_service.sh agent
sudo ./scripts/uninstall_ncc_service.sh server
```

Diese Befehle erhalten Konfiguration und Agent-Puffer. Nur `--purge` löscht die Daten
des gewählten Bestandteils. Unter Windows ist das entsprechende optionale Argument
`-Purge`.

## Tailscale-Betriebstest

`ncc-doctor` führt keine Änderungen aus. Es prüft Namensauflösung, den Tailscale-
Adressbereich, API-Erreichbarkeit, Datenbankbereitschaft und den passenden Token:

```bash
export NCC_DOCTOR_TOKEN='individueller-agent-token'
ncc-doctor agent \
  --server-url http://100.100.100.10:8350 \
  --tailscale --allow-insecure-http
```

Für den Servermodus wird stattdessen der Dashboard-Token verwendet. Bei normalem
Remote-Betrieb verlangt das Werkzeug HTTPS. `--no-verify-tls` ist nur für einen bewusst
eingesetzten privaten Test mit selbstsigniertem Zertifikat vorgesehen.

## Verifikation und Grenze

- Windows-PowerShell-Skripte werden syntaktisch auf Windows geprüft.
- Shell-Skripte werden unter Ubuntu syntaktisch geprüft.
- Dienstkonfiguration, Diagnose, URL-Schutz und Token-Header besitzen automatisierte
  Tests.
- Der vollständige Python-, Frontend- und PostgreSQL-Testlauf bleibt aktiv.

Die tatsächliche Installation auf dem Windows-Root-Server benötigt dessen lokale
Administratorfreigabe und die echte PostgreSQL-/Tailscale-Konfiguration. Diese finale
Umgebungsprüfung erfolgt beim geplanten Root-Server-Rollout und kann nicht durch CI
simuliert werden.
