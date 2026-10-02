from __future__ import annotations

import httpx

from ncc_server.config import ServerSettings


async def send_telegram_alert(settings: ServerSettings, message: str) -> bool:
    token = settings.telegram_bot_token.get_secret_value()
    chat_id = settings.telegram_chat_id.strip()
    if not settings.telegram_enabled or not token or not chat_id:
        return False
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": chat_id, "text": f"NCC-Warnung\n{message}"},
            )
        return response.is_success
    except httpx.HTTPError:
        return False
