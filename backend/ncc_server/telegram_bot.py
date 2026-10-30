"""The NCC Telegram bot: linking accounts, delivering alerts, weekly recaps.

The server owner's chat from server.env keeps receiving everything. Any
dashboard account can additionally link its own chat: it asks the dashboard
for a short code and sends it to the bot. A friend's chat then receives the
alerts and the weekly recap of their own devices only.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import secrets
from datetime import datetime, timedelta, timezone
from html import escape

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from ncc_server.alert_service import AlertNotification
from ncc_server.config import ServerSettings
from ncc_server.database import Database
from ncc_server.game_service import playtime_statistics
from ncc_server.hardware_stats import hardware_statistics
from ncc_server.models import (
    AuditEvent,
    Node,
    TelegramBotState,
    TelegramLink,
    TelegramLinkCode,
    User,
    utc_now,
)
from ncc_server.telegram import send_telegram_message, telegram_bot_available

logger = logging.getLogger(__name__)
LINK_LIFETIME = timedelta(minutes=15)
CODE_PATTERN = re.compile(r"^[A-Z0-9]{10}$")
RECAP_WEEKDAY, RECAP_HOUR = 0, 9  # Monday, 09:00 server time
_bot_username: str | None = None


def create_link_code(session: Session, user_id: str) -> tuple[str, datetime]:
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    code = "".join(secrets.choice(alphabet) for _ in range(10))
    expires = utc_now() + LINK_LIFETIME
    # One open code per account; asking again replaces it.
    for old in session.scalars(select(TelegramLinkCode).where(TelegramLinkCode.user_id == user_id)):
        session.delete(old)
    session.add(TelegramLinkCode(user_id=user_id, code_hash=_digest(code), expires_at=expires))
    session.commit()
    return code, expires


def link_chat(session: Session, code: str, chat_id: str, telegram_name: str | None) -> User | None:
    record = session.scalar(select(TelegramLinkCode).where(TelegramLinkCode.code_hash == _digest(code.upper())))
    if record is None or _aware(record.expires_at) <= utc_now():
        return None
    user = session.get(User, record.user_id)
    session.delete(record)
    if user is None or not user.active:
        session.commit()
        return None
    # A chat belongs to one account, and an account to one chat.
    for other in session.scalars(select(TelegramLink).where(TelegramLink.chat_id == chat_id, TelegramLink.user_id != user.id)):
        session.delete(other)
    link = session.scalar(select(TelegramLink).where(TelegramLink.user_id == user.id))
    if link is None:
        link = TelegramLink(user_id=user.id, chat_id=chat_id)
        session.add(link)
    link.chat_id, link.telegram_name, link.linked_at = chat_id, (telegram_name or "")[:128] or None, utc_now()
    session.add(AuditEvent(actor_type="telegram", actor_id=user.id, action="telegram.linked"))
    session.commit()
    return user


def unlink_user(session: Session, user_id: str) -> None:
    link = session.scalar(select(TelegramLink).where(TelegramLink.user_id == user_id))
    if link is not None:
        session.delete(link)
        session.add(AuditEvent(actor_type="dashboard-user", actor_id=user_id, action="telegram.unlinked"))
        session.commit()


def alert_recipients(session: Session, settings: ServerSettings, notification: AlertNotification) -> list[str]:
    """Chats for one alert: the server owner's, plus linked accounts that may see the device."""
    chats: list[str] = []
    if settings.telegram_chat_id.strip():
        chats.append(settings.telegram_chat_id.strip())
    rows = session.execute(select(TelegramLink, User).join(User, User.id == TelegramLink.user_id).where(User.active.is_(True))).all()
    for link, user in rows:
        if user.role == "friend" and notification.owner_user_id != user.id:
            continue
        if link.chat_id not in chats:
            chats.append(link.chat_id)
    return chats


async def bot_username(settings: ServerSettings, transport: httpx.AsyncBaseTransport | None = None) -> str | None:
    global _bot_username
    if _bot_username or not telegram_bot_available(settings):
        return _bot_username
    try:
        async with httpx.AsyncClient(timeout=10.0, transport=transport) as client:
            response = await client.get(f"https://api.telegram.org/bot{settings.telegram_bot_token.get_secret_value()}/getMe")
        username = response.json().get("result", {}).get("username")
        _bot_username = str(username) if username else None
    except (httpx.HTTPError, ValueError):
        return None
    return _bot_username


async def poll_updates(database: Database, settings: ServerSettings, transport: httpx.AsyncBaseTransport | None = None, timeout: int = 25) -> int:
    """Handle new bot messages once; long-polls for up to ``timeout`` seconds."""
    with database.session() as session:
        offset = _state(session).update_offset
    async with httpx.AsyncClient(timeout=timeout + 10, transport=transport) as client:
        response = await client.get(
            f"https://api.telegram.org/bot{settings.telegram_bot_token.get_secret_value()}/getUpdates",
            params={"offset": offset, "timeout": timeout, "allowed_updates": json.dumps(["message"])},
        )
    updates = response.json().get("result", []) if response.is_success else []
    for update in updates:
        reply = None
        with database.session() as session:
            state = _state(session)
            state.update_offset = max(state.update_offset, int(update.get("update_id", 0)) + 1)
            session.commit()
            message = update.get("message") or {}
            chat = message.get("chat") or {}
            text = str(message.get("text") or "").strip()
            # Links only from private chats; a group must not collect someone's alerts.
            if chat.get("type") == "private" and text:
                reply = _handle_message(session, str(chat.get("id")), _display_name(message.get("from") or {}), text)
        if reply:
            await send_telegram_message(settings, str(chat.get("id")), reply, transport)
    return len(updates)


