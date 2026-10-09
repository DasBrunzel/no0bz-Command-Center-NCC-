# Changelog

Alle wesentlichen Änderungen werden hier dokumentiert.

## [Unreleased]

### Fixed

- Der 0.6-Collector führt bei einem kurzzeitig blockierten Sensor bis zu einer
  Minute den letzten gültigen Wert fort, statt fehlende CPU-, RAM- oder GPU-Daten
  als künstliche Nullwerte an das Dashboard zu liefern.
- Der Windows-GPU-Collector verarbeitet fremde Treiberzeichen mit explizitem
  UTF-8-Fallback, sodass ein einzelner nicht decodierbarer Countertext keinen
  Reader-Thread mehr beschädigt.
- Alle für Core-Migration, Rollback und Release-Schlüssel verwendeten
  PowerShell-Skripte sind jetzt ASCII-kompatibel, damit Windows PowerShell 5
  sie unabhängig von der lokalen ANSI-Codepage zuverlässig parst.

### Added

- `initialize_ncc_release_signer.ps1` erstellt einen dauerhaften,
  passphrasengeschützten Ed25519-Release-Signierer mit restriktiven Windows-ACLs
  und gibt ausschließlich dessen öffentlichen Verifikationsschlüssel aus.
- Die Update-Freigabe im Dashboard verwendet bei mehreren kompatiblen Releases
  eine sichtbare Auswahl statt einer manuell einzutippenden Release-ID.

## [0.6.0-beta.1] - 2026-10-08

### Added

- Neuer, noch nicht installierter Rust-Prototyp `ncc-core` für NCC 0.6.
- Sichere Zustandsmaschine für Payload-Staging, Aktivierung, Health-Prüfung und
  automatischen Rollback auf die vorherige Payload-Version.
- SHA-256- und Ed25519-Prüfung für Release-Artefakte; Staging akzeptiert nur
  Signaturen lokal vertrauenswürdiger Public Keys.
- Geheimnisfreier lokaler Health-Vertrag für Payloads sowie ein harmloser
  Test-Payload für künftige Core-/Rollback-Tests.
- Echten, eigenständigen Windows-Telemetrie-Payload für CPU, RAM, GPU,
  Laufwerke und Netzwerk paketiert; der erste Test läuft parallel zum 0.5-Agenten.
- Kontrollierter Windows-Wechsel mit automatischer Rückkehr zum 0.5-Agenten,
  falls der Core nicht gesund startet.
- Signierte Release-Verteilung: Commander registrieren Release-Manifeste,
  wählen pro Gerät Beta oder Stable und geben Updates bewusst je Node frei.
- NccCore lädt ausschließlich explizit freigegebene HTTPS-Artefakte, prüft
  Hash und Ed25519-Signatur gegen lokal installierte öffentliche Schlüssel und
  aktiviert sie bei einem kontrollierten Dienststart.
- Linux/systemd-Installation und isolierter Linux-Core-Migrationstest ergänzt.

### Changed

- Entwicklungszweig und Python-Paketversion auf `0.6.0-beta.1` angehoben.
- NCC 0.5-Server, bestehende Agenten, Pairings und Produktivinstallationen werden
  durch die 0.6-Vorarbeit nicht gestartet, ersetzt oder migriert.

## [0.5.0-beta.70] - 2026-10-08

### Fixed

- Die Traffic-Statistik lädt Geräte jetzt unabhängig. Eine fehlerhafte oder
  vorübergehend nicht erreichbare Geräteabfrage leert nicht mehr die komplette
  Statistikseite.

## [0.5.0-beta.69] - 2026-10-08

### Fixed

- Hotfix für Beta 68: Netzwerkverläufe werden wieder ohne einen zusätzlichen
  Zugriff auf ein nicht vorhandenes `metrics`-Objekt gezeichnet. Das Dashboard
  bleibt dadurch auch nach dem automatischen Telemetrie-Refresh sichtbar.

## [0.5.0-beta.68] - 2026-10-08

