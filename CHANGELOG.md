# 📜 no0bz Command Center (NCC) – Changelog

Alle wichtigen Änderungen, neuen Funktionen und Optimierungen für das **no0bz Command Center (NCC)** werden in dieser Datei chronologisch dokumentiert.

Das Format basiert auf [Keep a Changelog](https://keepachangelog.com/de/1.0.0/) und dieses Projekt hält sich an [Semantic Versioning](https://semver.org/lang/de/).

---

## [v3.12.0] - 2026-09-29

### 🚀 Neu & Hervorgehoben (Client/Server-Trennung, Nexus Rig Matrix & Reale NIC-Erkennung)
- **Interaktive Start-Abfrage im Terminal (Client vs. Server Trennung)**:
  - Beim Start von `main.py` oder `start_ncc.bat` im Terminal wird der Nutzer nun interaktiv gefragt, in welchem Modus das System gestartet werden soll:
    - `[1] Server-Modus (Master Hub Server)`: Verwaltet das Cluster, empfängt Telemetrie & Chat von allen Clients.
    - `[2] Client-Modus (Cluster Node / Zweitrechner)`: Fragt gezielt ab, ob eine Verbindung zu einem Server aufgebaut werden soll (mit Eingabe der Server-IP/Port) oder Standalone gestartet wird.
    - `[3] Standalone-Modus (Lokaler Einzel-PC)`: Autarker Betrieb ohne Netzwerkverbindungen.
  - Automatisierte Starts über `--mode [host|server|client|local|standalone]` und `--yes` (`-y`) bleiben für Skripte und Autostart voll funktionsfähig.
- **Multi-PC Hub umbenannt zu "NEXUS RIG MATRIX"**:
  - Der Multi-PC Hub wurde in das viel coolere **"NEXUS RIG MATRIX // NEURAL CLUSTER COMMAND"** umbenannt.
  - Verbesserte Kartenansicht, klare Rollenverteilung (`HOST` vs `CLIENT`), Ping-Anzeige und Ein-Klick-Dashboard-Umschaltung.
- **Echte Netzwerk-Erkennung (NIC) & Beseitigung der statischen "LAN 10 GbE" Anzeige**:
  - Die Netzwerkkarte und deren tatsächliche Verbindungsgeschwindigkeit werden nun dynamisch über `psutil.net_if_stats()` ermittelt:
    - 1.000 Mbit/s -> **LAN 1 GbE**
    - 2.500 Mbit/s -> **LAN 2.5 GbE**
    - 10.000 Mbit/s -> **LAN 10 GbE**
    - WLAN/Wireless -> **Wi-Fi (WLAN)**
  - Der genaue Adapter-Name wird im Kartenfuß angezeigt (z. B. Realtek, Intel oder System-NIC).
- **Behebung der Terminal-Fehler im Server/Client-Betrieb**:
  - Beseitigung des `ValueError: signal only works in main thread`-Fehlers, der durch einen zweiten uvicorn-Server in einem Hintergrund-Thread verursacht wurde. Alle Cluster- und Telemetrie-Endpunkte laufen nun stabil und ressourcenschonend über den Hauptdienst auf Port 8350.
- **Zuverlässiger Telemetrie- & Chat-Sync zwischen Client und Server**:
  - `ClientStreamer` verbindet sich automatisch mit dem Standard-Port 8350 des Servers (kein versehentlicher Fallback auf Port 80 mehr).
  - Der Server antwortet auf Telemetrie-Pushes direkt mit seinen eigenen Live-Metriken, sodass der Client in der Nexus Matrix und im Dashboard die echten Live-Werte des Master Servers sieht.
  - Chat-Nachrichten synchronisieren sich kontinuierlich und beidseitig zwischen Master Server und allen verbundenen Clients.

---

## [v3.11.0] - 2026-09-28

### 🚀 Neu & Behoben (Multi-PC, Chat & Cluster Inspector)
- **Voll funktionsfähiger Chat & Prompt-Sync**:
  - Beseitigung aller fehlerhaften `http://localhost:8350`-Aufrufe im Frontend: Chat-Nachrichten, Dateiuploads und Dateilöschungen nutzen nun korrekte relative API-Pfade (`/api/chat/*`) und synchronisieren sich zuverlässig mit dem Backend und der DuckDB-Datenbank.
  - WebSocket-Verbindung (`/ws/live`) bindet sich nun universell an den aktiven Host, wodurch Chat-Broadcasts in Echtzeit zwischen allen Tabs und Rechnern übertragen werden.
  - P2P- und Server-Weiterleitung im Client-Modus: Im Client-Betrieb erstellte Chat-Nachrichten werden automatisch an den Master-Server weitergeleitet.
- **Server-Sichtbarkeit im Client-Modus**:
  - Wenn ein Rechner im Client-Modus läuft, zeigt die Knotenliste im "Multi PC Hub" nun sowohl den verbundenen **Master Hub Server** (mit Krone `👑`, Server-IP, OS und Live-Telemetrie) als auch die lokale **Client Workstation** an.
- **Korrekte Rollen- und Icon-Zuordnung (Keine falsche Krone für Clients)**:
  - Im Client-Modus wird der Client-PC nun korrekt mit dem Laptop-Symbol (`💻`) und der Rolle `Client Node (Lokal)` dargestellt. Die Master-Krone (`👑`) und das `HOST`-Badge sind exklusiv dem Master Server vorbehalten.
- **Echtzeit-Dashboard-Umschaltung für Remote-Knoten ("Cluster Inspector")**:
  - Das Umschalten auf einen Remote-PC im "Multi PC Hub" ("Im Dashboard anzeigen") überträgt die Telemetrie des ausgewählten PCs (CPU-Last, RAM, GPU, Netzwerk I/O, Systemname) sofort und vollständig auf das Dashboard.
  - Ein neuer **Cluster Inspector Banner** informiert über den aktuell im Dashboard aktiven Knoten und bietet eine Ein-Klick-Rückkehr zur Standard-Systemansicht.
  - Auch die Quick-Stats in der Seitenleiste spiegeln den ausgewählten Remote-Knoten wider.

---

## [v3.10.0] - 2026-09-28

### 🚀 Neu & Optimiert
- **Full-Stack Universal Server Architecture (`server.ts` & `main.py`)**:
  - Nahtloser Dev- und Production-Serverbetrieb auf Port 3000 mit integrierten Express-APIs, nativem WebSocket-Streaming (`/ws/live`) und dynamisch gemounteten Vite-Middlewares.
  - Vollständige Behebung von Proxy-Verbindungsabbrüchen (`ECONNREFUSED 127.0.0.1:8350`): Sämtliche REST- und WebSocket-Endpoints (`/api/system/profile`, `/api/nodes`, `/api/processes`, `/api/kill`, `/api/chat/*`, `/ws/live`) reagieren sofort und fehlerfrei.
  - Reale Hardware-Erkennung für AMD Zen / Intel Core x86_64, dedizierte GPUs (NVIDIA/AMD) und Linux Container/Cloud Environments.
  - Erweiterter Prozess-Manager mit Spaltensortierung (PID, Name, CPU, RAM) und sofortiger Prozess-Terminierung.
  - Parallele Unterstützung für eigenständigen Python-3-Betrieb via `main.py` auf Port 8350 mit synchronisiertem Pre-compiled React Dashboard Bundle.

---

## [v3.8.2] - 2026-09-26

### 🚀 Neu & Hervorgehoben
- **Exklusive serverseitige Speicherung im Server-Betrieb**:
  - Im **Server-Betrieb (Host)**: Sämtliche Chat-Dateien (`data/server/vault/`) und die DuckDB-Datenbankhaltung (`no0bz_server.duckdb`) erfolgen *ausschließlich serverseitig*. Verbundene Clients übertragen Dateien und Telemetriedaten direkt an den Master-Server, der sie zentral speichert und an alle Clients streamt.
  - Im **Standalone-Modus (Lokal)**: Vollständig autarker Betrieb, bei dem Chat-Dateien (`data/local/vault/`) und die DuckDB-Datenbank (`no0bz_local.duckdb`) *ausschließlich lokal* auf dem Rechner gehalten werden.
  - Im **Client Node Modus**: Reine Remote-Verbindung zum Server (z. B. `192.168.1.100:8350`). Keine lokale Datenbanküberlastung; alle Dateien und Nachrichten werden serverseitig vorgehalten.
- **Konfigurationspersistenz (`ncc_config.json`)**:
  - Der gewählte Betriebsmodus (Server / Standalone / Client) sowie die Server-URL werden in `ncc_config.json` persistent gespeichert und beim Start automatisch geladen.
  - Dynamisches Umschalten des Betriebsmodus zur Laufzeit via `POST /api/multipc/mode` mit sofortigem Wechsel der Datenbankverbindung und des aktiven Vault-Speicherorts.
- **100% Funktionstüchtig ohne Platzhalter**:
  - Vollständiger Multipart-Form-Data Upload (`POST /api/chat/upload`) mit automatischer Dateiablage und DuckDB-Katalogisierung.
  - Echter Dateidownload (`GET /api/chat/download/{filename}`) und Löschfunktion (`DELETE /api/chat/files/{filename}`).
  - Chat-Nachrichten und Attachments werden in DuckDB (`chat_messages`, `chat_files`) persistiert und über WebSockets in Echtzeit an alle verbundenen Browser übertragen.

---

## [v3.8.1] - 2026-09-26

### 🚀 Neu & Hervorgehoben
- **Echtzeit Network I/O Canvas-Graph**:
  - Die Network I/O Kachel verfügt jetzt über einen hochpräzisen, echtzeitfähigen 60 FPS HTML5 Canvas-Graphen.
  - Zweifarbige Neon-Kurven mit leuchtenden Verläufen: **Download (RX)** in Cyan (`#00f0ff`) und **Upload (TX)** in Magenta/Amber (`#f59e0b`).
  - Automatische Skalierung mit Pegelanzeige, Spitzenwert-Indikator (Peak Mbps), Gitterlinien und 60-Sekunden-Verlaufsfenster.
- **Multi-PC Systemarchitektur (Local / Server Hosten / Auf Server verbinden)**:
  - Interaktive Modusauswahl beim Start oder jederzeit über den Header:
    1. **🖥️ Lokal (Standalone)**: Autarker Systemmonitor für den lokalen Rechner.
    2. **👑 Server hosten (NCC Master Hub)**: Macht diesen Rechner zum zentralen Hub-Server. Sammelt und speichert alle Telemetriedaten verbundener PCs in DuckDB (`node_metrics`) und zeigt alle aktiven PCs übersichtlich im Interface.
    3. **🔗 Auf Server verbinden (Client Node)**: Ermöglicht das Verbinden entfernter Rechner mit dem Server (z. B. `192.168.1.100:8350`), um Telemetrie sekündlich an den Host zu streamen.
  - **Server-Präsenz im Interface**: Der Server wird im Interface prominent mit Status, Port, Host-IP, Uptime, DuckDB-Speicherstand und Anzahl verbundener Clients dargestellt.
  - **Übersicht aller verbundenen PCs**: Detaillierte Kachel- und Tabellenansicht aller Clients inklusive PC-Name, Benutzername, IP-Adresse, Ping-Latenz, Betriebssystem, Live-CPU/RAM/GPU-Auslastung und Net I/O.
  - **Interaktiver Dashboard-Umschalter**: Ein Klick auf einen verbundenen PC schaltet das Haupt-Dashboard um, sodass die Live-Telemetrie dieses Rechners in Echtzeit analysiert werden kann.
- **Benutzerprofil & PC-Name im Chat**:
  - Im Chat wird standardmäßig automatisch der reale PC-Name (Hostname) als Absender verwendet.
  - Neuer **Profil-Editor** in den Einstellungen: Individuelle Anpassung von Benutzername/Alias, PC-Name, Cyber-Avatar (10 Icons), Rolle/Callsign (z. B. *Host Master, Gaming Rig, HPC Node*) und Statusnachricht mit sofortiger Synchronisation.
- **Feingranulare Versionierung**:
  - Gemäß Nutzer-Feedback werden Versionssprünge jetzt in feinen, nachvollziehbaren Schritten (`v3.8.1`, `v3.8.2` etc.) gepflegt.
- **Changelog-Navigation optimiert**:
  - Das Changelog wurde aus dem linken Menü entfernt und ist nun sauber über den Header-Button und die klickbaren Versions-Badges zugänglich.

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
