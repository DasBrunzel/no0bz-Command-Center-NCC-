# Phase 3: Geräteaufnahme und Heartbeats (`0.5.0-alpha.2`)

Stand: 2026-09-30

## Ergebnis

Der NCC-Server kann nun individuelle Agent-Zugänge erzeugen, einen Zugang dauerhaft
an genau einen Rechner binden und dessen Online-Zustand über authentifizierte
Heartbeats verfolgen. Registrierung und letzter Kontakt bleiben in PostgreSQL über
Serverneustarts hinweg erhalten.

## Agent-Token erzeugen

Nach `alembic upgrade head` wird ein Token direkt auf dem Server erzeugt:

```powershell
ncc-agent-token create --name "Gaming-PC"
```

Der Klartext-Token wird genau einmal ausgegeben. In PostgreSQL liegt ausschließlich
sein SHA-256-Hash. Standardmäßig läuft ein Token nach 720 Stunden ab. Ein anderes
Intervall oder ein Token ohne Ablaufdatum wird so erzeugt:

```powershell
ncc-agent-token create --name "Root-Agent" --expires-hours 168
ncc-agent-token create --name "Dauer-Agent" --expires-hours 0
```

Metadaten anzeigen oder einen einzelnen Zugang sofort sperren:

```powershell
ncc-agent-token list
ncc-agent-token revoke TOKEN-ID
```

## Aufnahmeablauf

1. Der Administrator erzeugt einen individuellen Token und übergibt ihn sicher.
2. Der Agent ruft `POST /api/v1/nodes/enroll` mit dem Token im Bearer-Header auf.
3. Der Server erzeugt den Node und bindet den Token an seine stabile Maschinen-ID.
4. Derselbe Token kann seine Maschine erneut anmelden, aber keine andere Identität übernehmen.
5. Der Agent sendet anschließend regelmäßig `POST /api/v1/nodes/heartbeat`.

Ein vom Administrator erzeugter Token gilt als ausdrückliche Einladung; der damit
neu aufgenommene Node wird deshalb automatisch freigegeben. Eine spätere Webverwaltung
kann den Node oder seinen Token wieder sperren.

## API

| Methode | Pfad | Zweck |
|---|---|---|
| `POST` | `/api/v1/nodes/enroll` | Token an eine Maschinen-ID binden |
| `POST` | `/api/v1/nodes/heartbeat` | letzten Kontakt und Agent-Metadaten aktualisieren |
| `GET` | `/api/v1/nodes/me` | eigenen Node- und Online-Status abrufen |

Die Authentifizierung erfolgt mit `Authorization: Bearer <Agent-Token>` oder dem
Header `X-NCC-Agent-Token`. Der alte gemeinsame NCC-0.4-Token gilt nicht für diese API.

## Sicherheitsgrenzen

- Tokens dürfen ausschließlich über HTTPS oder ein geschütztes Tailscale-Netz übertragen werden.
- Maschinen-IDs dürfen keine frei wechselnden Hostnamen sein; der kommende Agent erzeugt
  und speichert dafür eine stabile lokale UUID.
- Die Server-CLI besitzt absichtlich keinen HTTP-Admin-Endpunkt. Benutzeranmeldung und
  rollenbasierte Webverwaltung folgen in einer späteren Phase.
- Heartbeats enthalten in dieser Phase Statusmetadaten, aber noch keine Messwerte.
  Telemetrie und Offline-Puffer folgen mit `0.5.0-alpha.3`.

## Konfiguration

| Variable | Standard | Bedeutung |
|---|---:|---|
| `NCC_SERVER_HEARTBEAT_INTERVAL_SECONDS` | `10` | empfohlenes Heartbeat-Intervall |
| `NCC_SERVER_NODE_OFFLINE_AFTER_SECONDS` | `30` | Zeit bis zur Offline-Anzeige |

## Verifikation

Getestet werden Token-Hashing, Ablauf, Widerruf, Erstaufnahme, erneute Aufnahme,
Identitätskonflikte, Heartbeats, Persistenz und Offline-Berechnung. GitHub Actions
führt die Migration zusätzlich gegen einen echten PostgreSQL-17-Dienst aus.
