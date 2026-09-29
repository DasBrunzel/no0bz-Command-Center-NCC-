# no0bz Command Center (NCC)

![Version](https://img.shields.io/badge/version-0.1.0-12d8f4)
![Python](https://img.shields.io/badge/Python-3.10%2B-3776ab)
![License](https://img.shields.io/badge/license-MIT-green)

Real-Time System Monitor & Local Sync Hub (Python/FastAPI + React).

NCC ist ein lokales, quelloffenes Monitoring-Dashboard für Power User, Gamer,
Entwickler und Homelabs. Es sammelt Systemwerte über austauschbare Provider, streamt
sie per WebSocket, hält eine lokale Historie und verbindet mehrere PCs ohne externe
Telemetrie. Fehlende Hardware und optionale Tools werden als nicht verfügbar gemeldet.

> Teile dieses Projekts entstanden mit KI-Unterstützung. Änderungen sollten wie jeder
> andere Beitrag geprüft und auf der Zielhardware getestet werden.

## Screenshot

`docs/assets/dashboard.png` und `docs/assets/demo.gif` sind Platzhalter für einen
Release-Screenshot und ein kurzes Demo-GIF. Erzeuge sie mit `NCC_DEMO=1`, öffne das
Dashboard bei 1440 px Breite und erfasse CPU-, Netzwerk- und Node-Kacheln ohne Token
oder persönliche Daten.

## Schnellstart

### Windows 10/11

```powershell
git clone https://github.com/DasBrunzel/no0bz-Command-Center-NCC-.git
cd no0bz-Command-Center-NCC-
scripts\start_ncc.bat
```

### Linux

```bash
git clone https://github.com/DasBrunzel/no0bz-Command-Center-NCC-.git
cd no0bz-Command-Center-NCC-
chmod +x scripts/start_ncc.sh
./scripts/start_ncc.sh
```

Öffne danach <http://127.0.0.1:8350>. Beim ersten Start erzeugt NCC `.env` und zeigt
das zufällige Token einmal in der Konsole. Das gebaute Frontend ist im Repository
enthalten; Node.js wird nur zur Frontend-Entwicklung benötigt.

Demo-Modus: setze `NCC_DEMO=1` in `.env`. LAN-Betrieb: setze bewusst `NCC_HOST=0.0.0.0`
und `NCC_MODE=server`; lies vorher [SECURITY.md](SECURITY.md).

## Funktionen

- Echtzeit-CPU-, RAM-, Datenträger-, Netzwerk-, Akku-, GPU- und Prozessdaten
- Provider-Erkennung, Capability-Report, Timeouts, Cache und exponentieller Backoff
- WebSocket-Livestream und gebündelte lokale DuckDB-Historie mit Memory-Fallback
- Standalone-, Server- und Client-Modus mit Offline-Erkennung
- abgesicherter Prozess-Kill mit Schutzliste und Audit-Log
- lokaler Chat-/Prompt-/Datei-Hub mit Upload-Härtung
- responsive React-Oberfläche mit SVG-Gauges und Canvas-Netzwerkgraph
- neun zentral definierte Themes: CachyOS Cyan, Cyber Neon, Dark Matter OLED,
  Clean Light, Matrix Hacker, Dracula, Nordic Frost, Retro Amber, Nightmare Red

## Konfiguration

Alle Werte liegen in `.env`. Die Vorlage [.env.example](.env.example) dokumentiert:
`NCC_HOST`, `NCC_PORT`, `NCC_TOKEN`, `NCC_MODE`, `NCC_SERVER_URL`,
`NCC_UPLOAD_MAX_MB`, `NCC_UPLOAD_TOTAL_MB`, `NCC_RETENTION_HOURS`, `NCC_INTERVAL`,
`NCC_LHM_URL`, `NCC_DEMO` und `NCC_ALLOW_LOOPBACK_NO_TOKEN`.

## Unterstützte Hardware und Voraussetzungen

| Provider | Plattform | Werte | Voraussetzung/Rechte |
|---|---|---|---|
| psutil | Windows, Linux, macOS | CPU, RAM, Swap, Disks, Netz, Akku, Prozesse | keine Zusatztools |
| NVIDIA NVML | Windows, Linux | GPU, VRAM, Temperatur | NVIDIA-Treiber, optional `nvidia-ml-py` |
| Linux hwmon | Linux, Raspberry Pi OS | Temperaturen, Lüfter/GPU je nach Treiber | Leserechte auf `/sys` |
| smartctl | Windows, Linux | Laufwerkszustand (Best Effort) | smartmontools, ggf. erhöhte Rechte |
| LibreHardwareMonitor | Windows | Board, Lüfter, Spannungen, GPU, CPU-Power | lokaler Webserver Port 8085, ggf. Administrator |
| Demo | alle | vollständige synthetische Daten | `NCC_DEMO=1` |

Provider, die das aktuelle System nicht unterstützt, deaktivieren sich ohne Absturz und
erscheinen mit Grund im Hardware-Report.

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

## Lizenz

MIT – siehe [LICENSE](LICENSE).

