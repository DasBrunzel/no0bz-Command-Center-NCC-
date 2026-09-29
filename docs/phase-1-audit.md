# Phase 1: Bestandsaufnahme für NCC 0.5

Stand: 2026-09-30

## Ziel

Dieser Bericht bewertet NCC 0.4.1 als Ausgangsbasis für den geplanten dauerhaft
laufenden NCC Server. Der Zielzustand trennt Server, Agent, Weboberfläche und
Windows-Integration voneinander.

## Verifizierter Ausgangszustand

- Backend: Python 3.10+, FastAPI, Pydantic und psutil
- Frontend: React 18, TypeScript und Vite
- Speicherung: optional DuckDB, sonst flüchtiger Ringpuffer
- Plattformen: Windows- und Linux-Starter vorhanden
- Betriebsarten: `local`, `server` und `client` in derselben Anwendung
- Kommunikation: REST für Agent-Telemetrie, WebSocket für lokale Live-Daten
- aktuelle semantische Version: `0.4.1`

Die lokale Qualitätsprüfung war erfolgreich:

- 24 von 24 Backend-Tests bestanden
- Ruff ohne Beanstandung
- Mypy ohne Beanstandung
- TypeScript- und Produktions-Build erfolgreich

Der erste Testlauf wurde durch einen nicht beschreibbaren globalen Windows-
Testordner gestört. Mit einem beschreibbaren Projekt-Testordner bestanden alle
Tests. Das war ein Umgebungsproblem und kein fehlgeschlagener NCC-Test.

## Was übernommen werden kann

1. Die Aufteilung in FastAPI-Backend und React-Frontend ist eine geeignete Basis.
2. Die Provider-Abstraktion eignet sich für austauschbare Windows- und
   Linux-Sammler.
3. REST, WebSocket und Pydantic-Modelle können weiterentwickelt werden.
4. Die vorhandenen Sicherheits-Header, Dateinamensprüfung, Rate-Limits und
   Prozess-Schutzliste sind sinnvolle Grundbausteine.
5. Tailscale-Erkennung und plattformbezogene Startskripte liefern verwertbare
   Vorarbeit.
6. Das bestehende Nightmare-Design und die Theme-Variablen können als visuelle
   Grundlage dienen.
7. Tests und GitHub-Actions-Workflows bilden eine gute Ausgangsbasis für die
   weitere Qualitätssicherung.

## Kritische Architekturgrenzen

### Server, Agent und Web sind noch nicht getrennt

Alle Betriebsarten starten dieselbe FastAPI-Anwendung, dieselben lokalen Sammler,
die Speicherung und grundsätzlich auch die Weboberfläche. Ein Client ist daher
noch kein kleiner Hintergrund-Agent, und der Server ist noch kein eigenständiger
zentraler Dienst.

### Geräteverwaltung ist flüchtig

Registrierte Geräte werden nur in einem Python-Wörterbuch gehalten. Nach einem
Serverneustart sind Registrierung, letzter Kontakt und Profilinformationen
verloren. Es gibt keine dauerhafte Geräteidentität und keinen Freigabeprozess.

### Ein gemeinsamer Token für alles

Browser, Server und alle Agenten verwenden denselben statischen Token. Dadurch
kann ein verlorener Client-Token nicht einzeln gesperrt werden. Es fehlen
Benutzerkonten, Rollen, individuelle Agent-Schlüssel, Ablaufdaten und ein
vollständiges Audit der Anmeldungen.

Der WebSocket übergibt den Token außerdem als URL-Parameter. Für die Zielarchitektur
soll die Browseranmeldung über eine Sitzung erfolgen; Agenten erhalten jeweils
eigene, nur einmal sichtbare Tokens.

### Live-Daten zeigen nur den lokalen Server

`/ws/live` sendet ausschließlich den lokalen Snapshot des Prozesses. Remote-Nodes
werden zwar registriert und in `/api/nodes` aufgeführt, können aber nicht als
eigener Live-Datenstrom ausgewählt werden. Die Historie mischt lokale und entfernte
Punkte ohne verpflichtenden Node-Filter.

### Speicherung ist für den Zielbetrieb nicht ausreichend

