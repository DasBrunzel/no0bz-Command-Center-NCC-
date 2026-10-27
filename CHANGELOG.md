# Changelog

Alle wesentlichen Änderungen werden hier dokumentiert.

## [0.6.0-beta.8-dev.0] – Laufende Entwicklung

- Der Fleet Chat lädt Video-, Audio- und PDF-Anhänge erst beim Öffnen der
  Vorschau. Ein langer Verlauf löst dadurch keine unnötigen Mediendownloads aus.
- Fleet-Chat-Anhänge zeigen kleine Dateien in KB oder Byte statt irreführend
  als „0,0 MB“ an.
- Auf schmalen Bildschirmen bleiben im Fleet Chat der Nachrichtenverlauf und
  das Eingabefeld gemeinsam sichtbar; Nachrichtentext ist besser lesbar.
- Beim Wechsel zwischen Geräten zeigt die Netzwerk-Monatszahl keinen
  zwischengespeicherten Wert des zuvor ausgewählten Geräts mehr an.
- Agenten senden Herzschläge und wiederholen fehlgeschlagene Verbindungen
  unabhängig vom eingestellten Messintervall. Auch bei seltener Telemetrie
  bleibt der Online-Status aktuell und der Wiederverbindungsversuch pünktlich.
- Gepufferte Telemetrie wird erst entfernt, wenn der Server alle Messpunkte
  einer Sendung als übernommen oder bereits vorhanden bestätigt hat.
- Der Fleet Chat zählt beim Nachladen nur tatsächlich neue Nachrichten als
  ungelesen. Bereits gesendete oder zuvor geladene Nachrichten erhöhen den
  Zähler nicht noch einmal.
- Dashboard, Server, Python-Paket, Service-Integration und Core-Quellen tragen
  jetzt die gemeinsame Entwicklungsnummer. Die Übersicht „Installierte
  Komponenten“ zeigt zusätzlich die vom Server gemeldete Version und die
  tatsächlich installierten Agent-Versionen je OS-Profil. Ältere signierte
  Payloads und der 0.5-Rückfallagent behalten ihre eigenen Versionsangaben.
- Im Command Overview zeigen die Netzwerkzahlen und die Verlaufskurve jetzt
  dasselbe ausgewählte Gerät. Die Balken der Fleet-Verfügbarkeit bilden den
  echten Prozentwert ab statt künstlich schwankende Messwerte vorzutäuschen.
- Nach dem manuellen Zurücksetzen der Traffic-Statistik startet die
  Monatsberechnung mit dem ersten neuen Messpunkt. Ein Zählerstand vor dem
  Reset fließt nicht mehr erneut in die Anzeige ein.
- Der Live-Netzwerkverlauf der Statistik nutzt eine kompakte API, die nur
  Zeitstempel und Netzwerkwerte lädt. Prozesslisten und Hardware-Sensoren
  werden dafür nicht mehr für jedes Gerät übertragen.
- Im Fleet Chat bleibt eine gerade gesendete Nachricht sichtbar, auch wenn
  die erste Verlaufsabfrage erst danach antwortet.
- Dateidownloads im Fleet Chat behalten ihre temporäre Browser-Adresse bis
  nach dem Start des Speichervorgangs, statt sie sofort freizugeben.
- Ein Fehler der Warnungsabfrage verwirft geladene Fleet-Geräte nicht mehr;
  ein Fehler der Geräteabfrage lässt Warnungen und die angemeldete Ansicht
  bestehen. Nur ein echter HTTP-401-Fehler beendet die Sitzung.
- Die Statistik lädt Monatsverkehr für höchstens zwei Geräte gleichzeitig.
  Eine langsame Geräteabfrage hält die Werte aller anderen Geräte nicht mehr auf.
- Der Agent zählt abgeschlossene Messungen nun unabhängig von der Systemuhr.
  Nach einer Uhrzeitkorrektur laufen Uploads weiter; der noch leere
  Collector-Startzustand wird nicht als Telemetrie versendet.
- Wenn das Speichern einer Chat-Nachricht in der Datenbank fehlschlägt, entfernt
  NCC den bereits geschriebenen Anhang wieder. Dadurch sammeln sich bei
  Datenbankfehlern keine verwaisten Upload-Dateien an.
- OS-Profile eines Dualboot-PCs lassen sich im Fleet Explorer einem vorhandenen
  physischen Gerät zuordnen oder wieder lösen. Der Navigator zeigt das Gerät
  dann einmal und bevorzugt das gerade aktive Profil; Commander können zwischen
  den Profilen wechseln.
