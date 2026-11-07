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
| D-15 | Beta-Tester sehen Verwaltungsaktionen **gesperrt mit Hinweis** (z. B. Kanal, Release, Spiel-Erfassung; den Gaming Mode dürfen sie ab 0.7), Aktionen ohne Lesewert (Code erstellen, Widerrufen, Anordnen) sind **ausgeblendet** | gesperrte Schalter erklären, warum etwas nicht geht; reine Schreibformulare sind nur Rauschen | alles ausblenden (Beta-Tester würden Funktionen nicht kennen) |
| D-16 | Pairing-Freigabe in der Liste nur für Commander, über den Pairing-Link für jede Rolle | Backend erlaubt `approve` jeder Identität; der Link ist der vorgesehene Weg für Freunde/Beta-Tester, die Liste ist Verwaltung | Freigabe-Button für alle (widerspräche „keine Geräte verwalten“) |
| D-17 | Hardware-Bilder aus `static/assets/hardware/` werden **nicht** übernommen, stattdessen typografische Hersteller-Plaketten (AMD/Intel/NVIDIA) im Emaille-Stil | Produktfotos/Logos Dritter passen nicht zum Stellwerk-Stil und sind lizenzrechtlich heikel; die Plakette ist lesbar und braucht 0 kB | Bilder nach `public/` kopieren |
| D-18 | Chart-Palette: vier Serienfarben in fester Reihenfolge, mit dem dataviz-Validator geprüft (hell gegen `#f2f6f2`, dunkel gegen `#1d242a`: alle Prüfungen bestanden; hell: Orange 2,99:1 Kontrast → Legende + Tabellenansicht vorhanden). Signalfarben sind reserviert und nie Serienfarben | Lesbarkeit und Farbfehlsichtigkeit | – |
| D-19 | Farbmischung (`color-mix`) in **OKLab**, nicht OKLCH | OKLCH interpoliert den Farbton: Signalgelb über dunklem Blau-Grau wurde im Dunkelmodus türkis | – |
| D-20 | TanStack Query **5.106.1** statt 5.107.1 | pnpm 12 lehnt Pakete jünger als ein Tag ab (`minimumReleaseAge`). 5.107.1 erschien am 06.11.2026; statt die Supply-Chain-Regel per Ausnahme zu umgehen, wird die neueste regelkonforme Version derselben Major genutzt | Ausnahme in `pnpm-workspace.yaml` |
| D-21 | Theme-Wahl (Automatisch/Emaille/Nachtschicht) in `localStorage` | reine Darstellungsvorliebe, kein Secret; Zugriff in try/catch | – |
| D-22 | Tests gegen eine **schema-getreue Mock-API** (`tests/mock/api.ts`) per Playwright-Routing; derselbe Mock liefert über `tests/mock/serve.ts` den Build wie FastAPI aus (für Screenshots/Lighthouse) | kein laufendes Backend/Postgres in dieser Umgebung; Rechteprüfungen im Mock folgen `require_*_access` und `manageable_node` | MSW (zusätzliche Abhängigkeit im App-Bundle bzw. Worker) |

## 3. PWA

| # | Entscheidung | Begründung | Verworfen |
|---|---|---|---|
| P-01 | Service Worker unter **`/sw.js`** mit Scope `/`, vom Server ausgeliefert (`app.py`, ab 0.7) mit `Cache-Control: no-cache`; Manifest und Icons unter `/assets/` | ein Worker im Wurzelpfad steuert das ganze Dashboard; `no-cache` sorgt dafür, dass ein neuer Worker nach einem Update sofort ankommt | `/assets/sw.js` + `/assets/app.html` als Startseite (Zwischenstand vor 0.7, solange das Backend nichts im Root auslieferte; ältere Registrierungen unter `/assets/` meldet `pwa.ts` ab) |
| P-02 | Ein Build-Plugin schreibt die Precache-Liste (`/` und alle Assets) und einen Inhalts-Hash in `sw.js` | jede Version hat ihren eigenen Cache, alte werden beim Aktivieren gelöscht | Workbox (schwere Abhängigkeit für 60 Zeilen) |
| P-03 | Strategie: Seite network-first mit Offline-Kopie, gehashte Assets cache-first, `/api/` **nie** gecacht | Offline zeigt die Shell „Server nicht erreichbar“ statt einer Browser-Fehlerseite; Telemetrie veraltet nie unbemerkt | Stale-while-revalidate für API |
| P-04 | App-Badge über `navigator.setAppBadge(aktiveWarnungen)`, wenn verfügbar | Progressive Enhancement | – |
| P-05 | Hash-Routing bleibt | funktioniert ohne SPA-Fallback-Route und mit Lesezeichen aus allen Versionen | Pfad-Routing mit Catch-all im Backend (kein Mehrwert für ein internes Dashboard) |

**Geprüft:** `tests/pwa.spec.ts` (Mock) installiert den Worker, schaltet das Netz ab und lädt `/` neu – die Shell erscheint mit „Server nicht erreichbar“. `tests/live.spec.ts` prüft gegen den echten Server, dass `/sw.js` aktiv wird.

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
| Lage, Mobil (mit gzip, Server ab 0.7) | 94 | 100 | 100 | 100 |
| Lage, Mobil (ohne Kompression, Server bis 0.6) | 83 | 100 | 100 | 100 |