DuckDB ist nur optional installiert. Ohne diese Abhängigkeit liegt die Historie
ausschließlich im Arbeitsspeicher und verschwindet beim Neustart. Benutzer,
Geräte, Tokens, Alarme und Aufträge besitzen überhaupt kein dauerhaftes Modell.

Für NCC 0.5 wird PostgreSQL als zentrale Betriebsdatenbank empfohlen. DuckDB kann
später optional für Exporte oder analytische Archive erhalten bleiben.

### Noch kein sicherer Auftragskanal

Es gibt noch keine dauerhafte Queue für Verwaltungsaufträge, keine
Ergebnisübermittlung, keine Rollenprüfung und keine kontrollierte PowerShell-
Schnittstelle. Der vorhandene Prozess-Kill wirkt nur auf den Rechner, auf dem die
Webanwendung läuft.

## Befunde zur Hardwareerfassung

### CPU

Die aktuelle Windows-Registry-Abfrage liefert auf dem geprüften Rechner korrekt:

`AMD Ryzen 7 5700X 8-Core Processor`

Der frühere generische AMD64-Name ist damit lokal behoben. Der neue Agent benötigt
trotzdem automatisierte Tests für Windows und Linux sowie eine klar erkennbare
Fallback-Anzeige.

### Windows-GPU

Die Adapterbezeichnung wird herstellerunabhängig aus Windows gelesen. Die
Auslastung stammt jedoch aus einem PowerShell-Aufruf der Windows Performance
Counter bei nahezu jedem Erfassungszyklus. Aktuell werden alle positiven GPU-
Engine-Werte summiert und derselbe Gesamtwert jedem gefundenen Adapter zugewiesen.
Das kann Werte überzeichnen und kann mehrere GPUs nicht korrekt unterscheiden.

Bei NVIDIA überschreibt NVML anschließend diese Daten mit genaueren Werten. Für
AMD und Intel fehlen in diesem Fallback VRAM-Belegung und Temperatur. Für NCC 0.5
brauchen Windows-GPUs eine dauerhafte, adapterbezogene Zuordnung der Performance-
Counter; Herstellerwerkzeuge bleiben optionale Ergänzungen.

### Netzwerk

Die erste Messung ist konstruktionsbedingt null, weil noch kein vorheriger
Zählerstand existiert. Danach wird die Rate aus Zählerdifferenzen berechnet und
geglättet. Auf dem geprüften Rechner lieferte eine zweite Messung plausible Werte.

Der Sammler wählt aber nur eine aktive Schnittstelle anhand der seit dem Start
insgesamt übertragenen Bytes. Das ist für Ethernet, WLAN, virtuelle Adapter und
Tailscale nicht zuverlässig genug. Die neue Version soll alle Schnittstellen
erfassen, virtuelle Adapter kennzeichnen und zusätzlich eine konfigurierbare
Hauptschnittstelle bestimmen.

### Datenträger

Auch Datenträgerraten benötigen zwei Messpunkte. Unter Windows wird ein
Laufwerksbuchstabe einem physischen Datenträger zugeordnet. Teilen mehrere Volumes
denselben physischen Datenträger, kann dessen gesamte I/O-Rate auf mehreren
Laufwerkskacheln erscheinen. Volume-Belegung und physische Geräte-I/O müssen daher
in der neuen Datenstruktur getrennt werden.

### Provider-Ausführung

Die Provider besitzen zwar einen Thread-Pool, werden aktuell aber nacheinander
eingereicht und sofort abgewartet. Mehrere langsame Provider können deshalb einen
Messzyklus verlängern. Provider-spezifische Intervalle, etwa für SMART, sind zwar
teilweise deklariert, werden vom Registry-Ablauf aber noch nicht ausgewertet.

NCC 0.5 soll schnelle Zähler, langsame Hardwareabfragen und statische
Inventardaten getrennt planen.

## Befunde zur Weboberfläche

- Neun Themes und zentrale CSS-Variablen sind bereits vorhanden.
- Das Frontend ist produktiv baubar, aber die Hauptkomponenten sind stark
  verdichtet und müssen vor größeren Erweiterungen aufgeteilt werden.
