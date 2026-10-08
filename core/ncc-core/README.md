# ncc-core (0.6-Prototyp)

Der Rust-Prototyp implementiert ausschließlich die lokale Update-Zustandsmaschine:
Artefakt mit SHA-256 prüfen, in einen versionsbezogenen Ordner stagen, aktivieren und
bei einem fehlenden Health-Signal zurückrollen. Er ist **noch kein Windows-Dienst**
und wird von NCC 0.5 nicht gestartet.

```powershell
cargo test --manifest-path core/ncc-core/Cargo.toml
```

Der Prototyp enthält bereits die Ed25519-Prüflogik für einen exakt an Version,
SHA-256 und Größe gebundenen Release-Statement. Als Nächstes wird sie an den
Staging-Befehl und eine vertrauenswürdige Public-Key-Liste gebunden. Private
Signaturschlüssel gehören nicht in dieses Repository und werden erst vor einem
veröffentlichten 0.6-Release eingerichtet.

Ein Payload meldet seinen erfolgreichen Start künftig über eine lokale,
geheimnisfreie Datei mit folgendem Inhalt an Core:

```json
{"payload_version":"0.6.0-beta.1","status":"ready"}
```

Nur die aktive Version mit Status `ready` gilt als gesund; jede andere Antwort führt
nach Ablauf des späteren 90-Sekunden-Fensters zum Rollback.
