# Entscheidungen – NCC Frontend v2

Format: Entscheidung · Begründung · verworfene Alternativen. Neueste Ergänzungen stehen am Ende des jeweiligen Abschnitts.

## 1. Gestaltung: drei Richtungen

### A · „Stellwerk“ (gewählt)

- **Stimmung:** Du sitzt am Stelltisch deiner eigenen kleinen Bahn – jedes Gerät ist ein Gleisabschnitt, jede Lampe sagt sofort, was los ist.
- **Typografie:** *Barlow Condensed* (600/700) für Überschriften, Zahlen im Kopf und Beschriftungen auf dem Gleisbild, *Barlow* (400–600) für Fließtext und Tabellen. Beide stammen aus derselben Familie, angelehnt an Verkehrsbeschilderung (DIN-Nähe), unterscheiden sich klar über die Breite. Tabellen und Messwerte mit `tabular-nums`. Codes und Tokens in `ui-monospace`, nur dort, wo man Zeichen abtippen muss.
- **Farbpalette (OKLCH):** Emaille-Tafel `oklch(93% .012 145)` als Fläche, Schiefer-Tinte `oklch(26% .03 255)` für Text und Gleise, vier Signallampen mit fester Bedeutung: Fahrt-Grün `oklch(62% .17 145)` = online, Signalgelb `oklch(78% .16 75)` = Warnung, Halt-Rot `oklch(58% .21 28)` = kritisch, Rangier-Blau `oklch(55% .17 262)` = Gaming Mode. Dunkle Variante „Nachtschicht“ mit eigenen Stufen statt Invertierung.
- **Layout-Idee:** Links ein schmaler Stelltisch mit den Bereichen, oben eine Meldeleiste (Verbindung, Warnungen, Serverzeit). Die Lage zeigt ein echtes Gleisbild: jede Fleet-Gruppe ist ein Gleis, jedes Gerät ein Block mit Lampe, Last und Namen. Ein Dualboot-PC ist eine **Weiche**: zwei OS-Profile zweigen von einem physischen Gerät ab, der aktive Strang leuchtet.
- **Motion:** Lampen glühen wie Glühlampen kurz auf und ab (`@property --glow`), Messbalken laufen weich auf neue Werte, der Wechsel von der Liste ins Detail ist ein View-Transition-Morph des Geräteblocks. Sonst Ruhe.
- **Das eine Detail:** die Weiche – Dualboot als Gleisweiche, deren gestellter Strang anzeigt, welches Betriebssystem gerade läuft.

### B · „LAN-Party-Zine“

- **Stimmung:** Ein fotokopiertes Heft vom letzten LAN-Wochenende, voller Insider und Bestenlisten.
- **Typografie:** *Rubik Mono One* als laute Display-Schrift, *Atkinson Hyperlegible* für Text.
- **Farbpalette:** reinweißes Papier, zwei Riso-Farben (Fluo-Pink, Federal Blue), Überdruck-Mischton.
- **Layout-Idee:** Magazin-Doppelseiten, Spielzeit als Titelstory, Geräte als „Teilnehmerliste“.
- **Motion:** Stempel-Effekt beim Erscheinen, leichte Passer-Verschiebung bei Hover.
- **Das eine Detail:** Fehlpasser (Misregistration) auf Gerätenamen.
- **Verworfen, weil:** Telemetrie, Sensoren und Tabellen leiden unter Halbton und Überdruck; Fluo-Pink trägt keine Statussemantik, und die Ästhetik verbraucht sich nach dem dritten Besuch.

### C · „Leiterplatte“

- **Stimmung:** Die Fleet als bestückte Platine – Geräte sind Bauteile, Daten fließen über Leiterbahnen.
- **Typografie:** *Chakra Petch* für Bestückungsdruck, *IBM Plex Sans* für Text.
- **Farbpalette:** Lötstopplack Dunkelblau, Bestückungsdruck-Weiß, ENIG-Gold als Akzent.
- **Layout-Idee:** Gerätekarten als ICs mit Pins, Verbindungen als Bahnen.
- **Motion:** Signale wandern als Lichtpunkte über Leiterbahnen.
- **Das eine Detail:** animierte Leiterbahn vom Gerät zur Meldeleiste.
- **Verworfen, weil:** sie zwangsläufig im „dunklen Dashboard mit Leuchteffekten“ landet, das ausdrücklich vermieden werden soll, und Dualboot/Gaming-Mode keine natürliche Entsprechung haben.

