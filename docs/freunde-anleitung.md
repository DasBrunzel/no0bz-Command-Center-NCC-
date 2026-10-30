# NCC für Freunde

NCC (no0bz Command Center) zeigt dir in einem Dashboard, wie es deinem PC
geht: Temperaturen, Auslastung, Lüfter, Laufwerke, welches Spiel du spielst
und wie lange. Bei Problemen meldet es sich auf Wunsch per Telegram.

Dein PC verbindet sich dafür mit dem NCC-Server deines Freundes. Du siehst
dort nur deine eigenen Geräte.

## Was du brauchst

- Windows 10 oder 11 (64 Bit)
- Tailscale und die Freigabe des NCC-Servers, die du per Link bekommst
- den **Einladungscode** für dein Konto, z. B. `K7QP-2MXD-9RTB`
- das Setup `ncc-agent-setup-0.6.0-windows-x86_64.exe`

## 1. Tailscale einrichten

1. Tailscale von <https://tailscale.com/download> installieren und mit einem
   Konto deiner Wahl anmelden.
2. Den Freigabe-Link öffnen, den du bekommen hast, und **Accept** wählen.
   Danach erscheint der NCC-Server in deiner Tailscale-Geräteliste.

## 2. NCC installieren

1. Das Setup starten. Windows zeigt eventuell „Der Computer wurde durch
   Windows geschützt“, weil das Setup kein gekauftes Code-Zertifikat hat:
   **Weitere Informationen → Trotzdem ausführen**. Die Installation selbst
   ist vom Server-Besitzer signiert und prüft jedes spätere Update.
2. Die Server-Adresse ist bereits eingebaut, du musst nichts eintragen.
3. Lass **„PawnIO installieren“** angehakt. Ohne diesen signierten Treiber
   fehlen CPU-Temperatur, CPU-Leistung und Mainboard-Lüfter.
4. Am Ende öffnet sich der Browser mit dem Koppel-Link.

## 3. Konto anlegen und PC koppeln

1. Auf der Anmeldeseite **Registrieren** wählen.
2. Einladungscode, einen Benutzernamen (Kleinbuchstaben, Ziffern, `.`, `-`,
   `_`) und ein Passwort mit mindestens 12 Zeichen eingeben.
3. **Konto anlegen**. Oben erscheint „Gerät gekoppelt“, nach wenigen Sekunden
   ist dein PC unter **Geräte** zu sehen.

Später meldest du dich unter **Benutzerkonto** an. Den Koppel-Link findest du
jederzeit im NCC-Symbol im Infobereich unter **Gerät koppeln…**.

## 4. Telegram verbinden (optional)

1. Im Dashboard **Einstellungen → Telegram verbinden → Verbindungscode
   erzeugen**.
2. **In Telegram öffnen** und im Chat mit dem NCC-Bot **Starten** drücken.
3. Der Bot bestätigt die Verbindung. Ab jetzt bekommst du Warnungen deiner
   Geräte und montags einen Wochenrückblick. `/stop` trennt die Verbindung.

## Was du einstellen kannst

In der Geräteansicht deines PCs:

- **Lüfter und Sensoren benennen** (✎ in der Mainboard-Kachel), z. B. Lüfter 2
  als „CPU-Lüfter“.
- **Spielerkennung**: mit Spieltitel, nur „spielt gerade“ oder aus.
- **Gaming Mode**: schaltet sich beim Spielen automatisch ein und unterdrückt
  dann Warnungen wegen hoher Auslastung. Temperaturwarnungen kommen trotzdem.

## Datenschutz

- Der Server-Besitzer sieht deine Geräte und deren Werte, inklusive der
  Spieltitel. Andere Freunde sehen deine Geräte nicht.
- Er kann einzelnen Konten erlauben, die Statistiken aller Geräte zu sehen;
  die Geräte selbst bleiben dann trotzdem verborgen.
- NCC liest nur Werte aus; es verändert keine Lüfterkurven, Taktraten oder
  Einstellungen und greift nicht in Spiele ein.

## Deinstallieren

**Einstellungen → Apps → no0bz Command Center Agent → Deinstallieren.** PawnIO
bleibt installiert und kann dort getrennt entfernt werden.

---

## Für den Server-Besitzer

1. **Einladung erzeugen:** Dashboard → Einstellungen → Benutzerkonten →
   **Freund einladen**. Der Code gilt sieben Tage und genau einmal.
2. **Server freigeben:** In der Tailscale-Verwaltung unter **Machines** beim
   NCC-Server **Share…** wählen und den Link schicken. Eine Freigabe öffnet
   alle Dienste dieses Rechners für den Freund; mit einer Tailscale-ACL lässt
   sie sich auf Port `8350` beschränken.
3. **Setup bauen:** Das Freunde-Setup trägt die Server-Adresse fest in sich:

   ```powershell
   .\scripts\build_ncc_agent_setup.ps1 -Version 0.6.0 -DefaultServerUrl http://100.92.199.35:8350 -PrivateKey <Schlüssel> -ArtifactUrl <URL>
   ```

   Eine bestehende Installation behält bei Updates ihre bisherige Adresse.
4. **Rechte:** Freunde verwalten nur ihre eigenen Geräte. Releases, Gruppen,
   Grenzwerte und das Entfernen von Geräten bleiben beim Commander. Unter
   Benutzerkonten lässt sich pro Freund **Alle Statistiken** freigeben und im
   Aktionsmenü eines Geräts der **Besitzer** ändern.
