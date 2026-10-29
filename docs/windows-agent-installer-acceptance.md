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
   steht im Infobereich. Das gilt auch bei einer stillen Neuinstallation aus
   einer angemeldeten Benutzersitzung.
3. Rechtsklick auf das Icon: **Dashboard öffnen** öffnet die eingegebene URL
   im Standardbrowser. Der Tooltip nennt die unter Apps & Features installierte
   Setup-Version und den Dienststatus. Der Payload kann eine andere Version
   tragen und erscheint weiterhin in der Agent-Telemetrie.
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

## Abnahmeprotokoll

### 29.10.2026 – Windows-11-Pro-VM `DESKTOP-LACED10`

Unsignierte Entwicklungs-Setups `0.6.0-beta.8-dev.1` und `-dev.2` aus Commit
`f3ccf34`, Start-Payload `0.6.0-beta.7`, NCC-Server auf Commit `323ffb8`.
Die VM hatte kein Visual C++ Redistributable installiert.

| Punkt | Ergebnis |
| --- | --- |
| Interaktive Erstinstallation | Bestanden nach Commit `1ab6da6`. Zuvor startete `ncc-core.exe` mangels `VCRUNTIME140.dll` nicht. |
| Pairing-Link und Kopplung | Bestanden. Der Link wurde über **Gerät koppeln…** im Tray geöffnet; danach Enrollment und laufende Telemetrie. |
| Abgelaufene Pairing-Anfrage | Bestanden mit dem aktualisierten Server; die Anfrage wurde nach 15 Minuten wieder geöffnet. Der alte Payload endete bis dahin bei jeder 410-Antwort. |
| Dienst und genau ein Tray nach Installation | Bestanden. |
| Einzelinstanz | Bestanden; ein zweiter Tray desselben Benutzers aus einer anderen Sitzung endete sofort. |
| **Beenden** mit **Nein** und **Ja** | Bestanden; der Dienst blieb über 20 Sekunden gestoppt, ohne Wiederherstellung durch die Dienstverwaltung. |
| Normaler Neustart | Bestanden; Dienst (verzögert automatisch) und genau ein Tray kamen ohne Eingriff zurück, die Kopplung blieb erhalten. |
| Manuelles stilles Upgrade `dev.1` → `dev.2` | Bestanden; Pairing-ID, Maschinen-ID und Agent-Zugang blieben gleich. Da Setup über SSH lief, startete der neue Tray in der SSH-Sitzung statt im Desktop. |
| Deinstallation | Bestanden; Dienst, Tray, Autostart, Apps-&-Features-Eintrag, beide Agent-Verzeichnisse, Setup-Übergabeverzeichnis, Aufgabe und Firewall-Regel waren entfernt. |
| Hybrid-Herunterfahren | Auf der VM nicht geprüft; siehe HorstPC. |
| Automatisches Update über die signierte HTTPS-Updatequelle | Bestanden am selben Tag mit dem Pre-Release `v0.6.0-beta.8-dev.2`: Ein frisch installiertes Setup `dev.2` lud 30 Sekunden nach dem Dienststart das signierte Setup `dev.3` aus dem Feed, installierte es ohne UAC und aktivierte den mitgelieferten Payload `0.6.0-beta.8-dev.2` gesund; `0.6.0-beta.7` blieb als Rückfallversion. Der Tray kehrte in der Desktop-Sitzung zurück. Ein manueller Dienstneustart während der Installation störte das Ergebnis nicht. Anschließend gelang das Browser-Pairing mit dem neuen Payload. |

### 29.10.2026 – Migration auf HorstPC

Signiertes Setup `0.6.0-beta.8-dev.4` (Commit `37807a8`) mit Payload
`0.6.0-beta.8-dev.2` über eine bestehende Installation aus `NccCore` mit Payload
`0.6.0-beta.7` und deaktiviertem `NccAgent`. Kein `NccServer` auf dem Gerät;
Windows-Schnellstart aktiv, Dualboot über einen Bootloader.

| Punkt | Ergebnis |
| --- | --- |
| Interaktives Setup ohne Server-URL | Bestanden; die Adresse wurde aus der alten Konfiguration übernommen. |
| Übernahme von Identität und Zugang | Bestanden; das bestehende Gerät liefert im Dashboard weiter Daten, ohne neues Pairing. Tray und Status melden das Gerät als gekoppelt. |
| Entfernen der Altinstallation | Bestanden; `NccCore`, `NccAgent`, alte Agent-Konfiguration und `venv` sind entfernt. `release-signer` blieb unverändert. |
| Dienst, Payload und Tray | Bestanden; `NccAgentCore` läuft, Payload `0.6.0-beta.8-dev.2` ist gesund, ein Tray in der Konsolensitzung. |
| Herunterfahren mit Schnellstart | Ausstehend. |