### Wahl und Begründung

**„Stellwerk“.** Ein Stellwerk ist ein Ort, der für genau das gebaut wurde, was NCC tun soll: viele Zustände auf einen Blick erfassbar machen, Fehler sofort sichtbar, ohne Lärm. Die Metapher bildet die NCC-Begriffe sauber ab (Lampe = Zustand, Gleis = Gruppe, Weiche = Dualboot, Störmelder = Warnungen, Rangierbetrieb = Gaming Mode) und bleibt dabei persönlich und verspielt. Die helle Emaille-Fläche ist bewusst das Gegenteil des alten dunklen Mint-Designs.

Selbstprüfung gegen Template-Defaults und was ich daraufhin geändert habe:
- Ursprünglich war ein warmes Cremeweiß als Tafel geplant → durch kühles, leicht grünliches Emaille-Grau ersetzt (Creme + Serif ist ein bekanntes Generator-Muster und passt nicht zu Stellwerks-Emaille).
- Monospace für alle kleinen Datenlabels wäre ein Default → nur noch für abtippbare Codes.
- Versal-Labels über jeder Überschrift → gestrichen; Beschriftungen stehen in normaler Schreibweise, Gleis- und Blocknamen sind das einzige Kondensierte.
- Ein Karten-Raster für Geräte → ersetzt durch das Gleisbild (Lage) und eine dichte Tabelle (Geräte).

## 2. Technik

