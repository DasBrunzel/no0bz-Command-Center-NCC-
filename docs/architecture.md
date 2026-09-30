# Architektur

## NCC 0.5 Zielarchitektur

```text
Windows-/Linux-Agenten ── HTTPS / API v1 ──► NCC Server ──► PostgreSQL
                                                    │
Browser ◄──── Fleet-API + statische React-App ──────┘
```

Der NCC-Server ist seit `0.5.0-alpha.1` eine eigene Anwendung ohne native GUI. Er startet
keine lokalen Hardware-Provider. Agent, Browseroberfläche und Windows-Integration
werden als getrennte Komponenten weiterentwickelt. PostgreSQL speichert den
Betriebszustand dauerhaft; Alembic versioniert jede Schemaänderung.

Seit `0.5.0-alpha.2` besitzt jeder Agent einen eigenen Zugang. Der Server speichert
nur den Token-Hash und bindet den Zugang bei der Aufnahme dauerhaft an eine stabile
Maschinen-ID. Authentifizierte Heartbeats aktualisieren `last_seen_at`; der
Online-Status wird aus diesem Zeitstempel und dem konfigurierten Timeout abgeleitet.

Seit `0.5.0-alpha.3` sammelt ein eigener `ncc_agent`-Prozess die Hardwaredaten. Jeder
Messpunkt wird vor der Übertragung in einem begrenzten lokalen SQLite-Puffer gespeichert.
Der Server dedupliziert Wiederholungen anhand einer agentseitigen Sample-UUID, bevor
er die nodebezogenen Punkte in PostgreSQL übernimmt.

Seit `0.5.0-beta.1` liefert der Server die gebaute React-Fleet-Oberfläche selbst aus.
Eine getrennt geschützte, nur lesende Fleet-API stellt Zusammenfassung, Nodes,
Online-Status, letzte Messwerte und begrenzte Telemetrieverläufe bereit. Der
Dashboard-Token ist ausdrücklich nicht identisch mit individuellen Agent-Tokens.

```text
Provider ─► Agent-Snapshot ─► SQLite-FIFO ─► HTTPS/Tailscale ─► API v1
                                                              │
                                                              ▼
                                              PostgreSQL telemetry_points
```

## NCC 0.4 Kompatibilitätsarchitektur

```text
Provider (psutil / NVML / hwmon / SMART / Demo)
        │ Probe + collect, eigener Timeout, Backoff
        ▼
ProviderRegistry ── Prioritäts-Merge
        │
        ▼
Collector-Thread ── threading.Lock ── aktueller Snapshot
        │                              │
        │                              ├── GET /api/metrics
        │                              └── WS /ws/live
        ▼
5-s-Puffer ── DuckDB oder Ringpuffer ── GET /api/history
        ▲
Node-Telemetrie ◄── NCC-Clients ◄── lokale Collector-Snapshots
```

Der Event-Loop führt keine blockierenden Hardwareabfragen aus. Jeder Provider wird im
Thread-Pool aufgerufen und nach Fehlern exponentiell pausiert. Der Collector ersetzt den
Snapshot atomar unter einem Lock. REST und WebSocket lesen dieselbe Kopie.

Der Storage-Recorder fragt den Snapshot unabhängig von verbundenen Browsern ab.
Schreibvorgänge werden fünf Sekunden gesammelt. Der stündliche Retention-Job entfernt
Punkte außerhalb des konfigurierten Fensters. Ohne DuckDB bleibt die App im begrenzten
In-Memory-Modus funktionsfähig.

Im Servermodus registrieren sich Clients mit demselben Token und senden ihre Snapshots.
Der Server markiert Nodes nach 15 Sekunden ohne Kontakt offline. Ein Client verbindet
sich mit exponentiellem Backoff erneut.

