# NCC Android – Konzept

Stand: 08.11.2026 · Status: Entwurf zur Abstimmung

Native Android-App (Kotlin + Jetpack Compose), die ein Android-Gerät als vollwertigen **Node** im
no0bz Command Center (NCC) betreibt: Gerätedaten sammeln, an den NCC-Server senden, Warnungen
empfangen, Fleet-Chat nutzen.

---

## 1. Rahmenbedingungen

| Punkt | Festlegung |
|---|---|
| Zielgerät | Google Pixel 7 Pro (Tensor G2 / GS201), Android 17 |
| minSdk / targetSdk | 34 (Android 14) / 37 (Android 17) |
| Sprache / UI | Kotlin, Jetpack Compose, Material 3 Expressive |
| Verteilung | privat (signierte APK), kein Play Store |
| Server | eigener NCC-Server, erreichbar über seine Tailscale-Adresse (Port 8350) |
| Netz | Tailscale ist Pflicht – ohne Tailnet-Verbindung arbeitet die App nur lokal |
| Test | Android-Emulator (Pixel 7 Pro-Profil, API 37, Google Play Image) + echtes Gerät |

---

## 2. Funktionen

### 2.1 Gerätedaten

| # | Wert | Quelle in Android | Hinweis |
|---|---|---|---|
| 1 | Gerätename | `Settings.Global.DEVICE_NAME`, Fallback `Build.MODEL` | |
| 2 | RAM gesamt | `ActivityManager.MemoryInfo.totalMem` | |
| 3 | RAM belegt/frei | `MemoryInfo.availMem` | |
| 4 | Speicher gesamt | `StatFs(Environment.getDataDirectory())` | |
| 5 | Speicher belegt/frei | `StatFs.availableBytes` | |
| 6 | SoC-Modell | `Build.SOC_MANUFACTURER` + `Build.SOC_MODEL` | Mapping-Tabelle, z. B. `GS201` → „Google Tensor G2“ |
| 7 | Kern-Architektur | `/sys/devices/system/cpu/cpufreq/policy*` (Cluster), `cpuinfo_max_freq`, `Build.SUPPORTED_ABIS` | Tensor G2: 2× X1 / 2× A78 / 4× A55 |
| 8 | Kern-Auslastung | **eingeschränkt** | `/proc/stat` ist seit Android 8 für Apps gesperrt. Ersatz: Taktauslastung je Kern (`cur/max`) + geschätzte Gesamtlast. UI kennzeichnet das als „Taktlast“. |
| 9 | Kern-Takt | `/sys/devices/system/cpu/cpuN/cpufreq/scaling_cur_freq` | Im Emulator meist nicht verfügbar → „n/a“ |
| 10 | Akku-Status | `BatteryManager` (Ladestand, lädt ja/nein, Quelle, Gesundheit, Ladezyklen) | |
| 11 | Akku-Temperatur | `ACTION_BATTERY_CHANGED` → `EXTRA_TEMPERATURE` (1/10 °C) | |
| 12 | Android-Version | `Build.VERSION.RELEASE`, `SDK_INT`, Sicherheitspatch | |
| 13 | GPS | Fused Location Provider | nur bei aktivierter Heatmap, standardmäßig **aus** |

Zusätzlich sinnvoll (günstig mitzunehmen): Netzwerktyp (WLAN/Mobil), WLAN-Signal, Thermal-Status
(`PowerManager.currentThermalStatus`), Uptime.

### 2.2 Erfassung und Upload

- **Intervall** einstellbar: 30 s · 1 min · 2 min · 5 min.
- Erfassung läuft in einem **Foreground Service** (dauerhafte Benachrichtigung). Nötig, weil
  WorkManager-Jobs frühestens alle 15 Minuten laufen.
- Jeder Messpunkt bekommt eine `sample_id` (UUID) und wird zuerst **lokal in Room** gespeichert.
  Der Server dedupliziert über die `sample_id` – doppeltes Senden ist harmlos.
