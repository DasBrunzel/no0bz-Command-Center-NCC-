from __future__ import annotations

from datetime import datetime
from html import escape

import httpx

from ncc_server import __version__
from ncc_server.alert_service import AlertNotification
from ncc_server.config import ServerSettings


_KIND_LABELS = {
    "offline": "Verbindung verloren",
    "cpu": "CPU-Auslastung",
    "memory": "RAM-Auslastung",
    "gpu": "GPU-Auslastung",
    "disk": "Laufwerksauslastung",
    "agent-no-telemetry": "Keine aktuelle Telemetrie",
    "agent-outdated": "Agent-Update erforderlich",
    "agent-duplicate": "Doppelte Telemetrie",
    "agent-network-outlier": "Unplausible Netzwerkzähler",
    "unraid-array": "Unraid-Array",
    "cpu-temperature": "CPU-Temperatur",
}


def format_telegram_alert(notification: AlertNotification, now: datetime | None = None) -> str:
    """Render one concise, readable Telegram HTML notification."""
    timestamp = (now or datetime.now().astimezone()).strftime("%d.%m.%Y · %H:%M")
    resolved = notification.state == "resolved"
    if resolved:
        heading = "✅ <b>NCC ENTWARNUNG</b>"
        priority = "Behoben"
    elif notification.severity == "critical":
        heading = "🔴 <b>NCC KRITISCHE WARNUNG</b>"
        priority = "Kritisch"
    else:
        heading = "🟠 <b>NCC WARNUNG</b>"
        priority = "Warnung"
    event = _KIND_LABELS.get(notification.kind, notification.kind.replace("-", " ").title())
    prefix = f"{notification.node_name}: "
    detail = notification.message.removeprefix(prefix)
    return "\n".join(
        (
            heading,
            "",
            f"🖥 <b>System:</b> {escape(notification.node_name)}",
            f"📌 <b>Ereignis:</b> {escape(event)}",
            f"⚑ <b>Status:</b> {priority}",
            f"💬 {escape(detail)}",
            "",
            f"🕒 {timestamp} · NCC {__version__}",
        )
    )


async def send_telegram_alert(settings: ServerSettings, notification: AlertNotification) -> bool:
    token = settings.telegram_bot_token.get_secret_value()
    chat_id = settings.telegram_chat_id.strip()
    if not settings.telegram_enabled or not token or not chat_id:
        return False
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={
                    "chat_id": chat_id,
                    "text": format_telegram_alert(notification),
                    "parse_mode": "HTML",
                    "disable_web_page_preview": True,
                },
            )
        return response.is_success
    except httpx.HTTPError:
        return False
