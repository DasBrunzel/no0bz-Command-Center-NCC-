# Telegram-Warnungen einrichten

NCC kann Warnungen ausschließlich über deinen eigenen Telegram-Bot an dich senden.
Der Bot-Token liegt danach nur in `%ProgramData%\no0bz\NCC\config\server.env` auf
HorstServer und wird weder im Dashboard noch in Logs angezeigt.

1. In Telegram `@BotFather` öffnen und mit `/newbot` einen Bot anlegen.
2. Den von BotFather angezeigten Token kopieren, aber nicht in einen Chat oder Browser
   einfügen.
3. Den eigenen neuen Bot öffnen und ihm `/start` senden.
4. Auf HorstServer als Administrator
   `scripts\configure_ncc_telegram.ps1` ausführen und den Token verdeckt eingeben.

Das Skript liest die Chat-ID direkt aus deiner `/start`-Nachricht, schreibt die
Konfiguration geschützt und startet nur den NCC-Serverdienst neu. Beim ersten aktiven
Ereignis folgt eine Telegram-Warnung; nach der Entspannung wird eine Entwarnung gesendet.