### Fixed

- Alle Netzwerkdiagramme lesen Telemetrie wieder korrekt aus `metrics.network`.
  Verläufe für Download und Upload werden dadurch je ausgewähltem Gerät
  angezeigt, statt leer oder mit Nullwerten zu erscheinen.

## [0.5.0-beta.67] - 2026-10-08

### Fixed

- Stabilitätsprüfung vereinheitlicht: der Integrationstest prüft jetzt die
  aktuelle Datenbankmigration `20261007_0015`.
- Strikte Typprüfung für Dashboard-Sitzungen, Agent-Token und Testkonfiguration
  ergänzt; ungültige Geheimnis-Typen werden früh erkannt.
- Alert-Auswertung und Testcode sind bereinigt, sodass Ruff, mypy und die
  Python-Kompilierung ohne Befunde laufen.

## [0.5.0-beta.66] - 2026-10-07

### Added

- Einstellungen enthalten jetzt einen geschützten Telegram-Bereich: Versand
  an-/ausschalten, Überschriften und Fußzeile anpassen sowie eine echte
  Testnachricht senden. Bot-Token und Chat-ID bleiben ausschließlich auf dem
  Server.

## [0.5.0-beta.65] - 2026-10-07

### Changed

- Telegram-Warnungen sind jetzt strukturierte, lesbare Meldungen mit
  Warnstufe, System, Ereignis, Detailtext, Zeitstempel und passender
  Entwarnung. Sonderzeichen in Gerätenamen werden sicher dargestellt.

## [0.5.0-beta.64] - 2026-10-07

### Fixed

- Die Netzwerkstatistik wird nicht mehr durch den fünfsekündlichen Live-Refresh
  abgebrochen. Traffic pro Gerät und der Gesamtverkehr laden unabhängig und
  aktualisieren sich anschließend kontrolliert.

### Added

- Die Verfügbarkeits-Rangliste wird dauerhaft serverseitig erfasst. Sie zeigt
  die beobachtete Verfügbarkeit je System sowie dessen längsten Uptime-Rekord.

## [0.5.0-beta.63] - 2026-10-07

### Fixed

- Ein im Fleet-Dashboard umbenannter Agent behält seinen Namen jetzt dauerhaft.
  Agent-Updates und erneute Anmeldungen aktualisieren nur noch technische
  Metadaten, niemals den gespeicherten Dashboard-Namen.

## [0.5.0-beta.62] - 2026-10-05

### Fixed

- Die tägliche Linux-PostgreSQL-Sicherung verwendet nun eine POSIX-kompatible
  Verarbeitung der Datenbank-URL und läuft dadurch zuverlässig unter systemd.

## [0.5.0-beta.61] - 2026-10-05

### Added

- Linux-Server erhalten einen persistenten, abgeschotteten Datenbereich für
  Chat-Anhänge sowie eine systemd-gestützte PostgreSQL-Sicherung: täglich um
  03:30 Uhr, mit 14 Tagen Aufbewahrung.

## [0.5.0-beta.60] - 2026-10-04

### Changed

- Der aktive Gaming-Modus ist im Fleet Navigator direkt auf der jeweiligen
  Geräte-Kachel sichtbar.
- Die Geräteaktionen – Gaming-Modus, Umbenennen, Rolle und Vergessen – liegen
  nun passend im Kopf der ausgewählten Node statt am Seitenende.

## [0.5.0-beta.59] - 2026-10-04

### Added

- Ein manueller, pro Gerät zeitlich begrenzter **Gaming-Modus** bereitet NCC
  auf die spätere automatische Spielerkennung von NCC 0.6 vor. Während er aktiv
  ist, pausieren ausschließlich CPU- und GPU-Lastwarnungen für das gewählte
  Gerät; Offline-, Temperatur-, Speicher- und sonstige Warnungen bleiben aktiv.

## [0.5.0-beta.58] - 2026-10-03

### Added