- Die Statistik „Netzwerk nach Gerät“ summiert die Monatswerte verknüpfter
  OS-Profile unter dem physischen Gerät und zählt dieses nur einmal.
- Ein Kontowechsel setzt Chat-Entwürfe und Anhänge zurück. Verspätete Antworten
  für ältere Nachrichten oder gesendete Nachrichten erscheinen nicht in der
  Sitzung des nächsten Benutzers.
- Inaktive Dualboot-Profile lösen keine Warnungen mehr durch alte CPU-, GPU-
  oder Agent-Messwerte aus, solange das andere OS-Profil online ist. Sind beide
  offline, bleibt die echte Offline-Warnung erhalten.
- Der Fleet Chat zeigt während der ersten Abfrage einen Ladezustand statt
  fälschlich einen leeren Verlauf und null Mitglieder. Antworten aus einer
  vorherigen Anmeldung überschreiben den Chat nach einem Kontowechsel nicht mehr.
- Die Backend-Typprüfung ist wieder fehlerfrei. Der Agent reicht seine
  Versionsangabe nun explizit weiter; Chat-, Benutzer- und Fleet-Abfragen
  verwenden passende Ergebnistypen.
- Antworten aus einem früheren Browser-Login werden nach erneutem Anmelden
  oder Abmelden verworfen. Das gilt auch dann, wenn sich der leere Token bei
  Cookie-Sitzungen nicht ändert.
- Die Unraid-Integration übernimmt die kumulativen Netzwerkzähler der
  Host-Schnittstelle in die Monatsstatistik. Bridge, physische NIC und virtuelle
  Docker-/Tailscale-Adapter werden nicht mehr mehrfach addiert; ältere APIs
  liefern weiterhin Live-Raten ohne erfundene Monatswerte.
- Fleet-Daten und Warnungen erscheinen nun sofort nach ihren Antworten. Langsame
  Einstellungsabfragen laufen unabhängig und halten den Fünf-Sekunden-Takt der
  Live-Anzeige nicht mehr an.
- Dashboard-Abfragen haben jetzt ein Zeitlimit; die aufwendigere Monatsstatistik
  erhält ein längeres. Einzelne fehlerhafte Konfigurationsabfragen blockieren
  nicht mehr alle erfolgreich geladenen Fleet-Daten. Bei Verbindungsfehlern
  wechselt die Live-Anzeige sichtbar auf „Verbindung unterbrochen“.
- Der Cookie-Login lädt das Dashboard auch dann neu, wenn der bisherige
  Legacy-Token bereits leer war. Während der Login-Maske pausiert das
  unauthentifizierte Fleet-Polling.
- Monatsverkehr wird in den Statistiken und Node-Ansichten automatisch als
  B, KB, MB, GB oder TB angezeigt. Kleine Werte erscheinen dadurch nicht mehr
  fälschlich als `0,00 TB` oder `0,0 GB`.
- Der Windows-Server-Watchdog prüft nun die tatsächliche Bind-Adresse aus
  `server.env` statt immer `127.0.0.1`. Zwei fehlgeschlagene Prüfungen sind
  nötig, bevor er NccServer neu startet. Server-Updates erneuern einen bereits
  installierten Watchdog automatisch.
- Der Server-Updater vergleicht alle installierten Dashboard-Dateien per SHA-256
  mit dem Git-Stand, einschließlich später geladener Chat-Module.
- Während Installation, Datenbankmigration und Abnahmetest hält der Server-Updater
  die Watchdog-Sperre. Der periodische Watchdog kann den Dienst dadurch nicht
  mitten im Update neu starten.
- Persönliche Dashboard-Konten mit Commander- und Beta-Tester-Rolle können nun in
  den Einstellungen verwaltet werden. Login und Passwortwechsel verwenden
  geschützte Browsersitzungen; das Sperren eines Kontos entzieht aktive Sitzungen.
  Einmalige Admin-Codes bleiben als Einstieg und Rückfall erhalten.
- Fleet-Chat-Nachrichten tragen den angemeldeten Benutzernamen. Ein vom Browser
  übermittelter Node-Name kann den Absender nicht mehr vortäuschen.
