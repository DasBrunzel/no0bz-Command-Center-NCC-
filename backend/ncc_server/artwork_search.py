"""Manual banner search on SteamGridDB for commanders.

The server searches, downloads previews and the chosen banner itself; the
dashboard only ever loads images from NCC (its CSP allows no other hosts).
Candidate URLs stay on the server in a short-lived cache, so a client can only
pick from what SteamGridDB returned, never pass an arbitrary URL.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from urllib.parse import quote

import httpx

from ncc_server.game_metadata import (
    STEAMGRIDDB_DIMENSIONS,
    STEAMGRIDDB_IMAGE_HOSTS,
    STEAMGRIDDB_URL,
    _download_image,
)

CACHE_SECONDS = 15 * 60
MAX_GAMES = 3
MAX_CANDIDATES = 12


@dataclass
class Candidate:
    game_name: str
    url: str
    thumb: str | None
    width: int | None
    height: int | None
    style: str | None
    preview: tuple[bytes, str] | None = None


@dataclass
class SearchResult:
    expires: float
    candidates: list[Candidate] = field(default_factory=list)


class ArtworkSearchCache:
    """Per-game search results for the last few minutes (process memory only)."""

    def __init__(self) -> None:
        self._entries: dict[str, SearchResult] = {}

    def put(self, game_id: str, candidates: list[Candidate]) -> None:
        now = time.monotonic()
        self._entries = {key: value for key, value in self._entries.items() if value.expires > now}
        self._entries[game_id] = SearchResult(now + CACHE_SECONDS, candidates)

    def get(self, game_id: str, index: int) -> Candidate | None:
        entry = self._entries.get(game_id)
        if entry is None or entry.expires <= time.monotonic() or not 0 <= index < len(entry.candidates):
            return None
        return entry.candidates[index]


async def search_candidates(client: httpx.AsyncClient, query: str, api_key: str) -> list[Candidate]:
    """Banner candidates for the best few name matches, best rated first."""
    headers = {"Authorization": f"Bearer {api_key}"}
    response = await client.get(f"{STEAMGRIDDB_URL}/search/autocomplete/{quote(query, safe='')}", headers=headers)
    response.raise_for_status()
    games = [
        item for item in response.json().get("data") or []
        if isinstance(item, dict) and isinstance(item.get("id"), int)
    ][:MAX_GAMES]
    candidates: list[Candidate] = []
    for game in games:
        grids = await client.get(f"{STEAMGRIDDB_URL}/grids/game/{game['id']}", headers=headers, params={
            "dimensions": STEAMGRIDDB_DIMENSIONS, "types": "static", "nsfw": "false", "humor": "false", "epilepsy": "false",
        })
        grids.raise_for_status()
        items = [item for item in grids.json().get("data") or [] if isinstance(item, dict) and isinstance(item.get("url"), str)]
        items.sort(key=lambda item: item["score"] if isinstance(item.get("score"), int) else 0, reverse=True)
        for item in items:
            candidates.append(Candidate(
                game_name=str(game.get("name") or query)[:128],
                url=item["url"],
                thumb=item["thumb"] if isinstance(item.get("thumb"), str) else None,
                width=item["width"] if isinstance(item.get("width"), int) else None,
                height=item["height"] if isinstance(item.get("height"), int) else None,
                style=str(item["style"])[:32] if item.get("style") else None,
            ))
            if len(candidates) >= MAX_CANDIDATES:
                return candidates
    return candidates


async def preview(client: httpx.AsyncClient, candidate: Candidate) -> tuple[bytes, str] | None:
    if candidate.preview is None:
        for url in (candidate.thumb, candidate.url):
            if url and (image := await _download_image(client, url, STEAMGRIDDB_IMAGE_HOSTS)) is not None:
                candidate.preview = image
                break
    return candidate.preview


async def full_image(client: httpx.AsyncClient, candidate: Candidate) -> tuple[bytes, str] | None:
    """The full banner, or the thumbnail when the full image is too large."""
    for url in (candidate.url, candidate.thumb):
        if url and (image := await _download_image(client, url, STEAMGRIDDB_IMAGE_HOSTS)) is not None:
            return image
    return None