- Fleet Chat erkennt nun Bild-, Video-, Audio- und PDF-Anhänge automatisch.
  Bilder und PDFs öffnen sich in einer großen Vorschau mit Download, während
  Videos und Audio direkt im Chat abspielbar sind.

## [0.5.0-beta.57] - 2026-10-03

### Added

- Der neue **Fleet Chat** speichert Nachrichten dauerhaft auf dem NCC-Server.
  Alle Geräte erscheinen automatisch als Chatter; Text, Markdown und Anhänge bis
  100 MiB können zentral geteilt werden.
- Das Warnungszentrum kann aktive Hinweise als erledigt markieren. Bleibt eine
  Ursache bestehen, wird die Warnung durch die normale Prüfung erneut geöffnet.

### Changed

- Warnungszentrum, aktive Prozessliste und Fleet Navigator wurden übersichtlicher
  gestaltet. Der Navigator selbst ist nun ein- und ausklappbar; einzelne Gruppen
  bleiben beim Ausklappen stets sichtbar.

## [0.5.0-beta.56] - 2026-10-03

### Fixed

- Der Agent puffert denselben Hintergrund-Schnappschuss nur noch einmal. Dadurch
  erzeugen langsame oder versetzt laufende Sammler keine fälschliche
  Doppeltelemetrie-Warnung mehr.

## [0.5.0-beta.55] - 2026-10-03

### Fixed

- Die Doppeltelemetrie-Erkennung berücksichtigt nur noch Messungen in echter
  Millisekunden-Nähe. Reguläre, aufeinanderfolgende Windows-Messungen im Abstand
  von einer Sekunde erzeugen damit keine falsche Agent-Gesundheitswarnung mehr.

## [0.5.0-beta.54] - 2026-10-03

### Added

- Serverseitige **Agent-Gesundheitswarnungen** erkennen ohne Zugriff auf das
  Zielgerät ausbleibende Telemetrie, deutlich veraltete Agent-Versionen,
  wiederholte Doppeltelemetrie sowie wiederkehrende unplausible Netzwerkzähler.
- Die Hinweise erscheinen im NCC-Warnungszentrum und werden bei aktivierten
  Benachrichtigungen auch über Telegram versendet.

## [0.5.0-beta.53] - 2026-10-03

### Fixed

- Die Traffic-Plausibilitätsprüfung berücksichtigt zusätzlich die vom Agenten
  gemeldete Live-Up-/Downloadrate. Dadurch werden niedrige Live-Raten nicht mehr
  mit mehrgigabytegroßen Zählerdeltas verrechnet.

## [0.5.0-beta.52] - 2026-10-03

### Fixed

- NCC verwirft nahezu zeitgleiche Telemetriedoppelmeldungen desselben Geräts,
  auch wenn sie unterschiedliche Sample-IDs besitzen.
- Die Monatsverkehrsberechnung ignoriert Zählersprünge oberhalb einer plausiblen
  Netzwerkgeschwindigkeit und lässt solche Ausreißer nicht zum nächsten
  Berechnungs-Basiswert werden.

## [0.5.0-beta.51] - 2026-10-03

### Added

- Die Statistikübersicht zeigt nun den gesamten gemeldeten Festplattenspeicher
  aller Systeme inklusive belegtem Anteil und Gesamtauslastung.

## [0.5.0-beta.50] - 2026-10-03

### Added

- Commander können die sichtbare **Traffic-Statistik** in den Einstellungen
  zurücksetzen. Der neue Zeitraum beginnt sofort; Rohtelemetrie und historische
  Daten werden dabei nicht gelöscht.
- Migration `20261003_0011` speichert den Reset-Zeitpunkt dauerhaft auf dem Server.

### Security

- Das Zurücksetzen ist serverseitig auf Commander beschränkt und wird im Audit-Log
  festgehalten.

## [0.5.0-beta.49] - 2026-10-03

### Added

