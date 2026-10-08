# ncc-core (0.6-Prototyp)

Der Rust-Prototyp implementiert ausschließlich die lokale Update-Zustandsmaschine:
Artefakt mit SHA-256 prüfen, in einen versionsbezogenen Ordner stagen, aktivieren und
bei einem fehlenden Health-Signal zurückrollen. Er ist **noch kein Windows-Dienst**
und wird von NCC 0.5 nicht gestartet.

```powershell
cargo test --manifest-path core/ncc-core/Cargo.toml
```

Der künftige Schritt ergänzt eine Ed25519-Signaturprüfung, Payload-Start per lokaler
IPC und einen getrennten Windows-/systemd-Dienst. Private Signaturschlüssel gehören
nicht in dieses Repository und werden erst vor einem veröffentlichten 0.6-Release
eingerichtet.
