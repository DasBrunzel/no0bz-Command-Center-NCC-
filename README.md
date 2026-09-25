# ⚡ no0bz Command Center (NCC)

<div align="center">

```text
  _  _  ___   ___  ____ _____ 
 | \| |/ _ \ / _ \| __ )__  / 
 | .` | | | | | | |  _ \ / /  
 |_|\_|\___/ \___/| |_) / /_  
                  |____/____| COMMAND CENTER
```

**High-Performance Real-Time System Monitor & Local P2P Sync Hub**  
*Built for Power Users, Gamers, Devs & Homelab Admins.*

[![Version](https://img.shields.io/badge/Version-v3.8.0-cyan.svg?style=for-the-badge)](https://github.com)
[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![DuckDB](https://img.shields.io/badge/DuckDB-TimeSeries-FFF000?style=for-the-badge&logo=duckdb&logoColor=black)](https://duckdb.org)
[![NVIDIA](https://img.shields.io/badge/NVML-NVIDIA%20GPU-76B900?style=for-the-badge&logo=nvidia&logoColor=white)](https://nvidia.com)
[![License](https://img.shields.io/badge/License-MIT-blue.svg?style=for-the-badge)](LICENSE)

</div>

---

## 🌟 Über das Projekt (Overview)

Das **no0bz Command Center (NCC)** ist ein leichtgewichtiges, ultra-schnelles und vollständig autonomes System-Monitoring-Dashboard. Es läuft als portable Single-File-Anwendung (`main.py`) auf Basis von **FastAPI** und **WebSockets** und liefert sekündliche Telemetriedaten direkt an ein interaktives Bento-Grid Web-Frontend auf **Port 8350**.

---

## 🛠️ Wie und womit das no0bz Command Center (NCC) erstellt wurde

Das **no0bz Command Center (NCC)** wurde von Grund auf als kompromisslos schnelles, ressourcenschonendes und visuell ansprechendes System-Monitoring- & Hub-Werkzeug für Enthusiasten entwickelt. Hier ist der vollständige technische Aufbau im Detail:

### 1. ⚙️ Backend & Asynchroner Server-Core
* **Sprache:** Python 3 (3.10+)
* **Web-Framework:** [FastAPI](https://fastapi.tiangolo.com/) – bietet blitzschnelle asynchrone Endpunkte, integrierte Typvalidierung und minimale CPU-Latenz.
* **ASGI-Server:** [Uvicorn](https://www.uvicorn.org/) – ein extrem leichtgewichtiger, produktionsreifer ASGI-Webserver, der auf Port `8350` lauscht.
* **Multithreading:** Ein entkoppelter Hintergrund-Thread (`DataCollector`) sammelt alle System- und GPU-Metriken kontinuierlich im Hintergrund. Zugriffskonflikte werden durch Python `threading.Lock()` (`data_lock` & `chat_lock`) verhindert.

### 2. ⚡ Echtzeit-Telemetrie via WebSockets
* **Echtzeit-Stream (`/ws/live`):** Anstelle von ineffizientem HTTP-Polling, das den Browser und Server unnötig belastet, nutzt das NCC einen bidirektionalen WebSocket.
* Alle Metriken (CPU, RAM, GPU, Disks, Network, Lüfter) werden in kompakten 1-Sekunden-Paketen an alle verbundenen Browser-Clients gepusht.

### 3. 🖥️ Low-Level Hardware-Schnittstellen
* **System- & OS-Metriken:** [`psutil`](https://github.com/giampaolo/psutil) liest Kernel-Metriken wie CPU-Last pro Kern, Taktfrequenzen, Arbeitsspeicher, Swap, Partitionsbelegung und I/O-Durchsatz (MB/s).
* **Native NVIDIA GPU-Beschleunigung:** Über die offizielle NVIDIA Management Library ([`nvidia-ml-py`](https://pypi.org/project/nvidia-ml-py/) bzw. C-API `pynvml`) werden GPU-Auslastung, dedizierter VRAM, Hotspot-Temperaturen und Leistungsaufnahme (Watt) direkt vom NVIDIA-Treiber abgefragt.
* **Motherboard- & Lüfter-Sensoren:** Bei Bedarf integriert sich NCC nahtlos an den lokalen REST-Endpunkt von [LibreHardwareMonitor](https://github.com/LibreHardwareMonitor/LibreHardwareMonitor) (`http://127.0.0.1:8085/data.json`), um Lüfterdrehzahlen (RPM) und CPU-Package-Power auszulesen.

