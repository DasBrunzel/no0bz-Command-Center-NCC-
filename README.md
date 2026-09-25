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

[![Version](https://img.shields.io/badge/Version-v3.6.3-cyan.svg?style=for-the-badge)](https://github.com)
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

## ✨ Features

- ⚡ **1-Sekunden Live-Telemetrie via WebSockets**: Kein lästiges HTTP-Polling – Metriken werden in Echtzeit gestreamt.
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
  - Speichert Telemetriedaten lokal in `no0bz_metrics.duckdb`.
  - Automatische Bereinigung älterer Daten (24h Rolling Window).
  - Interaktive Verlaufs-Charts über die REST-Schnittstelle (`/api/history`).
- 🛠️ **Integrierter Task- / Prozess-Manager**:
  - Live-Liste aller laufenden Prozesse sortiert nach RAM / CPU.
  - Instant-Suche nach Prozessname.
  - Direkte Prozessbeendigung (Kill PID) über gesicherten POST-Endpunkt (`/api/kill`).
- 💬 **Lokaler P2P Hub (Prompt & File Sharing)**:
  - Text-Prompts, Code-Snippets und Notizen zwischen Geräten im lokalen Netzwerk austauschen.
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
  Starting no0bz Command Center (NCC) v3.6.3...
========================================================
[NCC] Dashboard running at: http://127.0.0.1:8350
```

---

### Option B: Manueller Start via Terminal / PowerShell

#### 1. Repository klonen oder herunterladen
```bash
git clone https://github.com/DEIN-BENUTZERNAME/DEIN-REPO-NAME.git
cd DEIN-REPO-NAME
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
| `GET` | `/api/history?minutes=60` | Zeitreihen-Abfrage aus der DuckDB-Datenbank |
| `POST` | `/api/kill` | Beendet einen Prozess anhand seiner PID (`{"pid": 1234}`) |
| `GET` | `/api/chat/messages` | Ruft gespeicherte Chat-, Code- und Prompt-Nachrichten ab |
| `POST` | `/api/chat/send` | Sendet einen Prompt oder eine Notiz |
| `POST` | `/api/chat/upload` | Multi-Datei-Upload in den Ordner `ncc_uploads/` |
| `GET` | `/api/chat/files` | Auflistung aller übertragenen Dateien |

---

## 🔄 GitHub Repository Synchronisation

### Dein Projekt auf GitHub hochladen:

Wenn du bereits ein Repository auf GitHub erstellt hast (z. B. `https://github.com/DEIN-ACCOUNT/no0bz-command-center.git`), führe einfach folgende Befehle in deinem Terminal / deiner PowerShell aus:

```bash
# 1. Git initialisieren (falls noch nicht geschehen)
git init

# 2. Alle Dateien hinzufügen
git add .

# 3. Ersten Commit erstellen
git commit -m "feat: Initial release v3.6.3 no0bz Command Center"

# 4. Standard-Branch auf 'main' setzen
git branch -M main

# 5. Remote-Repository mit deiner GitHub-URL verknüpfen
git remote add origin https://github.com/DEIN-ACCOUNT/no0bz-command-center.git

# 6. Auf GitHub pushen
git push -u origin main
```

### Spätere Updates herunterladen:
```bash
git pull origin main
```

---

## 🔒 Datenschutz & Sicherheit

- Das no0bz Command Center ist für den **lokalen Einsatz (Localhost / LAN)** konzipiert.
- Es werden keinerlei Telemetriedaten an externe Server gesendet.
- DuckDB speichert historische Daten ausschließlich lokal in der Datei `no0bz_metrics.duckdb`.

---

## 📜 Lizenz

Veröffentlicht unter der [MIT License](LICENSE).  
Entwickelt mit ❤️ für die **no0bz** Community.