Die Abweichung vor 0.7 lag allein am LCP: FastAPIs `StaticFiles` lieferte JS/CSS unkomprimiert (≈ 296 kB statt 91 kB). Seit 0.7 komprimiert `DashboardGZipMiddleware` die Dashboard-Dateien; der echte Server liefert das Haupt-Bundle mit 91 kB aus (per `curl` geprüft). Außerdem umgesetzt: Code-Splitting pro Bereich, Lazy Loading von Charts/Markdown/Tabs, `modulepreload` für die Lage, Font-Preload, paralleles Vorladen der Lage-Daten während der Sitzungsprüfung, CLS 0.

## 6. Backend-Änderungen in 0.7

Umgesetzt nach Abnahme der Vorschläge (Tests: `tests/test_dashboard_v2_server.py`):

| Änderung | Entscheidung |
|---|---|
| gzip | nur für Dashboard-Dateien (`/`, `/assets/*`, `/sw.js`). API-Antworten bleiben unkomprimiert: einige tragen Einmal-Tokens neben Anfragedaten (BREACH-artige Angriffe), und kleine JSON-Antworten gewinnen kaum |
| `/sw.js` | eigene Route, `no-cache` |
| `index.html` | jetzt mit `Cache-Control: no-cache`. Beim Test gegen den echten Server zeigte der Browser nach einem Neubau die alte Seite aus seinem Heuristik-Cache – nach einem Update hätte sie auf gelöschte Assets gezeigt |
| Pairing ablehnen | `POST /agent-pairings/{id}/cancel`, nur Commander. Eine abgelehnte Anfrage bleibt eine Anfragedauer (15 min) gesperrt und kann nicht mehr freigegeben werden; danach darf der Agent neu anfragen. Eine dauerhafte Sperre hätte Geräte nach einem Fehlklick unbrauchbar gemacht, weil der Agent seine Pairing-ID behält |
| SteamGridDB-Suche | Server sucht, liefert Vorschau und Banner selbst (CSP `img-src 'self'` bleibt unverändert); Kandidaten-URLs bleiben 15 min im Server-Speicher, der Client wählt nur einen Index. Ein gewählter Banner wird wie ein Upload gespeichert (`artwork_source = "upload"`, Audit mit `origin: steamgriddb`) und nie automatisch ersetzt |
| Gaming Mode für Beta-Tester | eigene Prüfung `access.gaming_mode_node`; alle anderen Rechte von `manageable_node` bleiben unverändert |
| Paketdaten | `static/assets/**/*` statt fester Unterordner; sonst hätte das Update auf HorstServer an fehlenden `icons/` abgebrochen |

Nach 0.7.0 umgesetzt (Tests: `tests/test_open_items_api.py`, `frontend/tests/open-items.spec.ts`):

| Änderung | Entscheidung |
|---|---|
| Benutzer löschen | `DELETE /users/{id}`, nur Commander. Das Dashboard bietet Löschen nur für deaktivierte Konten an. Der Server lehnt das eigene Konto, den letzten aktiven Commander und Konten mit Geräten ab (409) – Geräte zuerst umhängen oder vergessen, sonst fielen sie still an den Server-Besitzer. Sitzungen, Telegram-Verknüpfung und Link-Codes werden gelöscht, Chat-Nachrichten behalten den Namen, offene Kopplungen des Freundes werden abgelehnt. Die Bereinigung steht ausdrücklich im Code, weil SQLite die `ON DELETE`-Regeln nicht durchsetzt. Das Audit vermerkt Name und Rolle |
| Agent-Einladung mit Rolle | `access_role` (`commander` oder `beta_tester`, Vorgabe `commander`) im Request und in der Antwort. Die Spalte gab es schon am Token; Enrollment übernimmt sie, keine Migration |
| Gruppen umbenennen | `PATCH /fleet/groups/{id}`, nur Commander. Standardgruppen behalten ihre ID, also auch die Platzierungsregeln (Freunde-Geräte landen weiter in `default-friends`). Ein umbenannter Standardname wird nicht mehr übersetzt, weil `groupLabel` nur Großbuchstaben-Platzhalter ersetzt |
| Live-Netzwerk der Fleet | `GET /fleet/network?minutes=30` (1–360). Pro Bucket (Fensterlänge / 90, mindestens 10 s) wird je Gerät gemittelt und dann addiert, damit häufig meldende Geräte nicht mehrfach zählen. Geladen wird nur das `network`-Fragment der Telemetrie. Der Verlauf ist damit beim ersten Laden da und nicht mehr an die offene Seite gebunden |
| Typen für Statistik | `PlaytimeStatisticsResponse` und `HardwareStatisticsResponse` als `response_model`; die Felder entsprechen genau den bisherigen Dicts, das Frontend musste nichts ändern |

Weiterhin bewusst so gelassen:

- Zeitstempel ohne Zeitzone (SQLite) liest der Client zentral als UTC (`client.ts`, `utcReviver`); Postgres liefert ohnehin `+00:00`.