- Zentrale **Statistikseite** mit Fleet-Verfügbarkeit, gewichteter CPU- und
  RAM-Gesamtauslastung, GPU-Übersicht, kombinierter System-Rangliste,
  Monatsverkehr pro Gerät und Live-Gesamtgraph für den Netzwerkverkehr.
- Fleet-Übersicht und Navigator mit einklappbarem Seitenmenü, einklappbaren
  Gerätegruppen, frei platzierbaren Gruppen sowie Gerätenamen und NCC-Versionen.
- Unraid-Integration für Array-/Laufwerksbelegung, Temperaturen, VMs und Docker-
  Container. Laufende VMs und Container werden zuerst gezeigt.
- Drei zusätzliche, strukturell unterschiedliche Dashboard-Layouts (**Orbit**,
  **Blueprint**, **Studio**) zusätzlich zu den bestehenden Farbthemes.
- Betriebssystem- sowie CPU-/GPU-Modellanzeige mit Herstellerlogos in der Kachel
  **Ausgewählter Node**.

### Changed

- Admin-Codes und Browser-Pairing sind der normale Weg zum Dashboard und zur
  Geräteaufnahme. Interne Agent-Zugänge werden nicht im Dashboard angezeigt.
- Verfügbarkeit und Netzwerkverkehr sind kompakter dargestellt; die Agentenliste
  steht direkt in der Verfügbarkeitskachel.
- Fleet-Warnungen können in der Übersicht einzeln ausgeblendet werden.
- Die Telemetrie-Navigation wurde durch **Statistiken** ersetzt.

### Fixed

- Hardware-Logos werden als Bestandteil des NccServer-Pakets ausgeliefert und
  zuverlässig über `/assets/hardware/` bereitgestellt.
- Dashboard-Fußzeile und alle NCC-Komponenten verwenden konsistent
  `0.5.0-beta.49`.

### Verified

- Frontend-Produktionsbuild und 75 automatisierte Tests erfolgreich.
- NccServer auf HorstServer aktualisiert; Readiness, Versions-API, Dashboard und
  eine ausgelieferte Hardware-Grafik liefern HTTP 200.

## [0.5.0-beta.38] - 2026-10-03

### Added

- Einfaches Dashboard-Rollenmodell mit **Commander**- und **Beta-Tester**-Zugängen.
- Admin-Code-Erstellung mit optionalem Beta-Tester-Schalter und sichtbarem Badge.
- Beta-Tester können das Dashboard ansehen, aber keine neuen Codes erstellen oder
  Geräte, Einladungen und Zugänge löschen bzw. widerrufen.
- Persistente Fleet-Gruppen und Gerätepositionen mit Bearbeiten-Modus, Drag & Drop
  und frei erstellbaren Gruppen.

### Changed

- Fleet-Karten behalten auch in kleinen Gruppen eine einheitliche Breite.
- Die Browser-Freigabe zeigt die Rolle des neuen Zugangs sichtbar an.
- Datenbankmigration `20261003_0009` ergänzt die Admin-Code-Rollen.

### Verified

- NCC Server auf HorstServer aktualisiert; Readiness und Versions-API liefern HTTP 200.
- 74 automatisierte Tests und der Frontend-Produktionsbuild erfolgreich.

## [0.5.0-beta.35] - 2026-10-03

### Added

- Persistente Fleet-Navigator-Gruppen mit Drag-&-Drop-Sortierung und eigenen Gruppen.
- Migration `20261003_0008` für Gerätepositionen und Fleet-Gruppen.

## [0.5.0-beta.34] - 2026-10-02

### Changed

- Fleet Navigator zeigt NCC-Versionen, gruppiert PCs/Laptops und Server zweispaltig
  und enthält Platzhalter für Mobile und Friends.

## [0.5.0-beta.9] - 2026-10-02

### Added

- Linux-Agenten können sich nun per browserbestätigtem Pairing aufnehmen lassen,
  ohne einen Agent-Token zu kopieren oder anzuzeigen.
- Der Windows-Agent-Installer verwendet denselben browserbestätigten Ablauf.

### Added

