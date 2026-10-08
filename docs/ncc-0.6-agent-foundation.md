# NCC 0.6 – Agent Foundation

**Status:** Entwurf und Vorbereitungsphase. NCC 0.5 bleibt bis zu einem bewusst
geplanten Migrationsrelease vollständig unterstützt.

## Ziel

Der bisherige Agent ist funktional, aber seine Installation und Aktualisierung ist
zu eng an den Python-Checkout und teilweise an dieselbe Laufzeit wie der Server
gekoppelt. NCC 0.6 trennt deshalb den dauerhaften, kleinen Dienst vom eigentlichen
Telemetrieprogramm:

```text
NCC Core (kompiliert, dauerhaft) ── lokale IPC ──► NCC Telemetry Payload
        │                                               │
        ├── Konfiguration + Pairing                     ├── Provider / Hardware
        ├── Release-Download + Integritätsprüfung       ├── SQLite-FIFO
        ├── Start, Überwachung, Rollback                 └── HTTPS zu NCC Server
        └── Windows-Service / systemd
```

Der **NCC Core** wird ein kleiner statischer, plattformübergreifender Dienst
(voraussichtlich Rust). Er sammelt selbst *keine* Hardwaredaten und kennt keine
Dashboard-Funktionen. So bleibt der privilegierte, dauerhafte Teil klein und
auditierbar. Der austauschbare **Telemetry Payload** enthält Provider, Puffer und
Übertragungslogik. Er kann unabhängig aktualisiert oder bei einem fehlerhaften
Release zurückgesetzt werden.

## Nicht verhandelbare Regeln

1. Server und Agent besitzen stets getrennte Installationsverzeichnisse und
   getrennte Laufzeiten. Ein Agent-Update darf nie ein laufendes Serverpaket
   austauschen.
2. `agent.env`, Pairing-Geheimnis, lokale Zugangsdaten und der SQLite-Puffer werden
   durch Updates weder angezeigt noch ersetzt.
3. Ein Release wird zuerst vollständig heruntergeladen, per SHA-256 und Ed25519
   geprüft und dann atomar aktiviert. Bei fehlendem Gesundheitsnachweis rollt Core
   auf den vorherigen Payload zurück.
4. Der Server weist Updates nur aus; er kann sie nicht still auf ein Gerät drücken.
   Auto-Update ist pro Gerät und Kanal ausdrücklich aktivierbar.
5. NCC 0.5-Agenten bleiben mit API v1 kompatibel. Die 0.6-Umstellung ist opt-in,
   einzeln pro Gerät und rückgängig machbar.

## Core-Verantwortung

| Aufgabe | Core | Payload |
| --- | --- | --- |
| Start beim Systemstart | Ja | Nein |
| Update herunterladen / prüfen / aktivieren | Ja | Nein |
| Rollback | Ja | Meldet Gesundheitsstatus |
| Pairing-Dateien und Zugriffsrechte bewahren | Ja | Nutzt nur geladene Werte |
| CPU, GPU, RAM, Laufwerke, Netzwerk erfassen | Nein | Ja |
| SQLite-Telemetriepuffer | Nein | Ja |
| Kommunikation zum NCC-Server | Nur Update-Metadaten | Telemetrie / Heartbeat |

## Installationslayout

Windows:

```text
%ProgramData%\\no0bz\\NCC\\
  core\\ncc-core.exe
  config\\agent.env                 # vorhanden, niemals durch Update ersetzen
  state\\                           # Pairing, Core-Status, Rollback-Marker
  payloads\\0.6.0-beta.1\\          # unveränderlicher Payload
  payloads\\0.6.0-beta.2\\
  current -> payloads\\0.6.0-beta.2
  telemetry-buffer\\                # bestehender Puffer, migrationsfähig
```

Linux verwendet dieselbe Trennung unter `/opt/ncc/core`, `/opt/ncc/payloads`,
`/etc/ncc/agent.env` und `/var/lib/ncc-agent`.

## Signiertes Release-Manifest

Die erste implementierbare 0.6-Schnittstelle ist ein signiertes Manifest. Core
akzeptiert ausschließlich Artefakte, die zu Plattform und Architektur passen und
deren Hash sowie Signatur gültig sind. Das Format ist in
[`ncc-agent-release-manifest.schema.json`](ncc-agent-release-manifest.schema.json)
festgelegt.

