# Phase 8 – Lokale Fleet-Warnungen

## Ergebnis

Das Dashboard bewertet die zuletzt empfangene Telemetrie direkt in der Fleet-Ansicht.
Warnungen bleiben vollständig lokal im NCC-Dashboard: Es werden keine Daten an einen
externen Benachrichtigungsdienst übertragen.

## Auslöser

- Ein Gerät ist offline.
- CPU-, Arbeitsspeicher- oder GPU-Auslastung liegt bei mindestens 90 Prozent.
- Ein gemeldetes Laufwerk ist zu mindestens 90 Prozent belegt.

Ab 95 Prozent wird eine Auslastungswarnung als kritisch dargestellt. Der Bereich
aktualisiert sich mit dem vorhandenen Dashboard-Intervall und verschwindet automatisch,
sobald ein neuer Messwert wieder unterhalb des Grenzwerts liegt.

## Nächster Ausbau

Später können daraus vom Nutzer einstellbare Regeln und optionale externe
Benachrichtigungen entstehen. Die lokale Warnübersicht ist dafür bewusst die sichere
Grundlage.
