# Windows-Agent-Installer: Abnahme auf einem Test-PC

Diese Prüfung benötigt einen entbehrlichen Windows-PC oder eine Windows-VM mit
Desktop. Die CI prüft Dienst, Installation, Migration, Updates, Rollback,
Tray-Prozess und Deinstallation. Nur eine echte Benutzersitzung kann das
Infobereich-Menü und das Verhalten nach einem Hybrid-Herunterfahren belegen.

## Voraussetzungen

- Einen frisch gebauten, signierten NCC-Agent-Installer und dessen
  `*.manifest.json` und `*.sha256` verwenden. Die Versionsnummer vor dem Test
  notieren. Auf einem Produktivgerät keine Test-Installer aus der CI einsetzen.
- Den Test-PC vor der Installation sichern oder einen VM-Snapshot anlegen.
- Falls das Dashboard geöffnet werden soll, muss die angegebene Server-URL vom
  Test-PC erreichbar sein. Für den Dienst- und Tray-Start reicht auch eine
  lokale Test-URL; das Dashboard öffnet dann zwar im Browser, antwortet aber
  nicht.

## Installation und Tray

1. `setup.exe` mit einem normalen Benutzer starten und die UAC-Anfrage für
   die Installation bestätigen. Server-URL eingeben.
2. Nach Abschluss ohne erneute Benutzeraktion prüfen: `NccAgentCore` läuft,
   Starttyp ist automatisch oder verzögert automatisch, und genau ein NCC-Icon
   steht im Infobereich.
3. Rechtsklick auf das Icon: **Dashboard öffnen** öffnet die eingegebene URL
   im Standardbrowser. Der Tooltip nennt Version und Dienststatus.
4. **Beenden** zunächst mit **Nein** beantworten: Dienst und Icon bleiben.
   Danach **Ja** wählen: Dienst stoppt, Tray endet und das Icon verschwindet
   ohne manuelles Aktualisieren der Taskleiste. Es erscheint keine UAC-Anfrage.
5. Nach mindestens zehn Sekunden prüfen, dass der Dienst gestoppt bleibt.

## Neustart und Schnellstart

1. Windows normal neu starten und sich anmelden. Dienst und Tray müssen von
   selbst wieder laufen; genau ein Icon darf sichtbar sein.
2. Erneut über **Beenden** stoppen und den gestoppten Zustand prüfen.
3. Bei aktiviertem Windows-Schnellstart als Administrator ausführen:

   ```powershell
   shutdown.exe /s /hybrid /t 0
   ```

4. Gerät physisch wieder einschalten und sich anmelden. Auch jetzt müssen
   Dienst und Tray ohne Eingriff wieder laufen.

## Update und Deinstallation

1. Einen neueren signierten Installer über die konfigurierte HTTPS-Updatequelle
   bereitstellen. Der Dienst muss das Update selbst erkennen, ohne UAC
   installieren und danach wieder laufen. Der Tray muss in derselben
   Benutzersitzung zurückkehren. Pairing-ID und Agent-Daten bleiben gleich.
2. Über **Apps & Features** deinstallieren. Danach dürfen `NccAgentCore`, der
   Tray-Prozess, der Autostart-Eintrag `NccTray`, der Apps-&-Features-Eintrag
   sowie die Verzeichnisse `C:\Program Files\no0bz\NCC Agent` und
   `C:\ProgramData\no0bz\NCC Agent` nicht mehr vorhanden sein.
3. Falls auf demselben Gerät auch `NccServer` läuft, dessen Dienst,
   Konfiguration und Datenbank unverändert prüfen.

Jeden fehlgeschlagenen Punkt mit Windows-Version, Agent-Version, Zeitpunkt,
Screenshot und dem Setup-Log aus `%TEMP%` dokumentieren. Den Test-PC bei einem
Fehler nicht durch wiederholte Installationen bereinigen; zuerst den Zustand
sichern.
