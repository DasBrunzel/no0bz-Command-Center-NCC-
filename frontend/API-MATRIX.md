# API- und Rechte-Matrix

Quelle: `backend/ncc_server/api/v1/*.py`, `backend/ncc_server/auth.py`, `backend/ncc_server/access.py`, `backend/ncc_server/schemas.py`.
Alle Pfade relativ zu `/api/v1`. UI-Orte sind Hash-Routen des neuen Frontends (siehe `DECISIONS.md`, D-04).

## Rollen-Legende

| Kürzel | Bedeutung | Backend-Prüfung |
|---|---|---|
| **öffentlich** | ohne Sitzung | – |
| **angemeldet** | jede Dashboard-Identität (Commander, Beta-Tester, Freund) | `require_dashboard_access` / `require_dashboard_identity` |
| **Team** | Commander oder Beta-Tester, keine Freunde | `require_staff_access` |
| **Commander** | nur Commander | `require_commander_access` |
| **Verwalter** | Commander für jedes Gerät, Freund nur für eigene Geräte. Beta-Tester bekommen **403** | `access.manageable_node` |
| **Konto** | angemeldet **und** persönliches Konto (keine Admin-Code-Sitzung) | `_personal_account` / `identity.user_id` |
| **Agent** | nur Agenten-Token, kein Dashboard | `require_agent_token` |

Freunde sehen über `access.visible_node_ids` nur eigene Geräte (oder alle Statistiken mit `full_statistics`). Das Frontend blendet für Freunde alle Team-Bereiche aus.

## Matrix

✅ = im neuen UI erreichbar und geprüft (Code-Abgleich `src/api/endpoints.ts` ↔ Aufrufer, Playwright-Tests und Mock in `tests/mock/api.ts`) · ➖ = bewusst nicht im Dashboard (Agent-/Betriebs-API)

