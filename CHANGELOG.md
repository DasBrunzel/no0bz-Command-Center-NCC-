# 📜 no0bz Command Center (NCC) – Changelog

Alle wichtigen Änderungen, neuen Funktionen und Optimierungen für das **no0bz Command Center (NCC)** werden in dieser Datei chronologisch dokumentiert.

Das Format basiert auf [Keep a Changelog](https://keepachangelog.com/de/1.0.0/) und dieses Projekt hält sich an [Semantic Versioning](https://semver.org/lang/de/).

---

## [v3.8.0] - 2026-09-25

### 🚀 Neu & Hervorgehoben
- **Fast-Boot Hardware-Cache (`ncc_system_cache.json`)**:
  - Beim ersten Start des NCC werden alle statischen und semi-statischen System- und Hardware-Informationen (CPU-Modell, Kernanzahl, Taktraten, Speichertopologie, GPU-Details, Festplatten-Layout, Netzwerkkarten) ermittelt und als lokales Hardware-Profil in `ncc_system_cache.json` abgespeichert.
  - Bei jedem nachfolgenden Start wird das Profil in unter **1 Millisekunde** blitzschnell aus dem Cache geladen. Das spart wertvolle Startzeit und vermeidet wiederholte, hardwareintensive Probing-Abfragen.
  - Neuer REST-Endpunkt `GET /api/system/profile` zum Abrufen des Hardware-Profils.
  - Neuer POST-Endpunkt `POST /api/system/profile/refresh` sowie ein Schnellzugriff-Button in den NCC-Einstellungen, um den Cache jederzeit bei Hardware-Änderungen neu einzulesen.
- **Ausführliche GitHub-Architekturdokumentation**:
  - In der `README.md` wurde ein umfangreicher Abschnitt hinzugefügt (*„Wie und womit das no0bz Command Center (NCC) erstellt wurde“*), der alle verwendeten Technologien, Backend-Strukturen, WebSocket-Streaming, Hardware-Treiber und Frontend-Architektur detailliert aufschlüsselt.

---

## [v3.7.0] - 2026-09-25

### 🚀 Neu & Hervorgehoben
- **Integrierter Changelog-Viewer im NCC**: Das Changelog kann nun direkt im Command Center über das Seitenmenü, den Header-Button oder durch Klick auf das Versions-Badge `v3.7.0` eingesehen werden.
- **Vollständig autarkes Single-File Dashboard**: Das identische High-Performance React-Frontend ist jetzt direkt als komprimiertes Bundle in `main.py` eingebettet. Das Ausführen von `python main.py` benötigt keinen separaten Node.js- oder npm-Build-Schritt mehr – die Cyber-Oberfläche lädt sofort vollständig und einsatzbereit.
- **Vorkompilierter `dist/`-Ordner im Repository**: Für Nutzer, die das Repository klonen oder herunterladen, ist das gebaute Frontend direkt verfügbar.
- **Dynamische WebSocket-Host-Erkennung**: Der WebSocket (`/ws/live`) ermittelt die Server-Adresse dynamisch über `window.location.host`. Das ermöglicht den nahtlosen Zugriff über LAN-IPs (z. B. `192.168.x.x:8350`), Hostnames, Reverse Proxies oder Port-Weiterleitungen ohne harte Bindung an `localhost`.
- **Neue Backend-Routen**:
  - `/api/changelog`: Liefert das aktuelle Changelog als JSON/Text für den Client.
  - `/changelog`: Eigenständige, formatierte HTML-Changelog-Seite für Direktaufrufe im Browser.

### ⚡ Verbesserungen & Performance
- **NVIDIA GPU-Treiber Modernisierung**: Bevorzugt primär das offizielle, moderne `nvidia-ml-py` vor dem veralteten `pynvml`-Paket, wodurch lästige Deprecation-Warnungen beim Start entfallen.
- **Bereinigte Dokumentation**: GitHub-Synchronisations-Befehle aus der allgemeinen `README.md` entfernt, um die Anleitung fokussiert und übersichtlich zu halten.
- **Automatischer Browser-Start**: Die Windows-Batchdatei `start_ncc.bat` öffnet nach dem Starten des Python-Servers automatisch `http://localhost:8350`.

### 🐛 Fehlerbehebungen
- Behebung des Problems, bei dem nach dem Klonen von GitHub nur die minimalistische Platzhalter-Infobox statt des vollen Command Centers angezeigt wurde.
- Versionsanzeige im Footer und Header einheitlich auf `v3.7.0` synchronisiert.

---

## [v3.6.3] - 2026-09-18

### 🚀 Neu
- **P2P Chat & Prompt Sync Hub**: Lokaler, hochperformanter Echtzeit-Chat zum Synchronisieren von KI-Prompts, Code-Snippets und System-Befehlen zwischen mehreren PCs im lokalen Netzwerk.
- **Dateibrowser & Chat Vault**: Drag-and-Drop Dateitransfer mit automatischer Vorschau für Bilder, Dateigrößen-Formatierung und Download-Verwaltung (`/api/chat/upload`, `/api/chat/download/*`).
- **Prozess-Manager mit Task-Kill**: Vollwertige Prozesstabelle mit CPU- und RAM-Sortierung, Schnellsuche und Prozessbeendigung via `POST /api/kill`.
- **DuckDB 24h Telemetrie-Historie**: Lokale Zeitreihen-Datenbank (`no0bz_metrics.duckdb`) für 1-Sekunden-Metriken mit automatischer 24h-Bereinigung und Verlaufs-Charts.
- **Dual-Style Logo & Themes**: Umschaltbar zwischen **Classic Cyber Cyan** (`#00ffc8` / `#06b6d4`) und **Nightmare Red** (`#ef4444`) mit interaktivem Bento-Grid-Layout.

---

## [v3.5.0] - 2026-09-02

### 🚀 Neu
- **LibreHardwareMonitor (LHM) Fallback**: Automatischer Abruf erweiterter Sensordaten über den lokalen LHM-Webserver (`http://127.0.0.1:8085/data.json`).
- **Lüfterdrehzahl- & Mainboard-Überwachung**: Auslesen von Lüfter-Drehzahlen (RPM) und CPU-Package-Leistungsaufnahme (Watt).
- **SVG Circular Gauges**: Dynamische Kreisdiagramme mit Gradienten-Bögen für CPU-, GPU- und RAM-Auslastung.

### ⚡ Verbesserungen
- Thread-sichere Datensammlung via Python `threading.Lock` (`data_lock`) zur Vermeidung von Race Conditions bei parallelen WebSocket-Clients.

---

## [v3.1.0] - 2026-08-15

### 🚀 Neu
- **Echtzeit-WebSockets (`/ws/live`)**: Umstellung von HTTP-Polling auf Push-Streaming im 1-Sekunden-Takt für minimale Latenz und geringe Systemlast.
- **Native NVIDIA NVML-Unterstützung**: Direktes Auslesen von GPU-Load, VRAM-Belegung, GPU-Temperatur und Power-Draw über die NVIDIA C-API.
- **Multi-Core & NVMe Monitoring**: psutil-Integration für Einzelkern-Auslastung, Festplatten-Durchsatz (MB/s Read/Write) und Netzwerktraffic.

---

## [v3.0.0] - 2026-07-28

### 🚀 Initialer Release
- **no0bz Command Center (NCC)**: Erstveröffentlichung als ultra-schneller, schlanker System-Monitor auf Basis von Python 3, FastAPI und Uvicorn auf Port 8350.
- Cyberpunk- und Bento-Grid-Design im no0bz Community-Look.
