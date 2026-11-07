# NCC 0.7.0 auf HorstServer ausrollen

Server und Dashboard 0.7.0 vom Branch `claude/ncc-frontend-v2`. Agenten, Core und Payload bleiben bei 0.6.2 und müssen nicht angefasst werden.

## Was sich auf dem Server ändert

- Neues Dashboard „Stellwerk“ (statische Dateien in `backend/ncc_server/static`, im Git-Stand gebaut und committet).
- Neue Endpoints: Kopplung ablehnen, SteamGridDB-Bannersuche; Beta-Tester dürfen den Gaming Mode schalten.
- Dashboard-Dateien werden gzip-komprimiert, `index.html` und `/sw.js` ohne Cache ausgeliefert.
- Datenbank: Migration `20261107_0026` (Herkunft von Bannern, nur eine neue Spalte). Sie stammt aus dem letzten Stand des codex-Branches und läuft beim Update automatisch.
- Paketdaten nehmen jetzt alle Unterordner von `static/assets/` mit (vorher fehlte `icons/`).

## Vorher prüfen (auf HorstServer)

1. Repo: `C:\Users\BigHorst\Desktop\ncc`, aktueller Branch `codex/ncc-v0.6-agent-foundation`.
2. `git status` zeigt keine Änderungen außer ggf. unter `backend/ncc_server/static/`.
3. Der Branch `claude/ncc-frontend-v2` ist auf `origin` gepusht (das erledigt HorstPC).

## Update (Admin-PowerShell auf HorstServer)

```powershell
cd C:\Users\BigHorst\Desktop\ncc
git status --short
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\update_ncc_server_release_distribution.ps1 -Branch claude/ncc-frontend-v2
```

Das Skript sichert `server.env` und die Postgres-Datenbank, wechselt auf den Branch, installiert das Paket, prüft jede Dashboard-Datei per Hash, migriert, startet `NccServer` neu und prüft `ready`, `version`, Dashboard und die Release-Route. Am Ende steht ein JSON mit `Result`, `Commit` und `DashboardAssets`.

Hat `git status` geänderte Dateien unter `backend/ncc_server/static/` gezeigt: zuerst `git restore --source=HEAD --worktree -- backend/ncc_server/static` (die alten Dateien sichert `update_ncc_server_dashboard_safe.ps1`, falls du sie behalten willst).

## Danach prüfen

```powershell
$base = 'http://<NCC_SERVER_HOST>:8350'   # Wert aus server.env
(Invoke-WebRequest "$base/api/v1/version" -UseBasicParsing).Content          # {"version":"0.7.0","api":"v1"}
(Invoke-WebRequest "$base/" -UseBasicParsing -Headers @{ 'Accept-Encoding' = 'gzip' }).Headers['Content-Encoding']   # gzip
(Invoke-WebRequest "$base/sw.js" -UseBasicParsing).StatusCode                   # 200
```

Im Browser: Dashboard öffnen, einmal neu laden. Erwartet: Lage mit Gleisbild, alle Geräte, Störmelder. Optional der automatische Rundgang von einem Rechner mit Node/pnpm:

```bash
cd frontend && LIVE_URL=http://<host>:8350 LIVE_TOKEN=<Dashboard-Token> pnpm exec playwright test live
```

## Optional: SteamGridDB-Suche einschalten

Ohne API-Key zeigt der Spiel-Dialog einen Hinweis und verlinkt SteamGridDB. Mit Key (kostenlos unter steamgriddb.com › Preferences › API) in `%ProgramData%\no0bz\NCC\config\server.env`:

```
NCC_SERVER_STEAMGRIDDB_API_KEY=<key>
```

danach `Restart-Service NccServer`.

## Zurück auf den alten Stand

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\update_ncc_server_release_distribution.ps1 -Branch codex/ncc-v0.6-agent-foundation
```

Die Migration `0026` ist rein additiv; der alte Server läuft mit ihr weiter. Die Datenbanksicherung vom Update liegt unter `%ProgramData%\no0bz\NCC\backups` (siehe `backup_ncc_postgres.ps1`).

## Prompt für Claude Code auf HorstServer

In einer **Admin-PowerShell** auf HorstServer im Repo `claude` starten und einfügen:

> Rolle NCC 0.7.0 vom Branch `claude/ncc-frontend-v2` auf diesem Server aus. Lies zuerst `docs/deploy-0.7-horstserver.md` (nach `git fetch origin claude/ncc-frontend-v2` mit `git show origin/claude/ncc-frontend-v2:docs/deploy-0.7-horstserver.md`). Prüfe `git status`; ändere nichts außerhalb von `backend/ncc_server/static/`, ohne mich zu fragen. Führe dann `scripts\update_ncc_server_release_distribution.ps1 -Branch claude/ncc-frontend-v2` aus, zeig mir das JSON-Ergebnis und mach die Prüfungen aus „Danach prüfen“. Bei einem Fehler: nichts reparieren, sondern die Ausgabe zeigen und auf mich warten. Nicht pushen, nicht mergen.
