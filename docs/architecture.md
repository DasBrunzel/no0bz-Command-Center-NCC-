# Architektur

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