- Grundlage für eine browserbestätigte Agent-Aufnahme: zeitlich begrenzte,
  geheimnisgeschützte Pairing-Anfragen, die erst nach Dashboard-Freigabe einen
  internen Agent-Zugang erhalten.

## [0.5.0-beta.8] - 2026-10-02

### Added

- Achtstellige, einmalige Admin-Codes für vollständigen Browserzugang zum Dashboard.
- Admin-Code-Verwaltung im Bereich **Gerät hinzufügen**: erstellen, Status sehen und
  Zugang widerrufen.

### Security

- Codes werden nur als SHA-256-Prüfwert gespeichert und nie erneut angezeigt.
- Ein eingelöster Code erzeugt eine HttpOnly-Browsersitzung; ein Widerruf beendet alle
  mit diesem Code ausgestellten Sitzungen.
- Der bisherige Dashboard-Token bleibt nur während der Umstellung als Rückfallzugang
  verfügbar und wird nicht mehr als regulärer Login beworben.

## [0.5.0-beta.6] - 2026-10-01

### Fixed

- Linux-Agent-Installer kann mit `--replace-config` einen bewusst erneuerten
  Agent-Token sicher in die bestehende Dienstkonfiguration übernehmen.

## [0.5.0-beta.5] - 2026-10-01

### Fixed

- Widerrufene Einladungen verschwinden aus der normalen Token-Verwaltung. Der
  Sicherheitsnachweis bleibt weiterhin im Audit-Log erhalten.

## [0.5.0-beta.4] - 2026-10-01

### Fixed

- Ein widerrufener Token wird nach dem Sperren aus der Dashboard-Liste entfernt.
- Neue explizite Aktion **Gerät vergessen**: entfernt einen Node einschließlich seiner
  Telemetrie und Agent-Token-Bindungen. Danach kann dieselbe Maschinen-ID mit einem
  neuen Token wieder aufgenommen werden.
- Der bisherige Schutz gegen die Übernahme einer bestehenden Maschinen-ID bleibt für
  alle nicht ausdrücklich vergessenen Geräte unverändert aktiv.

## [0.5.0-beta.3] - 2026-10-01

### Added

- Dashboard-geführte Geräteaufnahme: individuelle Agent-Einladungen direkt im Bereich
  **Gerät hinzufügen** erstellen, einmalig kopieren, überwachen und widerrufen.
- Wählbare Token-Laufzeiten (24 Stunden, 7 Tage, 30 Tage oder ohne Ablauf).
- Geschützte Verwaltungs-API für Agent-Einladungen unter `/api/v1/agent-invitations`.

### Security

- Der Klartext eines Einladungs-Tokens wird nur in der Erstellungsantwort geliefert;
  Listen und Statusansichten enthalten nie Geheimnisse.
- Dashboard-erstellte und widerrufene Einladungen werden mit dem Akteur `dashboard`
  im Audit-Log vermerkt.

## [0.5.0-beta.2] - 2026-10-01

### Added

- Echte Windows-Dienste für NCC Server und NCC Agent über `pywin32`.
- Native, gehärtete systemd-Units für Server und Agent unter Linux.
- Interaktive Windows- und Linux-Installer für normalen und Tailscale-Betrieb.
- Sichere Update-Installation, die vorhandene Konfigurationen, Tokens und Agent-Puffer
  bewahrt.
- Deinstallationswerkzeuge mit optionalem, ausdrücklich anzuforderndem Daten-Purge.
- Status- und Logwerkzeuge für beide Betriebssysteme.
- `ncc-doctor` für API-, Datenbank-, Token-, DNS- und Tailscale-Diagnosen.
- `ncc-migrate` für reproduzierbare Datenbankmigrationen in Dienstumgebungen.
- Plattformübergreifende CI-Prüfung der Installationsskripte.

### Security

- Dienstkonfigurationen werden außerhalb des Repositorys mit eingeschränkten
  Dateirechten gespeichert.
