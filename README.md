# no0bz Command Center (NCC)

![Version](https://img.shields.io/badge/version-0.5.0--beta.65-ff334f)
![Python](https://img.shields.io/badge/Python-3.10%2B-3776ab)
![License](https://img.shields.io/badge/license-MIT-green)

Real-Time System Monitor & Local Sync Hub (Python/FastAPI + React).

> **NCC 0.5 befindet sich im Beta-Test.** Die aktuelle Version `0.5.0-beta.65`
> besteht aus einem dauerhaft laufenden Server, GUI-losen Windows-/Linux-Agenten,
> einer Unraid-API-Integration und einer gemeinsamen Fleet-Weboberfläche. Die
> NCC-0.4-Starter bleiben ausschließlich als Kompatibilitätsschicht erhalten.

## NCC-0.5-Server und Fleet-Dashboard (Beta)

Der Server ist eine separate, GUI-lose Anwendung. Er nimmt Telemetrie von Windows-
und Linux-Agenten sowie der Unraid-API entgegen und stellt das Dashboard zentral
über Tailscale oder lokal bereit. Der Server selbst kann bei Bedarf zusätzlich als
normaler NCC-Agent aufgenommen werden. PostgreSQL, Migrationen und Server können mit
Docker Compose gemeinsam gestartet werden:

```powershell
$env:NCC_POSTGRES_PASSWORD = "ein-langes-eigenes-passwort"
$env:NCC_SERVER_DASHBOARD_TOKEN = "ein-langer-zufaelliger-dashboard-token"
docker compose up --build
```

Danach steht das Dashboard unter <http://127.0.0.1:8350> bereit. Status und
API-Dokumentation liegen unter `/api/v1/status/live` und `/api/docs`.
Für den normalen Zugriff wird im Dashboard ein einmaliger achtstelliger Admin-Code
erstellt. Nach dessen Eingabe erhält der Browser eine geschützte Sitzung. Der frühere
Dashboard-Token ist nur noch ein technischer Rückfallzugang für bestehende
Installationen und wird nicht für die tägliche Nutzung benötigt.

### Geräteaufnahme per Browser-Pairing

Neue Windows- und Linux-Agenten benötigen keinen kopierbaren Token. Der Installer
erzeugt lokal eine geheime, 15 Minuten gültige Pairing-Anfrage und zeigt einen
Browser-Link an. Auf dem Zielgerät diesen Link öffnen, mit einem achtstelligen
Admin-Code anmelden und die Verbindung wird automatisch hergestellt. Das Dashboard
zeigt dabei den Status **Wartet**, **Freigegeben** oder **Verbunden**.

Der interne Agent-Zugang bleibt ausschließlich zwischen Agent und Server. Wird ein
Gerät später neu gekoppelt, bleibt seine Maschinen-ID erhalten und der alte Zugang
wird widerrufen. Der Installer zeigt nach der Einrichtung den persönlichen
Browser-Link für genau dieses Gerät an.

### Commander und Beta-Tester

Bestehende Dashboard-Zugänge bleiben **Commander**. Beim Erstellen eines neuen
achtstelligen Admin-Codes kann der Schalter **Beta-Tester** aktiviert werden. Dieser
Zugang erhält im Dashboard ein Badge und darf Daten ansehen, aber keine neuen Codes
erstellen sowie keine Geräte, Einladungen oder Zugänge löschen oder widerrufen.

Admin-Codes werden nur einmal angezeigt, als Hash gespeichert und erzeugen eine
HttpOnly-Browsersitzung. Ein Widerruf beendet die zugehörige Sitzung.

### Dashboard, Fleet und Statistiken

Das Dashboard enthält eine Fleet-Übersicht, einen sortierbaren **Fleet Navigator**
mit frei anlegbaren Gruppen sowie eine Detailansicht für jedes Gerät. Die
Detailansicht zeigt Betriebssystem, CPU-/GPU-Modell und — soweit erkannt — passende
Herstellerlogos. Die Navigation und Gruppen können eingeklappt werden.

Die Seite **Statistiken** fasst die gesamte Fleet zusammen: Verfügbarkeit je Agent,
gewichtete CPU- und RAM-Kapazität, GPUs, eine kombinierte Auslastungsrangliste,
Monatsverkehr sowie einen Live-Gesamtverlauf für Up- und Download. Rohdaten bleiben
erhalten; die Monatsanzeige beginnt am Monatsersten neu.

Der Server überwacht zudem die **Agent-Gesundheit** unabhängig vom Zugriff auf das
jeweilige Gerät. Warnungen informieren über fehlende frische Telemetrie, alte
Agent-Versionen, wiederholte Doppelmeldungen und unplausible Netzwerkzähler. Sie
erscheinen im Warnungszentrum und können über Telegram zugestellt werden.

Neben den Farbthemes stehen in den Einstellungen drei alternative Dashboard-Layouts
bereit: **Orbit**, **Blueprint** und **Studio**. Die Auswahl wird nur im jeweiligen
Browser gespeichert.

### Unraid

Unraid wird ohne NCC-Agent über die offizielle Unraid-API integriert. NCC zeigt
Array- und Laufwerksbelegung, Temperaturen soweit verfügbar, VMs und Docker-
Container an. Laufende Workloads stehen immer oben. Die Unraid-Verbindung wird auf
dem NCC-Server konfiguriert; der API-Schlüssel wird nicht im Dashboard angezeigt.

### Neuer Windows-/Linux-Agent

Der Agent benötigt kein Browserfenster und keinen lokalen Webserver. Für eine
Tailscale-Verbindung auf Windows (PowerShell als Administrator):

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\install_ncc_service.ps1 -Component Agent -Tailscale -ServerUrl 100.64.0.10 -AgentMode Task
```

Unter Linux:

```bash
sudo ./scripts/install_ncc_agent_service.sh --tailscale 100.64.0.10
```

Für Tailscale existieren `start_ncc_agent_tailscale.bat` und
`start_ncc_agent_tailscale.sh`. Messwerte werden zuerst in einem begrenzten lokalen
SQLite-Puffer gespeichert und nach Verbindungsunterbrechungen automatisch übertragen.
Die vollständige Anleitung steht im [Phase-4-Bericht](docs/phase-4-agent.md).

### Dauerbetrieb als Dienst

Unter Windows werden Server oder Agent über einen Doppelklick installiert; die
PowerShell-Installation fordert bei Bedarf selbst Administratorrechte an:

```text
scripts\install_ncc_server_tailscale_service.bat
scripts\install_ncc_agent_tailscale_service.bat
```

Ohne Tailscale stehen `install_ncc_server_service.bat` und
`install_ncc_agent_service.bat` bereit. Unter Linux:

```bash
sudo ./scripts/install_ncc_server_tailscale_service.sh
sudo ./scripts/install_ncc_agent_tailscale_service.sh SERVER-NAME-ODER-IP
```

Die Installer bewahren vorhandene Konfigurationen und Pairing-Zugänge bei Updates. Normales
Deinstallieren entfernt nur den Dienst; `-Purge` unter Windows beziehungsweise
`--purge` unter Linux löscht auf ausdrücklichen Wunsch auch Konfiguration oder
Agent-Puffer. Status und Logs zeigt `ncc_service_status.bat` beziehungsweise
`ncc_service_status.sh`.

Eine Verbindung lässt sich ohne Änderungen mit `ncc-doctor` prüfen. Token sollten
über `NCC_DOCTOR_TOKEN` gesetzt werden, damit sie nicht in der Prozessliste stehen:

```powershell
$env:NCC_DOCTOR_TOKEN = "dashboard-token"
ncc-doctor server --server-url http://100.100.100.10:8350 --tailscale --allow-insecure-http
```

Alle Details stehen im [Phase-6-Bericht](docs/phase-6-services.md).

NCC ist ein lokales, quelloffenes Monitoring-Dashboard für Power User, Gamer,
Entwickler und Homelabs. Es sammelt Systemwerte über austauschbare Provider, streamt
sie per WebSocket, hält eine lokale Historie und verbindet mehrere PCs ohne externe
Telemetrie. Fehlende Hardware und optionale Tools werden als nicht verfügbar gemeldet.

> Teile dieses Projekts entstanden mit KI-Unterstützung. Änderungen sollten wie jeder
> andere Beitrag geprüft und auf der Zielhardware getestet werden.

## Screenshot

`docs/assets/dashboard.png` und `docs/assets/demo.gif` sind Platzhalter für einen
Release-Screenshot und ein kurzes Demo-GIF. `NCC_DEMO=1` ist ausschließlich für
Entwickler: Es erzeugt künstliche Testwerte, damit Screenshots keine echten System-
oder Netzwerkdaten enthalten. Für Installation und normalen Betrieb wird
`NCC_DEMO=1` nicht benötigt.

## Legacy-Schnellstart (NCC 0.4)

> Dieser Abschnitt dokumentiert nur die erhaltene NCC-0.4-Kompatibilität. Für neue
> NCC-0.5-Installationen nutze den Server-/Agenten-Dienst und das Browser-Pairing
> weiter oben.

### Windows 10/11

```powershell
git clone https://github.com/DasBrunzel/no0bz-Command-Center-NCC-.git
cd no0bz-Command-Center-NCC-
scripts\start_ncc_local.bat
```

### Linux

```bash
git clone https://github.com/DasBrunzel/no0bz-Command-Center-NCC-.git
cd no0bz-Command-Center-NCC-
chmod +x scripts/start_ncc*.sh
./scripts/start_ncc_local.sh
```

Öffne danach <http://127.0.0.1:8350>. Beim ersten Start erzeugt NCC `.env` und zeigt
das zufällige Token einmal in der Konsole. Das gebaute Frontend ist im Repository
enthalten; Node.js wird nur zur Frontend-Entwicklung benötigt.

Demo-Modus: setze `NCC_DEMO=1` in `.env`. LAN-Betrieb: setze bewusst `NCC_HOST=0.0.0.0`
und `NCC_MODE=server`; lies vorher [SECURITY.md](SECURITY.md).

### NCC-0.4-Kompatibilitätsmodi

Die bisherige NCC-Anwendung übernimmt je nach Starter weiterhin eine der drei
Legacy-Rollen. Diese Starter gehören noch nicht zur neuen NCC-0.5-Architektur:

| Rolle | Windows | Linux | Zweck |
|---|---|---|---|
| Local | `scripts\start_ncc_local.bat` | `scripts/start_ncc_local.sh` | einzelner PC, nur Loopback |
| Server | `scripts\start_ncc_server.bat` | `scripts/start_ncc_server.sh` | Dashboard und Sammelstelle im LAN |
| Client | `scripts\start_ncc_client.bat` | `scripts/start_ncc_client.sh` | sendet seine Telemetrie an den Server |
| Tailscale-Server | `scripts\start_ncc_tailscale_server.bat` | `scripts/start_ncc_tailscale_server.sh` | bindet ausschließlich an die Tailscale-IP |
| Tailscale-Client | `scripts\start_ncc_tailscale_client.bat` | `scripts/start_ncc_tailscale_client.sh` | verbindet sich über Tailscale-IP oder MagicDNS |

Beim Client-Start werden die Server-URL, beispielsweise
`http://192.168.1.10:8350`, und der `NCC_TOKEN` des Servers abgefragt. Server und
Client müssen denselben Token verwenden. Die Synchronisation läuft über Port 8350.

### Tailscale-Schnellstart

Tailscale muss auf Server und Client angemeldet und verbunden sein. Auf dem Server:

```powershell
scripts\start_ncc_tailscale_server.bat
```

Der Starter erkennt ausschließlich Adressen aus Tailscales CGNAT-Bereich
`100.64.0.0/10`, bindet NCC an diese Adresse und zeigt die fertige URL an. Existiert
noch kein Token, werden `.env` und `ncc-token-transfer.txt` erzeugt. Übertrage diese
Datei sicher auf den Client und starte dort:

```powershell
scripts\start_ncc_tailscale_client.bat
```

Alternativ können Ziel und Übergabedatei direkt angegeben werden:

```powershell
scripts\start_ncc_tailscale_client.bat 100.100.100.10 ncc-token-transfer.txt
```

Der Client prüft Adresse, Server-Modus und gemeinsamen Token vor dem eigentlichen
Start. Bei einem abweichenden Token oder gesperrten Port erscheint dadurch eine
konkrete Fehlermeldung statt einer stillen Verbindungswiederholung.

Nach dem Import sollte `ncc-token-transfer.txt` auf beiden Geräten gelöscht werden.
Der dauerhafte Token liegt in der von Git ausgeschlossenen `.env`. Tailscale-Grants
sollten TCP-Port 8350 nur für die vorgesehenen Clients freigeben.

### Legacy-Token-Verwaltung

Unter Windows öffnet `scripts\manage_ncc_token.bat` ein Menü. Unter Linux stehen
folgende Aufrufe zur Verfügung:

```bash
scripts/manage_ncc_token.sh generate
scripts/manage_ncc_token.sh show
scripts/manage_ncc_token.sh rotate
scripts/manage_ncc_token.sh export ncc-token-transfer.txt
scripts/manage_ncc_token.sh import ncc-token-transfer.txt
```

Eine Rotation macht den bisherigen Token sofort ungültig. Danach müssen die neue
Übergabedatei auf allen Clients importiert und alle NCC-Prozesse neu gestartet werden.

## Funktionen

- Zentraler Server für Windows-/Linux-Agenten und die Unraid-API
- Echtzeit-CPU-, RAM-, Datenträger-, Netzwerk-, Akku-, GPU- und Prozessdaten
- Fleet Navigator mit Gruppen, Drag-&-Drop-Sortierung, einklappbaren Bereichen und
  benutzerdefinierten Gruppen
- Statistikseite mit Fleet-Kapazität, Verfügbarkeit, Auslastungsrangliste,
  Monatsverkehr und Live-Gesamtgraph
- Unraid-Übersicht für Laufwerke, Temperaturen, VMs und Docker-Container
- Browser-Pairing ohne kopierbare Agent-Tokens
- Commander-/Beta-Tester-Rollen mit sichtbaren Badges und serverseitigem Schutz
- Provider-Erkennung, Capability-Report, Timeouts, Cache und exponentieller Backoff
- WebSocket-Livestream und gebündelte lokale DuckDB-Historie mit Memory-Fallback
- Standalone-, Server- und Client-Modus mit Offline-Erkennung
- abgesicherter Prozess-Kill mit Schutzliste und Audit-Log
- lokaler Chat-/Prompt-/Datei-Hub mit Upload-Härtung
- responsive React-Oberfläche mit SVG-Gauges, Hardwarelogos, Netzwerkverläufen und
  einklappbarer Navigation
- Farbthemes sowie drei vollständige alternative Layouts: Orbit, Blueprint und Studio

## Konfiguration

Alle Werte liegen in `.env`. Die Vorlage [.env.example](.env.example) dokumentiert:
`NCC_HOST`, `NCC_PORT`, `NCC_TOKEN`, `NCC_MODE`, `NCC_SERVER_URL`,
`NCC_UPLOAD_MAX_MB`, `NCC_UPLOAD_TOTAL_MB`, `NCC_RETENTION_HOURS`, `NCC_INTERVAL`,
`NCC_LHM_URL`, `NCC_DEMO` und `NCC_ALLOW_LOOPBACK_NO_TOKEN`.

## Unterstützte Hardware und Voraussetzungen

| Provider | Plattform | Werte | Voraussetzung/Rechte |
|---|---|---|---|
| psutil | Windows, Linux, macOS | CPU, RAM, Swap, Disks, Netz, Akku, Prozesse | keine Zusatztools |
| NVIDIA NVML | Windows, Linux | GPU, VRAM, Temperatur | NVIDIA-Treiber; `nvidia-ml-py` ist enthalten |
| Windows GPU Counters | Windows | AMD-, Intel- und NVIDIA-Name/Auslastung | aktueller Grafiktreiber, keine Administratorrechte |
| Linux AMDGPU | Linux | AMD-Auslastung, VRAM und Temperatur | aktiver `amdgpu`-Kerneltreiber |
| Linux hwmon | Linux, Raspberry Pi OS | Temperaturen, Lüfter/GPU je nach Treiber | Leserechte auf `/sys` |
| smartctl | Windows, Linux | Laufwerkszustand (Best Effort) | smartmontools, ggf. erhöhte Rechte |
| LibreHardwareMonitor | Windows | optionale Zusatzwerte: Board, Lüfter, Spannungen, CPU-Power | nicht erforderlich; lokaler Webserver Port 8085 |
| Demo | alle | vollständige synthetische Daten | `NCC_DEMO=1` |

Provider, die das aktuelle System nicht unterstützt, deaktivieren sich ohne Absturz und
erscheinen mit Grund im Hardware-Report.

LibreHardwareMonitor ist ausdrücklich **keine Voraussetzung**. CPU, RAM, Netzwerk,
Datenträger und Prozesse kommen plattformübergreifend aus `psutil`; NVIDIA verwendet
NVML, Windows besitzt einen herstellerunabhängigen GPU-Fallback und Linux liest AMD
direkt über `amdgpu`/sysfs. Ohne LHM fehlen lediglich einige optionale Sensorwerte.

## API

| Methode | Pfad | Zweck | Schreibschutz |
|---|---|---|---|
| WS | `/ws/live` | Live-Snapshot | Token außerhalb erlaubtem Loopback |
| GET | `/` | Dashboard | nein |
| GET | `/api/metrics` | aktueller Snapshot | nein |
| GET | `/api/sensors/capabilities` | verfügbare Sensoren | nein |
| GET | `/api/nodes` | PC-Präsenz | nein |
| POST | `/api/nodes/register` | Node registrieren | Token + Rate-Limit |
| POST | `/api/nodes/telemetry` | Node-Snapshot | Token + Rate-Limit |
| GET | `/api/multipc/mode` | Betriebsmodus | nein |
| GET | `/api/auth/check` | Client-Verbindung und Token prüfen | Token |
| POST | `/api/profile` | Profil speichern | Token |
| GET | `/api/system/profile` | Hardware-Cache | nein |
| POST | `/api/system/profile/refresh` | Hardware neu erkennen | Token |
| GET | `/api/changelog` | Changelog als JSON | nein |
| GET | `/changelog` | Changelog als HTML | nein |
| GET | `/api/history?minutes=60` | lokale/Node-Historie | nein |
| POST | `/api/kill` | Prozess beenden | Token + Rate-Limit |
| GET | `/api/chat/messages` | Nachrichten | nein |
| POST | `/api/chat/send` | Nachricht senden | Token + Rate-Limit |
| POST | `/api/chat/upload` | Dateien hochladen | Token + Rate-Limit |
| GET | `/api/chat/files` | Dateien auflisten | nein |

## Entwicklung

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux: source .venv/bin/activate
python -m pip install -e ".[dev]"
pytest -q
ruff check backend tests scripts
mypy
cd frontend && pnpm install && pnpm run build
```

Die Datenbank schreibt in Batches von fünf Sekunden. Bei einem harten Absturz können
daher maximal ungefähr fünf Sekunden noch ungeflushter Messwerte verloren gehen.
Retention läuft geplant statt bei jedem Insert. Der In-Memory-Fallback ist auf 86.400
Punkte begrenzt.

## Benchmark

Lokale Messung am 29.09.2026 unter Windows/Python 3.13, 10 Läufe mit automatisch
erkannten Providern: Mittelwert 1.636,00 ms, P95 1.691,28 ms, Prozess-RSS 54,84 MB
und gemessene Prozess-CPU 38,3 %. Werte sind system- und providerabhängig. Reproduziere
sie mit `PYTHONPATH=backend python scripts/bench.py`; es werden bewusst keine
unbelegten Ressourcenversprechen gemacht.

Weitere Dokumente: [Architektur](docs/architecture.md),
[Provider hinzufügen](docs/adding-a-provider.md), [Plattform-Setup](docs/platform-setup.md),
[Security](SECURITY.md) und [Contributing](CONTRIBUTING.md).

## Versionierung

NCC verwendet ab Version `0.3.0` [Semantic Versioning](https://semver.org/):
`MAJOR.MINOR.PATCH`. Inkompatible Änderungen erhöhen MAJOR, neue kompatible
Funktionen MINOR und kompatible Fehlerkorrekturen PATCH. Backend, Frontend,
Dokumentation und Release-Tags tragen dieselbe Versionsnummer.

## Lizenz

MIT – siehe [LICENSE](LICENSE).

