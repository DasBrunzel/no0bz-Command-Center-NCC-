# Contributing

Danke für Beiträge zu NCC. Öffne bei größerer Hardwarearbeit zuerst ein Issue. Halte
Provider optional, lokal und fehlertolerant; neue externe Telemetrie ist nicht zulässig.

1. Forke das Repository und erstelle einen fokussierten Branch.
2. Ergänze Tests für neue API-, Security- und Providerpfade.
3. Führe `ruff check backend tests scripts`, `mypy`, `pytest -q`,
   `pnpm run typecheck` und `pnpm run build` aus.
4. Nutze Conventional Commits (`feat:`, `fix:`, `docs:`, `test:`).
5. Ergänze `CHANGELOG.md` und dokumentiere echte Hardwaretests samt OS/Treiber.

Keine Tokens, Hardware-Reports mit Seriennummern oder persönlichen Chat-/Upload-Dateien
committen. Mit einem Beitrag stimmst du der Veröffentlichung unter MIT zu.