- **Upload-Regel** (Einstellung):
  - *Sofort* – sendet, sobald der Server erreichbar ist.
  - *Nur bei WLAN + Laden* (Standard) – der Foreground Service prüft bei jeder Messung, ob ein
    ungedrosseltes WLAN/Ethernet anliegt **und** das Gerät lädt (umgesetzt in M2 statt WorkManager,
    weil der Dienst ohnehin läuft). „Jetzt hochladen“ ignoriert die Regel.
  - Lebenszeichen gehen unabhängig von der Regel bei jeder Messung raus (wenige Hundert Byte).
- **Logdateien** je Tag:
  - `YYYY-MM-DD.gpx` – GPS-Track (nur wenn GPS aktiv).
  - `YYYY-MM-DD.jsonl` – Messwerte, eine Zeile pro Messpunkt.
  - Werden mit dem Upload an den Server übertragen und lokal nach Bestätigung aufgeräumt
    (Aufbewahrung einstellbar).

### 2.3 Live-Modus (drei Stufen)

| Stufe | Auslöser | Takt | Daten |
|---|---|---|---|
| ⚡ Lokal live | App im Vordergrund | 1 s | nur Anzeige in der App, nichts wird extra gesendet |
| 📡 Server live | Dashboard zeigt das Gerät an **oder** manuell eingeschaltet | 1–2 s | Streaming per WebSocket, GPS hohe Genauigkeit |
| 🌙 Hintergrund | sonst | 30 s – 5 min | lokal puffern, Upload nach Upload-Regel |

- „Server live“ startet **auf Abruf**: Der Server meldet `viewer.present`, sobald ein Dashboard
  das Gerät öffnet; ohne Zuschauer fällt das Gerät nach 30 s zurück.
- Option „Server live nur im WLAN“.
- Grobe Datenmenge: ~300 Byte/Messpunkt → ca. 0,5 MB pro Stunde Live bei 2 s.

### 2.4 Warnungen (über den NCC-Server, ohne Google)

- Neuer Zustellkanal **„App“** in der bestehenden `alert-policy` (neben Telegram), schaltbar im
  Dashboard und in der App.
- Zustellung über den dauerhaften WebSocket des Foreground Service.
- Benachrichtigungskanal mit hoher Priorität (Ton, Vibration, Sperrbildschirm).
- **Nachholen:** Nach jedem Reconnect fragt die App `/fleet/alerts` ab der letzten bekannten ID ab.
- Voraussetzungen, die die App beim Einrichten prüft und erklärt:
  - Akkuoptimierung für NCC „Nicht eingeschränkt“.
  - Tailscale als „Durchgehend aktives VPN“.
  - Benachrichtigungsberechtigung.

### 2.5 Fleet-Chat + Kamera

- Voller Chat wie im Dashboard: Nachrichten (Markdown), Teilnehmer, Anhänge ansehen/hochladen.
- Neue Nachrichten kommen per WebSocket statt Polling.
- Kamera über **CameraX**: Foto aufnehmen → Vorschau → Upload über `/fleet/chat/uploads`.
- Kamera auch für den **Kopplungs-QR-Code** (siehe 3.1).

### 2.6 GPS-Heatmap

- Standard **aus**; einschaltbar in App **und** Dashboard (beide Seiten sehen denselben Schalter).
- App sammelt Punkte nur bei aktivierter Heatmap; Hintergrund-Standort (`ACCESS_BACKGROUND_LOCATION`)
  wird erst beim Einschalten angefragt.
- Darstellung **nur im Dashboard** (Leaflet + Heatmap-Ebene, OSM-Kacheln), Zeitraumfilter.
- Löschen der GPS-Historie aus App und Dashboard möglich.

### 2.7 Tailscale-Pflicht

- Die App kann kein eigenes Tailnet aufbauen; die offizielle Tailscale-App wird vorausgesetzt.
- Prüfung beim Start und bei Netzwechsel: VPN-Transport aktiv **und** `GET /api/v1/status/live`
  auf der eingetragenen Server-Adresse antwortet.
- Ohne Verbindung: Sperrbildschirm mit Hinweis + Knopf „Tailscale öffnen“; Erfassung läuft lokal weiter.

### 2.8 Updates

