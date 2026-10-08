# ncc-core (0.6)

Der Rust-Core implementiert die lokale Update-Zustandsmaschine: Ein signiertes
Payload-Archiv wird per SHA-256 und Ed25519 geprüft, sicher in ein
versionsbezogenes Verzeichnis entpackt, bewusst aktiviert und beim fehlenden
Health-Signal zurückgerollt. Der separate Windows-Dienst heißt `NccCore`; er
startet ausschließlich einen zuvor aktivierten Payload und ersetzt den
bestehenden NCC-0.5-Agenten nicht.

```powershell
cargo test --manifest-path core/ncc-core/Cargo.toml
```

Die Ed25519-Prüfung ist an Version, SHA-256 und Artefaktgröße gebunden. Private
Signaturschlüssel gehören nie in dieses Repository.

Ein Payload meldet seinen erfolgreichen Start künftig über eine lokale,
geheimnisfreie Datei mit folgendem Inhalt an Core:

```json
{"payload_version":"0.6.0-beta.1","status":"ready"}
```

Nur die aktive Version mit Status `ready` gilt als gesund; jede andere Antwort führt
nach Ablauf des konfigurierten Zeitfensters zum Rollback.

Für die erste, parallele und harmlose Windows-Abnahme existiert
`scripts/start_ncc_core_test_migration.ps1`. Es installiert nur `NccCore` und einen
lokalen Test-Payload. Der NCC-0.5-Agent, seine Konfiguration, Pairing-Daten und
Telemetrie bleiben unangetastet.