- Der Fleet Chat lädt ältere Nachrichten seitenweise und fragt neue Beiträge
  über einen Cursor ab. Mitglieder werden seltener geladen; ausgeblendete Tabs
  pausieren die Abfrage. Tagestrenner, neue-Nachrichten-Hinweis und eine
  mehrzeilige Eingabe erleichtern längere Unterhaltungen.
- Markdown-Nachrichten im Fleet Chat werden formatiert angezeigt. Eingebettetes
  HTML und externe Bilder bleiben deaktiviert; Links öffnen in einem neuen Tab.
- Die Migration `20261026_0018` verbindet Benutzerkonten mit Dashboard-Sitzungen
  und Chat-Nachrichten.
- Der Agent ermittelt die statische Host-Kennung nur noch beim Start. Wiederholte
  Heartbeats warten damit nicht auf einen erneuten Windows-CIM-Aufruf.
- Das Dashboard lädt Live-Nodes und Warnungen im kurzen Takt, Konto-, Release-
  und Einstellungsdaten nur noch jede Minute. In versteckten Tabs pausiert das
  Polling. Die gewählte Node lädt nach dem ersten Verlauf nur neue Messpunkte;
  Verbindungsfehler erscheinen als Verbindungszustand statt als Login-Maske.
- Das Dashboard übernimmt die dunkelgrüne „Alles im Blick“-Demo als neue
  Oberfläche: Navigation, Command Overview, Fleet Explorer, Node-Detail,
  Statistiken, Warnungen und Fleet Chat verwenden deren Layout und Design-Tokens.
  Demo-Telemetrie wurde nicht übernommen; alle angezeigten Werte und Aktionen
  bleiben an die produktiven NCC-Endpunkte gebunden.
- Monats-Traffic und Telemetrie-Verlauf werden in den Statistiken unabhängig
  geladen. Ein vorübergehender Fehler einer Abfrage entfernt damit keine bereits
  erfolgreich geladenen Monatswerte mehr.
- Monats-Traffic liest in der Datenbank nur Zeitstempel und Netzwerkzähler statt
  vollständiger Telemetrie-Datensätze. Das Dashboard berechnet die Monatswerte
  nacheinander und höchstens alle fünf Minuten; der Live-Verlauf lädt separat.
  Alte Messwerte offline gegangener Nodes erscheinen nicht mehr als Live-Traffic.
- Der Agent wählt den Netzwerkadapter nach aktuellem Datenverkehr statt nach
  dem höchsten Zähler seit dem Systemstart. Bei einem Adapterwechsel setzt die
  Monatsstatistik eine neue Zählerbasis, damit kein künstlicher Traffic entsteht.
  Live-Graphen richten Agent-Samples nach Zeit aus; offline gegangene Nodes
  fließen nicht mehr in aktuelle CPU-, RAM- und GPU-Werte ein.
- Der Windows-Server-Updater verwendet das mit dem Commit ausgelieferte
  Frontend-Bundle und verändert dadurch keine versionierten Builddateien mehr.
  Ein separater Update-Helfer sichert vorhandene lokale Dashboard-Dateien in
  einem separaten Sicherungsordner, bevor der Server aktualisiert wird.
- Der Server-Updater vergleicht das Dashboard im Repository, im installierten
  Python-Paket und in der laufenden HTTP-Antwort. Ein Dienstneustart mit einem
  veralteten Dashboard gilt dadurch nicht mehr als erfolgreiches Update.

- Das Fleet-Dashboard wurde auf die neue **Mission-Control**-Informationsarchitektur
  umgestellt: Zuerst erscheinen Fleet-Status, offene Ereignisse und Live-Traffic,
  danach ein gruppierter Fleet Explorer und schließlich die vollständige Detail- und
  Aktionsansicht der gewählten Node. Die Ansicht nutzt weiterhin ausschließlich
  echte NCC-API-Daten; Rollen, Themes, Gaming-Mode, Umbenennen, Releases und
  Geräteverwaltung bleiben unverändert verfügbar.

- Das komplette Fleet-Dashboard erhielt das neue **Command Deck**-Design:
  ein Live-Roster der Fleet, eine fokussierte Node-Arbeitsfläche für Compute,
  Speicher, GPU, Netzwerk und Storage sowie eine integrierte Ereignisleiste.
  Navigation, Karten, Statusflächen und mobile Darstellung wurden von Grund
  auf neu strukturiert. Die vorhandenen Node-Aktionen und Themes bleiben
  erhalten; Themes steuern weiterhin ausschließlich die Farbwelt.