- Optional: App-Updates über den bestehenden `releases`-Mechanismus des NCC-Servers.
  Die App lädt die APK und Android fragt nur „Installieren?“.

---

## 3. Anbindung an den NCC-Server

### 3.1 Was es schon gibt (ncc_server, API v1)

| Bereich | Endpunkte | Nutzung durch die App |
|---|---|---|
| Kopplung | `POST /agent-pairings/register`, `/{id}/approve`, `/{id}/claim` | App registriert sich, Dashboard bestätigt (QR-Code/Code), App holt ihr Agent-Token ab |
| Node | `POST /nodes/enroll`, `/nodes/heartbeat`, `GET /nodes/me` | Anmeldung und Lebenszeichen wie jeder Agent |
| Telemetrie | `POST /nodes/telemetry` (max. 100 Punkte / 2 MiB, `sample_id`-Dedupe) | Batch-Upload aus dem Puffer |
| Warnungen | `GET /fleet/alerts`, `GET/PUT /fleet/alert-policy` | Nachholen + Kanal-Schalter |
| Chat | `/fleet/chat/messages`, `/participants`, `/uploads`, `/messages/{id}/attachment` | Chat + Kamera-Upload |
| Releases | `releases`, `/fleet/nodes/{id}/update-check` | optionaler Updater |

### 3.2 Was am Server ergänzt werden muss

1. **Plattform `android`** – `NodeEnrollmentRequest.platform` erlaubt bisher nur
   `windows | linux | darwin`.
2. **Erreichbarkeit** – Server lauscht standardmäßig auf `127.0.0.1:8350`; für das Handy muss er
   (auch) auf seiner Tailscale-Adresse lauschen (Docker: `NCC_SERVER_HOST=0.0.0.0`).
3. **Chat mit Agent-Token** – `/fleet/chat/*` verlangt heute eine Dashboard-Identität. Lösung:
   gekoppeltes Android-Gerät wird einem Benutzer zugeordnet (Owner) und darf in dessen Namen chatten
   (eigener Scope am Token).
4. **WebSocket** `GET /api/v1/nodes/stream` (Agent-Token):
   - hoch: `telemetry.live`, `ack`
   - runter: `alert.new`, `chat.new`, `viewer.present`, `viewer.gone`, `config.update`, `ping`
5. **Alert-Kanal „App“** in `alert-policy`.
6. **Dateien-Upload** `POST /nodes/logs` für GPX/JSONL.
7. **GPS/Heatmap** – Speicherung der Punkte, Endpunkt für den Dashboard-Layer, Opt-in-Schalter pro Node.
8. **Dashboard** – Android-Node-Ansicht (Kerne je Cluster, Akku, Heatmap), Live-Zuschauer-Signal.

Rate-Limits: Heartbeat/Telemetrie per REST sind begrenzt (`limited(...)`) – Live-Daten laufen
deshalb ausschließlich über den WebSocket.

### 3.2a Umgesetzt in M2 (Branch `claude/android-node` im Server-Repo)

| Änderung | Datei | Grund |
|---|---|---|
| Plattform `android` erlaubt | `schemas.py` | Kopplung/Anmeldung der App |
| Online-Bewertung nach angekündigtem Intervall (`metadata.heartbeat_interval_seconds`, max. 600 s, Kulanz 2 Intervalle + 30 s) | `node_service.py` | Server erwartet sonst alle 10 s ein Lebenszeichen und meldet nach 30 s „offline“ – zu teuer für den Akku |
| Keine RAM-Warnung für Android | `alert_service.py` | Android hält RAM absichtlich mit Cache voll |
| Keine Warnung „keine aktuelle Telemetrie“ für Android | `alert_service.py` | Upload-Regel „WLAN + Laden“ verzögert Telemetrie bewusst |
| Tests | `tests/test_android_nodes.py` | Kopplung → Anmeldung → Lebenszeichen → Telemetrie, Online-Regel, Warnregeln |

Die Taktlast wird **nicht** als `cpu.percent` gesendet (sonst CPU-Warnungen), sondern unter
`android.clock_load`. `machine_id` beginnt mit `android-`, dadurch landet das Gerät automatisch in
der Dashboard-Gruppe „Mobil“ (`default-mobile`). GPX-Upload folgt mit der Heatmap (M5).

