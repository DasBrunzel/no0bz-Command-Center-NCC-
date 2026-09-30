# Changelog

Alle wesentlichen Änderungen werden hier dokumentiert.

## [Unreleased]

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

