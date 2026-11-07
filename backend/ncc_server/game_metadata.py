"""Fetch artwork and store details for detected games.

Only the server talks to the Steam store (and, with an API key, SteamGridDB)
and only with a game title or app id, never with device data. Images are
stored in the database and served by NCC itself, so the dashboard never loads
third-party content. A banner uploaded in the dashboard is never replaced.
"""

from __future__ import annotations

import logging
from datetime import timedelta
from urllib.parse import quote, urlparse

import httpx
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, undefer

from ncc_server.database import Database
from ncc_server.game_service import normalized_title
from ncc_server.models import Game, utc_now

logger = logging.getLogger(__name__)
STORE_SEARCH_URL = "https://store.steampowered.com/api/storesearch/"
APP_DETAILS_URL = "https://store.steampowered.com/api/appdetails"
ALLOWED_IMAGE_HOSTS = (".steamstatic.com", ".steampowered.com", ".akamaihd.net")
STEAMGRIDDB_URL = "https://www.steamgriddb.com/api/v2"
STEAMGRIDDB_IMAGE_HOSTS = (".steamgriddb.com",)
# Banners in the Steam header format, so they look like the other cards.
STEAMGRIDDB_DIMENSIONS = "920x430,460x215"
STEAMGRIDDB_RECHECK = timedelta(days=7)
STEAMGRIDDB_CANDIDATES = 3
MAX_IMAGE_BYTES = 2 * 1024 * 1024
MAX_ATTEMPTS = 3
RETRY_AFTER = timedelta(hours=6)
BATCH_SIZE = 5


async def refresh_game_metadata(
    database: Database,
    transport: httpx.AsyncBaseTransport | None = None,
    steamgriddb_key: str = "",
) -> int:
    """Fetch details for a few pending games; return how many were completed."""
    with database.session() as session:
        pending = _pending_ids(session)
        artwork_pending = _artwork_pending_ids(session) if steamgriddb_key else []
    if not pending and not artwork_pending:
        return 0
    completed = 0
    async with httpx.AsyncClient(timeout=15, transport=transport, headers={"User-Agent": "no0bz-ncc-server"}) as client:
        for game_id in pending:
            with database.session() as session:
                game = session.get(Game, game_id, options=[undefer(Game.header_image)])
                if game is None:
                    continue
                try:
                    await _fetch(client, game)
                    completed += 1
                except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
                    game.metadata_attempts += 1
                    logger.info("Game details for %s not available yet: %s", game.title, exc)
                game.metadata_checked_at = utc_now()
                session.commit()
        for game_id in artwork_pending:
            with database.session() as session:
                game = session.get(Game, game_id, options=[undefer(Game.header_image)])
                if game is None:
                    continue
                checked_at = utc_now()
                try:
                    if await _steamgriddb_banner(client, game, steamgriddb_key):
                        completed += 1
                except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
                    # Try again after the usual retry delay, not only next week.
                    checked_at = checked_at - STEAMGRIDDB_RECHECK + RETRY_AFTER
                    logger.info("SteamGridDB banner for %s not available yet: %s", game.title, exc)
                game.artwork_checked_at = checked_at
                session.commit()
    return completed


def _pending_ids(session: Session) -> list[str]:
    retry_before = utc_now() - RETRY_AFTER
    return list(session.scalars(
        select(Game.id)
        .where(
            Game.match_state == "pending",
            Game.metadata_attempts < MAX_ATTEMPTS,
            or_(Game.metadata_checked_at.is_(None), Game.metadata_checked_at < retry_before),
        )
        .order_by(Game.created_at)
        .limit(BATCH_SIZE)
    ).all())


def _artwork_pending_ids(session: Session) -> list[str]:
    recheck_before = utc_now() - STEAMGRIDDB_RECHECK
    return list(session.scalars(
        select(Game.id)
        .where(
            Game.match_state == "none",
            Game.header_content_type.is_(None),
            or_(Game.artwork_source.is_(None), Game.artwork_source != "upload"),
            or_(Game.artwork_checked_at.is_(None), Game.artwork_checked_at < recheck_before),
        )
        .order_by(Game.created_at)
        .limit(BATCH_SIZE)
    ).all())