- Windows-Dienste laufen ohne sichtbares Konsolenfenster und erhalten automatische,
  begrenzte Neustartregeln.
- systemd-Dienste verwenden Prozesshärtung; der Server läuft als eigener `ncc`-Benutzer.
- Diagnosetokens können über eine Umgebungsvariable übergeben werden und müssen nicht
  in der Prozessliste erscheinen.

## [0.5.0-beta.1] - 2026-09-30

### Added

- Moderne, responsive Fleet-Weboberfläche für Desktop, Tablet und Smartphone.
- Geräteübersicht mit Online-Status, letztem Kontakt und aktuellen CPU-, RAM-, GPU-,
  Netzwerk- und Laufwerkswerten.
- Telemetrieansicht mit den letzten 120 Messpunkten je Gerät.
- Neun dauerhaft im Browser gespeicherte Themes.
- Nur lesende Fleet-API für Zusammenfassung, Nodes und Telemetrieverläufe.
- Auslieferung der gebauten React-App direkt durch den eigenständigen NCC-Server.
- Kleines `ncc-dashboard-token`-Werkzeug zur sicheren Erzeugung des Browser-Zugangs.

### Security

- Separater Dashboard-Token; Agent-Tokens werden niemals an den Browser gegeben.
- Tokenloser Dashboard-Zugriff ist standardmäßig ausschließlich über Loopback möglich
  und kann für Serverbetrieb vollständig deaktiviert werden.

## [0.5.0-alpha.3] - 2026-09-30

### Added

- Eigenständiger GUI-loser Windows-/Linux-Agent mit stabiler lokaler Geräte-UUID.
- Plattformübergreifende Hardwareerfassung über die vorhandene Provider-Schicht.
- Begrenzter, persistenter SQLite-Offline-Puffer mit FIFO-Verhalten.
- Gebündelte Telemetrieübertragung mit exponentiellem Reconnect-Backoff.
- Idempotente Sample-IDs verhindern doppelte Messpunkte nach unsicheren Antworten.
- Windows-, Linux- und Tailscale-Starter für den neuen Agenten.
- Dritte Alembic-Migration für eindeutige Telemetrie-Sample-IDs.

### Security

- Agent-Token wird nur im Authorization-Header übertragen und nicht protokolliert.
- Normales Remote-HTTP wird abgewiesen; unsicheres HTTP muss für ein geschütztes
  Tailscale-Netz ausdrücklich aktiviert werden.
- Identitätsdatei und Offline-Puffer erhalten unter Unix restriktive Dateirechte.

## [0.5.0-alpha.2] - 2026-09-30

### Added

- Individuelle, widerrufbare Agent-Tokens mit optionalem Ablaufdatum und einmaliger
  Klartextausgabe über das Werkzeug `ncc-agent-token`.
- Persistente Geräteaufnahme, die einen Token dauerhaft an genau eine Maschinen-ID bindet.
- Authentifizierte Heartbeats und eine Agent-Selbstansicht unter `/api/v1/nodes`.
- Dauerhafte Agent-Version, Metadaten, letzter Kontakt und letzte Token-Verwendung.
- Audit-Ereignisse für Token-Erstellung, Token-Widerruf und Geräteaufnahme.
- Zweite Alembic-Migration für den neuen Agent- und Heartbeat-Zustand.

### Security

- Agent-Tokens werden ausschließlich als SHA-256-Hash gespeichert.
- Abgelaufene, widerrufene, unbekannte und bereits anders gebundene Tokens werden abgewiesen.
- Der gemeinsame NCC-0.4-Token wird von der neuen API nicht akzeptiert.

## [0.5.0-alpha.1] - 2026-09-30

### Added

- Eigenständige, GUI-lose Server-Anwendung als getrenntes Python-Paket.
- Versionierte Server-API unter `/api/v1` mit Live- und Readiness-Prüfung.
- PostgreSQL-Datenmodell für Nodes, Telemetrie, Benutzer, Agent-Tokens und Audit-Ereignisse.
- Erste Alembic-Migration sowie PostgreSQL- und Server-Dienste für Docker Compose.
- Eigener `ncc-server`-Kommandozeilenstart und separate Server-Konfiguration.

