# Phase 7 – Browser-Pairing für Geräte

Ab `0.5.0-beta.9` erfolgt die gewöhnliche Geräteaufnahme ohne sichtbaren Agent-Token:

1. Agent unter Windows oder Linux installieren.
2. Den ausgegebenen Pairing-Link auf dem Zielgerät im Browser öffnen.
3. Einen achtstelligen Admin-Code eingeben.
4. Der Agent ruft seinen internen Zugang einmalig ab und verbindet sich mit der Fleet.

Pairing-Anfragen laufen nach 15 Minuten ab. Der Server speichert nur den Prüfwert des
lokalen Pairing-Geheimnisses. Bei einer erneuten Aufnahme derselben Maschinen-ID wird
der bestehende Node beibehalten und der frühere Agent-Zugang widerrufen.

## API

| Methode | Pfad | Zweck |
| --- | --- | --- |
| `POST` | `/api/v1/agent-pairings/register` | Lokale Pairing-Anfrage anlegen |
| `POST` | `/api/v1/agent-pairings/{id}/approve` | Anfrage nach Browser-Adminzugang freigeben |
| `POST` | `/api/v1/agent-pairings/{id}/claim` | Internen Agent-Zugang einmalig abrufen |
| `GET` | `/api/v1/agent-pairings` | Pairing-Status im Dashboard anzeigen |