| # | Entscheidung | Begründung | Verworfen |
|---|---|---|---|
| D-01 | React 19.3, TypeScript 7.0 (nativer Compiler), Vite 8.3, `@vitejs/plugin-react` 6.2 | jeweils neueste stabile Major-Version laut `pnpm view` (Stand 2026-11-07) | – |
| D-02 | **TanStack Query 5** als Datenlayer | Polling mit `refetchInterval`, pausiert automatisch bei verstecktem Tab (`refetchIntervalInBackground: false`), alte Daten bleiben bis neue da sind, Mutationen mit Invalidierung | SWR (weniger Mutationskomfort), Eigenbau (unnötig) |
| D-03 | **Eigener Hash-Router** (~80 Zeilen) statt TanStack Router | FastAPI liefert nur `/` als `index.html` aus; tiefe Pfade wie `/geraete/x` würden 404 liefern. Hash-Routen funktionieren ohne Backend-Änderung. Der Router stößt View Transitions selbst an. | TanStack Router (würde Hash-History ebenso brauchen, +40 kB für 7 Routen) |
| D-04 | Routen: `#/` Lage, `#/geraete`, `#/geraete/<id>`, `#/hardware`, `#/spiele`, `#/chat`, `#/aufnahme`, `#/releases`, `#/einstellungen/<tab>` | Bereiche folgen den Aufgaben, nicht den Endpoints | – |
| D-05 | Styling: **reines CSS** mit Cascade Layers (`reset, tokens, base, components, features, utilities`), Nesting, OKLCH, `color-mix()`, `@property`, Container Queries | keine Laufzeit, keine Build-Abhängigkeit, Plattform-Features direkt nutzbar | Tailwind (altes Design nutzte es; Utility-Klassen passen schlecht zu `@property`/Layers) |
| D-06 | Charts als **eigene SVG-Komponenten** (Sparkline, Fläche, Säulen, Heatmap), lazy pro Bereich | vier einfache Formen, volle Kontrolle über Marks nach dataviz-Regeln, 0 kB Bibliothek | Recharts/visx/uPlot (40–100 kB für vier Formen) |
| D-07 | Animationen ausschließlich CSS (View Transitions, `@starting-style`, Scroll-driven Animations, `@property`) | Plattform statt Bibliothek; `prefers-reduced-motion` greift zentral | Motion/Framer (≈ 40 kB) |
| D-08 | Markdown im Chat: `react-markdown` + `remark-gfm`, nur im lazy Chat-Chunk | sicher (kein `dangerouslySetInnerHTML`), GFM für Tabellen/Listen | marked + DOMPurify (zwei Pakete, HTML-Pfad) |
| D-09 | Schriften selbst gehostet über `@fontsource/barlow` und `@fontsource/barlow-condensed`, nur benötigte Schnitte, `font-display: swap` | offline verfügbar, keine Drittanbieter-Anfrage | Google Fonts CDN (bricht Offline-Shell, Datenschutz) |
| D-10 | Icons als kleiner eigener SVG-Satz | ~25 Symbole, alles im Stil der Stellwerks-Piktogramme | lucide-react (wurde im alten Frontend genutzt) |
| D-11 | Dashboard-Token-Fallback nur **im Speicher** (Modulvariable), eingebbar unter „Alte Installation?“ im Login | Vorgabe: keine Secrets in `localStorage`. Nach Neuladen muss der Token erneut eingegeben werden; Cookie-Login ist der Normalfall | `sessionStorage` (ebenfalls Web Storage, würde XSS-lesbar bleiben) |
| D-12 | 401-Behandlung: zentraler Fehlertyp `ApiError`; jede 401 außerhalb der Login-Requests setzt den Auth-Status auf „abgemeldet“, leert den Query-Cache und stoppt alles Polling (Queries sind `enabled` nur im angemeldeten Zustand) → keine Schleife | ein einziger Ort entscheidet über die Abmeldung | Retry-on-401 (Endlosschleifen-Risiko) |
| D-13 | Rechte im UI über einen `useCan()`-Hook mit den Fähigkeiten aus `API-MATRIX.md` (commander, team, manage(node)) | eine Quelle der Wahrheit, testbar | verstreute Rollenvergleiche |
| D-14 | Es gibt eine dritte Rolle **Freund** (`friend`, aus `auth.py`/`access.py`): sieht nur eigene Geräte, verwaltet sie selbst. Das UI blendet für Freunde Aufnahme, Releases, Konten und Server-Telegram aus | der Brief nennt nur Commander/Beta-Tester, das Backend kennt drei Rollen; Registrierung per Einladung erzeugt immer Freunde | Freunde wie Beta-Tester behandeln (würde 403 und fremde Geräte-Links erzeugen) |
| D-15 | Beta-Tester sehen Verwaltungsaktionen **gesperrt mit Hinweis** (z. B. Gaming Mode, Kanal, Release), Aktionen ohne Lesewert (Code erstellen, Widerrufen, Anordnen) sind **ausgeblendet** | gesperrte Schalter erklären, warum etwas nicht geht; reine Schreibformulare sind nur Rauschen | alles ausblenden (Beta-Tester würden Funktionen nicht kennen) |
| D-16 | Pairing-Freigabe in der Liste nur für Commander, über den Pairing-Link für jede Rolle | Backend erlaubt `approve` jeder Identität; der Link ist der vorgesehene Weg für Freunde/Beta-Tester, die Liste ist Verwaltung | Freigabe-Button für alle (widerspräche „keine Geräte verwalten“) |
| D-17 | Hardware-Bilder aus `static/assets/hardware/` werden **nicht** übernommen, stattdessen typografische Hersteller-Plaketten (AMD/Intel/NVIDIA) im Emaille-Stil | Produktfotos/Logos Dritter passen nicht zum Stellwerk-Stil und sind lizenzrechtlich heikel; die Plakette ist lesbar und braucht 0 kB | Bilder nach `public/` kopieren |
| D-18 | Chart-Palette: vier Serienfarben in fester Reihenfolge, mit dem dataviz-Validator geprüft (hell gegen `#f2f6f2`, dunkel gegen `#1d242a`: alle Prüfungen bestanden; hell: Orange 2,99:1 Kontrast → Legende + Tabellenansicht vorhanden). Signalfarben sind reserviert und nie Serienfarben | Lesbarkeit und Farbfehlsichtigkeit | – |
| D-19 | Farbmischung (`color-mix`) in **OKLab**, nicht OKLCH | OKLCH interpoliert den Farbton: Signalgelb über dunklem Blau-Grau wurde im Dunkelmodus türkis | – |
| D-20 | TanStack Query **5.106.1** statt 5.107.1 | pnpm 12 lehnt Pakete jünger als ein Tag ab (`minimumReleaseAge`). 5.107.1 erschien am 06.11.2026; statt die Supply-Chain-Regel per Ausnahme zu umgehen, wird die neueste regelkonforme Version derselben Major genutzt | Ausnahme in `pnpm-workspace.yaml` |
| D-21 | Theme-Wahl (Automatisch/Emaille/Nachtschicht) in `localStorage` | reine Darstellungsvorliebe, kein Secret; Zugriff in try/catch | – |
| D-22 | Tests gegen eine **schema-getreue Mock-API** (`tests/mock/api.ts`) per Playwright-Routing; derselbe Mock liefert über `tests/mock/serve.ts` den Build wie FastAPI aus (für Screenshots/Lighthouse) | kein laufendes Backend/Postgres in dieser Umgebung; Rechteprüfungen im Mock folgen `require_*_access` und `manageable_node` | MSW (zusätzliche Abhängigkeit im App-Bundle bzw. Worker) |

