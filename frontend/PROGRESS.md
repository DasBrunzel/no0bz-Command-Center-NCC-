# Arbeitsstand (für die Wiederaufnahme)

Branch: `claude/ncc-frontend-v2`. Diese Datei wird am Ende durch `README.md` ersetzt.

## Erledigt
- Analyse, `API-MATRIX.md`, `DECISIONS.md` (Richtung „Stellwerk“)
- Fundament: Tokens/CSS-Layers, API-Client + Typen, Auth (3 Login-Modi, Pairing-Link, 401-Rückfall), Hash-Router mit View Transitions, Shell, PWA-Gerüst
- Lage (Gleisbild mit Weichen, Störmelder, Live-Verkehr)
- Geräte-Liste (Suche, Filter, Anordnen-Dialog), Hardware-Statistik
- Node-Detail mit Tabs Übersicht, Sensoren, Netzwerk, Spiele, Updates, Verwaltung
- Mock-API (`tests/mock/`) und Mock-Server: `MOCK_PORT=8351 MOCK_ROLE=commander node tests/mock/serve.ts`

## Offen
1. Spiele (Bibliothek, Spielzeit, Banner-Upload/Zuschnitt, SteamGridDB-Link)
2. Chat (Cursor-Pagination, Markdown, Uploads, Teilnehmer)
3. Geräte aufnehmen (Pairings, Agent-Einladungen, Admin-Codes)
4. Releases, Einstellungen (Konto, Konten/Einladungen, Warnregeln, Telegram)
5. Mock: `after`-Cursor für Telemetrie korrekt beantworten
6. PWA-PNG-Icons erzeugen (Playwright-Render aus `public/assets/icons/*.svg`)
7. Playwright-Tests, Screenshots (Lade/Leer/Fehler, mobil), Lighthouse, README, CI (pnpm 12)
