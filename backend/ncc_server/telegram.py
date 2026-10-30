from __future__ import annotations

from datetime import datetime
from html import escape

import httpx
from sqlalchemy.orm import Session

from ncc_server import __version__
from ncc_server.alert_service import AlertNotification
from ncc_server.config import ServerSettings
from ncc_server.models import TelegramNotificationSettings, utc_now

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
    "gpu-temperature": "GPU-Temperatur",
}


def telegram_is_configured(settings: ServerSettings) -> bool:
    """The server owner's own chat from server.env is set up."""
    return bool(telegram_bot_available(settings) and settings.telegram_chat_id.strip())


def telegram_bot_available(settings: ServerSettings) -> bool:
    """Accounts can link their own chats; no server-owner chat needed."""
    return bool(settings.telegram_enabled and settings.telegram_bot_token.get_secret_value())


def get_telegram_settings(session: Session) -> TelegramNotificationSettings:
    preferences = session.get(TelegramNotificationSettings, "default")
    if preferences is None:
        preferences = TelegramNotificationSettings(id="default")
        session.add(preferences)
        session.commit()
    return preferences


def update_telegram_settings(
    session: Session, values: dict[str, object]
) -> TelegramNotificationSettings:
    preferences = get_telegram_settings(session)
    for name, value in values.items():
        setattr(preferences, name, value)
    preferences.updated_at = utc_now()
    session.commit()
    session.refresh(preferences)
    return preferences


def format_telegram_alert(
    notification: AlertNotification,
    preferences: TelegramNotificationSettings | None = None,
    now: datetime | None = None,
) -> str:
    """Render one concise, readable Telegram HTML notification."""
    timestamp = (now or datetime.now().astimezone()).strftime("%d.%m.%Y · %H:%M")
    resolved = notification.state == "resolved"
    if resolved:
        title = preferences.resolved_title if preferences else "NCC ENTWARNUNG"
        heading = f"✅ <b>{escape(title)}</b>"
        priority = "Behoben"
    elif notification.severity == "critical":
        title = preferences.critical_title if preferences else "NCC KRITISCHE WARNUNG"
        heading = f"🔴 <b>{escape(title)}</b>"
        priority = "Kritisch"
    else:
        title = preferences.warning_title if preferences else "NCC WARNUNG"
        heading = f"🟠 <b>{escape(title)}</b>"
        priority = "Warnung"
    if notification.kind.startswith(("drive-temperature-", "disk-temperature-")):
        event = "Laufwerkstemperatur"
    else:
        event = _KIND_LABELS.get(notification.kind, notification.kind.replace("-", " ").title())
    prefix = f"{notification.node_name}: "
    detail = notification.message.removeprefix(prefix)
    footer = preferences.footer if preferences else "NCC {version}"
    footer = footer.replace("{version}", __version__).replace("{time}", timestamp)
    return "\n".join(
        (
            heading,
            "",
            f"🖥 <b>System:</b> {escape(notification.node_name)}",
            f"📌 <b>Ereignis:</b> {escape(event)}",
            f"⚑ <b>Status:</b> {priority}",
            f"💬 {escape(detail)}",
            "",
            f"🕒 {escape(footer)}",
        )
    )


async def send_telegram_alert(
    settings: ServerSettings,
    notification: AlertNotification,
    preferences: TelegramNotificationSettings | None = None,
    chat_id: str | None = None,
) -> bool:
    """Send to the given chat, or to the server owner's chat from server.env."""
    target = chat_id or settings.telegram_chat_id.strip()
    if not telegram_bot_available(settings) or not target:
        return False
    return await send_telegram_message(settings, target, format_telegram_alert(notification, preferences))


async def send_telegram_message(
    settings: ServerSettings, chat_id: str, text: str, transport: httpx.AsyncBaseTransport | None = None,
) -> bool:
    token = settings.telegram_bot_token.get_secret_value()
    try:
        async with httpx.AsyncClient(timeout=10.0, transport=transport) as client:
            response = await client.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": chat_id, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True},
            )
        return response.is_success
    except httpx.HTTPError:
        return False
