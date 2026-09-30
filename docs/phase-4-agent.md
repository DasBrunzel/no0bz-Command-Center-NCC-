# Phase 4: Windows-/Linux-Agent und Offline-Puffer (`0.5.0-alpha.3`)

Stand: 2026-09-30

## Ergebnis

NCC besitzt nun einen eigenständigen, GUI-losen Agenten für Windows und Linux. Er
sammelt lokale Hardwarewerte über die vorhandenen Provider, registriert sich mit
dem individuellen Agent-Token und überträgt Messwerte gebündelt an den NCC-Server.
Ist der Server nicht erreichbar, bleiben die Punkte in einem lokalen SQLite-Puffer
und werden nach dem Wiederverbinden automatisch nachgeliefert.

## Vorbereitung auf dem Server

Serverdatenbank migrieren und einen eigenen Token für den Zielrechner erzeugen:

```powershell
alembic upgrade head
ncc-agent-token create --name "Gaming-PC"
```

Der ausgegebene Token gehört ausschließlich zu diesem Agenten. Geht dessen lokale
Identitätsdatei verloren, ist für die neue Identität ein neuer Token erforderlich.

## Windows-Start

```powershell
scripts\start_ncc_agent.bat
```

Der Starter fragt Server-URL und Agent-Token ab. Der Token wird bei der Eingabe
verdeckt und nur als Umgebungsvariable an den laufenden Prozess weitergegeben.

Für Tailscale:

```powershell
scripts\start_ncc_agent_tailscale.bat 100.100.100.10
```

Alternativ kann ein MagicDNS-Name angegeben werden. Der Tailscale-Starter aktiviert
HTTP ausdrücklich, weil der Transport bereits durch Tailscale verschlüsselt ist.

## Linux-Start

```bash
chmod +x scripts/start_ncc_agent*.sh
./scripts/start_ncc_agent.sh
```

Tailscale:

```bash
./scripts/start_ncc_agent_tailscale.sh 100.100.100.10
```

## Dauerhafte Konfiguration

Kopiere `ncc-agent.env.example` nach `ncc-agent.env` und trage mindestens
`NCC_AGENT_SERVER_URL` sowie `NCC_AGENT_TOKEN` ein. Diese Datei wird von Git
ignoriert. Für den Regelbetrieb wird HTTPS erwartet. Nur in einem ausdrücklich
vertrauenswürdigen Tailscale-Netz darf gesetzt werden:

```text
NCC_AGENT_ALLOW_INSECURE_HTTP=1
```

## Geräteidentität und lokaler Zustand

Beim ersten Start erzeugt der Agent eine zufällige UUID und speichert sie dauerhaft:

- Windows: `%LOCALAPPDATA%\no0bz\NCC Agent\machine-id`
- Linux: `~/.local/state/ncc-agent/machine-id`

Im selben Verzeichnis liegt `telemetry-buffer.sqlite3`. Der Puffer enthält standardmäßig
höchstens 10.000 Punkte. Bei vollständigem Puffer werden die ältesten Punkte zuerst
entfernt. Token oder andere Zugangsdaten werden nicht in dieser Datenbank gespeichert.

## Übertragungsverhalten

1. Der Agent sammelt standardmäßig alle fünf Sekunden einen Snapshot.
2. Jeder Punkt erhält eine zufällige UUID und landet zuerst im lokalen Puffer.
3. Der Agent nimmt das Gerät auf beziehungsweise sendet einen Heartbeat.
4. Bis zu 25 Punkte werden je Anfrage an `/api/v1/nodes/telemetry` gesendet.
5. Erst nach einer erfolgreichen Serverantwort löscht der Agent die lokalen Punkte.
6. Doppelt gesendete Sample-IDs werden vom Server erkannt und nicht erneut gespeichert.
7. Bei Ausfällen steigt die Wiederholungswartezeit schrittweise bis maximal 60 Sekunden.

## Unterstützte Messwerte

Der Agent verwendet dieselbe Provider-Schicht wie die bisherige lokale Anwendung:

- CPU, RAM, Swap, Netzwerk, Volumes, Datenträger und Prozesse über `psutil`
- NVIDIA über NVML
- Windows-GPUs herstellerunabhängig über Performance Counter
- Linux AMDGPU und hwmon über sysfs
- optionale SMART- und LibreHardwareMonitor-Ergänzungen

LibreHardwareMonitor bleibt optional und ist unter Linux nicht erforderlich.

## Abgrenzung

`0.5.0-alpha.3` ist ein lauffähiger Agent-Prozess, aber noch kein installierter
Windows-Dienst oder Linux-systemd-Paket. Diese Integrationen folgen mit der späteren
Installer-/Dienstphase. Als nächster Entwicklungsschritt ist die neue Fleet-Weboberfläche
für `0.5.0-beta.1` vorgesehen.
