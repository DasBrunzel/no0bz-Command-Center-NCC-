# Phase 5 – Fleet-Weboberfläche

## Ergebnis

`0.5.0-beta.1` macht den dauerhaft laufenden NCC-Server zur zentralen Browser-
Anlaufstelle. Die Oberfläche wird als statische React-App direkt vom Server ausgeliefert
und zeigt ausschließlich Daten aus PostgreSQL. Auf dem Root-Server ist weiterhin kein
Desktopfenster und kein Browser erforderlich.

## Oberfläche

- Fleet-Zusammenfassung mit Gesamt-, Online- und Offline-Zahlen
- Online-Geräte zuerst, anschließend alphabetisch sortiert
- Gerätesuche und Node-Inspector
- CPU-, RAM- und GPU-Gauges
- Netzwerk- und Laufwerkswerte
- Verlauf der letzten 120 CPU-, RAM- und GPU-Messpunkte
- responsive Navigation für Desktop, Tablet und Smartphone
- neun Themes von Nightmare Red bis Clean Light

Die Oberfläche aktualisiert Fleet und Status alle fünf Sekunden. Auswahl und Theme
bleiben im Browser erhalten; Messdaten werden nicht im Browser dauerhaft gespeichert.

## Fleet-API

| Methode | Pfad | Inhalt |
|---|---|---|
| `GET` | `/api/v1/fleet/summary` | Fleet-Zähler und Serverzeit |
| `GET` | `/api/v1/fleet/nodes` | alle Nodes mit letztem Messpunkt |
| `GET` | `/api/v1/fleet/nodes/{id}` | einzelner Node |
| `GET` | `/api/v1/fleet/nodes/{id}/telemetry` | bis zu 1.000 Messpunkte |

## Dashboard-Zugang

Der Dashboard-Zugang ist vom Agent-Zugang getrennt. Für einen nur lokal gebundenen
Server darf die Loopback-Ausnahme aktiv bleiben. Für Tailscale, LAN oder Reverse Proxy:

```dotenv
NCC_SERVER_DASHBOARD_TOKEN=ein-langer-zufaelliger-dashboard-token
NCC_SERVER_DASHBOARD_ALLOW_LOOPBACK_WITHOUT_TOKEN=0
```

Der Browser sendet diesen Wert als `X-NCC-Dashboard-Token`. Er wird lokal im Browser
gespeichert. Ein individueller Agent-Token gehört niemals in die Browseroberfläche.
Ein zufälliger Wert kann mit `ncc-dashboard-token` erzeugt werden.

## Verifikation

- 39 Python-Tests einschließlich Authentifizierung und Fleet-Datenfluss
- Ruff und strikte Mypy-Prüfung für Windows und Linux
- TypeScript-Typprüfung und Vite-Produktions-Build
- visuelle Prüfung des mobilen und 1440-Pixel-Desktop-Layouts

Als nächster geplanter Schritt folgt `0.5.0-beta.2` mit Windows-Dienst,
Linux-systemd-Integration, Installern und einem vollständigen Tailscale-Betriebstest.