- Windows-0.6-Payloads enthalten nun einen direkt eingebundenen, rein lesenden
  LibreHardwareMonitor-Helper. NCC ergänzt damit CPU-/GPU-Temperaturen, Leistung,
  Taktraten, Lüfter und weitere Board-Sensoren ohne einen separat gestarteten
  LHM-Webserver. Nicht verfügbare Sensoren bleiben ein sicherer Fallback auf die
  bisherigen psutil-, NVML- und Windows-GPU-Provider.
- Das Node-Dashboard zeigt für solche Windows-Agenten eine kompakte
  Live-Hardware-Sensorleiste mit CPU/GPU-Werten, Board-Lüfterstand sowie der Zahl
  erkannter Temperatur-, Lüfter- und Spannungsmessungen.
- `stage_ncc_core_local_release.ps1` erlaubt eine kontrollierte lokale Verteilung
  eines bereits signierten Payloads. Sie nutzt denselben Hash- und Ed25519-Check
  wie der Serverpfad und lässt den vorherigen Payload als Rollback erhalten.
- Der Windows-Payload-Builder fügt nun auch bei einem Conda-basierten
  Build-Python die SQLite-Erweiterung samt Laufzeitbibliothek explizit hinzu.
  Ohne diese Bibliotheken konnte ein gepackter Payload vor dem Health-Signal mit
  `ImportError: DLL load failed while importing _sqlite3` abbrechen.

- Der Windows-Servicewrapper meldet einen unerwartet beendeten NCC-Worker nun
  als echten Dienstfehler. Die bestehenden SCM-Recovery-Aktionen können den
  Dienst dadurch wieder starten, statt einen scheinbar sauberen Stopp zu sehen.
- Neuer lokaler `NCC Server Watchdog`: prüft die Readiness von NccServer alle
  fünf Minuten und startet ihn bei einem hängenden oder fehlenden HTTP-Worker
  kontrolliert neu. Die Prüfung erfolgt ausschließlich über `127.0.0.1` und
  öffnet keinerlei zusätzliche Netzwerkfläche.
  Die Installation verwendet `schtasks.exe` statt eines versionsabhängigen
  ScheduledTasks-Repetition-Objekts und funktioniert damit auch auf älteren
  Windows-Server-Modulen.

## [0.6.0-beta.7] - 2026-10-17

- Windows-Payload mit Start-Selbsttest vor dem Signieren; die Release-Beschreibung
  nennt außerdem die benötigten SQLite- und OpenSSL-Laufzeitbibliotheken.

## [0.6.0-beta.6] - 2026-10-17

- Reparatur des Windows-Payload-Pakets: SQLite-Erweiterung und benötigte
  Laufzeitbibliothek werden wieder mitgeliefert.

## [0.6.0-beta.5] - 2026-10-17

- Rein lesender LibreHardwareMonitor-Helper im Windows-Payload für CPU-/GPU-
  Sensoren; bisherige Telemetrie-Provider bleiben als Fallback erhalten.

## [0.6.0-beta.4] - 2026-10-11

### Fixed

- Der Windows-Core-Bootstrap registriert für `NccCore` nun dieselbe
  `PYTHONPATH`-Dienstumgebung wie der bestehende `NccServer`. Dadurch kann
  `pythonservice.exe` die Core-Serviceklasse auch unter `LocalSystem` laden;
  zuvor brach der Dienst noch vor dem Anlegen von `core.log` ab.

- Der Windows-Core-Bootstrap erkennt nun auch den älteren Task-basierten
  `NccAgent`. Nach einem gesunden Core-Start entfernt er diese Systemaufgabe
  kontrolliert, sodass keine Doppeltelemetrie entsteht; der Rollback stellt den
  ursprünglichen Task samt archivierter Konfiguration wieder her.

- Der Linux-Core-Bootstrap legt `/etc/ncc` nun als `root:ncc` mit Modus `0750`
  an. Dadurch kann der unprivilegierte Core die weiterhin geschuetzte
  `core.env` durchlaufen und lesen; zuvor schlug der Release-Update-Check auf
  frisch installierten Linux-Systemen mit `Permission denied` fehl.

- Der Linux-Core-Bootstrap erstellt den Download-Arbeitsordner jetzt direkt mit
  den Rechten des unprivilegierten `ncc`-Dienstkontos. Damit können
  freigegebene Payloads ohne nachträgliche Rechtekorrektur heruntergeladen
  werden.