### 3.2b M3: Live-Modus + Warnungen (Branch `claude/android-live`, baut auf `claude/android-node` auf)

- **Live-Hub im Server-Prozess** (nur Arbeitsspeicher, keine Datenbank):
  - merkt sich die offenen App-Verbindungen je Node,
  - die Dashboard-Zuschauer je Node (laufen 15 s nach der letzten Abfrage ab),
  - den neuesten Live-Messpunkt je Node.
- **WebSocket `GET /api/v1/nodes/stream`** (Agent-Token im `Authorization`-Header).
- **Dashboard-Endpunkt `GET /api/v1/fleet/nodes/{id}/live`** liefert den neuesten Live-Punkt und
  meldet dabei „ich schaue zu“. Die Android-Ansicht im Dashboard fragt ihn alle 2 s ab, solange sie offen ist.
  Live-Punkte landen **nicht** in der Datenbank; die Historie bleibt bei den regulären Messpunkten.
- **Warnungen**: Nach jeder Warnprüfung (alle 30 s) vergleicht der Hub die aktiven Warnungen mit
  dem letzten Stand und schickt Neues/Behobenes an die Apps – unabhängig von Telegram.
  Beim Verbinden kommt ein `alert.snapshot` aller aktiven Warnungen (= Nachholen).
  Commander-Geräte sehen alle Warnungen, andere nur die ihrer eigenen Geräte.
- **Schalter**: `app_alerts_enabled` in den Warnregeln (Dashboard, Datenbank-Migration 0027) +
  „Warnungen aufs Handy“ in der App. Beide müssen an sein.
- Fernsteuerung per `config.update` folgt später (eigener Meilenstein).

### 3.2c M4: Chat, Kamera und Flotte

- **Chat-Zugang für die App**: `/api/v1/nodes/chat/*` (Agent-Token) – Nachrichten, Teilnehmer, Senden,
  Upload, Anhang laden. Nachrichten tragen das Gerät als Absender (`sender_node_id`); gehört das Gerät
  einem Dashboard-Konto, schreibt es in dessen Namen, sonst unter dem Gerätenamen.
- Neue Nachrichten gehen als `chat.new` über den Live-Kanal an alle verbundenen Apps.
- **Kamera**: statt CameraX startet die App die Kamera-App des Systems (weniger Code, keine
  Kamera-Berechtigung nötig). Fotos werden auf max. 2560 px verkleinert und als JPEG hochgeladen.
- **Flotte**: `GET /api/v1/nodes/fleet` liefert die Geräte, die das Handy sehen darf
  (Commander: alle; Gerät eines Freundes: nur dessen eigene).

### 3.3 WebSocket-Nachrichten

```json
// App → Server
{ "type": "telemetry.live", "recorded_at": "2026-11-08T12:00:00Z", "metrics": { "memory": { … }, "android": { … } } }
// Server → App
{ "type": "viewer.present", "interval_ms": 2000 }
{ "type": "viewer.gone" }
{ "type": "alert.snapshot", "alerts": [ { "alert_id": "…", "severity": "warning", "node_name": "Tower", "kind": "disk", "message": "…" } ] }
{ "type": "alert.new", "alert": { … } }
{ "type": "alert.resolved", "alert": { … } }
{ "type": "ping" }
// später
{ "type": "config.update", "heatmap_enabled": true, "interval_s": 60, "upload_rule": "wifi_charging" }
```

Keepalive alle 25 s; Reconnect mit exponentiellem Backoff (1 s → max. 60 s).

### 3.4 Metrik-Schlüssel (Vorschlag)

`device.name`, `os.version`, `os.sdk`, `soc.model`, `ram.total`, `ram.used`, `storage.total`,
`storage.used`, `cpu.cores`, `cpu.cluster.N.cores`, `cpu.cluster.N.max_freq`,
`cpu.core.N.freq`, `cpu.core.N.load_freq`, `battery.level`, `battery.charging`,
`battery.temp_c`, `battery.health`, `thermal.status`, `net.type`, `net.wifi_rssi`,
`gps.lat`, `gps.lon`, `gps.acc` (nur wenn Heatmap aktiv).