- Die Oberfläche ist noch auf den lokalen Snapshot ausgerichtet.
- Die Quick-Stats-Zeile `Disks Read` zeigt derzeit einen Netzwerkwert.
- Die Node-Ansicht nennt Port 8351, während die Anwendung Port 8350 verwendet.
- Benutzerbezogene Layouts, Alarmansicht, Rechte und dauerhaft gespeicherte
  Einstellungen fehlen.

## Sicherheits- und Betriebsbefunde

1. HTTPS wird erwartet, aber nicht vom Programm selbst eingerichtet.
2. Einige lesende API-Endpunkte sind im Servermodus ohne Anmeldung erreichbar.
3. Node-IDs basieren auf Hostnamen und sind mit dem gemeinsamen Token nachbildbar.
4. Registrierungs- und Telemetrie-Node-ID werden noch nicht an eine dauerhaft
   bekannte Geräteidentität gebunden.
5. Eine Trennung zwischen Webbenutzer, Agent und Administrator existiert nicht.
6. Das Frontend nutzt teilweise `latest`-Abhängigkeiten; reproduzierbare Builds
   sollten feste, kontrolliert aktualisierte Versionen verwenden.
7. Die Docker-Datenablage und der tatsächliche Pfad der DuckDB-Datei sind nicht
   konsistent aufeinander abgestimmt.

## Prioritäten für NCC 0.5

### P0 – Fundament

- Server, Agent und Web logisch sowie paketbezogen trennen
- versionierte API unter `/api/v1`
- PostgreSQL-Datenmodell und Migrationen
- individuelle Geräteidentität und Agent-Tokens
- Browseranmeldung mit Rollen
- persistente Node-Registrierung und Heartbeats
- nodebezogene Live- und Verlaufsdaten
- Windows-Dienst für den Server

### P1 – Verlässliche Messwerte

- adapterbezogene Windows-GPU-Erfassung für AMD, Intel und NVIDIA
- getrennte Modelle für Volumes und physische Laufwerke
- Messwerte pro Netzwerkschnittstelle
- Warm-up-Status statt irreführender Nullwerte
- unabhängige Erfassungsintervalle und parallele Provider-Ausführung
- Offline-Puffer im Agenten

### P2 – Bedienung und Automatisierung

- moderne, komponentenbasierte Fleet-Oberfläche
- Alarmregeln und Benachrichtigungen
- sichere Auftragsqueue
- erlaubnisbasierter PowerShell-Adapter
- Agent-Updates und Diagnosepakete
- Linux-systemd-Paketierung

## Vorgeschlagene Versionsfolge

- `0.5.0-alpha.1`: Server-Grundgerüst, PostgreSQL und Migrationen
- `0.5.0-alpha.2`: Geräteaufnahme, individuelle Tokens und Heartbeats
- `0.5.0-alpha.3`: Windows-/Linux-Agent und Offline-Puffer
- `0.5.0-beta.1`: neue Fleet-Weboberfläche und Themes
- `0.5.0-beta.2`: Windows-Dienst, Installer und Tailscale-Betriebstest
- `0.5.0`: stabilisierte erste Server-/Agent-Version

## Git-Ausgangslage

Das GitHub-Repository besitzt auf `main` bereits 23 Commits. Der geprüfte Stand
`0.4.1` ist damit als Ausgangspunkt vorhanden. Davon wurde auf GitHub der Branch
`codex/ncc-v0.5-foundation` abgezweigt; `main` blieb unverändert.

Das `.git`-Verzeichnis im lokalen Arbeitsordner ist in der aktuellen geschützten
Arbeitsumgebung nicht beschreibbar und enthält keine nutzbare lokale Historie oder
Remote-Verknüpfung. Die weitere Versionsführung erfolgt deshalb zunächst auf dem
GitHub-Branch. Lokale Quell- und Laufzeitdateien bleiben davon unberührt.

## Abschluss von Phase 1

Die technische Bestandsaufnahme ist abgeschlossen. Der Ausgangsstand auf `main`
ist gesichert und der Entwicklungsbranch `codex/ncc-v0.5-foundation` ist
vorhanden. Als nächster Entwicklungsschritt kann `0.5.0-alpha.1` beginnen.
