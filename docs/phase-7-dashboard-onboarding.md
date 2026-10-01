# Phase 7 – Dashboard-Geräteaufnahme

Ab `0.5.0-beta.3` erstellt ein Administrator Agent-Einladungen im Fleet-Dashboard:

1. Dashboard öffnen und **Gerät hinzufügen** wählen.
2. Einen eindeutigen Gerätenamen und eine Laufzeit wählen.
3. Den einmalig angezeigten Token kopieren.
4. Den Token im Agent-Installer des Zielsystems eingeben.

Der Server speichert nur den Hash des Tokens. Der Klartext kann nach dem Schließen der
Anzeige nicht wiederhergestellt werden. Die Übersicht zeigt ausschließlich Namen,
Status und Zeitstempel. Eine noch aktive Einladung kann jederzeit widerrufen werden.

## API

Alle Endpunkte benötigen den Dashboard-Token in `X-NCC-Dashboard-Token`.

| Methode | Pfad | Zweck |
| --- | --- | --- |
| `GET` | `/api/v1/agent-invitations` | Status aller Einladungen abrufen |
| `POST` | `/api/v1/agent-invitations` | Einladung erzeugen, Klartext nur einmal zurückgeben |
| `POST` | `/api/v1/agent-invitations/{token_id}/revoke` | Einladung widerrufen |

Für automatisierte oder Notfallabläufe bleibt das lokale Werkzeug
`ncc-agent-token` verfügbar. Für die gewöhnliche Aufnahme eines Geräts ist der
Dashboard-Weg vorgesehen.
