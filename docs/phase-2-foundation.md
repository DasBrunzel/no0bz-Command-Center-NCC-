# Phase 2: Server-Fundament (`0.5.0-alpha.1`)

Stand: 2026-09-30

## Ergebnis

NCC besitzt nun eine eigenständige Server-Anwendung im Paket `ncc_server`. Sie ist
vom bisherigen lokalen Dashboard getrennt, startet keine Hardware-Provider und
liefert keine Browser-GUI aus. Die bestehende NCC-0.4-Anwendung bleibt während der
weiteren Migration als Kompatibilitätsschicht im Paket `ncc` erhalten.

## Server-API

Die erste versionierte API liegt unter `/api/v1`:

| Pfad | Bedeutung |
|---|---|
| `GET /api/v1/status/live` | Prozess läuft |
| `GET /api/v1/status/ready` | PostgreSQL ist erreichbar |
| `GET /api/v1/version` | Server- und API-Version |
| `GET /api/docs` | interaktive API-Dokumentation |

Der Root-Pfad liefert nur Server-Metadaten als JSON. Es werden keine HTML-Dateien
oder Frontend-Assets bereitgestellt.

## Persistentes Datenmodell

Die erste Alembic-Migration erzeugt diese Tabellen:

- `nodes`: dauerhafte Geräteidentitäten und Freigabestatus
- `telemetry_points`: nodebezogene Messpunkte
- `users`: spätere Browserbenutzer und Rollen
- `agent_tokens`: vorbereitete individuelle und widerrufbare Agent-Schlüssel
- `audit_events`: nachvollziehbare sicherheitsrelevante Aktionen

Passwörter und Tokens sind im Modell ausschließlich als Hash vorgesehen. Aufnahme,
Token-Ausgabe und Heartbeats werden in `0.5.0-alpha.2` implementiert.

## Start mit Docker Compose

Vor dem ersten Start muss ein eigenes Datenbankpasswort gesetzt werden:

```powershell
$env:NCC_POSTGRES_PASSWORD = "ein-langes-eigenes-passwort"
docker compose up --build
```

Compose wartet auf PostgreSQL, führt `alembic upgrade head` aus und startet danach
den GUI-losen Server auf Port 8350. Für den späteren Root-Server-Betrieb kommen noch
Windows-Dienst, HTTPS-Reverse-Proxy und Backup-Automation hinzu.

## Abgrenzung der Alpha 1

Diese Phase schafft das ausführbare und migrierbare Fundament. Noch nicht enthalten
sind Geräteaufnahme, echte Agent-Authentifizierung, Heartbeats, Telemetrie-Annahme
und die neue Weboberfläche. Diese Funktionen folgen in den nächsten Alpha-Phasen.