Das Manifest enthält keine Tokens, Pairing-IDs oder Geräteinformationen.

## Referenzimplementierung

Die repository-interne Referenz unter `backend/ncc_core` implementiert bereits die
entscheidenden, plattformneutralen Zustandsübergänge: Artefakt per Hash prüfen,
stagen, als `awaiting_health` aktivieren und nach einem fehlerhaften
Gesundheitsnachweis zurückrollen. Sie wird von NCC 0.5 weder importiert noch als
Dienst installiert. Ihre Tests bilden den Vertrag ab, den der spätere kompilierte
Core erfüllen muss.

## Gesundheitsvertrag und Rollback

Nach dem Umschalten startet Core den neuen Payload und erwartet innerhalb von 90
Sekunden einen lokalen Gesundheitsnachweis mit Payload-Version und erfolgreicher
Initialisierung. Ein fehlender Nachweis, unerwarteter Exit oder wiederholte
Startschleifen führen zum automatischen Rückwechsel auf die vorherige Version.
Core schreibt dafür einen lokalen, geheimnisfreien Status:

```json
{
  "active_payload": "0.6.0-beta.2",
  "previous_payload": "0.6.0-beta.1",
  "last_update": "2026-10-08T12:00:00Z",
  "health": "healthy"
}
```

## Bestehende NCC-0.5-Geräte migrieren

1. Core wird zusätzlich zum vorhandenen 0.5-Agenten installiert, aber noch nicht
   aktiviert.
2. Core importiert ausschließlich Konfigurationspfad, Maschinen-ID und SQLite-Puffer
   aus der bestehenden Installation.
3. Der Nutzer bestätigt die Aktivierung im Dashboard oder lokal.
4. Core beendet den alten Agenten kontrolliert, startet den 0.6-Payload und prüft
   Heartbeat sowie Telemetrie.
5. Erst nach erfolgreicher Bestätigung wird der alte Dienst entfernt. Bei Fehlern
   bleibt oder wird der alte Agent wiederhergestellt.

## Physische Geräte und Dualboot

Ab 0.6 werden **Agent-Profile** (Windows, Linux, später Android) von einem
**physischen Gerät** getrennt. Ein Agent meldet zusätzlich eine normalisierte
SMBIOS-UUID, sofern das System sie sicher lesen kann. Der Server speichert nur einen
gehashten Gerätefingerabdruck. Profiles mit demselben Fingerabdruck können im
Dashboard zu einem Gerät wie `HorstPC` zusammengeführt werden.

Es gibt immer eine manuelle Zusammenführen-/Trennen-Funktion, weil VMs,
Mainboard-Wechsel und eingeschränkte Firmwaredaten Ausnahmen darstellen. Ist ein
Profil offline, während ein anderes Profil desselben Geräts online ist, entsteht
keine Offline-Warnung. Kapazitäten (CPU, RAM, Speicher) zählen in der
Flottenstatistik pro physischem Gerät nur einmal.

## Umsetzungsreihenfolge

1. Manifest, Signaturschlüssel, Artefakt-Builder und reine Core-Statusmodelle.
2. Separater Core-Dienst für Windows und Linux, zunächst ohne automatisches Update.
3. Payload-Staging, Health-IPC und Rollback.
4. Dashboard: Update-Kanal, Version, Health und manuelle Aktivierung.
5. Opt-in-Migration eines Testgeräts; danach Beta-Tester und erst zum Schluss
   produktive Geräte.
6. Datenmodell und UI für physische Geräte / Dualboot-Profile.

## Abnahmekriterien für die erste 0.6-Beta

- Ein Payload-Update kann einen Agenten aktualisieren, ohne NCC Server oder einen
  anderen lokalen Agenten zu beeinflussen.
- Absichtlich beschädigtes Artefakt wird vor Aktivierung abgewiesen.
- Absichtlich abstürzender Payload wird automatisch zurückgerollt.
- Pairing, Browser-Zugang, SQLite-Puffer und Dashboard-Name überleben Update und
  Rollback.
- Windows und Linux nutzen dieselbe Manifest- und Rollback-Semantik.