async def _fetch(client: httpx.AsyncClient, game: Game) -> None:
    app_id = game.steam_app_id
    if app_id is None:
        app_id = await _search(client, game.title)
        if app_id is None:
            # Not on Steam under this name; the dashboard shows the title only.
            game.match_state = "none"
            return
    response = await client.get(APP_DETAILS_URL, params={"appids": app_id, "l": "german", "cc": "de"})
    response.raise_for_status()
    entry = response.json()[str(app_id)]
    if not entry.get("success"):
        game.match_state = "none"
        return
    data = entry["data"]
    game.steam_app_id = app_id
    game.store_name = str(data.get("name") or "")[:256] or None
    game.description = str(data.get("short_description") or "")[:2000] or None
    game.genres = [str(item["description"])[:64] for item in data.get("genres", []) if isinstance(item, dict) and item.get("description")][:6]
    game.developers = [str(item)[:128] for item in data.get("developers", []) if item][:4]
    release = data.get("release_date")
    game.release_date = str(release.get("date"))[:64] if isinstance(release, dict) and release.get("date") else None
    image_url = data.get("header_image")
    if isinstance(image_url, str) and game.artwork_source != "upload":
        image = await _download_image(client, image_url)
        if image is not None:
            game.header_image, game.header_content_type = image
            game.artwork_source = "steam"
    game.match_state = "matched"


async def _search(client: httpx.AsyncClient, title: str) -> int | None:
    response = await client.get(STORE_SEARCH_URL, params={"term": title, "l": "german", "cc": "DE"})
    response.raise_for_status()
    wanted = normalized_title(title)
    for item in response.json().get("items", []):
        # Only an exact name match; a near miss would show the wrong cover.
        if isinstance(item, dict) and normalized_title(str(item.get("name", ""))) == wanted and isinstance(item.get("id"), int):
            return int(item["id"])
    return None


async def _steamgriddb_banner(client: httpx.AsyncClient, game: Game, api_key: str) -> bool:
    """Store a SteamGridDB banner for a game that has no Steam match."""
    headers = {"Authorization": f"Bearer {api_key}"}
    response = await client.get(f"{STEAMGRIDDB_URL}/search/autocomplete/{quote(game.title, safe='')}", headers=headers)
    response.raise_for_status()
    wanted = normalized_title(game.title)
    grid_game = next((
        item["id"] for item in response.json().get("data") or []
        # Only an exact name match; a near miss would show the wrong banner.
        if isinstance(item, dict) and isinstance(item.get("id"), int)
        and normalized_title(str(item.get("name", ""))) == wanted
    ), None)
    if grid_game is None:
        return False
    response = await client.get(f"{STEAMGRIDDB_URL}/grids/game/{grid_game}", headers=headers, params={
        "dimensions": STEAMGRIDDB_DIMENSIONS, "types": "static", "nsfw": "false", "humor": "false", "epilepsy": "false",
    })
    response.raise_for_status()
    grids = [item for item in response.json().get("data") or [] if isinstance(item, dict)]
    grids.sort(key=lambda item: item["score"] if isinstance(item.get("score"), int) else 0, reverse=True)
    for grid in grids[:STEAMGRIDDB_CANDIDATES]:
        for url in (grid.get("url"), grid.get("thumb")):
            if not isinstance(url, str):
                continue
            image = await _download_image(client, url, STEAMGRIDDB_IMAGE_HOSTS)
            if image is not None:
                game.header_image, game.header_content_type = image
                game.artwork_source = "steamgriddb"
                return True
    return False


async def _download_image(
    client: httpx.AsyncClient, url: str, allowed_hosts: tuple[str, ...] = ALLOWED_IMAGE_HOSTS
) -> tuple[bytes, str] | None:
    parsed = urlparse(url)
    if parsed.scheme != "https" or not (parsed.hostname or "").endswith(allowed_hosts):
        return None
    response = await client.get(url)
    response.raise_for_status()
    content_type = response.headers.get("content-type", "").split(";")[0].strip()
    if content_type not in {"image/jpeg", "image/png", "image/webp"} or len(response.content) > MAX_IMAGE_BYTES:
        return None
    return response.content, content_type