| ✓ | Methode | Endpoint | Rolle | Zweck | UI-Ort |
|---|---|---|---|---|---|
| ✅ | GET | `/version` | öffentlich | Server-Version | Fußzeile der Navigation, Einstellungen › Über |
| ✅ | GET | `/status/live` | öffentlich | Erreichbarkeit | Einstellungen › Über (Status-Lampe) |
| ➖ | GET | `/status/ready` | öffentlich | DB-Bereitschaft | nur für Betrieb/Healthchecks |
| ✅ | POST | `/admin-codes/redeem` | öffentlich | Login per 8-stelligem Code | Login › Admin-Code |
| ✅ | POST | `/admin-codes/logout` | öffentlich (Cookie) | Abmelden | Navigation › Abmelden |
| ✅ | GET | `/admin-codes/access` | angemeldet | Rolle der Sitzung | Sitzungsprüfung (App-Start, 401-Erkennung) |
| ✅ | GET | `/admin-codes` | Team | Admin-Codes auflisten | Aufnahme › Admin-Codes |
| ✅ | POST | `/admin-codes` | Commander | Code erstellen (optional Beta-Tester) | Aufnahme › Admin-Codes › „Code erstellen“ (einmalige Anzeige) |
| ✅ | POST | `/admin-codes/{code_id}/revoke` | Commander | Code widerrufen | Aufnahme › Admin-Codes › Zeilenaktion |
| ✅ | POST | `/users/login` | öffentlich | Login Benutzername/Passwort | Login › Konto |
| ✅ | POST | `/users/register` | öffentlich (Einladungscode) | Freundes-Konto registrieren | Login › Registrieren |
| ✅ | GET | `/users/me` | angemeldet | Name, Rolle, Konto-Art | App-Shell (Identität, Badge) |
| ✅ | POST | `/users/password` | Konto | Eigenes Passwort ändern (meldet andere Sitzungen ab) | Einstellungen › Mein Konto |
| ✅ | GET | `/users/me/telegram` | angemeldet | Persönliche Telegram-Verknüpfung | Einstellungen › Mein Konto › Telegram |
| ✅ | POST | `/users/me/telegram/link` | Konto | Link-Code erzeugen | Einstellungen › Mein Konto › „Telegram verknüpfen“ |
| ✅ | PATCH | `/users/me/telegram` | Konto | Wochenrückblick an/aus | Einstellungen › Mein Konto › Telegram |
| ✅ | DELETE | `/users/me/telegram` | Konto | Verknüpfung lösen | Einstellungen › Mein Konto › Telegram |
| ✅ | GET | `/users` | Commander | Konten auflisten | Einstellungen › Konten |
| ✅ | POST | `/users` | Commander | Konto anlegen | Einstellungen › Konten › „Konto anlegen“ |
| ✅ | PATCH | `/users/{user_id}` | Commander | Rolle, aktiv, volle Statistik | Einstellungen › Konten › Zeile |
| ✅ | GET | `/users/invites` | Commander | Konto-Einladungen | Einstellungen › Konten › Einladungen |
| ✅ | POST | `/users/invites` | Commander | Einladung erstellen (Code einmalig) | Einstellungen › Konten › „Einladung erstellen“ |
| ✅ | POST | `/users/invites/{invite_id}/revoke` | Commander | Einladung widerrufen | Einstellungen › Konten › Einladungen |
| ✅ | GET | `/fleet/summary` | angemeldet | Zahlen der Fleet | Lage › Kopf |
| ✅ | GET | `/fleet/alerts?limit=` | angemeldet | Warnungen (aktiv + verlauf) | Lage › Störmelder, Warnungen-Popover, App-Badge |
| ✅ | POST | `/fleet/alerts/clear` | Commander | Aktive Warnungen leeren | Lage › Störmelder › „Alle quittieren“ |
| ✅ | GET | `/fleet/alert-policy` | angemeldet | Warnregeln lesen | Einstellungen › Warnregeln (für alle sichtbar, nur Commander speichern) |
| ✅ | PUT | `/fleet/alert-policy` | Commander | Warnregeln speichern | Einstellungen › Warnregeln |
| ✅ | GET | `/fleet/telegram` | Team | Server-Telegram-Einstellungen | Einstellungen › Telegram |
| ✅ | PUT | `/fleet/telegram` | Commander | Speichern | Einstellungen › Telegram |
| ✅ | POST | `/fleet/telegram/test` | Commander | Testnachricht | Einstellungen › Telegram › „Testnachricht senden“ |
| ✅ | GET | `/fleet/nodes` | angemeldet | Alle (sichtbaren) Nodes inkl. letzter Telemetrie | Lage (Gleisbild), Geräte, überall |
| ✅ | GET | `/fleet/nodes/{id}` | angemeldet (sichtbar) | Node-Detail | Geräte › Detail |
| ✅ | PATCH | `/fleet/nodes/{id}` | Verwalter | Umbenennen | Geräte › Detail › Verwaltung |
| ✅ | DELETE | `/fleet/nodes/{id}` | Commander | Node vergessen | Geräte › Detail › Verwaltung › Gefahrenzone |
| ✅ | PATCH | `/fleet/nodes/{id}/role` | Commander | Zugriffsrolle des Agenten | Geräte › Detail › Verwaltung |
| ✅ | PUT | `/fleet/nodes/{id}/owner` | Commander | Besitzer zuweisen | Geräte › Detail › Verwaltung |
| ✅ | PUT | `/fleet/nodes/{id}/gaming-mode` | Verwalter | Gaming Mode (0–480 min) | Geräte › Detail (Kopf), Lage › Gleisbild-Popover |
| ✅ | PUT | `/fleet/nodes/{id}/sensor-labels` | Verwalter | Lüfter/Temperatur benennen | Geräte › Detail › Sensoren |
| ✅ | POST | `/fleet/nodes/{id}/update-check` | Verwalter | Update-Prüfung anstoßen | Geräte › Detail › Updates |
| ✅ | PUT | `/fleet/nodes/{id}/release` | Commander | Release zuweisen | Geräte › Detail › Updates (Releases › Zuweisung nutzt die Releases-Route) |
| ✅ | PUT | `/fleet/nodes/{id}/update-channel` | Commander | Kanal setzen | Geräte › Detail › Updates |
| ✅ | GET | `/fleet/nodes/{id}/telemetry?limit=&after=` | angemeldet (sichtbar) | Telemetrie-Verlauf, Cursor | Geräte › Detail › Verlauf (Charts) |
| ✅ | GET | `/fleet/nodes/{id}/network/history?limit=` | angemeldet (sichtbar) | Netzwerk-Verlauf | Geräte › Detail › Netzwerk (Lage › Live-Verkehr summiert `latest` aus `/fleet/nodes`) |
| ✅ | GET | `/fleet/nodes/{id}/network/month` | angemeldet (sichtbar) | Monatsverbrauch | Geräte › Detail › Netzwerk |
| ✅ | POST | `/fleet/network/reset` | Commander | Netzwerkzähler zurücksetzen | Geräte › Detail › Netzwerk |
| ✅ | GET | `/fleet/groups` | angemeldet | Gruppen | Geräte (Gruppierung), Lage (Gleise) |
| ✅ | POST | `/fleet/groups` | Commander | Gruppe anlegen | Geräte › „Anordnen“ |
| ✅ | PUT | `/fleet/layout` | Commander | Gruppen/Reihenfolge speichern | Geräte › „Anordnen“ |
| ✅ | GET | `/fleet/physical-devices` | angemeldet | Physische Geräte / Dualboot | Geräte (Weiche), Detail › Verwaltung |
| ✅ | POST | `/fleet/physical-devices` | Commander | Physisches Gerät aus Profilen anlegen | Geräte › Detail › Verwaltung › Dualboot |
| ✅ | POST | `/fleet/physical-devices/{d}/nodes/{n}` | Commander | Profil zuordnen | Geräte › Detail › Verwaltung › Dualboot |
| ✅ | DELETE | `/fleet/physical-devices/{d}/nodes/{n}` | Commander | Profil lösen | Geräte › Detail › Verwaltung › Dualboot |
| ✅ | GET | `/fleet/hardware/stats?days=&node_id=&utc_offset_minutes=` | angemeldet (Statistik-Sicht) | Hardware-Statistik | Geräte › Hardware-Statistik, Detail › Sensoren |
| ✅ | GET | `/fleet/games` | angemeldet | Spieleliste | Spiele › Bibliothek |
| ✅ | GET | `/fleet/games/stats?days=&node_id=&utc_offset_minutes=` | angemeldet | Spielzeit-Statistik | Spiele › Spielzeit |
| ✅ | PATCH | `/fleet/games/{id}` | Commander | Steam-Zuordnung korrigieren | Spiele › Spiel-Dialog |
| ✅ | GET | `/fleet/games/{id}/artwork` | angemeldet | Banner | Spiele, Now-Playing |
| ✅ | PUT | `/fleet/games/{id}/artwork` | Commander | Banner hochladen (roh, 920×430 zugeschnitten) | Spiele › Spiel-Dialog |
| ✅ | DELETE | `/fleet/games/{id}/artwork` | Commander | Banner entfernen | Spiele › Spiel-Dialog |
| ✅ | PUT | `/fleet/nodes/{id}/game-settings` | Verwalter | Spiel-Erfassung pro Node | Geräte › Detail › Spiele |
| ✅ | GET | `/fleet/chat/messages?limit=&before=&after=` | angemeldet | Nachrichten (Cursor) | Chat |
| ✅ | POST | `/fleet/chat/messages` | angemeldet | Nachricht (plain/markdown) | Chat › Eingabe |
| ✅ | POST | `/fleet/chat/uploads` | angemeldet | Nachricht mit Datei (multipart) | Chat › Anhang |
| ✅ | GET | `/fleet/chat/messages/{id}/attachment` | angemeldet | Anhang laden | Chat › Nachricht |
| ✅ | GET | `/fleet/chat/participants` | angemeldet | Teilnehmer | Chat › Teilnehmer |
| ✅ | GET | `/agent-pairings` | Team | Pairing-Anfragen | Aufnahme › Kopplungen |
| ✅ | POST | `/agent-pairings/{id}/approve` | angemeldet | Anfrage freigeben | Pairing-Link `?pair=`, Aufnahme › Kopplungen (nur Commander) |
| ➖ | POST | `/agent-pairings/register` | öffentlich (Agent) | Agent meldet sich an | – |
| ➖ | POST | `/agent-pairings/{id}/claim` | öffentlich (Agent-Secret) | Agent holt Token | – |
| ✅ | GET | `/agent-invitations` | Team | Agent-Einladungen | Aufnahme › Agent-Einladungen |
| ✅ | POST | `/agent-invitations` | Commander | Einladung erstellen (Token einmalig) | Aufnahme › Agent-Einladungen |
| ✅ | POST | `/agent-invitations/{id}/revoke` | Commander | Widerrufen | Aufnahme › Agent-Einladungen |
| ✅ | DELETE | `/agent-invitations/{id}` | Commander | Widerrufene entfernen | Aufnahme › Agent-Einladungen |
| ✅ | GET | `/releases` | Team | Release-Liste | Releases |
| ✅ | GET | `/releases/feed` | Team | Feed-Status (GitHub) | Releases › Kopf |
| ✅ | POST | `/releases` | Commander | Release per Manifest | Releases › „Manifest registrieren“ |
| ✅ | PUT | `/releases/nodes/{id}` | Commander | Release pro Node | Releases › Zuweisung |
| ✅ | PUT | `/releases/nodes/{id}/channel` | Commander | Kanal pro Node | Releases › Zuweisung |
| ➖ | GET | `/releases/pending` | Agent | – | – |
| ➖ | POST | `/nodes/enroll`, `/nodes/heartbeat`, `/nodes/telemetry`, GET `/nodes/me` | Agent | Agenten-Protokoll | – |

## Beta-Tester-Sicht (Kurzfassung)

Sichtbar und aktiv: Lesen aller Bereiche außer Konten, Chat schreiben, Pairing-Link freigeben, eigenes Passwort/Telegram (nur mit persönlichem Konto).
Ausgeblendet oder sichtbar gesperrt: Löschen, Widerrufen, Codes/Einladungen erstellen, Geräte verwalten (Umbenennen, Gaming Mode, Sensor-Namen, Update-Check, Spiel-Erfassung – alle `manageable_node` → 403), Gruppen/Anordnung, Dualboot, Releases zuweisen/anlegen, Warnregeln/Telegram speichern, Netzwerk-Reset, Spiele bearbeiten, Konten.