### Changed

- Projektversion nach Semantic Versioning auf `0.5.0-alpha.1` angehoben.
- Das Server-Container-Image enthält und startet keine Browseroberfläche und keine
  lokalen Hardware-Sammler mehr.

### Documentation

- Phase-1-Bestandsaufnahme für die geplante getrennte Server-, Agent-, Web- und
  Windows-Integrationsarchitektur dokumentiert.

## [0.4.1] - 2026-09-29

### Fixed

- Windows-Batchdateien werden mit CMD-kompatiblen CRLF-Zeilenenden ausgeliefert.
- Tailscale-Client normalisiert IPs, MagicDNS-Namen und vollständige URLs.
- Gemeinsame Token-Datei wird automatisch importiert und vor dem Start geprüft.
- Client/Server-Fehler sind sichtbar statt unbemerkter Wiederholungsversuche.

## [0.4.0] - 2026-09-29

### Added

- Dedizierte Tailscale-Server- und Client-Starter für Windows und Linux.
- Token-Manager zum Erzeugen, Rotieren, Exportieren und Importieren gemeinsamer Tokens.
- Automatische Erkennung und Validierung von Tailscale-Adressen aus `100.64.0.0/10`.

### Security

- Der Tailscale-Server bindet ausschließlich an seine Tailscale-IP statt an alle
  lokalen Netzwerkschnittstellen.
- Exportierte Token-Dateien werden mit restriktiven Dateirechten angelegt und sind
  von Git ausgeschlossen.

## [0.3.0] - 2026-09-29

### Added

- Herstellerunabhängige Windows-GPU-Erkennung sowie nativer Linux-AMDGPU-Provider.
- Echte, geglättete Netzwerk- und physische Datenträger-I/O-Raten pro Laufwerk.
- Explizite Local-, Server- und Client-Starter für Windows und Linux.
- Phase 0: Projektstruktur, FastAPI-Einstieg, Konfiguration, Startskripte und Frontend-Fallback.
- Phase 1: Token-Schutz, Host-/Origin-Prüfung, Security-Header, Rate-Limits und sichere Dateinamen.
- Phase 2: Provider-Registry mit Timeout/Backoff, psutil-, Demo-, NVML-, SMART- und hwmon-Provider sowie Hardware-Cache.
- Phase 3: Live-WebSocket, Metrics-REST, gebündelte DuckDB-/Memory-Speicherung, Retention und Historie.
- Phase 4: Local-/Server-/Client-Modi, Node-Registrierung, Präsenz, Telemetrie und Reconnect-Client.
- Phase 5: Prozessliste und abgesicherter Kill-Endpunkt mit Schutzliste und Audit-Log.
- Phase 6: Lokaler Chat-/Prompt-Hub, gehärtete Multi-Datei-Uploads und sichere Downloads.
- Phase 7: Persistentes Benutzer-/PC-Profil mit Präsenz-Synchronisierung.
- Phase 8: React-Bento-Dashboard, Live-Gauges, Canvas-Netzwerkgraph, neun Themes, Settings und Changelog-Viewer.
- Phase 9: Docker-/Compose-Setup, systemd-Unit, Plattformanleitung und optionaler PyInstaller-Build.
- Phase 10: Backend-/WebSocket-Tests, Frontend-Checks, plattformübergreifende CI, Releases, Dependabot, Audit und Benchmark.
- Phase 11: README, Architektur- und Provider-Dokumentation, Contribution-Leitfaden und Issue-Templates.

### Changed

- Windows zeigt den vollständigen CPU-Marketingnamen aus der Registry statt der
  generischen Family-/Model-Kennung.
- Frontend auf ein kompaktes Nightmare-Command-Center-Layout mit fester Navigation,
  Statusleisten, technischen Telemetrie-Karten und Storage-Matrix umgestellt.

