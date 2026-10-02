[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$root = Join-Path $env:ProgramData "no0bz\NCC"
$configPath = Join-Path $root "config\server.env"

if (-not (Test-Path -LiteralPath $configPath)) {
    throw "NCC-Server-Konfiguration wurde nicht gefunden: $configPath"
}

Write-Host "[NCC] Lege zuerst in Telegram bei @BotFather einen Bot an."
Write-Host "[NCC] Sende deinem neuen Bot anschließend /start und drücke hier erst dann Enter."
$secureToken = Read-Host "Bot-Token" -AsSecureString
$tokenPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureToken)
try {
    $botToken = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($tokenPointer)
    if ([string]::IsNullOrWhiteSpace($botToken)) { throw "Es wurde kein Bot-Token eingegeben." }
    Read-Host "Nachricht an den Bot gesendet? Weiter mit Enter"
    $updates = Invoke-RestMethod -Method Get -Uri "https://api.telegram.org/bot$botToken/getUpdates" -TimeoutSec 15
    $chat = @($updates.result | ForEach-Object { $_.message.chat } | Where-Object { $_.type -eq "private" }) | Select-Object -Last 1
    if ($null -eq $chat -or [string]::IsNullOrWhiteSpace([string]$chat.id)) {
        throw "Keine private /start-Nachricht gefunden. Bitte erneut ausführen."
    }

    $lines = @(Get-Content -LiteralPath $configPath)
    function Set-ServerValue([string]$Name, [string]$Value) {
        $script:lines = @($script:lines | ForEach-Object {
            if ($_ -match "^$([regex]::Escape($Name))=") { "$Name=$Value" } else { $_ }
        })
        if (-not ($script:lines | Where-Object { $_ -match "^$([regex]::Escape($Name))=" })) {
            $script:lines += "$Name=$Value"
        }
    }

    Set-ServerValue "NCC_SERVER_TELEGRAM_ENABLED" "true"
    Set-ServerValue "NCC_SERVER_TELEGRAM_BOT_TOKEN" $botToken
    Set-ServerValue "NCC_SERVER_TELEGRAM_CHAT_ID" ([string]$chat.id)
    Set-Content -LiteralPath $configPath -Value $lines -Encoding utf8
    Restart-Service -Name "NccServer" -ErrorAction Stop
    Write-Host "[NCC] Telegram-Warnungen sind eingerichtet. Der Bot-Token wurde nicht angezeigt."
} finally {
    if ($tokenPointer -ne [IntPtr]::Zero) { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($tokenPointer) }
    Remove-Variable botToken -ErrorAction SilentlyContinue
}
