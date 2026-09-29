# Einen Sensor-Provider hinzufügen

1. Lege im Paket `backend/ncc/collectors/` ein Modul an.
2. Erbe von `SensorProvider` und definiere `name`, `platforms`, `priority` und `interval`.
3. `is_available()` darf niemals wegen fehlender Hardware oder Imports auslösen.
4. `probe()` liefert `Capabilities`, einschließlich Grund und Installationshinweis.
5. `collect()` gibt ein JSON-kompatibles Dictionary zurück. Blockierende Prozesse
   immer mit fester Argumentliste, `shell=False` und Timeout starten.
6. Registriere die Instanz in `ProviderRegistry` und ergänze Mock-Tests.

```python
class ExampleProvider(SensorProvider):
    name = "example"
    platforms = {"linux"}
    priority = 60
    interval = 5.0

    def is_available(self) -> bool:
        return Path("/sys/example/value").is_file()

    def probe(self) -> Capabilities:
        available = self.is_available()
        return Capabilities(self.name, available, ["example"] if available else [],
                            None if available else "Kernel interface missing")

    def collect(self) -> dict[str, object]:
        return {"example": {"value": 42, "source": self.name}}
```

Mehrere Provider dürfen denselben Bereich liefern; die höhere Priorität gewinnt. Nutze
optionale Felder, gib die Quelle an und fange nur erwartbare Hardware-/Toolfehler ab.