def _handle_message(session: Session, chat_id: str, name: str | None, text: str) -> str:
    command, _, argument = text.partition(" ")
    command = command.split("@")[0].lower()
    if command == "/stop":
        link = session.scalar(select(TelegramLink).where(TelegramLink.chat_id == chat_id))
        if link is None:
            return "Dieser Chat ist mit keinem NCC-Konto verbunden."
        unlink_user(session, link.user_id)
        return "Verbindung getrennt. Du bekommst keine NCC-Nachrichten mehr."
    code = argument.strip().upper() if command == "/start" else text.strip().upper()
    if CODE_PATTERN.match(code):
        user = link_chat(session, code, chat_id, name)
        if user is None:
            return "Der Code ist ungültig oder abgelaufen. Erzeuge im Dashboard unter Einstellungen → Telegram einen neuen."
        scope = "deiner Geräte" if user.role == "friend" else "aller Geräte"
        return f"✅ Verbunden mit dem NCC-Konto <b>{escape(user.username)}</b>. Du bekommst jetzt die Warnungen {scope} und montags einen Wochenrückblick.\n\n/stop trennt die Verbindung."
    return "Hallo! Ich bin der NCC-Bot. Öffne im NCC-Dashboard Einstellungen → Telegram, erzeuge einen Code und schick ihn mir."


def weekly_recap_due(now: datetime, last_week: str | None) -> str | None:
    """Return the ISO week to send for, once per week from Monday 09:00."""
    if now.weekday() < RECAP_WEEKDAY or (now.weekday() == RECAP_WEEKDAY and now.hour < RECAP_HOUR):
        return None
    year, week, _ = now.isocalendar()
    key = f"{year}-W{week:02d}"
    return key if key != last_week else None


def recap_text(session: Session, node_ids: set[str] | None, utc_offset_minutes: int) -> str | None:
    playtime = playtime_statistics(session, days=7, node_id=None, utc_offset_minutes=utc_offset_minutes, node_ids=node_ids)
    hardware = hardware_statistics(session, days=7, node_id=None, utc_offset_minutes=utc_offset_minutes, node_ids=node_ids)
    if not playtime["total_seconds"] and not hardware["hours_covered"]:
        return None
    lines = ["📊 <b>NCC Wochenrückblick</b>", ""]
    if playtime["total_seconds"]:
        top = playtime["games"][0]
        lines.append(f"🎮 <b>Spielzeit:</b> {_hours(playtime['total_seconds'])} in {playtime['session_count']} {'Sitzung' if playtime['session_count'] == 1 else 'Sitzungen'}")
        if top.get("title"):
            lines.append(f"🏆 <b>Meistgespielt:</b> {escape(top['title'])} ({_hours(top['seconds'])})")
    else:
        lines.append("🎮 Diese Woche wurde nicht gespielt.")
    for metric, label in (("cpu_temperature_c", "Heißeste CPU"), ("gpu_temperature_c", "Heißeste GPU"), ("drive_temperature_c", "Heißeste SSD")):
        record = hardware["records"].get(metric)
        if record:
            device = f" auf {escape(record['node_name'])}" if record.get("node_name") else ""
            lines.append(f"🌡 <b>{label}:</b> {record['value']:.0f} °C{device}")
    if hardware["energy_wh"]:
        lines.append(f"⚡ <b>Energie CPU + GPU:</b> {hardware['energy_wh'] / 1000:.1f} kWh")
    return "\n".join(lines)


async def send_weekly_recaps(database: Database, settings: ServerSettings, now: datetime | None = None,
                             transport: httpx.AsyncBaseTransport | None = None) -> int:
    local = now or datetime.now().astimezone()
    offset = int((local.utcoffset() or timedelta(0)).total_seconds() // 60)
    with database.session() as session:
        state = _state(session)
        week = weekly_recap_due(local, state.last_recap_week)
        if week is None:
            return 0
        # Mark first: a crash must not resend the recap every minute.
        state.last_recap_week = week
        session.commit()
        messages: list[tuple[str, str]] = []
        owner_chat = settings.telegram_chat_id.strip()
        if owner_chat:
            text = recap_text(session, None, offset)
            if text:
                messages.append((owner_chat, text))
        rows = session.execute(select(TelegramLink, User).join(User, User.id == TelegramLink.user_id)
                               .where(User.active.is_(True), TelegramLink.weekly_recap.is_(True))).all()
        for link, user in rows:
            if link.chat_id == owner_chat or any(chat == link.chat_id for chat, _ in messages):
                continue
            scope = set(session.scalars(select(Node.id).where(Node.owner_user_id == user.id)).all()) if user.role == "friend" else None
            text = recap_text(session, scope, offset)
            if text:
                messages.append((link.chat_id, text))
    sent = 0
    for chat_id, text in messages:
        sent += await send_telegram_message(settings, chat_id, text, transport)
    return sent


def _state(session: Session) -> TelegramBotState:
    state = session.get(TelegramBotState, "default")
    if state is None:
        state = TelegramBotState(id="default", update_offset=0)
        session.add(state)
        session.flush()
    return state


def _display_name(sender: dict[str, object]) -> str | None:
    username = sender.get("username")
    if isinstance(username, str) and username:
        return f"@{username}"
    first = sender.get("first_name")
    return str(first) if first else None


def _hours(seconds: float) -> str:
    hours = seconds / 3600
    return f"{hours:.1f} Std.".replace(".", ",") if hours >= 1 else f"{round(seconds / 60)} Min."


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _aware(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value
