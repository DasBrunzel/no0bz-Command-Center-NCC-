# no0bz Command Center (NCC)

![Version](https://img.shields.io/badge/Version-0.7.1-ff334f)
![Python](https://img.shields.io/badge/Python-3.10%2B-3776ab)
![License](https://img.shields.io/badge/license-MIT-green)

Selbst gehostetes Monitoring für PCs, Server und Homelabs: ein dauerhaft
laufender Server (Python/FastAPI, PostgreSQL), GUI-lose Windows- und
Linux-Agenten, eine Unraid-API-Integration und ein gemeinsames Web-Dashboard.
Keine externe Telemetrie, Zugriff lokal oder über Tailscale.

> **Stand 0.7.1.** Server und Dashboard tragen `0.7.1`, Änderungen stehen im
> [CHANGELOG](CHANGELOG.md). Agenten, NCC Core und Payload stehen bei `0.6.2`;
> welche Version ein Gerät tatsächlich ausführt, zeigt das Dashboard aus
> seinem signierten Payload-Manifest. Der Server akzeptiert 0.5- und
> 0.6-Agenten parallel. Die NCC-0.4-Starter bleiben nur als
> Kompatibilitätsschicht erhalten.

## Server

Der Server ist eine separate, GUI-lose Anwendung. Er nimmt Telemetrie von
Windows- und Linux-Agenten sowie der Unraid-API entgegen und liefert das
Dashboard aus. Er kann bei Bedarf zusätzlich selbst als Agent aufgenommen
werden. PostgreSQL, Migrationen und Server starten gemeinsam mit Docker Compose:

```powershell
$env:NCC_POSTGRES_PASSWORD = "ein-langes-eigenes-passwort"
$env:NCC_SERVER_DASHBOARD_TOKEN = "ein-langer-zufaelliger-dashboard-token"
docker compose up --build
```

Danach steht das Dashboard unter <http://127.0.0.1:8350> bereit. Status und
API-Dokumentation liegen unter `/api/v1/status/live` und `/api/docs`; alle
Dashboard-Endpoints mit ihren Rechten stehen in
[`frontend/API-MATRIX.md`](frontend/API-MATRIX.md). Für den Dauerbetrieb siehe
[Dauerbetrieb als Dienst](#dauerbetrieb-als-dienst), für das Update eines
bestehenden Windows-Servers
[`docs/deploy-0.7-horstserver.md`](docs/deploy-0.7-horstserver.md).

### Anmeldung und Rollen

Man meldet sich mit einem persönlichen Konto (Benutzername und Passwort) oder
einem einmaligen achtstelligen Admin-Code an; beides erzeugt eine
HttpOnly-Browsersitzung. Der frühere Dashboard-Token ist nur noch ein
technischer Rückfallzugang.

| Rolle | Darf |
|---|---|
| **Commander** | alles: Geräte, Konten, Einladungen, Releases, Warnregeln, Telegram |
| **Beta-Tester** | alles sehen, nichts ändern; nur den Gaming Mode schalten |
| **Freund** | nur eigene Geräte sehen und verwalten, eigene Warnungen und Telegram-Chat |

Commander verwalten Konten unter **Einstellungen › Konten & Einladungen**:
Konten anlegen, Rollen ändern, deaktivieren und deaktivierte Konten endgültig
löschen (nicht das eigene, nicht den letzten Commander, keine Konten mit
Geräten). Freunde registrieren sich mit einem sieben Tage gültigen
Einladungscode; Commander können ihnen die Statistik aller Geräte freigeben.
Persönliche Konten ändern ihr Passwort unter **Mein Konto**, andere Sitzungen
werden dabei abgemeldet. Anleitung für Freunde:
[`docs/freunde-anleitung.md`](docs/freunde-anleitung.md).

### Geräte aufnehmen

Neue Windows- und Linux-Agenten brauchen keinen kopierbaren Token. Der
Installer erzeugt eine geheime, 15 Minuten gültige Kopplungsanfrage und zeigt
einen Browser-Link. Wer den Link öffnet und sich anmeldet, gibt das Gerät frei;
das Dashboard zeigt **Wartet**, **Freigegeben** oder **Verbunden**. Commander
können eine Anfrage auch ablehnen. Gibt ein Freund frei, gehört das Gerät
seinem Konto.

Für Geräte ohne Kopplungslink erstellen Commander unter **Aufnahme** eine
Agent-Einladung mit Gültigkeit und Rolle (Commander oder Beta-Tester); der
Token wird genau einmal angezeigt und nur als Hash gespeichert. Wird ein Gerät
später neu gekoppelt, bleibt seine Maschinen-ID erhalten und der alte Zugang
wird widerrufen.

### Dashboard „Stellwerk“

Das Dashboard (`frontend/`, React 19, TypeScript, Vite) ist hell und dunkel,
auf dem Handy nutzbar und als App installierbar, mit Offline-Gerüst und
Warnungszahl am App-Symbol. Die Bereiche:

- **Lage:** Gleisbild aller Geräte nach Gruppen (Dualboot-PCs als Weiche),
  Störmelder für aktive Warnungen und Live-Verkehr der ganzen Fleet mit
  Verlauf der letzten 30 Minuten.
- **Geräte:** Liste mit Suche und Filtern; Commander ordnen Geräte über
  „Anordnen“ in Gruppen, legen Gruppen an und benennen sie um. Die
  Detailansicht zeigt Übersicht, Sensoren, Netzwerk mit Monatsverbrauch,
  Spiele, Updates und Verwaltung (Umbenennen, Rolle, Besitzer,
  Dualboot-Zuordnung, Gaming Mode, Entfernen).
- **Hardware:** Stunden-Statistik je Gerät oder Fleet: Auslastung,
  Temperaturen, Leistung, Energie und Rekorde.
- **Spiele:** Spielzeit mit Bestenliste, Verlauf, Wochentag-Uhrzeit-Heatmap
  und letzten Sitzungen. Erkannt werden Steam- und Battle.net-Spiele; der
  Gaming Mode dämpft währenddessen Last-Warnungen. Commander laden eigene
  Banner hoch oder suchen sie bei SteamGridDB
  (`NCC_SERVER_STEAMGRIDDB_API_KEY`).
- **Chat:** Fleet-Chat mit Tagestrennung, Anhängen und sicher gerendertem
  Markdown.
- **Aufnahme** und **Releases** (Commander und Beta-Tester): Kopplungen,
  Agent-Einladungen, Admin-Codes sowie signierte Payload-Releases und
  Update-Kanäle.
- **Einstellungen:** Mein Konto, Konten & Einladungen, Warnregeln, Telegram, Über.

Das Dashboard fragt Live-Daten regelmäßig ab und pausiert in ausgeblendeten
Tabs. Entwicklung, Tests und Architekturentscheidungen:
[`frontend/README.md`](frontend/README.md) und
[`frontend/DECISIONS.md`](frontend/DECISIONS.md).

### Warnungen und Telegram

Der Server überwacht Last, Temperaturen von CPU, GPU und jedem Laufwerk sowie
die **Agent-Gesundheit** unabhängig vom Zugriff auf das Gerät: fehlende frische
Telemetrie, alte Agent-Versionen, Doppelmeldungen und unplausible
Netzwerkzähler. Warnungen erscheinen im Störmelder und können über Telegram
zugestellt werden, auch pro Konto in einen eigenen Chat mit Wochenrückblick.
Einrichtung: [`docs/telegram-alerts.md`](docs/telegram-alerts.md).

### Windows-Hardwaresensoren

Der Windows-0.6-Payload enthält einen lesenden LibreHardwareMonitor-Helfer. CPU-
Temperatur und Paketleistung benötigen zusätzlich funktionierenden Low-Level-
Sensorzugriff über PawnIO. Fehlt dieser Zugriff, kann der Helfer GPU-Werte liefern,
während CPU-Sensoren nur `0` melden; NCC zeigt dafür keinen erfundenen Messwert an.
Mit `sc.exe query PawnIO` lässt sich der Treiberstatus prüfen. Installation oder
Reparatur des Treibers erfolgt separat mit Administratorrechten; NCC deaktiviert
dafür keine Windows-Schutzfunktionen. Hintergrund:
[LibreHardwareMonitor](https://github.com/LibreHardwareMonitor/LibreHardwareMonitor/releases).

### NCC 0.6 Agent Foundation

NCC 0.6 teilt den Agenten in einen kleinen dauerhaften **NCC Core** und einen
austauschbaren Telemetrie-Payload. Updates werden signiert, atomar
aktiviert und bei einem fehlerhaften Payload automatisch zurückgerollt. Bestehende
NCC-0.5-Agenten bleiben kompatibel und werden nur bewusst, einzeln pro Gerät
migriert. Ein physisches Gerät kann mehrere OS-Profile enthalten, etwa Windows
und CachyOS im Dualboot, und erscheint im Fleet Explorer nur einmal. Details:
[NCC 0.6 Agent Foundation](docs/ncc-0.6-agent-foundation.md).

### NCC 0.6: kontrollierte Payload-Updates

NCC 0.6 trennt den dauerhaften **NccCore** vom austauschbaren Payload. Der Core
akzeptiert ein Update nur, wenn alle Schutzschichten erfüllt sind: HTTPS-Download,
exakte Größe, SHA-256 und eine Ed25519-Signatur eines lokal vertrauenswürdigen
öffentlichen Schlüssels. Ein privater Signaturschlüssel gehört niemals auf einen
NCC-Server oder ein Zielgerät.

Signierte Payload-Manifeste aus den GitHub-Releases registriert der Server
alle 15 Minuten selbst, sofern ein vertrauenswürdiger Release-Schlüssel sie
signiert hat; Commander können ein Manifest unter **Releases** auch von Hand
registrieren. Jedes Gerät folgt im Kanal **Beta** oder **Stable** automatisch
dem neuesten Release und geht dabei nie zurück; eine feste Zuweisung bleibt
möglich. Erst beim nächsten kontrollierten NccCore-Start lädt und aktiviert
der Core das Release; schlägt dessen Health-Check fehl, bleibt die letzte
funktionierende Payload erhalten beziehungsweise wird zurückgerollt.

Den öffentlichen Schlüssel eines eigenen Release-Signierers installiert man
einmalig, erhöht und ohne private Schlüssel zu kopieren:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\install_ncc_core_trusted_key.ps1 -KeyId release-2026 -PublicKey BASE64_ED25519_PUBLIC_KEY
```

Unter Linux übernimmt dies `sudo ./scripts/install_ncc_core_trusted_key.sh
release-2026 BASE64_ED25519_PUBLIC_KEY`. Für die erste Migration stehen
`start_ncc_core_real_payload_test.ps1`,
`switch_ncc_core_to_primary.ps1` und
`rollback_ncc_core_to_agent.ps1` bereit. Der Wechsel wird erst nach einem
erfolgreichen Paralleltest ausgeführt; der 0.5-Agent bleibt bis dahin Rückfall.

Einen bestehenden Windows-NCC-Server aktualisiert
`update_ncc_server_release_distribution.ps1 -Branch main`. Es verlangt einen
sauberen Git-Checkout, sichert `server.env` und PostgreSQL vor der Migration,
prüft jede ausgelieferte Dashboard-Datei gegen den Git-Stand und anschließend
NccServer, Version und Release-Route. Agenten und ihre Konfiguration werden
dabei nicht angefasst.

Für den ersten dauerhaften Signierer auf einer vertrauenswürdigen Windows-
Release-Workstation erzeugt `initialize_ncc_release_signer.ps1` einen
passphrasengeschützten Ed25519-Privatschlüssel unter
`%ProgramData%\no0bz\NCC\release-signer`. Die Passphrase wird ausschließlich
von OpenSSL abgefragt und niemals an NCC übergeben. Anschließend wird **nur** der
ausgegebene öffentliche Schlüssel auf die jeweiligen NccCore-Installationen
verteilt. Der private Schlüssel bleibt auf der Release-Workstation.

Welche signierte Payload ein Gerät tatsächlich ausführt, zeigt seine
Agent-Version im Dashboard. Jedes Payload-Manifest verweist ausschließlich auf
HTTPS, enthält die exakte SHA-256-Prüfsumme sowie die Ed25519-Signatur mit
`ncc-release-2026`. Das private PEM und seine Passphrase gehören weder in Git
noch auf den NCC-Server.

Für ein vorhandenes Windows-Gerät mit NCC 0.5 baut
`build_ncc_core_bootstrap.ps1` ein kompaktes Bootstrap-ZIP. Auf dem Zielgerät
werden weder Rust noch ein Git-Checkout benötigt: Zuerst wird der freigegebene
Release im Dashboard dem bestehenden Node zugeteilt; danach wird das ZIP
entpackt und `install_ncc_core_bootstrap.ps1` erhöht ausgeführt. Der Bootstrap
übernimmt Token und Pairing-Identität, prüft den signierten Payload und entfernt
den alten `NccAgent`-Dienst beziehungsweise die ältere Systemaufgabe erst, wenn
NccCore gesund läuft. Für das unter `LocalSystem` laufende `pythonservice.exe`
setzt der Bootstrap die erforderliche isolierte `PYTHONPATH`-Dienstumgebung.
Die alte `agent.env` bleibt als datierte Sicherung erhalten.

### Eigenständiger Windows-Agent-Installer

`scripts/build_ncc_agent_setup.ps1` erzeugt aus dem signierten Start-Payload
eine eigenständige `setup.exe`. Ein Build-Befehl auf der Release-Workstation:

```powershell
.\scripts\build_ncc_agent_setup.ps1 -Version 0.6.2 -PrivateKey "C:\Pfad\zum\release-private.pem" -ArtifactUrl "https://example.org/ncc-agent-setup-0.6.2-windows-x86_64.exe"
```

Auf der Build-Maschine werden .NET SDK, Rust, Inno Setup und OpenSSL benötigt;
auf dem Ziel-PC sind sie im Installer beziehungsweise Payload enthalten. Der
Builder prüft den signierten Start-Payload und schreibt neben die `setup.exe`
eine SHA-256-Datei und ein signiertes Update-Manifest. Der private Schlüssel
bleibt auf der Build-Maschine. Das Update-Manifest muss über die konfigurierte
HTTPS-Updatequelle veröffentlicht werden. Für eine stille Erstinstallation:

```powershell
.\ncc-agent-setup-0.6.2-windows-x86_64.exe /VERYSILENT /SUPPRESSMSGBOXES /NORESTART /SERVERURL=https://ncc.example.org
```

Der Installer erlaubt normalen Benutzern am Dienst ausschließlich
Statusabfrage, Starten und Stoppen (`LCRPWP` im Windows-Dienst-Descriptor).
Ändern, Löschen und Austausch des Dienstes bleiben Administratoren vorbehalten.
Damit funktioniert „Beenden“ im Tray ohne UAC-Abfrage; ein manueller Stopp
löst keine Absturz-Wiederherstellung aus. Der Tray startet bei der Anmeldung
für alle Benutzer und prüft dann auch einen nach Schnellstart gestoppt
gebliebenen Dienst. Installations- und Upgrade-Tests laufen in isolierter
Windows-CI; die Bedienung des Tray-Menüs und ein echter Windows-Schnellstart
stehen noch zur Abnahme auf Zielhardware aus.
Die dafür vorgesehenen Schritte stehen in
[`docs/windows-agent-installer-acceptance.md`](docs/windows-agent-installer-acceptance.md).

### Wartungszugang für einen Windows-NCC-Server

`setup_ncc_windows_maintenance_ssh.ps1` richtet einmalig den Windows-Dienst
OpenSSH Server ein, hinterlegt einen angegebenen Administrator-**Public Key**
und beschränkt Port 22 auf das Tailscale-Netz (`100.64.0.0/10`). Es installiert
keinen NCC-Agenten und liest weder Passwörter noch private Schlüssel. So kann
der Server anschließend unabhängig von RDP über einen nachvollziehbaren,
privaten Wartungszugang administriert werden. Fehlende OpenSSH-Hostschlüssel
erzeugt das Setup vor dem ersten Dienststart automatisch. Bestehende NCC-
Offsite-Backupregeln für `nccbackup` bleiben erhalten; der aufrufende
Administrator wird lediglich zusätzlich in deren `AllowUsers`-Regel ergänzt.
Falls eine ältere, fehlerhafte `nccbackup`-OpenSSH-Regel Windows-OpenSSH mit
Fehler 1067 beendet, ersetzt `repair_ncc_windows_sshd_service.ps1` nach einem
Konfigurationsbackup ausschließlich diese eingehende SSH-Regel durch den
Wartungsbenutzer. Der tägliche `NccOffsiteTaildropReceiver` bleibt davon
unberührt, weil er nicht über SSH/SFTP arbeitet.

Falls `sshd` auf einem Windows-Server nicht startet, erzeugt
`debug_ncc_windows_sshd.ps1` vier Sekunden lang ein reines Vordergrund-Debuglog
und zeigt parallel mögliche Belegungen von TCP-Port 22. Es verändert den
installierten Dienst nicht.
`debug_ncc_windows_sshd_as_system.ps1` ergänzt dies bei einem Windows-Fehler
1067: Es startet die Diagnose kurz als `LocalSystem` (identisch zum Dienstkonto)
und zeigt anschließend dessen Debugausgabe; Konfiguration und Firewall bleiben
unverändert.
Wenn die `LocalSystem`-Diagnose selbst keine Datei unter `C:\ProgramData\ssh`
anlegen kann, stellt `repair_ncc_windows_sshd_acl.ps1` dort ausschließlich die
üblichen lokalen Zugriffsrechte für `SYSTEM` und die Administratorengruppe
wieder her, speichert vorher die vorhandenen ACLs und startet `sshd` erneut.
Falls `sshd.exe` im Vordergrund funktioniert, der Windows-Dienst aber weiterhin
mit 1067 beendet wird, sichert und installiert
`reinstall_ncc_windows_openssh_server.ps1` ausschließlich die optionale
OpenSSH-**Server**-Komponente neu. Es behält vorhandene öffentliche
Administratorschlüssel, verwendet eine frische Standardkonfiguration mit genau
einem Wartungsbenutzer und lässt Port 22 weiterhin nur aus Tailscale zu.

### Selbstheilung des Windows-NCC-Servers

`install_ncc_server_watchdog.ps1` installiert für `NccServer` eine lokale
SYSTEM-Aufgabe sowie eine Startaufgabe. Sie prüft alle fünf Minuten `/api/v1/status/ready` auf
der in `server.env` konfigurierten Serveradresse. Ein zweiter fehlgeschlagener
Prüfversuch bestätigt den Ausfall. Falls der Dienst zwar als *Running* gemeldet wird, aber der
HTTP-Worker nicht antwortet, startet sie nur `NccServer` neu und protokolliert
den Vorgang in `C:\ProgramData\no0bz\NCC\logs\server-watchdog.log`.
Der Watchdog wird bei einer erneuten Windows-Server-Installation automatisch
eingerichtet und bei Server-Updates aktualisiert.

Für vorhandene Linux-Geräte gibt es denselben kontrollierten Pfad als
`build_ncc_core_linux_bootstrap.sh`. Der Builder läuft auf einem Linux-x86_64-
Buildsystem und erzeugt ein `.tar.gz` mit NccCore, systemd-Unit und ausschließlich
dem öffentlichen Release-Schlüssel. Auf dem Zielgerät übernimmt
`install_ncc_core_linux_bootstrap.sh` das bereits browsergepairte Credential aus
dem geschützten Agent-Datenordner. Es akzeptiert nur einen zuvor im Dashboard
diesem Node zugewiesenen, signierten **Linux-x86_64-Payload**. Ohne eine solche
Freigabe oder bei fehlschlagendem Healthcheck bleibt der 0.5-Agent unverändert
aktiv. Nach Erfolg wird dessen `agent.env` datiert archiviert; der mitgelieferte
Rollback stellt sie wieder her.

Der Core läuft dabei bewusst als Systemkonto `ncc`: `/etc/ncc` ist nur für
`root` und diese Gruppe durchsuchbar, während `core.env` selbst mit `0640`
weiterhin ausschließlich für `root:ncc` lesbar bleibt.

Wurde ein Linux-Core-Payload anschließend ausreichend beobachtet, beendet
`sudo ./scripts/finalize_ncc_core_linux_migration.sh --expected-version <VERSION>`
die Parallelphase kontrolliert. Der Befehl prüft den Core vor und nach dem
Abschalten des alten Dienstes; bei einem Fehler wird der 0.5-Agent automatisch
wiederhergestellt.

### Unraid

Unraid wird ohne NCC-Agent über die offizielle Unraid-API integriert. NCC zeigt
Array- und Laufwerksbelegung, Temperaturen soweit verfügbar, VMs und Docker-
Container an. Laufende Workloads stehen immer oben. Die Unraid-Verbindung wird auf
dem NCC-Server konfiguriert; der API-Schlüssel wird nicht im Dashboard angezeigt.

### Neuer Windows-/Linux-Agent

Der Agent benötigt kein Browserfenster und keinen lokalen Webserver. Für eine
Tailscale-Verbindung auf Windows (PowerShell als Administrator):

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\install_ncc_service.ps1 -Component Agent -Tailscale -ServerUrl 100.64.0.10 -AgentMode Task
```

Unter Linux:

```bash
sudo ./scripts/install_ncc_agent_service.sh --tailscale 100.64.0.10
```

Für Tailscale existieren `start_ncc_agent_tailscale.bat` und
`start_ncc_agent_tailscale.sh`. Messwerte werden zuerst in einem begrenzten lokalen
SQLite-Puffer gespeichert und nach Verbindungsunterbrechungen automatisch übertragen.
Die vollständige Anleitung steht im [Phase-4-Bericht](docs/phase-4-agent.md).

### Dauerbetrieb als Dienst

Unter Windows werden Server oder Agent über einen Doppelklick installiert; die
PowerShell-Installation fordert bei Bedarf selbst Administratorrechte an:

```text
scripts\install_ncc_server_tailscale_service.bat
scripts\install_ncc_agent_tailscale_service.bat
```

Ohne Tailscale stehen `install_ncc_server_service.bat` und
`install_ncc_agent_service.bat` bereit. Unter Linux:

```bash
sudo ./scripts/install_ncc_server_tailscale_service.sh
sudo ./scripts/install_ncc_agent_tailscale_service.sh SERVER-NAME-ODER-IP
```

Die Installer bewahren vorhandene Konfigurationen und Pairing-Zugänge bei Updates. Normales
Deinstallieren entfernt nur den Dienst; `-Purge` unter Windows beziehungsweise
`--purge` unter Linux löscht auf ausdrücklichen Wunsch auch Konfiguration oder
Agent-Puffer. Status und Logs zeigt `ncc_service_status.bat` beziehungsweise
`ncc_service_status.sh`.

Eine Verbindung lässt sich ohne Änderungen mit `ncc-doctor` prüfen. Token sollten
über `NCC_DOCTOR_TOKEN` gesetzt werden, damit sie nicht in der Prozessliste stehen:

```powershell
$env:NCC_DOCTOR_TOKEN = "dashboard-token"
ncc-doctor server --server-url http://100.100.100.10:8350 --tailscale --allow-insecure-http
```

Alle Details stehen im [Phase-6-Bericht](docs/phase-6-services.md).

> Teile dieses Projekts entstanden mit KI-Unterstützung. Änderungen sollten wie jeder
> andere Beitrag geprüft und auf der Zielhardware getestet werden.

## Legacy-Schnellstart (NCC 0.4)

> Dieser Abschnitt dokumentiert nur die erhaltene NCC-0.4-Kompatibilität. Für neue
> NCC-0.5-Installationen nutze den Server-/Agenten-Dienst und das Browser-Pairing
> weiter oben.

### Windows 10/11

```powershell
git clone https://github.com/DasBrunzel/no0bz-Command-Center-NCC-.git
cd no0bz-Command-Center-NCC-
scripts\start_ncc_local.bat
```

### Linux

```bash
git clone https://github.com/DasBrunzel/no0bz-Command-Center-NCC-.git
cd no0bz-Command-Center-NCC-
chmod +x scripts/start_ncc*.sh
./scripts/start_ncc_local.sh
```

Öffne danach <http://127.0.0.1:8350>. Beim ersten Start erzeugt NCC `.env` und zeigt
das zufällige Token einmal in der Konsole. Das gebaute Frontend ist im Repository
enthalten; Node.js wird nur zur Frontend-Entwicklung benötigt.

Demo-Modus: setze `NCC_DEMO=1` in `.env`. LAN-Betrieb: setze bewusst `NCC_HOST=0.0.0.0`
und `NCC_MODE=server`; lies vorher [SECURITY.md](SECURITY.md).

### NCC-0.4-Kompatibilitätsmodi

Die bisherige NCC-Anwendung übernimmt je nach Starter weiterhin eine der drei
Legacy-Rollen. Diese Starter gehören noch nicht zur neuen NCC-0.5-Architektur:

| Rolle | Windows | Linux | Zweck |
|---|---|---|---|
| Local | `scripts\start_ncc_local.bat` | `scripts/start_ncc_local.sh` | einzelner PC, nur Loopback |
| Server | `scripts\start_ncc_server.bat` | `scripts/start_ncc_server.sh` | Dashboard und Sammelstelle im LAN |
| Client | `scripts\start_ncc_client.bat` | `scripts/start_ncc_client.sh` | sendet seine Telemetrie an den Server |
| Tailscale-Server | `scripts\start_ncc_tailscale_server.bat` | `scripts/start_ncc_tailscale_server.sh` | bindet ausschließlich an die Tailscale-IP |
| Tailscale-Client | `scripts\start_ncc_tailscale_client.bat` | `scripts/start_ncc_tailscale_client.sh` | verbindet sich über Tailscale-IP oder MagicDNS |

Beim Client-Start werden die Server-URL, beispielsweise
`http://192.168.1.10:8350`, und der `NCC_TOKEN` des Servers abgefragt. Server und
Client müssen denselben Token verwenden. Die Synchronisation läuft über Port 8350.

### Tailscale-Schnellstart

Tailscale muss auf Server und Client angemeldet und verbunden sein. Auf dem Server:

```powershell
scripts\start_ncc_tailscale_server.bat
```

Der Starter erkennt ausschließlich Adressen aus Tailscales CGNAT-Bereich
`100.64.0.0/10`, bindet NCC an diese Adresse und zeigt die fertige URL an. Existiert
noch kein Token, werden `.env` und `ncc-token-transfer.txt` erzeugt. Übertrage diese
Datei sicher auf den Client und starte dort:

```powershell
scripts\start_ncc_tailscale_client.bat
```

Alternativ können Ziel und Übergabedatei direkt angegeben werden:

```powershell
scripts\start_ncc_tailscale_client.bat 100.100.100.10 ncc-token-transfer.txt
```

Der Client prüft Adresse, Server-Modus und gemeinsamen Token vor dem eigentlichen
Start. Bei einem abweichenden Token oder gesperrten Port erscheint dadurch eine
konkrete Fehlermeldung statt einer stillen Verbindungswiederholung.

Nach dem Import sollte `ncc-token-transfer.txt` auf beiden Geräten gelöscht werden.
Der dauerhafte Token liegt in der von Git ausgeschlossenen `.env`. Tailscale-Grants
sollten TCP-Port 8350 nur für die vorgesehenen Clients freigeben.

### Legacy-Token-Verwaltung

Unter Windows öffnet `scripts\manage_ncc_token.bat` ein Menü. Unter Linux stehen
folgende Aufrufe zur Verfügung:

```bash
scripts/manage_ncc_token.sh generate
scripts/manage_ncc_token.sh show
scripts/manage_ncc_token.sh rotate
scripts/manage_ncc_token.sh export ncc-token-transfer.txt
scripts/manage_ncc_token.sh import ncc-token-transfer.txt
```

Eine Rotation macht den bisherigen Token sofort ungültig. Danach müssen die neue
Übergabedatei auf allen Clients importiert und alle NCC-Prozesse neu gestartet werden.

## Funktionen

- Zentraler Server für Windows-/Linux-Agenten und die Unraid-API, PostgreSQL mit Migrationen
- Echtzeit-CPU-, RAM-, Datenträger-, Netzwerk-, Akku-, GPU-, Sensor- und Prozessdaten
- Dashboard „Stellwerk“: hell und dunkel, mobil, als App installierbar
- Gruppen mit eigener Reihenfolge, anlegen und umbenennen; Dualboot-Profile als ein Gerät
- Live-Verkehr der ganzen Fleet, Netzwerkverlauf und Monatsverbrauch je Gerät
- Hardware-Statistik pro Stunde, Spielzeit-Statistik mit Steam- und Battle.net-Erkennung
- Warnungen für Last, Temperaturen und Agent-Gesundheit, Zustellung über Telegram
- Rollen Commander, Beta-Tester und Freund mit serverseitigem Schutz
- Browser-Pairing ohne kopierbare Tokens, Agent-Einladungen mit Rolle
- Signierte, automatisch verteilte Payload-Updates mit Rollback (NCC Core)
- Fleet-Chat mit Anhängen und sicher gerendertem Markdown
- Unraid-Übersicht für Laufwerke, Temperaturen, VMs und Docker-Container

## Konfiguration

Der Server liest `NCC_SERVER_*`-Werte, als Dienst unter Windows aus
`%ProgramData%\no0bz\NCC\config\server.env`. Die wichtigsten stehen in
[.env.example](.env.example): `NCC_SERVER_HOST`, `NCC_SERVER_PORT`,
`NCC_SERVER_DATABASE_URL`, `NCC_SERVER_DASHBOARD_TOKEN` und
`NCC_SERVER_NODE_OFFLINE_AFTER_SECONDS`; dazu optional
`NCC_SERVER_STEAMGRIDDB_API_KEY` für die Bannersuche und die Telegram-Werte aus
[`docs/telegram-alerts.md`](docs/telegram-alerts.md). Agenten nutzen
[ncc-agent.env.example](ncc-agent.env.example).

Die lokale 0.4-Anwendung liest `.env` mit `NCC_HOST`, `NCC_PORT`, `NCC_TOKEN`, `NCC_MODE`, `NCC_SERVER_URL`,
`NCC_UPLOAD_MAX_MB`, `NCC_UPLOAD_TOTAL_MB`, `NCC_RETENTION_HOURS`, `NCC_INTERVAL`,
`NCC_LHM_URL`, `NCC_DEMO` und `NCC_ALLOW_LOOPBACK_NO_TOKEN`.

## Unterstützte Hardware und Voraussetzungen

| Provider | Plattform | Werte | Voraussetzung/Rechte |
|---|---|---|---|
| psutil | Windows, Linux, macOS | CPU, RAM, Swap, Disks, Netz, Akku, Prozesse | keine Zusatztools |
| NVIDIA NVML | Windows, Linux | GPU, VRAM, Temperatur | NVIDIA-Treiber; `nvidia-ml-py` ist enthalten |
| Windows GPU Counters | Windows | AMD-, Intel- und NVIDIA-Name/Auslastung | aktueller Grafiktreiber, keine Administratorrechte |
| Linux AMDGPU | Linux | AMD-Auslastung, VRAM und Temperatur | aktiver `amdgpu`-Kerneltreiber |
| Linux hwmon | Linux, Raspberry Pi OS | Temperaturen, Lüfter/GPU je nach Treiber | Leserechte auf `/sys` |
| smartctl | Windows, Linux | Laufwerkszustand (Best Effort) | smartmontools, ggf. erhöhte Rechte |
| LibreHardwareMonitor | Windows | Temperaturen, Lüfter, Spannungen, CPU-/GPU-Leistung und Taktraten | direkt als rein lesender Helper im Windows-0.6-Payload enthalten |
| Demo | alle | vollständige synthetische Daten | `NCC_DEMO=1` |

Provider, die das aktuelle System nicht unterstützt, deaktivieren sich ohne Absturz und
erscheinen mit Grund im Hardware-Report.

Der Windows-0.6-Payload bringt `LibreHardwareMonitorLib` als kleinen, rein lesenden
Helper mit. Er läuft nur für eine Momentaufnahme, verändert **nie** Lüfterkurven,
Taktraten, Spannungen oder Firmware und ergänzt die vorhandenen psutil/NVML-Werte.
Ist ein Sensor oder der Helper nicht verfügbar, arbeitet der Agent unverändert mit
den bestehenden Providern weiter. Der bisher optionale lokale LHM-Webserver auf Port
8085 bleibt als Kompatibilitäts-Fallback erhalten. LibreHardwareMonitor steht unter
MPL-2.0; ein Hinweis ist in jedem Windows-Payload enthalten.

Für eine kontrollierte lokale Notfall- oder Testverteilung kann ein bereits
signiertes Archiv mit `scripts/stage_ncc_core_local_release.ps1` eingespielt
werden. Auch dabei validiert NccCore vor dem Entpacken zwingend SHA-256 und die
installierte Ed25519-Release-Signatur; der vorherige Payload bleibt als Rollback.

## NCC 0.6 Linux-Payloads

Ein Linux-Payload wird auf Linux mit
`scripts/build_ncc_payload_linux.sh --version <SemVer>` gebaut. Das Ergebnis ist
zunächst bewusst **unsigniert**. Das Windows-Skript
`scripts/sign_ncc_payload_artifact.ps1` signiert das fertige Archiv danach in einer
erhöhten PowerShell mit dem ausschließlich auf HorstPC liegenden privaten
Release-Schlüssel. So bleibt der Linux-Build reproduzierbar, ohne den privaten
Schlüssel auf einen Agenten oder in WSL zu kopieren.

## API der NCC-0.4-Kompatibilität

Die Server-API `/api/v1` ist unter `/api/docs` dokumentiert, ihre Rechte in
[`frontend/API-MATRIX.md`](frontend/API-MATRIX.md). Die folgende Tabelle gilt
nur für die erhaltene lokale 0.4-Anwendung:

| Methode | Pfad | Zweck | Schreibschutz |
|---|---|---|---|
| WS | `/ws/live` | Live-Snapshot | Token außerhalb erlaubtem Loopback |
| GET | `/` | Dashboard | nein |
| GET | `/api/metrics` | aktueller Snapshot | nein |
| GET | `/api/sensors/capabilities` | verfügbare Sensoren | nein |
| GET | `/api/nodes` | PC-Präsenz | nein |
| POST | `/api/nodes/register` | Node registrieren | Token + Rate-Limit |
| POST | `/api/nodes/telemetry` | Node-Snapshot | Token + Rate-Limit |
| GET | `/api/multipc/mode` | Betriebsmodus | nein |
| GET | `/api/auth/check` | Client-Verbindung und Token prüfen | Token |
| POST | `/api/profile` | Profil speichern | Token |
| GET | `/api/system/profile` | Hardware-Cache | nein |
| POST | `/api/system/profile/refresh` | Hardware neu erkennen | Token |
| GET | `/api/changelog` | Changelog als JSON | nein |
| GET | `/changelog` | Changelog als HTML | nein |
| GET | `/api/history?minutes=60` | lokale/Node-Historie | nein |
| POST | `/api/kill` | Prozess beenden | Token + Rate-Limit |
| GET | `/api/chat/messages` | Nachrichten | nein |
| POST | `/api/chat/send` | Nachricht senden | Token + Rate-Limit |
| POST | `/api/chat/upload` | Dateien hochladen | Token + Rate-Limit |
| GET | `/api/chat/files` | Dateien auflisten | nein |

## Entwicklung

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux: source .venv/bin/activate
python -m pip install -e ".[dev]"
pytest -q
ruff check backend tests scripts
mypy
cd frontend && pnpm install && pnpm run build && pnpm test
```

Die Datenbank schreibt in Batches von fünf Sekunden. Bei einem harten Absturz können
daher maximal ungefähr fünf Sekunden noch ungeflushter Messwerte verloren gehen.
Retention läuft geplant statt bei jedem Insert. Der In-Memory-Fallback ist auf 86.400
Punkte begrenzt.

## Benchmark

Lokale Messung am 29.09.2026 unter Windows/Python 3.13, 10 Läufe mit automatisch
erkannten Providern: Mittelwert 1.636,00 ms, P95 1.691,28 ms, Prozess-RSS 54,84 MB
und gemessene Prozess-CPU 38,3 %. Werte sind system- und providerabhängig. Reproduziere
sie mit `PYTHONPATH=backend python scripts/bench.py`; es werden bewusst keine
unbelegten Ressourcenversprechen gemacht.

Weitere Dokumente: [Architektur](docs/architecture.md),
[Provider hinzufügen](docs/adding-a-provider.md), [Plattform-Setup](docs/platform-setup.md),
[Security](SECURITY.md) und [Contributing](CONTRIBUTING.md).

## Versionierung

NCC verwendet ab Version `0.3.0` [Semantic Versioning](https://semver.org/):
`MAJOR.MINOR.PATCH`. Inkompatible Änderungen erhöhen MAJOR, neue kompatible
Funktionen MINOR und kompatible Fehlerkorrekturen PATCH. Server, Dashboard und
Release-Tags tragen dieselbe Versionsnummer; Agent, NCC Core und Payload haben
einen eigenen Versionsstrang, weil sie getrennt signiert und verteilt werden.

## Lizenz

MIT – siehe [LICENSE](LICENSE).