### 4. 🗄️ Lokale Zeitreihen-Datenbank (DuckDB)
* **High-Speed Analytics:** [`DuckDB`](https://duckdb.org/) agiert als eingebettete, spaltenorientierte In-Process SQL-Datenbank (`no0bz_metrics.duckdb`).
* Sekündliche Snapshots werden verlustfrei persistiert.
* **Automatisches 24h Rolling Window:** Ältere Einträge werden automatisch bereinigt, um Speicherplatz zu schonen.

### 5. 🎨 Reaktives Cyber-Frontend & Bento-Grid
* **Technologie:** React 18, TypeScript, Tailwind CSS, Lucide Icons.
* **Bento-Grid Design:** Modulare Kachel-Architektur mit CSS Variables für dynamische Themes (u. a. *CachyOS Cyan, Nightmare Red, Cyber Neon, Dark Matter OLED, Matrix Hacker*).
* **Hardware-Beschleunigte Graphen:** 60 FPS HTML5 Canvas-Rendering für ruckelfreie Verlaufsdiagramme ohne schwere externe Chart-Bibliotheken.
* **SVG Circular Gauges:** Maßgeschneiderte Vektor-Bögen mit Farbgradienten für CPU-, RAM- und GPU-Last.

### 6. 🚀 Fast-Boot Hardware-Cache (`ncc_system_cache.json`)
* **Intelligentes Erststart-Profiling:** Beim ersten Start des NCC wird eine Analyse aller statischen Hardwarekomponenten (CPU-Architektur, Taktraten, Speichertopologie, GPU-Modell, Festplatten-Layout, Netzwerkkarten) durchgeführt und in der Datei `ncc_system_cache.json` gespeichert.
* **Blitzstart bei Folge-Starts:** Bei jedem weiteren Start wird dieses Profil in unter **1 Millisekunde** direkt aus dem Cache geladen. Das spart wertvolle Startzeit und vermeidet wiederholte, hardwareintensive Probing-Abfragen. Über den Button in den Einstellungen oder `POST /api/system/profile/refresh` kann der Cache jederzeit manuell aktualisiert werden.

### 7. 📦 Vollständige Single-File Autarkie
* Das gebaute React-Frontend ist zusätzlich als komprimierter Base64-String direkt im Quellcode von `main.py` integriert. Dadurch kann das Command Center auf jedem Rechner ohne vorherige Installation von Node.js oder npm sofort mit vollem Funktionsumfang ausgeführt werden.

---

## ✨ Features

- ⚡ **Fast-Boot Hardware-Cache (`ncc_system_cache.json`)**: Blitzstart in <1ms ohne erneutes Hardware-Probing.
- ⚡ **1-Sekunden Live-Telemetrie via WebSockets**: Metriken werden in Echtzeit gestreamt.
- 📜 **Integrierter Changelog-Viewer**: Direkt über das NCC-Menü und als Markdown auf GitHub verfügbar.
- 🎨 **Modernes Bento-Grid Dashboard**:
  - 8 Cyber-Themes: *CachyOS Cyan, Cyber Neon, Dark Matter OLED, Clean Light, Matrix Hacker, Dracula, Nordic Frost, Retro Amber*.
  - SVG-Gauges, animierte Balken & responsive Karten.
- 🎮 **NVIDIA GPU-Monitoring (NVML)**:
  - GPU-Auslastung (%), VRAM-Nutzung (GB), Temperatur (°C) & Power Draw (Watt).
  - Volle Unterstützung für das moderne `nvidia-ml-py` sowie das klassische `pynvml`.
- 💻 **Umfassende CPU-, RAM-, Disk- & Netzwerk-Metriken**:
  - CPU-Gesamtauslastung & Kern-Verteilung.
  - RAM- und Swap-Speicher.
  - Physische Laufwerke mit R/W-Geschwindigkeiten (MB/s).
  - Netzwerkdurchsatz (Download / Upload in Mbps) & Gesamt-Transfer.
- 🌡️ **LibreHardwareMonitor (LHM) Fallback**:
  - Liest automatisch Lüfterdrehzahlen (RPM), CPU Package Power & Mainboard-Sensoren über den lokalen LHM-Webserver (`http://127.0.0.1:8085/data.json`).
- 🗄️ **DuckDB Time-Series Logging**:
  - Speichert Telemetriedaten lokal in `no0bz_metrics.duckdb` mit 24h Rolling Window.
  - Interaktive Verlaufs-Charts über die REST-Schnittstelle (`/api/history`).
- 🛠️ **Integrierter Task- / Prozess-Manager**:
  - Live-Liste aller laufenden Prozesse sortiert nach RAM / CPU.
  - Instant-Suche nach Prozessname und gezielte Prozessbeendigung (`/api/kill`).
- 💬 **Lokaler P2P Hub (Prompt & File Sharing)**:
  - Text-Prompts, Code-Snippets und Notizen zwischen Geräten im LAN austauschen.
  - Drag & Drop Datei-Upload mit Vorschau und lokalem Speicher in `ncc_uploads/`.
- 📦 **Zero-Bloat Single-File Architektur**:
  - Läuft out-of-the-box mit einer einzigen Datei (`main.py`) oder dem beiliegenden Starter-Script `start_ncc.bat`.

---

## 🚀 Schnellstart (Quickstart)

### Option A: Windows 1-Klick Start (Empfohlen)

Doppelklicke einfach auf die Datei **`start_ncc.bat`** im Projektordner.  
Das Skript installiert automatisch alle notwendigen Pakete aus der `requirements.txt` und startet das Dashboard!

```text
========================================================
  Starting no0bz Command Center (NCC) v3.8.0...
========================================================
[NCC] Dashboard running at: http://127.0.0.1:8350
```

---

### Option B: Manueller Start via Terminal / PowerShell

#### 1. Repository klonen oder herunterladen
```bash
git clone https://github.com/DEIN-BENUTZERNAME/DEIN-REPO-NAME.git](https://github.com/DasBrunzel/no0bz-Command-Center-NCC-.git
cd no0bz-Command-Center-NCC-
```

#### 2. Virtuelle Umgebung anlegen & aktivieren (optional, aber empfohlen)
**Unter Windows (PowerShell):**
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

**Unter Linux / macOS:**
```bash
python3 -m venv venv
source venv/bin/activate
```

#### 3. Abhängigkeiten installieren
```bash
pip install -r requirements.txt
```

#### 4. no0bz Command Center starten
```bash
python main.py
```

Öffne deinen Browser unter: **[http://127.0.0.1:8350](http://127.0.0.1:8350)**

---

## 📋 Anforderungen (`requirements.txt`)

| Paket | Zweck | Status |
| :--- | :--- | :--- |
| `fastapi` | Asynchrones High-Speed Backend | Erforderlich |
| `uvicorn[standard]` | ASGI-Webserver & WebSockets | Erforderlich |
| `psutil` | System-, CPU-, RAM- & Disk-Metriken | Erforderlich |
| `python-multipart` | Datei-Uploads & Multipart-Formulare | Erforderlich |
| `nvidia-ml-py` | Offizielle NVIDIA NVML GPU-Schnittstelle | Optional (für NVIDIA GPUs) |
| `duckdb` | Lokale Zeitreihen-Datenbank (24h History) | Optional (Automatischer In-Memory Fallback) |

> 💡 **Hinweis zu NVIDIA:** Falls kein NVIDIA-Treiber installiert ist oder eine AMD/Intel-GPU genutzt wird, läuft das System nahtlos im CPU/RAM-Modus weiter, ohne abzustürzen.

---

## 🌡️ Lüfter & Mainboard-Sensoren einbinden (Optional)

Um Lüfter-Drehzahlen (RPM) und erweiterte Mainboard-Temperaturen anzuzeigen:
1. Lade [LibreHardwareMonitor](https://github.com/LibreHardwareMonitor/LibreHardwareMonitor) herunter.
2. Starte LibreHardwareMonitor als Administrator.
3. Aktiviere im Menü: **Options** ➔ **Remote Web Server** ➔ **Run** (Port: `8085`).
4. NCC erkennt den Webserver automatisch unter `http://127.0.0.1:8085/data.json` und schaltet die Anzeige frei!

---

## 📡 API & WebSocket Dokumentation

| Methode | Endpunkt | Beschreibung |
| :--- | :--- | :--- |
| `WS` | `/ws/live` | WebSocket-Stream mit sekundengenauen Systemmetriken im JSON-Format |
| `GET` | `/` | Das vollständige, reaktive HTML5/JS Dashboard |
| `GET` | `/api/metrics` | Snapshot der aktuellen Systemmetriken als REST-Response |
| `GET` | `/api/system/profile` | Liefert das gecachte Fast-Boot Hardware-Profil (`ncc_system_cache.json`) |
| `POST` | `/api/system/profile/refresh` | Forciert eine Neu-Erkennung der Hardware und aktualisiert den Cache |
| `GET` | `/api/changelog` | Liefert das aktuelle Changelog als JSON-Payload |
| `GET` | `/changelog` | Eigenständige, formatierte HTML-Changelog-Seite |
| `GET` | `/api/history?minutes=60` | Zeitreihen-Abfrage aus der DuckDB-Datenbank |
| `POST` | `/api/kill` | Beendet einen Prozess anhand seiner PID (`{"pid": 1234}`) |
| `GET` | `/api/chat/messages` | Ruft gespeicherte Chat-, Code- und Prompt-Nachrichten ab |
| `POST` | `/api/chat/send` | Sendet einen Prompt oder eine Notiz |
| `POST` | `/api/chat/upload` | Multi-Datei-Upload in den Ordner `ncc_uploads/` |
| `GET` | `/api/chat/files` | Auflistung aller übertragenen Dateien |

---

## 🔒 Datenschutz & Sicherheit

- Das no0bz Command Center ist für den **lokalen Einsatz (Localhost / LAN)** konzipiert.
- Es werden keinerlei Telemetriedaten an externe Server gesendet.
- DuckDB speichert historische Daten ausschließlich lokal in der Datei `no0bz_metrics.duckdb`.

---

## 📜 Lizenz

Veröffentlicht unter der [MIT License](LICENSE).  
Entwickelt mit ❤️ für die **no0bz** Community.