## 3. PWA unter den Grenzen des Backends

| # | Entscheidung | Begründung | Verworfen |
|---|---|---|---|
| P-01 | Manifest, Icons und Service Worker liegen unter **`/assets/`** (`frontend/public/assets/…`) | FastAPI liefert außer `/`, `/assets/*` und `/api/*` nichts aus; `/manifest.webmanifest` oder `/sw.js` wären 404 | Dateien im Wurzelverzeichnis (nicht auslieferbar ohne Backend-Änderung) |
| P-02 | Service Worker `/assets/sw.js` mit Scope `/assets/`; ein Build-Plugin legt zusätzlich **`/assets/app.html`** (Kopie von `index.html`) an. Das Manifest startet die installierte App unter `/assets/app.html` | Ein SW darf nur Seiten unterhalb seines eigenen Pfads steuern (ohne `Service-Worker-Allowed`-Header). So läuft die installierte App vollständig offline-fähig, ohne das Backend anzufassen. Die normale Seite `/` bleibt unverändert und registriert den SW trotzdem (er cached dann die Assets vor) | Workbox/vite-plugin-pwa (setzt `/sw.js` im Root voraus) |
| P-03 | SW-Strategie: App-Shell (`app.html`, JS/CSS/Fonts/Icons) precache mit Build-Hash-Liste; API-Requests werden **nie** gecacht (Telemetrie soll nicht veralten, Antworten tragen `no-store`) | Offline zeigt die Shell den Zustand „Server nicht erreichbar“ statt einer Browser-Fehlerseite | Stale-while-revalidate für API (würde veraltete Lage als aktuell zeigen) |
| P-04 | App-Badge über `navigator.setAppBadge(aktiveWarnungen)`, wenn verfügbar | Progressive Enhancement; ohne API passiert nichts | – |

**Geprüft:** `tests/pwa.spec.ts` installiert den Service Worker, schaltet das Netz ab und lädt `/assets/app.html` neu – die Shell erscheint mit „Server nicht erreichbar“.

**Vorschlag ans Backend:** Ein `GET /sw.js` (oder der Header `Service-Worker-Allowed: /` auf `/assets/sw.js`) plus eine SPA-Fallback-Route würden `app.html` und Hash-Routing überflüssig machen.

## 4. Browser-Unterstützung und Fallbacks