---

## 4. App-Architektur

```
app/
 ├─ ui/            Compose-Screens, Theme (an NCC-Dashboard angelehnt: Barlow / Barlow Condensed)
 ├─ collect/       Sensor-Leser (Memory, Storage, Cpu, Battery, Soc, Location)
 ├─ service/       MonitorService (Foreground, Typ location|specialUse), Live-Steuerung
 ├─ sync/          WorkManager-Upload, GPX/JSONL-Writer
 ├─ net/           Ktor-Client (REST + WebSocket), Tailscale-Check
 ├─ data/          Room (Messpunkte, Alerts, Chat-Cache), DataStore (Einstellungen)
 └─ pairing/       Kopplung, Token im Android Keystore (verschlüsselt)
```

Bibliotheken: Compose + Material 3, Navigation Compose, Room, DataStore, WorkManager, Ktor,
kotlinx.serialization, CameraX, ML Kit Barcode (QR), Play Services Location, Vico (Diagramme),
Hilt (DI).

## 5. Bildschirme

1. **Einrichtung** – Tailscale-Check → Kopplung (QR/Code) → Berechtigungen → Akkuoptimierung.
2. **Dashboard** – Kacheln wie im NCC-Dashboard: Gerät, RAM, Speicher, SoC, Kern-Cluster mit
   Takt-Balken, Akku + Temperatur; Live-Indikator.
3. **Kerne** – Detailansicht je Cluster, Verlauf.
4. **Chat** – Nachrichtenliste, Eingabe, Kamera/Galerie.
5. **Warnungen** – Liste, Filter, Quittieren.
6. **Einstellungen** – Intervall, Upload-Regel, Live-Optionen, Heatmap, Warnungen, Logs, Server.

## 6. Test im Emulator

- AVD „Pixel 7 Pro“, API 37, Google Play x86_64, WHPX-Beschleunigung (auf dem PC verfügbar).
- Tailscale aus dem Play Store im Emulator installieren und anmelden.
- GPS: GPX-Route über *Extended Controls → Location* abspielen (Heatmap-Test).
- Akku/Laden: `adb emu power ac on|off`, `adb emu power capacity 42`.
- WLAN/Mobil: `adb shell svc wifi enable|disable`.
- Erwartete Emulator-Lücken: Kern-Takt, SoC-Modell → Anzeige „n/a“.

## 7. Meilensteine

1. **M1 Grundgerüst** – Projekt, Theme, Dashboard mit lokalen Gerätedaten (1–12), läuft im Emulator.
2. **M2 Kopplung + Upload** – Server: Plattform `android` + Tailscale-Bind; App: Pairing, Heartbeat,
   Puffer, Upload-Regel, Logdateien.
3. **M3 Live + Warnungen** – WebSocket am Server, Live-Stufen, Alert-Kanal „App“.
4. **M4 Chat + Kamera** – Chat-Scope am Token, Chat-UI, CameraX-Upload.
5. **M5 GPS-Heatmap** – Opt-in, Erfassung, Dashboard-Layer.
6. **M6 Feinschliff** – Updater über NCC-Releases, Widgets/Quick-Settings-Kachel, Barrierefreiheit.

## 8. Entscheidungen

| Frage | Entscheidung (08.11.2026) |
|---|---|
| Wer darf das Handy koppeln und sehen? | Nur der Commander über das Dashboard. Kopplung und Ansicht sind an `require_commander_access` gebunden. |
| Aufbewahrung der GPS-Daten am Server | Mindestens **1 Jahr**. Löschen nur manuell oder durch eine spätere, ausdrücklich eingestellte Frist ≥ 1 Jahr. |
| Darf das Dashboard die App fernsteuern? | **Ja**: über `config.update` im WebSocket (Intervall, Upload-Regel, Live-Optionen, Heatmap, Warnungen). Änderungen werden in der App als Hinweis angezeigt und im Audit-Log des Servers festgehalten. |