- Der Windows-Core-Bootstrap übernimmt bei browsergepairten 0.5-Agenten das
  vorhandene lokale Agent-Credential ausschließlich in die ACL-geschützte
  `core.env`, damit die authentisierte Release-Abfrage funktioniert. Der Token
  wird nicht ausgegeben oder in das Bootstrap-Paket aufgenommen.
- Die Erstinstallation erkennt einen noch nicht vorhandenen `NccCore`-Dienst
  zuverlässig und registriert ihn direkt, statt ihn fälschlich aktualisieren zu
  wollen.
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

- `setup_ncc_windows_maintenance_ssh.ps1` richtet einen ausschließlich über
  Tailscale erreichbaren OpenSSH-Wartungszugang für Windows-NCC-Server ein.
  Der Zugang akzeptiert nur einen explizit übergebenen Public Key und sichert
  vorhandene Administrator-Schlüsseldateien vor einer Ergänzung.
  Fehlende Windows-OpenSSH-Hostschlüssel werden vor dem ersten Dienststart
  idempotent erzeugt.
  Bestehende, eingeschränkte Offsite-Backupregeln bleiben dabei aktiv; der
  aktuelle Administrator wird nur ergänzend freigegeben und erhält zusätzlich
  einen Standard-`.ssh/authorized_keys`-Eintrag.
  Die Firewall-Einschränkung verwendet nun auch auf älteren Windows-Server-
  NetSecurity-Modulen den kompatiblen Pipeline-Pfad.
  Eine verwaiste, nicht mehr auflösbare `nccbackup`-OpenSSH-Regel wird nur
  dann gesichert und entfernt, wenn das zugehörige lokale Konto tatsächlich
  fehlt; so kann Windows-OpenSSH nicht mehr mit Fehler 1332 beim Dienststart
  abbrechen. Der Taildrop-Empfänger bleibt davon unabhängig.
  `repair_ncc_windows_sshd_service.ps1` ist der kontrollierte Reparaturpfad
  für bereits bestehende Regeln, die `sshd` mit Windows-Fehler 1067 beenden:
  Es sichert die Konfiguration, entfernt nur den alten SSH/SFTP-Stanza und
  begrenzt den Dienst weiter auf den Wartungsbenutzer.
  `debug_ncc_windows_sshd_as_system.ps1` liefert bei Windows-Fehler 1067 die
  entscheidende Diagnose unter `LocalSystem`, ohne die bestehende SSH- oder
  Firewall-Konfiguration zu ändern.
  Die temporäre Diagnose-Startdatei liegt dafür ebenfalls unter `ProgramData`,
  damit `LocalSystem` nicht am geschützten Benutzer-Tempordner scheitert.
  Ein Startmarker und `whoami` unterscheiden zusätzlich einen Fehler des
  Aufgabenplaners eindeutig von einem Fehler innerhalb von `sshd`.
  `repair_ncc_windows_sshd_acl.ps1` repariert bei einem fehlenden
  `LocalSystem`-Zugriff die Standard-ACLs des OpenSSH-ProgramData-Ordners
  (ausschließlich `SYSTEM` und lokale Administratoren) und sichert sie vorher.
  `reinstall_ncc_windows_openssh_server.ps1` ist der datengesicherte
  Letztreparaturpfad für einen weiterhin mit 1067 scheiternden Windows-
  OpenSSH-Dienst: nur die Server-Komponente wird neu installiert; der Zugang
  bleibt auf Tailscale und den aktuellen Wartungsbenutzer begrenzt.

- `debug_ncc_windows_sshd.ps1` erfasst einen kurzlebigen, nicht verändernden
  Vordergrund-Diagnoselauf für einen fehlschlagenden Windows-OpenSSH-Dienst.

- `finalize_ncc_core_linux_migration.sh` beendet die Parallelphase eines
  Linux-0.5-Agenten kontrolliert: Es prüft zunächst den gesunden Core-Payload,
  archiviert die alte Konfiguration, deaktiviert den Legacy-Dienst und stellt
  ihn bei einem fehlschlagenden Nachtest automatisch wieder her.

- `build_ncc_payload_linux.sh` erzeugt einen quellcheckoutfreien Linux-x86_64-
  Telemetrie-Payload. Die Signatur erfolgt getrennt auf HorstPC über
  `sign_ncc_payload_artifact.ps1`; der private Release-Schlüssel bleibt dadurch
  außerhalb von Linux-Buildsystemen und Agenten.