| Feature | Einsatz | Fallback |
|---|---|---|
| View Transitions | Routenwechsel, Geräteblock → Detailkopf (`view-transition-name` je Node) | ohne API sofortiger Wechsel |
| `@starting-style`, `transition-behavior: allow-discrete` | Dialoge, Popover, Toasts, Störmelder-Kacheln, Chat-Nachrichten | ohne Unterstützung ohne Einblendung |
| Scroll-driven Animations | Schatten der Meldeleiste beim Scrollen | ohne Unterstützung kein Schatten |
| Container Queries | Blöcke im Gleisbild, Messkacheln, Tabellen-Spalten, Rangliste | – (alle Zielbrowser) |
| `@property` | `--glow` der Lampen, `--value` der Messbalken (weich animierte Live-Werte) | Sprung statt Übergang |
| Popover API + Anchor Positioning | Menüs (Gaming Mode, Mehr), Warnungs-Popover | ohne Anchor Positioning zentriert der Browser das Popover (UA-Standard) |
| `<dialog>` | alle Dialoge, Klick auf Hintergrund schließt | – |
| `light-dark()`, OKLCH, `color-mix()` | Token-System | – (alle Zielbrowser seit 2024) |
| `appearance: base-select`, `field-sizing: content`, `interpolate-size` | Selects, Chat-Eingabe, Ausklapp-Höhen | normale Selects/Textareas |
| Badging API | Zahl aktiver Warnungen am App-Symbol | nichts |
| `prefers-reduced-motion` | setzt alle Motion-Tokens auf 0 ms, deaktiviert View Transitions und Blinken | – |

## 5. Lighthouse (13.6.0, gegen `tests/mock/serve.ts`, Commander-Sitzung)

| Seite | Performance | Barrierefreiheit | Best Practices | SEO |
|---|---|---|---|---|
| Lage, Desktop | 100 | 100 | 100 | 100 |
| Spiele, Hardware, Desktop | 98–100 | 100 | 100 | 100 |
| 13 weitere Ansichten (A11y/Best Practices) | – | 100 | 100 | – |
| Lage, Mobil (ohne Kompression, wie FastAPI heute) | **83** | 100 | 100 | 100 |
| Lage, Mobil (mit gzip) | 94 | 100 | 100 | 100 |

**Begründete Abweichung:** Mobil bleibt Performance ohne Kompression unter 90. Ursache ist allein das LCP (4,7 s im simulierten langsamen 4G): FastAPIs `StaticFiles` liefert JS/CSS unkomprimiert aus (≈ 296 kB statt 92 kB für das Haupt-Bundle, davon ≈ 70 % React). Bereits umgesetzt: Code-Splitting pro Bereich, Lazy Loading von Charts/Markdown/Tabs, `modulepreload` für die Lage, Font-Preload, paralleles Vorladen der Lage-Daten während der Sitzungsprüfung, CLS 0. Mit gzip-Auslieferung (gemessen über `MOCK_GZIP=1`) erreicht dieselbe Seite 94. **Vorschlag ans Backend:** `app.add_middleware(GZipMiddleware, minimum_size=1024)` in `app.py`.

## 6. API-Vorschläge (nicht umgesetzt, Backend bleibt unverändert)

- **Kompression** statischer Dateien (siehe Abschnitt 5).

- **Beta-Tester und Gaming Mode:** `manageable_node` lehnt Beta-Tester ab; sie sehen den Schalter daher gesperrt. Falls gewünscht, bräuchte es eine eigene Prüfung.
- **Kein Endpoint für ausstehende Pairings abbrechen** (`cancelled` existiert als Status, aber keine Route). Das UI bietet daher kein „Ablehnen“ an.
- **SteamGridDB-Suche:** Der Server sucht Banner nur automatisch (mit API-Key). Es gibt keinen Endpoint für eine manuelle Suche. Das UI verlinkt deshalb die SteamGridDB-Suche zum Spiel in einem neuen Tab; das gefundene Bild wird über den Upload zugeschnitten und hochgeladen.
- **Benutzer löschen:** existiert nicht; „Deaktivieren“ über `PATCH active=false`.
- **Agent-Einladung Rolle:** `AgentInvitationCreateRequest` kennt keine Rolle; neue Agenten starten mit der Server-Vorgabe.
- **Live-Netzwerk der ganzen Fleet:** kein Sammel-Endpoint. Das UI summiert die `latest.metrics.network`-Werte aus `/fleet/nodes` und hält einen kurzen Verlauf im Speicher.
- `/fleet/games/stats` und `/fleet/hardware/stats` haben kein `response_model`; die Typen im Frontend sind aus `game_service.playtime_statistics` und `hardware_stats.hardware_statistics` abgeleitet.
