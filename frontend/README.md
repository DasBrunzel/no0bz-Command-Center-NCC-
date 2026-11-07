# NCC Dashboard „Stellwerk“ (0.7)

Web-Frontend des no0bz Command Center. React 19, TypeScript 7, Vite 8, TanStack Query 5, reines CSS. Das Backend (`backend/ncc_server`) bleibt unverändert; alle Daten kommen per Polling aus `/api/v1`.

## Start

```bash
pnpm install
pnpm dev          # Vite auf :5173, /api → http://127.0.0.1:8350 (echter NCC-Server)
```

Ohne echten Server: Mock-Server starten und `pnpm dev` dagegen laufen lassen (oder den Build direkt ansehen):

```bash
pnpm build
MOCK_PORT=8350 MOCK_ROLE=commander node tests/mock/serve.ts   # dann http://127.0.0.1:8350
```

`MOCK_ROLE` ist `commander`, `beta_tester`, `friend` oder `none` (Login-Bildschirm). Zugangsdaten für den Mock stehen in `tests/mock/api.ts` (`CREDENTIALS`).

## Build und Prüfungen

```bash
pnpm typecheck    # App und Node-Teil (Vite-Config, Tests)
pnpm build        # schreibt nach ../backend/ncc_server/static (emptyOutDir)
pnpm test         # Playwright, braucht vorher pnpm build
SCREENS=1 pnpm exec playwright test screens   # Screenshots nach test-results/screens
```

FastAPI liefert `index.html` unter `/` (ohne Cache), alles unter `/assets/` und ab Server 0.7 den Service Worker unter `/sw.js`; Dashboard-Dateien kommen gzip-komprimiert. Manifest und Icons liegen in `public/assets/`, der Worker in `public/sw.js` (Details: `DECISIONS.md`, Abschnitt 3).

Vor einem Live-Gang gegen einen echten Server prüfen (CSP, Konsolenfehler, 5xx, Service Worker):

```bash
LIVE_URL=http://127.0.0.1:8350 pnpm exec playwright test live
```

Ohne Loopback-Zugang zusätzlich `LIVE_TOKEN=<Dashboard-Token>` setzen.

## Struktur

```
src/
  api/          client.ts (fetch, Cookie, Fallback-Token, Fehlertexte), endpoints.ts (alle Endpoints, Query-Keys, Polling-Intervalle),
                queries.ts (gemeinsame Hooks), types.ts (aus schemas.py abgeleitet)
  app/          App (Provider, Pairing-Link), auth (Sitzung, 401, Rollen/useCan), Shell (Navigation, Meldeleiste), pwa, theme
  components/   Design-System: Lampe, Meter, Dialog, Menü, Toasts, Zustände, Secret, Charts, Icons
  features/     overview (Lage, Gleisbild, Störmelder, Live-Verkehr) · fleet · node (Detail-Tabs) · hardware · games · chat
                · enrollment (Aufnahme) · releases · settings · login
  lib/          Hash-Router mit View Transitions, Formatierer (de-DE), Node-Helfer
  styles/       tokens.css (Design-Tokens), base, components, charts, shell, utilities – Cascade Layers
tests/          Playwright-Specs, mock/ (schema-getreue Mock-API und Server), tools/ (Icon-Rendering)
```

Routen (Hash, weil FastAPI nur `/` ausliefert): `#/`, `#/geraete`, `#/geraete/<id>?tab=…`, `#/hardware`, `#/spiele`, `#/chat`, `#/aufnahme`, `#/releases`, `#/einstellungen/<tab>`.

## Design-System

Richtung „Stellwerk“: Emaille-Tafel, Schiefer-Tinte, vier Signallampen mit fester Bedeutung. Alle Werte kommen aus `src/styles/tokens.css`:

| Token | Bedeutung |
|---|---|
| `--c-panel`, `--c-panel-raised`, `--c-panel-sunken`, `--c-line*` | Flächen und Linien (hell „Emaille“, dunkel „Nachtschicht“ über `light-dark()`) |
| `--c-ink`, `--c-ink-2`, `--c-ink-3` | Text in drei Stufen |
| `--c-go` / `--c-caution` / `--c-stop` / `--c-shunt` / `--c-unlit` | Online · Warnung · Kritisch · Gaming Mode · Offline – nur für Zustände |
| `--c-*-ink` | dieselben Signale als Textfarbe mit ausreichendem Kontrast |
| `--c-series-1…4`, `--c-seq-*` | Chart-Farben (validiert), nie für Text |
| `--font-display` (Barlow Condensed), `--font-text` (Barlow), `--font-code` | Typografie; Zahlen in Tabellen mit `tabular-nums` |
| `--fs-xs … --fs-5xl` | klassische Größenskala 12–60 px |
| `--s-1 … --s-8` | Abstände im 4-px-Raster |
| `--r-1 … --r-3`, `--r-round` | Radien |
| `--t-fast`, `--t-med`, `--t-slow`, `--t-lamp`, `--ease-*` | Motion; bei `prefers-reduced-motion` alle 0 ms |

Bausteine: `.lamp[data-state]`, `.btn` (`-primary`, `-danger`, `-quiet`, `-s`, `-icon`), `.panel`, `.field`/`.input`/`.select`, `.switch`, `.segmented`, `.tabs`, `.table`, `.meter` (Wert über `--value`), `.badge[data-tone]`, `.dialog`, `.menu` (Popover), `.state` (leer/Fehler), `.secret` (einmalige Anzeige).

## Weiterführend

- `API-MATRIX.md` – jeder Endpoint mit Rolle, Zweck und Ort im UI
- `DECISIONS.md` – Gestaltungsrichtungen, Technikwahl, PWA, Browser-Fallbacks, Lighthouse, API-Vorschläge