- Linux erhält einen eigenständigen 0.6-Core-Bootstrap: Der neue Builder
  `build_ncc_core_linux_bootstrap.sh` paketiert einen Linux-x86_64-Core, die
  systemd-Unit und nur den öffentlichen Release-Schlüssel. Der Installer
  `install_ncc_core_linux_bootstrap.sh` übernimmt das bestehende lokale
  Browser-Credential, prüft einen bewusst zugewiesenen signierten Linux-Payload
  und archiviert den 0.5-Agenten erst nach einem erfolgreichen Healthcheck.

- `build_ncc_core_bootstrap.ps1` erstellt ein kompaktes Windows-Bootstrap-ZIP
  für bestehende NCC-0.5-Geräte. Es enthält den kompilierten NccCore, die
  minimale Windows-Dienstlogik und ausschließlich den öffentlichen
  Release-Verifikationsschlüssel — keinen privaten Signaturschlüssel.
- `install_ncc_core_bootstrap.ps1` übernimmt die vorhandene Agent-Identität,
  akzeptiert nur einen zuvor im Dashboard freigegebenen signierten Payload und
  entfernt den alten `NccAgent`-Dienst erst nach erfolgreichem Core-Healthcheck.
  Die frühere `agent.env` wird dabei als rückholbare Sicherung abgelegt.
- `initialize_ncc_release_signer.ps1` erstellt einen dauerhaften,
  passphrasengeschützten Ed25519-Release-Signierer mit restriktiven Windows-ACLs
  und gibt ausschließlich dessen öffentlichen Verifikationsschlüssel aus.
- Die Update-Freigabe im Dashboard verwendet bei mehreren kompatiblen Releases
  eine sichtbare Auswahl statt einer manuell einzutippenden Release-ID.
- `update_ncc_server_release_distribution.ps1` ermoeglicht ein begrenztes,
  vorab gesichertes Windows-Server-Update fuer die Dashboard-Release-Verteilung,
  ohne Agenten oder deren Konfiguration anzufassen.

### Changed

- Die Linux-Core-Installation übernimmt das bestehende lokale
  Agent-Credential sicher in die gruppengeschützte `core.env`, damit
  browsergepairte 0.5-Agenten authentisiert nach freigegebenen Releases suchen
  können. Das ursprüngliche `agent.env` bleibt bis zu einer bewussten Migration
  unverändert.

## [0.6.0-beta.3] - 2026-10-09

### Fixed

- Der signierte Payload übernimmt die durch NccCore verifizierte
  Manifest-Version für seinen Health-Record. Dadurch wird ein freigegebenes
  Release nicht mehr wegen einer fest einkompilierten Fallback-Version unnötig
  zurückgerollt.
- Ein Release, das bereits seinen Health-Check nicht bestanden hat und
  zurückgerollt wurde, wird beim nächsten NccCore-Start nicht erneut in einer
  Update-Schleife versucht.
- `repair_ncc_core_orphan_payloads.ps1` entfernt ausschließlich verwaiste
  Test-Payload-Prozesse im NCC-Core-Zustandsordner und startet den zuletzt
  gesunden Payload kontrolliert neu.

### Added

- Read-only-Diagnose `diagnose_ncc_duplicate_telemetry.ps1` zeigt die
  relevanten NCC-Dienste, Payload-Prozesse und NCC-Aufgaben, ohne Token oder
  Pairing-Geheimnisse auszugeben.

## [0.6.0-beta.2] - 2026-10-09

### Added

- Erster veröffentlichter, signierter Windows-x86_64-Payload als GitHub-
  Pre-Release `v0.6.0-beta.2`. Das zugehörige Manifest ist für die bewusste
  Registrierung und Update-Freigabe im NCC-Dashboard vorgesehen.
- Sicheres Diagnose- und Reparaturskript für die Zugriffsrechte des lokalen
  Release-Signierers, ohne privaten Schlüssel oder Passphrase auszugeben.

### Fixed

- Der Payload-Build erkennt fehlende erhöhte Rechte vor dem zeitaufwendigen
  PyInstaller-Build und prüft den Zugriff auf den privaten Signaturschlüssel
  vor dem Paketieren.
- Signierer-ACLs werden für den Ordner und jede vorhandene Schlüsseldatei
  getrennt gesetzt. Zugriff bleibt auf `SYSTEM` und lokale Administratoren
  begrenzt.

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

